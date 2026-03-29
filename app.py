from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests, json

from database import init_db, get_conn
from models import *
from auth import *

from fastapi import UploadFile, File
import shutil
import os

from logging_config import get_logger, clip_text

RAG_AVAILABLE = True
RAG_IMPORT_ERROR = ""
try:
    from rag.ingest import ingest_file, ingest_directory
    from rag.query import build_rag_context
except Exception as exc:
    RAG_AVAILABLE = False
    RAG_IMPORT_ERROR = str(exc)

OLLAMA = "http://127.0.0.1:11434"
logger = get_logger("app")

app = FastAPI()

# ✅ Proper DB init
@app.on_event("startup")
def startup():
    logger.info("Application startup initiated.")
    init_db()
    logger.info("Database initialized. RAG available=%s error=%s", RAG_AVAILABLE, RAG_IMPORT_ERROR)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- MODELS ----------
@app.get("/models")
def models():
    logger.info("Fetching models from Ollama.")
    try:
        data = requests.get(f"{OLLAMA}/api/tags").json()
        logger.info("Models fetched successfully. Count=%s", len(data.get("models", [])))
        return data
    except Exception as exc:
        logger.exception("Failed to fetch models: %s", exc)
        return {"models": []}


# ---------- PAGES ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return RedirectResponse(url="/login", status_code=302)


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

#@app.get("/login", response_class=HTMLResponse)
#def login_page(request: Request):
#    return templates.TemplateResponse("login.html", {"request": request})
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# ---------- AUTH ----------
@app.post("/signup")
def signup(user: UserCreate):
    logger.info("Signup attempt username=%s", user.username)
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users(username, password) VALUES (?, ?)",
            (user.username, hash_password(user.password))
        )
        conn.commit()
        logger.info("Signup success username=%s", user.username)
    except Exception as e:
        logger.exception("Signup failed username=%s error=%s", user.username, e)
        raise HTTPException(400, "Username already exists")

    conn.close()
    return {"status": "created"}


@app.post("/login")
def login(user: UserLogin):
    logger.info("Login attempt username=%s", user.username)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, password FROM users WHERE username=?", (user.username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        logger.warning("Login failed (unknown user) username=%s", user.username)
        raise HTTPException(401, "Invalid credentials")

    user_id, hashed = row

    if not verify_password(user.password, hashed):
        logger.warning("Login failed (bad password) username=%s", user.username)
        raise HTTPException(401, "Invalid credentials")

    logger.info("Login success username=%s user_id=%s", user.username, user_id)
    return {"token": create_token(user_id)}


# ---------- CONVERSATIONS ----------
@app.get("/conversations")
def conversations(user_id: int = Depends(get_current_user)):
    logger.info("List conversations user_id=%s", user_id)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, title FROM conversations WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()

    conn.close()
    logger.info("Conversations fetched user_id=%s count=%s", user_id, len(rows))
    return [{"id": r[0], "title": r[1]} for r in rows]


@app.post("/conversations")
def new_chat(data: ConversationCreate, user_id: int = Depends(get_current_user)):
    logger.info("Create conversation requested user_id=%s title=%s", user_id, data.title)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO conversations(user_id, title) VALUES (?, ?)", (user_id, data.title))
    conn.commit()

    cid = cur.lastrowid
    conn.close()

    logger.info("Conversation created user_id=%s conversation_id=%s title=%s", user_id, cid, data.title)
    return {"id": cid}


# ---------- CHAT ----------
@app.post("/chat-stream")
def chat(req: ChatRequest, user_id: int = Depends(get_current_user)):
    logger.info(
        "Chat request start user_id=%s conversation_id=%s model=%s use_rag=%s prompt=%s",
        user_id,
        req.conversation_id,
        req.model,
        req.use_rag,
        clip_text(req.prompt),
    )
    conn = get_conn()
    cur = conn.cursor()

    # Save user message
    cur.execute(
        "INSERT INTO messages(conversation_id, role, content) VALUES (?, 'user', ?)",
        (req.conversation_id, req.prompt)
    )
    conn.commit()

    cur.execute(
        "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id",
        (req.conversation_id,)
    )
    msgs = [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    logger.info("Conversation history loaded conversation_id=%s message_count=%s", req.conversation_id, len(msgs))

    if req.use_rag and RAG_AVAILABLE:
        logger.info("RAG context build requested conversation_id=%s", req.conversation_id)
        context = build_rag_context(req.prompt)
        if context:
            logger.info("RAG context added conversation_id=%s context_chars=%s", req.conversation_id, len(context))
            msgs.insert(0, {
                "role": "system",
                "content": (
                    "Use the reference context below when relevant. "
                    "If context is not sufficient, say so.\n\n"
                    f"{context}"
                )
            })
        else:
            logger.info("RAG context empty conversation_id=%s", req.conversation_id)
    elif req.use_rag and not RAG_AVAILABLE:
        logger.warning("RAG requested but unavailable. error=%s", RAG_IMPORT_ERROR)

    logger.info("Sending chat request to Ollama model=%s conversation_id=%s", req.model, req.conversation_id)
    r = requests.post(f"{OLLAMA}/api/chat", json={
        "model": req.model,
        "messages": msgs,
        "stream": True
    }, stream=True)
    logger.info("Ollama response stream opened status_code=%s", r.status_code)

    def stream():
        full = ""
        logger.info("Streaming response started conversation_id=%s", req.conversation_id)
        try:
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line.decode())
                if "message" in data:
                    chunk = data["message"]["content"]
                    full += chunk
                    yield chunk
        finally:
            try:
                cur.execute(
                    "INSERT INTO messages(conversation_id, role, content) VALUES (?, 'assistant', ?)",
                    (req.conversation_id, full)
                )
                conn.commit()
                logger.info(
                    "Assistant response stored conversation_id=%s response_chars=%s response=%s",
                    req.conversation_id,
                    len(full),
                    clip_text(full),
                )
            finally:
                conn.close()
                logger.info("Streaming response finished conversation_id=%s", req.conversation_id)

    return StreamingResponse(stream(), media_type="text/plain")


# ---------- RENAME ----------
@app.put("/conversations/{cid}")
def rename_chat(cid: int, data: ConversationCreate, user_id: int = Depends(get_current_user)):
    logger.info("Rename conversation requested user_id=%s conversation_id=%s new_title=%s", user_id, cid, data.title)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (cid, user_id))
    if not cur.fetchone():
        raise HTTPException(404, "Not found")

    cur.execute("UPDATE conversations SET title=? WHERE id=?", (data.title, cid))
    conn.commit()
    conn.close()

    logger.info("Conversation renamed user_id=%s conversation_id=%s new_title=%s", user_id, cid, data.title)
    return {"status": "updated"}


# ---------- DELETE ----------
@app.delete("/conversations/{cid}")
def delete_chat(cid: int, user_id: int = Depends(get_current_user)):
    logger.info("Delete conversation requested user_id=%s conversation_id=%s", user_id, cid)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (cid, user_id))
    if not cur.fetchone():
        raise HTTPException(404, "Not found")

    cur.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    cur.execute("DELETE FROM conversations WHERE id=?", (cid,))

    conn.commit()
    conn.close()

    logger.info("Conversation deleted user_id=%s conversation_id=%s", user_id, cid)
    return {"status": "deleted"}


# ---------- GET MESSAGES ----------
@app.get("/messages/{cid}")
def get_messages(cid: int, user_id: int = Depends(get_current_user)):
    logger.info("Get messages requested user_id=%s conversation_id=%s", user_id, cid)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id", (cid,))
    rows = cur.fetchall()

    conn.close()
    logger.info("Messages fetched conversation_id=%s count=%s", cid, len(rows))
    return [{"role": r[0], "content": r[1]} for r in rows]


# ---------- UPLOAD ----------
@app.post("/upload")
def upload_file(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    logger.info("Upload requested user_id=%s filename=%s", user_id, file.filename)
    if not RAG_AVAILABLE:
        logger.error("Upload rejected: RAG unavailable error=%s", RAG_IMPORT_ERROR)
        raise HTTPException(500, f"RAG is unavailable: {RAG_IMPORT_ERROR}")

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    logger.info("File stored at path=%s", file_path)

    chunks, status = ingest_file(file_path)
    if chunks == 0 and status != "ok":
        logger.warning("Ingest failed filename=%s status=%s", file.filename, status)
        raise HTTPException(400, status)

    logger.info("Upload ingest success filename=%s chunks=%s", file.filename, chunks)
    return {"status": "uploaded", "chunks": chunks, "file": file.filename}


@app.post("/upload-directory")
def upload_directory(data: DirectoryIngestRequest, user_id: int = Depends(get_current_user)):
    logger.info("Directory ingest requested user_id=%s path=%s", user_id, data.path)
    if not RAG_AVAILABLE:
        logger.error("Directory ingest rejected: RAG unavailable error=%s", RAG_IMPORT_ERROR)
        raise HTTPException(500, f"RAG is unavailable: {RAG_IMPORT_ERROR}")
    result = ingest_directory(data.path)
    logger.info(
        "Directory ingest completed path=%s files=%s chunks=%s errors=%s",
        data.path,
        result.get("ingested_files"),
        result.get("total_chunks"),
        len(result.get("errors", [])),
    )
    return result


@app.get("/rag-status")
def rag_status():
    logger.info("RAG status requested.")
    return {"available": RAG_AVAILABLE, "error": RAG_IMPORT_ERROR}
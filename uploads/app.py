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

RAG_AVAILABLE = True
RAG_IMPORT_ERROR = ""
try:
    from rag.ingest import ingest_file, ingest_directory
    from rag.query import build_rag_context
except Exception as exc:
    RAG_AVAILABLE = False
    RAG_IMPORT_ERROR = str(exc)

OLLAMA = "http://127.0.0.1:11434"

app = FastAPI()

# ✅ Proper DB init
@app.on_event("startup")
def startup():
    init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- MODELS ----------
@app.get("/models")
def models():
    try:
        return requests.get(f"{OLLAMA}/api/tags").json()
    except:
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
    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users(username, password) VALUES (?, ?)",
            (user.username, hash_password(user.password))
        )
        conn.commit()
    except Exception as e:
        print("Signup error:", e)
        raise HTTPException(400, "Username already exists")

    conn.close()
    return {"status": "created"}


@app.post("/login")
def login(user: UserLogin):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, password FROM users WHERE username=?", (user.username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(401, "Invalid credentials")

    user_id, hashed = row

    if not verify_password(user.password, hashed):
        raise HTTPException(401, "Invalid credentials")

    return {"token": create_token(user_id)}


# ---------- CONVERSATIONS ----------
@app.get("/conversations")
def conversations(user_id: int = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id, title FROM conversations WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()

    conn.close()
    return [{"id": r[0], "title": r[1]} for r in rows]


@app.post("/conversations")
def new_chat(data: ConversationCreate, user_id: int = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("INSERT INTO conversations(user_id, title) VALUES (?, ?)", (user_id, data.title))
    conn.commit()

    cid = cur.lastrowid
    conn.close()

    return {"id": cid}


# ---------- CHAT ----------
@app.post("/chat-stream")
def chat(req: ChatRequest, user_id: int = Depends(get_current_user)):
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

    if req.use_rag and RAG_AVAILABLE:
        context = build_rag_context(req.prompt)
        if context:
            msgs.insert(0, {
                "role": "system",
                "content": (
                    "Use the reference context below when relevant. "
                    "If context is not sufficient, say so.\n\n"
                    f"{context}"
                )
            })

    r = requests.post(f"{OLLAMA}/api/chat", json={
        "model": req.model,
        "messages": msgs,
        "stream": True
    }, stream=True)

    def stream():
        full = ""
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
            finally:
                conn.close()

    return StreamingResponse(stream(), media_type="text/plain")


# ---------- RENAME ----------
@app.put("/conversations/{cid}")
def rename_chat(cid: int, data: ConversationCreate, user_id: int = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (cid, user_id))
    if not cur.fetchone():
        raise HTTPException(404, "Not found")

    cur.execute("UPDATE conversations SET title=? WHERE id=?", (data.title, cid))
    conn.commit()
    conn.close()

    return {"status": "updated"}


# ---------- DELETE ----------
@app.delete("/conversations/{cid}")
def delete_chat(cid: int, user_id: int = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT id FROM conversations WHERE id=? AND user_id=?", (cid, user_id))
    if not cur.fetchone():
        raise HTTPException(404, "Not found")

    cur.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    cur.execute("DELETE FROM conversations WHERE id=?", (cid,))

    conn.commit()
    conn.close()

    return {"status": "deleted"}


# ---------- GET MESSAGES ----------
@app.get("/messages/{cid}")
def get_messages(cid: int, user_id: int = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id", (cid,))
    rows = cur.fetchall()

    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


# ---------- UPLOAD ----------
@app.post("/upload")
def upload_file(file: UploadFile = File(...), user_id: int = Depends(get_current_user)):
    if not RAG_AVAILABLE:
        raise HTTPException(500, f"RAG is unavailable: {RAG_IMPORT_ERROR}")

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    chunks, status = ingest_file(file_path)
    if chunks == 0 and status != "ok":
        raise HTTPException(400, status)

    return {"status": "uploaded", "chunks": chunks, "file": file.filename}


@app.post("/upload-directory")
def upload_directory(data: DirectoryIngestRequest, user_id: int = Depends(get_current_user)):
    if not RAG_AVAILABLE:
        raise HTTPException(500, f"RAG is unavailable: {RAG_IMPORT_ERROR}")
    return ingest_directory(data.path)


@app.get("/rag-status")
def rag_status():
    return {"available": RAG_AVAILABLE, "error": RAG_IMPORT_ERROR}
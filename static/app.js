const chat = document.getElementById("chat");
const promptBox = document.getElementById("prompt");
const modelSelect = document.getElementById("model");
const useRagCheckbox = document.getElementById("useRag");
const fileInput = document.getElementById("fileInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const uploadBtn = document.getElementById("uploadBtn");
const ingestDirBtn = document.getElementById("ingestDirBtn");
let currentAbortController = null;
let isGenerating = false;

// Redirect to login if token is missing.
(function () {
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = "/login";
  }
})();

function getAuthHeaders() {
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = "/login";
    return null;
  }

  return {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token
  };
}

async function loadModels() {
  try {
    const r = await fetch("/models");
    const data = await r.json();

    modelSelect.innerHTML = "";
    (data.models || []).forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = m.name;
      modelSelect.appendChild(opt);
    });
  } catch (e) {
    console.error("Failed to load models", e);
  }
}

loadModels();

function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = marked.parse(text || "");
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function setGeneratingState(generating) {
  isGenerating = generating;
  if (sendBtn) sendBtn.disabled = generating;
  if (stopBtn) stopBtn.disabled = !generating;
}

function stopGeneration() {
  if (currentAbortController) {
    currentAbortController.abort();
  }
}

async function send() {
  if (isGenerating) return;

  if (!currentConversation) {
    alert("Create a chat first");
    return;
  }

  const text = promptBox.value.trim();
  if (!text) return;

  const headers = getAuthHeaders();
  if (!headers) return;

  promptBox.value = "";
  addMessage(text, "user");
  const aiDiv = addMessage("", "ai");
  currentAbortController = new AbortController();
  setGeneratingState(true);

  try {
    const r = await fetch("/chat-stream", {
      method: "POST",
      headers,
      signal: currentAbortController.signal,
      body: JSON.stringify({
        model: modelSelect.value,
        prompt: text,
        conversation_id: currentConversation,
        use_rag: !!(useRagCheckbox && useRagCheckbox.checked)
      })
    });

    if (r.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
      return;
    }

    if (!r.ok || !r.body) {
      aiDiv.innerHTML = marked.parse("Error: failed to fetch AI response.");
      return;
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let full = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      full += decoder.decode(value);
      aiDiv.innerHTML = marked.parse(full);
    }

    loadConversations();
  } catch (e) {
    if (e.name === "AbortError") {
      const partial = aiDiv.textContent?.trim() || "";
      if (!partial) {
        aiDiv.innerHTML = marked.parse("_Generation stopped._");
      }
    } else {
      console.error("Chat request failed", e);
      aiDiv.innerHTML = marked.parse("Error: unable to contact server.");
    }
  } finally {
    currentAbortController = null;
    setGeneratingState(false);
  }
}

async function uploadFile() {
  if (!fileInput) return;

  if (!fileInput.files || fileInput.files.length === 0) {
    fileInput.click();
    return;
  }

  const file = fileInput.files[0];
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = "/login";
    return;
  }

  const form = new FormData();
  form.append("file", file);

  if (uploadBtn) uploadBtn.disabled = true;
  try {
    const r = await fetch("/upload", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token
      },
      body: form
    });

    const data = await r.json();
    if (!r.ok) {
      throw new Error(data.detail || "Upload failed");
    }

    alert(`Uploaded ${data.file} (${data.chunks} chunks indexed)`);
    fileInput.value = "";
  } catch (e) {
    alert(`Upload failed: ${e.message}`);
  } finally {
    if (uploadBtn) uploadBtn.disabled = false;
  }
}

if (fileInput) {
  fileInput.addEventListener("change", () => {
    if (fileInput.files && fileInput.files.length > 0) {
      uploadFile();
    }
  });
}

async function ingestDirectory() {
  const path = prompt("Enter absolute directory path to index for RAG:");
  if (!path) return;

  const headers = getAuthHeaders();
  if (!headers) return;

  if (ingestDirBtn) ingestDirBtn.disabled = true;
  try {
    const r = await fetch("/upload-directory", {
      method: "POST",
      headers,
      body: JSON.stringify({ path })
    });
    const data = await r.json();
    if (!r.ok) {
      throw new Error(data.detail || "Directory ingest failed");
    }
    alert(
      `Indexed files: ${data.ingested_files}, chunks: ${data.total_chunks}, errors: ${data.errors.length}`
    );
  } catch (e) {
    alert(`Directory ingest failed: ${e.message}`);
  } finally {
    if (ingestDirBtn) ingestDirBtn.disabled = false;
  }
}

promptBox.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
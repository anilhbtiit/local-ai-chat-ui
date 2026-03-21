let currentConversation = null;


// ---------- AUTH ----------
function getToken() {
  return localStorage.getItem("token");
}

function getAuthHeaders() {
  const token = getToken();
  if (!token) return null;

  return {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token
  };
}


// ---------- LOAD CONVERSATIONS ----------
async function loadConversations() {
  const headers = getAuthHeaders();
  if (!headers) return;

  let r = await fetch("/conversations", { headers });

  if (r.status === 401) {
    localStorage.removeItem("token");
    window.location = "/login";
    return;
  }

  let data = await r.json();

  let container = document.getElementById("conversations");
  if (!container) return;

  container.innerHTML = "";

  data.forEach(c => {
    let div = document.createElement("div");
    div.className = "chat-item";

    div.innerHTML = `
      <span onclick="loadChat(${c.id})">${c.title}</span>
      <span class="actions">
        <button onclick="renameChat(${c.id}, '${c.title.replace(/'/g, "\\'")}')">✏️</button>
        <button onclick="deleteChat(${c.id})">🗑️</button>
      </span>
    `;

    container.appendChild(div);
  });
}


// ---------- NEW CHAT ----------
async function newChat() {
  const headers = getAuthHeaders();
  if (!headers) {
    window.location = "/login";
    return;
  }

  let r = await fetch("/conversations", {
    method: "POST",
    headers,
    body: JSON.stringify({ title: "New Chat" })
  });

  if (r.status === 401) {
    localStorage.removeItem("token");
    window.location = "/login";
    return;
  }

  let data = await r.json();

  currentConversation = data.id;

  clearChat();
  loadConversations();
}


// ---------- RENAME ----------
async function renameChat(id, oldTitle) {
  const newTitle = prompt("Enter new chat name:", oldTitle);
  if (!newTitle) return;

  const headers = getAuthHeaders();
  if (!headers) return;

  let r = await fetch(`/conversations/${id}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ title: newTitle })
  });

  if (r.status === 401) {
    localStorage.removeItem("token");
    window.location = "/login";
    return;
  }

  loadConversations();
}


// ---------- DELETE ----------
async function deleteChat(id) {
  if (!confirm("Delete this chat?")) return;

  const headers = getAuthHeaders();
  if (!headers) return;

  let r = await fetch(`/conversations/${id}`, {
    method: "DELETE",
    headers
  });

  if (r.status === 401) {
    localStorage.removeItem("token");
    window.location = "/login";
    return;
  }

  if (currentConversation === id) {
    clearChat();
    currentConversation = null;
  }

  loadConversations();
}


// ---------- LOAD CHAT ----------
async function loadChat(id) {
  const headers = getAuthHeaders();
  if (!headers) return;

  currentConversation = id;

  let r = await fetch(`/messages/${id}`, { headers });

  if (r.status === 401) {
    localStorage.removeItem("token");
    window.location = "/login";
    return;
  }

  let data = await r.json();

  clearChat();

  data.forEach(m => addMessage(m.content, m.role));
}


// ---------- CLEAR ----------
function clearChat() {
  const chat = document.getElementById("chat");
  if (chat) chat.innerHTML = "";
}


// ---------- INIT ----------
window.onload = function () {
  if (document.getElementById("conversations")) {
    loadConversations();
  }
};
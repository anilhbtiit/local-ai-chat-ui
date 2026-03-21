const chat = document.getElementById("chat");
const promptBox = document.getElementById("prompt");
const modelSelect = document.getElementById("model");


// 🔐 Redirect if not logged in
(function () {
    const token = localStorage.getItem("token");
  
    if (!token) {
      window.location.href = "/login";
    }
  })();
  
// 🔐 Get token and build headers
function getAuthHeaders() {
  const token = localStorage.getItem("token");

  if (!token) {
    window.location = "/login";
    return {};
  }

  return {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + token
  };
}


// ---------- LOAD MODELS ----------
async function loadModels() {
  try {
    let r = await fetch("/models", {
      headers: getAuthHeaders()
    });

    if (r.status === 401) {
      window.location = "/login";
      return;
    }

    let data = await r.json();

    (data.models || []).forEach(m => {
      let opt = document.createElement("option");
      opt.value = m.name;
      opt.text = m.name;
      modelSelect.appendChild(opt);
    });

  } catch (e) {
    console.error("Model load failed", e);
  }
}

loadModels();


// ---------- ADD MESSAGE ----------
function addMessage(text, type) {
  let div = document.createElement("div");
  div.className = "msg " + type;

  // Markdown rendering
  div.innerHTML = marked.parse(text);

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;

  return div;
}


// ---------- SEND MESSAGE ----------
async function send() {

  if (!currentConversation) {
    alert("Create a chat first");
    return;
  }

  let text = promptBox.value.trim();
  if (!text) return;

  promptBox.value = "";

  addMessage(text, "user");
  let aiDiv = addMessage("", "ai");

  try {
    let r = await fetch("/chat-stream", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        model: modelSelect.value,
        prompt: text,
        conversation_id: currentConversation
      })
    });

    if (r.status === 401) {
      window.location = "/login";
      return;
    }

    const reader = r.body.getReader();
    const decoder = new TextDecoder();

    let full = "";

    while (true) {
      let { done, value } = await reader.read();
      if (done) break;

      let chunk = decoder.decode(value);
      full += chunk;

      aiDiv.innerHTML = marked.parse(full);
    }

    // Refresh sidebar (chat title etc.)
    loadConversations();

  } catch (e) {
    console.error("Chat error:", e);
    addMessage("❌ Error communicating with server", "ai");
  }
}


// ---------- ENTER KEY HANDLING ----------
promptBox.addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
const chat = document.getElementById("chat");
const promptBox = document.getElementById("prompt");
const modelSelect = document.getElementById("model");

async function loadModels() {
  let r = await fetch("/models");
  let data = await r.json();

  (data.models || []).forEach(m => {
    let opt = document.createElement("option");
    opt.value = m.name;
    opt.text = m.name;
    modelSelect.appendChild(opt);
  });
}

loadModels();

function addMessage(text, type) {
  let div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = marked.parse(text);
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function send() {
  let text = promptBox.value.trim();
  if (!text || !currentConversation) return;

  promptBox.value = "";
  addMessage(text, "user");

  let aiDiv = addMessage("", "ai");

  let r = await fetch("/chat-stream", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      model: modelSelect.value,
      prompt: text,
      conversation_id: currentConversation
    })
  });

  const reader = r.body.getReader();
  const decoder = new TextDecoder();

  let full = "";

  while (true) {
    let {done, value} = await reader.read();
    if (done) break;

    let chunk = decoder.decode(value);
    full += chunk;
    aiDiv.innerHTML = marked.parse(full);
  }

  loadConversations();
}

promptBox.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
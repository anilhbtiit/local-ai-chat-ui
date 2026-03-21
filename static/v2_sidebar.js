let currentConversation = null;

async function loadConversations() {
  let r = await fetch("/conversations");
  let data = await r.json();

  let container = document.getElementById("conversations");
  container.innerHTML = "";

  data.forEach(c => {
    let div = document.createElement("div");
    div.innerText = c.title;
    div.onclick = () => loadChat(c.id);
    container.appendChild(div);
  });
}

async function newChat() {
  let r = await fetch("/conversations", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({title: "New Chat"})
  });

  let data = await r.json();

  currentConversation = data.id;

  loadConversations();
  clearChat();
}

async function loadChat(id) {
  currentConversation = id;

  let r = await fetch(`/messages/${id}`);
  let data = await r.json();

  clearChat();

  data.forEach(m => {
    addMessage(marked.parse(m.content), m.role);
  });
}

function clearChat() {
  document.getElementById("chat").innerHTML = "";
}

loadConversations();
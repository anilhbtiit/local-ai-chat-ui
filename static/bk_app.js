const chat = document.getElementById("chat")
const promptBox = document.getElementById("prompt")
const modelSelect = document.getElementById("model")

async function loadModels(){

let r = await fetch("/models")
let data = await r.json()

data.models.forEach(m => {

let opt = document.createElement("option")
opt.value = m.name
opt.text = m.name

modelSelect.appendChild(opt)

})

}

loadModels()

function addMessage(text,type){

let div=document.createElement("div")
div.className="message "+type
div.innerText=text

chat.appendChild(div)

chat.scrollTop=chat.scrollHeight

return div
}


async function send(){

let prompt=promptBox.value
promptBox.value=""

addMessage(prompt,"user")

let aiDiv=addMessage("","ai")

let r = await fetch("/chat-stream",{
method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({
model:modelSelect.value,
prompt:prompt
})
})

const reader = r.body.getReader()
const decoder = new TextDecoder()

while(true){

const {done,value}=await reader.read()

if(done) break

aiDiv.innerText += decoder.decode(value)

chat.scrollTop=chat.scrollHeight

}

}
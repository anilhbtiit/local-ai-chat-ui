from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    model: str
    prompt: str
    conversation_id: int

class ConversationCreate(BaseModel):
    title: str

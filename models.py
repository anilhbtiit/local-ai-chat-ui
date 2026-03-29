from pydantic import BaseModel
from typing import Optional

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
    use_rag: Optional[bool] = False

class ConversationCreate(BaseModel):
    title: str


class DirectoryIngestRequest(BaseModel):
    path: str

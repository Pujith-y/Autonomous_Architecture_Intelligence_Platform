from pydantic import BaseModel
from pydantic.networks import EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
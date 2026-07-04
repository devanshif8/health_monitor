import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class DoctorRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6, max_length=128)


class DoctorLogin(BaseModel):
    email: EmailStr
    password: str


class DoctorOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    doctor: DoctorOut

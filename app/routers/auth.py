from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doctor import Doctor
from app.schemas.auth import DoctorLogin, DoctorOut, DoctorRegister, Token
from app.services.auth import (
    create_access_token,
    get_current_doctor,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(body: DoctorRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Doctor).where(Doctor.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    doctor = Doctor(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    db.add(doctor)
    await db.flush()

    token = create_access_token(doctor.id)
    return Token(access_token=token, doctor=DoctorOut.model_validate(doctor))


@router.post("/login", response_model=Token)
async def login(body: DoctorLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Doctor).where(Doctor.email == body.email))
    doctor = result.scalar_one_or_none()
    if doctor is None or not verify_password(body.password, doctor.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(doctor.id)
    return Token(access_token=token, doctor=DoctorOut.model_validate(doctor))


@router.get("/me", response_model=DoctorOut)
async def me(current: Doctor = Depends(get_current_doctor)):
    return current

"""Account routes: signup, login, current-user, and profile verification."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies.db import get_db
from api.dependencies.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from config.logging import logger
from models.database.models import UserDB
from models.schemas import Token, UserCreate, UserLogin, UserPublic

router = APIRouter(prefix="/api/auth", tags=["auth"])


PROFILE_FIELDS = [
    "phone", "linkedin", "github", "portfolio", "leetcode",
    "college", "degree", "graduation_year", "skills", "objective",
    "tone", "resume_path", "resume_filename",
]


def _completeness(user: UserDB) -> int:
    """Simple, transparent completeness score used by the profile-verification screen."""
    weighted = [
        (user.name, 15), (user.email, 10), (user.phone, 5),
        (user.linkedin, 10), (user.github, 10), (user.portfolio, 10),
        (user.college, 10), (user.degree, 5), (user.graduation_year, 5),
        (bool(user.skills), 10), (user.objective, 5), (user.resume_path, 15),
    ]
    total = sum(w for _, w in weighted)
    earned = sum(w for v, w in weighted if v)
    return round(earned / total * 100) if total else 0


def to_public(user: UserDB) -> dict:
    data = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "profile_verified": bool(user.profile_verified),
        "profile_completeness": _completeness(user),
    }
    for f in PROFILE_FIELDS:
        data[f] = getattr(user, f)
    data["skills"] = data["skills"] or []
    data["tone"] = data["tone"] or "professional"
    return UserPublic(**data).model_dump()


@router.post("/signup", response_model=Token)
async def signup(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = UserDB(
        email=payload.email,
        name=payload.name.strip() or payload.email.split("@")[0],
        password_hash=hash_password(payload.password),
        skills=[],
        tone="professional",
        profile_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info(f"New account created: {user.email}")

    token = create_access_token(user.id, user.email)
    return Token(access_token=token, user=to_public(user))


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(user.id, user.email)
    return Token(access_token=token, user=to_public(user))


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserDB = Depends(get_current_user)):
    return to_public(current_user)


@router.post("/logout")
async def logout():
    # JWTs are stateless here; logging out is a client-side token discard.
    # This endpoint exists so the frontend has a single, explicit call to make.
    return {"status": "logged_out"}

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.auth_utils import hash_password, verify_password
from app.dependencies import get_db
from app.models import User, Organization, OrgMembership
from app.services.workspace_bootstrap import ensure_default_workspace_for_user
from app.schemas import UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])
DbDep = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: UserRegister, request: Request, db: DbDep):
    existing_user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already in use")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    # Create default organization for the new user
    org = Organization(
        name=f"{user.email.split('@')[0]}'s Org",
        slug=f"org-{str(user.id)[:8]}",
        settings={},
    )
    db.add(org)
    db.flush()

    # Add user as owner of their new org
    db.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))

    db.flush()
    ensure_default_workspace_for_user(user, db)
    db.refresh(user)

    request.session["user_id"] = str(user.id)
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: UserLogin, request: Request, db: DbDep):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    request.session["user_id"] = str(user.id)
    return user


@router.post("/logout", status_code=204)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

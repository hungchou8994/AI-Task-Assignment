from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.auth import ensure_person_access, get_current_user
from app.dependencies import get_db
from app.models import Person, Task, User
from app.schemas import PersonCreate, PersonUpdate, PersonResponse

router = APIRouter(prefix="/api/people", tags=["people"])
DbDep = Annotated[Session, Depends(get_db)]


@router.post("", response_model=PersonResponse, status_code=201)
def create_person(
    payload: PersonCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    person = Person(**payload.model_dump())
    db.add(person)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already in use")
    db.refresh(person)
    return person


@router.get("", response_model=list[PersonResponse])
def list_people(
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return db.scalars(select(Person)).all()


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: UUID,
    data: PersonUpdate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    person = ensure_person_access(person_id, current_user, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=204)
def delete_person(
    person_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    person = ensure_person_access(person_id, current_user, db)
    db.query(Task).filter(Task.assignee_id == person_id).update(
        {Task.assignee_id: None},
        synchronize_session=False,
    )
    db.delete(person)
    db.commit()
    # PostgreSQL ON DELETE SET NULL automatically nulls tasks.assignee_id — no manual update needed

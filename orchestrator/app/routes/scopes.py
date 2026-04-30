from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..models import Client, Scope, AuditLog
from ..schemas import ScopeIn, ScopeOut
from ..security import require_admin

router = APIRouter(prefix="/clients/{slug}/scopes", tags=["scopes"])


def _client_or_404(db: Session, slug: str) -> Client:
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.get("", response_model=list[ScopeOut])
def list_scopes(slug: str, db: Session = Depends(get_db), _u: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    return db.scalars(select(Scope).where(Scope.client_id == client.id)).all()


@router.post("", response_model=ScopeOut, status_code=status.HTTP_201_CREATED)
def add_scope(slug: str, payload: ScopeIn, db: Session = Depends(get_db),
              user: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    existing = db.scalar(select(Scope).where(
        Scope.client_id == client.id, Scope.kind == payload.kind, Scope.value == payload.value
    ))
    if existing:
        return existing
    scope = Scope(client_id=client.id, **payload.model_dump())
    db.add(scope)
    db.add(AuditLog(actor=user, action="scope.add", target=f"{slug}:{payload.kind}:{payload.value}"))
    db.commit()
    db.refresh(scope)
    return scope


@router.delete("/{scope_id}", status_code=status.HTTP_204_NO_CONTENT)
def del_scope(slug: str, scope_id: int, db: Session = Depends(get_db),
              user: str = Depends(require_admin)):
    client = _client_or_404(db, slug)
    scope = db.scalar(select(Scope).where(Scope.id == scope_id, Scope.client_id == client.id))
    if not scope:
        raise HTTPException(404, "Scope not found")
    db.add(AuditLog(actor=user, action="scope.delete", target=f"{slug}:{scope.value}"))
    db.delete(scope)
    db.commit()

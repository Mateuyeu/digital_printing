from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..db import get_db
from ..models import Client, AuditLog
from ..schemas import ClientCreate, ClientOut
from ..security import require_admin

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db), _user: str = Depends(require_admin)):
    return db.scalars(select(Client).order_by(Client.id)).all()


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate,
                  db: Session = Depends(get_db),
                  user: str = Depends(require_admin)):
    if db.scalar(select(Client).where(Client.slug == payload.slug)):
        raise HTTPException(409, f"Client slug '{payload.slug}' already exists")
    client = Client(**payload.model_dump())
    db.add(client)
    db.add(AuditLog(actor=user, action="client.create", target=payload.slug,
                    detail=payload.model_dump()))
    db.commit()
    db.refresh(client)
    return client


@router.get("/{slug}", response_model=ClientOut)
def get_client(slug: str, db: Session = Depends(get_db), _user: str = Depends(require_admin)):
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    return client


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(slug: str, db: Session = Depends(get_db), user: str = Depends(require_admin)):
    client = db.scalar(select(Client).where(Client.slug == slug))
    if not client:
        raise HTTPException(404, "Client not found")
    db.add(AuditLog(actor=user, action="client.delete", target=slug))
    db.delete(client)
    db.commit()

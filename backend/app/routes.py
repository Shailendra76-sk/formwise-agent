from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import AddressCreate, DocumentMetadata, EducationCreate, ProfileUpdate
from app.auth import require_user_id
from app.config import settings
from app.database import get_db
from app.db_models import AddressRecord, AuditLogRecord, DocumentRecord, EducationRecord, ProfileRecord
from app.security import sha256_bytes, validate_upload
from app.storage import PrivateStorage

router = APIRouter(prefix="/v1", tags=["profile-vault"])
storage = PrivateStorage(settings.storage_root)


def ensure_profile(db: Session, user_id: str) -> ProfileRecord:
    profile = db.get(ProfileRecord, user_id)
    if profile is None:
        profile = ProfileRecord(user_id=user_id)
        db.add(profile)
        db.flush()
    return profile


def audit(db: Session, user_id: str, action: str, resource_type: str, resource_id: str | None = None) -> None:
    db.add(AuditLogRecord(user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id))


@router.get("/profile")
def get_profile(user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    return ensure_profile(db, user_id).__dict__ | {"_sa_instance_state": None}


@router.put("/profile")
def update_profile(payload: ProfileUpdate, user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    profile = ensure_profile(db, user_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    audit(db, user_id, "profile.updated", "profile", user_id)
    db.commit()
    return {"user_id": profile.user_id, **payload.model_dump(exclude_unset=False)}


@router.post("/addresses")
def add_address(payload: AddressCreate, user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    ensure_profile(db, user_id)
    record = AddressRecord(user_id=user_id, **payload.model_dump())
    db.add(record)
    db.flush()
    audit(db, user_id, "address.created", "address", record.id)
    db.commit()
    return {k: v for k, v in record.__dict__.items() if k != "_sa_instance_state"}


@router.get("/addresses")
def list_addresses(user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(AddressRecord).where(AddressRecord.user_id == user_id)).all()
    return [{k: v for k, v in row.__dict__.items() if k != "_sa_instance_state"} for row in rows]


@router.delete("/addresses/{address_id}")
def delete_address(address_id: str, user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    row = db.scalar(select(AddressRecord).where(AddressRecord.id == address_id, AddressRecord.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="address not found")
    db.delete(row)
    audit(db, user_id, "address.deleted", "address", address_id)
    db.commit()
    return {"deleted": True}


@router.post("/education")
def add_education(payload: EducationCreate, user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    ensure_profile(db, user_id)
    record = EducationRecord(user_id=user_id, **payload.model_dump())
    db.add(record)
    db.flush()
    audit(db, user_id, "education.created", "education", record.id)
    db.commit()
    return {k: v for k, v in record.__dict__.items() if k != "_sa_instance_state"}


@router.get("/education")
def list_education(user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(EducationRecord).where(EducationRecord.user_id == user_id)).all()
    return [{k: v for k, v in row.__dict__.items() if k != "_sa_instance_state"} for row in rows]


@router.post("/documents", response_model=DocumentMetadata, status_code=201)
async def upload_document(file: UploadFile = File(...), user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    validate_upload(file.filename or "", content_type, len(data), settings.max_upload_size_bytes)
    digest = sha256_bytes(data)
    storage_key = f"{secrets.token_hex(16)}-{digest}.bin"
    storage.save(user_id, storage_key, data)
    record = DocumentRecord(
        user_id=user_id,
        original_filename=file.filename or "document",
        storage_key=storage_key,
        content_type=content_type,
        size_bytes=len(data),
        sha256=digest,
    )
    db.add(record)
    db.flush()
    audit(db, user_id, "document.uploaded", "document", record.id)
    db.commit()
    return DocumentMetadata(original_filename=record.original_filename, content_type=record.content_type, size_bytes=record.size_bytes, sha256=record.sha256, status=record.status)


@router.get("/documents")
def list_documents(user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    rows = db.scalars(select(DocumentRecord).where(DocumentRecord.user_id == user_id, DocumentRecord.status != "deleted")).all()
    return [{"id": row.id, "original_filename": row.original_filename, "content_type": row.content_type, "size_bytes": row.size_bytes, "sha256": row.sha256, "status": row.status, "created_at": row.created_at} for row in rows]


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, user_id: str = Depends(require_user_id), db: Session = Depends(get_db)):
    row = db.scalar(select(DocumentRecord).where(DocumentRecord.id == document_id, DocumentRecord.user_id == user_id))
    if row is None:
        raise HTTPException(status_code=404, detail="document not found")
    storage.delete(user_id, row.storage_key)
    row.status = "deleted"
    audit(db, user_id, "document.deleted", "document", document_id)
    db.commit()
    return {"deleted": True}

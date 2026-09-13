from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db_models import AddressRecord, EducationRecord, ProfileRecord


class VerifiedDataStatus:
    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INVALID_FIELD = "INVALID_FIELD"
    ERROR = "ERROR"


@dataclass(frozen=True)
class VerifiedDataResult:
    status: str
    field_key: str
    value: Any | None = None
    message: str | None = None
    source: str | None = None

    @property
    def usable(self) -> bool:
        return self.status == VerifiedDataStatus.VERIFIED


# Explicit allow-list: the agent can request only these fields, never arbitrary
# SQLAlchemy columns or user-controlled expressions.
FIELD_SPECS: dict[str, tuple[str, str]] = {
    "full_name": ("profile", "full_name"),
    "date_of_birth": ("profile", "date_of_birth"),
    "gender": ("profile", "gender"),
    "email": ("profile", "email"),
    "phone": ("profile", "phone"),
    "permanent_address.line1": ("address:permanent", "line1"),
    "permanent_address.line2": ("address:permanent", "line2"),
    "permanent_address.city": ("address:permanent", "city"),
    "permanent_address.state": ("address:permanent", "state"),
    "permanent_address.postal_code": ("address:permanent", "postal_code"),
    "permanent_address.country": ("address:permanent", "country"),
    "education.latest.qualification": ("education:latest", "qualification"),
    "education.latest.institution": ("education:latest", "institution"),
    "education.latest.board_university": ("education:latest", "board_university"),
    "education.latest.passing_year": ("education:latest", "passing_year"),
    "education.latest.percentage_or_cgpa": ("education:latest", "percentage_or_cgpa"),
}


def _stringify(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    return value


class VerifiedDataService:
    """Fail-closed gateway for minimal, on-demand user data reads."""

    def __init__(self, db: Session):
        self.db = db

    def get_field(self, user_id: str, field_key: str) -> VerifiedDataResult:
        spec = FIELD_SPECS.get(field_key)
        if spec is None:
            return VerifiedDataResult(
                status=VerifiedDataStatus.INVALID_FIELD,
                field_key=field_key,
                message="field is not approved for on-demand access",
            )

        try:
            scope, attribute = spec
            if scope == "profile":
                return self._profile_field(user_id, field_key, attribute)
            if scope == "address:permanent":
                return self._address_field(user_id, field_key, attribute)
            if scope == "education:latest":
                return self._education_field(user_id, field_key, attribute)
            return VerifiedDataResult(
                status=VerifiedDataStatus.ERROR,
                field_key=field_key,
                message="unsupported field scope",
            )
        except Exception as exc:
            return VerifiedDataResult(
                status=VerifiedDataStatus.ERROR,
                field_key=field_key,
                message=f"verified data lookup failed: {exc}",
            )

    def _profile_field(self, user_id: str, field_key: str, attribute: str) -> VerifiedDataResult:
        profile = self.db.get(ProfileRecord, user_id)
        if profile is None:
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="profile not found")
        value = getattr(profile, attribute, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="field value not found", source="profiles")
        return VerifiedDataResult(VerifiedDataStatus.VERIFIED, field_key, _stringify(value), source="profiles")

    def _address_field(self, user_id: str, field_key: str, attribute: str) -> VerifiedDataResult:
        rows = self.db.scalars(
            select(AddressRecord).where(
                AddressRecord.user_id == user_id,
                AddressRecord.label.ilike("permanent"),
            )
        ).all()
        if not rows:
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="permanent address not found")
        if len(rows) > 1:
            return VerifiedDataResult(VerifiedDataStatus.CONFLICT, field_key, message="multiple permanent addresses found")
        value = getattr(rows[0], attribute, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="address field value not found", source="addresses")
        return VerifiedDataResult(VerifiedDataStatus.VERIFIED, field_key, _stringify(value), source="addresses")

    def _education_field(self, user_id: str, field_key: str, attribute: str) -> VerifiedDataResult:
        rows = self.db.scalars(
            select(EducationRecord)
            .where(EducationRecord.user_id == user_id)
            .order_by(EducationRecord.passing_year.desc().nullslast(), EducationRecord.id.desc())
        ).all()
        if not rows:
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="education record not found")
        # "latest" is deterministic only when the newest year is unique.
        newest_year = rows[0].passing_year
        newest = [row for row in rows if row.passing_year == newest_year]
        if newest_year is not None and len(newest) > 1:
            return VerifiedDataResult(VerifiedDataStatus.CONFLICT, field_key, message="multiple latest education records found")
        row = newest[0]
        value = getattr(row, attribute, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            return VerifiedDataResult(VerifiedDataStatus.NOT_FOUND, field_key, message="education field value not found", source="education")
        return VerifiedDataResult(VerifiedDataStatus.VERIFIED, field_key, _stringify(value), source="education")

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.db_models import AddressRecord, EducationRecord, ProfileRecord
from app.verified_data_service import VerifiedDataService, VerifiedDataStatus


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_on_demand_profile_field_is_verified_and_scoped():
    db = make_db()
    db.add(ProfileRecord(user_id="u1", full_name="Demo User", date_of_birth=date(2000, 1, 2)))
    db.commit()

    result = VerifiedDataService(db).get_field("u1", "full_name")

    assert result.status == VerifiedDataStatus.VERIFIED
    assert result.value == "Demo User"
    db.close()


def test_missing_field_returns_not_found_without_value():
    db = make_db()
    db.add(ProfileRecord(user_id="u1", full_name="Demo User"))
    db.commit()

    result = VerifiedDataService(db).get_field("u1", "phone")

    assert result.status == VerifiedDataStatus.NOT_FOUND
    assert result.value is None
    db.close()


def test_duplicate_permanent_address_is_conflict():
    db = make_db()
    db.add(ProfileRecord(user_id="u1", full_name="Demo User"))
    db.add_all(
        [
            AddressRecord(user_id="u1", label="permanent", line1="One"),
            AddressRecord(user_id="u1", label="permanent", line1="Two"),
        ]
    )
    db.commit()

    result = VerifiedDataService(db).get_field("u1", "permanent_address.line1")

    assert result.status == VerifiedDataStatus.CONFLICT
    assert result.value is None
    db.close()


def test_duplicate_latest_education_is_conflict():
    db = make_db()
    db.add(ProfileRecord(user_id="u1", full_name="Demo User"))
    db.add_all(
        [
            EducationRecord(user_id="u1", qualification="BSc", passing_year=2024),
            EducationRecord(user_id="u1", qualification="BA", passing_year=2024),
        ]
    )
    db.commit()

    result = VerifiedDataService(db).get_field("u1", "education.latest.qualification")

    assert result.status == VerifiedDataStatus.CONFLICT
    assert result.value is None
    db.close()


def test_arbitrary_field_is_rejected():
    db = make_db()

    result = VerifiedDataService(db).get_field("u1", "profiles.secret_column")

    assert result.status == VerifiedDataStatus.INVALID_FIELD
    assert result.value is None
    db.close()

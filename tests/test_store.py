import pytest
import sqlite3
import datetime
from store import ExperienceStore
from models import Experience, Project, Bullet, JDSession, GapDiscovery

@pytest.fixture
def temp_store(tmp_path):
    db_path = tmp_path / "resume.db"
    return ExperienceStore(str(db_path))

def test_store_init(temp_store):
    with sqlite3.connect(temp_store.db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "experiences" in tables
        assert "projects" in tables
        assert "jd_sessions" in tables
        assert "audit_log" in tables

def test_save_and_get_experience(temp_store):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exp = Experience(
        id="exp1", role="SWE", company="Acme", employment_type="full_time",
        created_at=now, updated_at=now
    )

    temp_store.save_experience(exp, "user")

    saved = temp_store.get_experience("exp1")
    assert saved is not None
    assert saved.role == "SWE"
    assert saved.version == 1

    # Test update and version bump
    saved.company = "Acme Corp"
    temp_store.save_experience(saved, "user")

    updated = temp_store.get_experience("exp1")
    assert updated.company == "Acme Corp"
    assert updated.version == 2

def test_add_bullet_to_experience(temp_store):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exp = Experience(
        id="exp2", role="Dev", company="Startup", employment_type="full_time",
        created_at=now, updated_at=now
    )
    temp_store.save_experience(exp, "user")

    bullet = Bullet(
        id="b1", text="Built MVP.", has_metric=False, source="user_raw",
        created_at=now
    )
    temp_store.add_bullet_to_experience("exp2", bullet, "user")

    updated = temp_store.get_experience("exp2")
    assert len(updated.bullets) == 1
    assert updated.bullets[0].text == "Built MVP."
    assert updated.version == 2

def test_semantic_search(temp_store):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exp = Experience(
        id="exp3", role="Python Backend Developer", company="Tech Corp",
        employment_type="full_time", created_at=now, updated_at=now,
        skills=["Python", "FastAPI"]
    )
    temp_store.save_experience(exp, "user")

    results = temp_store.semantic_search("backend engineering with Python")
    assert len(results) > 0
    assert results[0]["entity_type"] == "experience"
    assert results[0]["entity"].id == "exp3"
    assert results[0]["score"] > 0

def test_audit_log(temp_store):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proj = Project(
        id="proj1", name="Test Project", description="Testing", status="active",
        created_at=now, updated_at=now
    )
    temp_store.save_project(proj, "user")

    with sqlite3.connect(temp_store.db_path) as conn:
        cursor = conn.execute("SELECT data FROM audit_log ORDER BY id DESC")
        row = cursor.fetchone()
        assert row is not None
        assert "Test Project" in row[0]

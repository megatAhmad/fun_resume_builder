from __future__ import annotations

import json
import sqlite3
import datetime
from typing import Literal, Any, cast

import numpy as np

from models import Experience, Project, JDSession, Bullet, AuditEntry
from embeddings import embed, cosine_similarity

class ExperienceStore:
    def __init__(self, db_path: str = "resume.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    id          TEXT PRIMARY KEY,
                    data        TEXT NOT NULL,
                    embedding   BLOB,
                    is_active   INTEGER DEFAULT 1,
                    version     INTEGER DEFAULT 1,
                    created_at  TEXT,
                    updated_at  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id          TEXT PRIMARY KEY,
                    data        TEXT NOT NULL,
                    embedding   BLOB,
                    is_active   INTEGER DEFAULT 1,
                    version     INTEGER DEFAULT 1,
                    created_at  TEXT,
                    updated_at  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jd_sessions (
                    id          TEXT PRIMARY KEY,
                    data        TEXT NOT NULL,
                    created_at  TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    data        TEXT NOT NULL,
                    created_at  TEXT
                )
            """)

    def _log_audit(
        self,
        conn: sqlite3.Connection,
        entity_type: Literal["experience", "project", "bullet"],
        entity_id: str,
        action: Literal["created", "updated", "deactivated", "bullet_added", "gap_enriched"],
        triggered_by: Literal["user", "agent"],
        after_snapshot: str,
        before_snapshot: str | None = None,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry = AuditEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            triggered_by=triggered_by,
            created_at=now
        )
        conn.execute(
            "INSERT INTO audit_log (data, created_at) VALUES (?, ?)",
            (entry.model_dump_json(), now)
        )

    def _serialize_embedding(self, emb: np.ndarray) -> bytes:
        return emb.tobytes()

    def _deserialize_embedding(self, blob: bytes) -> np.ndarray:
        return np.frombuffer(blob, dtype=np.float32)

    def get_experience(self, exp_id: str) -> Experience | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data FROM experiences WHERE id = ?", (exp_id,))
            row = cursor.fetchone()
            if row:
                return Experience.model_validate_json(row[0])
            return None

    def list_experiences(self, active_only: bool = True) -> list[Experience]:
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT data FROM experiences"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            cursor = conn.execute(query)
            return [Experience.model_validate_json(row[0]) for row in cursor.fetchall()]

    def save_experience(self, exp: Experience, triggered_by: Literal["user", "agent"]) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        exp.updated_at = now

        # Calculate embedding
        emb = embed(exp.all_text())
        emb_blob = self._serialize_embedding(emb)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data, version FROM experiences WHERE id = ?", (exp.id,))
            row = cursor.fetchone()

            before_snapshot = None
            if row:
                before_snapshot = row[0]
                exp.version = row[1] + 1
                action = "updated" if exp.is_active else "deactivated"
            else:
                exp.version = 1
                action = "created"

            data_json = exp.model_dump_json()

            self._log_audit(
                conn,
                entity_type="experience",
                entity_id=exp.id,
                action=action,
                triggered_by=triggered_by,
                before_snapshot=before_snapshot,
                after_snapshot=data_json
            )

            conn.execute("""
                INSERT INTO experiences (id, data, embedding, is_active, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    data=excluded.data,
                    embedding=excluded.embedding,
                    is_active=excluded.is_active,
                    version=excluded.version,
                    updated_at=excluded.updated_at
            """, (exp.id, data_json, emb_blob, int(exp.is_active), exp.version, exp.created_at, exp.updated_at))

    def get_project(self, proj_id: str) -> Project | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data FROM projects WHERE id = ?", (proj_id,))
            row = cursor.fetchone()
            if row:
                return Project.model_validate_json(row[0])
            return None

    def list_projects(self, active_only: bool = True) -> list[Project]:
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT data FROM projects"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            cursor = conn.execute(query)
            return [Project.model_validate_json(row[0]) for row in cursor.fetchall()]

    def save_project(self, proj: Project, triggered_by: Literal["user", "agent"]) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        proj.updated_at = now

        emb = embed(proj.all_text())
        emb_blob = self._serialize_embedding(emb)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data, version FROM projects WHERE id = ?", (proj.id,))
            row = cursor.fetchone()

            before_snapshot = None
            if row:
                before_snapshot = row[0]
                proj.version = row[1] + 1
                action = "updated" if proj.is_active else "deactivated"
            else:
                proj.version = 1
                action = "created"

            data_json = proj.model_dump_json()

            self._log_audit(
                conn,
                entity_type="project",
                entity_id=proj.id,
                action=action,
                triggered_by=triggered_by,
                before_snapshot=before_snapshot,
                after_snapshot=data_json
            )

            conn.execute("""
                INSERT INTO projects (id, data, embedding, is_active, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    data=excluded.data,
                    embedding=excluded.embedding,
                    is_active=excluded.is_active,
                    version=excluded.version,
                    updated_at=excluded.updated_at
            """, (proj.id, data_json, emb_blob, int(proj.is_active), proj.version, proj.created_at, proj.updated_at))

    def add_bullet_to_experience(self, exp_id: str, bullet: Bullet, triggered_by: Literal["user", "agent"]) -> None:
        exp = self.get_experience(exp_id)
        if not exp:
            raise ValueError(f"Experience {exp_id} not found")

        exp.bullets.append(bullet)

        # Soft audit note: save_experience will log the full update. We explicitly log the bullet addition first.
        with sqlite3.connect(self.db_path) as conn:
            self._log_audit(
                conn,
                entity_type="bullet",
                entity_id=bullet.id,
                action="gap_enriched" if bullet.source == "gap_enriched" else "bullet_added",
                triggered_by=triggered_by,
                after_snapshot=bullet.model_dump_json()
            )

        # This will save the experience, re-embed, and log an 'updated' audit entry.
        self.save_experience(exp, triggered_by)

    def add_bullet_to_project(self, proj_id: str, bullet: Bullet, triggered_by: Literal["user", "agent"]) -> None:
        proj = self.get_project(proj_id)
        if not proj:
            raise ValueError(f"Project {proj_id} not found")

        proj.bullets.append(bullet)

        with sqlite3.connect(self.db_path) as conn:
            self._log_audit(
                conn,
                entity_type="bullet",
                entity_id=bullet.id,
                action="gap_enriched" if bullet.source == "gap_enriched" else "bullet_added",
                triggered_by=triggered_by,
                after_snapshot=bullet.model_dump_json()
            )

        self.save_project(proj, triggered_by)

    def save_jd_session(self, session: JDSession) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO jd_sessions (id, data, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    data=excluded.data
            """, (session.id, session.model_dump_json(), session.created_at))

    def list_jd_sessions(self) -> list[JDSession]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT data FROM jd_sessions ORDER BY created_at DESC")
            return [JDSession.model_validate_json(row[0]) for row in cursor.fetchall()]

    def semantic_search(self, query_text: str, top_k: int = 3, active_only: bool = True) -> list[dict[str, Any]]:
        query_emb = embed(query_text)

        results = []
        with sqlite3.connect(self.db_path) as conn:
            # Search Experiences
            q_exp = "SELECT data, embedding FROM experiences"
            if active_only:
                q_exp += " WHERE is_active = 1"
            for row in conn.execute(q_exp):
                data, emb_blob = row
                if not emb_blob:
                    continue
                emb = self._deserialize_embedding(emb_blob)
                score = cosine_similarity(query_emb, emb)

                classification = "gap"
                if score >= 0.72:
                    classification = "strong"
                elif score >= 0.42:
                    classification = "potential"

                results.append({
                    "entity": Experience.model_validate_json(data),
                    "entity_type": "experience",
                    "score": score,
                    "classification": classification
                })

            # Search Projects
            q_proj = "SELECT data, embedding FROM projects"
            if active_only:
                q_proj += " WHERE is_active = 1"
            for row in conn.execute(q_proj):
                data, emb_blob = row
                if not emb_blob:
                    continue
                emb = self._deserialize_embedding(emb_blob)
                score = cosine_similarity(query_emb, emb)

                classification = "gap"
                if score >= 0.72:
                    classification = "strong"
                elif score >= 0.42:
                    classification = "potential"

                results.append({
                    "entity": Project.model_validate_json(data),
                    "entity_type": "project",
                    "score": score,
                    "classification": classification
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

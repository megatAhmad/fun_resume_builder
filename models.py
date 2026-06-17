from __future__ import annotations

import json
import os
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Configuration ---

class AppConfig(BaseModel):
    llm_retry_max: int = Field(default=3)
    llm_wait_time: int = Field(default=5)  # in seconds
    llm_model: str = Field(default="anthropic/claude-3-haiku")


def load_config(path: str = "config.json") -> AppConfig:
    default_model = os.getenv("RESUME_MODEL", "anthropic/claude-3-haiku")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if "llm_model" not in data:
                    data["llm_model"] = default_model
                return AppConfig(**data)
            except Exception:
                pass
    return AppConfig(llm_model=default_model)


def save_config(config: AppConfig, path: str = "config.json") -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=4)


# --- Core Data Models ---

class Bullet(BaseModel):
    id: str
    text: str
    skills_demonstrated: list[str] = Field(default_factory=list)
    has_metric: bool
    source: Literal["user_raw", "agent_uplifted", "gap_enriched"]
    is_active: bool = Field(default=True)
    created_at: str


class Experience(BaseModel):
    id: str
    role: str
    company: str
    team_or_division: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    bullets: list[Bullet] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    team_size: Optional[int] = None
    direct_reports: Optional[int] = None
    industry: Optional[str] = None
    employment_type: Literal["full_time", "contract", "internship", "part_time"]
    is_active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: str
    updated_at: str

    def all_text(self) -> str:
        parts = [self.role, self.company]
        if self.team_or_division:
            parts.append(self.team_or_division)
        if self.industry:
            parts.append(self.industry)

        for bullet in self.bullets:
            if bullet.is_active:
                parts.append(bullet.text)

        parts.extend(self.skills)
        return " ".join(parts)


class Project(BaseModel):
    id: str
    name: str
    description: str
    bullets: list[Bullet] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    url: Optional[str] = None
    status: Literal["active", "completed", "paused", "archived"]
    is_active: bool = Field(default=True)
    version: int = Field(default=1)
    created_at: str
    updated_at: str

    def all_text(self) -> str:
        parts = [self.name, self.description]
        for bullet in self.bullets:
            if bullet.is_active:
                parts.append(bullet.text)
        parts.extend(self.skills)
        return " ".join(parts)


class GapDiscovery(BaseModel):
    id: str
    jd_requirement_snippet: str
    agent_hypothesis: str
    suspected_entity_id: str
    suspected_entity_type: Literal["experience", "project"]
    similarity_score: float
    user_confirmed: Optional[bool] = None
    user_clarification: Optional[str] = None
    enriched_bullet: Optional[Bullet] = None
    created_at: str


class JDSession(BaseModel):
    id: str
    jd_raw: str
    jd_role_title: Optional[str] = None
    jd_company: Optional[str] = None
    strong_matches: list[str] = Field(default_factory=list)
    potential_matches: list[str] = Field(default_factory=list)
    gap_discoveries: list[GapDiscovery] = Field(default_factory=list)
    created_at: str


class AuditEntry(BaseModel):
    entity_type: Literal["experience", "project", "bullet"]
    entity_id: str
    action: Literal["created", "updated", "deactivated", "bullet_added", "gap_enriched"]
    before_snapshot: Optional[str] = None
    after_snapshot: str
    triggered_by: Literal["user", "agent"]
    created_at: str

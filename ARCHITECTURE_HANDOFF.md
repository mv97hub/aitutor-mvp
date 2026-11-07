# Architecture handoff

This file quotes the repository as of commit `ea917f9` on `main`. Every schema, interface, prompt template, and the sample course below is copied from source or produced by calling that source. There is no `src/` tree. The API is `apps/api`. The web app is `apps/web`.

### 1. Directory Structure & Tech Stack

Complete repository file list. Dependency lockfile `package-lock.json` is named here and its contents are omitted. There is no `node_modules` or generated vendor tree in the checkout.

```
.env.example
.gitignore
README.md
apps/api/alembic/env.py
apps/api/alembic/script.py.mako
apps/api/alembic/versions/001_initial.py
apps/api/alembic/versions/002_syllabus_blocks.py
apps/api/alembic/versions/003_model_prompts.py
apps/api/alembic/versions/004_prompt_message.py
apps/api/alembic/versions/005_syllabus_quests.py
apps/api/alembic/versions/006_quest_cycle.py
apps/api/alembic/versions/007_tutor_profile.py
apps/api/alembic/versions/008_stay_on_course.py
apps/api/alembic/versions/009_studio.py
apps/api/alembic/versions/010_studio_ready.py
apps/api/alembic/versions/011_studio_quiz_minutes.py
apps/api/alembic/versions/012_quests_on_course.py
apps/api/alembic/versions/013_tutor_quests_on_course.py
apps/api/alembic.ini
apps/api/app/__init__.py
apps/api/app/blocks.py
apps/api/app/course_io.py
apps/api/app/curriculum/__init__.py
apps/api/app/curriculum/geometry.py
apps/api/app/curriculum/macro.py
apps/api/app/curriculum/rome.py
apps/api/app/curriculum/shape.py
apps/api/app/database.py
apps/api/app/engine/__init__.py
apps/api/app/engine/assemble.py
apps/api/app/engine/choices.py
apps/api/app/engine/defaults.py
apps/api/app/engine/placeholders.py
apps/api/app/engine/types.py
apps/api/app/flow.py
apps/api/app/main.py
apps/api/app/models.py
apps/api/app/present.py
apps/api/app/prompt_loader.py
apps/api/app/queries.py
apps/api/app/routes/__init__.py
apps/api/app/routes/catalog.py
apps/api/app/routes/sessions.py
apps/api/app/routes/studio.py
apps/api/app/routes/tutor_profile.py
apps/api/app/schemas.py
apps/api/app/seed.py
apps/api/app/studio.py
apps/api/app/tutor_profile.py
apps/api/app/widgets.py
apps/api/pytest.ini
apps/api/requirements.txt
apps/api/tests/test_curriculum.py
apps/api/tests/test_diagram.py
apps/api/tests/test_engine.py
apps/api/tests/test_flow.py
apps/api/tests/test_studio.py
apps/web/app/admin/agent-customizations/page.tsx
apps/web/app/admin/agent-profiles/page.tsx
apps/web/app/admin/page.tsx
apps/web/app/admin/tutor-configuration/page.tsx
apps/web/app/api/chat/route.ts
apps/web/app/api/studio/chat/route.ts
apps/web/app/create-course/page.tsx
apps/web/app/globals.css
apps/web/app/layout.tsx
apps/web/app/manage-courses/page.tsx
apps/web/app/page.tsx
apps/web/app/viewchats/page.tsx
apps/web/components/AdminApp.tsx
apps/web/components/BrandMark.tsx
apps/web/components/ChatBox.tsx
apps/web/components/CreateCourse.tsx
apps/web/components/KidSession.tsx
apps/web/components/LessonBlocks.tsx
apps/web/components/ManageCourses.tsx
apps/web/components/ViewChats.tsx
apps/web/components/admin/AdminFrame.tsx
apps/web/components/admin/AdminMenu.tsx
apps/web/components/admin/AgentCustomizations.tsx
apps/web/lib/api.ts
apps/web/lib/kickoff.ts
apps/web/lib/model.ts
apps/web/lib/studio-build.test.ts
apps/web/lib/studio-build.ts
apps/web/lib/studio-chat.test.ts
apps/web/lib/studio-chat.ts
apps/web/lib/studio.ts
apps/web/lib/types.ts
apps/web/next-env.d.ts
apps/web/next.config.ts
apps/web/package.json
apps/web/public/kinder-computers-logo.png
apps/web/tsconfig.json
docker-compose.yml
package-lock.json
package.json
```

Web App Router pages and route handlers:

- `apps/web/app/page.tsx` serves `/`
- `apps/web/app/admin/page.tsx` serves `/admin`
- `apps/web/app/admin/agent-profiles/page.tsx` serves `/admin/agent-profiles`
- `apps/web/app/admin/agent-customizations/page.tsx` serves `/admin/agent-customizations`
- `apps/web/app/admin/tutor-configuration/page.tsx` serves `/admin/tutor-configuration`
- `apps/web/app/create-course/page.tsx` serves `/create-course`
- `apps/web/app/manage-courses/page.tsx` serves `/manage-courses`
- `apps/web/app/viewchats/page.tsx` serves `/viewchats`
- `apps/web/app/api/chat/route.ts` serves `POST /api/chat`
- `apps/web/app/api/studio/chat/route.ts` serves `POST /api/studio/chat`

FastAPI mounts four routers from `apps/api/app/main.py` plus `GET /health`. Catalog, session, and tutor-profile routes have no prefix. Studio routes use prefix `/studio`.

Catalog routes in `apps/api/app/routes/catalog.py`:

- `GET /profile-defaults`
- `GET /students`
- `POST /students`
- `PATCH /students/{student_id}`
- `GET /courses`
- `POST /courses`
- `POST /courses/import`
- `GET /courses/{course_id}`
- `GET /courses/{course_id}/export`
- `POST /courses/import-studio`
- `POST /courses/{course_id}/remove`
- `GET /courses/{course_id}/quests`
- `PATCH /courses/{course_id}`
- `DELETE /courses/{course_id}`
- `GET /quests/{quest_id}`
- `PATCH /quests/{quest_id}`
- `DELETE /quests/{quest_id}`
- `PUT /quests/{quest_id}/beats`

Session routes in `apps/api/app/routes/sessions.py`:

- `GET /sessions`
- `POST /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/board`
- `GET /sessions/{session_id}/prompt`
- `POST /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/advance`
- `POST /sessions/{session_id}/grade-widget`
- `POST /sessions/{session_id}/check-diagram`
- `GET /sessions/{session_id}/model-prompts`
- `POST /sessions/{session_id}/model-prompts`
- `POST /sessions/{session_id}/turn-score`

Tutor profile routes in `apps/api/app/routes/tutor_profile.py`:

- `GET /tutor-profile`
- `PUT /tutor-profile`

Studio routes in `apps/api/app/routes/studio.py`:

- `GET /studio/courses`
- `POST /studio/courses`
- `POST /studio/courses/{course_id}/delete`
- `POST /studio/courses/{course_id}/copy`
- `GET /studio/courses/{course_id}`
- `PATCH /studio/courses/{course_id}`
- `POST /studio/courses/{course_id}/ready`
- `POST /studio/courses/{course_id}/phase`
- `GET /studio/courses/{course_id}/messages`
- `POST /studio/courses/{course_id}/opening`
- `POST /studio/courses/{course_id}/turns`
- `POST /studio/courses/{course_id}/fallback`
- `POST /studio/courses/{course_id}/push-draft`
- `POST /studio/courses/{course_id}/advance-stage`
- `POST /studio/courses/{course_id}/stage`
- `POST /studio/courses/{course_id}/tree`
- `POST /studio/courses/{course_id}/messages`
- `POST /studio/courses/{course_id}/messages/{message_id}/accept`
- `POST /studio/courses/{course_id}/messages/{message_id}/dismiss`
- `POST /studio/courses/{course_id}/edit`
- `POST /studio/courses/{course_id}/undo`
- `GET /studio/courses/{course_id}/prompt`
- `GET /studio/settings`
- `PUT /studio/settings`

Runtime stack: Next.js 16 App Router and React 19 in `apps/web`. FastAPI, SQLAlchemy 2, Alembic, and psycopg against Postgres 16 in `apps/api` and `docker-compose.yml`. Tutor and studio model calls use the Vercel AI SDK (`ai`, `@ai-sdk/openai`) in the Next.js route handlers. The Python API does not call an LLM SDK. Structured output is a JSON Schema object passed to `Output.object` / `jsonSchema`. Pydantic validates HTTP bodies. The web `package.json` depends on `zod`, and no `z.object` schema exists in this repository.

Source file `package.json`:

```json
{
  "name": "aitutor-mvp",
  "private": true,
  "workspaces": [
    "apps/web"
  ],
  "scripts": {
    "dev:web": "npm run dev --workspace web",
    "build:web": "npm run build --workspace web"
  }
}
```

Source file `apps/web/package.json`:

```json
{
  "name": "web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "node --experimental-strip-types --experimental-detect-module --test lib/*.test.ts"
  },
  "dependencies": {
    "@ai-sdk/openai": "4.0.106",
    "@ai-sdk/react": "4.0.163",
    "ai": "7.0.159",
    "next": "16.4.3",
    "react": "19.3.1",
    "react-dom": "19.3.1",
    "zod": "4.6.7"
  },
  "devDependencies": {
    "@types/node": "26.6.6",
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "typescript": "7.0.2"
  }
}
```

Source file `apps/api/requirements.txt`:

```text
fastapi==0.162.0
uvicorn[standard]==0.54.0
sqlalchemy==2.1.6
alembic==1.20.1
psycopg[binary]==3.3.6
pydantic==2.14.2
python-dotenv==1.2.4
httpx==0.28.1
pytest==9.2.0
```

Source file `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: aitutor
      POSTGRES_PASSWORD: aitutor
      POSTGRES_DB: aitutor
    ports:
      - "5432:5432"
    volumes:
      - aitutor_pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aitutor -d aitutor"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  aitutor_pg:
```

Source file `apps/api/app/database.py`:

```python
import os
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_API_DIR / ".env")
load_dotenv(_REPO_ROOT / ".env")

DEFAULT_DATABASE_URL = "postgresql+psycopg://aitutor:aitutor@localhost:5432/aitutor"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


class Base(DeclarativeBase):
    pass


engine = create_engine(database_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Source file `apps/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.catalog import router as catalog_router
from app.routes.sessions import router as sessions_router
from app.routes.studio import router as studio_router
from app.routes.tutor_profile import router as tutor_profile_router

app = FastAPI(title="AI Tutor", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(catalog_router)
app.include_router(sessions_router)
app.include_router(tutor_profile_router)
app.include_router(studio_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
```

Source file `apps/web/lib/api.ts`:

```typescript
export function apiBase(): string {
  const configured =
    typeof window === "undefined"
      ? process.env.API_URL || process.env.NEXT_PUBLIC_API_URL
      : process.env.NEXT_PUBLIC_API_URL;
  return (configured || "http://localhost:8000").replace(/\/$/, "");
}

function detailFrom(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join(" ");
  }
  return fallback;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const body = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    throw new Error(detailFrom(body, text || `Request failed (${response.status})`));
  }
  return body as T;
}
```

Source file `apps/web/lib/model.ts`:

```typescript
/** Cheapest small chat model that can run a short tutor turn. */
export const DEFAULT_OPENAI_MODEL = "gpt-4o-mini";

/** OPENAI_MODEL overrides the default. The same OPENAI_API_KEY is used either way. */
export function openaiModelName(): string {
  const configured = process.env.OPENAI_MODEL?.trim();
  return configured || DEFAULT_OPENAI_MODEL;
}
```

### 2. Core Entities Data Model: Users, AI Agents & Courses (Verbatim)

Requested names that are not tables, and the models that fill those roles:

- There is no `users` table, no auth user, and no role column. Learner accounts are `students`.
- There is no `child_configs` table and no separate learner-profile table. Age, reading level, modality, and interests are columns on `students`. Age-band defaults live in `AgeProfile` inside `apps/api/app/engine/defaults.py`, quoted in section 4. Progress is `sessions.current_beat_id`, `sessions.status`, and `beat_results`.
- There is no `ai_agents` table. The live tutor personality is the singleton row `tutor_profiles.id = 'default'`. `load_prompt` reads that row. The `students.tutor_*` columns are a legacy per-student copy and are not injected into the tutor system prompt.
- There is no `course_preferences` table. Kid-catalog preferences are columns on `courses`: `description`, `audience`, `age_band`, `quest_count`, `goals_per_quest`, `quiz_minutes`, `standards_alignment`. Studio preferences are columns on `studio_courses` (`audience`, `focus`, `theme`, `depth`, `quiz_minutes`, `sources`) plus the JSON column `studio_courses.preferences`.
- There is no `success_criteria` table. Kid catalog stores a weighted rubric JSON on `quests.success_criterion` and one text criterion on each `quest_goals.success_criterion`. Studio stores goal 1 on `studio_quests.learning_goal` and `studio_quests.success_criterion`. Later goals are `studio_quest_goals` rows with `position >= 2`.
- There is no `closing` table. Kid catalog closing is `quest_closes` (`kind` essay, single, multi, or none). Studio closing is `studio_quest_close` (`close_style`, `answer_style`, `choice_mode`, `items`, `intent`).
- Quests are `quests` (kid catalog, child of `courses`) and `studio_quests` (Create course, child of `studio_courses`). Goals are `quest_goals` and `studio_quest_goals`. Studio also has `studio_moves`, which are not used by the kid tutor prompt.
- `Course` has no `units` table. Legacy seed files still nest quests under a `units` list. `validate_course` flattens that list onto `quests` before insert. `Layer1Beat.unit_title` is passed as an empty string by `load_prompt`.

SQLAlchemy models, the current schema:

Source file `apps/api/app/models.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")
QUEST_TYPES = ("core", "branch", "capstone")
BEAT_ROLES = (
    "engage",
    "try",
    "name",
    "show",
    "teach_back",
)


class Student(Base):
    """Layer 2 lives here. The tutor_* columns are the old per-student copy of
    layers 3 and 4. The live settings are the single tutor_profiles row.
    These columns stay so that move is not a destructive migration.
    """

    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    age: Mapped[int | None] = mapped_column(Integer)
    reading_level: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    modality: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    interests: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tutor_persona: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    tutor_lexicon: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tutor_metaphors: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tutor_sidekick: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    tutor_socratic_strictness: Mapped[str] = mapped_column(
        String(40), nullable=False, default="balanced"
    )
    tutor_struggle_window: Mapped[str] = mapped_column(
        String(40), nullable=False, default="minimum"
    )
    tutor_anti_spoiler: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tutor_pacing: Mapped[str] = mapped_column(
        String(80), nullable=False, default="short-turns-one-question"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list[Session]] = relationship(back_populates="student")


class TutorProfile(Base):
    """One default tutor profile, applied to every student."""

    __tablename__ = "tutor_profiles"
    __table_args__ = (
        CheckConstraint("id = 'default'", name="ck_tutor_profiles_singleton"),
        CheckConstraint(
            "instructive >= 1 AND instructive <= 5",
            name="ck_tutor_profiles_instructive",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    instructive: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    persona: Mapped[str] = mapped_column(String(40), nullable=False)
    lexicon: Mapped[str] = mapped_column(String(40), nullable=False)
    voice_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metaphors: Mapped[str] = mapped_column(String(40), nullable=False)
    sidekick: Mapped[str] = mapped_column(String(40), nullable=False)
    struggle_window: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    anti_spoiler: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    one_question: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_interests: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    stay_on_course: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    growth_praise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "age_band IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_age_band",
        ),
        CheckConstraint(
            "audience IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_audience",
        ),
        CheckConstraint(
            "quiz_minutes IN (2, 5, 10)",
            name="ck_courses_quiz_minutes",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    age_band: Mapped[str] = mapped_column(String(8), nullable=False)
    standards_alignment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    competency_dictionary: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audience: Mapped[str] = mapped_column(String(8), nullable=False, default="9-11")
    quest_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    goals_per_quest: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quiz_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    in_catalog: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    quests: Mapped[list[Quest]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Quest.position",
    )


class Quest(Base):
    __tablename__ = "quests"
    __table_args__ = (
        UniqueConstraint("course_id", "position", name="uq_quests_course_position"),
        CheckConstraint(
            "quest_type IN ('core', 'branch', 'capstone')",
            name="ck_quests_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    quest_type: Mapped[str] = mapped_column(String(16), nullable=False, default="core")
    prerequisite_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    competency_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dinner_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requires_teach_back: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped[Course] = relationship(back_populates="quests")
    goals: Mapped[list[QuestGoal]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="QuestGoal.position",
    )
    close: Mapped[QuestClose | None] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        uselist=False,
    )
    beats: Mapped[list[Beat]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="Beat.position",
    )
    sessions: Mapped[list[Session]] = relationship(back_populates="quest")


class QuestGoal(Base):
    """One learning goal and the single criterion that finishes it."""

    __tablename__ = "quest_goals"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_quest_goals_position"),
        CheckConstraint("position >= 1", name="ck_quest_goals_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[Quest] = relationship(back_populates="goals")


class QuestClose(Base):
    """How a quest ends: an essay, a single choice, a multi-choice, or no questions."""

    __tablename__ = "quest_closes"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('essay', 'single', 'multi', 'none')",
            name="ck_quest_closes_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    quest: Mapped[Quest] = relationship(back_populates="close")


class Beat(Base):
    __tablename__ = "beats"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_beats_quest_position"),
        CheckConstraint(
            "role IN ('engage', 'try', 'name', 'show', 'teach_back')",
            name="ck_beats_role",
        ),
        CheckConstraint("position >= 1", name="ck_beats_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(32), nullable=False, default="understand")
    cognitive_load: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rubric: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception_map: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    hint_ladder: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    widget: Mapped[dict | None] = mapped_column(JSON)

    quest: Mapped[Quest] = relationship(back_populates="beats")
    results: Mapped[list[BeatResult]] = relationship(back_populates="beat")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_sessions_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_beat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="sessions")
    quest: Mapped[Quest] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )
    results: Mapped[list[BeatResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BeatResult.seq",
    )
    prompts: Mapped[list[ModelPrompt]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ModelPrompt.seq",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class BeatResult(Base):
    __tablename__ = "beat_results"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_beat_results_session_seq"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_beat_results_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    beat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception: Mapped[str | None] = mapped_column(Text)
    hint_tier: Mapped[str | None] = mapped_column(String(16))
    choice: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="results")
    beat: Mapped[Beat] = relationship(back_populates="results")


class ModelPrompt(Base):
    """One model call: the system prompt plus the messages sent to the model."""

    __tablename__ = "model_prompts"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_model_prompts_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="prompts")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StudioCourse(Base):
    """A course built in CreateCourse. Separate from the tutor courses table."""

    __tablename__ = "studio_courses"
    __table_args__ = (
        CheckConstraint(
            "depth IN ('survey', 'standard', 'go_deep')",
            name="ck_studio_courses_depth",
        ),
        CheckConstraint(
            "quiz_minutes IN (2, 5, 10)",
            name="ck_studio_courses_quiz_minutes",
        ),
        CheckConstraint("schema_version >= 1", name="ck_studio_courses_schema_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    audience: Mapped[str] = mapped_column(Text, nullable=False, default="")
    focus: Mapped[str] = mapped_column(Text, nullable=False, default="")
    theme: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    depth: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    quiz_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    sources: Mapped[str] = mapped_column(Text, nullable=False, default="")
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    quests: Mapped[list["StudioQuest"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="StudioQuest.position",
    )
    messages: Mapped[list["StudioMessage"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="StudioMessage.seq",
    )


class StudioQuest(Base):
    """A quest on the course. There is no unit tier."""

    __tablename__ = "studio_quests"
    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_studio_quests_course_code"),
        CheckConstraint("position >= 1", name="ck_studio_quests_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    course: Mapped[StudioCourse] = relationship(back_populates="quests")
    close: Mapped["StudioQuestClose | None"] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        uselist=False,
    )
    goals: Mapped[list["StudioQuestGoal"]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="StudioQuestGoal.position",
    )
    moves: Mapped[list["StudioMove"]] = relationship(
        back_populates="quest",
        cascade="all, delete-orphan",
        order_by="StudioMove.position",
    )


class StudioQuestGoal(Base):
    """A goal after the first. The quest columns remain goal 1."""

    __tablename__ = "studio_quest_goals"
    __table_args__ = (
        UniqueConstraint("quest_id", "position", name="uq_studio_quest_goals_position"),
        CheckConstraint("position >= 2", name="ck_studio_quest_goals_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[StudioQuest] = relationship(back_populates="goals")


class StudioMove(Base):
    __tablename__ = "studio_moves"
    __table_args__ = (
        UniqueConstraint("course_id", "code", name="uq_studio_moves_course_code"),
        CheckConstraint("position >= 1", name="ck_studio_moves_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_quests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[StudioQuest] = relationship(back_populates="moves")


class StudioQuestClose(Base):
    """How a quest ends. One row per quest. Dynamic choices store intent only."""

    __tablename__ = "studio_quest_close"
    __table_args__ = (
        CheckConstraint(
            "close_style IN ('one', 'several')",
            name="ck_studio_quest_close_style",
        ),
        CheckConstraint(
            "answer_style IN ('multiple_choice', 'essay', 'mixed')",
            name="ck_studio_quest_close_answer",
        ),
        CheckConstraint(
            "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
            name="ck_studio_quest_close_choice",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_quests.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    close_style: Mapped[str] = mapped_column(String(16), nullable=False)
    answer_style: Mapped[str] = mapped_column(String(32), nullable=False)
    choice_mode: Mapped[str | None] = mapped_column(String(16))
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    intent: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quest: Mapped[StudioQuest] = relationship(back_populates="close")


class StudioMessage(Base):
    """Creation chat for one studio course. Not a kid session."""

    __tablename__ = "studio_messages"
    __table_args__ = (
        UniqueConstraint("course_id", "seq", name="uq_studio_messages_course_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_studio_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("studio_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    proposal: Mapped[dict | None] = mapped_column(JSON)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )

    course: Mapped[StudioCourse] = relationship(back_populates="messages")


class StudioSettings(Base):
    """The CreateCourse model. The kid tutor does not read this row."""

    __tablename__ = "studio_settings"
    __table_args__ = (
        CheckConstraint("id = 'default'", name="ck_studio_settings_singleton"),
        CheckConstraint(
            "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini')",
            name="ck_studio_settings_model",
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False, default="gpt-4o-mini")
```

Alembic migration history. These files are the applied DDL. The models above are the current mapped schema after `013_tutor_quests_on_course`.

Source file `apps/api/alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.database import Base, database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Source file `apps/api/alembic/versions/001_initial.py`:

```python
"""Initial tutor tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_students_slug"),
    )
    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("preamble", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_lesson_plans_slug"),
    )
    op.create_index(
        "uq_lesson_plans_one_active",
        "lesson_plans",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False),
        sa.Column("tutor_instructions", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_plan_id"], ["lesson_plans.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "lesson_plan_id", "position", name="uq_topics_plan_position"
        ),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tutor_prompt", sa.Text(), nullable=False),
        sa.Column("rubric", sa.Text()),
        sa.Column("pass_criteria", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('teach', 'practice', 'quiz')", name="ck_checkpoints_kind"
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "topic_id", "position", name="uq_checkpoints_topic_position"
        ),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("current_topic_id", sa.Uuid()),
        sa.Column("current_checkpoint_id", sa.Uuid()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_sessions_status"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["lesson_plan_id"], ["lesson_plans.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["current_topic_id"], ["topics.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["current_checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_sessions_student_id", "sessions", ["student_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_id", sa.String(200)),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
        sa.UniqueConstraint("client_id", name="uq_messages_client_id"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_table(
        "checkpoint_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_results_score"),
        sa.UniqueConstraint("session_id", "seq", name="uq_results_session_seq"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_checkpoint_results_session_id", "checkpoint_results", ["session_id"]
    )


def downgrade() -> None:
    op.drop_table("checkpoint_results")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("checkpoints")
    op.drop_table("topics")
    op.drop_index("uq_lesson_plans_one_active", table_name="lesson_plans")
    op.drop_table("lesson_plans")
    op.drop_table("students")
```

Source file `apps/api/alembic/versions/002_syllabus_blocks.py`:

```python
"""Block fields on checkpoints: rubric rows, hints, quiz widgets.

Revision ID: 002_syllabus_blocks
Revises: 001_initial
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_syllabus_blocks"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KIND_SQL = "kind IN ('teach', 'practice', 'quiz', 'discovery', 'teach_back')"
OLD_KIND_SQL = "kind IN ('teach', 'practice', 'quiz')"


def upgrade() -> None:
    op.add_column("students", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("lesson_plans", sa.Column("age_min", sa.Integer(), nullable=True))
    op.add_column("lesson_plans", sa.Column("age_max", sa.Integer(), nullable=True))
    op.drop_constraint("ck_checkpoints_kind", "checkpoints", type_="check")
    op.create_check_constraint("ck_checkpoints_kind", "checkpoints", KIND_SQL)
    op.add_column("checkpoints", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column(
        "checkpoints",
        sa.Column("rubric_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "checkpoints",
        sa.Column(
            "hint_ladder",
            sa.JSON(),
            nullable=False,
            server_default=sa.text('\'{"nudge": "", "analogy": "", "scaffold": ""}\''),
        ),
    )
    op.add_column(
        "checkpoints",
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="70"),
    )
    op.add_column("checkpoints", sa.Column("quiz", sa.JSON(), nullable=True))
    op.add_column(
        "checkpoint_results",
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("checkpoint_results", sa.Column("misconception", sa.Text(), nullable=True))
    op.add_column("checkpoint_results", sa.Column("hint_tier", sa.String(16), nullable=True))
    op.add_column("checkpoint_results", sa.Column("choice", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("checkpoint_results", "choice")
    op.drop_column("checkpoint_results", "hint_tier")
    op.drop_column("checkpoint_results", "misconception")
    op.drop_column("checkpoint_results", "rubric_met")
    op.drop_column("checkpoints", "quiz")
    op.drop_column("checkpoints", "pass_score")
    op.drop_column("checkpoints", "hint_ladder")
    op.drop_column("checkpoints", "rubric_rows")
    op.drop_column("checkpoints", "objective")
    op.drop_constraint("ck_checkpoints_kind", "checkpoints", type_="check")
    op.create_check_constraint("ck_checkpoints_kind", "checkpoints", OLD_KIND_SQL)
    op.drop_column("lesson_plans", "age_max")
    op.drop_column("lesson_plans", "age_min")
    op.drop_column("students", "age")
```

Source file `apps/api/alembic/versions/003_model_prompts.py`:

```python
"""Store the system prompt and messages sent to the model.

Revision ID: 003_model_prompts
Revises: 002_syllabus_blocks
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_model_prompts"
down_revision: Union[str, None] = "002_syllabus_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "model_prompts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], ondelete="CASCADE", name="fk_model_prompts_session_id"
        ),
        sa.UniqueConstraint("session_id", "seq", name="uq_model_prompts_session_seq"),
    )
    op.create_index("ix_model_prompts_session_id", "model_prompts", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_model_prompts_session_id", table_name="model_prompts")
    op.drop_table("model_prompts")
```

Source file `apps/api/alembic/versions/004_prompt_message.py`:

```python
"""Tie each stored model prompt to the message that started that turn.

Revision ID: 004_prompt_message
Revises: 003_model_prompts
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_prompt_message"
down_revision: Union[str, None] = "003_model_prompts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("model_prompts", sa.Column("message_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_model_prompts_message_id",
        "model_prompts",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_model_prompts_message_id", "model_prompts", ["message_id"])
    op.execute(
        """
        WITH numbered_prompts AS (
            SELECT id,
                   session_id,
                   row_number() OVER (PARTITION BY session_id ORDER BY seq) AS turn_no
            FROM model_prompts
        ),
        numbered_messages AS (
            SELECT id,
                   session_id,
                   row_number() OVER (PARTITION BY session_id ORDER BY seq) AS turn_no
            FROM messages
            WHERE role = 'user'
        )
        UPDATE model_prompts
        SET message_id = numbered_messages.id
        FROM numbered_prompts
        JOIN numbered_messages
          ON numbered_messages.session_id = numbered_prompts.session_id
         AND numbered_messages.turn_no = numbered_prompts.turn_no
        WHERE model_prompts.id = numbered_prompts.id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_model_prompts_message_id", table_name="model_prompts")
    op.drop_constraint("fk_model_prompts_message_id", "model_prompts", type_="foreignkey")
    op.drop_column("model_prompts", "message_id")
```

Source file `apps/api/alembic/versions/005_syllabus_quests.py`:

```python
"""Replace lesson plans with a 4-tier syllabus and retarget sessions at a quest.

Local test transcripts are cleared. This is not a production data migration.

Revision ID: 005_syllabus_quests
Revises: 004_prompt_message
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_syllabus_quests"
down_revision: Union[str, None] = "004_prompt_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM checkpoint_results")
    op.execute("DELETE FROM sessions")

    op.drop_table("checkpoint_results")
    op.drop_column("sessions", "current_checkpoint_id")
    op.drop_column("sessions", "current_topic_id")
    op.drop_column("sessions", "lesson_plan_id")
    op.drop_table("checkpoints")
    op.drop_table("topics")
    op.drop_index("uq_lesson_plans_one_active", table_name="lesson_plans")
    op.drop_table("lesson_plans")

    op.add_column("students", sa.Column("reading_level", sa.String(80), nullable=False, server_default=""))
    op.add_column("students", sa.Column("modality", sa.String(80), nullable=False, server_default=""))
    op.add_column(
        "students",
        sa.Column("interests", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("students", sa.Column("tutor_persona", sa.String(160), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_lexicon", sa.Text(), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_metaphors", sa.Text(), nullable=False, server_default=""))
    op.add_column("students", sa.Column("tutor_sidekick", sa.String(200), nullable=False, server_default=""))
    op.add_column(
        "students",
        sa.Column("tutor_socratic_strictness", sa.String(40), nullable=False, server_default="balanced"),
    )
    op.add_column(
        "students",
        sa.Column("tutor_struggle_window", sa.String(40), nullable=False, server_default="minimum"),
    )
    op.add_column(
        "students",
        sa.Column("tutor_anti_spoiler", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "students",
        sa.Column(
            "tutor_pacing",
            sa.String(80),
            nullable=False,
            server_default="short-turns-one-question",
        ),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("age_band", sa.String(8), nullable=False),
        sa.Column("standards_alignment", sa.Text(), nullable=False, server_default=""),
        sa.Column("competency_dictionary", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "age_band IN ('6-8', '9-11', '12-14', '15-17')",
            name="ck_courses_age_band",
        ),
        sa.UniqueConstraint("code", name="uq_courses_code"),
    )
    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("enduring_understanding", sa.Text(), nullable=False, server_default=""),
        sa.Column("continuity_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_diagnostic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_capstone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "number", name="uq_units_course_number"),
    )
    op.create_index("ix_units_course_id", "units", ["course_id"])
    op.create_table(
        "quests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("quest_type", sa.String(16), nullable=False, server_default="core"),
        sa.Column("prerequisite_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("competency_tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("dinner_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "quest_type IN ('core', 'branch', 'capstone')",
            name="ck_quests_type",
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code", name="uq_quests_code"),
        sa.UniqueConstraint("unit_id", "position", name="uq_quests_unit_position"),
    )
    op.create_index("ix_quests_unit_id", "quests", ["unit_id"])
    op.create_table(
        "beats",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("bloom_level", sa.String(32), nullable=False, server_default="understand"),
        sa.Column("cognitive_load", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("rubric", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception_map", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hint_ladder", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("widget", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "role IN ('mystery_hook', 'interactive_toy', 'diagnostic_gate', 'feynman_flip')",
            name="ck_beats_role",
        ),
        sa.CheckConstraint("position >= 1 AND position <= 4", name="ck_beats_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_beats_quest_position"),
    )
    op.create_index("ix_beats_quest_id", "beats", ["quest_id"])

    op.add_column("sessions", sa.Column("quest_id", sa.Uuid(), nullable=False))
    op.add_column("sessions", sa.Column("current_beat_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_sessions_quest_id", "sessions", "quests", ["quest_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_sessions_current_beat_id",
        "sessions",
        "beats",
        ["current_beat_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_sessions_quest_id", "sessions", ["quest_id"])

    op.create_table(
        "beat_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("beat_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception", sa.Text(), nullable=True),
        sa.Column("hint_tier", sa.String(16), nullable=True),
        sa.Column("choice", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_beat_results_score"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["beat_id"], ["beats.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("session_id", "seq", name="uq_beat_results_session_seq"),
    )
    op.create_index("ix_beat_results_session_id", "beat_results", ["session_id"])


def downgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")
    op.drop_index("ix_beat_results_session_id", table_name="beat_results")
    op.drop_table("beat_results")
    op.drop_index("ix_sessions_quest_id", table_name="sessions")
    op.drop_constraint("fk_sessions_current_beat_id", "sessions", type_="foreignkey")
    op.drop_constraint("fk_sessions_quest_id", "sessions", type_="foreignkey")
    op.drop_column("sessions", "current_beat_id")
    op.drop_column("sessions", "quest_id")
    op.drop_index("ix_beats_quest_id", table_name="beats")
    op.drop_table("beats")
    op.drop_index("ix_quests_unit_id", table_name="quests")
    op.drop_table("quests")
    op.drop_index("ix_units_course_id", table_name="units")
    op.drop_table("units")
    op.drop_table("courses")
    for column in (
        "tutor_pacing",
        "tutor_anti_spoiler",
        "tutor_struggle_window",
        "tutor_socratic_strictness",
        "tutor_sidekick",
        "tutor_metaphors",
        "tutor_lexicon",
        "tutor_persona",
        "interests",
        "modality",
        "reading_level",
    ):
        op.drop_column("students", column)

    op.create_table(
        "lesson_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("preamble", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("age_min", sa.Integer(), nullable=True),
        sa.Column("age_max", sa.Integer(), nullable=True),
        sa.UniqueConstraint("slug", name="uq_lesson_plans_slug"),
    )
    op.create_index(
        "uq_lesson_plans_one_active",
        "lesson_plans",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "topics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lesson_plan_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False),
        sa.Column("tutor_instructions", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_plan_id"], ["lesson_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("lesson_plan_id", "position", name="uq_topics_plan_position"),
    )
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("tutor_prompt", sa.Text(), nullable=False),
        sa.Column("rubric", sa.Text()),
        sa.Column("pass_criteria", sa.Text()),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("objective", sa.Text()),
        sa.Column("rubric_rows", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hint_ladder", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("pass_score", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("quiz", sa.JSON()),
        sa.CheckConstraint(
            "kind IN ('teach', 'practice', 'quiz', 'discovery', 'teach_back')",
            name="ck_checkpoints_kind",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("topic_id", "position", name="uq_checkpoints_topic_position"),
    )
    op.add_column("sessions", sa.Column("lesson_plan_id", sa.Uuid(), nullable=False))
    op.add_column("sessions", sa.Column("current_topic_id", sa.Uuid(), nullable=True))
    op.add_column("sessions", sa.Column("current_checkpoint_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "sessions_lesson_plan_id_fkey",
        "sessions",
        "lesson_plans",
        ["lesson_plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "sessions_current_topic_id_fkey",
        "sessions",
        "topics",
        ["current_topic_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "sessions_current_checkpoint_id_fkey",
        "sessions",
        "checkpoints",
        ["current_checkpoint_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "checkpoint_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("checkpoint_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("rubric_met", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("misconception", sa.Text()),
        sa.Column("hint_tier", sa.String(16)),
        sa.Column("choice", sa.JSON()),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_results_score"),
        sa.UniqueConstraint("session_id", "seq", name="uq_results_session_seq"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_checkpoint_results_session_id", "checkpoint_results", ["session_id"])
```

Source file `apps/api/alembic/versions/006_quest_cycle.py`:

```python
"""Quest goal, success criterion, and a variable move cycle.

Local test sessions are cleared. Beats from the four-role script are removed
so the new role check can apply. The seed rewrites Rome, Geometry, and AP Macro.

Revision ID: 006_quest_cycle
Revises: 005_syllabus_quests
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_quest_cycle"
down_revision: Union[str, None] = "005_syllabus_quests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")

    op.add_column("quests", sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "quests",
        sa.Column("success_criterion", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "quests",
        sa.Column("requires_teach_back", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.drop_constraint("ck_beats_role", "beats", type_="check")
    op.drop_constraint("ck_beats_position", "beats", type_="check")
    op.execute("DELETE FROM beats")
    op.create_check_constraint(
        "ck_beats_role",
        "beats",
        "role IN ('engage', 'try', 'name', 'show', 'teach_back')",
    )
    op.create_check_constraint("ck_beats_position", "beats", "position >= 1")


def downgrade() -> None:
    op.execute("DELETE FROM model_prompts")
    op.execute("DELETE FROM messages")
    op.execute("DELETE FROM beat_results")
    op.execute("DELETE FROM sessions")
    op.execute("DELETE FROM beats")
    op.drop_constraint("ck_beats_position", "beats", type_="check")
    op.drop_constraint("ck_beats_role", "beats", type_="check")
    op.create_check_constraint(
        "ck_beats_role",
        "beats",
        "role IN ('mystery_hook', 'interactive_toy', 'diagnostic_gate', 'feynman_flip')",
    )
    op.create_check_constraint("ck_beats_position", "beats", "position >= 1 AND position <= 4")
    op.drop_column("quests", "requires_teach_back")
    op.drop_column("quests", "success_criterion")
    op.drop_column("quests", "learning_goal")
```

Source file `apps/api/alembic/versions/007_tutor_profile.py`:

```python
"""One default tutor profile for layers 3 and 4.

Student tutor_* columns stay. This does not clear classes or rewrite courses.

Revision ID: 007_tutor_profile
Revises: 006_quest_cycle
Create Date: 2026-11-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_tutor_profile"
down_revision: Union[str, None] = "006_quest_cycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tutor_profiles",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("instructive", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("persona", sa.String(40), nullable=False),
        sa.Column("lexicon", sa.String(40), nullable=False),
        sa.Column("voice_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metaphors", sa.String(40), nullable=False),
        sa.Column("sidekick", sa.String(40), nullable=False),
        sa.Column("struggle_window", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("anti_spoiler", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("one_question", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_interests", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("growth_praise", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 'default'", name="ck_tutor_profiles_singleton"),
        sa.CheckConstraint(
            "instructive >= 1 AND instructive <= 5",
            name="ck_tutor_profiles_instructive",
        ),
        sa.CheckConstraint(
            "persona IN ('curious-co-explorer', 'tactical-coach', 'debate-moderator', 'patient-explainer')",
            name="ck_tutor_profiles_persona",
        ),
        sa.CheckConstraint(
            "lexicon IN ('early-concrete', 'middle-grade-vivid', 'precise-visual', 'analytical-high-school')",
            name="ck_tutor_profiles_lexicon",
        ),
        sa.CheckConstraint(
            "metaphors IN ('playground-sports', 'buildings-machines', 'policy-cause', 'none')",
            name="ck_tutor_profiles_metaphors",
        ),
        sa.CheckConstraint(
            "sidekick IN ('bumbling-partner', 'rookie-picture', 'pundit', 'off')",
            name="ck_tutor_profiles_sidekick",
        ),
        sa.CheckConstraint(
            "struggle_window IN ('short', 'standard', 'long')",
            name="ck_tutor_profiles_struggle",
        ),
    )
    op.execute(
        """
        INSERT INTO tutor_profiles (
            id, instructive, persona, lexicon, voice_override, metaphors, sidekick,
            struggle_window, anti_spoiler, one_question, use_interests, growth_praise
        ) VALUES (
            'default', 3, 'curious-co-explorer', 'middle-grade-vivid', false,
            'playground-sports', 'bumbling-partner', 'standard', true, true, true, true
        )
        """
    )


def downgrade() -> None:
    op.drop_table("tutor_profiles")
```

Source file `apps/api/alembic/versions/008_stay_on_course.py`:

```python
"""Add stay_on_course to the default tutor profile.

Existing rows get true from the server default. This adds one column.
It does not clear classes, chats, courses, or the profile row.

Revision ID: 008_stay_on_course
Revises: 007_tutor_profile
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_stay_on_course"
down_revision: Union[str, None] = "007_tutor_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_profiles",
        sa.Column(
            "stay_on_course",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tutor_profiles", "stay_on_course")
```

Source file `apps/api/alembic/versions/009_studio.py`:

```python
"""Add CreateCourse studio tables.

This revision creates only studio_ tables. It does not drop tutor tables,
and it does not reseed courses, chats, or studio rows.

Revision ID: 009_studio
Revises: 008_stay_on_course
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_studio"
down_revision: Union[str, None] = "008_stay_on_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False, server_default=""),
        sa.Column("focus", sa.Text(), nullable=False, server_default=""),
        sa.Column("theme", sa.String(240), nullable=False, server_default=""),
        sa.Column("depth", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("sources", sa.Text(), nullable=False, server_default=""),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "depth IN ('survey', 'standard', 'go_deep')",
            name="ck_studio_courses_depth",
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_studio_courses_schema_version"),
        sa.UniqueConstraint("code", name="uq_studio_courses_code"),
    )
    op.create_table(
        "studio_settings",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("model", sa.String(64), nullable=False, server_default="gpt-4o-mini"),
        sa.CheckConstraint("id = 'default'", name="ck_studio_settings_singleton"),
        sa.CheckConstraint(
            "model IN ('gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini')",
            name="ck_studio_settings_model",
        ),
    )
    op.create_table(
        "studio_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_units_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_units_course_code"),
    )
    op.create_index("ix_studio_units_course_id", "studio_units", ["course_id"])
    op.create_table(
        "studio_quests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_quests_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["studio_units.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_quests_course_code"),
    )
    op.create_index("ix_studio_quests_course_id", "studio_quests", ["course_id"])
    op.create_index("ix_studio_quests_unit_id", "studio_quests", ["unit_id"])
    op.create_table(
        "studio_moves",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_moves_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_moves_course_code"),
    )
    op.create_index("ix_studio_moves_course_id", "studio_moves", ["course_id"])
    op.create_index("ix_studio_moves_quest_id", "studio_moves", ["quest_id"])
    op.create_table(
        "studio_quest_close",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("close_style", sa.String(16), nullable=False),
        sa.Column("answer_style", sa.String(32), nullable=False),
        sa.Column("choice_mode", sa.String(16), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("intent", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint(
            "close_style IN ('one', 'several')",
            name="ck_studio_quest_close_style",
        ),
        sa.CheckConstraint(
            "answer_style IN ('multiple_choice', 'essay', 'mixed')",
            name="ck_studio_quest_close_answer",
        ),
        sa.CheckConstraint(
            "choice_mode IS NULL OR choice_mode IN ('predefined', 'dynamic')",
            name="ck_studio_quest_close_choice",
        ),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", name="uq_studio_quest_close_quest"),
    )
    op.create_table(
        "studio_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_studio_messages_role"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "seq", name="uq_studio_messages_course_seq"),
    )
    op.create_index("ix_studio_messages_course_id", "studio_messages", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_studio_messages_course_id", table_name="studio_messages")
    op.drop_table("studio_messages")
    op.drop_table("studio_quest_close")
    op.drop_index("ix_studio_moves_quest_id", table_name="studio_moves")
    op.drop_index("ix_studio_moves_course_id", table_name="studio_moves")
    op.drop_table("studio_moves")
    op.drop_index("ix_studio_quests_unit_id", table_name="studio_quests")
    op.drop_index("ix_studio_quests_course_id", table_name="studio_quests")
    op.drop_table("studio_quests")
    op.drop_index("ix_studio_units_course_id", table_name="studio_units")
    op.drop_table("studio_units")
    op.drop_table("studio_settings")
    op.drop_table("studio_courses")
```

Source file `apps/api/alembic/versions/010_studio_ready.py`:

```python
"""Add the studio course draft flag.

A course is a draft until the creator marks it ready. This adds one column.
It does not drop tutor or studio tables, and it does not reseed chats or courses.

Revision ID: 010_studio_ready
Revises: 009_studio
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_studio_ready"
down_revision: Union[str, None] = "009_studio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_courses",
        sa.Column("ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("studio_courses", "ready")
```

Source file `apps/api/alembic/versions/011_studio_quiz_minutes.py`:

```python
"""Store the minimum time before a studio course's closing quiz.

The kid tutor does not read this column. This adds one column and records
the same number in the course preferences JSON. It does not drop tables,
delete rows, or reseed chats or courses.

Revision ID: 011_studio_quiz_minutes
Revises: 010_studio_ready
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_studio_quiz_minutes"
down_revision: Union[str, None] = "010_studio_ready"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "studio_courses",
        sa.Column("quiz_minutes", sa.Integer(), nullable=False, server_default="5"),
    )
    op.create_check_constraint(
        "ck_studio_courses_quiz_minutes",
        "studio_courses",
        "quiz_minutes IN (2, 5, 10)",
    )
    op.execute(
        """
        UPDATE studio_courses
        SET preferences = (
            COALESCE(preferences, '{}'::json)::jsonb
            || jsonb_build_object('quiz_minutes', quiz_minutes)
        )::json
        WHERE NOT (COALESCE(preferences, '{}'::json)::jsonb ? 'quiz_minutes')
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_studio_courses_quiz_minutes", "studio_courses", type_="check")
    op.drop_column("studio_courses", "quiz_minutes")
```

Source file `apps/api/alembic/versions/012_quests_on_course.py`:

```python
"""Lift studio quests onto the course and drop the unit tier.

Every studio quest, close, and move stays. Quest positions are renumbered in
unit order, then the unit table goes away. Extra goals live in a new table.
Goal 1 stays on the quest columns. Kid course tables and kid chat are not
touched.

Revision ID: 012_quests_on_course
Revises: 011_studio_quiz_minutes
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012_quests_on_course"
down_revision: Union[str, None] = "011_studio_quiz_minutes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "studio_quest_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 2", name="ck_studio_quest_goals_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["studio_quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_studio_quest_goals_position"),
    )
    op.create_index("ix_studio_quest_goals_quest_id", "studio_quest_goals", ["quest_id"])
    op.execute(
        """
        WITH ordered AS (
            SELECT q.id AS id,
                   row_number() OVER (
                       PARTITION BY q.course_id
                       ORDER BY u.position, q.position, q.code
                   ) AS pos
            FROM studio_quests AS q
            JOIN studio_units AS u ON u.id = q.unit_id
        )
        UPDATE studio_quests AS q
        SET position = ordered.pos
        FROM ordered
        WHERE q.id = ordered.id
        """
    )
    op.drop_constraint("studio_quests_unit_id_fkey", "studio_quests", type_="foreignkey")
    op.drop_index("ix_studio_quests_unit_id", table_name="studio_quests")
    op.drop_column("studio_quests", "unit_id")
    op.drop_index("ix_studio_units_course_id", table_name="studio_units")
    op.drop_table("studio_units")


def downgrade() -> None:
    op.create_table(
        "studio_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_studio_units_position"),
        sa.ForeignKeyConstraint(["course_id"], ["studio_courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "code", name="uq_studio_units_course_code"),
    )
    op.create_index("ix_studio_units_course_id", "studio_units", ["course_id"])
    op.add_column("studio_quests", sa.Column("unit_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        INSERT INTO studio_units (id, course_id, code, position, title, learning_goal, success_criterion)
        SELECT gen_random_uuid(), c.id, c.code || '-U1', 1, c.title, '', ''
        FROM studio_courses AS c
        """
    )
    op.execute(
        """
        UPDATE studio_quests AS q
        SET unit_id = u.id
        FROM studio_units AS u
        WHERE u.course_id = q.course_id
        """
    )
    op.alter_column("studio_quests", "unit_id", nullable=False)
    op.create_index("ix_studio_quests_unit_id", "studio_quests", ["unit_id"])
    op.create_foreign_key(
        "studio_quests_unit_id_fkey",
        "studio_quests",
        "studio_units",
        ["unit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_studio_quest_goals_quest_id", table_name="studio_quest_goals")
    op.drop_table("studio_quest_goals")
```

Source file `apps/api/alembic/versions/013_tutor_quests_on_course.py`:

```python
"""Lift tutor quests onto the course and store goals and a close.

Quests leave the unit tier. Each quest keeps its id, so sessions and messages
stay attached. Goal rows and one close are filled from the lesson that was
already there. Chat rows are not deleted.

Revision ID: 013_tutor_quests_on_course
Revises: 012_quests_on_course
Create Date: 2026-11-05
"""

from typing import Sequence, Union
import json
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "013_tutor_quests_on_course"
down_revision: Union[str, None] = "012_quests_on_course"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _points(raw) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    texts = []
    for row in raw:
        if isinstance(row, dict) and str(row.get("text") or "").strip():
            texts.append(str(row["text"]).strip())
    return texts


def _close_from_widget(prompt: str | None, widget) -> tuple[str, str, list]:
    if isinstance(widget, str):
        try:
            widget = json.loads(widget)
        except json.JSONDecodeError:
            widget = None
    question = (prompt or "").strip()
    if not isinstance(widget, dict):
        if "?" in question:
            return "essay", question, []
        return "none", "", []
    stem = str(widget.get("prompt") or question).strip()
    choices = widget.get("choices") if isinstance(widget.get("choices"), list) else []
    answer = widget.get("answer")
    kind = widget.get("type")
    items = []
    if kind in {"single", "flaw", "multi"}:
        answers = set(answer if isinstance(answer, list) else [answer])
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            text = str(choice.get("text") or "").strip()
            if not text:
                continue
            items.append({"text": text, "correct": choice.get("id") in answers})
        return ("multi" if kind == "multi" else "single"), stem, items
    if stem:
        return "essay", stem, []
    return "none", "", []


def _backfill_goals_and_closes() -> None:
    bind = op.get_bind()
    quests = bind.execute(
        sa.text("SELECT id, learning_goal, success_criterion FROM quests")
    ).mappings()
    for quest in quests:
        texts = _points(quest["success_criterion"])
        goal = str(quest["learning_goal"] or "").strip()
        rows = [{"learning_goal": goal or texts[0], "success_criterion": texts[0]}] if texts else [
            {"learning_goal": goal or "States the idea.", "success_criterion": goal or "States the idea."}
        ]
        for index, text in enumerate(texts[1:], start=2):
            rows.append({"learning_goal": text, "success_criterion": text})
        if texts:
            rows[0] = {"learning_goal": goal or texts[0], "success_criterion": texts[0]}
        for position, row in enumerate(rows, start=1):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO quest_goals (id, quest_id, position, learning_goal, success_criterion)
                    VALUES (:id, :quest_id, :position, :learning_goal, :success_criterion)
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "quest_id": quest["id"],
                    "position": position,
                    "learning_goal": row["learning_goal"],
                    "success_criterion": row["success_criterion"],
                },
            )
    shows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT ON (quest_id) quest_id, prompt, widget
            FROM beats
            WHERE role = 'show'
            ORDER BY quest_id, position
            """
        )
    ).mappings()
    seen: set = set()
    for show in shows:
        seen.add(show["quest_id"])
        kind, question, items = _close_from_widget(show["prompt"], show["widget"])
        bind.execute(
            sa.text(
                """
                INSERT INTO quest_closes (id, quest_id, kind, question, items)
                VALUES (:id, :quest_id, :kind, :question, CAST(:items AS json))
                """
            ),
            {
                "id": uuid.uuid4(),
                "quest_id": show["quest_id"],
                "kind": kind,
                "question": question,
                "items": json.dumps(items),
            },
        )
    missing = bind.execute(sa.text("SELECT id FROM quests")).scalars()
    for quest_id in missing:
        if quest_id in seen:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO quest_closes (id, quest_id, kind, question, items)
                VALUES (:id, :quest_id, 'none', '', CAST('[]' AS json))
                """
            ),
            {"id": uuid.uuid4(), "quest_id": quest_id},
        )


def upgrade() -> None:
    op.add_column("courses", sa.Column("description", sa.Text(), nullable=False, server_default=""))
    op.add_column("courses", sa.Column("audience", sa.String(8), nullable=False, server_default="9-11"))
    op.add_column("courses", sa.Column("quest_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("courses", sa.Column("goals_per_quest", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("courses", sa.Column("quiz_minutes", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("courses", sa.Column("in_catalog", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(
        """
        UPDATE courses
        SET description = standards_alignment,
            audience = age_band
        """
    )
    op.create_check_constraint(
        "ck_courses_audience",
        "courses",
        "audience IN ('6-8', '9-11', '12-14', '15-17')",
    )
    op.create_check_constraint(
        "ck_courses_quiz_minutes",
        "courses",
        "quiz_minutes IN (2, 5, 10)",
    )
    op.add_column("quests", sa.Column("course_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE quests AS q
        SET course_id = u.course_id
        FROM units AS u
        WHERE u.id = q.unit_id
        """
    )
    op.execute(
        """
        WITH ordered AS (
            SELECT q.id AS id,
                   row_number() OVER (
                       PARTITION BY u.course_id
                       ORDER BY u.number, q.position, q.code
                   ) AS pos
            FROM quests AS q
            JOIN units AS u ON u.id = q.unit_id
        )
        UPDATE quests AS q
        SET position = ordered.pos + 10000
        FROM ordered
        WHERE q.id = ordered.id
        """
    )
    op.execute("UPDATE quests SET position = position - 10000 WHERE position > 10000")
    op.drop_constraint("uq_quests_unit_position", "quests", type_="unique")
    op.drop_constraint("quests_unit_id_fkey", "quests", type_="foreignkey")
    op.drop_index("ix_quests_unit_id", table_name="quests")
    op.drop_column("quests", "unit_id")
    op.alter_column("quests", "course_id", nullable=False)
    op.create_index("ix_quests_course_id", "quests", ["course_id"])
    op.create_foreign_key(
        "quests_course_id_fkey",
        "quests",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_quests_course_position", "quests", ["course_id", "position"])
    op.drop_index("ix_units_course_id", table_name="units")
    op.drop_table("units")
    op.create_table(
        "quest_goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("learning_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("success_criterion", sa.Text(), nullable=False, server_default=""),
        sa.CheckConstraint("position >= 1", name="ck_quest_goals_position"),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", "position", name="uq_quest_goals_position"),
    )
    op.create_index("ix_quest_goals_quest_id", "quest_goals", ["quest_id"])
    op.create_table(
        "quest_closes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("quest_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.CheckConstraint(
            "kind IN ('essay', 'single', 'multi', 'none')",
            name="ck_quest_closes_kind",
        ),
        sa.ForeignKeyConstraint(["quest_id"], ["quests.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("quest_id", name="uq_quest_closes_quest_id"),
    )
    _backfill_goals_and_closes()
    op.execute(
        """
        UPDATE courses AS c
        SET quest_count = COALESCE((
                SELECT count(*) FROM quests AS q WHERE q.course_id = c.id
            ), 0),
            goals_per_quest = COALESCE((
                SELECT max(counted.n) FROM (
                    SELECT count(*) AS n
                    FROM quest_goals AS g
                    JOIN quests AS q ON q.id = g.quest_id
                    WHERE q.course_id = c.id
                    GROUP BY g.quest_id
                ) AS counted
            ), 1)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_quest_goals_quest_id", table_name="quest_goals")
    op.drop_table("quest_goals")
    op.drop_table("quest_closes")
    op.create_table(
        "units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("enduring_understanding", sa.Text(), nullable=False, server_default=""),
        sa.Column("continuity_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_diagnostic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_capstone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("course_id", "number", name="uq_units_course_number"),
    )
    op.create_index("ix_units_course_id", "units", ["course_id"])
    op.add_column("quests", sa.Column("unit_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        INSERT INTO units (
            id, course_id, number, title, enduring_understanding, continuity_summary,
            is_diagnostic, is_capstone
        )
        SELECT gen_random_uuid(), c.id, 1, c.title, '', c.description, false, false
        FROM courses AS c
        """
    )
    op.execute(
        """
        UPDATE quests AS q
        SET unit_id = u.id
        FROM units AS u
        WHERE u.course_id = q.course_id
        """
    )
    op.alter_column("quests", "unit_id", nullable=False)
    op.create_index("ix_quests_unit_id", "quests", ["unit_id"])
    op.create_foreign_key(
        "quests_unit_id_fkey",
        "quests",
        "units",
        ["unit_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_quests_unit_position", "quests", ["unit_id", "position"])
    op.drop_constraint("uq_quests_course_position", "quests", type_="unique")
    op.drop_constraint("quests_course_id_fkey", "quests", type_="foreignkey")
    op.drop_index("ix_quests_course_id", table_name="quests")
    op.drop_column("quests", "course_id")
    op.drop_constraint("ck_courses_quiz_minutes", "courses", type_="check")
    op.drop_constraint("ck_courses_audience", "courses", type_="check")
    op.drop_column("courses", "in_catalog")
    op.drop_column("courses", "quiz_minutes")
    op.drop_column("courses", "goals_per_quest")
    op.drop_column("courses", "quest_count")
    op.drop_column("courses", "audience")
    op.drop_column("courses", "description")
```

Pydantic request and response models. These are the API schemas. They are not Zod.

Source file `apps/api/app/schemas.py`:

```python
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.engine.choices import METAPHORS, PERSONAS, SIDEKICKS, STRUGGLE_WINDOWS, VOICES, ids


AgeBand = Literal["6-8", "9-11", "12-14", "15-17"]
QuestType = Literal["core", "branch", "capstone"]
BeatRole = Literal["engage", "try", "name", "show", "teach_back"]
Bloom = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]
Load = Literal["low", "medium", "high"]


class StudentOut(BaseModel):
    id: UUID
    slug: str
    display_name: str
    age: int | None = None
    age_band: str
    reading_level: str = ""
    modality: str = ""
    interests: list[str] = Field(default_factory=list)
    tutor_persona: str = ""
    tutor_lexicon: str = ""
    tutor_metaphors: str = ""
    tutor_sidekick: str = ""
    tutor_socratic_strictness: str = "balanced"
    tutor_struggle_window: str = "minimum"
    tutor_anti_spoiler: bool = True
    tutor_pacing: str = "short-turns-one-question"


class StudentCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=4, le=18)
    reading_level: str | None = None
    modality: str | None = None
    interests: list[str] | None = None
    tutor_persona: str | None = None
    tutor_lexicon: str | None = None
    tutor_metaphors: str | None = None
    tutor_sidekick: str | None = None
    tutor_socratic_strictness: str | None = None
    tutor_struggle_window: str | None = None
    tutor_anti_spoiler: bool | None = None
    tutor_pacing: str | None = None


class StudentPatch(BaseModel):
    reading_level: str | None = None
    modality: str | None = None
    interests: list[str] | None = None
    tutor_persona: str | None = None
    tutor_lexicon: str | None = None
    tutor_metaphors: str | None = None
    tutor_sidekick: str | None = None
    tutor_socratic_strictness: str | None = None
    tutor_struggle_window: str | None = None
    tutor_anti_spoiler: bool | None = None
    tutor_pacing: str | None = None


def _closed(value: str, options: tuple[tuple[str, str], ...], field: str) -> None:
    allowed = ids(options)
    if value not in allowed:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(allowed))}")


class TutorProfileIn(BaseModel):
    instructive: int = Field(ge=1, le=5)
    persona: str
    lexicon: str
    voice_override: bool = False
    metaphors: str
    sidekick: str
    struggle_window: str
    anti_spoiler: bool = True
    one_question: bool = True
    use_interests: bool = True
    stay_on_course: bool = True
    growth_praise: bool = True

    @model_validator(mode="after")
    def closed_choices(self) -> "TutorProfileIn":
        _closed(self.persona, PERSONAS, "persona")
        _closed(self.lexicon, VOICES, "lexicon")
        _closed(self.metaphors, METAPHORS, "metaphors")
        _closed(self.sidekick, SIDEKICKS, "sidekick")
        _closed(self.struggle_window, STRUGGLE_WINDOWS, "struggle_window")
        return self


class TutorProfileOut(TutorProfileIn):
    updated_at: datetime


class ProfileDefaults(BaseModel):
    age_band: str
    reading_level: str
    modality: str
    interests: list[str] = Field(default_factory=list)
    tutor_persona: str
    tutor_lexicon: str
    tutor_metaphors: str
    tutor_sidekick: str
    tutor_socratic_strictness: str
    tutor_struggle_window: str
    tutor_anti_spoiler: bool
    tutor_pacing: str


class Competency(BaseModel):
    code: str
    description: str


class StudioImportIn(BaseModel):
    studio_course_id: UUID


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str | None = None
    age_band: AgeBand = "9-11"
    standards_alignment: str = ""


class CoursePatch(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=40)
    age_band: AgeBand
    standards_alignment: str = ""
    competency_dictionary: list[Competency] = Field(default_factory=list)


class UnitCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    number: int | None = Field(default=None, ge=1)
    enduring_understanding: str = ""
    continuity_summary: str = "This unit connects to the quest before it. The next quest carries that idea forward."
    is_diagnostic: bool = False
    is_capstone: bool = False


class UnitPatch(UnitCreate):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)


class QuestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    code: str = Field(min_length=1, max_length=40)
    quest_type: QuestType = "core"
    prerequisite_codes: list[str] = Field(default_factory=list)
    competency_tags: list[str] = Field(default_factory=list)
    dinner_prompt: str = ""
    learning_goal: str = "State the idea this quest is building."
    success_criterion: list = Field(default_factory=list)
    requires_teach_back: bool = False


class QuestPatch(QuestCreate):
    pass


class RubricRowIn(BaseModel):
    id: str = ""
    text: str = ""
    weight: int = Field(default=0, ge=0, le=100)


class HintLadderIn(BaseModel):
    nudge: str = ""
    analogy: str = ""
    scaffold: str = ""


class TrapIn(BaseModel):
    id: str = ""
    trap: str = ""
    note: str = ""


class QuizChoiceIn(BaseModel):
    id: str = ""
    text: str = ""
    misconception: str = ""


class QuizIn(BaseModel):
    type: Literal["single", "multi", "flaw", "order"]
    prompt: str = ""
    choices: list[QuizChoiceIn] = Field(default_factory=list)
    answer: str | list[str] = ""
    explain: bool = False
    misconception: str = ""


class BeatIn(BaseModel):
    role: BeatRole
    bloom_level: Bloom = "understand"
    cognitive_load: Load = "medium"
    prompt: str = ""
    rubric: list[RubricRowIn] = Field(default_factory=list)
    misconception_map: list[TrapIn] = Field(default_factory=list)
    hint_ladder: HintLadderIn = Field(default_factory=HintLadderIn)
    widget: QuizIn | None = None


class BeatWrite(BaseModel):
    beats: list[BeatIn]


class CourseSummary(BaseModel):
    id: UUID
    code: str
    title: str
    age_band: str
    standards_alignment: str
    description: str = ""
    audience: str = ""
    quest_count: int
    goals_per_quest: int = 1
    quiz_minutes: int = 5


class QuestNode(BaseModel):
    id: UUID
    code: str
    title: str
    quest_type: str
    prerequisite_codes: list[str]
    competency_tags: list[str]
    dinner_prompt: str
    position: int


class GoalOut(BaseModel):
    position: int
    learning_goal: str = ""
    success_criterion: str = ""


class CloseOut(BaseModel):
    kind: Literal["essay", "single", "multi", "none"]
    question: str = ""
    items: list[dict] = Field(default_factory=list)


class CatalogQuest(BaseModel):
    id: UUID
    code: str
    title: str
    position: int
    goals: list[GoalOut] = Field(default_factory=list)
    close: CloseOut | None = None


class CourseTree(BaseModel):
    id: UUID
    code: str
    title: str
    age_band: str
    standards_alignment: str
    description: str = ""
    audience: str = ""
    quest_count: int = 1
    goals_per_quest: int = 1
    quiz_minutes: int = 5
    competency_dictionary: list[dict]
    quests: list[CatalogQuest]


class QuestListItem(BaseModel):
    id: UUID
    code: str
    title: str
    quest_type: str
    prerequisite_codes: list[str]
    competency_tags: list[str]
    unit_number: int
    unit_title: str
    position: int


class BeatOut(BaseModel):
    id: UUID
    position: int
    role: str
    bloom_level: str
    cognitive_load: str
    prompt: str
    rubric: list[dict]
    misconception_map: list[dict]
    hint_ladder: dict
    widget: dict | None = None


class QuestDetail(QuestNode):
    course_id: UUID
    learning_goal: str = ""
    success_criterion: list[dict] = Field(default_factory=list)
    requires_teach_back: bool = False
    beats: list[BeatOut]
    goals: list[GoalOut] = Field(default_factory=list)
    close: CloseOut | None = None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    client_id: str | None
    created_at: datetime


class BoardResult(BaseModel):
    id: UUID
    score: int
    passed: bool
    feedback: str
    created_at: datetime


class BoardBeat(BaseModel):
    id: UUID
    position: int
    role: str
    latest_result: BoardResult | None


class RubricRowOut(BaseModel):
    id: str
    text: str
    weight: int
    met: bool


class QuizChoiceOut(BaseModel):
    id: str
    text: str


class QuizOut(BaseModel):
    type: Literal["single", "flaw", "order", "multi"]
    prompt: str
    choices: list[QuizChoiceOut]
    explain: bool


class BlockStep(BaseModel):
    id: UUID
    position: int
    kind: str
    title: str
    state: str


class CurrentBlock(BaseModel):
    id: UUID
    kind: str
    title: str
    objective: str
    tutor_prompt: str
    rubric: list[RubricRowOut]
    hint_tier: Literal["nudge", "analogy", "scaffold"]
    hint_text: str
    quiz: QuizOut | None


class BoardOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    course_code: str
    course_title: str
    quest_id: UUID
    quest_code: str
    quest_title: str
    enduring_understanding: str
    current_beat_id: UUID | None
    beats: list[BoardBeat]
    messages: list[MessageOut]
    steps: list[BlockStep]
    current_block: CurrentBlock | None = None


class ResultOut(BaseModel):
    id: UUID
    beat_id: UUID
    beat_role: str
    beat_position: int
    quest_title: str
    score: int
    passed: bool
    feedback: str
    misconception: str | None = None
    hint_tier: str | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    student_id: UUID
    student_display_name: str
    quest_id: UUID
    quest_code: str
    quest_title: str
    course_title: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    result_count: int


class ModelPromptOut(BaseModel):
    id: UUID
    session_id: UUID
    message_id: UUID | None = None
    seq: int
    system_prompt: str
    messages: list[Any]
    model: str
    created_at: datetime


class SessionQuest(BaseModel):
    id: UUID
    code: str
    title: str
    course_code: str
    course_title: str


class SessionBeat(BaseModel):
    id: UUID
    position: int
    role: str


class SessionAdminOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    quest: SessionQuest
    current_beat_id: UUID | None
    beats: list[SessionBeat]
    messages: list[MessageOut]
    results: list[ResultOut]
    prompts: list[ModelPromptOut] = Field(default_factory=list)


class PromptBundleOut(BaseModel):
    system_prompt: str
    response_schema: dict
    temperature: float


class SessionOpen(BaseModel):
    student_id: UUID
    quest_id: UUID
    fresh: bool = False


class MessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    client_id: str | None = Field(default=None, max_length=200)


class WidgetIn(BaseModel):
    choice: str | list[str]
    explanation: str = Field(default="", max_length=2000)


class DiagramCheckIn(BaseModel):
    diagram: Any = None


class TurnScoreIn(BaseModel):
    rubric_met: list[str] = Field(default_factory=list)
    misconception: str | None = None
    hint_tier: Literal["nudge", "analogy", "scaffold"] = "nudge"
    advance: bool = False


class ModelPromptIn(BaseModel):
    system_prompt: str = Field(min_length=1)
    messages: list[Any] = Field(default_factory=list)
    model: str = Field(default="", max_length=120)
    message_id: UUID | None = None


StudioDepth = Literal["survey", "standard", "go_deep"]
StudioCloseStyle = Literal["one", "several"]
StudioAnswerStyle = Literal["multiple_choice", "essay", "mixed"]
StudioChoiceMode = Literal["predefined", "dynamic"]


class StudioChoiceOut(BaseModel):
    text: str
    correct: bool = False


class StudioCloseOut(BaseModel):
    close_style: StudioCloseStyle
    answer_style: StudioAnswerStyle
    choice_mode: StudioChoiceMode | None = None
    items: list[StudioChoiceOut] = Field(default_factory=list)
    questions: list[StudioChoiceOut] = Field(default_factory=list)
    intent: str = ""
    selection: Literal["single", "multi"] | None = None


class StudioGoalOut(BaseModel):
    position: int
    learning_goal: str
    success_criterion: str


class StudioMoveOut(BaseModel):
    id: UUID
    code: str
    position: int
    title: str
    learning_goal: str
    success_criterion: str


class StudioQuestOut(BaseModel):
    id: UUID
    code: str
    position: int
    title: str
    learning_goal: str
    success_criterion: str
    goals: list[StudioGoalOut] = Field(default_factory=list)
    close: StudioCloseOut | None = None
    moves: list[StudioMoveOut]


class StudioPhaseOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    open_codes: list[str]


class StudioStripOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    filled: bool
    active: bool


class StudioViewOut(BaseModel):
    name: Literal["quests", "goals", "close", "ready"]
    label: Literal["Quests", "Goals/Success Criteria", "Close", "Ready"]
    codes: list[str]


class StudioPhaseIn(BaseModel):
    name: Literal["quests", "goals", "close", "ready", "structure"]


class StudioCourseOut(BaseModel):
    id: UUID
    code: str
    title: str
    audience: str
    focus: str
    theme: str
    depth: StudioDepth
    quiz_minutes: Literal[2, 5, 10]
    sources: str
    schema_version: int
    close_default: StudioCloseOut
    ready: bool
    gaps: list[str]
    phase: StudioPhaseOut
    strip: list[StudioStripOut]
    view: StudioViewOut
    quests: list[StudioQuestOut]
    quest_count: int = 10
    goals_per_quest: int = 3
    undo: bool = False
    stage: StudioPhaseOut | None = None
    stage_strip: list[StudioStripOut] = Field(default_factory=list)
    stage_view: StudioViewOut | None = None
    stage_gaps: list[str] = Field(default_factory=list)
    can_advance: bool = False
    can_push: bool = False
    updated_at: datetime


class StudioCourseSummary(BaseModel):
    id: UUID
    code: str
    title: str
    updated_at: datetime


class StudioCourseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=240)


class StudioDeleteIn(BaseModel):
    password: str = Field(default="", max_length=200)


class StudioCopyIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)


class StudioPreferencesIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    audience: str = ""
    focus: str = ""
    theme: str = ""
    description: str = ""
    depth: StudioDepth = "standard"
    quiz_minutes: int = 5
    sources: str = ""
    quest_count: int = 10
    goals_per_quest: int = 3
    close_default: dict


class StudioMessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    seq: int
    proposal: dict | None = None
    applied: bool
    created_at: datetime


class StudioMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)
    proposal: dict | None = None


class StudioSettingsOut(BaseModel):
    model: str
    options: list[str]


class StudioSettingsIn(BaseModel):
    model: str = Field(min_length=1, max_length=64)


class StudioPromptOut(BaseModel):
    model: str
    system_prompt: str
    response_schema: dict
    temperature: float


class StudioIndexesIn(BaseModel):
    indexes: list[int] | None = None


class StudioEditIn(BaseModel):
    kind: Literal["quest", "move"]
    code: str = Field(min_length=1, max_length=40)
    title: str | None = None
    learning_goal: str | None = None
    success_criterion: str | None = None


class StudioAcceptOut(BaseModel):
    course: StudioCourseOut
    message: StudioMessageOut


class StudioOpeningOut(BaseModel):
    course: StudioCourseOut
    messages: list[StudioMessageOut]


class StudioTurnIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class StudioTurnOut(BaseModel):
    wrote: bool
    handled: bool = False
    awaiting_draft: bool = False
    user: StudioMessageOut | None = None
    assistant: StudioMessageOut | None = None
    course: StudioCourseOut | None = None


class StudioDraftIn(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    operations: list[dict[str, Any]] | None = None
    reply: str = ""
    fallback: bool = False


class StudioFallbackIn(BaseModel):
    content: str = Field(default="", max_length=20000)


class StudioTreeEditIn(BaseModel):
    action: Literal[
        "add_quest",
        "update_quest",
        "delete_quest",
        "add_goal",
        "update_goal",
        "delete_goal",
        "set_close",
    ]
    code: str | None = None
    title: str | None = None
    position: int | None = None
    learning_goal: str | None = None
    success_criterion: str | None = None
    close: dict[str, Any] | None = None
```

TypeScript interfaces for the kid catalog, tutor profile, board, and chat viewer. There is no Zod schema in `apps/web`. A repository search for `z.object` and `from "zod"` returns no matches. `zod` is listed in `apps/web/package.json` and is unused by application source.

Source file `apps/web/lib/types.ts`:

```typescript
export type Student = {
  id: string;
  slug: string;
  display_name: string;
  age: number | null;
  age_band: string;
  reading_level: string;
  modality: string;
  interests: string[];
  tutor_persona: string;
  tutor_lexicon: string;
  tutor_metaphors: string;
  tutor_sidekick: string;
  tutor_socratic_strictness: string;
  tutor_struggle_window: string;
  tutor_anti_spoiler: boolean;
  tutor_pacing: string;
};

export type TutorProfile = {
  instructive: number;
  persona: string;
  lexicon: string;
  voice_override: boolean;
  metaphors: string;
  sidekick: string;
  struggle_window: string;
  anti_spoiler: boolean;
  one_question: boolean;
  use_interests: boolean;
  stay_on_course: boolean;
  growth_praise: boolean;
  updated_at?: string;
};

export type ProfileDefaults = {
  age_band: string;
  reading_level: string;
  modality: string;
  interests: string[];
  tutor_persona: string;
  tutor_lexicon: string;
  tutor_metaphors: string;
  tutor_sidekick: string;
  tutor_socratic_strictness: string;
  tutor_struggle_window: string;
  tutor_anti_spoiler: boolean;
  tutor_pacing: string;
};

export type CourseSummary = {
  id: string;
  code: string;
  title: string;
  age_band: string;
  standards_alignment: string;
  description: string;
  audience: string;
  quest_count: number;
  goals_per_quest: number;
  quiz_minutes: number;
};

export type QuestListItem = {
  id: string;
  code: string;
  title: string;
  quest_type: string;
  prerequisite_codes: string[];
  competency_tags: string[];
  unit_number: number;
  unit_title: string;
  position: number;
};

export type Competency = {
  code: string;
  description: string;
};

export type QuestNode = {
  id: string;
  code: string;
  title: string;
  quest_type: string;
  prerequisite_codes: string[];
  competency_tags: string[];
  dinner_prompt: string;
  position: number;
};

export type CourseGoal = {
  position: number;
  learning_goal: string;
  success_criterion: string;
};

export type CourseClose = {
  kind: "essay" | "single" | "multi" | "none";
  question: string;
  items: { text: string; correct?: boolean }[];
};

export type CatalogQuest = {
  id: string;
  code: string;
  title: string;
  position: number;
  goals: CourseGoal[];
  close: CourseClose | null;
};

export type CourseTree = {
  id: string;
  code: string;
  title: string;
  age_band: string;
  standards_alignment: string;
  description: string;
  audience: string;
  quest_count: number;
  goals_per_quest: number;
  quiz_minutes: number;
  competency_dictionary: Competency[];
  quests: CatalogQuest[];
};

export type RubricRowInput = {
  id: string;
  text: string;
  weight: number;
};

export type HintLadder = {
  nudge: string;
  analogy: string;
  scaffold: string;
};

export type TrapInput = {
  id: string;
  trap: string;
  note: string;
};

export type QuizChoiceInput = {
  id: string;
  text: string;
  misconception: string;
};

export type QuizInput = {
  type: "single" | "multi" | "flaw" | "order";
  prompt: string;
  choices: QuizChoiceInput[];
  answer: string | string[];
  explain: boolean;
  misconception: string;
};

export type BeatOut = {
  id: string;
  position: number;
  role: string;
  bloom_level: string;
  cognitive_load: string;
  prompt: string;
  rubric: RubricRowInput[];
  misconception_map: TrapInput[];
  hint_ladder: HintLadder;
  widget: QuizInput | null;
};

export type QuestDetail = QuestNode & {
  course_id: string;
  learning_goal: string;
  success_criterion: RubricRowInput[];
  requires_teach_back: boolean;
  beats: BeatOut[];
  goals: CourseGoal[];
  close: CourseClose | null;
};

export type BoardResult = {
  id: string;
  score: number;
  passed: boolean;
  feedback: string;
  created_at: string;
};

export type BoardBeat = {
  id: string;
  position: number;
  role: string;
  latest_result: BoardResult | null;
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  client_id: string | null;
  created_at: string;
};

export type RubricRow = {
  id: string;
  text: string;
  weight: number;
  met: boolean;
};

export type QuizChoice = {
  id: string;
  text: string;
};

export type KidQuiz = {
  type: "single" | "multi" | "flaw" | "order";
  prompt: string;
  choices: QuizChoice[];
  explain: boolean;
};

export type TriangleSide = {
  label: string;
  length: number;
};

export type TriangleAngle = {
  label: string;
  degrees: number;
};

export type TriangleDiagram = {
  kind: "triangle";
  sides: TriangleSide[];
  angles: TriangleAngle[];
  right_angle: boolean;
};

export type BlockStep = {
  id: string;
  position: number;
  kind: string;
  title: string;
  state: string;
};

export type CurrentBlock = {
  id: string;
  kind: string;
  title: string;
  objective: string;
  tutor_prompt: string;
  rubric: RubricRow[];
  hint_tier: "nudge" | "analogy" | "scaffold";
  hint_text: string;
  quiz: KidQuiz | null;
};

export type Board = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  course_code: string;
  course_title: string;
  quest_id: string;
  quest_code: string;
  quest_title: string;
  enduring_understanding: string;
  current_beat_id: string | null;
  beats: BoardBeat[];
  messages: StoredMessage[];
  steps: BlockStep[];
  current_block: CurrentBlock | null;
};

export type ResultRow = {
  id: string;
  beat_id: string;
  beat_role: string;
  beat_position: number;
  quest_title: string;
  score: number;
  passed: boolean;
  feedback: string;
  misconception: string | null;
  hint_tier: string | null;
  created_at: string;
};

export type SessionSummary = {
  id: string;
  student_id: string;
  student_display_name: string;
  quest_id: string;
  quest_code: string;
  quest_title: string;
  course_title: string;
  status: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  result_count: number;
};

export type ModelPrompt = {
  id: string;
  session_id: string;
  message_id: string | null;
  seq: number;
  system_prompt: string;
  messages: unknown[];
  model: string;
  created_at: string;
};

export type SessionQuest = {
  id: string;
  code: string;
  title: string;
  course_code: string;
  course_title: string;
};

export type SessionBeat = {
  id: string;
  position: number;
  role: string;
};

export type SessionDetail = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  student: Student;
  quest: SessionQuest;
  current_beat_id: string | null;
  beats: SessionBeat[];
  messages: StoredMessage[];
  results: ResultRow[];
  prompts: ModelPrompt[];
};

export type PromptBundle = {
  system_prompt: string;
  response_schema: Record<string, unknown>;
  temperature: number;
};
```

TypeScript interfaces for the Create course studio, including preferences fields on `StudioCourse`, goals, and close:

Source file `apps/web/lib/studio.ts`:

```typescript
export type StudioClose = {
  close_style: "one" | "several";
  answer_style: "multiple_choice" | "essay" | "mixed";
  choice_mode: "predefined" | "dynamic" | null;
  items: { text: string; correct?: boolean }[];
  questions: { text: string }[];
  intent: string;
  selection?: "single" | "multi" | null;
};

export type StudioGoal = {
  position: number;
  learning_goal: string;
  success_criterion: string;
};

export type StudioMove = {
  id: string;
  code: string;
  position: number;
  title: string;
  learning_goal: string;
  success_criterion: string;
};

export type StudioQuest = {
  id: string;
  code: string;
  position: number;
  title: string;
  learning_goal: string;
  success_criterion: string;
  goals: StudioGoal[];
  close: StudioClose | null;
  moves: StudioMove[];
};

export type StudioPhaseName = "quests" | "goals" | "close" | "ready";

export type StudioPhase = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  open_codes: string[];
};

export type StudioStripPhase = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  filled: boolean;
  active: boolean;
};

export type StudioView = {
  name: StudioPhaseName;
  label: "Quests" | "Goals/Success Criteria" | "Close" | "Ready";
  codes: string[];
};

export type StudioCourse = {
  id: string;
  code: string;
  title: string;
  audience: string;
  focus: string;
  theme: string;
  depth: "survey" | "standard" | "go_deep";
  quiz_minutes: 2 | 5 | 10;
  sources: string;
  schema_version: number;
  close_default: StudioClose;
  ready: boolean;
  gaps: string[];
  phase: StudioPhase;
  strip: StudioStripPhase[];
  view: StudioView;
  quests: StudioQuest[];
  quest_count: number;
  goals_per_quest: number;
  undo: boolean;
  stage: StudioPhase;
  stage_strip: StudioStripPhase[];
  stage_view: StudioView;
  stage_gaps: string[];
  can_advance: boolean;
  can_push: boolean;
  updated_at: string;
};

export type StudioSummary = {
  id: string;
  code: string;
  title: string;
  updated_at: string;
};

export type StudioOperation = {
  op: "add" | "update" | "remove";
  kind: "course" | "quest" | "move";
  code: string;
  parent?: string | null;
  title?: string | null;
  learning_goal?: string | null;
  success_criterion?: string | null;
  position?: number | null;
};

export type StudioMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  seq: number;
  proposal: { operations: StudioOperation[]; phase?: StudioPhaseName } | null;
  applied: boolean;
  created_at: string;
};

export type StudioSettings = {
  model: string;
  options: string[];
};

export const DEPTHS = [
  { value: "survey", label: "Survey" },
  { value: "standard", label: "Standard" },
  { value: "go_deep", label: "Go deep" },
] as const;

export const AGE_BANDS = ["6-8", "9-11", "12-14", "15-17"] as const;

export const QUIZ_MINUTES = [2, 5, 10] as const;

export function describeOperation(op: StudioOperation): string {
  const title = op.title ? `: ${op.title}` : "";
  if (op.op === "remove") return `Remove ${op.code}`;
  if (op.op === "add") return `Add ${op.kind} ${op.code}${title}`;
  return `Update ${op.code}${title}`;
}

export function closeSummary(close: StudioClose): string {
  const count = close.questions?.length ?? 0;
  const question = count === 0 ? "No questions" : close.close_style === "one" ? "One question" : "Several questions";
  const answer =
    close.answer_style === "multiple_choice"
      ? "Multiple choice"
      : close.answer_style === "essay"
        ? "Essay"
        : "Mixed";
  if (close.answer_style === "essay" && count === 0) return "No questions";
  if (close.answer_style === "essay") return `${question} · ${answer}`;
  if (close.selection === "multi") return `${question} · Multi-choice`;
  if (close.answer_style === "multiple_choice") return `${question} · Single choice`;
  const mode = close.choice_mode === "predefined" ? "Predefined choices" : "Dynamic choices";
  return `${question} · ${answer} · ${mode}`;
}
```

### 3. Pipeline 1: Course Creation LLM Logic & Preferences Injection

The Course Designer is `apps/api/app/studio.py`. The Next.js caller is `apps/web/app/api/studio/chat/route.ts`. Python does not call the model. `GET /studio/courses/{course_id}/prompt` returns `system_prompt`, `response_schema`, `temperature` (`STUDIO_TEMPERATURE = 0.4`), and the model id from `studio_settings`.

Preference injection path: `PATCH /studio/courses/{course_id}` calls `update_preferences`. That function writes `title`, `audience`, `focus`, `theme` (from `theme`, or from `description` when theme is blank), `depth`, `quiz_minutes`, and `sources` onto columns, and writes `close_default`, `depth`, `quiz_minutes`, `audience`, `theme`, `sources`, `quest_count`, and `goals_per_quest` into `studio_courses.preferences`. `system_prompt` then reads `course.theme` as `Course description`, calls `phase_instructions`, `quest_count_of`, and `goals_per_quest_of`, and appends `json.dumps` of `course_out(course)`. The model is told that a patch is not saved until `Push draft to Tree`, which is `push_draft` then `apply_patch`.

Structured output is `response_schema(course)`, which narrows operations by `instruction_stage`. The stage is quests, goals, close, or ready. Goals operations carry `learning_goal`, `success_criterion`, and `goals`. Close operations carry `close` from `_close_schema`.

Admin import of a file is `POST /courses/import`, which calls `replace_course` after `validate_course`. Admin import of a studio draft is `POST /courses/import-studio` with body `StudioImportIn.studio_course_id`, which calls `copy_studio_into_catalog`. That builds a kid-catalog dict in `catalog_from_studio` (`_rubric_from_goals`, `_close_from_studio_row`, `_beats_for_close`) and persists it with `replace_course` or `update_course_in_place`. Seed courses do not go through the studio LLM. `seed()` calls the same `replace_course` / `update_course_in_place` on `COURSES` from `apps/api/app/curriculum/__init__.py`.

Source file `apps/api/app/studio.py`:

```python
"""CreateCourse studio: preferences, the typed patch, and the model row.

The tutor seed does not import this module. Patches are checked before they
are written. A model reply can describe a change, and the tree stays as it
is until the creator confirms that change in the chat.
"""

from __future__ import annotations

import copy
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.models import (
    StudioCourse,
    StudioMessage,
    StudioMove,
    StudioQuest,
    StudioQuestClose,
    StudioQuestGoal,
    StudioSettings,
)
from app.schemas import (
    StudioCloseOut,
    StudioCourseOut,
    StudioCourseSummary,
    StudioMessageOut,
    StudioMoveOut,
    StudioPhaseOut,
    StudioGoalOut,
    StudioQuestOut,
    StudioStripOut,
    StudioViewOut,
)

logger = logging.getLogger(__name__)

CLOSE_STYLES = ("one", "several")
ANSWER_STYLES = ("multiple_choice", "essay", "mixed")
CHOICE_MODES = ("predefined", "dynamic")
DEPTHS = ("survey", "standard", "go_deep")
QUIZ_MINUTES = (2, 5, 10)
AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")
STUDIO_MODELS = ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini")
DEFAULT_STUDIO_MODEL = "gpt-4o-mini"
SCHEMA_VERSION = 2
SETTINGS_ID = "default"
STUDIO_TEMPERATURE = 0.4
DELETE_PASSWORD = "BulmerGardens"

COURSE_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")
NODE_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){1,6}$")
KINDS = ("course", "quest", "move")
OPS = ("add", "update", "remove")
PARENT_KIND = {"move": "quest"}
DEFAULT_QUEST_COUNT = 10
DEFAULT_GOALS_PER_QUEST = 3
TEXT_LIMITS = {
    "title": 240,
    "audience": 500,
    "focus": 2000,
    "theme": 240,
    "sources": 500,
    "learning_goal": 2000,
    "success_criterion": 2000,
    "intent": 2000,
}
COURSE_FIELDS = ("title", "audience", "focus", "theme", "depth", "sources", "close_default")
NODE_FIELDS = ("title", "learning_goal", "success_criterion", "position")

_MISSING = object()

def _close_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "close_style": {"type": "string", "enum": ["one", "several"]},
            "answer_style": {
                "type": "string",
                "enum": ["multiple_choice", "essay", "mixed"],
            },
            "choice_mode": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["predefined", "dynamic"]},
                ]
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"text": {"type": "string"}, "correct": {"type": "boolean"}},
                    "required": ["text", "correct"],
                },
            },
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            "intent": {"type": "string"},
            "selection": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["single", "multi"]},
                ],
                "description": "single or multi for a choice question. Null for an essay or no questions.",
            },
        },
        "required": ["close_style", "answer_style", "choice_mode", "items", "questions", "intent", "selection"],
    }


def _operation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "op": {"type": "string", "enum": ["add", "update", "remove"]},
            "kind": {"type": "string", "enum": ["course", "quest", "move"]},
            "code": {"type": "string"},
            "parent": {
                "type": ["string", "null"],
                "description": (
                    "Parent code when adding a move. Quests sit on the course, so parent is null. "
                    "Null on update. An update names the item by its own code and must not send a parent."
                ),
            },
            "title": {"type": ["string", "null"]},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "learning_goal": {"type": "string"},
                                "success_criterion": {"type": "string"},
                                "position": {"type": "integer"},
                            },
                            "required": ["learning_goal", "success_criterion", "position"],
                        },
                    },
                ]
            },
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
            "audience": {"type": ["string", "null"]},
            "focus": {"type": ["string", "null"]},
            "theme": {"type": ["string", "null"]},
            "depth": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "enum": ["survey", "standard", "go_deep"]},
                ]
            },
            "sources": {"type": ["string", "null"]},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
            "close_default": {"anyOf": [{"type": "null"}, _close_schema()]},
        },
        "required": [
            "op",
            "kind",
            "code",
            "parent",
            "title",
            "learning_goal",
            "success_criterion",
            "goals",
            "position",
            "audience",
            "focus",
            "theme",
            "depth",
            "sources",
            "close",
            "close_default",
        ],
    }


STUDIO_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": (
                "What the creator reads. Say which framework a suggestion comes from. "
                "Do not say the course was saved or that the structure was accepted."
            ),
        },
        "patch": {
            "description": "Null when nothing should change. Otherwise typed add, update, or remove operations.",
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "operations": {
                            "type": "array",
                            "maxItems": 40,
                            "items": _operation_schema(),
                        }
                    },
                    "required": ["operations"],
                },
            ],
        },
    },
    "required": ["reply", "patch"],
}


def _plain_error(field: str, message: str) -> str:
    """One sentence for the chat. No raw field path such as `close_style:`."""
    labels = {
        "close_style": "Close style",
        "answer_style": "Answer style",
        "choice_mode": "Choice mode",
        "learning_goal": "The learning goal",
        "success_criterion": "The success criterion",
        "close_default": "The close default",
        "content": "The message",
        "proposal": "The proposal",
        "message": "The message",
        "model": "The model",
        "patch": "The patch",
        "op": "The operation",
        "kind": "The kind",
        "code": "The code",
        "parent": "The parent",
        "title": "The title",
        "items": "The items",
        "questions": "The questions",
        "goals": "The goals",
        "intent": "The intent",
        "close": "The close",
        "position": "The position",
        "audience": "The audience",
        "focus": "The focus",
        "theme": "The theme",
        "sources": "The sources",
        "depth": "Detail",
        "phase": "The phase",
        "ready": "Ready",
        "password": "The password",
    }
    if field == "parent":
        return message if message.endswith(".") else f"The parent {message}."
    if message[:1].isupper():
        return message if message.endswith(".") else f"{message}."
    label = labels.get(field, "This value")
    if message.startswith("dynamic "):
        return "Dynamic choices store the intent, not the items."
    if message.startswith("each "):
        return f"{message[0].upper()}{message[1:]}."
    return f"{label} {message}."


class StudioError(Exception):
    def __init__(self, field: str, message: str, status: int = 422, plain: str | None = None) -> None:
        self.field = field
        self.message = message
        self.status = status
        self.plain = plain if plain is not None else _plain_error(field, message)
        super().__init__(self.plain)


POSITION_REASON = "Position must be an integer from 1 to 200."


def rejection_reply(_model_reply: str, reason: str) -> str:
    """The chat shows this reason alone. The model's claim that it saved is dropped."""
    return reason.strip()


class _Node:
    def __init__(self, kind: str, code: str, parent: str | None, position: int) -> None:
        self.kind = kind
        self.code = code
        self.parent = parent
        self.position = position


def default_close() -> dict:
    return {
        "close_style": "one",
        "answer_style": "essay",
        "choice_mode": None,
        "items": [],
        "questions": [],
        "intent": "",
    }


def default_preferences() -> dict:
    return {
        "close_default": default_close(),
        "depth": "standard",
        "quiz_minutes": 5,
        "audience": "",
        "theme": "",
        "sources": "",
        "quest_count": DEFAULT_QUEST_COUNT,
        "goals_per_quest": DEFAULT_GOALS_PER_QUEST,
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _field(op: dict, key: str):
    if key not in op or op[key] is None:
        return _MISSING
    return op[key]


def _text(field: str, value, *, required: bool = False, allow_blank: bool = True) -> str:
    if not isinstance(value, str):
        raise StudioError(field, "must be text")
    text = value.strip()
    if required and not text:
        raise StudioError(field, "is required")
    if not allow_blank and not text:
        raise StudioError(field, "is required")
    limit = TEXT_LIMITS[field]
    if len(text) > limit:
        raise StudioError(field, "is too long")
    return text


def _upper(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StudioError(field, "must be a short code")
    return value.strip().upper()


def normalize_course_code(value) -> str:
    code = _upper(value, "code")
    if not COURSE_CODE.fullmatch(code):
        raise StudioError("code", "must be a short code such as GEO")
    return code


def normalize_node_code(value, course_code: str, field: str = "code") -> str:
    code = _upper(value, field)
    prefix = f"{course_code}-"
    if not NODE_CODE.fullmatch(code) or len(code) > 40 or not code.startswith(prefix):
        raise StudioError(field, f"must be a short stable code such as {course_code}-Q1")
    return code


def normalize_depth(value) -> str:
    if value not in DEPTHS:
        raise StudioError("depth", "must be survey, standard, or go_deep", plain="Detail must be survey, standard, or go deep.")
    return value


def normalize_quiz_minutes(value) -> int:
    if isinstance(value, bool) or value not in QUIZ_MINUTES:
        raise StudioError(
            "quiz_minutes",
            "must be 2, 5, or 10",
            plain="Minimum time before the closing quiz must be 2, 5, or 10 minutes.",
        )
    return value


def normalize_audience(value) -> str:
    if value not in AGE_BANDS:
        raise StudioError(
            "audience",
            "must be an age band",
            plain="Audience must be 6-8, 9-11, 12-14, or 15-17.",
        )
    return value


def normalize_sources(value) -> str:
    text = _text("sources", value)
    if text.lower() == "none":
        return ""
    return text


def _items(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StudioError("items", "must be a list of choices")
    cleaned = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            text = item["text"].strip()
        else:
            raise StudioError("items", "each choice needs text")
        if not text or len(text) > 240:
            raise StudioError("items", "each choice needs short text")
        choice = {"text": text}
        if isinstance(item, dict) and item.get("correct") is True:
            choice["correct"] = True
        cleaned.append(choice)
    return cleaned


def _questions(value) -> list[dict]:
    """A close may list no questions. One or more is ordinary, and empty still saves."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise StudioError("questions", "must be a list")
    cleaned = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            text = item["text"].strip()
        else:
            raise StudioError("questions", "each question needs text")
        if not text or len(text) > 500:
            raise StudioError("questions", "each question needs short text")
        cleaned.append({"text": text})
    return cleaned


def normalize_goals(value) -> list[dict]:
    """Goal rows for one quest. Position 1 is stored on the quest columns."""
    if not isinstance(value, list):
        raise StudioError("goals", "must be a list")
    cleaned = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise StudioError("goals", "each goal needs text")
        goal_raw = item.get("learning_goal")
        criterion_raw = item.get("success_criterion")
        goal = _text("learning_goal", goal_raw if isinstance(goal_raw, str) else "")
        criterion = _text("success_criterion", criterion_raw if isinstance(criterion_raw, str) else "")
        position = item.get("position", index)
        if position is None:
            position = index
        cleaned.append(
            {
                "position": _position(position),
                "learning_goal": goal,
                "success_criterion": criterion,
            }
        )
    cleaned.sort(key=lambda row: row["position"])
    return [
        {"position": number, "learning_goal": row["learning_goal"], "success_criterion": row["success_criterion"]}
        for number, row in enumerate(cleaned, start=1)
    ]


def _target_count(value, default: int, field: str, plain: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 200:
        raise StudioError(field, "must be a whole number from 1 to 200", plain=plain)
    return value


def quest_count_of(course: StudioCourse) -> int:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("quest_count") if isinstance(raw, dict) else None
    try:
        return _target_count(stored, DEFAULT_QUEST_COUNT, "quest_count", "Number of quests must be a whole number from 1 to 200.")
    except StudioError:
        return DEFAULT_QUEST_COUNT


def goals_per_quest_of(course: StudioCourse) -> int:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("goals_per_quest") if isinstance(raw, dict) else None
    try:
        return _target_count(
            stored,
            DEFAULT_GOALS_PER_QUEST,
            "goals_per_quest",
            "Goals per quest must be a whole number from 1 to 200.",
        )
    except StudioError:
        return DEFAULT_GOALS_PER_QUEST


def normalize_close(value, field: str = "close") -> dict:
    if not isinstance(value, dict):
        raise StudioError(field, "must say how the quest closes")
    style = value.get("close_style")
    if style not in CLOSE_STYLES:
        raise StudioError("close_style", "must be one or several")
    answer = value.get("answer_style")
    if answer not in ANSWER_STYLES:
        raise StudioError("answer_style", "must be multiple_choice, essay, or mixed")
    mode = value.get("choice_mode")
    if mode == "":
        mode = None
    intent = value.get("intent")
    if intent is None:
        intent = ""
    if not isinstance(intent, str):
        raise StudioError("intent", "must be text")
    intent = intent.strip()
    if len(intent) > TEXT_LIMITS["intent"]:
        raise StudioError("intent", "is too long")
    items = _items(value.get("items"))
    questions = _questions(value.get("questions"))
    if answer == "essay":
        if mode is not None:
            raise StudioError("choice_mode", "is only for multiple choice")
        if items:
            raise StudioError("items", "are stored only for predefined choices")
        if intent:
            raise StudioError("intent", "is stored only for dynamic choices")
        return {
            "close_style": style,
            "answer_style": answer,
            "choice_mode": None,
            "items": [],
            "questions": questions,
            "intent": "",
            "selection": None,
        }
    if mode not in CHOICE_MODES:
        raise StudioError("choice_mode", "must be predefined or dynamic")
    if mode == "predefined":
        if len(items) < 2 or len(items) > 8:
            raise StudioError("items", "needs two to eight choices")
        if intent:
            raise StudioError("intent", "is stored only for dynamic choices")
        selection = value.get("selection")
        if selection not in ("single", "multi"):
            selection = "single"
        return {
            "close_style": style,
            "answer_style": answer,
            "choice_mode": "predefined",
            "items": items,
            "questions": questions,
            "intent": "",
            "selection": selection,
        }
    if items:
        raise StudioError("items", "dynamic choices store only the intent")
    # A blank close can name dynamic choices before anyone writes an intent.
    return {
        "close_style": style,
        "answer_style": answer,
        "choice_mode": "dynamic",
        "items": [],
        "questions": questions,
        "intent": intent,
        "selection": None,
    }


def close_default_of(course: StudioCourse) -> dict:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    stored = raw.get("close_default") if isinstance(raw, dict) else None
    if not isinstance(stored, dict):
        return default_close()
    try:
        return normalize_close(stored, "close_default")
    except StudioError:
        return default_close()


def _position(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 200:
        raise StudioError("position", "must be an integer from 1 to 200", plain=POSITION_REASON)
    return value


def _slot(existing: list, row, position: int) -> None:
    others = sorted(
        [item for item in existing if item.code != row.code],
        key=lambda item: (item.position, item.code),
    )
    if position < 1 or position > len(others) + 1:
        raise StudioError(
            "position",
            "is past the end of this list",
            plain="Position is past the end of this list.",
        )
    ordered = others[: position - 1] + [row] + others[position - 1 :]
    for index, item in enumerate(ordered, start=1):
        item.position = index


def _compact(rows: list) -> None:
    ordered = sorted(rows, key=lambda item: (item.position, item.code))
    for index, item in enumerate(ordered, start=1):
        item.position = index


def _operations(patch) -> list:
    if isinstance(patch, list):
        raw = patch
    elif isinstance(patch, dict) and isinstance(patch.get("operations"), list):
        raw = patch["operations"]
    else:
        raise StudioError(
            "patch",
            "must be add, update, or remove operations addressed by code",
        )
    if not raw:
        raise StudioError("patch", "needs at least one add, update, or remove")
    if len(raw) > 40:
        raise StudioError("patch", "is too large")
    return raw


_STRUCTURAL = ("op", "kind", "code")
_CLOSE_FIELDS = frozenset(
    {"close_style", "answer_style", "choice_mode", "items", "questions", "intent", "selection"}
)
# Parent is accepted on an add only. On an update it is redundant and dropped.
_TIER_FIELDS = {
    "course": frozenset(COURSE_FIELDS),
    "unit": frozenset(NODE_FIELDS),
    "quest": frozenset(NODE_FIELDS) | {"close", "goals"},
    "move": frozenset(NODE_FIELDS),
}


def _log_drop(field: str, kind, code) -> None:
    logger.info("studio patch dropped %s on %s %s", field, kind, code)


def _sanitize_close(value, kind, code):
    if not isinstance(value, dict):
        return value
    for key, item in value.items():
        if key not in _CLOSE_FIELDS and item is not None:
            _log_drop(f"close.{key}", kind, code)
    return {key: value[key] for key in _CLOSE_FIELDS if key in value}


def _keep_tier_fields(raw: dict, op_name: str) -> dict:
    """Keep the fields this tier accepts. Anything else is logged and dropped."""
    kind = raw.get("kind")
    code = raw.get("code")
    allowed = set(_TIER_FIELDS.get(kind, ()))
    if op_name == "add" and kind in ("unit", "quest", "move"):
        allowed.add("parent")
    cleaned = {key: raw[key] for key in _STRUCTURAL if key in raw}
    for key, value in raw.items():
        if key in _STRUCTURAL:
            continue
        if key == "parent" and op_name != "add":
            if value is not None:
                _log_drop("parent", kind, code)
            continue
        if key not in allowed:
            if value is not None:
                _log_drop(str(key), kind, code)
            continue
        if key in ("close", "close_default") and isinstance(value, dict):
            value = _sanitize_close(value, kind, code)
        cleaned[key] = value
    return cleaned


def _patch_view(course: StudioCourse) -> dict:
    """A tracked stage can patch any quest in that stage. Older courses still use the open wave."""
    if stored_stage(course):
        name = active_stage_name(course)
        return {
            "name": name,
            "label": _stage_label(name),
            "codes": _codes_in_phase(course, name),
        }
    return viewed_phase(course)


def _phase_only(course: StudioCourse, phase: str) -> str:
    listed = ", ".join(_patch_view(course)["codes"]) or "the open quests"
    if phase == "goals":
        return f"Goals only updates learning goals for {listed}."
    return f"Close only updates the close for {listed}."


def _outside_phase(course: StudioCourse, op_name: str, kind: str, code) -> str | None:
    """Goals and Close only touch quests in this course. A draft does not have to name every quest."""
    view = _patch_view(course)
    phase = view["name"]
    codes = {str(item).upper() for item in view["codes"]}
    code_text = str(code or "").strip().upper()
    if phase == "quests":
        if kind == "course":
            return "Quests only changes quests and moves."
        if kind == "unit":
            return "A unit is not part of this course."
        return None
    if phase == "goals":
        if kind == "quest" and code_text in codes and op_name in ("add", "update"):
            return None
        return _phase_only(course, "goals")
    if phase == "close":
        if kind == "quest" and code_text in codes and op_name in ("add", "update"):
            return None
        return _phase_only(course, "close")
    if op_name == "add" and code_text not in codes:
        return "This course is ready. New items are not added from a patch."
    return None


def _nodes_for(course: StudioCourse) -> dict[str, _Node]:
    nodes = {course.code: _Node("course", course.code, None, 0)}
    for quest in course.quests:
        nodes[quest.code] = _Node("quest", quest.code, course.code, quest.position)
        for move in quest.moves:
            nodes[move.code] = _Node("move", move.code, quest.code, move.position)
    return nodes


def _parent_from_code(course_code: str, kind: str, code: str) -> str | None:
    if kind != "move" or "-" not in code or not code.startswith(f"{course_code}-"):
        return None
    return code.rsplit("-", 1)[0]


def _with_inferred_parent(course_code: str, raw: dict) -> dict:
    """A move code supplies its quest when the patch left parent empty. Quests have no parent."""
    if raw.get("op") != "add" or raw.get("kind") != "move":
        return raw
    code = raw.get("code")
    if not isinstance(code, str) or not code.strip():
        return raw
    parent = raw.get("parent")
    if isinstance(parent, str) and parent.strip():
        candidate = parent.strip().upper()
        if NODE_CODE.fullmatch(candidate) and candidate.startswith(f"{course_code}-"):
            return raw
    inferred = _parent_from_code(course_code, "move", code.strip().upper())
    if not inferred:
        return raw
    copied = dict(raw)
    copied["parent"] = inferred
    return copied


def _write_rank(op) -> int:
    """Quests, then goals, then closes. Moves follow the quest they belong to."""
    if not isinstance(op, dict):
        return 9
    kind = op.get("kind")
    name = op.get("op")
    if name == "add" and kind == "quest":
        return 0
    if name == "add" and kind == "move":
        return 1
    has_goal = any(op.get(key) is not None for key in ("goals", "learning_goal", "success_criterion"))
    has_close = isinstance(op.get("close"), dict)
    if has_goal and not has_close:
        return 2
    if has_close:
        return 3
    if name == "remove":
        return 5
    return 4


def _order_writes(ops: list) -> list:
    """A confirm writes quests, then goals, then closes."""
    return sorted(list(ops), key=_write_rank)


def split_patch(course: StudioCourse, patch) -> tuple[list[dict], list[str], list[dict]]:
    """Plan each operation. A bad sibling is skipped. Nothing is written."""
    nodes = _nodes_for(course)
    state = {
        "title": course.title,
        "audience": course.audience,
        "focus": course.focus,
        "theme": course.theme,
        "depth": course.depth,
        "sources": course.sources,
        "close_default": close_default_of(course),
    }
    planned: list[dict] = []
    skipped: list[str] = []
    kept: list[dict] = []
    phase = _patch_view(course)["name"]
    for raw in _order_writes(_operations(patch)):
        try:
            if not isinstance(raw, dict):
                raise StudioError("patch", "each change must be an object")
            raw = _with_inferred_parent(course.code, raw)
            op_name = raw.get("op")
            kind = raw.get("kind")
            if op_name not in OPS:
                raise StudioError("op", "must be add, update, or remove")
            if kind == "unit":
                raise StudioError(
                    "kind",
                    "a unit is not part of this course",
                    plain="A unit is not part of this course.",
                )
            if kind not in KINDS:
                raise StudioError("kind", "must be course, quest, or move")
            blocked = _outside_phase(course, op_name, kind, raw.get("code"))
            if blocked:
                raise StudioError("phase", blocked, plain=blocked)
            cleaned = _keep_tier_fields(raw, op_name)
            if phase == "goals":
                cleaned.pop("close", None)
                cleaned.pop("title", None)
                cleaned.pop("position", None)
                if (
                    _field(cleaned, "learning_goal") is _MISSING
                    and _field(cleaned, "success_criterion") is _MISSING
                    and _field(cleaned, "goals") is _MISSING
                ):
                    raise StudioError("phase", "goals", plain=_phase_only(course, "goals"))
            elif phase == "close":
                cleaned.pop("learning_goal", None)
                cleaned.pop("success_criterion", None)
                cleaned.pop("goals", None)
                cleaned.pop("title", None)
                cleaned.pop("position", None)
                if _field(cleaned, "close") is _MISSING:
                    raise StudioError("phase", "close", plain=_phase_only(course, "close"))
            if op_name == "add":
                step = _plan_add(course.code, cleaned, nodes, state)
            elif op_name == "update":
                step = _plan_update(course.code, cleaned, nodes, state)
            else:
                step = _plan_remove(course.code, cleaned, nodes)
        except StudioError as exc:
            if exc.plain not in skipped:
                skipped.append(exc.plain)
            continue
        if step is not None:
            planned.append(step)
            kept.append(raw)
    return planned, skipped, kept


def plan_patch(course: StudioCourse, patch) -> list[dict]:
    """Check a patch against this course. Nothing is written."""
    planned, skipped, _kept = split_patch(course, patch)
    if not planned:
        plain = " ".join(skipped) if skipped else "That change had nothing to save."
        raise StudioError("patch", "needs at least one add, update, or remove", plain=plain)
    if skipped:
        raise StudioError("patch", "has a change that was skipped", plain=" ".join(skipped))
    return planned


def _siblings(nodes: dict[str, _Node], parent: str, kind: str) -> list[_Node]:
    return [node for node in nodes.values() if node.parent == parent and node.kind == kind]


def _plan_add(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict:
    kind = raw["kind"]
    if kind == "course":
        raise StudioError("op", "the course already exists")
    code = normalize_node_code(raw.get("code"), course_code)
    existing = nodes.get(code)
    if existing is not None:
        if existing.kind != kind:
            raise StudioError(
                "code",
                f"{code} is already a {existing.kind}",
                plain=f"{code} is already a {existing.kind}.",
            )
        return _plan_update(course_code, raw, nodes, state)
    if kind == "quest":
        parent_code = course_code
    else:
        parent_code = normalize_node_code(raw.get("parent"), course_code, "parent")
        parent = nodes.get(parent_code)
        if parent is None:
            raise StudioError(
                "parent",
                f"{parent_code} is not in this course yet",
                plain=f"The parent {parent_code} is not in this course yet.",
            )
        if parent.kind != PARENT_KIND[kind]:
            raise StudioError("parent", f"{code} must be added under a {PARENT_KIND[kind]}")
    title = _text("title", raw.get("title"), required=True)
    goal = ""
    criterion = ""
    goals = None
    if kind == "quest" and _field(raw, "goals") is not _MISSING:
        goals = normalize_goals(raw.get("goals"))
        if goals:
            goal = goals[0]["learning_goal"]
            criterion = goals[0]["success_criterion"]
    else:
        if _field(raw, "learning_goal") is not _MISSING:
            goal = _text("learning_goal", raw.get("learning_goal"))
        if _field(raw, "success_criterion") is not _MISSING:
            criterion = _text("success_criterion", raw.get("success_criterion"))
    close = None
    if kind == "quest" and _field(raw, "close") is not _MISSING:
        close = normalize_close(raw.get("close"))
    row = _Node(kind, code, parent_code, 0)
    group = _siblings(nodes, parent_code, kind)
    position = len(group) + 1 if _field(raw, "position") is _MISSING else _position(raw.get("position"))
    _slot(group, row, position)
    nodes[code] = row
    planned = {
        "op": "add",
        "kind": kind,
        "code": code,
        "parent": parent_code if kind != "quest" else None,
        "title": title,
        "learning_goal": goal,
        "success_criterion": criterion,
        "position": row.position,
    }
    if kind == "quest":
        planned["close"] = close
        if goals is not None:
            planned["goals"] = goals
    return planned


def _plan_update(course_code: str, raw: dict, nodes: dict[str, _Node], state: dict) -> dict | None:
    kind = raw["kind"]
    if kind == "course":
        code = normalize_course_code(raw.get("code"))
        if code != course_code:
            raise StudioError("code", "does not match this course")
        planned: dict = {"op": "update", "kind": "course", "code": code}
        if _field(raw, "title") is not _MISSING:
            planned["title"] = _text("title", raw.get("title"), required=True)
            state["title"] = planned["title"]
        if _field(raw, "audience") is not _MISSING:
            planned["audience"] = _text("audience", raw.get("audience"))
            state["audience"] = planned["audience"]
        if _field(raw, "focus") is not _MISSING:
            planned["focus"] = _text("focus", raw.get("focus"))
            state["focus"] = planned["focus"]
        if _field(raw, "theme") is not _MISSING:
            planned["theme"] = _text("theme", raw.get("theme"))
            state["theme"] = planned["theme"]
        if _field(raw, "depth") is not _MISSING:
            planned["depth"] = normalize_depth(raw.get("depth"))
            state["depth"] = planned["depth"]
        if _field(raw, "sources") is not _MISSING:
            planned["sources"] = normalize_sources(raw.get("sources"))
            state["sources"] = planned["sources"]
        if _field(raw, "close_default") is not _MISSING:
            planned["close_default"] = normalize_close(raw.get("close_default"), "close_default")
            state["close_default"] = planned["close_default"]
        if len(planned) == 3:
            return None
        return planned

    code = normalize_node_code(raw.get("code"), course_code)
    node = nodes.get(code)
    if node is None:
        raise StudioError("code", f"{code} is not in this course")
    if node.kind != kind:
        raise StudioError("kind", f"{code} is a {node.kind}")
    planned = {"op": "update", "kind": kind, "code": code}
    if _field(raw, "title") is not _MISSING:
        planned["title"] = _text("title", raw.get("title"), required=True)
    if _field(raw, "learning_goal") is not _MISSING:
        planned["learning_goal"] = _text("learning_goal", raw.get("learning_goal"))
    if _field(raw, "success_criterion") is not _MISSING:
        planned["success_criterion"] = _text("success_criterion", raw.get("success_criterion"))
    if _field(raw, "position") is not _MISSING:
        position = _position(raw.get("position"))
        _slot(_siblings(nodes, node.parent or "", kind), node, position)
        planned["position"] = node.position
    if kind == "quest" and _field(raw, "goals") is not _MISSING:
        goals = normalize_goals(raw.get("goals"))
        planned["goals"] = goals
        if goals:
            planned["learning_goal"] = goals[0]["learning_goal"]
            planned["success_criterion"] = goals[0]["success_criterion"]
        else:
            planned["learning_goal"] = ""
            planned["success_criterion"] = ""
    if kind == "quest" and _field(raw, "close") is not _MISSING:
        planned["close"] = normalize_close(raw.get("close"))
    if len(planned) == 3:
        return None
    return planned


def _plan_remove(course_code: str, raw: dict, nodes: dict[str, _Node]) -> dict:
    kind = raw["kind"]
    if kind == "course":
        raise StudioError("op", "the course is not removed from a patch")
    code = normalize_node_code(raw.get("code"), course_code)
    node = nodes.get(code)
    if node is None:
        raise StudioError("code", f"{code} is not in this course")
    if node.kind != kind:
        raise StudioError("kind", f"{code} is a {node.kind}")
    parent = node.parent
    _drop(nodes, code)
    _compact(_siblings(nodes, parent or "", kind))
    return {"op": "remove", "kind": kind, "code": code}


def _drop(nodes: dict[str, _Node], code: str) -> None:
    children = [node.code for node in nodes.values() if node.parent == code]
    for child in children:
        _drop(nodes, child)
    del nodes[code]


def _pack_items(items: list, questions: list, selection: str | None = None):
    """Keep a choice list as a list. Questions and the single/multi flag share that JSON column."""
    if questions or selection in ("single", "multi"):
        packed: dict = {"choices": list(items), "questions": list(questions)}
        if selection in ("single", "multi"):
            packed["selection"] = selection
        return packed
    return list(items)


def _unpack_close(stored) -> tuple[list, list, str | None]:
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        selection = stored.get("selection") if stored.get("selection") in ("single", "multi") else None
        return choices, questions, selection
    if isinstance(stored, list):
        return list(stored), [], None
    return [], [], None


def _unpack_items(stored) -> tuple[list, list]:
    choices, questions, _selection = _unpack_close(stored)
    return choices, questions


def goal_rows(quest: StudioQuest) -> list[dict]:
    """Goal 1 is the quest columns. Later rows are studio_quest_goals."""
    extras = sorted(quest.goals, key=lambda row: row.position)
    has_first = bool(str(quest.learning_goal or "").strip() or str(quest.success_criterion or "").strip())
    if not has_first and not extras:
        return []
    rows = [
        {
            "position": 1,
            "learning_goal": quest.learning_goal or "",
            "success_criterion": quest.success_criterion or "",
        }
    ]
    for extra in extras:
        rows.append(
            {
                "position": extra.position,
                "learning_goal": extra.learning_goal or "",
                "success_criterion": extra.success_criterion or "",
            }
        )
    return rows


def _goals_incomplete(quest: StudioQuest) -> bool:
    rows = goal_rows(quest)
    if not rows:
        return True
    return any(
        not str(row["learning_goal"] or "").strip() or not str(row["success_criterion"] or "").strip()
        for row in rows
    )


def _replace_goals(quest: StudioQuest, goals: list[dict]) -> None:
    """Write the goal list. Flush removed extras before the new rows, so positions do not collide."""
    session = object_session(quest)
    if not goals:
        quest.learning_goal = ""
        quest.success_criterion = ""
    else:
        quest.learning_goal = goals[0]["learning_goal"]
        quest.success_criterion = goals[0]["success_criterion"]
    for extra in list(quest.goals):
        if session is not None:
            session.delete(extra)
    quest.goals.clear()
    if session is not None:
        session.flush()
    for row in goals[1:]:
        quest.goals.append(
            StudioQuestGoal(
                position=row["position"],
                learning_goal=row["learning_goal"],
                success_criterion=row["success_criterion"],
            )
        )


def _fill_close(quest: StudioQuest, close: dict) -> None:
    row = quest.close
    if row is None:
        row = StudioQuestClose()
        quest.close = row
        session = object_session(quest)
        if session is not None:
            session.add(row)
    items = close.get("items") or []
    questions = list(close.get("questions") or [])
    if isinstance(items, dict):
        unpacked, unpacked_questions = _unpack_items(items)
        items = unpacked
        if not questions:
            questions = unpacked_questions
    row.close_style = close["close_style"]
    row.answer_style = close["answer_style"]
    row.choice_mode = close.get("choice_mode")
    row.items = _pack_items(list(items), questions, close.get("selection"))
    row.intent = close.get("intent") or ""


def _apply(course: StudioCourse, planned: list[dict]) -> None:
    for step in planned:
        if step["op"] == "add":
            _apply_add(course, step)
        elif step["op"] == "update":
            _apply_update(course, step)
        else:
            _apply_remove(course, step)


def _apply_add(course: StudioCourse, step: dict) -> None:
    kind = step["kind"]
    if kind == "quest":
        row = StudioQuest(
            course_id=course.id,
            code=step["code"],
            position=step["position"],
            title=step["title"],
            learning_goal=step["learning_goal"],
            success_criterion=step["success_criterion"],
        )
        course.quests.append(row)
        _slot(list(course.quests), row, step["position"])
        if step.get("goals") is not None:
            _replace_goals(row, step["goals"])
        if step.get("close") is not None:
            _fill_close(row, step["close"])
        return
    quest = _quest(course, step["parent"])
    row = StudioMove(
        course_id=course.id,
        code=step["code"],
        position=step["position"],
        title=step["title"],
        learning_goal=step["learning_goal"],
        success_criterion=step["success_criterion"],
    )
    quest.moves.append(row)
    _slot(list(quest.moves), row, step["position"])


def _apply_update(course: StudioCourse, step: dict) -> None:
    if step["kind"] == "course":
        for key in ("title", "audience", "focus", "theme", "depth", "sources"):
            if key in step:
                setattr(course, key, step[key])
        if "close_default" in step:
            prefs = dict(course.preferences or {})
            prefs["close_default"] = step["close_default"]
            course.preferences = prefs
        return
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        _assign_node(row, step)
        if "position" in step:
            _slot(list(course.quests), row, step["position"])
        if "goals" in step:
            _replace_goals(row, step["goals"])
        if "close" in step:
            _fill_close(row, step["close"])
        return
    row = _move(course, step["code"])
    _assign_node(row, step)
    if "position" in step:
        _slot(list(row.quest.moves), row, step["position"])


def _assign_node(row, step: dict) -> None:
    for key in ("title", "learning_goal", "success_criterion"):
        if key in step:
            setattr(row, key, step[key])


def _apply_remove(course: StudioCourse, step: dict) -> None:
    if step["kind"] == "quest":
        row = _quest(course, step["code"])
        course.quests.remove(row)
        _compact(list(course.quests))
        return
    row = _move(course, step["code"])
    quest = row.quest
    quest.moves.remove(row)
    _compact(list(quest.moves))


def _quest(course: StudioCourse, code: str) -> StudioQuest:
    for quest in course.quests:
        if quest.code == code:
            return quest
    raise StudioError("code", f"{code} is not in this course")


def _move(course: StudioCourse, code: str) -> StudioMove:
    for quest in course.quests:
        for move in quest.moves:
            if move.code == code:
                return move
    raise StudioError("code", f"{code} is not in this course")


def apply_patch(db: Session, course: StudioCourse, patch) -> None:
    planned = plan_patch(course, patch)
    _apply(course, planned)
    course.updated_at = _now()
    db.flush()


def create_course(db: Session, *, code: str, title: str) -> StudioCourse:
    normalized = normalize_course_code(code)
    label = _text("title", title, required=True)
    taken = db.scalar(select(StudioCourse.id).where(StudioCourse.code == normalized))
    if taken is not None:
        raise StudioError("code", "is already used", status=409)
    course = StudioCourse(
        code=normalized,
        title=label,
        audience="",
        focus="",
        theme="",
        depth="standard",
        quiz_minutes=5,
        sources="",
        preferences=default_preferences(),
        schema_version=SCHEMA_VERSION,
        ready=False,
    )
    db.add(course)
    db.flush()
    return course


def delete_studio_course(db: Session, course: StudioCourse, password: str) -> None:
    """Delete one studio course after the password. Tutor courses and kid chats stay."""
    if not isinstance(password, str) or not hmac.compare_digest(password, DELETE_PASSWORD):
        raise StudioError("password", "is wrong", plain="The password is wrong.")
    db.delete(course)
    db.flush()


def _node_codes(course: StudioCourse) -> list[str]:
    codes: list[str] = []
    for quest in course.quests:
        codes.append(quest.code)
        for move in quest.moves:
            codes.append(move.code)
    return codes


def _retarget_code(code: str, old: str, new: str) -> str:
    prefix = f"{old}-"
    if code.startswith(prefix):
        return f"{new}-{code[len(prefix):]}"
    return code


def fresh_course_code(db: Session, source: StudioCourse) -> str:
    taken = set(db.scalars(select(StudioCourse.code)).all())
    nodes = _node_codes(source)
    for number in range(2, 1000):
        suffix = str(number)
        room = 16 - len(suffix)
        if room < 1:
            break
        candidate = f"{source.code[:room]}{suffix}"
        if candidate in taken or candidate == source.code or not COURSE_CODE.fullmatch(candidate):
            continue
        rewritten = [_retarget_code(code, source.code, candidate) for code in nodes]
        if any(len(code) > 40 or not NODE_CODE.fullmatch(code) for code in rewritten):
            continue
        return candidate
    raise StudioError("code", "a new code is not available", plain="Could not choose a new code.")


def _copy_close(quest: StudioQuest, source: StudioQuestClose) -> None:
    row = StudioQuestClose(
        close_style=source.close_style,
        answer_style=source.answer_style,
        choice_mode=source.choice_mode,
        items=copy.deepcopy(source.items or []),
        intent=source.intent or "",
    )
    quest.close = row
    session = object_session(quest)
    if session is not None:
        session.add(row)


def copy_studio_course(db: Session, source: StudioCourse, title: str) -> StudioCourse:
    """Copy the course under a new code and name. The creation chat is not copied."""
    label = _text("title", title, required=True)
    code = fresh_course_code(db, source)
    course = StudioCourse(
        code=code,
        title=label,
        audience=source.audience,
        focus=source.focus,
        theme=source.theme,
        depth=source.depth,
        quiz_minutes=source.quiz_minutes,
        sources=source.sources,
        preferences=_preferences_without_undo(source),
        schema_version=source.schema_version,
        ready=source.ready,
    )
    db.add(course)
    db.flush()
    for quest in sorted(source.quests, key=lambda row: (row.position, row.code)):
        new_quest = StudioQuest(
            course_id=course.id,
            code=_retarget_code(quest.code, source.code, code),
            position=quest.position,
            title=quest.title,
            learning_goal=quest.learning_goal,
            success_criterion=quest.success_criterion,
        )
        course.quests.append(new_quest)
        db.flush()
        for extra in sorted(quest.goals, key=lambda row: row.position):
            new_quest.goals.append(
                StudioQuestGoal(
                    position=extra.position,
                    learning_goal=extra.learning_goal,
                    success_criterion=extra.success_criterion,
                )
            )
        if quest.close is not None:
            _copy_close(new_quest, quest.close)
        for move in sorted(quest.moves, key=lambda row: (row.position, row.code)):
            new_quest.moves.append(
                StudioMove(
                    course_id=course.id,
                    code=_retarget_code(move.code, source.code, code),
                    position=move.position,
                    title=move.title,
                    learning_goal=move.learning_goal,
                    success_criterion=move.success_criterion,
                )
            )
    db.flush()
    return course


def update_preferences(course: StudioCourse, body: dict) -> None:
    course.title = _text("title", body.get("title"), required=True)
    course.audience = normalize_audience(body.get("audience", ""))
    course.focus = _text("focus", body.get("focus", ""))
    theme_value = body.get("theme", None)
    if not isinstance(theme_value, str) or not theme_value.strip():
        described = body.get("description", "")
        if isinstance(described, str) and described.strip():
            theme_value = described
    theme = _text("theme", theme_value or "")
    if theme.lower() in {"none", "no theme"}:
        theme = ""
    course.theme = theme
    course.depth = normalize_depth(body.get("depth"))
    course.quiz_minutes = normalize_quiz_minutes(body.get("quiz_minutes", course.quiz_minutes))
    course.sources = normalize_sources(body.get("sources", ""))
    close = normalize_close(body.get("close_default"), "close_default")
    quest_count = _target_count(
        body.get("quest_count", DEFAULT_QUEST_COUNT),
        DEFAULT_QUEST_COUNT,
        "quest_count",
        "Number of quests must be a whole number from 1 to 200.",
    )
    goals_per_quest = _target_count(
        body.get("goals_per_quest", DEFAULT_GOALS_PER_QUEST),
        DEFAULT_GOALS_PER_QUEST,
        "goals_per_quest",
        "Goals per quest must be a whole number from 1 to 200.",
    )
    prefs = dict(course.preferences or {})
    prefs["close_default"] = close
    prefs["depth"] = course.depth
    prefs["quiz_minutes"] = course.quiz_minutes
    prefs["audience"] = course.audience
    prefs["theme"] = course.theme
    prefs["sources"] = course.sources
    prefs["quest_count"] = quest_count
    prefs["goals_per_quest"] = goals_per_quest
    course.preferences = prefs
    course.schema_version = SCHEMA_VERSION
    course.updated_at = _now()


def load_course(db: Session, course_id) -> StudioCourse | None:
    return db.scalar(
        select(StudioCourse)
        .where(StudioCourse.id == course_id)
        .options(
            selectinload(StudioCourse.quests).selectinload(StudioQuest.moves),
            selectinload(StudioCourse.quests).selectinload(StudioQuest.close),
            selectinload(StudioCourse.quests).selectinload(StudioQuest.goals),
        )
    )


def list_courses(db: Session) -> list[StudioCourse]:
    return list(
        db.scalars(select(StudioCourse).order_by(StudioCourse.updated_at.desc(), StudioCourse.title)).all()
    )


def list_messages(db: Session, course: StudioCourse) -> list[StudioMessage]:
    return list(
        db.scalars(
            select(StudioMessage).where(StudioMessage.course_id == course.id).order_by(StudioMessage.seq)
        ).all()
    )


_GOAL_LINE = re.compile(r"(?:learning\s+)?goal\s*:\s*(.+)", re.IGNORECASE)
_CRITERION_LINE = re.compile(r"(?:success\s+)?criterion\s*:\s*(.+)", re.IGNORECASE)


def _clean_goal_line(raw_line: str) -> str:
    line = re.sub(r"[*_#`]", "", raw_line).strip().lstrip("-•").strip()
    line = re.sub(r"^\d+[.)]\s*", "", line).strip()
    return re.sub(r"^quest\s+", "", line, flags=re.IGNORECASE).strip()


def _header_code(line: str, codes: set[str]) -> tuple[str, str] | None:
    """A block starts with the quest code. The rest of the line may hold the goal."""
    if _GOAL_LINE.match(line) or _CRITERION_LINE.match(line):
        return None
    for code in sorted(codes, key=len, reverse=True):
        match = re.match(rf"{re.escape(code)}\b\s*[:\-–—]?\s*(.*)$", line, flags=re.IGNORECASE)
        if match:
            return code, match.group(1).strip()
    return None


def _remember_goal(found: dict[str, list[dict]], code: str, goal: str, criterion: str) -> None:
    goal = goal.strip()
    criterion = criterion.strip()
    if not goal or not criterion:
        return
    found.setdefault(code, []).append(
        {
            "position": len(found.get(code, [])) + 1,
            "learning_goal": goal,
            "success_criterion": criterion,
        }
    )


def _parse_goal_blocks(text: str, codes: set[str]) -> dict[str, list[dict]]:
    """Goal blocks in a reply, keyed by quest code. A block starts with the code."""
    found: dict[str, list[dict]] = {}
    current: str | None = None
    pending: str | None = None
    for raw_line in (text or "").splitlines():
        line = _clean_goal_line(raw_line)
        if not line:
            continue
        header = _header_code(line, codes)
        if header:
            current, remainder = header
            found.setdefault(current, [])
            pending = None
            criterion = _CRITERION_LINE.search(remainder)
            if criterion:
                before = remainder[: criterion.start()].strip(" .:-")
                goal_match = _GOAL_LINE.match(before)
                goal = goal_match.group(1).strip() if goal_match else before
                _remember_goal(found, current, goal, criterion.group(1))
                continue
            goal_match = _GOAL_LINE.match(remainder)
            if goal_match:
                pending = goal_match.group(1).strip()
            continue
        if current is None:
            continue
        goal_line = _GOAL_LINE.match(line)
        criterion_line = _CRITERION_LINE.match(line)
        if goal_line:
            pending = goal_line.group(1).strip()
            continue
        if criterion_line and pending:
            _remember_goal(found, current, pending, criterion_line.group(1))
            pending = None
    return {code: rows for code, rows in found.items() if rows}


def _operation_goal_rows(op: dict) -> list[dict] | None:
    goals = op.get("goals")
    if isinstance(goals, list) and goals:
        return [item for item in goals if isinstance(item, dict)]
    goal = op.get("learning_goal")
    criterion = op.get("success_criterion")
    if isinstance(goal, str) and goal.strip() or isinstance(criterion, str) and criterion.strip():
        return [
            {
                "position": 1,
                "learning_goal": goal if isinstance(goal, str) else "",
                "success_criterion": criterion if isinstance(criterion, str) else "",
            }
        ]
    return None


def _split_goals_by_quest_code(operations: list, codes: set[str]) -> list:
    """A goals array that names later quests is one update per quest, not extra goals on the first."""
    expanded: list = []
    for op in operations:
        if not isinstance(op, dict):
            expanded.append(op)
            continue
        goals = op.get("goals")
        if not isinstance(goals, list):
            expanded.append(op)
            continue
        buckets: dict[str, list] = {}
        plain: list = []
        for item in goals:
            if not isinstance(item, dict):
                plain.append(item)
                continue
            named = str(item.get("code") or "").strip().upper()
            if named in codes:
                buckets.setdefault(named, []).append(item)
            else:
                plain.append(item)
        if not buckets:
            expanded.append(op)
            continue
        own = str(op.get("code") or "").strip().upper()
        if plain:
            copied = dict(op)
            copied["goals"] = plain
            expanded.append(copied)
        elif own and own not in buckets:
            copied = dict(op)
            copied.pop("goals", None)
            expanded.append(copied)
        for code, rows in buckets.items():
            expanded.append(
                {
                    "op": "update",
                    "kind": "quest",
                    "code": code,
                    "parent": None,
                    "goals": [
                        {
                            "position": index,
                            "learning_goal": row.get("learning_goal") or "",
                            "success_criterion": row.get("success_criterion") or "",
                        }
                        for index, row in enumerate(rows, start=1)
                        if isinstance(row, dict)
                    ],
                }
            )
    return expanded


def _expand_goals_operations(course: StudioCourse, operations: list, text: str) -> list:
    """Keep every quest the reply or the patch names. Do not stop after the first quest."""
    codes = {quest.code for quest in course.quests}
    operations = _split_goals_by_quest_code(list(operations), codes)
    covered: set[str] = set()
    for op in operations:
        if not isinstance(op, dict):
            continue
        code = str(op.get("code") or "").strip().upper()
        if code in codes and _operation_goal_rows(op):
            covered.add(code)
    parsed = _parse_goal_blocks(text, codes)
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        rows = parsed.get(quest.code)
        if not rows or quest.code in covered:
            continue
        operations.append(
            {
                "op": "update",
                "kind": "quest",
                "code": quest.code,
                "parent": None,
                "goals": rows,
            }
        )
        covered.add(quest.code)
    return operations


def _skipped_goals_sentence(codes: list[str]) -> str:
    if len(codes) == 1:
        return f"Skipped {codes[0]}, which still needs a goal and a success criterion."
    listed = ", ".join(codes[:-1]) + " and " + codes[-1]
    return f"Skipped {listed}, which still need a goal and a success criterion."


def _note_skipped_goals(db: Session, course: StudioCourse, codes: list[str]) -> None:
    """One sentence naming the quests this goals push left without a goal."""
    sentence = _skipped_goals_sentence(codes)
    messages = list_messages(db, course)
    if messages and messages[-1].content.strip() == sentence:
        return
    add_message(db, course, role="assistant", content=sentence, proposal=None)


def add_message(
    db: Session,
    course: StudioCourse,
    *,
    role: str,
    content: str,
    proposal: dict | None,
) -> StudioMessage:
    text = content.strip()
    if not text:
        raise StudioError("content", "is required")
    if len(text) > 20000:
        raise StudioError("content", "is too long")
    if role == "user" and proposal is not None:
        raise StudioError("proposal", "a creator message cannot carry a patch")
    stored = None
    if proposal is not None:
        if isinstance(proposal, dict):
            phase_hint = _phase_name(proposal.get("phase")) or (
                active_stage_name(course) if stored_stage(course) else viewed_phase(course)["name"]
            )
            ops = proposal.get("operations")
            if phase_hint == "goals" and isinstance(ops, list):
                proposal = dict(proposal)
                proposal["operations"] = _expand_goals_operations(course, ops, text)
        _planned, skipped, kept = split_patch(course, proposal)
        if not kept:
            plain = " ".join(skipped) if skipped else "That change had nothing to save."
            raise StudioError("patch", "needs at least one add, update, or remove", plain=plain)
        phase = _phase_name(proposal.get("phase")) if isinstance(proposal, dict) else None
        if phase is None:
            phase = _patch_view(course)["name"]
        stored = {"operations": copy.deepcopy(kept), "phase": phase}
        if skipped:
            text = text.rstrip() + "\n" + "\n".join(skipped)
    seq = db.scalar(select(func.max(StudioMessage.seq)).where(StudioMessage.course_id == course.id))
    message = StudioMessage(
        course_id=course.id,
        role=role,
        content=text,
        seq=(seq or 0) + 1,
        proposal=stored,
        applied=False,
    )
    db.add(message)
    course.updated_at = _now()
    db.flush()
    return message


_CONFIRM_EXACT = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "ok",
        "okay",
        "sure",
        "confirm",
        "do it",
        "go ahead",
        "write it",
        "write that",
        "save that",
        "add them",
        "add those",
        "add it",
        "add that",
    }
)
_CONFIRM_BLOCK = re.compile(r"\b(?:but|except|change|instead|don't|do not|wait|not yet)\b", re.IGNORECASE)
_THIN_DESCRIPTION = frozenset({"", "none", "no theme", "no description"})


def _confirm_text(text: str) -> str | None:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed or "?" in collapsed or _CONFIRM_BLOCK.search(collapsed):
        return None
    return collapsed.rstrip(".!").strip().lower()


_STAGE_KEY = "stage"
_STAGE_VIEW = "stage_view"
_STAGE_MOVE = re.compile(
    r"\b(?:next stage|next phase|move on|mark complete|final submit|go to (?:the )?(?:next|goals|close|ready))\b",
    re.IGNORECASE,
)
_NEXT_STAGE = {"quests": "goals", "goals": "close", "close": "ready"}


def _prefs_dict(course: StudioCourse) -> dict:
    raw = course.preferences
    return dict(raw) if isinstance(raw, dict) else {}


def stored_stage(course: StudioCourse) -> str | None:
    value = _prefs_dict(course).get(_STAGE_KEY)
    if value == "structure":
        value = "quests"
    if value in ("quests", "goals", "close", "ready"):
        return str(value)
    return None


def tracked_stage_name(course: StudioCourse) -> str:
    """The stage Mark Complete has reached. Chat never moves this."""
    stored = stored_stage(course)
    if stored:
        return stored
    if course.ready:
        return "ready"
    return "quests"


def active_stage_name(course: StudioCourse) -> str:
    """The tab on screen. An earlier completed tab can be opened again."""
    view = _prefs_dict(course).get(_STAGE_VIEW)
    if view == "structure":
        view = "quests"
    stage = tracked_stage_name(course)
    order = {"quests": 0, "goals": 1, "close": 2, "ready": 3}
    if view in order and order[view] <= order[stage]:
        return str(view)
    return stage


def _write_pref(course: StudioCourse, key: str, value) -> None:
    prefs = _prefs_dict(course)
    if value is None:
        prefs.pop(key, None)
    else:
        prefs[key] = value
    course.preferences = prefs


def wants_stage_change(text: str) -> bool:
    return _STAGE_MOVE.search(text or "") is not None


def stage_gaps_for(course: StudioCourse, stage: str) -> list[str]:
    """What still blocks Mark Complete for this stage."""
    quests = sorted(course.quests, key=lambda row: (row.position, row.code))
    if stage == "ready":
        return []
    if not quests:
        return ["No quests yet."]
    if stage == "quests":
        return []
    gaps: list[str] = []
    if stage == "goals":
        for quest in quests:
            rows = goal_rows(quest)
            if not rows:
                gaps.append(f"{quest.code}: no learning goal")
                continue
            for row in rows:
                if not str(row["learning_goal"] or "").strip():
                    gaps.append(f"{quest.code}: goal {row['position']} has no learning goal")
                elif not str(row["success_criterion"] or "").strip():
                    gaps.append(f"{quest.code}: goal {row['position']} has no success criterion")
        return gaps
    for quest in quests:
        if quest.close is None:
            gaps.append(f"{quest.code}: no close")
            continue
        if quest.close.answer_style == "multiple_choice":
            items, _questions = _unpack_items(quest.close.items)
            if len(items) < 2:
                gaps.append(f"{quest.code}: a choice question needs at least 2 options")
    return gaps


_STAGE_ORDER = {"quests": 0, "goals": 1, "close": 2, "ready": 3}


def can_advance_stage(course: StudioCourse) -> bool:
    """Mark Complete is on when the stage on screen has no gaps, including after stepping back."""
    stage = active_stage_name(course)
    if stage == "ready":
        return tracked_stage_name(course) == "ready" and not bool(course.ready)
    return not stage_gaps_for(course, stage)


def description_is_specific(theme: str) -> bool:
    text = (theme or "").strip()
    if text.lower() in _THIN_DESCRIPTION:
        return False
    return len(re.findall(r"[A-Za-z0-9']+", text)) >= 8


_QUEST_SECTIONS = (
    "Introducing {subject}",
    "Where {subject} comes from",
    "The main ideas in {subject}",
    "How {subject} works",
    "A careful look at {subject}",
    "Trying {subject} yourself",
    "Common questions about {subject}",
    "Checking what you know about {subject}",
    "Pulling {subject} together",
    "What to remember about {subject}",
)


def _course_subject(theme: str) -> str:
    """The subject the quests are about. One phrase, not a slice of the sentence."""
    text = re.sub(r"\s+", " ", (theme or "").strip())
    text = re.sub(
        r"^(?:please\s+)?(?:create|make|build|design)\s+(?:me\s+)?(?:a|an)\s+course\s+(?:about|on|for)\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^(?:a|an)\s+(?:short\s+|brief\s+)?course\s+(?:about|on|for)\s+",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    subject = re.split(r"[.!?]\s+|\s+\b(?:include|including|incl)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    subject = subject.strip(" .,:;\"'")
    if not subject:
        subject = "this subject"
    room = TEXT_LIMITS["title"] - len("Checking what you know about ")
    if len(subject) > room:
        trimmed = subject[:room].rsplit(" ", 1)[0].strip()
        subject = trimmed or subject[:room]
    return subject


def _draft_quest_titles(theme: str, count: int) -> list[str]:
    """Real section titles about the subject. Never copies or slices the description."""
    count = max(1, min(count, 40))
    subject = _course_subject(theme)
    titles = [pattern.format(subject=subject) for pattern in _QUEST_SECTIONS]
    while len(titles) < count:
        part = len(titles) - len(_QUEST_SECTIONS) + 1
        titles.append(f"Going further with {subject}, part {part}")
    return [title[: TEXT_LIMITS["title"]] for title in titles[:count]]


def _titles_from_reply(reply: str) -> list[str]:
    """Numbered titles the assistant already listed. Not slices of the description."""
    titles: list[str] = []
    for line in (reply or "").splitlines():
        match = re.match(r"\s*(?:\d{1,2}[.)]\s+|[-*]\s+)(.+)", line)
        if not match:
            continue
        title = match.group(1).strip().strip(" .")
        if len(title) < 3 or len(title) > TEXT_LIMITS["title"]:
            continue
        lowered = title.lower()
        if lowered.startswith("i've added") or lowered.startswith("i have added") or lowered.startswith("i added"):
            continue
        titles.append(title)
    return titles


def _normalize_quest_adds(course: StudioCourse, operations: list | None) -> list[dict]:
    adds: list[dict] = []
    for raw in operations or []:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("op") or "add") != "add":
            continue
        if str(raw.get("kind") or "quest") != "quest":
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        adds.append(raw)
    normalized: list[dict] = []
    for index, raw in enumerate(adds, start=1):
        code = str(raw.get("code") or f"{course.code}-Q{index}").strip().upper()
        normalized.append(
            {
                "op": "add",
                "kind": "quest",
                "code": code,
                "parent": None,
                "title": str(raw["title"]).strip()[: TEXT_LIMITS["title"]],
                "position": index,
            }
        )
    return normalized


_FALSE_CLAIM = re.compile(
    r"\b(i've added|i have added|i added|added the quests|now in the course)\b",
    re.IGNORECASE,
)


def reply_without_false_claim(reply: str) -> str:
    """A chat line may list titles. It may not say they were written until the write succeeds."""
    text = (reply or "").strip()
    if not text or _FALSE_CLAIM.search(text):
        return "Those quests are not in the course yet."
    return text


def _checker_view(course: StudioCourse, name: str):
    """Point the patch checker at a stage, then put the previous view back."""
    prefs = _prefs_dict(course)
    previous = prefs.get("phase_view")
    prefs["phase_view"] = name
    course.preferences = prefs
    return previous


def _restore_checker_view(course: StudioCourse, previous) -> None:
    prefs = _prefs_dict(course)
    if previous is None:
        prefs.pop("phase_view", None)
    else:
        prefs["phase_view"] = previous
    course.preferences = prefs


def _quests_opening(course: StudioCourse) -> str:
    count = quest_count_of(course)
    return (
        "A quest is one section of the course the learner works through. "
        f"Should I draft {count} quests from the course description? "
        "Nothing is written until you click Push draft to Tree."
    )


def _goals_opening(course: StudioCourse) -> str:
    per_quest = goals_per_quest_of(course)
    return (
        "A goal is what the learner should come away able to do, and each goal has an observable success criterion. "
        f"I can draft {per_quest} goals for every quest, all in one go or one quest at a time. "
        "Nothing is written until you click Push draft to Tree."
    )


def _close_opening(_course: StudioCourse) -> str:
    return (
        "A close is how a quest ends. It can be an essay, a single choice, a multi-choice, or no questions. "
        "I can suggest a close for every quest, all in one go or one quest at a time. "
        "Nothing is written until you click Push draft to Tree."
    )


def opening_for(course: StudioCourse) -> tuple[str, dict | None]:
    """The stage on screen. Titles and closes stay in the draft until Push draft to Tree."""
    stage = active_stage_name(course) if stored_stage(course) else "quests"
    if stage == "goals":
        return _goals_opening(course), None
    if stage == "close":
        return _close_opening(course), None
    if stage == "ready":
        return (
            "The quests, goals, and closes are in place. "
            "Click Final Submit above the tree when you want to mark the course ready."
        ), None
    return _quests_opening(course), None


def seed_opening(db: Session, course: StudioCourse) -> list[StudioMessage]:
    existing = list_messages(db, course)
    if existing:
        return existing
    if stored_stage(course) is None:
        _write_pref(course, _STAGE_KEY, "quests")
    content, proposal = opening_for(course)
    add_message(db, course, role="assistant", content=content, proposal=proposal)
    return list_messages(db, course)


def _stage_label(name: str) -> str:
    return {
        "quests": "Quests",
        "goals": "Goals/Success Criteria",
        "close": "Close",
        "ready": "Ready",
    }.get(name, "Quests")


def _fallback_operations(course: StudioCourse, stage: str) -> list[dict]:
    if stage == "quests":
        count = min(quest_count_of(course), 40)
        existing = sorted(course.quests, key=lambda row: (row.position, row.code))
        if existing:
            return [
                {
                    "op": "update",
                    "kind": "quest",
                    "code": quest.code,
                    "parent": None,
                    "title": quest.title,
                    "position": quest.position,
                }
                for quest in existing
            ]
        return [
            {
                "op": "add",
                "kind": "quest",
                "code": f"{course.code}-Q{index}",
                "parent": None,
                "title": title,
                "position": index,
            }
            for index, title in enumerate(_draft_quest_titles(course.theme or "", count), start=1)
        ]
    if stage == "goals":
        per_quest = min(goals_per_quest_of(course), 40)
        operations = []
        for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
            goals = [
                {
                    "position": index,
                    "learning_goal": f"Work through {quest.title}, part {index}.",
                    "success_criterion": f"States one fact from {quest.title}, part {index}.",
                }
                for index in range(1, per_quest + 1)
            ]
            operations.append(
                {
                    "op": "update",
                    "kind": "quest",
                    "code": quest.code,
                    "parent": None,
                    "goals": goals,
                }
            )
        return operations
    if stage == "close":
        operations = []
        for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
            operations.append(
                {
                    "op": "update",
                    "kind": "quest",
                    "code": quest.code,
                    "parent": None,
                    "close": {
                        "close_style": "one",
                        "answer_style": "essay",
                        "choice_mode": None,
                        "items": [],
                        "questions": [{"text": f"What should you remember from {quest.title}?"}],
                        "intent": "",
                    },
                }
            )
        return operations
    return []


def _fallback_reply(course: StudioCourse, stage: str, operations: list[dict]) -> str:
    if stage == "quests":
        count = len(operations) or quest_count_of(course)
        titles = [str(op.get("title") or "") for op in operations if op.get("title")]
        listed = "\n".join(f"{index}. {title}" for index, title in enumerate(titles, start=1))
        lead = (
            f"Here is a draft of {count} quests from the course description. "
            "Click Push draft to Tree to add them. Nothing is in the tree until then."
        )
        return f"{lead}\n{listed}".strip()
    if stage == "goals":
        per_quest = goals_per_quest_of(course)
        return (
            f"Here is a draft of {per_quest} goals for each quest, each with a success criterion. "
            "I can do them all in one go, or we can take one quest at a time. "
            "Click Push draft to Tree when you want them in the tree."
        )
    if stage == "close":
        return (
            "Here is an essay close for each quest. "
            "I can do them all in one go, or we can take one quest at a time. "
            "Click Push draft to Tree when you want them in the tree."
        )
    return "This course is ready. Click Final Submit above the tree."


def _save_unapplied(db: Session, course: StudioCourse, content: str, proposal: dict | None) -> StudioMessage:
    stage = active_stage_name(course)
    previous = _checker_view(course, stage)
    try:
        message = add_message(db, course, role="assistant", content=content, proposal=proposal)
    finally:
        _restore_checker_view(course, previous)
    message.applied = False
    return message


def chat_turn(db: Session, course: StudioCourse, content: str) -> dict:
    """Save a chat line. Never writes the tree and never advances the stage."""
    text = content.strip()
    if not text:
        raise StudioError("content", "is required")
    if len(text) > 20000:
        raise StudioError("content", "is too long")
    user = add_message(db, course, role="user", content=text, proposal=None)
    fresh = load_course(db, course.id) or course
    if wants_stage_change(text):
        assistant = add_message(
            db,
            fresh,
            role="assistant",
            content="Click Mark Complete above the tree to move to the next stage.",
            proposal=None,
        )
        fresh = load_course(db, course.id) or fresh
        return {"wrote": False, "handled": True, "user": user, "assistant": assistant, "course": fresh}
    return {"wrote": False, "handled": False, "user": user, "course": fresh}


def attach_fallback_draft(db: Session, course: StudioCourse, content: str) -> dict:
    """A draft for the stage on screen. The tree stays as it is until Push draft to Tree."""
    stage = active_stage_name(course)
    if wants_stage_change(content):
        assistant = add_message(
            db,
            course,
            role="assistant",
            content="Click Mark Complete above the tree to move to the next stage.",
            proposal=None,
        )
        fresh = load_course(db, course.id) or course
        return {"wrote": False, "user": None, "assistant": assistant, "course": fresh}
    operations = _fallback_operations(course, stage)
    proposal = {"operations": operations, "phase": stage} if operations else None
    reply = reply_without_false_claim(_fallback_reply(course, stage, operations))
    assistant = _save_unapplied(db, course, reply, proposal)
    fresh = load_course(db, course.id) or course
    return {"wrote": False, "assistant": assistant, "course": fresh}


def _latest_draft(db: Session, course: StudioCourse) -> StudioMessage | None:
    found = None
    for message in list_messages(db, course):
        if message.role == "assistant" and isinstance(message.proposal, dict) and message.proposal.get("operations"):
            found = message
    return found


def stage_draft(db: Session, course: StudioCourse) -> StudioMessage | None:
    """The latest draft, and only when it belongs to the stage on screen."""
    stage = active_stage_name(course)
    if stage == "ready":
        return None
    message = _latest_draft(db, course)
    if message is None:
        return None
    if _proposal_phase(message.proposal) != stage:
        return None
    return message


def can_push_draft(course: StudioCourse) -> bool:
    session = object_session(course)
    if session is None:
        return False
    return stage_draft(session, course) is not None


def push_draft(db: Session, course: StudioCourse) -> StudioCourse:
    """Upsert the latest draft for the stage on screen. A draft from another stage is ignored."""
    stage = active_stage_name(course)
    if stage == "ready":
        raise StudioError("stage", "ready has no draft", plain="Ready has nothing to push. Click Final Submit above the tree.")
    message = stage_draft(db, course)
    if message is None:
        return load_course(db, course.id) or course
    ops = _proposal_ops(message)
    if stage == "goals":
        ops = _expand_goals_operations(course, ops, message.content)
    _remember_undo(course, message)
    previous = _checker_view(course, stage)
    try:
        planned, skipped, _kept = split_patch(course, {"operations": ops})
        if not planned:
            plain = " ".join(skipped) if skipped else "That change had nothing to save."
            raise StudioError("patch", "needs at least one add, update, or remove", plain=plain)
        _apply(course, planned)
        course.updated_at = _now()
        db.flush()
    finally:
        _restore_checker_view(course, previous)
    message.applied = True
    course.ready = False
    course.updated_at = _now()
    db.flush()
    fresh = load_course(db, course.id) or course
    if stage == "goals":
        missing = [
            quest.code
            for quest in sorted(fresh.quests, key=lambda row: (row.position, row.code))
            if _goals_incomplete(quest)
        ]
        if missing:
            _note_skipped_goals(db, fresh, missing)
            fresh = load_course(db, course.id) or fresh
    return fresh


def advance_stage(db: Session, course: StudioCourse) -> StudioCourse:
    """Mark Complete on the stage on screen. Stepping back returns to the furthest stage."""
    stage = active_stage_name(course)
    tracked = tracked_stage_name(course)
    if stage == "ready":
        if tracked != "ready":
            raise StudioError(
                "stage",
                "is later than the open stage",
                plain=f"Mark {_stage_label(tracked)} complete before opening Ready.",
            )
        course.ready = True
        course.updated_at = _now()
        db.flush()
        return load_course(db, course.id) or course
    gaps = stage_gaps_for(course, stage)
    if gaps:
        raise StudioError("stage", "still open", plain=" ".join(gaps))
    if _STAGE_ORDER[stage] < _STAGE_ORDER[tracked]:
        _write_pref(course, _STAGE_VIEW, None)
        course.updated_at = _now()
        db.flush()
        return load_course(db, course.id) or course
    _write_pref(course, _STAGE_KEY, _NEXT_STAGE[stage])
    _write_pref(course, _STAGE_VIEW, None)
    course.updated_at = _now()
    db.flush()
    fresh = load_course(db, course.id) or course
    content, proposal = opening_for(fresh)
    add_message(db, fresh, role="assistant", content=content, proposal=proposal)
    return load_course(db, course.id) or fresh


def set_stage_view(course: StudioCourse, name: str) -> None:
    """Open an earlier stage again. Later stages stay locked."""
    if name == "structure":
        name = "quests"
    if name not in ("quests", "goals", "close", "ready"):
        raise StudioError(
            "stage",
            "must be a course stage",
            plain="Choose Quests, Goals/Success Criteria, Close, or Ready.",
        )
    if _STAGE_ORDER[name] > _STAGE_ORDER[tracked_stage_name(course)]:
        raise StudioError(
            "stage",
            "is later than the open stage",
            plain=f"Mark {_stage_label(tracked_stage_name(course))} complete before opening {_stage_label(name)}.",
        )
    if name == tracked_stage_name(course):
        _write_pref(course, _STAGE_VIEW, None)
    else:
        _write_pref(course, _STAGE_VIEW, name)
    course.updated_at = _now()


def _next_quest_code(course: StudioCourse) -> str:
    taken = {quest.code for quest in course.quests}
    number = 1
    while f"{course.code}-Q{number}" in taken:
        number += 1
    return f"{course.code}-Q{number}"


def _quest_by_code(course: StudioCourse, code: str) -> StudioQuest:
    wanted = (code or "").strip().upper()
    for quest in course.quests:
        if quest.code == wanted:
            return quest
    raise StudioError("code", f"{wanted} is not in this course", plain=f"{wanted} is not in this course.")


def edit_tree(
    db: Session,
    course: StudioCourse,
    *,
    action: str,
    code: str | None = None,
    title: str | None = None,
    position: int | None = None,
    learning_goal: str | None = None,
    success_criterion: str | None = None,
    close: dict | None = None,
) -> None:
    """A popup write for the stage on screen. Other stages stay locked."""
    stage = active_stage_name(course)
    quest_actions = {"add_quest", "update_quest", "delete_quest"}
    goal_actions = {"add_goal", "update_goal", "delete_goal"}
    if action in quest_actions and stage != "quests":
        raise StudioError("stage", "quests only", plain="Quest edits are only open in the Quests stage.")
    if action in goal_actions and stage != "goals":
        raise StudioError("stage", "goals only", plain="Goal edits are only open in the Goals/Success Criteria stage.")
    if action == "set_close" and stage != "close":
        raise StudioError("stage", "close only", plain="Close edits are only open in the Close stage.")
    _remember_undo(course, None)
    if action == "add_quest":
        label = _text("title", title or "", required=True)
        row = StudioQuest(
            course_id=course.id,
            code=_next_quest_code(course),
            position=len(course.quests) + 1,
            title=label,
            learning_goal="",
            success_criterion="",
        )
        course.quests.append(row)
    elif action == "update_quest":
        quest = _quest_by_code(course, code or "")
        quest.title = _text("title", title or "", required=True)
    elif action == "delete_quest":
        quest = _quest_by_code(course, code or "")
        course.quests.remove(quest)
        db.delete(quest)
        _compact(list(course.quests))
    elif action == "add_goal":
        quest = _quest_by_code(course, code or "")
        rows = goal_rows(quest)
        rows.append(
            {
                "position": len(rows) + 1,
                "learning_goal": _text("learning_goal", learning_goal or ""),
                "success_criterion": _text("success_criterion", success_criterion or ""),
            }
        )
        _replace_goals(quest, normalize_goals(rows))
    elif action == "update_goal":
        quest = _quest_by_code(course, code or "")
        rows = goal_rows(quest)
        slot = position or 1
        found = False
        for row in rows:
            if row["position"] == slot:
                row["learning_goal"] = _text("learning_goal", learning_goal or "")
                row["success_criterion"] = _text("success_criterion", success_criterion or "")
                found = True
        if not found:
            raise StudioError("position", "is not a goal on this quest", plain="That goal is not on this quest.")
        _replace_goals(quest, normalize_goals(rows))
    elif action == "delete_goal":
        quest = _quest_by_code(course, code or "")
        slot = position or 1
        rows = [row for row in goal_rows(quest) if row["position"] != slot]
        _replace_goals(quest, normalize_goals(rows) if rows else [])
    elif action == "set_close":
        quest = _quest_by_code(course, code or "")
        _fill_close(quest, normalize_close(close))
    else:
        raise StudioError("action", "is not a tree edit", plain="That edit is not available.")
    course.ready = False
    course.updated_at = _now()
    db.flush()
_UNDO = "_undo"


def _preferences_without_undo(course: StudioCourse) -> dict:
    prefs = copy.deepcopy(course.preferences or {})
    if isinstance(prefs, dict):
        prefs.pop(_UNDO, None)
    return prefs if isinstance(prefs, dict) else {}


def has_undo(course: StudioCourse) -> bool:
    prefs = course.preferences if isinstance(course.preferences, dict) else {}
    undo = prefs.get(_UNDO)
    return isinstance(undo, dict) and isinstance(undo.get("course"), dict)


def _phase_name(name) -> str | None:
    """Stored phase id structure opens on Quests."""
    if name == "structure":
        return "quests"
    if name in ("quests", "goals", "close", "ready"):
        return name
    return None


def _proposal_phase(proposal) -> str | None:
    if isinstance(proposal, dict):
        return _phase_name(proposal.get("phase"))
    return None


def _proposal_ops(message: StudioMessage) -> list[dict]:
    proposal = message.proposal if isinstance(message.proposal, dict) else None
    ops = proposal.get("operations") if proposal else None
    if not isinstance(ops, list) or not ops:
        raise StudioError("proposal", "there is nothing to accept")
    return list(ops)


def _pick_indexes(count: int, indexes: list[int] | None) -> list[int]:
    if indexes is None:
        return list(range(count))
    if not indexes:
        raise StudioError("items", "choose at least one", plain="Choose at least one change.")
    chosen: list[int] = []
    for index in indexes:
        if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= count or index in chosen:
            raise StudioError("items", "is not in this proposal", plain="That change is not in this proposal.")
        chosen.append(index)
    return chosen


def _store_ops(ops: list[dict], phase: str | None) -> dict:
    stored: dict = {"operations": ops}
    if phase:
        stored["phase"] = phase
    return stored


def _close_snapshot(quest: StudioQuest) -> dict | None:
    if quest.close is None:
        return None
    items, questions = _unpack_items(quest.close.items)
    return {
        "close_style": quest.close.close_style,
        "answer_style": quest.close.answer_style,
        "choice_mode": quest.close.choice_mode,
        "items": copy.deepcopy(items),
        "questions": copy.deepcopy(questions),
        "intent": quest.close.intent or "",
        "selection": _unpack_close(quest.close.items)[2],
    }


def _course_snapshot(course: StudioCourse) -> dict:
    quests = []
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        quests.append(
            {
                "code": quest.code,
                "position": quest.position,
                "title": quest.title,
                "learning_goal": quest.learning_goal,
                "success_criterion": quest.success_criterion,
                "goals": goal_rows(quest),
                "close": _close_snapshot(quest),
                "moves": [
                    {
                        "code": move.code,
                        "position": move.position,
                        "title": move.title,
                        "learning_goal": move.learning_goal,
                        "success_criterion": move.success_criterion,
                    }
                    for move in sorted(quest.moves, key=lambda row: (row.position, row.code))
                ],
            }
        )
    return {
        "title": course.title,
        "audience": course.audience,
        "focus": course.focus,
        "theme": course.theme,
        "depth": course.depth,
        "quiz_minutes": course.quiz_minutes,
        "sources": course.sources,
        "ready": bool(course.ready),
        "schema_version": course.schema_version,
        "preferences": _preferences_without_undo(course),
        "quests": quests,
    }


def _snapshot_quests(snap: dict) -> list[dict]:
    """New snapshots store quests. An older snapshot stored them under units."""
    if isinstance(snap.get("quests"), list):
        rows = [dict(item) for item in snap["quests"] if isinstance(item, dict)]
    else:
        rows = []
        for unit in snap.get("units") or []:
            if not isinstance(unit, dict):
                continue
            for quest in unit.get("quests") or []:
                if isinstance(quest, dict):
                    rows.append(dict(quest))
    rows.sort(key=lambda item: (item.get("position") or 0, str(item.get("code") or "")))
    for index, item in enumerate(rows, start=1):
        item["position"] = index
    return rows


def _message_undo(message: StudioMessage) -> dict:
    return {
        "id": str(message.id),
        "applied": bool(message.applied),
        "proposal": copy.deepcopy(message.proposal),
    }


def _remember_undo(course: StudioCourse, message: StudioMessage | None) -> None:
    prefs = _preferences_without_undo(course)
    prefs[_UNDO] = {
        "message_id": str(message.id) if message is not None else None,
        "applied": bool(message.applied) if message is not None else None,
        "proposal": copy.deepcopy(message.proposal) if message is not None else None,
        "messages": [_message_undo(message)] if message is not None else [],
        "course": _course_snapshot(course),
    }
    course.preferences = prefs


def _remember_writes(course: StudioCourse, messages: list[StudioMessage]) -> None:
    """One undo covers every proposal a confirm writes."""
    prefs = _preferences_without_undo(course)
    last = messages[-1] if messages else None
    prefs[_UNDO] = {
        "message_id": str(last.id) if last is not None else None,
        "applied": bool(last.applied) if last is not None else None,
        "proposal": copy.deepcopy(last.proposal) if last is not None else None,
        "messages": [_message_undo(message) for message in messages],
        "course": _course_snapshot(course),
    }
    course.preferences = prefs


def _restore_course(db: Session, course: StudioCourse, snap: dict) -> None:
    for key in ("title", "audience", "focus", "theme", "depth", "quiz_minutes", "sources", "ready", "schema_version"):
        setattr(course, key, snap[key])
    course.preferences = dict(snap.get("preferences") or {})
    for quest in list(course.quests):
        db.delete(quest)
    course.quests.clear()
    db.flush()
    db.expire(course, ["quests"])
    for quest_data in _snapshot_quests(snap):
        quest = StudioQuest(
            course_id=course.id,
            code=quest_data["code"],
            position=quest_data["position"],
            title=quest_data["title"],
            learning_goal=quest_data.get("learning_goal") or "",
            success_criterion=quest_data.get("success_criterion") or "",
        )
        course.quests.append(quest)
        db.flush()
        goals = quest_data.get("goals")
        if isinstance(goals, list) and goals:
            _replace_goals(
                quest,
                [
                    {
                        "position": item.get("position") or index,
                        "learning_goal": item.get("learning_goal") or "",
                        "success_criterion": item.get("success_criterion") or "",
                    }
                    for index, item in enumerate(goals, start=1)
                    if isinstance(item, dict)
                ],
            )
        close = quest_data.get("close")
        if isinstance(close, dict):
            _fill_close(quest, close)
        for move_data in quest_data.get("moves") or []:
            quest.moves.append(
                StudioMove(
                    course_id=course.id,
                    code=move_data["code"],
                    position=move_data["position"],
                    title=move_data["title"],
                    learning_goal=move_data.get("learning_goal") or "",
                    success_criterion=move_data.get("success_criterion") or "",
                )
            )
    db.flush()


def accept_proposal(
    db: Session, course: StudioCourse, message: StudioMessage, indexes: list[int] | None = None
) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    ops = _proposal_ops(message)
    chosen = _pick_indexes(len(ops), indexes)
    selected = [ops[index] for index in chosen]
    _remember_undo(course, message)
    apply_patch(db, course, {"operations": selected})
    chosen_set = set(chosen)
    remaining = [op for index, op in enumerate(ops) if index not in chosen_set]
    if remaining:
        message.proposal = _store_ops(remaining, _proposal_phase(message.proposal))
        message.applied = False
    else:
        message.applied = True
    if course_phase(course)["name"] != "ready":
        course.ready = False
    course.updated_at = _now()
    db.flush()


def dismiss_proposal(course: StudioCourse, message: StudioMessage, indexes: list[int] | None = None) -> None:
    if message.course_id != course.id:
        raise StudioError("message", "is not part of this course", status=404)
    if message.applied:
        raise StudioError("proposal", "that change is already saved", status=409)
    ops = _proposal_ops(message)
    if indexes is None:
        message.proposal = None
    else:
        chosen = set(_pick_indexes(len(ops), indexes))
        remaining = [op for index, op in enumerate(ops) if index not in chosen]
        message.proposal = _store_ops(remaining, _proposal_phase(message.proposal)) if remaining else None
    course.updated_at = _now()


def edit_item(
    db: Session,
    course: StudioCourse,
    *,
    kind: str,
    code: str,
    title: str | None,
    learning_goal: str | None,
    success_criterion: str | None,
) -> None:
    if kind == "unit":
        raise StudioError("kind", "a unit is not part of this course", plain="A unit is not part of this course.")
    if kind not in ("quest", "move"):
        raise StudioError("kind", "must be a quest or move", plain="Edit a quest or a move.")
    raw: dict = {"op": "update", "kind": kind, "code": code}
    if title is not None:
        raw["title"] = title
    if learning_goal is not None:
        raw["learning_goal"] = learning_goal
    if success_criterion is not None:
        raw["success_criterion"] = success_criterion
    cleaned = _keep_tier_fields(raw, "update")
    step = _plan_update(course.code, cleaned, _nodes_for(course), {})
    if step is None:
        raise StudioError("patch", "needs a change", plain="That change had nothing to save.")
    _remember_undo(course, None)
    _apply(course, [step])
    if course_phase(course)["name"] != "ready":
        course.ready = False
    course.updated_at = _now()
    db.flush()


def undo_last(db: Session, course: StudioCourse) -> None:
    prefs = course.preferences if isinstance(course.preferences, dict) else {}
    undo = prefs.get(_UNDO) if isinstance(prefs, dict) else None
    if not isinstance(undo, dict) or not isinstance(undo.get("course"), dict):
        raise StudioError("proposal", "nothing to undo", plain="There is nothing to undo.")
    message = None
    message_id = undo.get("message_id")
    if message_id:
        message = db.get(StudioMessage, UUID(str(message_id)))
        if message is None or message.course_id != course.id:
            raise StudioError("message", "that undo is no longer available", plain="That undo is no longer available.")
    _restore_course(db, course, undo["course"])
    rows = undo.get("messages")
    if isinstance(rows, list) and rows:
        for item in rows:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            row = db.get(StudioMessage, UUID(str(item["id"])))
            if row is None or row.course_id != course.id:
                continue
            row.proposal = copy.deepcopy(item.get("proposal"))
            row.applied = bool(item.get("applied"))
    elif message is not None:
        message.proposal = copy.deepcopy(undo.get("proposal"))
        message.applied = bool(undo.get("applied"))
    course.updated_at = _now()
    db.flush()


def ensure_settings(db: Session) -> StudioSettings:
    row = db.get(StudioSettings, SETTINGS_ID)
    if row is not None:
        return row
    row = StudioSettings(id=SETTINGS_ID, model=DEFAULT_STUDIO_MODEL)
    db.add(row)
    db.flush()
    return row


def set_model(db: Session, model: str) -> StudioSettings:
    if not isinstance(model, str) or model not in STUDIO_MODELS:
        raise StudioError("model", "must be gpt-4o-mini, gpt-4o, or gpt-4.1-mini")
    row = ensure_settings(db)
    row.model = model
    db.flush()
    return row


def course_phase(course: StudioCourse) -> dict:
    """The one wave still open. Later waves are not part of this result."""
    quests = sorted(course.quests, key=lambda row: (row.position, row.code))
    if not quests:
        return {"name": "quests", "label": "Quests", "open_codes": [course.code]}
    missing_goals: list[str] = []
    missing_close: list[str] = []
    for quest in quests:
        if _goals_incomplete(quest):
            missing_goals.append(quest.code)
        style = quest.close.close_style if quest.close is not None else ""
        if not str(style or "").strip():
            missing_close.append(quest.code)
    if missing_goals:
        return {"name": "goals", "label": "Goals/Success Criteria", "open_codes": missing_goals}
    if missing_close:
        return {"name": "close", "label": "Close", "open_codes": missing_close}
    return {"name": "ready", "label": "Ready", "open_codes": []}


PHASES = (
    ("quests", "Quests"),
    ("goals", "Goals/Success Criteria"),
    ("close", "Close"),
    ("ready", "Ready"),
)
PHASE_ORDER = {name: index for index, (name, _label) in enumerate(PHASES)}
PHASE_LABELS = dict(PHASES)


def _stored_phase_view(course: StudioCourse) -> str | None:
    raw = course.preferences if isinstance(course.preferences, dict) else {}
    value = raw.get("phase_view") if isinstance(raw, dict) else None
    if value == "structure":
        value = "quests"
    if value in PHASE_ORDER:
        return str(value)
    return None


def _quest_codes(course: StudioCourse) -> list[str]:
    return [quest.code for quest in sorted(course.quests, key=lambda row: (row.position, row.code))]


def _codes_in_phase(course: StudioCourse, name: str) -> list[str]:
    if name == "quests":
        codes = _quest_codes(course)
        return codes or [course.code]
    if name in ("goals", "close"):
        return _quest_codes(course)
    return []


def viewed_phase(course: StudioCourse) -> dict:
    """The phase the chat and the strip highlight. Earlier choices include filled items."""
    open_phase = course_phase(course)
    stored = _stored_phase_view(course)
    if stored is None or stored == open_phase["name"]:
        return {
            "name": open_phase["name"],
            "label": open_phase["label"],
            "codes": list(open_phase["open_codes"]),
            "stepped_back": False,
        }
    if PHASE_ORDER[stored] > PHASE_ORDER[open_phase["name"]]:
        return {
            "name": stored,
            "label": PHASE_LABELS[stored],
            "codes": _codes_in_phase(course, stored),
            "stepped_back": False,
        }
    return {
        "name": stored,
        "label": PHASE_LABELS[stored],
        "codes": _codes_in_phase(course, stored),
        "stepped_back": True,
    }


def phase_strip(course: StudioCourse) -> list[dict]:
    open_phase = course_phase(course)
    view = viewed_phase(course)
    open_index = PHASE_ORDER[open_phase["name"]]
    return [
        {
            "name": name,
            "label": label,
            "filled": (course.ready if name == "ready" else PHASE_ORDER[name] < open_index),
            "active": name == view["name"],
        }
        for name, label in PHASES
    ]


def set_phase_view(course: StudioCourse, name: str) -> None:
    """Point the chat at an earlier phase. Later rows stay as they are."""
    if name == "structure":
        name = "quests"
    if name not in PHASE_ORDER:
        raise StudioError(
            "phase",
            "must be a course phase",
            plain="Choose Quests, Goals/Success Criteria, Close, or Ready.",
        )
    open_phase = course_phase(course)
    if PHASE_ORDER[name] > PHASE_ORDER[open_phase["name"]]:
        raise StudioError(
            "phase",
            "is later than the open wave",
            plain=f"Finish {open_phase['label']} before opening {PHASE_LABELS[name]}.",
        )
    prefs = dict(course.preferences or {})
    if name == open_phase["name"]:
        prefs.pop("phase_view", None)
    else:
        prefs["phase_view"] = name
    course.preferences = prefs
    course.updated_at = _now()


def instruction_stage(course: StudioCourse) -> str:
    """Once Mark Complete is in use, the prompt follows that stage. Older courses keep the inferred wave."""
    if stored_stage(course):
        return active_stage_name(course)
    return viewed_phase(course)["name"]


def _tracked_phase_instructions(course: StudioCourse) -> str:
    stage = active_stage_name(course)
    label = _stage_label(stage)
    codes = ", ".join(code for code in _quest_codes(course)) or "none"
    count = quest_count_of(course)
    per_quest = goals_per_quest_of(course)
    if stage == "quests":
        focus = (
            "Talk only about quests. "
            f"Ask whether to draft {count} quests from the course description. "
            "When they want a draft, include one add or update per quest you are changing, with a real title about the subject. "
            "A patch does not remove quests it leaves out. "
            "Do not copy or slice the description. Do not mention other stages. "
            "Do not say the quests were added. The tree changes only when they click Push draft to Tree."
        )
    elif stage == "goals":
        focus = (
            "Talk only about goals and success criteria. "
            f"Offer {per_quest} goals per quest, all in one go or one quest at a time. "
            "Each goal needs an observable success criterion. "
            "When a draft covers more than one quest, write one block per quest that starts with that quest's code, "
            "then a Goal line and a Success criterion line for each goal. "
            "The patch has one update for every one of those codes. Do not stop after the first quest. "
            "Do not attach a later quest's goals to the first quest. "
            "A patch may name only the quests you are changing. Quests you leave out keep their goals. "
            "A patch updates each quest by code and sets parent to null. "
            "Do not fill close style in this patch. "
            "Do not say the goals were added. The tree changes only when they click Push draft to Tree."
        )
    elif stage == "close":
        focus = (
            "Talk only about closing questions. "
            "Offer a close for each quest, all in one go or one quest at a time. "
            "A close can be an essay, a single choice, a multi-choice, or no questions. "
            "A choice question needs at least two options. "
            "Set selection to single or multi, and mark correct on the right options. "
            "A patch may name only the quests you are changing. Quests you leave out keep their close. "
            "Do not say the closes were added. The tree changes only when they click Push draft to Tree."
        )
    else:
        focus = "The course is ready to submit. If they ask to change a stage, tell them to click Mark Complete above the tree. Do not send a patch."
    move = "If they ask to move to the next stage, tell them to click Mark Complete above the tree. Do not change the stage yourself."
    return (
        f"Current phase: {label}.\n"
        f"Codes in this stage: {codes}.\n"
        f"{focus}\n"
        f"{move}\n"
    )


def phase_instructions(course: StudioCourse) -> str:
    if stored_stage(course):
        return _tracked_phase_instructions(course)
    view = viewed_phase(course)
    if view["stepped_back"]:
        codes = ", ".join(view["codes"]) if view["codes"] else "none"
        open_label = course_phase(course)["label"]
        if view["name"] == "goals":
            focus = (
                "Offer a learning goal for each of these quests, including items already filled. "
                "A quest can hold several goals, each with its own criterion. "
                "Draft a criterion whenever you draft a goal. "
                "An update names that quest's code and sets parent to null. "
                "Do not wipe close style."
            )
        elif view["name"] == "quests":
            focus = (
                "Update these quests by code. Set parent to null. "
                "Do not wipe learning goals or close style."
            )
        else:
            focus = "An update names the item's code and sets parent to null. Do not wipe later work."
        return (
            f"Current phase: {view['label']}.\n"
            f"Codes in this phase: {codes}.\n"
            f"Patch only those codes. {focus}\n"
            f"The next unfinished wave is {open_label}. Later phases are not wiped.\n"
        )
    phase = course_phase(course)
    codes = ", ".join(phase["open_codes"]) if phase["open_codes"] else "none"
    count = quest_count_of(course)
    per_quest = goals_per_quest_of(course)
    if phase["name"] == "quests":
        focus = (
            "A quest is one section of the course the learner works through. "
            "Nothing is written until the creator confirms. "
            f"If no quests are on the course yet, ask whether to draft {count} quests from the course description, "
            "or whether they want something else. Do not send quest titles before that yes. "
            f"When they say yes, draft {count} real quest titles about the subject in the course description. "
            "Do not copy the description, and do not slice the description sentence into titles. "
            "Do not explain other phases in this reply. "
            "Empty learning goals are allowed."
        )
        later = "Do not fill learning goals or close style in this patch."
    elif phase["name"] == "goals":
        focus = (
            "A quest can hold several goals, each with its own criterion. "
            f"Offer {per_quest} goals per quest. "
            "Offer a learning goal for each open quest, addressed by that quest's code. "
            "Do not stop after the first quest. One update per quest code. "
            "Draft a criterion whenever you draft a goal. "
            "An update names that quest's code and sets parent to null."
        )
        later = "Do not fill close style in this patch."
    elif phase["name"] == "close":
        focus = (
            "Offer one close per quest, normally at least one question. "
            "An empty question list is saved when asked. "
            "An update names that code and sets parent to null."
        )
        later = "Do not add new goals in this patch."
    else:
        focus = "Quests, learning goals, and close styles are in place. Mark ready can be turned on."
        later = "There is no later phase. Do not send a patch unless the creator asks for a change."
    return (
        f"Current phase: {phase['label']}.\n"
        f"Codes still open in this phase: {codes}.\n"
        f"Patch only those codes. {focus}\n"
        f"{later}\n"
    )


def course_gaps(course: StudioCourse) -> list[str]:
    """Empty required fields on a saved item. These marks do not undo the draft."""
    gaps: list[str] = []
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        rows = goal_rows(quest)
        if not rows or any(not str(row["learning_goal"] or "").strip() for row in rows):
            gaps.append(f"{quest.code}: no learning goal")
        elif any(not str(row["success_criterion"] or "").strip() for row in rows):
            gaps.append(f"{quest.code}: no success criterion")
        style = quest.close.close_style if quest.close is not None else ""
        if not str(style or "").strip():
            gaps.append(f"{quest.code}: no close style")
        for move in sorted(quest.moves, key=lambda row: (row.position, row.code)):
            _goal_gap(gaps, move.code, move.learning_goal)
    return gaps


def _goal_gap(gaps: list[str], code: str, learning_goal: str | None) -> None:
    if not str(learning_goal or "").strip():
        gaps.append(f"{code}: no learning goal")


def mark_ready(course: StudioCourse) -> None:
    """Record that the creator says this draft is complete. Nothing is copied."""
    phase = course_phase(course)
    gaps = course_gaps(course)
    if phase["name"] != "ready":
        listed = "; ".join(gaps) if gaps else ", ".join(phase["open_codes"])
        raise StudioError(
            "ready",
            f"still has open gaps: {listed}",
            plain=f"These gaps are still open: {listed}.",
        )
    course.ready = True
    course.updated_at = _now()


def _close_out(close: dict | None) -> StudioCloseOut | None:
    if close is None:
        return None
    return StudioCloseOut(
        close_style=close["close_style"],
        answer_style=close["answer_style"],
        choice_mode=close["choice_mode"],
        items=list(close.get("items") or []),
        questions=list(close.get("questions") or []),
        intent=close["intent"],
        selection=close.get("selection") if close.get("selection") in ("single", "multi") else None,
    )


def _row_close(row: StudioQuestClose | None) -> StudioCloseOut | None:
    if row is None:
        return None
    items, questions, selection = _unpack_close(row.items)
    return StudioCloseOut(
        close_style=row.close_style,
        answer_style=row.answer_style,
        choice_mode=row.choice_mode,
        items=items,
        questions=questions,
        intent=row.intent or "",
        selection=selection,
    )


def course_out(course: StudioCourse) -> StudioCourseOut:
    quests = []
    for quest in sorted(course.quests, key=lambda row: (row.position, row.code)):
        moves = [
            StudioMoveOut(
                id=move.id,
                code=move.code,
                position=move.position,
                title=move.title,
                learning_goal=move.learning_goal,
                success_criterion=move.success_criterion,
            )
            for move in sorted(quest.moves, key=lambda row: (row.position, row.code))
        ]
        quests.append(
            StudioQuestOut(
                id=quest.id,
                code=quest.code,
                position=quest.position,
                title=quest.title,
                learning_goal=quest.learning_goal,
                success_criterion=quest.success_criterion,
                goals=[StudioGoalOut(**row) for row in goal_rows(quest)],
                close=_row_close(quest.close),
                moves=moves,
            )
        )
    default = close_default_of(course)
    return StudioCourseOut(
        id=course.id,
        code=course.code,
        title=course.title,
        audience=course.audience,
        focus=course.focus,
        theme=course.theme,
        depth=course.depth,
        quiz_minutes=course.quiz_minutes,
        sources=course.sources,
        schema_version=course.schema_version,
        close_default=_close_out(default),
        ready=bool(course.ready),
        gaps=course_gaps(course),
        phase=StudioPhaseOut(**course_phase(course)),
        strip=[StudioStripOut(**item) for item in phase_strip(course)],
        view=StudioViewOut(
            name=viewed_phase(course)["name"],
            label=viewed_phase(course)["label"],
            codes=viewed_phase(course)["codes"],
        ),
        quests=quests,
        quest_count=quest_count_of(course),
        goals_per_quest=goals_per_quest_of(course),
        undo=has_undo(course),
        stage=_stage_out(course),
        stage_strip=[StudioStripOut(**item) for item in _stage_strip(course)],
        stage_view=_stage_view_out(course),
        stage_gaps=stage_gaps_for(course, active_stage_name(course)),
        can_advance=can_advance_stage(course),
        can_push=can_push_draft(course),
        updated_at=course.updated_at,
    )


def _stage_out(course: StudioCourse) -> StudioPhaseOut:
    name = tracked_stage_name(course)
    return StudioPhaseOut(name=name, label=_stage_label(name), open_codes=_quest_codes(course))


def _stage_view_out(course: StudioCourse) -> StudioViewOut:
    name = active_stage_name(course)
    return StudioViewOut(name=name, label=_stage_label(name), codes=_quest_codes(course))


def _stage_strip(course: StudioCourse) -> list[dict]:
    tracked = tracked_stage_name(course)
    active = active_stage_name(course)
    order = {"quests": 0, "goals": 1, "close": 2, "ready": 3}
    tracked_index = order[tracked]
    return [
        {
            "name": name,
            "label": label,
            "filled": order[name] < tracked_index or (name == "ready" and bool(course.ready)),
            "active": name == active,
        }
        for name, label in PHASES
    ]


def summary_out(course: StudioCourse) -> StudioCourseSummary:
    return StudioCourseSummary(
        id=course.id,
        code=course.code,
        title=course.title,
        updated_at=course.updated_at,
    )


def message_out(message: StudioMessage) -> StudioMessageOut:
    return StudioMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        seq=message.seq,
        proposal=message.proposal,
        applied=message.applied,
        created_at=message.created_at,
    )


def _goals_schema() -> dict:
    return {
        "description": "Only this quest's goals. Later quests get their own operation.",
        "anyOf": [
            {"type": "null"},
            {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "learning_goal": {"type": "string"},
                        "success_criterion": {"type": "string"},
                        "position": {"type": "integer"},
                    },
                    "required": ["learning_goal", "success_criterion", "position"],
                },
            },
        ],
    }


def _phase_operation_schema(phase: str) -> dict:
    if phase == "goals":
        properties = {
            "op": {"type": "string", "enum": ["update", "add"]},
            "kind": {"type": "string", "enum": ["quest"]},
            "code": {"type": "string"},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": _goals_schema(),
        }
    elif phase == "close":
        properties = {
            "op": {"type": "string", "enum": ["update", "add"]},
            "kind": {"type": "string", "enum": ["quest"]},
            "code": {"type": "string"},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
        }
    elif phase == "ready":
        properties = {
            "op": {"type": "string", "enum": ["update", "remove"]},
            "kind": {"type": "string", "enum": ["quest", "move"]},
            "code": {"type": "string"},
            "title": {"type": ["string", "null"]},
            "learning_goal": {"type": ["string", "null"]},
            "success_criterion": {"type": ["string", "null"]},
            "goals": _goals_schema(),
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
            "close": {"anyOf": [{"type": "null"}, _close_schema()]},
        }
    else:
        properties = {
            "op": {"type": "string", "enum": ["add", "update", "remove"]},
            "kind": {"type": "string", "enum": ["quest", "move"]},
            "code": {"type": "string"},
            "parent": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "position": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        }
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }
    if phase == "goals":
        schema["description"] = "One update per quest code. Do not stop after the first quest."
    return schema


def response_schema(course: StudioCourse) -> dict:
    """The only patch shape the model may emit for the phase on screen."""
    phase = instruction_stage(course)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reply": {
                "type": "string",
                "description": (
                    "What the creator reads. Talk through the suggestion for the phase on screen "
                    "and ask one clear question. Say which framework a suggestion comes from. "
                    "Do not say the course was saved. The tree changes only when the creator clicks Push draft to Tree."
                ),
            },
            "patch": {
                "description": (
                    "Null when nothing should change. Otherwise one update per quest code, "
                    "and do not stop after the first quest. Each operation's goals belong only to that quest."
                    if phase == "goals"
                    else "Null when nothing should change. Otherwise operations allowed in this phase."
                ),
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "operations": {
                                "type": "array",
                                "maxItems": 40,
                                "items": _phase_operation_schema(phase),
                            }
                        },
                        "required": ["operations"],
                    },
                ],
            },
        },
        "required": ["reply", "patch"],
    }


def system_prompt(course: StudioCourse, messages: list[StudioMessage]) -> str:
    tree = course_out(course).model_dump(mode="json")
    pending = []
    for message in messages:
        if message.proposal and not message.applied:
            pending.append(message.proposal)
    pending_note = "There is no held patch."
    if pending:
        pending_note = (
            "These patches are held and are not part of the course JSON below. "
            "They are written only after the creator confirms in the chat:\n"
            + "\n".join(str(item) for item in pending)
        )
    description = course.theme.strip() if course.theme and course.theme.strip() else "none yet"
    return (
        "You are helping a person build one course in the CreateCourse studio.\n"
        f"Course description: {description}\n"
        "Quests, learning goals, and close items follow this course description.\n"
        "The creator states a focus. You propose the next change for the phase on screen, "
        "talk through it, and ask one clear question about what to change.\n"
        "You may use widely known national curricula and standard texts as suggestions. "
        "You must say which framework a suggestion comes from. "
        "Label every curriculum idea as a suggestion.\n"
        "You have no web search and no document upload. Do not claim you searched the web or read an uploaded file.\n"
        "Nothing is written until the creator clicks Push draft to Tree. "
        "Chat never changes the tree and never moves the stage. "
        "If they ask to move to the next stage, tell them to click Mark Complete above the tree. "
        "Do not say you added the quests. "
        "There is no Accept button and no Skip button. "
        "The server still checks a pushed draft. A rejected operation is skipped and the rest can be saved. "
        "Do not say the course was saved, and do not say the structure was written.\n"
        "The response schema lists the only fields for this phase. "
        "Goals and Close refuse a code that is not a quest in this course.\n"
        "A Goals or Close patch does not have to name every quest. Quests left out stay as they are.\n"
        f"{phase_instructions(course)}"
        "Return a reply plus an optional patch. The patch is a list of operations. "
        "Each operation is add, update, or remove, and it names a code. "
        "Do not rewrite the whole tree in prose. The server ignores anything that is not a typed patch.\n"
        "Each add names these fields: code, parent code, title, position as an integer from 1, "
        "learning goal, success criterion, and quest-close choices. "
        "In the patch JSON those fields are code, parent, title, position, learning_goal, "
        "success_criterion, goals, and close.\n"
        "A quest can hold several goals. Each goal has its own success criterion. "
        "A success criterion is one observable action about this goal only, specific enough that the close can test it. "
        "It is not a quiz item. "
        "Example: goal “Understand that the angles of a triangle add to 180°”, "
        "criterion “States that the three angles add to 180° and uses that to find a missing angle.” "
        "Draft a criterion whenever you draft a goal. The tree changes only when the creator clicks Push draft to Tree.\n"
        "A position of 0 is invalid. Leave position null and the server fills the next free number. "
        "A position outside 1 to 200, or past the end of the list, is skipped and reported in one sentence. "
        "The other operations can still be saved.\n"
        "A missing learning goal or quest-close choice does not block the write. "
        "The course is a draft from the moment it is created. "
        "The tree marks a missing learning goal, a goal with no success criterion, and a missing close style. "
        "An empty question list is allowed and is not a gap. "
        "Those marks do not undo the draft. "
        "Mark ready only records that the creator says the draft is complete.\n"
        "The course close default is a preference in the header. "
        "Copy it into a quest's quest-close choices when you want that close. "
        "If close is null, the quest is stored with no close style. The server does not invent one.\n"
        "Normally offer at least one question on a close. Save an empty question list when the creator asks for it.\n"
        "To change an item, name its code and set parent to null. A parent sent on an update is ignored. "
        "An add of a code that is already in this course is saved as an update of that item. "
        "To add an item, choose a new short stable code "
        f"such as {course.code}-Q1 or {course.code}-Q1-M1 and name the parent code when the item is a move.\n"
        "On an add, a quest has no parent. A move parent is a quest code.\n"
        "Codes stay inside this course. Use null for a field you are not changing. An add requires a title.\n"
        "close_style is one or several. answer_style is multiple_choice, essay, or mixed. "
        "Essay stores neither items nor intent.\n"
        "depth, sources, audience, focus, and theme are course preferences. "
        "depth is survey, standard, or go_deep. "
        f"Number of quests is a target of {quest_count_of(course)}, and goals per quest is a target of {goals_per_quest_of(course)}. "
        "Neither number is a hard cap.\n"
        "The server drops course preferences copied onto a quest or move, and still saves the item.\n"
        "sources is the framework to honor, or none.\n"
        f"{pending_note}\n"
        "The course so far, read from the database:\n"
        f"{json.dumps(tree)}"
    )
```

Source file `apps/api/app/routes/studio.py`:

```python
"""CreateCourse HTTP API. These routes do not read or write tutor sessions."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudioMessage
from app.schemas import (
    StudioAcceptOut,
    StudioCopyIn,
    StudioCourseCreate,
    StudioCourseOut,
    StudioCourseSummary,
    StudioDeleteIn,
    StudioDraftIn,
    StudioEditIn,
    StudioFallbackIn,
    StudioTreeEditIn,
    StudioIndexesIn,
    StudioMessageIn,
    StudioMessageOut,
    StudioOpeningOut,
    StudioPhaseIn,
    StudioPreferencesIn,
    StudioPromptOut,
    StudioSettingsIn,
    StudioSettingsOut,
    StudioTurnIn,
    StudioTurnOut,
)
from app.studio import (
    STUDIO_MODELS,
    STUDIO_TEMPERATURE,
    StudioError,
    accept_proposal,
    add_message,
    advance_stage,
    attach_fallback_draft,
    chat_turn,
    copy_studio_course,
    course_out,
    create_course,
    delete_studio_course,
    dismiss_proposal,
    edit_item,
    edit_tree,
    ensure_settings,
    list_courses,
    list_messages,
    load_course,
    mark_ready,
    message_out,
    response_schema,
    seed_opening,
    push_draft,
    set_model,
    set_phase_view,
    set_stage_view,
    summary_out,
    system_prompt,
    undo_last,
    update_preferences,
)

router = APIRouter(prefix="/studio")


def _fail(exc: StudioError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.plain)


def _course(db: Session, course_id: UUID):
    course = load_course(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _message(db: Session, course_id: UUID, message_id: UUID) -> StudioMessage:
    message = db.get(StudioMessage, message_id)
    if message is None or message.course_id != course_id:
        raise HTTPException(status_code=404, detail="Message not found")
    return message


@router.get("/courses", response_model=list[StudioCourseSummary])
def get_courses(db: Session = Depends(get_db)) -> list[StudioCourseSummary]:
    return [summary_out(course) for course in list_courses(db)]


@router.post("/courses", response_model=StudioCourseOut)
def post_course(body: StudioCourseCreate, db: Session = Depends(get_db)) -> StudioCourseOut:
    try:
        course = create_course(db, code=body.code, title=body.title)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/delete")
def post_delete(course_id: UUID, body: StudioDeleteIn, db: Session = Depends(get_db)) -> dict:
    course = _course(db, course_id)
    try:
        delete_studio_course(db, course, body.password)
    except StudioError as exc:
        raise _fail(exc) from exc
    return {"deleted": True}


@router.post("/courses/{course_id}/copy", response_model=StudioCourseOut)
def post_copy(course_id: UUID, body: StudioCopyIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        copied = copy_studio_course(db, course, body.title)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(copied)


@router.get("/courses/{course_id}", response_model=StudioCourseOut)
def get_course(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    return course_out(_course(db, course_id))


@router.patch("/courses/{course_id}", response_model=StudioCourseOut)
def patch_course(
    course_id: UUID, body: StudioPreferencesIn, db: Session = Depends(get_db)
) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        update_preferences(course, body.model_dump())
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/ready", response_model=StudioCourseOut)
def post_ready(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        mark_ready(course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/phase", response_model=StudioCourseOut)
def post_phase(course_id: UUID, body: StudioPhaseIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        set_phase_view(course, body.name)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.get("/courses/{course_id}/messages", response_model=list[StudioMessageOut])
def get_messages(course_id: UUID, db: Session = Depends(get_db)) -> list[StudioMessageOut]:
    course = _course(db, course_id)
    return [message_out(message) for message in list_messages(db, course)]


@router.post("/courses/{course_id}/opening", response_model=StudioOpeningOut)
def post_opening(course_id: UUID, db: Session = Depends(get_db)) -> StudioOpeningOut:
    course = _course(db, course_id)
    try:
        messages = seed_opening(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id) or course
    return StudioOpeningOut(course=course_out(fresh), messages=[message_out(message) for message in messages])


@router.post("/courses/{course_id}/turns", response_model=StudioTurnOut)
def post_turn(course_id: UUID, body: StudioTurnIn, db: Session = Depends(get_db)) -> StudioTurnOut:
    course = _course(db, course_id)
    try:
        result = chat_turn(db, course, body.content)
    except StudioError as exc:
        raise _fail(exc) from exc
    assistant = result.get("assistant")
    return StudioTurnOut(
        wrote=False,
        handled=bool(result.get("handled")),
        user=message_out(result["user"]) if result.get("user") else None,
        assistant=message_out(assistant) if assistant else None,
        course=course_out(result["course"]) if result.get("course") else None,
    )


@router.post("/courses/{course_id}/fallback", response_model=StudioTurnOut)
def post_fallback(course_id: UUID, body: StudioFallbackIn, db: Session = Depends(get_db)) -> StudioTurnOut:
    course = _course(db, course_id)
    try:
        result = attach_fallback_draft(db, course, body.content)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioTurnOut(
        wrote=False,
        handled=True,
        assistant=message_out(result["assistant"]),
        course=course_out(result["course"]),
    )


@router.post("/courses/{course_id}/push-draft", response_model=StudioCourseOut)
def post_push_draft(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        fresh = push_draft(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(fresh)


@router.post("/courses/{course_id}/advance-stage", response_model=StudioCourseOut)
def post_advance_stage(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        fresh = advance_stage(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(fresh)


@router.post("/courses/{course_id}/stage", response_model=StudioCourseOut)
def post_stage(course_id: UUID, body: StudioPhaseIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        set_stage_view(course, body.name)
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/tree", response_model=StudioCourseOut)
def post_tree(course_id: UUID, body: StudioTreeEditIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        edit_tree(
            db,
            course,
            action=body.action,
            code=body.code,
            title=body.title,
            position=body.position,
            learning_goal=body.learning_goal,
            success_criterion=body.success_criterion,
            close=body.close,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id) or course
    return course_out(fresh)


@router.post("/courses/{course_id}/messages", response_model=StudioMessageOut)
def post_message(
    course_id: UUID, body: StudioMessageIn, db: Session = Depends(get_db)
) -> StudioMessageOut:
    course = _course(db, course_id)
    try:
        message = add_message(
            db,
            course,
            role=body.role,
            content=body.content,
            proposal=body.proposal,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    return message_out(message)


@router.post("/courses/{course_id}/messages/{message_id}/accept", response_model=StudioAcceptOut)
def post_accept(
    course_id: UUID,
    message_id: UUID,
    body: StudioIndexesIn | None = None,
    db: Session = Depends(get_db),
) -> StudioAcceptOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        accept_proposal(db, course, message, None if body is None else body.indexes)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioAcceptOut(course=course_out(course), message=message_out(message))


@router.post("/courses/{course_id}/messages/{message_id}/dismiss", response_model=StudioMessageOut)
def post_dismiss(
    course_id: UUID,
    message_id: UUID,
    body: StudioIndexesIn | None = None,
    db: Session = Depends(get_db),
) -> StudioMessageOut:
    course = _course(db, course_id)
    message = _message(db, course_id, message_id)
    try:
        dismiss_proposal(course, message, None if body is None else body.indexes)
    except StudioError as exc:
        raise _fail(exc) from exc
    return message_out(message)


@router.post("/courses/{course_id}/edit", response_model=StudioCourseOut)
def post_edit(course_id: UUID, body: StudioEditIn, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        edit_item(
            db,
            course,
            kind=body.kind,
            code=body.code,
            title=body.title,
            learning_goal=body.learning_goal,
            success_criterion=body.success_criterion,
        )
    except StudioError as exc:
        raise _fail(exc) from exc
    return course_out(course)


@router.post("/courses/{course_id}/undo", response_model=StudioCourseOut)
def post_undo(course_id: UUID, db: Session = Depends(get_db)) -> StudioCourseOut:
    course = _course(db, course_id)
    try:
        undo_last(db, course)
    except StudioError as exc:
        raise _fail(exc) from exc
    fresh = load_course(db, course_id)
    return course_out(fresh or course)


@router.get("/courses/{course_id}/prompt", response_model=StudioPromptOut)
def get_prompt(course_id: UUID, db: Session = Depends(get_db)) -> StudioPromptOut:
    course = _course(db, course_id)
    settings = ensure_settings(db)
    messages = list_messages(db, course)
    return StudioPromptOut(
        model=settings.model,
        system_prompt=system_prompt(course, messages),
        response_schema=response_schema(course),
        temperature=STUDIO_TEMPERATURE,
    )


@router.get("/settings", response_model=StudioSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> StudioSettingsOut:
    row = ensure_settings(db)
    return StudioSettingsOut(model=row.model, options=list(STUDIO_MODELS))


@router.put("/settings", response_model=StudioSettingsOut)
def put_settings(body: StudioSettingsIn, db: Session = Depends(get_db)) -> StudioSettingsOut:
    try:
        row = set_model(db, body.model)
    except StudioError as exc:
        raise _fail(exc) from exc
    return StudioSettingsOut(model=row.model, options=list(STUDIO_MODELS))
```

Source file `apps/web/app/api/studio/chat/route.ts`:

```typescript
import { openai } from "@ai-sdk/openai";
import { Output, convertToModelMessages, jsonSchema, streamText, type JSONSchema7, type UIMessage } from "ai";

import { api, apiBase } from "@/lib/api";
import type { StudioMessage } from "@/lib/studio";
import { detailFrom, plainFailure, replyIfUnwritten, settleModelResult } from "@/lib/studio-chat";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

const ALLOWED_MODELS = new Set(["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"]);

type PromptBundle = {
  model: string;
  system_prompt: string;
  response_schema: JSONSchema7;
  temperature: number;
};

type CourseEdit = {
  reply?: string;
  patch?: { operations?: unknown[] } | null;
};

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function POST(req: Request) {
  let body: { courseId?: string; content?: string };
  try {
    body = (await req.json()) as { courseId?: string; content?: string };
  } catch {
    return new Response("Expected JSON with courseId and content.", { status: 400 });
  }
  const courseId = body.courseId;
  const content = body.content?.trim() ?? "";
  if (!courseId) return new Response("courseId is required.", { status: 400 });
  if (!content) return new Response("content is required.", { status: 400 });

  let user: StudioMessage | undefined;
  try {
    const turn = await api<{
      wrote: boolean;
      handled?: boolean;
      user?: StudioMessage;
      assistant?: StudioMessage;
      course?: unknown;
    }>(`/studio/courses/${courseId}/turns`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
    user = turn.user;
    if (turn.handled && turn.user && turn.assistant) {
      return Response.json({
        user: turn.user,
        assistant: turn.assistant,
        course: turn.course,
        wrote: false,
        handled: true,
      });
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not read that message.";
    return new Response(message, { status: 502 });
  }

  if (!process.env.OPENAI_API_KEY?.trim()) {
    try {
      const drafted = await api<{ assistant: StudioMessage; course?: unknown }>(
        `/studio/courses/${courseId}/fallback`,
        {
          method: "POST",
          body: JSON.stringify({ content }),
        },
      );
      return Response.json({
        user,
        assistant: drafted.assistant,
        course: drafted.course,
        wrote: false,
        handled: true,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not draft that reply.";
      return new Response(message, { status: 502 });
    }
  }

  let bundle: PromptBundle;
  let history: StudioMessage[];
  try {
    bundle = await api<PromptBundle>(`/studio/courses/${courseId}/prompt`);
    history = await api<StudioMessage[]>(`/studio/courses/${courseId}/messages`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the course.";
    return new Response(message, { status: 502 });
  }

  if (!ALLOWED_MODELS.has(bundle.model)) {
    return new Response("That CreateCourse model is not allowed.", { status: 422 });
  }

  const uiMessages: UIMessage[] = history.map((message) => ({
    id: message.id,
    role: message.role,
    parts: [{ type: "text", text: message.content }],
  }));
  const modelMessages = await convertToModelMessages(uiMessages);

  let assistantText = "";
  let proposal: { operations: unknown[] } | null = null;
  let assistant: StudioMessage | null = null;
  let note = "";

  for (let attempt = 0; attempt < 2 && !assistant; attempt++) {
    let output: CourseEdit;
    try {
      const result = streamText({
        model: openai(bundle.model),
        output: Output.object({
          schema: jsonSchema(bundle.response_schema),
          name: "course_edit",
          description: "A reply and an optional typed patch addressed by code. No web search.",
        }),
        instructions: note ? `${bundle.system_prompt}\n${note}` : bundle.system_prompt,
        messages: modelMessages,
        temperature: bundle.temperature,
      });
      output = (await result.output) as CourseEdit;
    } catch (error) {
      const decision = settleModelResult({
        attempt,
        failure: error instanceof Error ? error.message : "The model did not answer.",
        kind: "schema",
        reply: "",
        operations: [],
      });
      if (decision.action === "retry") {
        note = decision.note;
        continue;
      }
      return new Response(decision.action === "banner" ? decision.text : plainFailure(error), { status: 502 });
    }

    const reply = typeof output.reply === "string" ? output.reply : "";
    const operations = output.patch && Array.isArray(output.patch.operations) ? output.patch.operations : [];
    const decision = settleModelResult({
      attempt,
      failure: null,
      kind: null,
      reply,
      operations,
    });
    if (decision.action !== "save") {
      return new Response("The model reply could not be read.", { status: 502 });
    }
    assistantText = replyIfUnwritten(decision.text);
    proposal = decision.proposal;
    if (!proposal) break;

    const saved = await fetch(`${apiBase()}/studio/courses/${courseId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role: "assistant", content: assistantText, proposal }),
      cache: "no-store",
    });
    const savedBody = await readBody(saved);
    if (saved.ok) {
      assistant = savedBody as StudioMessage;
      break;
    }
    const failureKind = saved.status === 422 ? "checker" : "transport";
    const failed = settleModelResult({
      attempt,
      failure: detailFrom(savedBody, saved.status === 422 ? "That change was rejected." : "Could not save the reply."),
      kind: failureKind,
      reply: assistantText,
      operations,
    });
    if (failed.action === "retry") {
      note = failed.note;
      proposal = null;
      continue;
    }
    if (failed.action === "banner") {
      return new Response(failed.text, { status: 502 });
    }
    assistantText = failed.text;
    proposal = null;
    break;
  }

  if (!assistant) {
    try {
      assistant = await api<StudioMessage>(`/studio/courses/${courseId}/messages`, {
        method: "POST",
        body: JSON.stringify({ role: "assistant", content: assistantText }),
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not save the reply.";
      return new Response(message, { status: 502 });
    }
  }

  let course: unknown = null;
  try {
    course = await api(`/studio/courses/${courseId}`);
  } catch {
    course = null;
  }
  return Response.json({ user, assistant, course, wrote: false });
}
```

Source file `apps/web/lib/studio-chat.ts`:

```typescript
/** Chat-route policy: one retry, then a plain sentence. No model call lives here. */

export type FailureKind = "schema" | "checker" | "transport";

export type SettleResult =
  | { action: "retry"; note: string }
  | { action: "banner"; text: string }
  | { action: "save"; text: string; proposal: { operations: unknown[] } | null };

export function rejectionReply(reason: string): string {
  return reason.trim();
}

export function detailFrom(body: unknown, fallback: string): string {
  if (typeof body === "string" && body.trim()) return body.trim();
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
  }
  return fallback;
}

export function plainFailure(error: unknown): string {
  const raw = error instanceof Error ? error.message : typeof error === "string" ? error : "";
  const collapsed = raw.replace(/\s+/g, " ").trim();
  if (!collapsed || collapsed.length > 180 || /[{[`]|schema|json/i.test(collapsed)) {
    return "The model reply could not be read.";
  }
  return collapsed.endsWith(".") ? collapsed : `${collapsed}.`;
}

export function retryNote(reason: string): string {
  return `The previous reply was rejected. ${reason.trim()} Send a patch that fixes this. Do not say the course was saved.`;
}

export function replyIfUnwritten(text: string): string {
  if (/\b(i['’]ve added|i have added|i added|added the quests|now in the course)\b/i.test(text)) {
    return "Those quests are not in the course yet.";
  }
  const trimmed = text.trim();
  return trimmed || "Those quests are not in the course yet.";
}

export function settleModelResult(input: {
  attempt: number;
  failure: string | null;
  kind: FailureKind | null;
  reply: string;
  operations: unknown[];
}): SettleResult {
  if (input.failure) {
    const sentence =
      input.kind === "schema" ? plainFailure(input.failure) : rejectionReply(input.failure);
    if (input.kind === "transport") return { action: "banner", text: sentence };
    if (input.attempt < 1) return { action: "retry", note: retryNote(sentence) };
    if (input.kind === "schema") return { action: "banner", text: sentence };
    return { action: "save", text: sentence, proposal: null };
  }
  const proposal = input.operations.length > 0 ? { operations: input.operations } : null;
  const text =
    input.reply.trim() ||
    (proposal
      ? "Here is a draft. Click Push draft to Tree when you want it in the course."
      : "I don't have a change for the course yet.");
  return { action: "save", text, proposal };
}
```

Source file `apps/web/lib/studio-build.ts`:

```typescript
export function bulkPrompt(phase: "goals" | "close", codes: string[]): string {
  const listed = codes.join(", ");
  if (phase === "goals") {
    return `Offer a learning goal for each open quest, addressed by that quest's code. A quest can hold several goals, and each goal needs its own success criterion. Draft a criterion whenever you draft a goal. Codes still open in this phase: ${listed}. Do not fill close style in this patch.`;
  }
  return `Offer quest-close choices for each open quest, addressed by that quest's code. Codes still open in this phase: ${listed}.`;
}
```

Source file `apps/api/app/course_io.py`:

```python
"""Validate, import, and export one Tier 1 course file."""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.blocks import normalize_hints, normalize_quiz, normalize_rows
from app.models import (
    AGE_BANDS,
    BEAT_ROLES,
    QUEST_TYPES,
    Beat,
    BeatResult,
    Course,
    Quest,
    QuestClose,
    QuestGoal,
    Session as TutorSession,
)

BLOOM_LEVELS = {"remember", "understand", "apply", "analyze", "evaluate", "create"}
LOADS = {"low", "medium", "high"}
WIDGET_TYPES = {"single", "multi", "flaw", "order"}
TYPED_ROLES = {"engage", "name", "teach_back"}
ROLE_ORDER = {role: index for index, role in enumerate(BEAT_ROLES)}
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,39}$")


class CourseFileError(Exception):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CourseFileError(field, "is required")
    return value.strip()


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?]", text))


def _as_list(value, field: str) -> list:
    if not isinstance(value, list):
        raise CourseFileError(field, "must be a list")
    return value


def normalize_goal(value, field: str) -> str:
    goal = _text(value, field)
    if _sentence_count(goal) != 1:
        raise CourseFileError(field, "must be one sentence")
    return goal


def normalize_criterion(raw, field: str) -> list[dict]:
    if not isinstance(raw, list):
        raise CourseFileError(field, "must be a list")
    rows = normalize_rows(raw)
    if not 2 <= len(rows) <= 3:
        raise CourseFileError(field, "needs two or three rows")
    if sum(row["weight"] for row in rows) != 100:
        raise CourseFileError(field, "weights must sum to 100")
    return rows


def check_moves(moves: list[dict], *, teach_back: bool, criterion: list[dict], field: str = "beats") -> None:
    if not moves:
        raise CourseFileError(field, "needs at least one move")
    if len(moves) > 6:
        raise CourseFileError(field, "needs at most six moves")
    ranks = [ROLE_ORDER[move["role"]] for move in moves]
    if ranks != sorted(ranks):
        raise CourseFileError(field, "must stay in cycle order")
    teach_indexes = [index for index, move in enumerate(moves) if move["role"] == "teach_back"]
    if teach_back and not teach_indexes:
        raise CourseFileError("requires_teach_back", "needs a teach-back move")
    if teach_indexes and not teach_back:
        raise CourseFileError(
            f"{field}[{teach_indexes[0]}].role",
            "teach-back is only for a quest that must explain",
        )
    if len(teach_indexes) > 1 or (teach_indexes and teach_indexes != [len(moves) - 1]):
        raise CourseFileError(f"{field}[{teach_indexes[0]}].role", "teach-back must be the last move")
    show_indexes = [index for index, move in enumerate(moves) if move["role"] == "show"]
    if not show_indexes:
        raise CourseFileError(field, "needs a show move for the success criterion")
    criterion_key = [(row["id"], row["text"], row["weight"]) for row in criterion]
    for index in show_indexes:
        move_key = [(row["id"], row["text"], row["weight"]) for row in moves[index]["rubric"]]
        if move_key != criterion_key:
            raise CourseFileError(f"{field}[{index}].rubric", "must match the success criterion")


def validate_move(raw, field: str) -> dict:
    if not isinstance(raw, dict):
        raise CourseFileError(field, "must be an object")
    role = _text(raw.get("role"), f"{field}.role")
    if role not in BEAT_ROLES:
        raise CourseFileError(f"{field}.role", "must be engage, try, name, show, or teach_back")
    bloom = _text(raw.get("bloom_level"), f"{field}.bloom_level").lower()
    if bloom not in BLOOM_LEVELS:
        raise CourseFileError(f"{field}.bloom_level", "must be a Bloom level")
    load = _text(raw.get("cognitive_load"), f"{field}.cognitive_load").lower()
    if load not in LOADS:
        raise CourseFileError(f"{field}.cognitive_load", "must be low, medium, or high")
    prompt = _text(raw.get("prompt"), f"{field}.prompt")
    rows = normalize_rows(raw.get("rubric") or [])
    if not rows:
        raise CourseFileError(f"{field}.rubric", "needs at least one row")
    if sum(row["weight"] for row in rows) != 100:
        raise CourseFileError(f"{field}.rubric", "weights must sum to 100")
    hints = normalize_hints(raw.get("hint_ladder") or {})
    for key in ("nudge", "analogy", "scaffold"):
        if not hints[key]:
            raise CourseFileError(f"{field}.hint_ladder.{key}", "is required")
    traps_raw = _as_list(raw.get("misconception_map"), f"{field}.misconception_map")
    traps: list[dict] = []
    seen: set[str] = set()
    for index, trap in enumerate(traps_raw):
        path = f"{field}.misconception_map[{index}]"
        if not isinstance(trap, dict):
            raise CourseFileError(path, "must be an object")
        trap_id = re.sub(r"[^a-z0-9-]", "", str(trap.get("id") or f"t{index + 1}").lower())[:40] or f"t{index + 1}"
        while trap_id in seen:
            trap_id = f"{trap_id}-{index + 1}"
        seen.add(trap_id)
        text = _text(trap.get("trap"), f"{path}.trap")
        note = _text(trap.get("note"), f"{path}.note")
        traps.append({"id": trap_id, "trap": text, "note": note})
    if not traps:
        raise CourseFileError(f"{field}.misconception_map", "needs at least one trap")
    widget = raw.get("widget")
    if role in TYPED_ROLES:
        if widget not in (None, {}):
            raise CourseFileError(f"{field}.widget", "must be empty on this move")
        widget = None
    if widget:
        try:
            widget = normalize_quiz(widget)
        except HTTPException as exc:
            raise CourseFileError(f"{field}.widget", str(exc.detail)) from exc
        if widget["type"] not in WIDGET_TYPES:
            raise CourseFileError(f"{field}.widget.type", "must be single, multi, flaw, or order")
    return {
        "role": role,
        "bloom_level": bloom,
        "cognitive_load": load,
        "prompt": prompt,
        "rubric": rows,
        "misconception_map": traps,
        "hint_ladder": hints,
        "widget": widget,
    }


def _validate_legacy(payload) -> dict:
    if not isinstance(payload, dict):
        raise CourseFileError("course", "must be an object")
    code = _text(payload.get("code"), "code")
    if not CODE_RE.match(code):
        raise CourseFileError("code", "must be letters, numbers, hyphens, and dots")
    title = _text(payload.get("title"), "title")
    age_band = _text(payload.get("age_band"), "age_band")
    if age_band not in AGE_BANDS:
        raise CourseFileError("age_band", "must be 6-8, 9-11, 12-14, or 15-17")
    standards = _text(payload.get("standards_alignment"), "standards_alignment")
    dictionary = _as_list(payload.get("competency_dictionary"), "competency_dictionary")
    competencies: list[dict] = []
    tags: set[str] = set()
    for index, item in enumerate(dictionary):
        path = f"competency_dictionary[{index}]"
        if not isinstance(item, dict):
            raise CourseFileError(path, "must be an object")
        tag = _text(item.get("code"), f"{path}.code")
        if not CODE_RE.match(tag):
            raise CourseFileError(f"{path}.code", "must be letters, numbers, hyphens, and dots")
        if tag in tags:
            raise CourseFileError(f"{path}.code", "is duplicated")
        tags.add(tag)
        competencies.append({"code": tag, "description": _text(item.get("description"), f"{path}.description")})
    units_raw = _as_list(payload.get("units"), "units")
    if not units_raw:
        raise CourseFileError("units", "needs at least one unit")
    units: list[dict] = []
    numbers: set[int] = set()
    quest_codes: list[str] = []
    for unit_index, raw_unit in enumerate(units_raw):
        path = f"units[{unit_index}]"
        if not isinstance(raw_unit, dict):
            raise CourseFileError(path, "must be an object")
        number = raw_unit.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise CourseFileError(f"{path}.number", "must be a positive integer")
        if number in numbers:
            raise CourseFileError(f"{path}.number", "is duplicated")
        numbers.add(number)
        continuity = _text(raw_unit.get("continuity_summary"), f"{path}.continuity_summary")
        if _sentence_count(continuity) < 2:
            raise CourseFileError(f"{path}.continuity_summary", "must be two sentences")
        quests_raw = _as_list(raw_unit.get("quests"), f"{path}.quests")
        if not quests_raw:
            raise CourseFileError(f"{path}.quests", "needs at least one quest")
        quests: list[dict] = []
        for quest_index, raw_quest in enumerate(quests_raw):
            qpath = f"{path}.quests[{quest_index}]"
            if not isinstance(raw_quest, dict):
                raise CourseFileError(qpath, "must be an object")
            quest_code = _text(raw_quest.get("code"), f"{qpath}.code")
            if not CODE_RE.match(quest_code):
                raise CourseFileError(f"{qpath}.code", "must be letters, numbers, and hyphens")
            if quest_code in quest_codes:
                raise CourseFileError(f"{qpath}.code", "is duplicated")
            quest_codes.append(quest_code)
            quest_type = _text(raw_quest.get("quest_type"), f"{qpath}.quest_type")
            if quest_type not in QUEST_TYPES:
                raise CourseFileError(f"{qpath}.quest_type", "must be core, branch, or capstone")
            prereqs_raw = _as_list(raw_quest.get("prerequisite_codes"), f"{qpath}.prerequisite_codes")
            prereqs = []
            for pre_index, prereq in enumerate(prereqs_raw):
                pre = _text(prereq, f"{qpath}.prerequisite_codes[{pre_index}]")
                if pre == quest_code:
                    raise CourseFileError(f"{qpath}.prerequisite_codes[{pre_index}]", "cannot be the quest itself")
                prereqs.append(pre)
            tag_raw = _as_list(raw_quest.get("competency_tags"), f"{qpath}.competency_tags")
            if not 1 <= len(tag_raw) <= 2:
                raise CourseFileError(f"{qpath}.competency_tags", "needs one or two tags")
            quest_tags = []
            for tag_index, tag in enumerate(tag_raw):
                cleaned = _text(tag, f"{qpath}.competency_tags[{tag_index}]")
                if cleaned not in tags:
                    raise CourseFileError(
                        f"{qpath}.competency_tags[{tag_index}]",
                        "is not in the competency dictionary",
                    )
                quest_tags.append(cleaned)
            goal = normalize_goal(raw_quest.get("learning_goal"), f"{qpath}.learning_goal")
            criterion = normalize_criterion(raw_quest.get("success_criterion"), f"{qpath}.success_criterion")
            teach_back = raw_quest.get("requires_teach_back")
            if not isinstance(teach_back, bool):
                raise CourseFileError(f"{qpath}.requires_teach_back", "must be true or false")
            beats_raw = _as_list(raw_quest.get("beats"), f"{qpath}.beats")
            beats = [
                validate_move(beat, f"{qpath}.beats[{index}]")
                for index, beat in enumerate(beats_raw)
            ]
            check_moves(
                beats,
                teach_back=teach_back,
                criterion=criterion,
                field=f"{qpath}.beats",
            )
            quests.append(
                {
                    "code": quest_code,
                    "title": _text(raw_quest.get("title"), f"{qpath}.title"),
                    "quest_type": quest_type,
                    "prerequisite_codes": prereqs,
                    "competency_tags": quest_tags,
                    "dinner_prompt": _text(raw_quest.get("dinner_prompt"), f"{qpath}.dinner_prompt"),
                    "learning_goal": goal,
                    "success_criterion": criterion,
                    "requires_teach_back": teach_back,
                    "beats": beats,
                }
            )
        units.append(
            {
                "number": number,
                "title": _text(raw_unit.get("title"), f"{path}.title"),
                "enduring_understanding": _text(
                    raw_unit.get("enduring_understanding"), f"{path}.enduring_understanding"
                ),
                "continuity_summary": continuity,
                "is_diagnostic": bool(raw_unit.get("is_diagnostic")),
                "is_capstone": bool(raw_unit.get("is_capstone")),
                "quests": quests,
            }
        )
    known = set(quest_codes)
    for unit_index, unit_body in enumerate(units):
        for quest_index, quest_body in enumerate(unit_body["quests"]):
            for pre_index, prereq in enumerate(quest_body["prerequisite_codes"]):
                if prereq not in known:
                    raise CourseFileError(
                        f"units[{unit_index}].quests[{quest_index}].prerequisite_codes[{pre_index}]",
                        "does not match a quest in this course",
                    )
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "standards_alignment": standards,
        "competency_dictionary": competencies,
        "units": units,
    }


CLOSE_KINDS = ("essay", "single", "multi", "none")
QUIZ_MINUTES = (2, 5, 10)


def goals_from_points(learning_goal: str, criterion: list) -> list[dict]:
    """One goal per criterion point. The quest sentence stays on the first goal."""
    texts = []
    for row in criterion or []:
        if isinstance(row, dict) and str(row.get("text") or "").strip():
            texts.append(str(row["text"]).strip())
    goal = (learning_goal or "").strip()
    if not texts:
        text = goal or "States the idea."
        return [{"position": 1, "learning_goal": goal or text, "success_criterion": text}]
    goals = [{"position": 1, "learning_goal": goal or texts[0], "success_criterion": texts[0]}]
    for index, text in enumerate(texts[1:], start=2):
        goals.append({"position": index, "learning_goal": text, "success_criterion": text})
    return goals


def close_from_beats(beats: list[dict]) -> dict:
    """The show move becomes an essay, a single choice, a multi-choice, or no questions."""
    show = next((beat for beat in beats if beat.get("role") == "show"), None)
    widget = show.get("widget") if isinstance(show, dict) else None
    prompt = str((show or {}).get("prompt") or "").strip()
    if not isinstance(widget, dict):
        if "?" in prompt:
            return {"kind": "essay", "question": prompt, "items": []}
        return {"kind": "none", "question": "", "items": []}
    question = str(widget.get("prompt") or prompt).strip()
    choices = widget.get("choices") if isinstance(widget.get("choices"), list) else []
    answer = widget.get("answer")
    kind = widget.get("type")
    if kind in {"single", "flaw", "multi"}:
        answers = set(answer if isinstance(answer, list) else [answer])
        items = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            text = str(choice.get("text") or "").strip()
            if not text:
                continue
            items.append({"text": text, "correct": choice.get("id") in answers})
        return {"kind": "multi" if kind == "multi" else "single", "question": question, "items": items}
    if question:
        return {"kind": "essay", "question": question, "items": []}
    return {"kind": "none", "question": "", "items": []}


def _preferred_goal_count(quests: list[dict]) -> int:
    counts = [max(1, len(quest.get("goals") or [])) for quest in quests]
    if not counts:
        return 1
    tally: dict[int, int] = {}
    for count in counts:
        tally[count] = tally.get(count, 0) + 1
    return max(tally, key=lambda count: (tally[count], count))


def _flatten(normalized: dict) -> dict:
    quests = []
    for unit in normalized["units"]:
        for quest in unit["quests"]:
            body = dict(quest)
            body["goals"] = goals_from_points(quest["learning_goal"], quest["success_criterion"])
            body["close"] = close_from_beats(quest["beats"])
            quests.append(body)
    for index, quest in enumerate(quests, start=1):
        quest["position"] = index
    audience = normalized["age_band"]
    return {
        "code": normalized["code"],
        "title": normalized["title"],
        "age_band": audience,
        "standards_alignment": normalized["standards_alignment"],
        "competency_dictionary": normalized["competency_dictionary"],
        "description": normalized["standards_alignment"],
        "audience": audience,
        "quest_count": len(quests) or 1,
        "goals_per_quest": _preferred_goal_count(quests),
        "quiz_minutes": 5,
        "quests": quests,
    }


def _header(payload: dict) -> dict:
    code = _text(payload.get("code"), "code")
    if not CODE_RE.match(code):
        raise CourseFileError("code", "must be letters, numbers, hyphens, and dots")
    title = _text(payload.get("title"), "title")
    age_band = _text(payload.get("age_band"), "age_band")
    if age_band not in AGE_BANDS:
        raise CourseFileError("age_band", "must be 6-8, 9-11, 12-14, or 15-17")
    audience = payload.get("audience") or age_band
    if audience not in AGE_BANDS:
        raise CourseFileError("audience", "must be 6-8, 9-11, 12-14, or 15-17")
    standards = payload.get("standards_alignment")
    if not isinstance(standards, str) or not standards.strip():
        standards = title
    else:
        standards = standards.strip()
    description = payload.get("description")
    if not isinstance(description, str):
        description = ""
    quiz_minutes = payload.get("quiz_minutes", 5)
    if quiz_minutes not in QUIZ_MINUTES:
        raise CourseFileError("quiz_minutes", "must be 2, 5, or 10")
    quest_count = payload.get("quest_count")
    if isinstance(quest_count, bool) or not isinstance(quest_count, int) or quest_count < 1:
        quest_count = None
    goals_per_quest = payload.get("goals_per_quest")
    if isinstance(goals_per_quest, bool) or not isinstance(goals_per_quest, int) or goals_per_quest < 1:
        goals_per_quest = None
    dictionary = _as_list(payload.get("competency_dictionary") or [], "competency_dictionary")
    competencies: list[dict] = []
    tags: set[str] = set()
    for index, item in enumerate(dictionary):
        path = f"competency_dictionary[{index}]"
        if not isinstance(item, dict):
            raise CourseFileError(path, "must be an object")
        tag = _text(item.get("code"), f"{path}.code")
        if not CODE_RE.match(tag):
            raise CourseFileError(f"{path}.code", "must be letters, numbers, hyphens, and dots")
        if tag in tags:
            raise CourseFileError(f"{path}.code", "is duplicated")
        tags.add(tag)
        competencies.append({"code": tag, "description": _text(item.get("description"), f"{path}.description")})
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "audience": audience,
        "standards_alignment": standards,
        "description": description.strip(),
        "quiz_minutes": quiz_minutes,
        "quest_count": quest_count,
        "goals_per_quest": goals_per_quest,
        "competency_dictionary": competencies,
        "tags": tags,
    }


def _validate_goals(raw, field: str) -> list[dict]:
    rows = _as_list(raw, field)
    if not rows:
        raise CourseFileError(field, "needs at least one goal")
    goals = []
    for index, item in enumerate(rows, start=1):
        path = f"{field}[{index - 1}]"
        if not isinstance(item, dict):
            raise CourseFileError(path, "must be an object")
        learning_goal = _text(item.get("learning_goal"), f"{path}.learning_goal")
        criterion = _text(item.get("success_criterion"), f"{path}.success_criterion")
        goals.append({"position": index, "learning_goal": learning_goal, "success_criterion": criterion})
    return goals


def _validate_close(raw, field: str) -> dict:
    if not isinstance(raw, dict):
        raise CourseFileError(field, "must say how the quest closes")
    kind = raw.get("kind")
    if kind not in CLOSE_KINDS:
        raise CourseFileError(f"{field}.kind", "must be essay, single, multi, or none")
    question = raw.get("question") or ""
    if not isinstance(question, str):
        raise CourseFileError(f"{field}.question", "must be text")
    items_raw = raw.get("items") or []
    if not isinstance(items_raw, list):
        raise CourseFileError(f"{field}.items", "must be a list")
    items = []
    for index, item in enumerate(items_raw):
        if isinstance(item, str) and item.strip():
            items.append({"text": item.strip(), "correct": False})
            continue
        if not isinstance(item, dict) or not str(item.get("text") or "").strip():
            raise CourseFileError(f"{field}.items[{index}]", "each choice needs text")
        items.append({"text": str(item["text"]).strip(), "correct": item.get("correct") is True})
    if kind in {"single", "multi"} and len(items) < 2:
        raise CourseFileError(f"{field}.items", "needs two choices")
    if kind in {"essay", "none"}:
        items = []
    if kind == "none":
        question = ""
    return {"kind": kind, "question": question.strip(), "items": items}


def _validate_catalog(payload: dict) -> dict:
    header = _header(payload)
    tags = header.pop("tags")
    quests_raw = _as_list(payload.get("quests"), "quests")
    quests = []
    quest_codes: list[str] = []
    for index, raw in enumerate(quests_raw):
        path = f"quests[{index}]"
        if not isinstance(raw, dict):
            raise CourseFileError(path, "must be an object")
        quest_code = _text(raw.get("code"), f"{path}.code")
        if not CODE_RE.match(quest_code):
            raise CourseFileError(f"{path}.code", "must be letters, numbers, and hyphens")
        if quest_code in quest_codes:
            raise CourseFileError(f"{path}.code", "is duplicated")
        quest_codes.append(quest_code)
        quest_type = _text(raw.get("quest_type") or "core", f"{path}.quest_type")
        if quest_type not in QUEST_TYPES:
            raise CourseFileError(f"{path}.quest_type", "must be core, branch, or capstone")
        prereqs_raw = _as_list(raw.get("prerequisite_codes") or [], f"{path}.prerequisite_codes")
        prereqs = []
        for pre_index, prereq in enumerate(prereqs_raw):
            pre = _text(prereq, f"{path}.prerequisite_codes[{pre_index}]")
            if pre == quest_code:
                raise CourseFileError(f"{path}.prerequisite_codes[{pre_index}]", "cannot be the quest itself")
            prereqs.append(pre)
        tag_raw = _as_list(raw.get("competency_tags") or [], f"{path}.competency_tags")
        quest_tags = []
        for tag_index, tag in enumerate(tag_raw):
            cleaned = _text(tag, f"{path}.competency_tags[{tag_index}]")
            if tags and cleaned not in tags:
                raise CourseFileError(
                    f"{path}.competency_tags[{tag_index}]",
                    "is not in the competency dictionary",
                )
            if not tags:
                raise CourseFileError(f"{path}.competency_tags[{tag_index}]", "is not in the competency dictionary")
            quest_tags.append(cleaned)
        goal = _text(raw.get("learning_goal"), f"{path}.learning_goal")
        criterion = normalize_rows(raw.get("success_criterion") or [])
        if not criterion:
            raise CourseFileError(f"{path}.success_criterion", "needs at least one row")
        if sum(row["weight"] for row in criterion) != 100:
            raise CourseFileError(f"{path}.success_criterion", "weights must sum to 100")
        teach_back = raw.get("requires_teach_back")
        if not isinstance(teach_back, bool):
            teach_back = False
        beats_raw = _as_list(raw.get("beats"), f"{path}.beats")
        beats = [validate_move(beat, f"{path}.beats[{beat_index}]") for beat_index, beat in enumerate(beats_raw)]
        check_moves(beats, teach_back=teach_back, criterion=criterion, field=f"{path}.beats")
        goals = _validate_goals(raw.get("goals"), f"{path}.goals")
        close = _validate_close(raw.get("close"), f"{path}.close")
        dinner = raw.get("dinner_prompt") or raw.get("title") or quest_code
        quests.append(
            {
                "code": quest_code,
                "title": _text(raw.get("title"), f"{path}.title"),
                "quest_type": quest_type,
                "prerequisite_codes": prereqs,
                "competency_tags": quest_tags,
                "dinner_prompt": _text(dinner, f"{path}.dinner_prompt"),
                "learning_goal": goal,
                "success_criterion": criterion,
                "requires_teach_back": teach_back,
                "beats": beats,
                "goals": goals,
                "close": close,
                "position": index + 1,
            }
        )
    known = set(quest_codes)
    for index, quest in enumerate(quests):
        for pre_index, prereq in enumerate(quest["prerequisite_codes"]):
            if prereq not in known:
                raise CourseFileError(
                    f"quests[{index}].prerequisite_codes[{pre_index}]",
                    "does not match a quest in this course",
                )
    header["quest_count"] = header["quest_count"] or len(quests) or 1
    header["goals_per_quest"] = header["goals_per_quest"] or _preferred_goal_count(quests)
    header["quests"] = quests
    return header


def validate_course(payload) -> dict:
    if not isinstance(payload, dict):
        raise CourseFileError("course", "must be an object")
    if "units" in payload and "quests" not in payload:
        return _flatten(_validate_legacy(payload))
    return _validate_catalog(payload)


def _quest_fields(quest: Quest) -> dict:
    return {
        "code": quest.code,
        "title": quest.title,
        "quest_type": quest.quest_type,
        "prerequisite_codes": list(quest.prerequisite_codes or []),
        "competency_tags": list(quest.competency_tags or []),
        "dinner_prompt": quest.dinner_prompt,
        "learning_goal": quest.learning_goal,
        "success_criterion": copy.deepcopy(quest.success_criterion or []),
        "requires_teach_back": bool(quest.requires_teach_back),
        "goals": [
            {
                "position": goal.position,
                "learning_goal": goal.learning_goal,
                "success_criterion": goal.success_criterion,
            }
            for goal in sorted(quest.goals, key=lambda item: item.position)
        ],
        "close": {
            "kind": quest.close.kind,
            "question": quest.close.question,
            "items": copy.deepcopy(quest.close.items or []),
        }
        if quest.close is not None
        else {"kind": "none", "question": "", "items": []},
        "beats": [
            {
                "role": beat.role,
                "bloom_level": beat.bloom_level,
                "cognitive_load": beat.cognitive_load,
                "prompt": beat.prompt,
                "rubric": copy.deepcopy(beat.rubric or []),
                "misconception_map": copy.deepcopy(beat.misconception_map or []),
                "hint_ladder": copy.deepcopy(beat.hint_ladder or {}),
                "widget": copy.deepcopy(beat.widget) if beat.widget else None,
            }
            for beat in sorted(quest.beats, key=lambda item: item.position)
        ],
    }


def export_course(course: Course) -> dict:
    return {
        "code": course.code,
        "title": course.title,
        "age_band": course.age_band,
        "standards_alignment": course.standards_alignment,
        "competency_dictionary": copy.deepcopy(course.competency_dictionary or []),
        "description": course.description or "",
        "audience": course.audience or course.age_band,
        "quest_count": course.quest_count,
        "goals_per_quest": course.goals_per_quest,
        "quiz_minutes": course.quiz_minutes,
        "quests": [
            _quest_fields(quest)
            for quest in sorted(course.quests, key=lambda item: item.position)
        ],
    }


def _apply_course_fields(course: Course, payload: dict) -> None:
    course.code = payload["code"]
    course.title = payload["title"]
    course.age_band = payload["age_band"]
    course.standards_alignment = payload["standards_alignment"]
    course.competency_dictionary = payload["competency_dictionary"]
    course.description = payload.get("description") or ""
    course.audience = payload.get("audience") or payload["age_band"]
    course.quest_count = int(payload.get("quest_count") or len(payload["quests"]) or 1)
    course.goals_per_quest = int(payload.get("goals_per_quest") or 1)
    course.quiz_minutes = int(payload.get("quiz_minutes") or 5)
    course.updated_at = datetime.now(timezone.utc)


def _append_quest(course: Course, body: dict, position: int) -> Quest:
    quest = Quest(
        code=body["code"],
        title=body["title"],
        quest_type=body["quest_type"],
        prerequisite_codes=body["prerequisite_codes"],
        competency_tags=body["competency_tags"],
        dinner_prompt=body["dinner_prompt"],
        learning_goal=body["learning_goal"],
        success_criterion=body["success_criterion"],
        requires_teach_back=body["requires_teach_back"],
        position=position,
    )
    course.quests.append(quest)
    for beat_position, beat_body in enumerate(body["beats"], start=1):
        quest.beats.append(
            Beat(
                position=beat_position,
                role=beat_body["role"],
                bloom_level=beat_body["bloom_level"],
                cognitive_load=beat_body["cognitive_load"],
                prompt=beat_body["prompt"],
                rubric=beat_body["rubric"],
                misconception_map=beat_body["misconception_map"],
                hint_ladder=beat_body["hint_ladder"],
                widget=beat_body["widget"],
            )
        )
    for goal in body["goals"]:
        quest.goals.append(
            QuestGoal(
                position=goal["position"],
                learning_goal=goal["learning_goal"],
                success_criterion=goal["success_criterion"],
            )
        )
    close = body["close"]
    quest.close = QuestClose(kind=close["kind"], question=close["question"], items=close["items"])
    return quest


def replace_course(db: Session, payload: dict) -> Course:
    """Upload replaces the course with this code. Open classes on it are cleared."""
    normalized = validate_course(payload)
    existing = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(selectinload(Course.quests))
    )
    incoming = [quest["code"] for quest in normalized["quests"]]
    if existing is None:
        if incoming:
            taken = db.scalar(select(Quest.id).where(Quest.code.in_(incoming)))
            if taken is not None:
                raise CourseFileError("quests", "a quest code is already used by another course")
        course = Course(
            code=normalized["code"],
            title=normalized["title"],
            age_band=normalized["age_band"],
            audience=normalized["audience"],
        )
        db.add(course)
        db.flush()
        _apply_course_fields(course, normalized)
        for position, quest_body in enumerate(normalized["quests"], start=1):
            _append_quest(course, quest_body, position)
        db.flush()
        return course
    quest_ids = [quest.id for quest in existing.quests]
    if quest_ids:
        db.execute(delete(TutorSession).where(TutorSession.quest_id.in_(quest_ids)))
        db.flush()
    for quest in list(existing.quests):
        db.delete(quest)
    db.flush()
    if incoming:
        clash = db.scalar(select(Quest.id).where(Quest.code.in_(incoming)))
        if clash is not None:
            raise CourseFileError("quests", "a quest code is already used by another course")
    _apply_course_fields(existing, normalized)
    for position, quest_body in enumerate(normalized["quests"], start=1):
        _append_quest(existing, quest_body, position)
    db.flush()
    return existing


def _beats_held(db: Session, beat_ids: list) -> bool:
    if not beat_ids:
        return False
    if db.scalar(select(TutorSession.id).where(TutorSession.current_beat_id.in_(beat_ids))) is not None:
        return True
    return db.scalar(select(BeatResult.id).where(BeatResult.beat_id.in_(beat_ids))) is not None


def _fill_beat(beat: Beat, body: dict) -> None:
    beat.role = body["role"]
    beat.bloom_level = body["bloom_level"]
    beat.cognitive_load = body["cognitive_load"]
    beat.prompt = body["prompt"]
    beat.rubric = body["rubric"]
    beat.misconception_map = body["misconception_map"]
    beat.hint_ladder = body["hint_ladder"]
    beat.widget = body["widget"]


def _sync_beats(quest: Quest, beats: list[dict]) -> None:
    by_position = {beat.position: beat for beat in quest.beats}
    incoming = set(range(1, len(beats) + 1))
    for position, body in enumerate(beats, start=1):
        beat = by_position.get(position)
        if beat is None:
            beat = Beat(position=position, role=body["role"])
            quest.beats.append(beat)
        _fill_beat(beat, body)
    for beat in list(quest.beats):
        if beat.position not in incoming:
            quest.beats.remove(beat)


def _fill_quest(quest: Quest, body: dict) -> None:
    quest.title = body["title"]
    quest.quest_type = body["quest_type"]
    quest.prerequisite_codes = body["prerequisite_codes"]
    quest.competency_tags = body["competency_tags"]
    quest.dinner_prompt = body["dinner_prompt"]
    quest.learning_goal = body["learning_goal"]
    quest.success_criterion = body["success_criterion"]
    quest.requires_teach_back = body["requires_teach_back"]


def _sync_goals(quest: Quest, goals: list[dict]) -> None:
    session = object_session(quest)
    for goal in list(quest.goals):
        quest.goals.remove(goal)
    if session is not None:
        session.flush()
    for goal in goals:
        quest.goals.append(
            QuestGoal(
                position=goal["position"],
                learning_goal=goal["learning_goal"],
                success_criterion=goal["success_criterion"],
            )
        )


def _sync_close(quest: Quest, close: dict) -> None:
    row = quest.close
    if row is None:
        quest.close = QuestClose(kind=close["kind"], question=close["question"], items=close["items"])
        return
    row.kind = close["kind"]
    row.question = close["question"]
    row.items = list(close["items"])


def update_course_in_place(db: Session, payload: dict) -> Course:
    """Refresh one course without deleting classes.

    Quests match by code and moves match by position. Columns, goals, and the
    close are updated on those rows. A quest that still has a class is not dropped.
    """
    normalized = validate_course(payload)
    course = db.scalar(
        select(Course)
        .where(Course.code == normalized["code"])
        .options(
            selectinload(Course.quests).selectinload(Quest.beats),
            selectinload(Course.quests).selectinload(Quest.goals),
            selectinload(Course.quests).selectinload(Quest.close),
        )
    )
    if course is None:
        raise CourseFileError("code", "is not in the database")

    incoming_codes = [quest["code"] for quest in normalized["quests"]]
    incoming_code_set = set(incoming_codes)
    quests_by_code = {quest.code: quest for quest in course.quests}
    dropped = [quest for quest in quests_by_code.values() if quest.code not in incoming_code_set]
    if dropped:
        dropped_ids = [quest.id for quest in dropped]
        held_id = db.scalar(
            select(TutorSession.quest_id).where(TutorSession.quest_id.in_(dropped_ids))
        )
        if held_id is not None:
            code = next(quest.code for quest in dropped if quest.id == held_id)
            raise CourseFileError("quests", f"{code} still has classes, so it cannot be removed")
        dropped_beats = [beat.id for quest in dropped for beat in quest.beats]
        if _beats_held(db, dropped_beats):
            raise CourseFileError("beats", "a move still has classes, so it cannot be removed")

    for quest_body in normalized["quests"]:
        quest = quests_by_code.get(quest_body["code"])
        if quest is None:
            continue
        incoming_positions = set(range(1, len(quest_body["beats"]) + 1))
        extra_ids = [beat.id for beat in quest.beats if beat.position not in incoming_positions]
        if _beats_held(db, extra_ids):
            raise CourseFileError("beats", "a move still has classes, so it cannot be removed")

    _apply_course_fields(course, normalized)
    for quest in list(course.quests):
        if quest.code not in incoming_code_set:
            course.quests.remove(quest)
    db.flush()

    live = [quests_by_code[code] for code in incoming_codes if code in quests_by_code]
    for offset, quest in enumerate(live, start=1):
        quest.position = 10_000 + offset
    db.flush()

    for position, quest_body in enumerate(normalized["quests"], start=1):
        quest = quests_by_code.get(quest_body["code"])
        if quest is None:
            clash = db.scalar(select(Quest.id).where(Quest.code == quest_body["code"]))
            if clash is not None:
                raise CourseFileError("quests", "a quest code is already used by another course")
            quest = _append_quest(course, quest_body, position)
            quests_by_code[quest.code] = quest
            continue
        quest.position = position
        _fill_quest(quest, quest_body)
        _sync_beats(quest, quest_body["beats"])
        _sync_goals(quest, quest_body["goals"])
        _sync_close(quest, quest_body["close"])
    db.flush()
    return course


def _rubric_from_goals(goals: list[dict]) -> list[dict]:
    count = len(goals)
    if count <= 1:
        text = goals[0]["success_criterion"] if goals else "States the idea."
        return [{"id": "goal-1", "text": text, "weight": 100}]
    base = 100 // count
    leftover = 100 - base * count
    rows = []
    for index, goal in enumerate(goals, start=1):
        rows.append(
            {
                "id": f"goal-{index}",
                "text": goal["success_criterion"],
                "weight": base + (leftover if index == 1 else 0),
            }
        )
    return rows


def _widget_from_close(close: dict) -> dict | None:
    if close["kind"] not in {"single", "multi"}:
        return None
    choices = []
    answers = []
    for index, item in enumerate(close["items"], start=1):
        choice_id = f"c{index}"
        choices.append(
            {
                "id": choice_id,
                "text": item["text"],
                "misconception": "" if item.get("correct") else "That choice answers a different question.",
            }
        )
        if item.get("correct"):
            answers.append(choice_id)
    if len(choices) < 2:
        return None
    if not answers:
        answers = [choices[0]["id"]]
    kind = "multi" if close["kind"] == "multi" else "single"
    return {
        "type": kind,
        "prompt": close["question"] or "Choose the best answer.",
        "choices": choices,
        "answer": answers if kind == "multi" else answers[0],
        "explain": False,
        "misconception": "Stay on the question this quest asked.",
    }


def _beats_for_close(goals: list[dict], close: dict) -> list[dict]:
    from app.flow import blank_beats

    beats = blank_beats(_rubric_from_goals(goals))
    widget = _widget_from_close(close)
    for beat in beats:
        if beat["role"] != "show":
            continue
        if close["kind"] == "essay" and close["question"]:
            beat["prompt"] = close["question"]
        elif close["kind"] == "none":
            beat["prompt"] = "There is no closing question. The quest ends when the goals are met."
            beat["widget"] = None
        elif widget is not None:
            beat["widget"] = widget
            beat["prompt"] = close["question"] or beat["prompt"]
    return beats


def _close_from_studio_row(row) -> dict:
    if row is None:
        return {"kind": "none", "question": "", "items": []}
    stored = row.items
    choices: list = []
    questions: list = []
    selection = None
    if isinstance(stored, dict):
        choices = stored.get("choices") if isinstance(stored.get("choices"), list) else []
        questions = stored.get("questions") if isinstance(stored.get("questions"), list) else []
        if stored.get("selection") in {"single", "multi"}:
            selection = stored["selection"]
    elif isinstance(stored, list):
        choices = stored
    question = ""
    if questions and isinstance(questions[0], dict):
        question = str(questions[0].get("text") or "").strip()
    answer = row.answer_style
    if answer == "essay" and not question:
        return {"kind": "none", "question": "", "items": []}
    if answer == "essay":
        return {"kind": "essay", "question": question, "items": []}
    items = []
    for choice in choices:
        if isinstance(choice, str) and choice.strip():
            items.append({"text": choice.strip(), "correct": False})
        elif isinstance(choice, dict) and str(choice.get("text") or "").strip():
            items.append({"text": str(choice["text"]).strip(), "correct": choice.get("correct") is True})
    if len(items) < 2:
        if question:
            return {"kind": "essay", "question": question, "items": []}
        return {"kind": "none", "question": "", "items": []}
    return {
        "kind": "multi" if selection == "multi" else "single",
        "question": question or "Choose the best answer.",
        "items": items,
    }


def catalog_from_studio(studio) -> dict:
    """Copy a Create course draft into the kid-catalog shape. The draft stays put."""
    from app.studio import goal_rows, goals_per_quest_of, quest_count_of

    audience = studio.audience if studio.audience in AGE_BANDS else "9-11"
    description = (studio.theme or studio.focus or "").strip()
    standards = (studio.focus or description or studio.title or "").strip() or studio.title
    quests = []
    for source in sorted(studio.quests, key=lambda item: (item.position, item.code)):
        rows = goal_rows(source)
        if not rows:
            rows = [{"learning_goal": source.title, "success_criterion": source.title}]
        goals = []
        for index, row in enumerate(rows, start=1):
            learning_goal = str(row.get("learning_goal") or "").strip() or source.title
            criterion = str(row.get("success_criterion") or "").strip() or learning_goal
            goals.append(
                {"position": index, "learning_goal": learning_goal, "success_criterion": criterion}
            )
        close = _close_from_studio_row(source.close)
        rubric = _rubric_from_goals(goals)
        quests.append(
            {
                "code": source.code,
                "title": source.title,
                "quest_type": "core",
                "prerequisite_codes": [],
                "competency_tags": [],
                "dinner_prompt": source.title,
                "learning_goal": goals[0]["learning_goal"],
                "success_criterion": rubric,
                "requires_teach_back": False,
                "beats": _beats_for_close(goals, close),
                "goals": goals,
                "close": close,
            }
        )
    return {
        "code": studio.code,
        "title": studio.title,
        "age_band": audience,
        "standards_alignment": standards,
        "competency_dictionary": [],
        "description": description,
        "audience": audience,
        "quest_count": quest_count_of(studio),
        "goals_per_quest": goals_per_quest_of(studio),
        "quiz_minutes": studio.quiz_minutes if studio.quiz_minutes in QUIZ_MINUTES else 5,
        "quests": quests,
    }


def copy_studio_into_catalog(db: Session, studio_id) -> Course:
    from app.studio import load_course as load_studio

    studio = load_studio(db, studio_id)
    if studio is None:
        raise CourseFileError("studio_course_id", "is not a Create course draft")
    payload = catalog_from_studio(studio)
    existing = db.scalar(select(Course.id).where(Course.code == payload["code"]))
    if existing is None:
        course = replace_course(db, payload)
    else:
        course = update_course_in_place(db, payload)
    course.in_catalog = True
    course.updated_at = datetime.now(timezone.utc)
    db.flush()
    return course
```

Source file `apps/api/app/routes/catalog.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.course_io import (
    CourseFileError,
    check_moves,
    copy_studio_into_catalog,
    export_course,
    normalize_criterion,
    normalize_goal,
    replace_course,
    validate_move,
)
from app.database import get_db
from app.engine.defaults import profile_for_age
from app.flow import apply_student_profile, now, unique_course_code, unique_student_slug
from app.models import (
    AGE_BANDS,
    Beat,
    Course,
    Quest,
    Session as TutorSession,
    Student,
)
from app.present import course_summary, course_tree, quest_detail, quest_list_item, student_out
from app.queries import load_course, load_quest, quest_in_use
from app.schemas import (
    BeatWrite,
    CourseCreate,
    CoursePatch,
    CourseSummary,
    CourseTree,
    StudioImportIn,
    ProfileDefaults,
    QuestDetail,
    QuestListItem,
    QuestPatch,
    StudentCreate,
    StudentOut,
    StudentPatch,
)

router = APIRouter()

ROSTER = ["iron-man", "storm", "spider-man", "wolverine"]


def _provided(body) -> set[str]:
    return set(body.model_fields_set)


def _clean_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    return [item.strip() for item in values if item and item.strip()]


@router.get("/profile-defaults", response_model=ProfileDefaults)
def profile_defaults(age: int) -> ProfileDefaults:
    if age < 4 or age > 18:
        raise HTTPException(status_code=422, detail="Age must be from 4 to 18")
    profile = profile_for_age(age)
    return ProfileDefaults(
        age_band=profile.age_band,
        reading_level=profile.reading_level,
        modality=profile.modality,
        interests=[],
        tutor_persona=profile.persona,
        tutor_lexicon=profile.lexicon,
        tutor_metaphors=profile.metaphors,
        tutor_sidekick=profile.sidekick,
        tutor_socratic_strictness=profile.socratic_strictness,
        tutor_struggle_window=profile.struggle_window,
        tutor_anti_spoiler=profile.anti_spoiler,
        tutor_pacing=profile.pacing,
    )


@router.get("/students", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db)) -> list[StudentOut]:
    students = list(db.scalars(select(Student)).all())
    students.sort(
        key=lambda student: (
            ROSTER.index(student.slug) if student.slug in ROSTER else len(ROSTER),
            student.display_name.lower(),
        )
    )
    return [student_out(student) for student in students]


@router.post("/students", response_model=StudentOut)
def create_student(body: StudentCreate, db: Session = Depends(get_db)) -> StudentOut:
    name = body.display_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name is required")
    student = Student(slug=unique_student_slug(db, name), display_name=name, age=body.age)
    provided = _provided(body)
    if "reading_level" in provided and body.reading_level is not None:
        student.reading_level = body.reading_level.strip()
    if "modality" in provided and body.modality is not None:
        student.modality = body.modality.strip()
    if "interests" in provided:
        student.interests = _clean_list(body.interests)
    if "tutor_persona" in provided and body.tutor_persona is not None:
        student.tutor_persona = body.tutor_persona.strip()
    if "tutor_lexicon" in provided and body.tutor_lexicon is not None:
        student.tutor_lexicon = body.tutor_lexicon.strip()
    if "tutor_metaphors" in provided and body.tutor_metaphors is not None:
        student.tutor_metaphors = body.tutor_metaphors.strip()
    if "tutor_sidekick" in provided and body.tutor_sidekick is not None:
        student.tutor_sidekick = body.tutor_sidekick.strip()
    if "tutor_socratic_strictness" in provided and body.tutor_socratic_strictness is not None:
        student.tutor_socratic_strictness = body.tutor_socratic_strictness.strip()
    if "tutor_struggle_window" in provided and body.tutor_struggle_window is not None:
        student.tutor_struggle_window = body.tutor_struggle_window.strip()
    if "tutor_anti_spoiler" in provided and body.tutor_anti_spoiler is not None:
        student.tutor_anti_spoiler = body.tutor_anti_spoiler
    if "tutor_pacing" in provided and body.tutor_pacing is not None:
        student.tutor_pacing = body.tutor_pacing.strip()
    apply_student_profile(student, provided=provided)
    db.add(student)
    db.flush()
    return student_out(student)


@router.patch("/students/{student_id}", response_model=StudentOut)
def patch_student(student_id: UUID, body: StudentPatch, db: Session = Depends(get_db)) -> StudentOut:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    provided = _provided(body)
    if "reading_level" in provided and body.reading_level is not None:
        student.reading_level = body.reading_level.strip()
    if "modality" in provided and body.modality is not None:
        student.modality = body.modality.strip()
    if "interests" in provided:
        student.interests = _clean_list(body.interests)
    if "tutor_persona" in provided and body.tutor_persona is not None:
        student.tutor_persona = body.tutor_persona.strip()
    if "tutor_lexicon" in provided and body.tutor_lexicon is not None:
        student.tutor_lexicon = body.tutor_lexicon.strip()
    if "tutor_metaphors" in provided and body.tutor_metaphors is not None:
        student.tutor_metaphors = body.tutor_metaphors.strip()
    if "tutor_sidekick" in provided and body.tutor_sidekick is not None:
        student.tutor_sidekick = body.tutor_sidekick.strip()
    if "tutor_socratic_strictness" in provided and body.tutor_socratic_strictness is not None:
        student.tutor_socratic_strictness = body.tutor_socratic_strictness.strip()
    if "tutor_struggle_window" in provided and body.tutor_struggle_window is not None:
        student.tutor_struggle_window = body.tutor_struggle_window.strip()
    if "tutor_anti_spoiler" in provided and body.tutor_anti_spoiler is not None:
        student.tutor_anti_spoiler = body.tutor_anti_spoiler
    if "tutor_pacing" in provided and body.tutor_pacing is not None:
        student.tutor_pacing = body.tutor_pacing.strip()
    db.flush()
    return student_out(student)


@router.get("/courses", response_model=list[CourseSummary])
def list_courses(age_band: str | None = None, db: Session = Depends(get_db)) -> list[CourseSummary]:
    if age_band is not None and age_band not in AGE_BANDS:
        raise HTTPException(status_code=422, detail="age_band must be 6-8, 9-11, 12-14, or 15-17")
    stmt = (
        select(Course)
        .where(Course.in_catalog.is_(True))
        .options(selectinload(Course.quests))
        .order_by(Course.title)
    )
    if age_band is not None:
        stmt = stmt.where(Course.age_band == age_band)
    return [course_summary(course) for course in db.scalars(stmt).all()]


@router.post("/courses", response_model=CourseTree)
def create_course(body: CourseCreate, db: Session = Depends(get_db)) -> CourseTree:
    code = (body.code or unique_course_code(db, body.title)).strip()
    if db.scalar(select(Course.id).where(Course.code == code)):
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course = Course(
        code=code,
        title=body.title.strip(),
        age_band=body.age_band,
        audience=body.age_band,
        standards_alignment=body.standards_alignment.strip(),
        description=body.standards_alignment.strip(),
        competency_dictionary=[],
        quest_count=1,
        goals_per_quest=1,
        quiz_minutes=5,
        updated_at=now(),
    )
    db.add(course)
    db.flush()
    return course_tree(load_course(db, course.id))


@router.post("/courses/import", response_model=CourseTree)
def import_course(payload: dict, db: Session = Depends(get_db)) -> CourseTree:
    try:
        course = replace_course(db, payload)
    except CourseFileError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    course.updated_at = now()
    db.flush()
    return course_tree(load_course(db, course.id))


@router.get("/courses/{course_id}", response_model=CourseTree)
def get_course(course_id: UUID, db: Session = Depends(get_db)) -> CourseTree:
    return course_tree(load_course(db, course_id))


@router.get("/courses/{course_id}/export")
def export_course_route(course_id: UUID, db: Session = Depends(get_db)) -> dict:
    return export_course(load_course(db, course_id))


@router.post("/courses/import-studio", response_model=CourseTree)
def import_studio_course(body: StudioImportIn, db: Session = Depends(get_db)) -> CourseTree:
    try:
        course = copy_studio_into_catalog(db, body.studio_course_id)
    except CourseFileError as exc:
        status = 404 if exc.field == "studio_course_id" else 422
        raise HTTPException(status_code=status, detail=f"{exc.field}: {exc.message}") from exc
    return course_tree(load_course(db, course.id))


@router.post("/courses/{course_id}/remove", status_code=204)
def remove_course(course_id: UUID, db: Session = Depends(get_db)) -> None:
    """Drop the course from the kid catalog. Sessions and messages stay."""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    course.in_catalog = False
    course.updated_at = now()


@router.get("/courses/{course_id}/quests", response_model=list[QuestListItem])
def list_course_quests(course_id: UUID, db: Session = Depends(get_db)) -> list[QuestListItem]:
    course = load_course(db, course_id)
    return [
        quest_list_item(quest)
        for quest in sorted(course.quests, key=lambda item: item.position)
    ]


@router.patch("/courses/{course_id}", response_model=CourseTree)
def patch_course(course_id: UUID, body: CoursePatch, db: Session = Depends(get_db)) -> CourseTree:
    course = load_course(db, course_id)
    code = body.code.strip()
    clash = db.scalar(select(Course.id).where(Course.code == code, Course.id != course.id))
    if clash is not None:
        raise HTTPException(status_code=409, detail="That course code is already used.")
    course.code = code
    course.title = body.title.strip()
    course.age_band = body.age_band
    course.standards_alignment = body.standards_alignment.strip()
    course.competency_dictionary = [item.model_dump() for item in body.competency_dictionary]
    course.updated_at = now()
    db.flush()
    return course_tree(course)


@router.delete("/courses/{course_id}", status_code=204)
def delete_course(course_id: UUID, db: Session = Depends(get_db)) -> None:
    course = load_course(db, course_id)
    quest_ids = [quest.id for quest in course.quests]
    if quest_ids:
        in_use = db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id.in_(quest_ids))
        )
        if in_use:
            raise HTTPException(status_code=409, detail="This course has classes, so it cannot be deleted.")
    db.delete(course)


@router.get("/quests/{quest_id}", response_model=QuestDetail)
def get_quest(quest_id: UUID, db: Session = Depends(get_db)) -> QuestDetail:
    return quest_detail(load_quest(db, quest_id))


@router.patch("/quests/{quest_id}", response_model=QuestDetail)
def patch_quest(quest_id: UUID, body: QuestPatch, db: Session = Depends(get_db)) -> QuestDetail:
    quest = load_quest(db, quest_id)
    code = body.code.strip()
    clash = db.scalar(select(Quest.id).where(Quest.code == code, Quest.id != quest.id))
    if clash is not None:
        raise HTTPException(status_code=409, detail="That quest code is already used.")
    tags = _clean_list(body.competency_tags)
    if len(tags) > 2:
        raise HTTPException(status_code=422, detail="competency_tags: needs one or two tags")
    try:
        goal = normalize_goal(body.learning_goal, "learning_goal")
        criterion = normalize_criterion(body.success_criterion, "success_criterion")
    except CourseFileError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    quest.code = code
    quest.title = body.title.strip()
    quest.quest_type = body.quest_type
    quest.prerequisite_codes = _clean_list(body.prerequisite_codes)
    quest.competency_tags = tags
    quest.dinner_prompt = body.dinner_prompt.strip()
    quest.learning_goal = goal
    quest.success_criterion = criterion
    quest.requires_teach_back = body.requires_teach_back
    quest.course.updated_at = now()
    db.flush()
    return quest_detail(quest)


@router.delete("/quests/{quest_id}", status_code=204)
def delete_quest(quest_id: UUID, db: Session = Depends(get_db)) -> None:
    quest = load_quest(db, quest_id)
    if quest_in_use(db, quest.id):
        raise HTTPException(status_code=409, detail="This quest has classes, so it cannot be deleted.")
    db.delete(quest)


@router.put("/quests/{quest_id}/beats", response_model=QuestDetail)
def put_beats(quest_id: UUID, body: BeatWrite, db: Session = Depends(get_db)) -> QuestDetail:
    quest = load_quest(db, quest_id)
    normalized = []
    try:
        for index, beat_body in enumerate(body.beats):
            normalized.append(validate_move(beat_body.model_dump(), f"beats[{index}]"))
        check_moves(
            normalized,
            teach_back=bool(quest.requires_teach_back),
            criterion=list(quest.success_criterion or []),
        )
    except CourseFileError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.field}: {exc.message}") from exc
    existing = sorted(quest.beats, key=lambda item: item.position)
    if len(existing) != len(normalized):
        if quest_in_use(db, quest.id):
            raise HTTPException(
                status_code=409,
                detail="This quest has classes, so its moves cannot be added or removed.",
            )
        for beat in list(quest.beats):
            db.delete(beat)
        db.flush()
        for position, fields in enumerate(normalized, start=1):
            quest.beats.append(
                Beat(
                    position=position,
                    role=fields["role"],
                    bloom_level=fields["bloom_level"],
                    cognitive_load=fields["cognitive_load"],
                    prompt=fields["prompt"],
                    rubric=fields["rubric"],
                    misconception_map=fields["misconception_map"],
                    hint_ladder=fields["hint_ladder"],
                    widget=fields["widget"],
                )
            )
    else:
        for beat, fields in zip(existing, normalized, strict=True):
            beat.role = fields["role"]
            beat.bloom_level = fields["bloom_level"]
            beat.cognitive_load = fields["cognitive_load"]
            beat.prompt = fields["prompt"]
            beat.rubric = fields["rubric"]
            beat.misconception_map = fields["misconception_map"]
            beat.hint_ladder = fields["hint_ladder"]
            beat.widget = fields["widget"]
    quest.course.updated_at = now()
    db.flush()
    return quest_detail(quest)
```

Source file `apps/api/app/seed.py`:

```python
"""Idempotent seed: four students and three courses.

Running this twice does not duplicate students. Rome, Geometry, and AP Macro are
updated in place. Sessions and messages stay. Any other course code is left as edited.
Students keep a tutor persona that was already saved. Blank tutor fields are filled
from the age band. The default tutor profile is inserted when it is missing and
is not overwritten.

Studio tables (studio_*) are not read or written here. A re-seed leaves them in place.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.course_io import replace_course, update_course_in_place
from app.curriculum import COURSES
from app.database import SessionLocal
from app.engine.defaults import profile_for_age
from app.models import Course, Student
from app.tutor_profile import ensure_default_profile

STUDENTS = [
    {
        "slug": "iron-man",
        "display_name": "Iron Man",
        "age": 10,
        "interests": ["inventions", "teams"],
    },
    {
        "slug": "storm",
        "display_name": "Storm",
        "age": 10,
        "interests": ["weather", "leadership"],
    },
    {
        "slug": "spider-man",
        "display_name": "Spider-Man",
        "age": 11,
        "interests": ["cities", "fairness"],
    },
    {
        "slug": "wolverine",
        "display_name": "Wolverine",
        "age": 16,
        "interests": ["history", "hard choices"],
    },
]


def _fill_student(student: Student, spec: dict) -> None:
    if student.age is None:
        student.age = spec["age"]
    if student.tutor_persona:
        return
    profile = profile_for_age(student.age)
    student.reading_level = profile.reading_level
    student.modality = profile.modality
    student.interests = list(spec["interests"])
    student.tutor_persona = profile.persona
    student.tutor_lexicon = profile.lexicon
    student.tutor_metaphors = profile.metaphors
    student.tutor_sidekick = profile.sidekick
    student.tutor_socratic_strictness = profile.socratic_strictness
    student.tutor_struggle_window = profile.struggle_window
    student.tutor_anti_spoiler = profile.anti_spoiler
    student.tutor_pacing = profile.pacing


def seed(db: Session) -> dict[str, int]:
    created_students = 0
    for spec in STUDENTS:
        student = db.scalar(select(Student).where(Student.slug == spec["slug"]))
        if student is None:
            student = Student(slug=spec["slug"], display_name=spec["display_name"], age=spec["age"])
            db.add(student)
            db.flush()
            created_students += 1
        _fill_student(student, spec)
    db.flush()

    created_courses = 0
    for payload in COURSES:
        exists = db.scalar(select(Course.id).where(Course.code == payload["code"]))
        if exists is None:
            replace_course(db, payload)
            created_courses += 1
        else:
            update_course_in_place(db, payload)
    ensure_default_profile(db)
    db.commit()
    return {"students_created": created_students, "courses_created": created_courses}


def main() -> None:
    db = SessionLocal()
    try:
        result = seed(db)
    finally:
        db.close()
    print(
        "students_created={students_created} courses_created={courses_created}".format(**result)
    )


if __name__ == "__main__":
    main()
```

Source file `apps/api/app/curriculum/__init__.py`:

```python
"""Seed courses. Quest codes match the curriculum blueprint."""

from app.curriculum.geometry import geometry_course
from app.curriculum.macro import macro_course
from app.curriculum.rome import rome_course

COURSES = [rome_course(), geometry_course(), macro_course()]
```

Legacy seed shape builders used by `rome_course`, `geometry_course`, and `macro_course` before `validate_course` flattens units into quests, goals, and close:

Source file `apps/api/app/curriculum/shape.py`:

```python
"""Compact builders for a Tier 1 course file."""

from __future__ import annotations


def rubric(*rows: tuple[str, str, int]) -> list[dict]:
    return [{"id": row_id, "text": text, "weight": weight} for row_id, text, weight in rows]


def ladder(nudge: str, analogy: str, scaffold: str) -> dict:
    return {"nudge": nudge, "analogy": analogy, "scaffold": scaffold}


def traps(*items: tuple[str, str, str]) -> list[dict]:
    return [{"id": row_id, "trap": trap, "note": note} for row_id, trap, note in items]


def half(left: tuple[str, str], right: tuple[str, str]) -> list[dict]:
    return rubric((left[0], left[1], 50), (right[0], right[1], 50))


def mcq(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: str,
    *,
    explain: bool = False,
    misconception: str = "",
) -> dict:
    return {
        "type": "single",
        "prompt": prompt,
        "choices": [
            {"id": choice_id, "text": text, "misconception": note}
            for choice_id, text, note in choices
        ],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def flaw(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: str,
    *,
    explain: bool = True,
    misconception: str = "",
) -> dict:
    body = mcq(prompt, choices, answer, explain=explain, misconception=misconception)
    body["type"] = "flaw"
    return body


def multi(
    prompt: str,
    choices: list[tuple[str, str, str]],
    answer: list[str],
    *,
    explain: bool = False,
    misconception: str = "",
) -> dict:
    return {
        "type": "multi",
        "prompt": prompt,
        "choices": [
            {"id": choice_id, "text": text, "misconception": note}
            for choice_id, text, note in choices
        ],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def ordering(
    prompt: str,
    choices: list[tuple[str, str]],
    answer: list[str],
    *,
    explain: bool = True,
    misconception: str = "",
) -> dict:
    return {
        "type": "order",
        "prompt": prompt,
        "choices": [{"id": choice_id, "text": text, "misconception": ""} for choice_id, text in choices],
        "answer": answer,
        "explain": explain,
        "misconception": misconception,
    }


def _beat(
    role: str,
    prompt: str,
    rows: list[dict],
    hints: dict,
    trap: list[dict],
    bloom: str,
    load: str,
    widget: dict | None,
) -> dict:
    return {
        "role": role,
        "bloom_level": bloom,
        "cognitive_load": load,
        "prompt": prompt,
        "rubric": rows,
        "misconception_map": trap,
        "hint_ladder": hints,
        "widget": widget,
    }


def quest(
    code: str,
    title: str,
    quest_type: str,
    prereqs: list[str],
    tags: list[str],
    dinner: str,
    beats: list[dict],
    *,
    goal: str,
    criterion: list[dict],
    teach_back: bool = False,
) -> dict:
    return {
        "code": code,
        "title": title,
        "quest_type": quest_type,
        "prerequisite_codes": prereqs,
        "competency_tags": tags,
        "dinner_prompt": dinner,
        "learning_goal": goal,
        "success_criterion": criterion,
        "requires_teach_back": teach_back,
        "beats": beats,
    }


def mv(
    role: str,
    prompt: str,
    rows: list[dict],
    nudge: str,
    analogy: str,
    scaffold: str,
    trap: tuple[str, str, str],
    *,
    bloom: str = "understand",
    load: str = "medium",
    widget: dict | None = None,
    extra_traps: tuple[tuple[str, str, str], ...] = (),
) -> dict:
    return _beat(
        role,
        prompt,
        rows,
        ladder(nudge, analogy, scaffold),
        traps(trap, *extra_traps),
        bloom,
        load,
        widget,
    )


def unit(
    number: int,
    title: str,
    enduring: str,
    continuity: str,
    quests: list[dict],
    *,
    diagnostic: bool = False,
    capstone: bool = False,
) -> dict:
    return {
        "number": number,
        "title": title,
        "enduring_understanding": enduring,
        "continuity_summary": continuity,
        "is_diagnostic": diagnostic,
        "is_capstone": capstone,
        "quests": quests,
    }


def course(
    code: str,
    title: str,
    age_band: str,
    standards: str,
    competencies: list[tuple[str, str]],
    units: list[dict],
) -> dict:
    return {
        "code": code,
        "title": title,
        "age_band": age_band,
        "standards_alignment": standards,
        "competency_dictionary": [
            {"code": tag, "description": text} for tag, text in competencies
        ],
        "units": units,
    }
```

### 4. Pipeline 2: AI Tutor Runtime LLM Workflow & Context Merging

The walkthrough engine is `load_prompt` in `apps/api/app/prompt_loader.py` plus `assemble` in `apps/api/app/engine/assemble.py`. The HTTP entry is `GET /sessions/{session_id}/prompt`. The model call is `POST /api/chat` in `apps/web/app/api/chat/route.ts`. Python does not call the tutor model.

Context merge inside `load_prompt`:

- Student / child config becomes `Layer2Student` from `sessions.student`: `display_name`, `age_band_for(student.age)`, `reading_level`, `modality`, `interests`, failed-attempt count on the current beat, and `_zpd`.
- Tutor persona becomes `Layer3Tutor` and `Layer4Discourse` from `load_profile`, the `tutor_profiles` row. `students.tutor_*` is not read here. `instructive` 1 through 5 sets `socratic_strictness` via `strictness_for` and `pacing` via `pacing_for`. `growth_praise` sets `Layer5Affect.praise` to `growth-mindset-only` or `result-or-effort`. Layers 6 and 7 are fixed placeholders.
- Active course state becomes `Layer1Beat`: course title and code, quest code and title, `learning_goal`, weighted `success_criterion` rows, beat role and prompt, rubric, misconception map, hint ladder, and the quest close. `_quest_walk` turns `quest_goals` into `GoalPoint` lines and `quest_closes` into `close_line` / `empty_close`. The close question and choices stay hidden until the show beat is the one on screen.

`assemble` concatenates seven layer blocks plus a Rules block into `system_prompt`, and always returns `RESPONSE_SCHEMA` and `TURN_TEMPERATURE = 0.4`. The schema requires `reply`, `rubric_met`, `misconception`, `hint_tier`, `advance`, and `diagram`.

Progression and evaluation:

- `POST /api/chat` saves the user message, loads the prompt (`kickoff=true` only when the single user text equals `KICKOFF`), streams `Output.object` against `response_schema`, stores the system prompt and messages with `POST /sessions/{id}/model-prompts`, checks `diagram` with `POST /sessions/{id}/check-diagram`, and, unless kickoff, posts `rubric_met`, `misconception`, `hint_tier`, and `advance` to `POST /sessions/{id}/turn-score`.
- A choice card is graded before the model speaks. `grade_widget` calls `grade_choice` and writes `beat_results` with `choice` ids. `apply_turn_score` then reads `rubric_met`.
- `_weights` scores the beat rubric. Pass score is `PASS_SCORE = 70`. `_criterion_met` scores `quests.success_criterion` the same way. On Try or Show, a met quest criterion calls `_complete`, which sets `sessions.status = 'completed'` and `current_beat_id = None` and skips later beats.
- Show with `quest_closes.kind = 'none'` and `advance` true also completes the quest. After the struggle window (`struggle_limit` on `tutor_profiles.struggle_window`) and `advance`, Show completes the quest. Name records a passing result and calls `advance` to the next beat. A passed typed beat, or a reveal after the window, calls `advance`, which moves `current_beat_id` to the next beat or completes the quest on the last beat.
- Goal-to-goal movement inside one quest is prompt text (`Walk these goals in order` in `_layer1`). There is no `current_goal_id` column. The stored cursor is `sessions.current_beat_id`.

Source file `apps/api/app/engine/types.py`:

```python
"""Typed inputs for the seven prompt layers.

Layer 2 is the student. Layers 3 and 4 are the tutor profile. They are
separate objects so the assembler does not read student columns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    text: str
    weight: int


@dataclass(frozen=True)
class MisconceptionTrap:
    id: str
    trap: str
    note: str


@dataclass(frozen=True)
class HintLadder:
    nudge: str
    analogy: str
    scaffold: str


@dataclass(frozen=True)
class WidgetChoice:
    id: str
    text: str
    misconception: str


@dataclass(frozen=True)
class WidgetGrade:
    correct: bool
    score: int
    passed: bool
    misconception: str | None
    choice_ids: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class WidgetTask:
    type: str
    prompt: str
    choices: tuple[WidgetChoice, ...]
    answer: str | tuple[str, ...]
    explain: bool
    grade: WidgetGrade | None


@dataclass(frozen=True)
class GoalPoint:
    """One studio goal and the criterion that finishes it."""

    learning_goal: str
    success_criterion: str


@dataclass(frozen=True)
class Layer1Beat:
    """Active Tier 4 beat, plus the unit continuity sentence."""

    course_title: str
    unit_title: str
    continuity: str
    quest_code: str
    quest_title: str
    beat_role: str
    beat_position: int
    beat_count: int
    bloom_level: str
    cognitive_load: str
    prompt: str
    rubric: tuple[RubricCriterion, ...]
    misconceptions: tuple[MisconceptionTrap, ...]
    hint_ladder: HintLadder
    widget: WidgetTask | None
    pass_score: int
    gate_cleared: bool
    finished: bool
    quest_objective: str = ""
    beat_objectives: tuple[str, ...] = ()
    learning_goal: str = ""
    success_criterion: tuple[RubricCriterion, ...] = ()
    requires_teach_back: bool = False
    opening_idea: str = ""
    course_code: str = ""
    goals: tuple[GoalPoint, ...] = ()
    empty_close: bool = False
    close_line: str = ""


@dataclass(frozen=True)
class Layer2Student:
    """Student traits. Attempt count and ZPD are computed at runtime."""

    display_name: str
    age_band: str
    reading_level: str
    modality: str
    interests: tuple[str, ...]
    attempt_count: int
    zpd: str


@dataclass(frozen=True)
class Layer3Tutor:
    """Tutor-agent voice. Not a student trait."""

    persona: str
    lexicon: str
    metaphors: str
    sidekick: str


@dataclass(frozen=True)
class Layer4Discourse:
    """Tutor-agent guardrails. Not a student trait.

    instructive is 1 (one short question) through 5 (a fuller lesson first).
    3 is today's short explanation, then one question.
    """

    socratic_strictness: str
    struggle_window: str
    anti_spoiler: bool
    pacing: str
    instructive: int = 3
    one_question: bool = True
    use_interests: bool = True
    stay_on_course: bool = True


@dataclass(frozen=True)
class Layer5Affect:
    praise: str


@dataclass(frozen=True)
class Layer6Metacognition:
    self_explanation: str


@dataclass(frozen=True)
class Layer7Memory:
    schedule: str


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    response_schema: dict
    temperature: float
```

Source file `apps/api/app/engine/choices.py`:

```python
"""Closed choices for the one default tutor profile.

The assembler understands these ids. Free text is not a profile value.
"""

from __future__ import annotations

PERSONAS: tuple[tuple[str, str], ...] = (
    ("curious-co-explorer", "Curious co-explorer"),
    ("tactical-coach", "Tactical coach"),
    ("debate-moderator", "Debate moderator"),
    ("patient-explainer", "Patient explainer"),
)

VOICES: tuple[tuple[str, str], ...] = (
    ("early-concrete", "Early concrete"),
    ("middle-grade-vivid", "Middle-grade vivid"),
    ("precise-visual", "Precise visual"),
    ("analytical-high-school", "Analytical high-school"),
)

METAPHORS: tuple[tuple[str, str], ...] = (
    ("playground-sports", "Playground and sports"),
    ("buildings-machines", "Buildings and machines"),
    ("policy-cause", "Policy and cause-and-effect"),
    ("none", "None (plain language only)"),
)

SIDEKICKS: tuple[tuple[str, str], ...] = (
    ("bumbling-partner", "Bumbling partner"),
    ("rookie-picture", "Rookie who trusts a picture"),
    ("pundit", "Pundit who skips the chain"),
    ("off", "Off"),
)

STRUGGLE_WINDOWS: tuple[tuple[str, str], ...] = (
    ("short", "Short (1 miss)"),
    ("standard", "Standard (2)"),
    ("long", "Long (3)"),
)

# Reading voice follows the persona unless the profile overrides it.
PERSONA_VOICE: dict[str, str] = {
    "curious-co-explorer": "middle-grade-vivid",
    "tactical-coach": "precise-visual",
    "debate-moderator": "analytical-high-school",
    "patient-explainer": "early-concrete",
}

_STRICTNESS = {
    1: "socratic",
    2: "mostly-socratic",
    3: "balanced",
    4: "mostly-instructive",
    5: "instructive",
}

_PACING = {
    1: "one-short-question",
    2: "short-question",
    3: "short-turns-one-question",
    4: "fact-then-question",
    5: "fuller-lesson-then-question",
}


def ids(options: tuple[tuple[str, str], ...]) -> set[str]:
    return {item[0] for item in options}


def strictness_for(level: int) -> str:
    return _STRICTNESS[min(5, max(1, level))]


def pacing_for(level: int) -> str:
    return _PACING[min(5, max(1, level))]
```

Source file `apps/api/app/engine/defaults.py`:

```python
"""Age-band defaults for layer 2 and for the tutor-agent settings in layers 3 and 4."""

from __future__ import annotations

from dataclasses import dataclass

AGE_BANDS = ("6-8", "9-11", "12-14", "15-17")


def age_band_for(age: int | None) -> str:
    if age is None or age <= 8:
        return "6-8"
    if age <= 11:
        return "9-11"
    if age <= 14:
        return "12-14"
    return "15-17"


@dataclass(frozen=True)
class AgeProfile:
    age_band: str
    reading_level: str
    modality: str
    persona: str
    lexicon: str
    metaphors: str
    sidekick: str
    socratic_strictness: str = "balanced"
    struggle_window: str = "minimum"
    anti_spoiler: bool = True
    pacing: str = "short-turns-one-question"


PROFILES: dict[str, AgeProfile] = {
    "6-8": AgeProfile(
        age_band="6-8",
        reading_level="early-reader",
        modality="hands-on",
        persona="Curious Co-Explorer",
        lexicon="early-grade concrete",
        metaphors="playground rules and familiar objects",
        sidekick="a sidekick with a clear flaw",
    ),
    "9-11": AgeProfile(
        age_band="9-11",
        reading_level="middle-grade",
        modality="story",
        persona="Curious Co-Explorer",
        lexicon="vivid middle-grade",
        metaphors="sports-team captain and playground rules",
        sidekick="a sidekick with a clear flaw",
    ),
    "12-14": AgeProfile(
        age_band="12-14",
        reading_level="grade-level",
        modality="visual",
        persona="Tactical Engineering Commander",
        lexicon="precise visual-spatial",
        metaphors="bridge truss, robotics hinge, and laser grid",
        sidekick="a rookie who treats a picture as a proof",
    ),
    "15-17": AgeProfile(
        age_band="15-17",
        reading_level="high-school",
        modality="verbal",
        persona="Spirited FOMC Debate Moderator",
        lexicon="analytical high-school; the student is a decision maker who must give multi-step causal chains",
        metaphors="policy levers and multi-step causal chains",
        sidekick="a pundit who skips the causal chain",
    ),
}


def profile_for_age(age: int | None) -> AgeProfile:
    return PROFILES[age_band_for(age)]


def profile_for_band(age_band: str) -> AgeProfile:
    return PROFILES.get(age_band, PROFILES["9-11"])
```

Source file `apps/api/app/engine/placeholders.py`:

```python
"""Fixed placeholder objects for layers 5, 6, and 7.

Nothing in these layers is inferred. The assembler always receives them.
"""

from app.engine.types import Layer5Affect, Layer6Metacognition, Layer7Memory


def affect_layer() -> Layer5Affect:
    return Layer5Affect(praise="growth-mindset-only")


def metacognition_layer() -> Layer6Metacognition:
    return Layer6Metacognition(self_explanation="one-line")


def memory_layer() -> Layer7Memory:
    return Layer7Memory(schedule="none")
```

Source file `apps/api/app/engine/assemble.py`:

```python
"""Assemble the system prompt, response schema, and temperature from seven layers."""

from __future__ import annotations

from app.engine.types import (
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    Layer5Affect,
    Layer6Metacognition,
    Layer7Memory,
    PromptBundle,
    WidgetTask,
)

TURN_TEMPERATURE = 0.4

RESPONSE_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reply": {
            "type": "string",
            "description": "The only text the student reads.",
        },
        "rubric_met": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Ids of rubric rows the student's written words earned.",
        },
        "misconception": {
            "type": ["string", "null"],
            "description": "A misconception to store, or null when the writing is fine.",
        },
        "hint_tier": {
            "type": "string",
            "enum": ["nudge", "analogy", "scaffold"],
        },
        "advance": {
            "type": "boolean",
            "description": "True only when this beat should end.",
        },
        "diagram": {
            "description": (
                "A picture of the idea being taught, and only when a picture makes that idea clearer. "
                "kind triangle is drawn in the geometry course. "
                "kind graph and kind map are named for a later pass and are not drawn. "
                "Null when no picture should appear. No HTML, no URL, and no free-form drawing prompt."
            ),
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "description": "A triangle the app draws from three sides and three angles.",
                    "properties": {
                        "kind": {"type": "string", "enum": ["triangle"]},
                        "sides": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Short plain text. No HTML and no URL.",
                                    },
                                    "length": {"type": "number"},
                                },
                                "required": ["label", "length"],
                            },
                            "description": "Sides a, b, and c, opposite angles A, B, and C.",
                        },
                        "angles": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Short plain text. No HTML and no URL.",
                                    },
                                    "degrees": {"type": "number"},
                                },
                                "required": ["label", "degrees"],
                            },
                            "description": "Angles A, B, and C, in degrees. They sum to 180.",
                        },
                        "right_angle": {
                            "type": ["boolean", "null"],
                            "description": "True to mark the right angle. Null when there is none.",
                        },
                    },
                    "required": ["kind", "sides", "angles", "right_angle"],
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "description": "graph and map are named for a later pass. The server drops them.",
                    "properties": {
                        "kind": {"type": "string", "enum": ["graph", "map"]},
                    },
                    "required": ["kind"],
                },
            ],
        },
    },
    "required": ["reply", "rubric_met", "misconception", "hint_tier", "advance", "diagram"],
}

_ROLE_LABEL = {
    "engage": "engage",
    "try": "try",
    "name": "name",
    "show": "show",
    "teach_back": "teach-back",
}


def hint_tier_for(attempt_count: int) -> str:
    if attempt_count <= 0:
        return "nudge"
    if attempt_count == 1:
        return "analogy"
    return "scaffold"


def struggle_limit(window: str) -> int:
    """Unsuccessful tries to hold before a worked answer is allowed.

    "short" is one miss. "standard" and "minimum" are two. "long" is three.
    A numeric window is that many unsuccessful tries. The ban must end.
    """
    text = (window or "").strip().lower()
    if text.isdigit():
        return int(text)
    if text == "short":
        return 1
    if text in {"extended", "long"}:
        return 3
    return 2


def instructive_level(value: int | None) -> int:
    try:
        level = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 3
    if level < 1:
        return 1
    if level > 5:
        return 5
    return level


def _diagram_rule(beat: Layer1Beat) -> str:
    """A picture is optional, and this pass draws a geometry triangle only."""
    shared = (
        "A diagram is for the idea being taught, and only when a picture makes that idea clearer. "
        "No HTML, no image URL, and no free-form drawing prompt. The app draws the picture."
    )
    if (beat.course_code or "").strip().lower() == "geometry":
        return (
            shared
            + " In this geometry course, diagram may be a triangle: kind \"triangle\", three sides "
            "(a short plain-text label and a length), three angles (a short plain-text label and degrees "
            "that sum to 180), and right_angle true only when one angle is a right angle. "
            "kind graph and kind map are named for a later pass and are not drawn. "
            "Set diagram to null when a picture would not help."
        )
    return (
        shared
        + " A triangle is only inside the geometry course. This course gets no picture. Set diagram to null."
    )


def _course_scope_rule(discourse: Layer4Discourse, beat: Layer1Beat) -> str | None:
    """Name the current course when the layer 4 switch is on.

    Depth inside that course stays allowed. A different subject gets one
    short line, then the turn returns. None leaves today's prompt unchanged,
    including the permission to answer a tangent.
    """
    if not discourse.stay_on_course:
        return None
    course = beat.course_title.strip() or "this course"
    quest = beat.quest_title.strip() or "this quest"
    return (
        f"Stay on {course}. Depth inside {course} stays allowed: go as deep as the student needs "
        f"on {course} and quest {quest}, including closely related ideas that serve this learning goal. "
        f"If the student brings up a different subject, acknowledge it in one short line and return to {course}. "
        "Do not explain that subject. Do not keep chatting about it."
    )


def _classic(discourse: Layer4Discourse) -> bool:
    """Level 3 with both default switches is today's teach-then-ask prompt."""
    return (
        instructive_level(discourse.instructive) == 3
        and discourse.one_question
        and discourse.use_interests
    )


def _question_rule(one_question: bool) -> str:
    if one_question:
        return "One question per turn, and it comes last. Do not ask a second question."
    return "A second question is allowed in the same turn when it helps the idea."


def _picture(use_interests: bool) -> str:
    if use_interests:
        return "a concrete picture from their interests"
    return "a concrete picture from the subject, not from their hobbies"


def _opening_sentence(discourse: Layer4Discourse) -> str:
    """Reply length for this instructive setting."""
    level = instructive_level(discourse.instructive)
    picture = _picture(discourse.use_interests)
    if level <= 1:
        return "One short question. Almost no explanation until they try."
    if level == 2:
        return "Ask one short question. At most one sentence of setup. Do not teach a lesson yet."
    if level == 3:
        return (
            f"A short explanation, then one question. A few sentences the student could retell: "
            f"the fact, {picture}, and why it matters."
        )
    if level == 4:
        return (
            f"Teach the fact and why it matters for this goal, using {picture}, then one question. "
            "A miss gets this longer explanation right away."
        )
    return (
        f"A fuller lesson first: the fact, {picture}, why it matters for this goal, then one question. "
        "Stuck students get the longer explanation on the first miss."
    )


def _miss_sentence(discourse: Layer4Discourse, attempt_count: int) -> str | None:
    """How soon a miss gets a real explanation. None means keep the opening shape."""
    level = instructive_level(discourse.instructive)
    question = _question_rule(discourse.one_question)
    picture = _picture(discourse.use_interests)
    if level <= 1:
        if attempt_count <= 0:
            return None
        return (
            "They have tried. Still almost no explanation. Ask one short question about what they tried. "
            "A real explanation waits until the struggle window. "
            + question
        )
    if level == 2:
        if attempt_count < 2:
            if attempt_count <= 0:
                return None
            return (
                "They missed once. Ask one short question. Do not give a real explanation yet. "
                + question
            )
        return (
            "They have missed twice. Give a short explanation of the idea, then stop before the passing answer. "
            + question
        )
    if level == 3:
        if attempt_count <= 0:
            return None
        return (
            "The student missed. Explain what they tried, what the idea actually is, and the next step. "
            "Do not give the worked answer yet. Do not teach the next move. "
            + question
        )
    if level == 4:
        if attempt_count <= 0:
            return None
        return (
            f"The student missed. Give the longer explanation now: the fact, {picture}, and why it matters, "
            "then the next step. Do not wait for another miss. Do not state the passing answer yet. "
            "Do not teach the next move. "
            + question
        )
    if attempt_count <= 0:
        return None
    return (
        f"The student is stuck. Give the longer explanation on this miss: the fact, {picture}, "
        "why it matters, and what they tried. Do not wait. Do not state the passing answer yet. "
        "Do not teach the next move. "
        + question
    )


_PERSONA_LINE = {
    "curious-co-explorer": "Speak as a curious co-explorer. Wonder alongside the student and explore the idea with them.",
    "tactical-coach": "Speak as a tactical coach. Be direct, concrete, and focused on the next move.",
    "debate-moderator": "Speak as a debate moderator. Ask for the chain of causes before the verdict.",
    "patient-explainer": "Speak as a patient explainer. Go slowly and make sure the last sentence landed.",
}

_LEXICON_LINE = {
    "early-concrete": "Write with an early concrete voice: short words and things they can point at.",
    "middle-grade-vivid": "Write with a middle-grade vivid voice: clear sentences and a picture they can see.",
    "precise-visual": "Write with a precise visual voice: shapes, positions, and exact relations.",
    "analytical-high-school": "Write with an analytical high-school voice. The student gives a multi-step chain.",
}

_METAPHOR_LINE = {
    "playground-sports": "When a picture helps, draw it from playground and sports.",
    "buildings-machines": "When a picture helps, draw it from buildings and machines.",
    "policy-cause": "When a picture helps, draw it from policy and cause-and-effect.",
    "none": "Use plain language only. Do not add a metaphor.",
}

_SIDEKICK_LINE = {
    "bumbling-partner": "On teach-back only, the sidekick is a bumbling partner who gets the idea wrong.",
    "rookie-picture": "On teach-back only, the sidekick is a rookie who trusts a picture.",
    "pundit": "On teach-back only, the sidekick is a pundit who skips the chain.",
    "off": "Teach-back sidekick is off. Do not invent a partner. The student explains the idea.",
}


def _hint_text(ladder: HintLadder, tier: str) -> str:
    return getattr(ladder, tier, "") or ""


def _rubric_line(beat: Layer1Beat) -> str:
    if not beat.rubric:
        return "None."
    return " ".join(
        f"{row.id} (weight {row.weight}): {row.text}" for row in beat.rubric
    )


def _traps_line(beat: Layer1Beat) -> str:
    if not beat.misconceptions:
        return "None."
    return " ".join(
        f"{trap.id}: {trap.trap} ({trap.note})" for trap in beat.misconceptions
    )


def _criterion_line(beat: Layer1Beat) -> str:
    if not beat.success_criterion:
        return _rubric_line(beat)
    return " ".join(
        f"{row.id} (weight {row.weight}): {row.text}" for row in beat.success_criterion
    )


def _answer_text(widget: WidgetTask) -> str:
    answer = widget.answer
    if isinstance(answer, tuple):
        return ", ".join(answer)
    return answer


def _widget_lines(widget: WidgetTask, *, reveal: bool) -> list[str]:
    choices = []
    for choice in widget.choices:
        note = f" misconception: {choice.misconception}" if choice.misconception else ""
        choices.append(f"{choice.id}. {choice.text}{note}")
    lines = [
        f"Choice widget ({widget.type}), graded by the server before you speak. Do not grade the taps.",
        f"Widget prompt: {widget.prompt}",
        f"Choices: {' | '.join(choices)}",
    ]
    if reveal:
        lines.append(f"Correct answer, for you only: {_answer_text(widget)}.")
    else:
        lines.append(
            "The correct widget answer stays hidden until the struggle window opens. Do not name it."
        )
    if widget.explain:
        lines.append(
            "A short written explanation may come with the choice. Grade that writing with rubric_met. Do not change the tap score."
        )
    else:
        lines.append("No written explanation is required.")
    grade = widget.grade
    if grade is None:
        lines.append("They have not submitted the card yet. Do not ask a second question. Set advance to false.")
        return lines
    lines.append(
        f"Server grade of the taps: {'passed' if grade.passed else 'not passed'}, score {grade.score}."
    )
    lines.append(f"Choice ids: {', '.join(grade.choice_ids) or 'none'}.")
    lines.append(f"Their explanation: {grade.explanation.strip() or 'none'}.")
    lines.append(
        f"Stored misconception: {grade.misconception or 'none'}. Keep it. Do not invent a different one for the taps."
    )
    return lines


def _layer1(
    beat: Layer1Beat,
    tier: str,
    *,
    reveal: bool,
    hold_widget: bool = False,
    discourse: Layer4Discourse | None = None,
) -> list[str]:
    role = _ROLE_LABEL.get(beat.beat_role, beat.beat_role.replace("_", " "))
    goal = beat.learning_goal.strip() or beat.quest_objective.strip() or beat.quest_title
    lines = [
        "Layer 1 — Active move",
        f"Course: {beat.course_title}.",
    ]
    if beat.unit_title.strip():
        lines.append(f"Unit: {beat.unit_title}.")
        lines.append(f"Unit continuity: {beat.continuity.strip() or 'None.'}")
    lines.extend(
        [
            f"Quest {beat.quest_code}: {beat.quest_title}.",
            f"Learning goal: {goal}",
            f"Success criterion: {_criterion_line(beat)}",
            f"Pass score: {beat.pass_score}. The quest finishes when those rows are met. After the struggle window on Show, explain why the answer fits and finish the quest.",
        ]
    )
    if beat.finished:
        lines.append(
            "This quest is finished. Congratulate the student in one or two sentences. Do not start another quest. Set advance to false, rubric_met to [], and misconception to null."
        )
        return lines
    lines.extend(
        [
            f"Move {beat.beat_position} of {beat.beat_count}: {role}.",
            f"Bloom level: {beat.bloom_level}. Cognitive load: {beat.cognitive_load}.",
            _move_task(beat, hold_widget=hold_widget),
            f"This move's rubric rows: {_rubric_line(beat)}",
            f"Misconception traps: {_traps_line(beat)}",
            "Hint ladder: "
            f"rung 1 nudge: {beat.hint_ladder.nudge or 'Ask them to try once more.'} "
            f"Rung 2 analogy: {beat.hint_ladder.analogy or 'Offer a picture, not the answer.'} "
            f"Rung 3 scaffold: {beat.hint_ladder.scaffold or 'Give a sentence starter.'}",
            f"Live hint tier for this turn: {tier}. Use this rung only: {_hint_text(beat.hint_ladder, tier) or 'Ask them to try once more.'}",
            f"Show already cleared: {'yes' if beat.gate_cleared else 'no'}.",
            "Mark the criterion: rubric_met lists ids from this move's rubric and, on Try or Show, any success-criterion ids their words earned.",
            "Advance when this move is done. If the success criterion is already met on Try or Show, the quest ends and later moves are skipped.",
        ]
    )
    if beat.beat_role == "engage":
        if discourse is None or _classic(discourse):
            lines.append(
                "Engage teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. No choice box."
            )
        else:
            lines.append(f"Engage. {_opening_sentence(discourse)} {_question_rule(discourse.one_question)} No choice box.")
    elif beat.beat_role == "name":
        if discourse is None or _classic(discourse):
            lines.append(
                "Name teaches, then asks. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last. Then set advance to true. Do not start the next move."
            )
        else:
            lines.append(
                f"Name. {_opening_sentence(discourse)} {_question_rule(discourse.one_question)} "
                "Then set advance to true. Do not start the next move."
            )
    elif beat.beat_role == "teach_back":
        lines.append(
            "Teach-back: the student corrects the sidekick. You may confirm a correct correction. Do not lecture the whole model."
        )
    if beat.widget is not None and beat.beat_role in {"try", "show"} and not hold_widget:
        lines.extend(_widget_lines(beat.widget, reveal=reveal))
    if beat.goals or beat.empty_close or beat.close_line.strip():
        if beat.goals:
            lines.append(
                "Walk these goals in order. Each goal is a discussion point, finished by its own criterion, before the close."
            )
            for index, point in enumerate(beat.goals, start=1):
                lines.append(f"Goal {index}: {point.learning_goal.strip() or 'None.'}")
                lines.append(f"Criterion {index}: {point.success_criterion.strip() or 'None.'}")
        if beat.close_line.strip():
            lines.append(beat.close_line.strip())
        if beat.empty_close and beat.beat_role == "show":
            lines.append("The close has no question. End the quest without asking one. Set advance to true.")
    return lines


def _move_task(beat: Layer1Beat, *, hold_widget: bool) -> str:
    if beat.beat_role == "engage":
        return (
            "Expand this idea in words a student could retell. Do not turn it into a quiz stem. "
            f"Idea: {beat.prompt}"
        )
    if beat.beat_role == "name":
        return (
            "Expand this idea, then ask one question about it. Do not turn it into a quiz stem. "
            f"Idea: {beat.prompt}"
        )
    if hold_widget:
        return (
            "The choice widget is not on screen. Teach this move before the check. "
            "Do not ask this move's choice question."
        )
    return f"Stay on this move. Task, in your own words if you need to: {beat.prompt}"


def _layer2(student: Layer2Student, *, use_interests: bool = True) -> list[str]:
    interests = ", ".join(student.interests) if student.interests else "none listed"
    if use_interests:
        interest_line = (
            f"Interests to turn into one concrete picture inside the explanation: {interests}. Do not list them back."
        )
    else:
        interest_line = (
            f"Recorded interests: {interests}. Examples stay on the subject. Do not use those hobbies as the picture."
        )
    return [
        "Layer 2 — Student",
        f"The student's name is {student.display_name}. Use it.",
        f"Age band: {student.age_band}.",
        f"Write at this reading level: {student.reading_level or 'unspecified'}. Do not announce the level.",
        f"Modality to use when you choose a picture: {student.modality or 'unspecified'}. Do not label it.",
        interest_line,
        f"Live attempt count on this move: {student.attempt_count}.",
        f"ZPD: {student.zpd}.",
    ]


def _layer3(tutor: Layer3Tutor) -> list[str]:
    persona = _PERSONA_LINE.get(tutor.persona)
    lexicon = _LEXICON_LINE.get(tutor.lexicon)
    metaphors = _METAPHOR_LINE.get(tutor.metaphors)
    sidekick = _SIDEKICK_LINE.get(tutor.sidekick)
    if persona is None and lexicon is None and metaphors is None and sidekick is None:
        return [
            "Layer 3 — Tutor agent",
            "Use this voice inside the explanation. Do not name the persona or dump these settings as labels.",
            f"Persona to speak as: {tutor.persona}.",
            f"Lexicon to write with: {tutor.lexicon}.",
            f"Metaphors to draw a picture from, when they fit the idea: {tutor.metaphors}.",
            f"Teach-back sidekick: {tutor.sidekick}.",
        ]
    return [
        "Layer 3 — Tutor agent",
        "Use this voice inside the explanation. Do not name the persona or dump these settings as labels.",
        persona or f"Persona to speak as: {tutor.persona}.",
        lexicon or f"Lexicon to write with: {tutor.lexicon}.",
        metaphors or f"Metaphors to draw a picture from, when they fit the idea: {tutor.metaphors}.",
        sidekick or f"Teach-back sidekick: {tutor.sidekick}.",
    ]


def _pacing_lines(
    discourse: Layer4Discourse,
    beat: Layer1Beat,
    *,
    missed: bool,
    attempt_count: int = 0,
) -> list[str]:
    if _classic(discourse):
        lines = [
            f"Pacing: {discourse.pacing}.",
            "Teach, then ask. One question per turn, and it comes last.",
            "On Engage and Name, use a few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this quest's goal.",
            "Do not say hint to the student.",
        ]
        if missed:
            lines.append(
                "The student missed. Explain what they tried, what the idea actually is, and the next step. Do not give the worked answer yet. Do not ask a second question. Do not teach the next move."
            )
        elif beat.beat_role == "name":
            lines.append(
                "This Name turn teaches the idea, then asks one question. Do not teach the next move."
            )
        elif beat.beat_role == "engage":
            lines.append(
                "This Engage turn teaches the idea, then asks one question. Do not ask them to pick an answer."
            )
        return lines
    lines = [
        f"Pacing: {discourse.pacing}.",
        _opening_sentence(discourse),
        _question_rule(discourse.one_question),
        "Do not say hint to the student.",
    ]
    if missed:
        sentence = _miss_sentence(discourse, attempt_count)
        if sentence:
            lines.append(sentence)
    elif beat.beat_role == "name":
        lines.append(f"This Name turn follows that length. {_question_rule(discourse.one_question)} Do not teach the next move.")
    elif beat.beat_role == "engage":
        lines.append(
            f"This Engage turn follows that length. {_question_rule(discourse.one_question)} Do not ask them to pick an answer."
        )
    return lines


def _window_sentence(window: str) -> str:
    known = {
        "short": "short (1 miss). Hold that window before stating the passing answer.",
        "standard": "standard (2 misses). Hold that window before stating the passing answer.",
        "long": "long (3 misses). Hold that window before stating the passing answer.",
    }
    text = (window or "").strip().lower()
    if text in known:
        return f"Productive-struggle window: {known[text]}"
    return (
        f"Productive-struggle window: {window}. Hold that window before stating the passing answer."
    )


def _layer4(
    discourse: Layer4Discourse,
    beat: Layer1Beat,
    student: Layer2Student,
    tutor: Layer3Tutor | None = None,
    *,
    reveal: bool,
) -> list[str]:
    limit = struggle_limit(discourse.struggle_window)
    closed = reveal
    missed = student.attempt_count > 0 and not closed
    lines = [
        "Layer 4 — Discourse",
        f"Socratic strictness: {discourse.socratic_strictness}.",
        _window_sentence(discourse.struggle_window),
        *_pacing_lines(discourse, beat, missed=missed, attempt_count=student.attempt_count),
        f"Unsuccessful tries on this move: {student.attempt_count} of {limit}.",
    ]
    if closed and beat.beat_role == "show":
        lines.append(
            "The struggle window is over. Explain why the worked answer fits the success criterion. Do not invent a different fact. Do not ask another question. Set advance to true. That finishes the quest."
        )
    elif closed:
        lines.append(
            "The struggle window is over. Explain why the worked answer fits this move's criterion, including the correct choice if this move has one. Do not invent a different fact. Do not ask another question. Do not teach the next move. Set advance to true so this move ends."
        )
    elif beat.beat_role in {"engage", "name"}:
        if _classic(discourse):
            lines.append(
                "This turn teaches the idea before the question. Do not give a later move's answer."
            )
        else:
            lines.append(f"{_opening_sentence(discourse)} Do not give a later move's answer.")
    elif discourse.anti_spoiler and beat.beat_role == "teach_back":
        if tutor is not None and tutor.sidekick.strip().lower() in {"off", "none"}:
            lines.append(
                "Sidekick is off. The student explains the idea in their own words. Do not invent a partner, and do not state the answer before they try."
            )
        else:
            lines.append(
                "The student is correcting the sidekick. You may confirm a correct correction. Do not lecture the whole model, and do not state the answer before they try."
            )
    elif discourse.anti_spoiler:
        lines.append(
            "Anti-spoiler ban, for this window only: teaching the idea is allowed, stating the answer that passes the move is not. When this window ends, explain why the answer fits and let the move end."
        )
    else:
        lines.append(
            "The anti-spoiler ban is off. You may confirm a correct idea once the student has attempted it. When this window ends, explain why the answer fits if they are still stuck."
        )
    scope = _course_scope_rule(discourse, beat)
    if scope:
        lines.append(scope)
    return lines


def _layer5(affect: Layer5Affect) -> list[str]:
    lines = [
        "Layer 5 — Affect",
        f"Praise policy: {affect.praise}.",
    ]
    if affect.praise == "growth-mindset-only":
        lines.append(
            "Growth-mindset praise only. Praise the strategy, the effort, or the revision. Do not praise innate talent or call the student smart."
        )
    else:
        lines.append(
            "Growth-mindset praise is off. You may praise a correct result as well as the effort. Do not infer a mood, and do not schedule a memory."
        )
    return lines


def _layer6(meta: Layer6Metacognition) -> list[str]:
    return [
        "Layer 6 — Metacognition",
        f"Self-explanation: {meta.self_explanation}.",
        "Ask for one self-explanation line. Do not ask for a second explanation in the same turn.",
    ]


def _layer7(memory: Layer7Memory) -> list[str]:
    return [
        "Layer 7 — Memory",
        f"Schedule: {memory.schedule}.",
        "No live Leitner scheduling. Do not assign a review card, a spaced-repetition drill, or a future practice set.",
    ]


def _rules(
    student: Layer2Student,
    beat: Layer1Beat,
    tier: str,
    discourse: Layer4Discourse,
    *,
    reveal: bool,
    missed: bool,
) -> list[str]:
    classic = _classic(discourse)
    scope = _course_scope_rule(discourse, beat)
    if scope:
        lines = [
            "Rules:",
            f"- {scope}",
            "- Stay on the active move inside this course. Do not dump the whole quest or teach a later move.",
        ]
    else:
        lines = [
            "Rules:",
            "- Stay on the active move. If they wander off, answer in one sentence and come back.",
            "- Do not dump the whole quest or teach a later move.",
        ]
    if classic:
        lines.append("- Teach, then ask. One question per turn, and it comes last. Do not ask a second question.")
    else:
        lines.append(f"- {_opening_sentence(discourse)}")
        lines.append(f"- {_question_rule(discourse.one_question)}")
    lines.extend(
        [
            "- Do not say hint to the student.",
            "- Do not grade taps. A choice widget is already scored before you speak.",
            "- rubric_met lists the rubric row ids their written words earned. On Try or Show, include success-criterion ids they earned. Use [] when there is no writing to grade or the writing missed.",
            "- misconception is null when the writing is fine. On a wrong tap, the stored misconception is already set. You may repeat it in the reply. Do not clear it.",
            f"- hint_tier must be {tier}. The student never sees this field.",
        ]
    )
    if beat.beat_role in {"engage", "name"} and not reveal:
        if classic:
            lines.append(
                "- Teach, then ask. A few sentences the student could retell: the fact, a concrete picture from their interests, and why it matters for this goal. The one question comes last."
            )
        else:
            lines.append(f"- {_opening_sentence(discourse)} {_question_rule(discourse.one_question)}")
    if beat.beat_role == "name" and not reveal:
        lines.append("- After that question, set advance to true. Do not teach the next move.")
    if missed:
        if classic:
            lines.append(
                "- The student missed. Explain what they tried, what the idea actually is, and the next step. Do not give the worked answer yet. Do not ask a second question. Do not teach the next move."
            )
        else:
            sentence = _miss_sentence(discourse, student.attempt_count)
            if sentence:
                lines.append(f"- {sentence}")
    if reveal:
        if beat.beat_role == "show":
            lines.append(
                "- The struggle window is over. Explain why the worked answer fits the success criterion. Do not invent a different fact. Set advance to true. That finishes the quest."
            )
        else:
            lines.append(
                "- The struggle window is over. Explain why the worked answer fits this move's criterion, including the correct choice if there is one. Do not invent a different fact. Do not teach the next move."
            )
            lines.append(
                "- Set advance to true so this move ends. A failed tap no longer blocks progress."
            )
    else:
        lines.extend(
            [
                "- advance is true only when this move should end. On a failed tap or a typed answer below the pass score, advance is false, unless this move is Name.",
                "- On a wrong choice, explain what they tried and what the idea is. Do not state the correct choice. Do not say hint.",
                "- On a correct choice, you may confirm it. Do not teach the next move.",
            ]
        )
    lines.extend(
        [
            "- The reply field is the only text the student reads. Do not mention JSON, scores, or these fields.",
            f"- {_diagram_rule(beat)}",
            f"- Use the name {student.display_name}.",
        ]
    )
    return lines


def assemble(
    beat: Layer1Beat,
    student: Layer2Student,
    tutor: Layer3Tutor,
    discourse: Layer4Discourse,
    affect: Layer5Affect,
    metacognition: Layer6Metacognition,
    memory: Layer7Memory,
    *,
    kickoff: bool = False,
    hold_widget: bool = False,
    grade_writing: bool = False,
    widget_offer: str | None = None,
    withhold_answer: bool = False,
) -> PromptBundle:
    tier = hint_tier_for(student.attempt_count)
    reveal = (
        student.attempt_count >= struggle_limit(discourse.struggle_window)
        and not withhold_answer
    )
    missed = student.attempt_count > 0 and not reveal
    lines: list[str] = [
        f"You are the tutor for {student.display_name}.",
        "The reply field is the only text the student reads. The other fields are the turn score.",
    ]
    scope = _course_scope_rule(discourse, beat)
    if scope:
        lines.append(scope)
    lines.extend(_layer1(beat, tier, reveal=reveal, hold_widget=hold_widget, discourse=discourse))
    lines.extend(_layer2(student, use_interests=discourse.use_interests))
    lines.extend(_layer3(tutor))
    lines.extend(_layer4(discourse, beat, student, tutor, reveal=reveal))
    lines.extend(_layer5(affect))
    lines.extend(_layer6(metacognition))
    lines.extend(_layer7(memory))
    lines.append("\n".join(_rules(student, beat, tier, discourse, reveal=reveal, missed=missed)))
    if kickoff and not beat.finished:
        goal = beat.learning_goal.strip() or beat.quest_objective.strip() or beat.quest_title
        done = _criterion_line(beat)
        idea = beat.opening_idea.strip() or goal
        if _classic(discourse):
            lines.append(
                "\n".join(
                    [
                        f"{student.display_name} just opened this quest. The first reply states the learning goal, what finished work looks like, and a short teaching of the first idea.",
                        f"Quest: {beat.quest_code} {beat.quest_title}.",
                        f"Learning goal: {goal}",
                        f"Done looks like: {done}",
                        f"First idea to teach: {idea}",
                        "Teach that idea in a few sentences the student could retell. Use a concrete picture from their interests, and say why it matters for this goal.",
                        "Use only that goal and that idea. Do not invent a different topic, event, or skill.",
                        "Do not preview later moves or give away later answers.",
                        "Do not ask them to pick an answer. The choice widget is not on screen.",
                        "One question may come last, about the idea you just taught, not about a list of choices.",
                        "Set rubric_met to [], misconception to null, and advance to false.",
                    ]
                )
            )
        else:
            lines.append(
                "\n".join(
                    [
                        f"{student.display_name} just opened this quest. The first reply follows the instructive setting.",
                        f"Quest: {beat.quest_code} {beat.quest_title}.",
                        f"Learning goal: {goal}",
                        f"Done looks like: {done}",
                        f"First idea to teach: {idea}",
                        _opening_sentence(discourse),
                        _question_rule(discourse.one_question),
                        "Use only that goal and that idea. Do not invent a different topic, event, or skill.",
                        "Do not preview later moves or give away later answers.",
                        "Do not ask them to pick an answer. The choice widget is not on screen.",
                        "Set rubric_met to [], misconception to null, and advance to false.",
                    ]
                )
            )
    elif hold_widget and not beat.finished:
        if grade_writing:
            closing = (
                "They have replied in their own words. Mark rubric_met from those words. "
                "Do not advance. Do not state the answer."
            )
        else:
            closing = "Set rubric_met to [], misconception to null, and advance to false."
        if _classic(discourse):
            teach = "Explain the idea, then ask one question. Do not list choices or ask them to pick."
        else:
            teach = "\n".join(
                [
                    _opening_sentence(discourse),
                    _question_rule(discourse.one_question),
                    "Do not list choices or ask them to pick.",
                ]
            )
        lines.append(
            "\n".join(
                [
                    "The choice widget is not on screen yet. This reply teaches the move.",
                    teach,
                    "The choices stay off this turn. They appear later, only to check an idea the student has explained in their own words, or to give one structured try before the answer if they are stuck.",
                    closing,
                ]
            )
        )
    elif widget_offer == "ask" and not beat.finished:
        question = (beat.widget.prompt if beat.widget is not None else "").strip() or "Choose the best answer."
        missed_card = beat.widget is not None and beat.widget.grade is not None and not beat.widget.grade.passed
        if missed_card:
            lines.append(
                "\n".join(
                    [
                        "They missed the choice. Explain that miss in one or two sentences.",
                        f"Then your last sentence is exactly: {question}",
                        "The choice card is on screen for another try. Do not ask an open question.",
                        "Do not name the correct choice. Set advance to false.",
                    ]
                )
            )
        else:
            lines.append(
                "\n".join(
                    [
                        "The choice card is on screen.",
                        f"Your reply is exactly this question and nothing else: {question}",
                        "Do not ask an open question. Do not name the correct choice. Set advance to false.",
                    ]
                )
            )
    return PromptBundle(
        system_prompt="\n\n".join(lines),
        response_schema=RESPONSE_SCHEMA,
        temperature=TURN_TEMPERATURE,
    )
```

Source file `apps/api/app/prompt_loader.py`:

```python
"""Build the seven layer objects from a class and call the prompt engine.

The engine package itself does not import the database.
"""

from __future__ import annotations

from sqlalchemy.orm import object_session

from app.engine.assemble import assemble
from app.engine.choices import pacing_for, strictness_for
from app.engine.defaults import age_band_for
from app.engine.placeholders import memory_layer, metacognition_layer
from app.engine.types import (
    GoalPoint,
    HintLadder,
    Layer1Beat,
    Layer2Student,
    Layer3Tutor,
    Layer4Discourse,
    Layer5Affect,
    MisconceptionTrap,
    PromptBundle,
    RubricCriterion,
    WidgetChoice,
    WidgetGrade,
    WidgetTask,
)
from app.models import Beat, Session as TutorSession
from app.queries import (
    awaiting_tap_reply,
    choice_offer,
    choice_submitted,
    close_choice_widget,
    latest_result,
    locate_beat,
    ordered_beats,
)
from app.tutor_profile import load_profile

PASS_SCORE = 70


def course_scope_on(profile: object) -> bool:
    """Read the course guard. A missing attribute or a null older row counts as on."""
    value = getattr(profile, "stay_on_course", True)
    if value is None:
        return True
    return bool(value)


def _rows(beat: Beat) -> tuple[RubricCriterion, ...]:
    rows = []
    for row in beat.rubric or []:
        if isinstance(row, dict) and row.get("id"):
            rows.append(
                RubricCriterion(
                    id=str(row["id"]),
                    text=str(row.get("text") or ""),
                    weight=int(row.get("weight") or 0),
                )
            )
    return tuple(rows)


def _traps(beat: Beat) -> tuple[MisconceptionTrap, ...]:
    traps = []
    for trap in beat.misconception_map or []:
        if isinstance(trap, dict) and trap.get("trap"):
            traps.append(
                MisconceptionTrap(
                    id=str(trap.get("id") or "trap"),
                    trap=str(trap.get("trap") or ""),
                    note=str(trap.get("note") or ""),
                )
            )
    return tuple(traps)


def _ladder(beat: Beat) -> HintLadder:
    raw = beat.hint_ladder if isinstance(beat.hint_ladder, dict) else {}
    return HintLadder(
        nudge=str(raw.get("nudge") or ""),
        analogy=str(raw.get("analogy") or ""),
        scaffold=str(raw.get("scaffold") or ""),
    )


def _widget(
    tutor_session: TutorSession,
    beat: Beat,
    *,
    include_grade: bool,
    quiz: dict | None = None,
) -> WidgetTask | None:
    if quiz is None:
        quiz = beat.widget if isinstance(beat.widget, dict) else None
    if quiz is None:
        return None
    choices = tuple(
        WidgetChoice(
            id=str(choice.get("id")),
            text=str(choice.get("text") or ""),
            misconception=str(choice.get("misconception") or ""),
        )
        for choice in quiz.get("choices") or []
        if isinstance(choice, dict)
    )
    answer = quiz.get("answer")
    if isinstance(answer, list):
        shown: str | tuple[str, ...] = tuple(str(item) for item in answer)
    else:
        shown = str(answer or "")
    grade = None
    if include_grade:
        matches = [
            result
            for result in tutor_session.results
            if result.beat_id == beat.id
            and isinstance(result.choice, dict)
            and result.choice.get("ids")
        ]
        result = max(matches, key=lambda item: item.seq) if matches else None
        if result is not None and isinstance(result.choice, dict):
            ids = tuple(str(item) for item in result.choice.get("ids") or [])
            grade = WidgetGrade(
                correct=bool(result.passed and result.score == 100),
                score=result.score,
                passed=result.passed,
                misconception=result.misconception,
                choice_ids=ids,
                explanation=str(result.choice.get("explanation") or ""),
            )
    return WidgetTask(
        type=str(quiz.get("type") or ""),
        prompt=str(quiz.get("prompt") or ""),
        choices=choices,
        answer=shown,
        explain=bool(quiz.get("explain")),
        grade=grade,
    )


def _zpd(tutor_session: TutorSession, beat: Beat | None) -> str:
    if beat is None:
        return "on-level"
    result = latest_result(tutor_session, beat.id)
    if result is None:
        return "on-level"
    if not result.passed:
        return "support"
    if result.score >= 85:
        return "stretch"
    return "on-level"


def _criterion(quest) -> tuple[RubricCriterion, ...]:
    rows = []
    for row in quest.success_criterion or []:
        if isinstance(row, dict) and row.get("id"):
            rows.append(
                RubricCriterion(
                    id=str(row["id"]),
                    text=str(row.get("text") or ""),
                    weight=int(row.get("weight") or 0),
                )
            )
    return tuple(rows)


def _quest_objective(quest) -> str:
    goal = (quest.learning_goal or "").strip()
    if goal:
        return goal
    return (quest.title or "").strip()


def _failed(tutor_session: TutorSession, beat_id) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.beat_id == beat_id and not result.passed
    )


def _quest_walk(quest, *, reveal_close: bool) -> tuple[tuple[GoalPoint, ...], bool, str]:
    """Goals, then the close, from the quest the kid is playing.

    The close kind is always named. The question and choices stay hidden until
    the show move is on screen, so a later check is not sitting in the kickoff.
    """
    rows = sorted(quest.goals or [], key=lambda item: item.position)
    points = tuple(
        GoalPoint(row.learning_goal or "", row.success_criterion or "")
        for row in rows
        if str(row.learning_goal or "").strip() or str(row.success_criterion or "").strip()
    )
    close = quest.close
    if close is None:
        return points, False, ""
    kind = close.kind
    question = (close.question or "").strip()
    if kind == "none":
        return points, True, "Close: No questions."
    if kind == "essay":
        if not reveal_close:
            return points, False, "Close: Essay."
        return points, False, f"Close: Essay. Question: {question or 'Ask for a short written answer.'}"
    label = "Multi-choice" if kind == "multi" else "Single choice"
    if not reveal_close:
        return points, False, f"Close: {label}."
    choices = []
    for item in close.items or []:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            choices.append(str(item["text"]).strip())
    choice_line = f" Choices: {'; '.join(choices)}." if choices else ""
    return points, False, f"Close: {label}. Question: {question or 'Choose the best answer.'}{choice_line}"


def load_prompt(tutor_session: TutorSession, *, kickoff: bool = False) -> PromptBundle:
    quest = tutor_session.quest
    course = quest.course
    student = tutor_session.student
    beats = ordered_beats(quest)
    quest_objective = _quest_objective(quest)
    criterion = _criterion(quest)
    goal = (quest.learning_goal or "").strip()
    current = locate_beat(quest, tutor_session.current_beat_id)
    show = next((beat for beat in beats if beat.role == "show"), None)
    gate_cleared = False
    if show is not None:
        show_result = latest_result(tutor_session, show.id)
        gate_cleared = show_result is not None and show_result.passed
    source = current
    finished = current is None
    if source is None and beats:
        source = beats[-1]
    engage = next((item for item in beats if item.role == "engage"), None)
    opening_idea = (engage.prompt if engage is not None else "").strip()
    offer = None
    submitted = False
    answering_tap = False
    if source is not None and not finished:
        offer = choice_offer(tutor_session, source)
        submitted = choice_submitted(tutor_session, source)
        answering_tap = awaiting_tap_reply(tutor_session, source)
    close_card = close_choice_widget(quest, source) if source is not None and not finished else None
    offer = "ask" if close_card is not None and offer == "ask" else None
    include_widget = close_card is not None and (offer == "ask" or answering_tap)
    on_show = source is not None and show is not None and source.id == show.id
    show_card = close_choice_widget(quest, show) if show is not None else None
    reveal_close = finished or (on_show and (offer == "ask" or answering_tap or show_card is None))
    studio_goals, empty_close, close_line = _quest_walk(quest, reveal_close=reveal_close)
    held = False
    grade_writing = False
    withhold_answer = offer == "ask"
    if source is None:
        beat_layer = Layer1Beat(
            course_title=course.title,
            unit_title="",
            continuity="",
            quest_code=quest.code,
            quest_title=quest.title,
            beat_role="",
            beat_position=0,
            beat_count=0,
            bloom_level="",
            cognitive_load="",
            prompt="",
            rubric=(),
            misconceptions=(),
            hint_ladder=HintLadder("", "", ""),
            widget=None,
            pass_score=PASS_SCORE,
            gate_cleared=False,
            finished=True,
            quest_objective=quest_objective,
            beat_objectives=(),
            learning_goal=goal,
            success_criterion=criterion,
            requires_teach_back=bool(quest.requires_teach_back),
            opening_idea=opening_idea,
            course_code=course.code,
            goals=studio_goals,
            empty_close=empty_close,
            close_line=close_line,
        )
        attempt_count = 0
    else:
        beat_layer = Layer1Beat(
            course_title=course.title,
            unit_title="",
            continuity="",
            quest_code=quest.code,
            quest_title=quest.title,
            beat_role=source.role,
            beat_position=source.position,
            beat_count=len(beats),
            bloom_level=source.bloom_level,
            cognitive_load=source.cognitive_load,
            prompt=source.prompt,
            rubric=_rows(source),
            misconceptions=_traps(source),
            hint_ladder=_ladder(source),
            widget=None
            if finished or not include_widget
            else _widget(
                tutor_session,
                source,
                include_grade=submitted or answering_tap,
                quiz=close_card,
            ),
            pass_score=PASS_SCORE,
            gate_cleared=gate_cleared,
            finished=finished,
            quest_objective=quest_objective,
            beat_objectives=(),
            learning_goal=goal,
            success_criterion=criterion,
            requires_teach_back=bool(quest.requires_teach_back),
            opening_idea=opening_idea,
            course_code=course.code,
            goals=studio_goals,
            empty_close=empty_close,
            close_line=close_line,
        )
        attempt_count = 0 if finished or current is None else _failed(tutor_session, current.id)
    interests = tuple(str(item) for item in (student.interests or []) if str(item).strip())
    student_layer = Layer2Student(
        display_name=student.display_name,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level,
        modality=student.modality,
        interests=interests,
        attempt_count=attempt_count,
        zpd=_zpd(tutor_session, None if finished else current),
    )
    profile = load_profile(object_session(tutor_session))
    level = min(5, max(1, int(profile.instructive or 3)))
    tutor_layer = Layer3Tutor(
        persona=profile.persona,
        lexicon=profile.lexicon,
        metaphors=profile.metaphors,
        sidekick=profile.sidekick,
    )
    discourse = Layer4Discourse(
        socratic_strictness=strictness_for(level),
        struggle_window=profile.struggle_window,
        anti_spoiler=bool(profile.anti_spoiler),
        pacing=pacing_for(level),
        instructive=level,
        one_question=bool(profile.one_question),
        use_interests=bool(profile.use_interests),
        stay_on_course=course_scope_on(profile),
    )
    affect = Layer5Affect(
        praise="growth-mindset-only" if profile.growth_praise else "result-or-effort"
    )
    return assemble(
        beat_layer,
        student_layer,
        tutor_layer,
        discourse,
        affect,
        metacognition_layer(),
        memory_layer(),
        kickoff=kickoff,
        hold_widget=held,
        grade_writing=grade_writing,
        widget_offer=offer,
        withhold_answer=withhold_answer,
    )
```

Source file `apps/api/app/tutor_profile.py`:

```python
"""The one default tutor profile. Every student uses this row."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.engine.choices import PERSONA_VOICE
from app.models import TutorProfile

PROFILE_ID = "default"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def default_row() -> TutorProfile:
    return TutorProfile(
        id=PROFILE_ID,
        instructive=3,
        persona="curious-co-explorer",
        lexicon="middle-grade-vivid",
        voice_override=False,
        metaphors="playground-sports",
        sidekick="bumbling-partner",
        struggle_window="standard",
        anti_spoiler=True,
        one_question=True,
        use_interests=True,
        stay_on_course=True,
        growth_praise=True,
        updated_at=_now(),
    )


def _fill(row: TutorProfile, source: TutorProfile) -> TutorProfile:
    row.instructive = source.instructive
    row.persona = source.persona
    row.lexicon = source.lexicon
    row.voice_override = source.voice_override
    row.metaphors = source.metaphors
    row.sidekick = source.sidekick
    row.struggle_window = source.struggle_window
    row.anti_spoiler = source.anti_spoiler
    row.one_question = source.one_question
    row.use_interests = source.use_interests
    row.stay_on_course = source.stay_on_course
    row.growth_praise = source.growth_praise
    row.updated_at = _now()
    return row


def ensure_default_profile(db: Session) -> TutorProfile:
    """Insert the default row when it is missing. Never overwrite a saved profile."""
    row = db.get(TutorProfile, PROFILE_ID)
    if row is not None:
        return row
    row = default_row()
    db.add(row)
    db.flush()
    return row


def reset_default_profile(db: Session) -> TutorProfile:
    """Put the singleton back to the built-in default. Tests use this."""
    row = db.get(TutorProfile, PROFILE_ID)
    if row is None:
        row = default_row()
        db.add(row)
    else:
        _fill(row, default_row())
    db.flush()
    return row


def load_profile(db: Session | None) -> TutorProfile:
    """The row the prompt assembler and the struggle window read.

    A missing row uses the same defaults as a fresh database. Callers that
    can write should use ensure_default_profile instead.
    """
    if db is None:
        return default_row()
    row = db.get(TutorProfile, PROFILE_ID)
    if row is None:
        return default_row()
    return row


def save_profile(
    db: Session,
    *,
    instructive: int,
    persona: str,
    lexicon: str,
    voice_override: bool,
    metaphors: str,
    sidekick: str,
    struggle_window: str,
    anti_spoiler: bool,
    one_question: bool,
    use_interests: bool,
    stay_on_course: bool,
    growth_praise: bool,
) -> TutorProfile:
    row = ensure_default_profile(db)
    if voice_override and lexicon != PERSONA_VOICE[persona]:
        stored_lexicon = lexicon
        stored_override = True
    else:
        stored_lexicon = PERSONA_VOICE[persona]
        stored_override = False
    row.instructive = instructive
    row.persona = persona
    row.lexicon = stored_lexicon
    row.voice_override = stored_override
    row.metaphors = metaphors
    row.sidekick = sidekick
    row.struggle_window = struggle_window
    row.anti_spoiler = anti_spoiler
    row.one_question = one_question
    row.use_interests = use_interests
    row.stay_on_course = stay_on_course
    row.growth_praise = growth_praise
    row.updated_at = _now()
    db.flush()
    return row
```

Source file `apps/api/app/flow.py`:

```python
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engine.assemble import hint_tier_for, struggle_limit
from app.engine.defaults import profile_for_age
from app.tutor_profile import load_profile
from app.models import Beat, BeatResult, Course, Message, ModelPrompt, Quest, Session as TutorSession, Student
from app.prompt_loader import PASS_SCORE
from app.queries import (
    awaiting_tap_reply,
    choice_offer,
    choice_submitted,
    close_choice_widget,
    latest_result,
    locate_beat,
    next_position,
    ordered_beats,
    replied_after_teaching,
)
from app.widgets import choice_ids, grade_choice, hint_text

def now() -> datetime:
    return datetime.now(timezone.utc)


def blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _unique_slug(taken, title: str, fallback: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or fallback
    slug = base
    suffix = 2
    while taken(slug):
        slug = f"{base[:40]}-{suffix}"
        suffix += 1
    return slug


def unique_student_slug(db: Session, name: str) -> str:
    return _unique_slug(
        lambda slug: db.scalar(select(Student.id).where(Student.slug == slug)) is not None,
        name,
        "learner",
    )


def unique_course_code(db: Session, title: str) -> str:
    return _unique_slug(
        lambda code: db.scalar(select(Course.id).where(Course.code == code)) is not None,
        title,
        "course",
    )


def apply_student_profile(student: Student, *, provided: set[str]) -> None:
    """Fill any layer field the request left out from the age-band defaults."""
    profile = profile_for_age(student.age)
    if "reading_level" not in provided:
        student.reading_level = profile.reading_level
    if "modality" not in provided:
        student.modality = profile.modality
    if "interests" not in provided:
        student.interests = []
    if "tutor_persona" not in provided:
        student.tutor_persona = profile.persona
    if "tutor_lexicon" not in provided:
        student.tutor_lexicon = profile.lexicon
    if "tutor_metaphors" not in provided:
        student.tutor_metaphors = profile.metaphors
    if "tutor_sidekick" not in provided:
        student.tutor_sidekick = profile.sidekick
    if "tutor_socratic_strictness" not in provided:
        student.tutor_socratic_strictness = profile.socratic_strictness
    if "tutor_struggle_window" not in provided:
        student.tutor_struggle_window = profile.struggle_window
    if "tutor_anti_spoiler" not in provided:
        student.tutor_anti_spoiler = profile.anti_spoiler
    if "tutor_pacing" not in provided:
        student.tutor_pacing = profile.pacing


def open_session(db: Session, student_id: uuid.UUID, quest_id: uuid.UUID, fresh: bool) -> TutorSession:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    from app.queries import load_quest

    quest = load_quest(db, quest_id)
    if not fresh:
        existing = db.scalar(
            select(TutorSession)
            .where(
                TutorSession.student_id == student.id,
                TutorSession.quest_id == quest.id,
                TutorSession.status == "in_progress",
            )
            .order_by(TutorSession.updated_at.desc())
        )
        if existing is not None:
            return existing
    beats = ordered_beats(quest)
    if not beats:
        raise HTTPException(status_code=400, detail="This quest does not have a move.")
    tutor_session = TutorSession(
        student_id=student.id,
        quest_id=quest.id,
        current_beat_id=beats[0].id,
        status="in_progress",
        updated_at=now(),
    )
    db.add(tutor_session)
    db.flush()
    return tutor_session


def append_message(
    db: Session,
    tutor_session: TutorSession,
    role: str,
    content: str,
    client_id: str | None,
) -> Message:
    if client_id:
        existing = db.scalar(select(Message).where(Message.client_id == client_id))
        if existing is not None:
            if existing.session_id != tutor_session.id:
                raise HTTPException(status_code=409, detail="That client_id belongs to another session.")
            existing.content = content
            tutor_session.updated_at = now()
            return existing
    seq = db.scalar(select(func.max(Message.seq)).where(Message.session_id == tutor_session.id))
    message = Message(
        session_id=tutor_session.id,
        role=role,
        content=content,
        client_id=client_id,
        seq=(seq or 0) + 1,
    )
    db.add(message)
    tutor_session.updated_at = now()
    db.flush()
    return message


def append_model_prompt(
    db: Session,
    tutor_session: TutorSession,
    system_prompt: str,
    messages: list,
    model: str,
    message_id: uuid.UUID | None = None,
) -> ModelPrompt:
    linked = None
    if message_id is not None:
        linked = db.get(Message, message_id)
        if linked is None or linked.session_id != tutor_session.id:
            raise HTTPException(status_code=400, detail="That message is not part of this class.")
    seq = db.scalar(
        select(func.max(ModelPrompt.seq)).where(ModelPrompt.session_id == tutor_session.id)
    )
    row = ModelPrompt(
        session_id=tutor_session.id,
        message_id=linked.id if linked is not None else None,
        seq=(seq or 0) + 1,
        system_prompt=system_prompt,
        messages=messages,
        model=model.strip(),
    )
    db.add(row)
    db.flush()
    return row


def failed_attempts(tutor_session: TutorSession, beat_id: uuid.UUID) -> int:
    return sum(1 for result in tutor_session.results if result.beat_id == beat_id and not result.passed)


def record_result(
    db: Session,
    tutor_session: TutorSession,
    score: int,
    passed: bool,
    feedback: str,
    rubric_met: list | None = None,
    misconception: str | None = None,
    hint_tier: str | None = None,
    choice: dict | None = None,
) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    seq = db.scalar(
        select(func.max(BeatResult.seq)).where(BeatResult.session_id == tutor_session.id)
    )
    result = BeatResult(
        session_id=tutor_session.id,
        beat_id=beat.id,
        seq=(seq or 0) + 1,
        score=score,
        passed=passed,
        feedback=feedback.strip(),
        rubric_met=list(rubric_met or []),
        misconception=blank_to_none(misconception),
        hint_tier=hint_tier,
        choice=choice,
    )
    db.add(result)
    tutor_session.updated_at = now()
    db.flush()
    db.expire(tutor_session, ["results"])
    return {
        "ok": True,
        "beat_id": str(beat.id),
        "role": beat.role,
        "score": score,
        "passed": passed,
        "feedback": result.feedback,
    }


def advance(db: Session, tutor_session: TutorSession, *, allow_unpassed: bool = False) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if tutor_session.status == "completed" or beat is None:
        return {"ok": False, "reason": "This quest is already finished."}
    result = latest_result(tutor_session, beat.id)
    if result is None or (not result.passed and not allow_unpassed):
        return {"ok": False, "reason": "This move needs a passing result before moving on."}
    beats = ordered_beats(tutor_session.quest)
    index = next(i for i, item in enumerate(beats) if item.id == beat.id)
    tutor_session.updated_at = now()
    if index + 1 >= len(beats):
        tutor_session.current_beat_id = None
        tutor_session.status = "completed"
        db.flush()
        return {"ok": True, "completed": True, "current_beat": None}
    nxt = beats[index + 1]
    tutor_session.current_beat_id = nxt.id
    db.flush()
    return {
        "ok": True,
        "completed": False,
        "from_role": beat.role,
        "current_beat": {"role": nxt.role, "position": nxt.position},
    }


def beat_state(
    beat: Beat,
    current_id: uuid.UUID | None,
    result: BeatResult | None,
    seen_current: bool,
    quest_complete: bool,
) -> str:
    if quest_complete:
        if result is not None and result.passed:
            return "passed"
        if result is not None:
            return "failed"
        return "done"
    if beat.id == current_id:
        return "current"
    if seen_current:
        return "upcoming"
    if result is not None and result.passed:
        return "passed"
    if result is not None:
        return "failed"
    return "done"


def grade_widget(
    db: Session,
    tutor_session: TutorSession,
    choice: str | list[str],
    explanation: str,
) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished, so there is nothing to score."}
    quiz = close_choice_widget(tutor_session.quest, beat)
    if quiz is None:
        return {"ok": False, "reason": "This move is a typed reply, not a choice widget."}
    ids = choice_ids(choice)
    if awaiting_tap_reply(tutor_session, beat):
        latest = latest_result(tutor_session, beat.id)
        same = (
            latest is not None
            and isinstance(latest.choice, dict)
            and list(latest.choice.get("ids") or []) == ids
        )
        if same:
            return {
                "ok": True,
                "correct": bool(latest.passed),
                "passed": latest.passed,
                "score": latest.score,
                "misconception": latest.misconception,
                "hint_tier": latest.hint_tier,
                "hint_text": hint_text(beat.hint_ladder, latest.hint_tier or "nudge"),
            }
    if not ids:
        return {"ok": False, "reason": "Choose an answer before sending."}
    graded = grade_choice(
        quiz, ids if quiz.get("type") in {"multi", "order"} else ids[0]
    )
    passed = graded["score"] >= PASS_SCORE
    tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
    feedback = "That choice is right." if graded["correct"] else "That choice is not right."
    if graded["misconception"]:
        feedback = f"{feedback} {graded['misconception']}"
    recorded = record_result(
        db,
        tutor_session,
        graded["score"],
        passed,
        feedback.strip(),
        misconception=graded["misconception"],
        hint_tier=tier,
        choice={"ids": ids, "explanation": explanation.strip()},
    )
    return {
        **recorded,
        "correct": graded["correct"],
        "misconception": graded["misconception"],
        "hint_tier": tier,
        "hint_text": hint_text(beat.hint_ladder, tier),
    }


def _window_closed(db: Session, tutor_session: TutorSession, beat: Beat) -> bool:
    return failed_attempts(tutor_session, beat.id) >= struggle_limit(
        load_profile(db).struggle_window
    )


def _weights(beat: Beat) -> dict[str, int]:
    weights: dict[str, int] = {}
    for row in beat.rubric or []:
        if isinstance(row, dict) and row.get("id"):
            weights[str(row["id"])] = int(row.get("weight") or 0)
    return weights


def _criterion_met(quest: Quest, rubric_met: list[str]) -> bool:
    weights: dict[str, int] = {}
    for row in quest.success_criterion or []:
        if isinstance(row, dict) and row.get("id"):
            weights[str(row["id"])] = int(row.get("weight") or 0)
    total = sum(weights.values())
    if total <= 0:
        return False
    earned = sum(weights[row_id] for row_id in rubric_met if row_id in weights)
    return round(100 * earned / total) >= PASS_SCORE


def _complete(db: Session, tutor_session: TutorSession) -> dict:
    tutor_session.current_beat_id = None
    tutor_session.status = "completed"
    tutor_session.updated_at = now()
    db.flush()
    return {"ok": True, "completed": True, "current_beat": None}


def _advance_move(
    db: Session,
    tutor_session: TutorSession,
    beat: Beat,
    met: list[str],
    *,
    reveal: bool,
    advance_flag: bool,
    passed: bool,
) -> bool:
    """Leave this move. A met criterion on Try or Show ends the quest."""
    close = tutor_session.quest.close
    if beat.role == "show" and close is not None and close.kind == "none" and advance_flag:
        return bool(_complete(db, tutor_session).get("ok"))
    if beat.role in {"try", "show"} and _criterion_met(tutor_session.quest, met):
        return bool(_complete(db, tutor_session).get("ok"))
    if beat.role == "show" and reveal and advance_flag:
        return bool(_complete(db, tutor_session).get("ok"))
    if beat.role == "name" or (advance_flag and (passed or reveal)):
        moved = advance(db, tutor_session, allow_unpassed=bool(beat.role == "name" or (reveal and not passed)))
        return bool(moved.get("ok"))
    return False


def apply_turn_score(
    db: Session,
    tutor_session: TutorSession,
    rubric_met: list[str],
    misconception: str | None,
    advance_flag: bool,
) -> dict:
    beat = locate_beat(tutor_session.quest, tutor_session.current_beat_id)
    if beat is None:
        return {"ok": False, "reason": "This quest is finished.", "advanced": False}
    weights = _weights(beat)
    met = [row_id for row_id in rubric_met if row_id in weights]
    latest = latest_result(tutor_session, beat.id)
    quiz = close_choice_widget(tutor_session.quest, beat)
    note = blank_to_none(misconception)
    submitted = choice_submitted(tutor_session, beat) if quiz is not None else True
    reveal = _window_closed(db, tutor_session, beat) and submitted
    offer = choice_offer(tutor_session, beat) if quiz is not None else None
    answering_tap = awaiting_tap_reply(tutor_session, beat) if quiz is not None else False
    if quiz is not None and offer is None and not answering_tap:
        if not replied_after_teaching(tutor_session, beat):
            return {
                "ok": True,
                "advanced": False,
                "graded_by": "opening",
                "passed": False,
                "score": 0,
                "feedback": "This move is still being taught.",
            }
        total = sum(weights.values()) or 0
        earned = sum(weights[row_id] for row_id in met)
        score = round(100 * earned / total) if total else 0
        passed = score >= PASS_SCORE
        feedback = "That meets this move." if passed else "Not yet. The idea still needs another try."
        recorded = record_result(
            db,
            tutor_session,
            score,
            passed,
            feedback,
            rubric_met=met,
            misconception=None if passed else note,
            hint_tier=hint_tier_for(failed_attempts(tutor_session, beat.id)),
        )
        return {**recorded, "advanced": False, "graded_by": "discussion"}
    if beat.role == "name":
        recorded = record_result(
            db,
            tutor_session,
            100,
            True,
            "The idea is connected. The next move can start.",
            rubric_met=met,
            hint_tier=hint_tier_for(failed_attempts(tutor_session, beat.id)),
        )
        advanced = _advance_move(
            db,
            tutor_session,
            beat,
            met,
            reveal=reveal,
            advance_flag=True,
            passed=True,
        )
        return {**recorded, "advanced": advanced, "graded_by": "model"}
    if (
        quiz is not None
        and answering_tap
        and latest is not None
        and isinstance(latest.choice, dict)
        and latest.choice.get("ids")
    ):
        latest.rubric_met = met
        if not latest.misconception and note and not latest.passed:
            latest.misconception = note
        tutor_session.updated_at = now()
        db.flush()
        should_advance = (
            bool(advance_flag and latest.passed)
            or (latest.passed and not quiz.get("explain"))
            or bool(advance_flag and reveal)
            or bool(beat.role in {"try", "show"} and _criterion_met(tutor_session.quest, met))
        )
        advanced = False
        if should_advance:
            advanced = _advance_move(
                db,
                tutor_session,
                beat,
                met,
                reveal=reveal,
                advance_flag=advance_flag or bool(latest.passed and not quiz.get("explain")),
                passed=latest.passed,
            )
        return {
            "ok": True,
            "graded_by": "widget",
            "score": latest.score,
            "passed": latest.passed,
            "advanced": advanced,
            "misconception": latest.misconception,
        }
    if quiz is not None and offer is not None:
        return {
            "ok": True,
            "advanced": False,
            "graded_by": "widget",
            "passed": False,
            "score": 0,
            "feedback": "Choose an answer on the widget.",
        }
    if quiz is not None:
        recorded = record_result(
            db,
            tutor_session,
            0,
            False,
            "Choose an answer on the widget.",
            rubric_met=met,
            hint_tier=hint_tier_for(failed_attempts(tutor_session, beat.id)),
        )
        return {**recorded, "advanced": False, "graded_by": "widget"}
    total = sum(weights.values()) or 0
    earned = sum(weights[row_id] for row_id in met)
    score = round(100 * earned / total) if total else 0
    passed = score >= PASS_SCORE
    tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
    feedback = "That meets this move." if passed else "Not yet. The idea still needs another try."
    if reveal and not passed:
        feedback = "The struggle window is over. A worked answer can move this on."
    recorded = record_result(
        db,
        tutor_session,
        score,
        passed,
        feedback,
        rubric_met=met,
        misconception=None if passed else note,
        hint_tier=tier,
    )
    advanced = False
    close = tutor_session.quest.close
    empty_close = beat.role == "show" and close is not None and close.kind == "none"
    if empty_close and advance_flag:
        advanced = _advance_move(
            db,
            tutor_session,
            beat,
            met,
            reveal=True,
            advance_flag=True,
            passed=passed,
        )
    elif advance_flag and (passed or reveal):
        advanced = _advance_move(
            db,
            tutor_session,
            beat,
            met,
            reveal=reveal,
            advance_flag=True,
            passed=passed,
        )
    elif beat.role in {"try", "show"} and _criterion_met(tutor_session.quest, met):
        advanced = _advance_move(
            db,
            tutor_session,
            beat,
            met,
            reveal=reveal,
            advance_flag=False,
            passed=passed,
        )
    return {**recorded, "advanced": advanced, "graded_by": "model"}


def blank_beats(criterion: list[dict] | None = None) -> list[dict]:
    """A starter cycle: engage, try, name, and show. Show holds the criterion."""
    rows = criterion or [
        {"id": "part-a", "text": "Names the first part of the idea.", "weight": 50},
        {"id": "part-b", "text": "Names the second part of the idea.", "weight": 50},
    ]
    roles = (
        ("engage", "understand", "The idea has one fact, a picture the student can retell, and a reason it matters for this goal."),
        ("try", "apply", "Teach this goal in words the student could retell."),
        ("name", "understand", "The try and the goal are the same idea: name the fact and why it matters."),
        ("show", "analyze", "Ask for the evidence in the success criterion."),
    )
    beats = []
    for role, bloom, prompt in roles:
        widget = None
        rubric = rows if role == "show" else [
            {"id": "part-a", "text": "Names the first part of the idea.", "weight": 50},
            {"id": "part-b", "text": "Names the second part of the idea.", "weight": 50},
        ]
        beats.append(
            {
                "role": role,
                "bloom_level": bloom,
                "cognitive_load": "medium",
                "prompt": prompt,
                "rubric": rubric,
                "misconception_map": [
                    {
                        "id": "nearby",
                        "trap": "A nearby idea answers this question.",
                        "note": "Stay on the idea named in the quest.",
                    }
                ],
                "hint_ladder": {
                    "nudge": "What is the question actually asking?",
                    "analogy": "Picture the idea with one concrete object.",
                    "scaffold": "The first part is ____. The second part is ____.",
                },
                "widget": widget,
            }
        )
    return beats
```

Source file `apps/api/app/queries.py`:

```python
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session, selectinload

from app.engine.assemble import struggle_limit
from app.models import Beat, BeatResult, Course, Message, Quest, Session as TutorSession
from app.tutor_profile import load_profile

KICKOFF_TEXT = "Hi! I'm ready to learn."


def load_course(db: Session, course_id: uuid.UUID) -> Course:
    course = db.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(
            selectinload(Course.quests).selectinload(Quest.goals),
            selectinload(Course.quests).selectinload(Quest.close),
            selectinload(Course.quests).selectinload(Quest.beats),
        )
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def load_quest(db: Session, quest_id: uuid.UUID) -> Quest:
    quest = db.scalar(
        select(Quest)
        .where(Quest.id == quest_id)
        .options(
            selectinload(Quest.beats),
            selectinload(Quest.goals),
            selectinload(Quest.close),
            selectinload(Quest.course),
        )
    )
    if quest is None:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quest


def load_session(db: Session, session_id: uuid.UUID) -> TutorSession:
    tutor_session = db.scalar(
        select(TutorSession)
        .where(TutorSession.id == session_id)
        .options(
            selectinload(TutorSession.student),
            selectinload(TutorSession.quest).selectinload(Quest.beats),
            selectinload(TutorSession.quest).selectinload(Quest.goals),
            selectinload(TutorSession.quest).selectinload(Quest.close),
            selectinload(TutorSession.quest).selectinload(Quest.course),
            selectinload(TutorSession.messages),
            selectinload(TutorSession.prompts),
            selectinload(TutorSession.results).selectinload(BeatResult.beat).selectinload(Beat.quest),
        )
    )
    if tutor_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return tutor_session


def ordered_beats(quest: Quest) -> list[Beat]:
    return sorted(quest.beats, key=lambda beat: beat.position)


def locate_beat(quest: Quest, beat_id: uuid.UUID | None) -> Beat | None:
    if beat_id is None:
        return None
    for beat in ordered_beats(quest):
        if beat.id == beat_id:
            return beat
    return None


def latest_result(tutor_session: TutorSession, beat_id: uuid.UUID) -> BeatResult | None:
    matches = [result for result in tutor_session.results if result.beat_id == beat_id]
    if not matches:
        return None
    return max(matches, key=lambda result: result.seq)


def _message_text(message: Message) -> str:
    return (message.content or "").strip()


def _own_words(message: Message) -> bool:
    text = _message_text(message)
    return message.role == "user" and bool(text) and text != KICKOFF_TEXT


def _failed_attempts(tutor_session: TutorSession, beat_id: uuid.UUID) -> int:
    return sum(
        1
        for result in tutor_session.results
        if result.beat_id == beat_id and not result.passed
    )


def _move_messages(tutor_session: TutorSession, beat: Beat) -> list[Message]:
    """Talk that belongs to this move, after the previous move's result."""
    beats = ordered_beats(tutor_session.quest)
    index = next((i for i, item in enumerate(beats) if item.id == beat.id), None)
    messages = [message for message in tutor_session.messages if _message_text(message)]
    if index is None:
        return []
    if index == 0:
        return messages
    previous = latest_result(tutor_session, beats[index - 1].id)
    if previous is None or previous.created_at is None:
        return []
    return [
        message
        for message in messages
        if message.created_at is not None and message.created_at > previous.created_at
    ]


def _latest_choice(tutor_session: TutorSession, beat: Beat) -> BeatResult | None:
    matches = [
        result
        for result in tutor_session.results
        if result.beat_id == beat.id
        and isinstance(result.choice, dict)
        and result.choice.get("ids")
    ]
    if not matches:
        return None
    return max(matches, key=lambda result: result.seq)


def choice_submitted(tutor_session: TutorSession, beat: Beat) -> bool:
    return _latest_choice(tutor_session, beat) is not None


def _offer_span(tutor_session: TutorSession, beat: Beat) -> tuple[list[Message], bool]:
    """Messages since the last submitted choice.

    The submitted choice is saved before the tutor replies, so a user message
    that arrives before that reply is the choice itself, not a new explanation.
    """
    messages = _move_messages(tutor_session, beat)
    latest = _latest_choice(tutor_session, beat)
    if latest is None or latest.created_at is None:
        return messages, False
    span = [
        message
        for message in messages
        if message.created_at is not None and message.created_at > latest.created_at
    ]
    cleaned: list[Message] = []
    seen_tutor = False
    for message in span:
        if message.role == "assistant":
            seen_tutor = True
            cleaned.append(message)
        elif message.role == "user" and not seen_tutor:
            continue
        else:
            cleaned.append(message)
    return cleaned, True


def _check_ready(span: list[Message]) -> bool:
    """True once a tutor reply follows the student's own words.

    The first tutor message is not enough, and neither is the move role.
    """
    seen_tutor = False
    seen_words = False
    ready = False
    for message in span:
        if message.role == "assistant":
            if seen_words:
                ready = True
            seen_tutor = True
        elif _own_words(message) and seen_tutor:
            seen_words = True
            ready = False
    return ready


def replied_after_teaching(tutor_session: TutorSession, beat: Beat) -> bool:
    """The idea has been said, and the student has answered in their own words."""
    span, _submitted = _offer_span(tutor_session, beat)
    seen_tutor = False
    for message in span:
        if message.role == "assistant":
            seen_tutor = True
        elif _own_words(message) and seen_tutor:
            return True
    return False


def awaiting_tap_reply(tutor_session: TutorSession, beat: Beat) -> bool:
    """True after a choice is stored and before the tutor has answered it."""
    latest = _latest_choice(tutor_session, beat)
    if latest is None or latest.created_at is None:
        return False
    for message in _move_messages(tutor_session, beat):
        if message.created_at is None or message.created_at <= latest.created_at:
            continue
        if message.role == "assistant":
            return False
    return True


def _placeholder_widget(widget: dict) -> bool:
    choices = widget.get("choices") or []
    return any(
        isinstance(choice, dict) and choice.get("text") == "The choice that matches the quest idea."
        for choice in choices
    )


def _widget_from_close(close) -> dict | None:
    items = close.items if isinstance(close.items, list) else []
    choices = []
    answers = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        choice_id = f"c{index}"
        choices.append(
            {
                "id": choice_id,
                "text": text,
                "misconception": "" if item.get("correct") else "That choice answers a different question.",
            }
        )
        if item.get("correct"):
            answers.append(choice_id)
    if len(choices) < 2:
        return None
    if not answers:
        answers = [choices[0]["id"]]
    kind = "multi" if close.kind == "multi" else "single"
    return {
        "type": kind,
        "prompt": (close.question or "").strip() or "Choose the best answer.",
        "choices": choices,
        "answer": answers if kind == "multi" else answers[0],
        "explain": False,
        "misconception": "Stay on the question this quest asked.",
    }


def close_choice_widget(quest, beat: Beat) -> dict | None:
    """The quest close, when it is a single or multi-choice card.

    Engage, Name, and Try stay talk. A placeholder Try widget is not a card.
    Essay and empty closes are typed, or they end the quest.
    """
    if beat is None or beat.role != "show":
        return None
    close = getattr(quest, "close", None)
    if close is not None and close.kind in {"none", "essay"}:
        return None
    widget = beat.widget if isinstance(beat.widget, dict) else None
    if widget and (_placeholder_widget(widget) or widget.get("type") not in {"single", "multi", "flaw"}):
        widget = None
    if widget is not None:
        return widget
    if close is not None and close.kind in {"single", "multi"}:
        return _widget_from_close(close)
    return None


def _window_closed_on(tutor_session: TutorSession, beat: Beat) -> bool:
    if _latest_choice(tutor_session, beat) is None:
        return False
    window = load_profile(object_session(tutor_session)).struggle_window or "standard"
    return _failed_attempts(tutor_session, beat.id) >= struggle_limit(window)


def choice_offer(tutor_session: TutorSession, beat: Beat) -> str | None:
    """"ask" when this turn's prompt should know the close card is on screen.

    The card is the quest close, and only the close. After a wrong choice the
    window can replace another try with the worked answer.
    """
    if close_choice_widget(tutor_session.quest, beat) is None:
        return None
    if tutor_session.current_beat_id != beat.id:
        return None
    if _window_closed_on(tutor_session, beat):
        return None
    return "ask"


def _invited(tutor_session: TutorSession, beat: Beat) -> bool:
    """The reply that asks for the pick is already in the chat."""
    latest = _latest_choice(tutor_session, beat)
    for message in _move_messages(tutor_session, beat):
        if latest is not None and latest.created_at is not None:
            if message.created_at is None or message.created_at <= latest.created_at:
                continue
        if message.role == "assistant" and _message_text(message):
            return True
    return False


def choice_widget_visible(tutor_session: TutorSession, beat: Beat) -> bool:
    """The card hangs on the inviting reply, not on a teaching turn."""
    if choice_offer(tutor_session, beat) is None:
        return False
    return _invited(tutor_session, beat)


def next_position(values: list[int]) -> int:
    return (max(values) if values else 0) + 1


def quest_in_use(db: Session, quest_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(func.count()).select_from(TutorSession).where(TutorSession.quest_id == quest_id)
        )
    )
```

Source file `apps/api/app/widgets.py`:

```python
"""Grade a choice widget, and check a lesson diagram before it reaches the client.

The model never scores these taps. A diagram is a checked description the app draws.
The model never returns an image file, an image URL, or a free-form drawing prompt.
"""

from __future__ import annotations

import math
import re

HINT_TIERS = ("nudge", "analogy", "scaffold")

# Kinds the reply schema may name. This pass draws a triangle only.
NAMED_DIAGRAM_KINDS = frozenset({"triangle", "graph", "map"})
_TRIANGLE_KEYS = frozenset({"kind", "sides", "angles", "right_angle"})
_SIDE_KEYS = frozenset({"label", "length"})
_ANGLE_KEYS = frozenset({"label", "degrees"})
_GEOMETRY = "geometry"
_ANGLE_SUM = 180.0
_SUM_TOLERANCE = 1.0
_RIGHT_TOLERANCE = 1.0
_RATIO_TOLERANCE = 0.05
_MAX_LABEL = 24
_MAX_SIDE = 10_000.0
_MARKUP = re.compile(r"[<>&]|://|www\.|javascript:", re.IGNORECASE)


def hint_tier_for(failed_attempts: int) -> str:
    if failed_attempts <= 0:
        return "nudge"
    if failed_attempts == 1:
        return "analogy"
    return "scaffold"


def hint_text(ladder: dict | None, tier: str) -> str:
    if not isinstance(ladder, dict):
        return ""
    return str(ladder.get(tier) or "").strip()


def choice_ids(choice: str | list[str]) -> list[str]:
    if isinstance(choice, str):
        text = choice.strip()
        return [text] if text else []
    return [str(item).strip() for item in choice if str(item).strip()]


def grade_choice(quiz: dict, choice: str | list[str]) -> dict:
    """Return correct, score, misconception. Score is 100 or 0."""
    qtype = quiz.get("type")
    expected = quiz.get("answer")
    picked = choice_ids(choice)
    by_id = {
        str(item.get("id")): item
        for item in (quiz.get("choices") or [])
        if isinstance(item, dict)
    }
    known = set(by_id)
    if not picked or any(item not in known for item in picked):
        return {
            "correct": False,
            "score": 0,
            "misconception": str(quiz.get("misconception") or "").strip() or None,
        }
    if qtype in {"single", "flaw"}:
        correct = len(picked) == 1 and picked[0] == expected
        if correct:
            return {"correct": True, "score": 100, "misconception": None}
        item = by_id.get(picked[0], {})
        note = str(item.get("misconception") or quiz.get("misconception") or "").strip()
        return {"correct": False, "score": 0, "misconception": note or None}
    if qtype == "multi":
        expected_ids = set(expected if isinstance(expected, list) else [expected])
        correct = set(picked) == expected_ids
    elif qtype == "order":
        expected_ids = list(expected if isinstance(expected, list) else [expected])
        correct = picked == expected_ids
    else:
        correct = False
    if correct:
        return {"correct": True, "score": 100, "misconception": None}
    note = str(quiz.get("misconception") or "").strip()
    return {"correct": False, "score": 0, "misconception": note or None}


def public_quiz(quiz: dict | None) -> dict | None:
    """Kid-facing widget. Answers and stored misconceptions stay on the server."""
    if not isinstance(quiz, dict) or quiz.get("type") not in {"single", "multi", "flaw", "order"}:
        return None
    choices = []
    for item in quiz.get("choices") or []:
        if not isinstance(item, dict):
            continue
        choices.append({"id": str(item.get("id")), "text": str(item.get("text") or "")})
    if len(choices) < 2:
        return None
    return {
        "type": quiz["type"],
        "prompt": str(quiz.get("prompt") or ""),
        "choices": choices,
        "explain": bool(quiz.get("explain")),
    }


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _label(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if not text or len(text) > _MAX_LABEL:
        return None
    if any(ord(char) < 32 for char in text):
        return None
    if _MARKUP.search(text):
        return None
    return text


def _pairs(value: object, keys: frozenset[str], number_key: str) -> list[tuple[str, float]] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    pairs: list[tuple[str, float]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != keys:
            return None
        label = _label(item.get("label"))
        number = _finite(item.get(number_key))
        if label is None or number is None:
            return None
        pairs.append((label, number))
    return pairs


def _right_mark(value: object, angles: list[float]) -> bool | None:
    if value is None:
        marked = False
    elif isinstance(value, bool):
        marked = value
    else:
        return None
    if not marked:
        return False
    if any(abs(angle - 90.0) <= _RIGHT_TOLERANCE for angle in angles):
        return True
    return None


def _sides_match_angles(sides: list[float], angles: list[float]) -> bool:
    a, b, c = sides
    angle_a = math.radians(angles[0])
    placed_x = b * math.cos(angle_a)
    placed_y = b * math.sin(angle_a)
    placed = math.hypot(placed_x - c, placed_y)
    if placed <= 0 or abs(placed - a) / a > _RATIO_TOLERANCE:
        return False
    ratios: list[float] = []
    for side, angle in zip(sides, angles, strict=True):
        sine = math.sin(math.radians(angle))
        if sine <= 1e-6:
            return False
        ratios.append(side / sine)
    base = ratios[0]
    return all(abs(item - base) / base <= _RATIO_TOLERANCE for item in ratios)


def _triangle(diagram: dict) -> dict | None:
    if set(diagram) - _TRIANGLE_KEYS:
        return None
    sides = _pairs(diagram.get("sides"), _SIDE_KEYS, "length")
    angles = _pairs(diagram.get("angles"), _ANGLE_KEYS, "degrees")
    if sides is None or angles is None:
        return None
    lengths = [length for _, length in sides]
    degrees = [degree for _, degree in angles]
    if any(length <= 0 or length > _MAX_SIDE for length in lengths):
        return None
    if any(degree <= 0 or degree >= 180 for degree in degrees):
        return None
    if abs(sum(degrees) - _ANGLE_SUM) > _SUM_TOLERANCE:
        return None
    left, middle, right = lengths
    if left + middle <= right or left + right <= middle or middle + right <= left:
        return None
    if not _sides_match_angles(lengths, degrees):
        return None
    mark = _right_mark(diagram.get("right_angle"), degrees)
    if mark is None:
        return None
    return {
        "kind": "triangle",
        "sides": [{"label": label, "length": length} for label, length in sides],
        "angles": [{"label": label, "degrees": degree} for label, degree in angles],
        "right_angle": mark,
    }


def _checked_diagram(diagram: object, course_code: str) -> dict | None:
    """Return a triangle the app can draw, or None when the picture is refused."""
    if not isinstance(diagram, dict):
        return None
    kind = diagram.get("kind")
    if not isinstance(kind, str) or kind not in NAMED_DIAGRAM_KINDS:
        return None
    if kind != "triangle":
        return None
    if (course_code or "").strip().lower() != _GEOMETRY:
        return None
    return _triangle(diagram)


def guard_reply(turn: dict, course_code: str) -> dict:
    """Keep the text reply. Drop a diagram that fails the check.

    A failed picture does not fail the turn.
    """
    if not isinstance(turn, dict):
        return {"reply": ""}
    kept = {key: value for key, value in turn.items() if key != "diagram"}
    diagram = _checked_diagram(turn.get("diagram"), course_code)
    if diagram is not None:
        kept["diagram"] = diagram
    return kept
```

Source file `apps/api/app/routes/sessions.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.flow import (
    advance,
    append_message,
    append_model_prompt,
    apply_turn_score,
    grade_widget,
    open_session,
)
from app.models import ModelPrompt, Quest, Session as TutorSession
from app.present import board, message_out, prompt_out, session_admin, session_summary
from app.prompt_loader import load_prompt
from app.queries import load_session
from app.widgets import guard_reply
from app.schemas import (
    BoardOut,
    MessageIn,
    MessageOut,
    ModelPromptIn,
    ModelPromptOut,
    PromptBundleOut,
    SessionAdminOut,
    SessionOpen,
    SessionSummary,
    DiagramCheckIn,
    TurnScoreIn,
    WidgetIn,
)

router = APIRouter()


def _session_options():
    return (
        selectinload(TutorSession.student),
        selectinload(TutorSession.quest).selectinload(Quest.course),
        selectinload(TutorSession.messages),
        selectinload(TutorSession.results),
    )


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(student_id: UUID | None = None, db: Session = Depends(get_db)) -> list[SessionSummary]:
    stmt = select(TutorSession).options(*_session_options()).order_by(TutorSession.updated_at.desc())
    if student_id is not None:
        stmt = stmt.where(TutorSession.student_id == student_id)
    return [session_summary(item) for item in db.scalars(stmt).all()]


@router.post("/sessions", response_model=BoardOut)
def create_session(body: SessionOpen, db: Session = Depends(get_db)) -> BoardOut:
    tutor_session = open_session(db, body.student_id, body.quest_id, body.fresh)
    db.flush()
    return board(load_session(db, tutor_session.id))


@router.get("/sessions/{session_id}", response_model=SessionAdminOut)
def get_session(session_id: UUID, db: Session = Depends(get_db)) -> SessionAdminOut:
    return session_admin(load_session(db, session_id))


@router.get("/sessions/{session_id}/board", response_model=BoardOut)
def get_board(session_id: UUID, db: Session = Depends(get_db)) -> BoardOut:
    return board(load_session(db, session_id))


@router.get("/sessions/{session_id}/prompt", response_model=PromptBundleOut)
def get_prompt(
    session_id: UUID, kickoff: bool = False, db: Session = Depends(get_db)
) -> PromptBundleOut:
    bundle = load_prompt(load_session(db, session_id), kickoff=kickoff)
    return PromptBundleOut(
        system_prompt=bundle.system_prompt,
        response_schema=bundle.response_schema,
        temperature=bundle.temperature,
    )


@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def create_message(session_id: UUID, body: MessageIn, db: Session = Depends(get_db)) -> MessageOut:
    tutor_session = load_session(db, session_id)
    message = append_message(db, tutor_session, body.role, body.content.strip(), body.client_id)
    return message_out(message)


@router.post("/sessions/{session_id}/advance")
def advance_session(session_id: UUID, db: Session = Depends(get_db)) -> dict:
    return advance(db, load_session(db, session_id))


@router.post("/sessions/{session_id}/grade-widget")
def grade_widget_route(session_id: UUID, body: WidgetIn, db: Session = Depends(get_db)) -> dict:
    return grade_widget(db, load_session(db, session_id), body.choice, body.explanation)


@router.post("/sessions/{session_id}/check-diagram")
def check_diagram_route(session_id: UUID, body: DiagramCheckIn, db: Session = Depends(get_db)) -> dict:
    """Check a diagram before it reaches the client. A refusal still returns 200."""
    tutor_session = load_session(db, session_id)
    course_code = tutor_session.quest.course.code
    guarded = guard_reply({"reply": "", "diagram": body.diagram}, course_code)
    return {"diagram": guarded.get("diagram")}


@router.get("/sessions/{session_id}/model-prompts", response_model=list[ModelPromptOut])
def list_model_prompts(session_id: UUID, db: Session = Depends(get_db)) -> list[ModelPromptOut]:
    tutor_session = load_session(db, session_id)
    rows = db.scalars(
        select(ModelPrompt).where(ModelPrompt.session_id == tutor_session.id).order_by(ModelPrompt.seq)
    ).all()
    return [prompt_out(row) for row in rows]


@router.post("/sessions/{session_id}/model-prompts", response_model=ModelPromptOut)
def create_model_prompt(
    session_id: UUID, body: ModelPromptIn, db: Session = Depends(get_db)
) -> ModelPromptOut:
    tutor_session = load_session(db, session_id)
    row = append_model_prompt(
        db, tutor_session, body.system_prompt, list(body.messages), body.model, body.message_id
    )
    return prompt_out(row)


@router.post("/sessions/{session_id}/turn-score")
def turn_score_route(session_id: UUID, body: TurnScoreIn, db: Session = Depends(get_db)) -> dict:
    return apply_turn_score(
        db, load_session(db, session_id), body.rubric_met, body.misconception, body.advance
    )
```

Source file `apps/api/app/routes/tutor_profile.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TutorProfile
from app.schemas import TutorProfileIn, TutorProfileOut
from app.tutor_profile import ensure_default_profile, save_profile

router = APIRouter()


def _out(row: TutorProfile) -> TutorProfileOut:
    return TutorProfileOut(
        instructive=row.instructive,
        persona=row.persona,
        lexicon=row.lexicon,
        voice_override=row.voice_override,
        metaphors=row.metaphors,
        sidekick=row.sidekick,
        struggle_window=row.struggle_window,
        anti_spoiler=row.anti_spoiler,
        one_question=row.one_question,
        use_interests=row.use_interests,
        stay_on_course=row.stay_on_course,
        growth_praise=row.growth_praise,
        updated_at=row.updated_at,
    )


@router.get("/tutor-profile", response_model=TutorProfileOut)
def get_tutor_profile(db: Session = Depends(get_db)) -> TutorProfileOut:
    return _out(ensure_default_profile(db))


@router.put("/tutor-profile", response_model=TutorProfileOut)
def put_tutor_profile(body: TutorProfileIn, db: Session = Depends(get_db)) -> TutorProfileOut:
    row = save_profile(
        db,
        instructive=body.instructive,
        persona=body.persona,
        lexicon=body.lexicon,
        voice_override=body.voice_override,
        metaphors=body.metaphors,
        sidekick=body.sidekick,
        struggle_window=body.struggle_window,
        anti_spoiler=body.anti_spoiler,
        one_question=body.one_question,
        use_interests=body.use_interests,
        stay_on_course=body.stay_on_course,
        growth_praise=body.growth_praise,
    )
    return _out(row)
```

Source file `apps/web/app/api/chat/route.ts`:

```typescript
import { openai } from "@ai-sdk/openai";
import {
  Output,
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  jsonSchema,
  streamText,
  wrapLanguageModel,
  type JSONSchema7,
  type LanguageModelMiddleware,
  type UIMessage,
} from "ai";

import { api } from "@/lib/api";
import { KICKOFF } from "@/lib/kickoff";
import { openaiModelName } from "@/lib/model";
import type { PromptBundle, TriangleDiagram } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 60;

const MISSING_KEY =
  "OPENAI_API_KEY is not set. Copy .env.example to apps/web/.env.local, set OPENAI_API_KEY to your real key, and restart the Next.js server.";

type TurnScore = {
  reply: string;
  rubric_met: string[];
  misconception: string | null;
  hint_tier: "nudge" | "analogy" | "scaffold";
  advance: boolean;
  diagram?: unknown;
};

type WidgetBody = {
  choice?: string | string[];
  explanation?: string;
};

async function checkedDiagram(sessionId: string, diagram: unknown): Promise<TriangleDiagram | null> {
  if (diagram == null) return null;
  try {
    const checked = await api<{ diagram: TriangleDiagram | null }>(`/sessions/${sessionId}/check-diagram`, {
      method: "POST",
      body: JSON.stringify({ diagram }),
    });
    if (!checked.diagram || checked.diagram.kind !== "triangle") return null;
    return checked.diagram;
  } catch (error) {
    console.error("Could not check the diagram", error);
    return null;
  }
}

function textOf(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("\n")
    .trim();
}

function jsonSafe(value: unknown): unknown {
  return JSON.parse(
    JSON.stringify(value, (_key, item: unknown) => {
      if (typeof item === "bigint") return item.toString();
      if (item instanceof Uint8Array) return Buffer.from(item).toString("base64");
      return item;
    }),
  );
}

type ModelCall = {
  prompt?: Array<{ role?: string; content?: unknown }>;
  temperature?: number;
  maxOutputTokens?: number;
  topP?: number;
  topK?: number;
  presencePenalty?: number;
  frequencyPenalty?: number;
  stopSequences?: string[];
  seed?: number;
  responseFormat?: unknown;
  tools?: unknown;
  toolChoice?: unknown;
  reasoning?: string;
};

function textOfContent(content: unknown) {
  return typeof content === "string" ? content : JSON.stringify(content);
}

function requestForCall(params: ModelCall, fallbackSystem: string) {
  const prompt = Array.isArray(params.prompt) ? params.prompt : [];
  const systemParts = prompt
    .filter((message) => message.role === "system")
    .map((message) => textOfContent(message.content))
    .filter((text) => text.length > 0);
  let systemPrompt = systemParts.join("\n\n");
  if (fallbackSystem && !systemPrompt.includes(fallbackSystem)) {
    systemPrompt = systemPrompt ? `${fallbackSystem}\n\n${systemPrompt}` : fallbackSystem;
  }
  const messages = prompt.filter((message) => message.role !== "system");
  const extras: Record<string, unknown> = {};
  if (params.temperature != null) extras.temperature = params.temperature;
  if (params.maxOutputTokens != null) extras.maxOutputTokens = params.maxOutputTokens;
  if (params.topP != null) extras.topP = params.topP;
  if (params.topK != null) extras.topK = params.topK;
  if (params.presencePenalty != null) extras.presencePenalty = params.presencePenalty;
  if (params.frequencyPenalty != null) extras.frequencyPenalty = params.frequencyPenalty;
  if (params.stopSequences != null) extras.stopSequences = params.stopSequences;
  if (params.seed != null) extras.seed = params.seed;
  if (params.responseFormat != null) extras.responseFormat = params.responseFormat;
  if (params.tools != null) extras.tools = params.tools;
  if (params.toolChoice != null) extras.toolChoice = params.toolChoice;
  if (params.reasoning != null && params.reasoning !== "provider-default") extras.reasoning = params.reasoning;
  const storedMessages = Object.keys(extras).length > 0 ? [...messages, { role: "request", content: extras }] : messages;
  return {
    system_prompt: systemPrompt || fallbackSystem,
    messages: jsonSafe(storedMessages),
  };
}

export async function POST(req: Request) {
  let body: { messages?: UIMessage[]; sessionId?: string; widget?: WidgetBody };
  try {
    body = (await req.json()) as { messages?: UIMessage[]; sessionId?: string; widget?: WidgetBody };
  } catch {
    return new Response("Expected JSON with sessionId and messages.", { status: 400 });
  }

  const sessionId = body.sessionId;
  const messages = body.messages ?? [];
  if (!sessionId) {
    return new Response("sessionId is required.", { status: 400 });
  }

  if (body.widget && body.widget.choice != null) {
    try {
      const graded = await api<{ ok: boolean; reason?: string }>(`/sessions/${sessionId}/grade-widget`, {
        method: "POST",
        body: JSON.stringify({
          choice: body.widget.choice,
          explanation: body.widget.explanation ?? "",
        }),
      });
      if (!graded.ok) {
        return new Response(graded.reason || "That choice could not be graded.", { status: 400 });
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not grade that choice.";
      return new Response(message, { status: 502 });
    }
  }

  if (!process.env.OPENAI_API_KEY?.trim()) {
    return new Response(MISSING_KEY, {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  let turnMessageId: string | null = null;
  const lastUser = [...messages].reverse().find((message) => message.role === "user");
  if (lastUser) {
    const content = textOf(lastUser);
    if (content) {
      try {
        const saved = await api<{ id: string }>(`/sessions/${sessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "user",
            content,
            client_id: lastUser.id,
          }),
        });
        turnMessageId = saved.id;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not save the message.";
        return new Response(message, { status: 502 });
      }
    }
  }

  const kickoff =
    messages.filter((message) => message.role === "user").length === 1 &&
    lastUser != null &&
    textOf(lastUser) === KICKOFF;

  let bundle: PromptBundle;
  try {
    bundle = await api<PromptBundle>(
      `/sessions/${sessionId}/prompt?kickoff=${kickoff ? "true" : "false"}`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load the prompt.";
    return new Response(message, { status: 502 });
  }

  const system = bundle.system_prompt;
  const modelMessages = await convertToModelMessages(messages);
  const modelName = openaiModelName();
  const captureRequest: LanguageModelMiddleware = {
    specificationVersion: "v4",
    wrapStream: async ({ doStream, params, model }) => {
      const request = requestForCall(params, system);
      const messagesForStore = Array.isArray(request.messages) ? request.messages : [];
      try {
        await api(`/sessions/${sessionId}/model-prompts`, {
          method: "POST",
          body: JSON.stringify({
            system_prompt: request.system_prompt,
            messages: messagesForStore,
            model: model.modelId || modelName,
            message_id: turnMessageId,
          }),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Could not store the prompt.";
        throw new Error(message);
      }
      return doStream();
    },
  };

  const result = streamText({
    model: wrapLanguageModel({ model: openai(modelName), middleware: captureRequest }),
    output: Output.object({
      schema: jsonSchema(bundle.response_schema as JSONSchema7),
      name: "turn_score",
      description: "Rubric rows met, misconception if any, hint tier, and the tutor reply.",
    }),
    instructions: system,
    messages: modelMessages,
    temperature: bundle.temperature,
    abortSignal: AbortSignal.timeout(60_000),
  });

  const stream = createUIMessageStream({
    execute: async ({ writer }) => {
      const id = "tutor-reply";
      writer.write({ type: "text-start", id });
      let sent = "";
      for await (const partial of result.partialOutputStream) {
        const piece = partial as Partial<TurnScore>;
        const reply = typeof piece.reply === "string" ? piece.reply : "";
        if (!reply.startsWith(sent)) continue;
        const delta = reply.slice(sent.length);
        if (delta) writer.write({ type: "text-delta", id, delta });
        sent = reply;
      }
      let finalScore: TurnScore;
      try {
        finalScore = (await result.output) as TurnScore;
      } catch (error) {
        writer.write({ type: "text-end", id });
        throw error;
      }
      const diagram = await checkedDiagram(sessionId, finalScore.diagram);
      if (diagram) {
        writer.write({ type: "data-diagram", id: "lesson-diagram", data: diagram });
      }
      writer.write({ type: "text-end", id });
      if (!kickoff) {
        try {
          await api(`/sessions/${sessionId}/turn-score`, {
            method: "POST",
            body: JSON.stringify({
              rubric_met: finalScore.rubric_met,
              misconception: finalScore.misconception,
              hint_tier: finalScore.hint_tier,
              advance: finalScore.advance,
            }),
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Could not save the score.";
          throw new Error(message);
        }
      }
      if (lastUser && sent.trim()) {
        try {
          await api(`/sessions/${sessionId}/messages`, {
            method: "POST",
            body: JSON.stringify({
              role: "assistant",
              content: sent.trim(),
              client_id: `${lastUser.id}:assistant`,
            }),
          });
        } catch (error) {
          console.error("Could not store the tutor reply", error);
        }
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
```

Source file `apps/web/lib/kickoff.ts`:

```typescript
export const KICKOFF = "Hi! I'm ready to learn.";
```

### 5. Chat Viewer & Telemetry Schema

There is no `chat_sessions` table. A kid class is `sessions`. Lines are `messages` (`role` user or assistant, `content`, `client_id`, `seq`). Each model call is `model_prompts` (`system_prompt`, `messages` JSON, `model`, optional `message_id`). Each score is `beat_results` (`beat_id`, `score`, `passed`, `feedback`, `rubric_met`, `misconception`, `hint_tier`, `choice`). `choice` stores the submitted choice ids and explanation. `rubric_met` stores the rubric and success-criterion ids the turn marked. `passed` is the success-criteria result for that beat. The tutor settings used for the turn are not a foreign key. They are the text inside `model_prompts.system_prompt` (layers 2, 3, and 4) plus `model_prompts.model`. Quest and goal position are not columns on `messages`. The session row holds `quest_id` and `current_beat_id`. `beat_results.beat_id` points at the move that was scored. Goal text is inside the stored system prompt, from `quest_goals` at prompt-build time.

The four tables, quoted again from `apps/api/app/models.py`:

```python
class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_sessions_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quests.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    current_beat_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped[Student] = relationship(back_populates="sessions")
    quest: Mapped[Quest] = relationship(back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.seq",
    )
    results: Mapped[list[BeatResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="BeatResult.seq",
    )
    prompts: Mapped[list[ModelPrompt]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ModelPrompt.seq",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_messages_session_seq"),
        CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="messages")


class BeatResult(Base):
    __tablename__ = "beat_results"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_beat_results_session_seq"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_beat_results_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    beat_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("beats.id", ondelete="RESTRICT"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_met: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    misconception: Mapped[str | None] = mapped_column(Text)
    hint_tier: Mapped[str | None] = mapped_column(String(16))
    choice: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="results")
    beat: Mapped[Beat] = relationship(back_populates="results")


class ModelPrompt(Base):
    """One model call: the system prompt plus the messages sent to the model."""

    __tablename__ = "model_prompts"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_model_prompts_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[Session] = relationship(back_populates="prompts")
```

Pydantic shapes the viewer returns:

```python
class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    client_id: str | None
    created_at: datetime


class BoardResult(BaseModel):
    id: UUID
    score: int
    passed: bool
    feedback: str
    created_at: datetime


class BoardBeat(BaseModel):
    id: UUID
    position: int
    role: str
    latest_result: BoardResult | None


class RubricRowOut(BaseModel):
    id: str
    text: str
    weight: int
    met: bool


class QuizChoiceOut(BaseModel):
    id: str
    text: str


class QuizOut(BaseModel):
    type: Literal["single", "flaw", "order", "multi"]
    prompt: str
    choices: list[QuizChoiceOut]
    explain: bool


class BlockStep(BaseModel):
    id: UUID
    position: int
    kind: str
    title: str
    state: str


class CurrentBlock(BaseModel):
    id: UUID
    kind: str
    title: str
    objective: str
    tutor_prompt: str
    rubric: list[RubricRowOut]
    hint_tier: Literal["nudge", "analogy", "scaffold"]
    hint_text: str
    quiz: QuizOut | None


class BoardOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    course_code: str
    course_title: str
    quest_id: UUID
    quest_code: str
    quest_title: str
    enduring_understanding: str
    current_beat_id: UUID | None
    beats: list[BoardBeat]
    messages: list[MessageOut]
    steps: list[BlockStep]
    current_block: CurrentBlock | None = None


class ResultOut(BaseModel):
    id: UUID
    beat_id: UUID
    beat_role: str
    beat_position: int
    quest_title: str
    score: int
    passed: bool
    feedback: str
    misconception: str | None = None
    hint_tier: str | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    student_id: UUID
    student_display_name: str
    quest_id: UUID
    quest_code: str
    quest_title: str
    course_title: str
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    result_count: int


class ModelPromptOut(BaseModel):
    id: UUID
    session_id: UUID
    message_id: UUID | None = None
    seq: int
    system_prompt: str
    messages: list[Any]
    model: str
    created_at: datetime


class SessionQuest(BaseModel):
    id: UUID
    code: str
    title: str
    course_code: str
    course_title: str


class SessionBeat(BaseModel):
    id: UUID
    position: int
    role: str


class SessionAdminOut(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    student: StudentOut
    quest: SessionQuest
    current_beat_id: UUID | None
    beats: list[SessionBeat]
    messages: list[MessageOut]
    results: list[ResultOut]
    prompts: list[ModelPromptOut] = Field(default_factory=list)
```

TypeScript shapes the viewer renders (`SessionSummary`, `ModelPrompt`, `SessionDetail`, `ResultRow`) are in `apps/web/lib/types.ts`, quoted in full in section 2.

`GET /sessions` lists summaries, optional `student_id` filter. `GET /sessions/{session_id}` returns `session_admin`: student, quest code and title, course title, current beat, beats, messages, results, and prompts. `ViewChats` loads students, then `/sessions?student_id=`, then `/sessions/{id}`. `promptForMessage` attaches each `model_prompts` row to `message_id`, and pairs any unlinked prompt with the next user message in sequence order. `promptOnRow` draws the debug button on the following assistant message. The dialog prints `model`, `created_at`, `system_prompt`, and `messages`, and separates a stored `role: request` note.

Source file `apps/api/app/present.py`:

```python
from __future__ import annotations

from app.engine.assemble import hint_tier_for
from app.engine.defaults import age_band_for
from app.flow import beat_state, failed_attempts
from app.models import Beat, BeatResult, Course, Message, ModelPrompt, Quest, Session as TutorSession
from app.queries import choice_widget_visible, close_choice_widget, latest_result, locate_beat, ordered_beats
from app.schemas import (
    BeatOut,
    BlockStep,
    BoardBeat,
    BoardOut,
    BoardResult,
    CatalogQuest,
    CloseOut,
    CourseSummary,
    CourseTree,
    CurrentBlock,
    GoalOut,
    MessageOut,
    ModelPromptOut,
    QuestDetail,
    QuestListItem,
    QuestNode,
    QuizChoiceOut,
    QuizOut,
    ResultOut,
    RubricRowOut,
    SessionAdminOut,
    SessionBeat,
    SessionQuest,
    SessionSummary,
    StudentOut,
)
from app.widgets import hint_text, public_quiz

ROLE_TITLE = {
    "engage": "Engage",
    "try": "Try",
    "name": "Name",
    "show": "Show",
    "teach_back": "Teach back",
}


def student_out(student) -> StudentOut:
    return StudentOut(
        id=student.id,
        slug=student.slug,
        display_name=student.display_name,
        age=student.age,
        age_band=age_band_for(student.age),
        reading_level=student.reading_level or "",
        modality=student.modality or "",
        interests=[str(item) for item in (student.interests or [])],
        tutor_persona=student.tutor_persona or "",
        tutor_lexicon=student.tutor_lexicon or "",
        tutor_metaphors=student.tutor_metaphors or "",
        tutor_sidekick=student.tutor_sidekick or "",
        tutor_socratic_strictness=student.tutor_socratic_strictness or "balanced",
        tutor_struggle_window=student.tutor_struggle_window or "minimum",
        tutor_anti_spoiler=bool(student.tutor_anti_spoiler),
        tutor_pacing=student.tutor_pacing or "short-turns-one-question",
    )


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        client_id=message.client_id,
        created_at=message.created_at,
    )


def prompt_out(row: ModelPrompt) -> ModelPromptOut:
    return ModelPromptOut(
        id=row.id,
        session_id=row.session_id,
        message_id=row.message_id,
        seq=row.seq,
        system_prompt=row.system_prompt,
        messages=list(row.messages or []),
        model=row.model,
        created_at=row.created_at,
    )


def _goal_out(goal) -> GoalOut:
    return GoalOut(
        position=goal.position,
        learning_goal=goal.learning_goal or "",
        success_criterion=goal.success_criterion or "",
    )


def _close_out(close) -> CloseOut | None:
    if close is None:
        return None
    return CloseOut(
        kind=close.kind,
        question=close.question or "",
        items=list(close.items or []),
    )


def course_summary(course: Course) -> CourseSummary:
    return CourseSummary(
        id=course.id,
        code=course.code,
        title=course.title,
        age_band=course.age_band,
        standards_alignment=course.standards_alignment,
        description=course.description or "",
        audience=course.audience or course.age_band,
        quest_count=len(course.quests),
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
    )


def _quest_node(quest: Quest) -> QuestNode:
    return QuestNode(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        quest_type=quest.quest_type,
        prerequisite_codes=list(quest.prerequisite_codes or []),
        competency_tags=list(quest.competency_tags or []),
        dinner_prompt=quest.dinner_prompt,
        position=quest.position,
    )


def _catalog_quest(quest: Quest) -> CatalogQuest:
    return CatalogQuest(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        position=quest.position,
        goals=[_goal_out(goal) for goal in sorted(quest.goals, key=lambda item: item.position)],
        close=_close_out(quest.close),
    )


def course_tree(course: Course) -> CourseTree:
    return CourseTree(
        id=course.id,
        code=course.code,
        title=course.title,
        age_band=course.age_band,
        standards_alignment=course.standards_alignment,
        description=course.description or "",
        audience=course.audience or course.age_band,
        quest_count=course.quest_count,
        goals_per_quest=course.goals_per_quest,
        quiz_minutes=course.quiz_minutes,
        competency_dictionary=list(course.competency_dictionary or []),
        quests=[
            _catalog_quest(quest)
            for quest in sorted(course.quests, key=lambda item: item.position)
        ],
    )


def quest_list_item(quest: Quest) -> QuestListItem:
    return QuestListItem(
        id=quest.id,
        code=quest.code,
        title=quest.title,
        quest_type=quest.quest_type,
        prerequisite_codes=list(quest.prerequisite_codes or []),
        competency_tags=list(quest.competency_tags or []),
        unit_number=0,
        unit_title="",
        position=quest.position,
    )


def beat_out(beat: Beat) -> BeatOut:
    return BeatOut(
        id=beat.id,
        position=beat.position,
        role=beat.role,
        bloom_level=beat.bloom_level,
        cognitive_load=beat.cognitive_load,
        prompt=beat.prompt,
        rubric=list(beat.rubric or []),
        misconception_map=list(beat.misconception_map or []),
        hint_ladder=dict(beat.hint_ladder or {}),
        widget=beat.widget if isinstance(beat.widget, dict) else None,
    )


def quest_detail(quest: Quest) -> QuestDetail:
    return QuestDetail(
        **_quest_node(quest).model_dump(),
        course_id=quest.course_id,
        goals=[_goal_out(goal) for goal in sorted(quest.goals, key=lambda item: item.position)],
        close=_close_out(quest.close),
        learning_goal=quest.learning_goal or "",
        success_criterion=list(quest.success_criterion or []),
        requires_teach_back=bool(quest.requires_teach_back),
        beats=[beat_out(beat) for beat in ordered_beats(quest)],
    )


def _rubric_rows(beat: Beat, met_ids: set[str]) -> list[RubricRowOut]:
    rows = []
    for row in beat.rubric or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        row_id = str(row["id"])
        rows.append(
            RubricRowOut(
                id=row_id,
                text=str(row.get("text") or ""),
                weight=int(row.get("weight") or 0),
                met=row_id in met_ids,
            )
        )
    return rows


def _quiz_out(quiz: dict | None) -> QuizOut | None:
    public = public_quiz(quiz)
    if public is None:
        return None
    return QuizOut(
        type=public["type"],
        prompt=public["prompt"],
        choices=[QuizChoiceOut(id=item["id"], text=item["text"]) for item in public["choices"]],
        explain=public["explain"],
    )


def board(tutor_session: TutorSession) -> BoardOut:
    quest = tutor_session.quest
    beats = ordered_beats(quest)
    complete = tutor_session.current_beat_id is None
    seen = False
    steps: list[BlockStep] = []
    board_beats: list[BoardBeat] = []
    current = None
    for beat in beats:
        result = latest_result(tutor_session, beat.id)
        state = beat_state(beat, tutor_session.current_beat_id, result, seen, complete)
        if beat.id == tutor_session.current_beat_id:
            seen = True
            tier = hint_tier_for(failed_attempts(tutor_session, beat.id))
            met = set(result.rubric_met or []) if result is not None else set()
            current = CurrentBlock(
                id=beat.id,
                kind=beat.role,
                title=ROLE_TITLE.get(beat.role, beat.role),
                objective=f"{ROLE_TITLE.get(beat.role, beat.role)} · {beat.bloom_level}",
                tutor_prompt=beat.prompt,
                rubric=_rubric_rows(beat, met),
                hint_tier=tier,  # type: ignore[arg-type]
                hint_text=hint_text(beat.hint_ladder, tier),
                quiz=_quiz_out(
                    close_choice_widget(quest, beat) if choice_widget_visible(tutor_session, beat) else None
                ),
            )
        steps.append(
            BlockStep(
                id=beat.id,
                position=beat.position,
                kind=beat.role,
                title=ROLE_TITLE.get(beat.role, beat.role),
                state=state,
            )
        )
        board_beats.append(
            BoardBeat(
                id=beat.id,
                position=beat.position,
                role=beat.role,
                latest_result=BoardResult(
                    id=result.id,
                    score=result.score,
                    passed=result.passed,
                    feedback=result.feedback,
                    created_at=result.created_at,
                )
                if result
                else None,
            )
        )
    return BoardOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        course_code=quest.course.code,
        course_title=quest.course.title,
        quest_id=quest.id,
        quest_code=quest.code,
        quest_title=quest.title,
        enduring_understanding=quest.course.description or "",
        current_beat_id=tutor_session.current_beat_id,
        beats=board_beats,
        messages=[message_out(message) for message in tutor_session.messages],
        steps=steps,
        current_block=current,
    )


def result_out(result: BeatResult) -> ResultOut:
    beat = result.beat
    return ResultOut(
        id=result.id,
        beat_id=beat.id,
        beat_role=beat.role,
        beat_position=beat.position,
        quest_title=beat.quest.title,
        score=result.score,
        passed=result.passed,
        feedback=result.feedback,
        misconception=result.misconception,
        hint_tier=result.hint_tier,
        created_at=result.created_at,
    )


def session_summary(tutor_session: TutorSession) -> SessionSummary:
    quest = tutor_session.quest
    return SessionSummary(
        id=tutor_session.id,
        student_id=tutor_session.student_id,
        student_display_name=tutor_session.student.display_name,
        quest_id=quest.id,
        quest_code=quest.code,
        quest_title=quest.title,
        course_title=quest.course.title,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        message_count=len(tutor_session.messages),
        result_count=len(tutor_session.results),
    )


def session_admin(tutor_session: TutorSession) -> SessionAdminOut:
    quest = tutor_session.quest
    return SessionAdminOut(
        id=tutor_session.id,
        status=tutor_session.status,
        created_at=tutor_session.created_at,
        updated_at=tutor_session.updated_at,
        student=student_out(tutor_session.student),
        quest=SessionQuest(
            id=quest.id,
            code=quest.code,
            title=quest.title,
            course_code=quest.course.code,
            course_title=quest.course.title,
        ),
        current_beat_id=tutor_session.current_beat_id,
        beats=[
            SessionBeat(id=beat.id, position=beat.position, role=beat.role)
            for beat in ordered_beats(quest)
        ],
        messages=[message_out(message) for message in tutor_session.messages],
        results=[result_out(result) for result in tutor_session.results],
        prompts=[prompt_out(row) for row in tutor_session.prompts],
    )
```

Source file `apps/web/components/ViewChats.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

import { AdminFrame } from "@/components/admin/AdminFrame";
import { api } from "@/lib/api";
import type { ModelPrompt, SessionDetail, SessionSummary, Student } from "@/lib/types";

function when(iso: string) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function messageRole(message: unknown) {
  if (message && typeof message === "object" && "role" in message && typeof message.role === "string") {
    return message.role;
  }
  return "message";
}

function messageBody(message: unknown) {
  const content =
    message && typeof message === "object" && "content" in message
      ? (message as { content: unknown }).content
      : message;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
        return JSON.stringify(part, null, 2);
      })
      .join("\n");
  }
  return JSON.stringify(content, null, 2);
}

function isRequestNote(message: unknown) {
  return messageRole(message) === "request";
}

export function ViewChats({ initialStudents, initialError }: { initialStudents: Student[]; initialError: string | null }) {
  const [students] = useState(initialStudents);
  const [studentFilter, setStudentFilter] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState(initialError);

  useEffect(() => {
    const query = studentFilter ? `?student_id=${studentFilter}` : "";
    let cancelled = false;
    api<SessionSummary[]>(`/sessions${query}`)
      .then((next) => {
        if (!cancelled) setSessions(next);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [studentFilter]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    api<SessionDetail>(`/sessions/${sessionId}`)
      .then((next) => {
        if (!cancelled) setSession(next);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  return (
    <AdminFrame
      current="chats"
      sidebar={
        <>
        <label>
          Student
          <select value={studentFilter} onChange={(event) => setStudentFilter(event.target.value)}>
            <option value="">Everyone</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>{student.display_name}</option>
            ))}
          </select>
        </label>
        <ul className="ds-list" aria-label="Classes">
          {sessions.length === 0 ? <li className="ds-quiet">No classes yet. Open a learner on the kid page.</li> : null}
          {sessions.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`ds-row ${item.id === sessionId ? "is-on" : ""}`}
                onClick={() => setSessionId(item.id)}
              >
                <strong>{item.student_display_name}</strong>
                <small>
                  {item.quest_title} · {item.status.replace("_", " ")} · {when(item.updated_at)}
                </small>
                <small>{item.message_count} messages · {item.result_count} scores</small>
              </button>
            </li>
          ))}
        </ul>
        </>
      }
    >
        {error ? (
          <div className="banner" role="alert" style={{ margin: 18 }}>
            <p>{error}</p>
          </div>
        ) : null}
        {session ? <SessionView session={session} /> : (
          <article className="transcript-view">
            <h2>Pick a class</h2>
            <p className="help">The transcript opens here. This page does not edit blocks.</p>
          </article>
        )}
    </AdminFrame>
  );
}

function promptForMessage(session: SessionDetail): Map<string, ModelPrompt> {
  const linked = new Map<string, ModelPrompt>();
  const unlinked: ModelPrompt[] = [];
  for (const prompt of [...(session.prompts ?? [])].sort((left, right) => left.seq - right.seq)) {
    if (prompt.message_id) {
      const current = linked.get(prompt.message_id);
      if (!current || prompt.seq >= current.seq) linked.set(prompt.message_id, prompt);
    } else {
      unlinked.push(prompt);
    }
  }
  let spare = 0;
  for (const message of session.messages) {
    if (message.role !== "user" || linked.has(message.id)) continue;
    const prompt = unlinked[spare];
    if (!prompt) break;
    linked.set(message.id, prompt);
    spare += 1;
  }
  return linked;
}

function promptOnRow(session: SessionDetail): Map<string, ModelPrompt> {
  const linked = promptForMessage(session);
  const placed = new Map<string, ModelPrompt>();
  session.messages.forEach((message, index) => {
    if (message.role !== "user") return;
    const prompt = linked.get(message.id);
    if (!prompt) return;
    const next = session.messages[index + 1];
    placed.set(next && next.role === "assistant" ? next.id : message.id, prompt);
  });
  return placed;
}

function PromptDialog({
  prompt,
  subtitle,
  onClose,
}: {
  prompt: ModelPrompt;
  subtitle: string;
  onClose: () => void;
}) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="prompt-backdrop" role="presentation" onMouseDown={onClose}>
      <div
        className="prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="prompt-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="prompt-title">View full prompt to debug</h2>
            <p>{subtitle}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>Close</button>
        </header>
        <div className="prompt-body">
          <p className="meta">
            {prompt.model || "Model"} · {when(prompt.created_at)}
          </p>
          <h3>System prompt</h3>
          <pre className="prompt-pre">{prompt.system_prompt}</pre>
          <h3>Messages sent to the model</h3>
          {prompt.messages.filter((message) => !isRequestNote(message)).length === 0 ? (
            <p className="help">No messages were attached to this call.</p>
          ) : null}
          <ol className="prompt-messages">
            {prompt.messages.filter((message) => !isRequestNote(message)).map((message, index) => (
              <li key={`${prompt.id}-${index}`}>
                <strong>{messageRole(message)}</strong>
                <pre className="prompt-pre">{messageBody(message)}</pre>
              </li>
            ))}
          </ol>
          {prompt.messages.filter(isRequestNote).map((message, index) => (
            <div key={`${prompt.id}-request-${index}`}>
              <h3>Also sent to the model</h3>
              <pre className="prompt-pre">{messageBody(message)}</pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function scoreCountLabel(count: number) {
  if (count === 0) return "None yet";
  if (count === 1) return "1 score";
  return `${count} scores`;
}

function SessionView({ session }: { session: SessionDetail }) {
  const [prompt, setPrompt] = useState<ModelPrompt | null>(null);
  const [scoresOpen, setScoresOpen] = useState(false);
  const icons = promptOnRow(session);
  useEffect(() => {
    setPrompt(null);
    setScoresOpen(false);
  }, [session.id]);
  const current = session.beats.find((beat) => beat.id === session.current_beat_id);
  const roleLabel: Record<string, string> = {
    engage: "engage",
    try: "try",
    name: "name",
    show: "show",
    teach_back: "teach-back",
  };
  return (
    <article className="transcript-view">
      <p className="eyebrow">{session.student.display_name}</p>
      <h2>{session.quest.title}</h2>
      <p className="meta">
        {session.quest.code} · {session.quest.course_title} · {session.status.replaceAll("_", " ")} · opened {when(session.created_at)}
        {current ? ` · now on ${roleLabel[current.role] ?? current.role}` : " · quest finished"}
      </p>
      <div className="score-fold">
        <h3>
          <button
            type="button"
            className="score-toggle"
            aria-expanded={scoresOpen}
            aria-controls="session-scores"
            onClick={() => setScoresOpen((open) => !open)}
          >
            <span>Scores</span>
            <span className="score-toggle-meta">
              {scoreCountLabel(session.results.length)}
              <span className="score-toggle-action">{scoresOpen ? "Hide" : "Show"}</span>
              <span className="score-chevron" aria-hidden="true">{scoresOpen ? "▴" : "▾"}</span>
            </span>
          </button>
        </h3>
        <div id="session-scores" hidden={!scoresOpen}>
          {session.results.length === 0 ? <p className="help">No beat scores stored yet.</p> : null}
          <ul className="score-list">
            {session.results.map((result) => (
              <li key={result.id}>
                <strong className={result.passed ? "pass" : "miss"}>
                  {result.passed ? "Passed" : "Not yet"} · {result.score}/100
                </strong>
                <span className="quiet">
                  {result.quest_title} · {roleLabel[result.beat_role] ?? result.beat_role} {result.beat_position} · {when(result.created_at)}
                  {result.hint_tier ? ` · hint ${result.hint_tier}` : ""}
                </span>
                <span>{result.feedback}</span>
                {result.misconception ? <span className="quiet">Misconception: {result.misconception}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <h3>Transcript</h3>
      {session.messages.length === 0 ? <p className="help">No messages stored yet.</p> : null}
      <ol className="transcript-list">
        {session.messages.map((message) => {
          const turnPrompt = icons.get(message.id);
          return (
            <li key={message.id} className={message.role}>
              <div className="transcript-line">
                <div>
                  <strong>{message.role === "user" ? session.student.display_name : "Tutor"}</strong>
                  <span className="quiet">{when(message.created_at)}</span>
                  <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{message.content}</p>
                </div>
                {turnPrompt ? (
                  <button
                    type="button"
                    className="ds-debug"
                    onClick={() => setPrompt(turnPrompt)}
                  >
                    View full prompt to debug
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
      {prompt ? (
        <PromptDialog
          prompt={prompt}
          subtitle={`${session.student.display_name} · ${session.quest.title}`}
          onClose={() => setPrompt(null)}
        />
      ) : null}
    </article>
  );
}
```

Source file `apps/web/app/viewchats/page.tsx`:

```tsx
import { ViewChats } from "@/components/ViewChats";
import { api } from "@/lib/api";
import type { Student } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata = { title: "View chats · AI Tutor" };

export default async function ViewChatsPage() {
  let students: Student[] = [];
  let error: string | null = null;
  try {
    students = await api<Student[]>("/students");
  } catch (err) {
    error = err instanceof Error ? err.message : "The tutor service is not reachable.";
  }
  return <ViewChats initialStudents={students} initialError={error} />;
}
```

### 6. End-to-End Master Data Model & Logic Intertwining Graphs (Mermaid.js)

Entity names in the request that are not tables: `User` is `students`. `ChildConfig` is columns on `students` (`age`, `reading_level`, `modality`, `interests`) plus `AgeProfile` in code, not a table. `AIAgent` is `tutor_profiles`. `CoursePreferences` is columns on `courses` and, for Create course, columns plus `preferences` JSON on `studio_courses`. `SuccessCriteria` is `quests.success_criterion` and `quest_goals.success_criterion`, and on the studio side `studio_quests.success_criterion` plus `studio_quest_goals.success_criterion`. `Closing` is `quest_closes` and `studio_quest_close`. `ChatSession` is `sessions`. `tutor_profiles` and `studio_settings` have no foreign keys. `sessions.current_beat_id` is nullable. `model_prompts.message_id` is nullable. `quest_closes.quest_id` and `studio_quest_close.quest_id` are unique.

```mermaid
erDiagram
  students {
    uuid id PK
    varchar slug UK
    varchar display_name
    int age
    varchar reading_level
    varchar modality
    json interests
    varchar tutor_persona
    text tutor_lexicon
    text tutor_metaphors
    varchar tutor_sidekick
    varchar tutor_socratic_strictness
    varchar tutor_struggle_window
    boolean tutor_anti_spoiler
    varchar tutor_pacing
    timestamptz created_at
  }
  tutor_profiles {
    varchar id PK
    int instructive
    varchar persona
    varchar lexicon
    boolean voice_override
    varchar metaphors
    varchar sidekick
    varchar struggle_window
    boolean anti_spoiler
    boolean one_question
    boolean use_interests
    boolean stay_on_course
    boolean growth_praise
    timestamptz updated_at
  }
  courses {
    uuid id PK
    varchar code UK
    varchar title
    varchar age_band
    text standards_alignment
    json competency_dictionary
    text description
    varchar audience
    int quest_count
    int goals_per_quest
    int quiz_minutes
    boolean in_catalog
    timestamptz created_at
    timestamptz updated_at
  }
  quests {
    uuid id PK
    uuid course_id FK
    varchar code UK
    varchar title
    varchar quest_type
    json prerequisite_codes
    json competency_tags
    text dinner_prompt
    text learning_goal
    json success_criterion
    boolean requires_teach_back
    int position
  }
  quest_goals {
    uuid id PK
    uuid quest_id FK
    int position
    text learning_goal
    text success_criterion
  }
  quest_closes {
    uuid id PK
    uuid quest_id FK
    varchar kind
    text question
    json items
  }
  beats {
    uuid id PK
    uuid quest_id FK
    int position
    varchar role
    varchar bloom_level
    varchar cognitive_load
    text prompt
    json rubric
    json misconception_map
    json hint_ladder
    json widget
  }
  sessions {
    uuid id PK
    uuid student_id FK
    uuid quest_id FK
    uuid current_beat_id FK
    varchar status
    timestamptz created_at
    timestamptz updated_at
  }
  messages {
    uuid id PK
    uuid session_id FK
    varchar role
    text content
    varchar client_id UK
    int seq
    timestamptz created_at
  }
  beat_results {
    uuid id PK
    uuid session_id FK
    uuid beat_id FK
    int seq
    int score
    boolean passed
    text feedback
    json rubric_met
    text misconception
    varchar hint_tier
    json choice
    timestamptz created_at
  }
  model_prompts {
    uuid id PK
    uuid session_id FK
    uuid message_id FK
    int seq
    text system_prompt
    json messages
    varchar model
    timestamptz created_at
  }
  studio_courses {
    uuid id PK
    varchar code UK
    varchar title
    text audience
    text focus
    varchar theme
    varchar depth
    int quiz_minutes
    text sources
    json preferences
    int schema_version
    boolean ready
    timestamptz created_at
    timestamptz updated_at
  }
  studio_quests {
    uuid id PK
    uuid course_id FK
    varchar code
    int position
    varchar title
    text learning_goal
    text success_criterion
  }
  studio_quest_goals {
    uuid id PK
    uuid quest_id FK
    int position
    text learning_goal
    text success_criterion
  }
  studio_moves {
    uuid id PK
    uuid course_id FK
    uuid quest_id FK
    varchar code
    int position
    varchar title
    text learning_goal
    text success_criterion
  }
  studio_quest_close {
    uuid id PK
    uuid quest_id FK
    varchar close_style
    varchar answer_style
    varchar choice_mode
    json items
    text intent
  }
  studio_messages {
    uuid id PK
    uuid course_id FK
    varchar role
    text content
    int seq
    json proposal
    boolean applied
    timestamptz created_at
  }
  studio_settings {
    varchar id PK
    varchar model
  }
  students ||--o{ sessions : student_id
  courses ||--o{ quests : course_id
  quests ||--o{ quest_goals : quest_id
  quests ||--o| quest_closes : quest_id
  quests ||--o{ beats : quest_id
  quests ||--o{ sessions : quest_id
  beats |o--o{ sessions : current_beat_id
  sessions ||--o{ messages : session_id
  sessions ||--o{ beat_results : session_id
  sessions ||--o{ model_prompts : session_id
  beats ||--o{ beat_results : beat_id
  messages |o--o{ model_prompts : message_id
  studio_courses ||--o{ studio_quests : course_id
  studio_quests ||--o{ studio_quest_goals : quest_id
  studio_quests ||--o| studio_quest_close : quest_id
  studio_quests ||--o{ studio_moves : quest_id
  studio_courses ||--o{ studio_moves : course_id
  studio_courses ||--o{ studio_messages : course_id
```

Cardinality notes grounded in the foreign keys: one `students` row to many `sessions`. One `courses` row to many `quests`. One `quests` row to many `quest_goals`, zero or one `quest_closes`, many `beats`, and many `sessions`. One `sessions` row to many `messages`, many `beat_results`, and many `model_prompts`. One `beats` row to many `beat_results`, and optionally to `sessions.current_beat_id`. One `studio_courses` row to many `studio_quests`, many `studio_moves`, and many `studio_messages`. One `studio_quests` row to many `studio_quest_goals` (position starts at 2), zero or one `studio_quest_close`, and many `studio_moves`.

Check constraints that the diagram attributes do not repeat: `ck_tutor_profiles_singleton` (`id = 'default'`), `ck_tutor_profiles_instructive` (1 through 5), `ck_courses_age_band` and `ck_courses_audience` (`6-8`, `9-11`, `12-14`, `15-17`), `ck_courses_quiz_minutes` and `ck_studio_courses_quiz_minutes` (`2`, `5`, `10`), `ck_quests_type` (`core`, `branch`, `capstone`), `ck_quest_closes_kind` (`essay`, `single`, `multi`, `none`), `ck_beats_role` (`engage`, `try`, `name`, `show`, `teach_back`), `ck_sessions_status` (`in_progress`, `completed`), `ck_messages_role` and `ck_studio_messages_role` (`user`, `assistant`), `ck_beat_results_score` (0 through 100), `ck_studio_courses_depth` (`survey`, `standard`, `go_deep`), `ck_studio_quest_close_style` (`one`, `several`), `ck_studio_quest_close_answer` (`multiple_choice`, `essay`, `mixed`), `ck_studio_quest_close_choice` (null, `predefined`, or `dynamic`), `ck_studio_settings_singleton`, `ck_studio_settings_model` (`gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`), `ck_studio_quest_goals_position` (`position >= 2`).

```mermaid
flowchart TD
  subgraph authoring ["authoring and import"]
    prefForm["CreateCourse patch body"]
    updatePreferences["update_preferences"]
    prefsJson["studio_courses.preferences JSON"]
    getStudioPrompt["GET /studio/courses/id/prompt"]
    systemPromptFn["system_prompt"]
    phaseInstructionsFn["phase_instructions"]
    responseSchemaFn["response_schema"]
    studioChat["POST /api/studio/chat"]
    streamStudio["streamText course_edit"]
    settle["settleModelResult"]
    saveStudioMessage["POST /studio/courses/id/messages"]
    pushDraft["push_draft then apply_patch"]
    importStudio["POST /courses/import-studio"]
    catalogFromStudio["catalog_from_studio"]
    importFile["POST /courses/import"]
    seedCall["seed"]
    validateCourse["validate_course"]
    replaceCourse["replace_course or update_course_in_place"]
  end
  subgraph runtime ["runtime prompt synthesis"]
    openSession["open_session"]
    kidChat["POST /api/chat"]
    getPrompt["GET /sessions/id/prompt"]
    loadPrompt["load_prompt"]
    loadProfile["load_profile"]
    questWalk["_quest_walk"]
    assembleFn["assemble"]
    responseSchemaTutor["RESPONSE_SCHEMA"]
  end
  subgraph execution ["execution and state loop"]
    gradeWidget["grade_widget"]
    streamTutor["streamText turn_score"]
    storePrompt["append_model_prompt"]
    turnScore["apply_turn_score"]
    criterionMet["_criterion_met"]
    advanceMove["_advance_move"]
    completeQuest["_complete"]
    persistRows["messages beat_results sessions model_prompts"]
    viewer["ViewChats GET /sessions and GET /sessions/id"]
  end
  prefForm --> updatePreferences
  updatePreferences --> prefsJson
  prefsJson --> getStudioPrompt
  getStudioPrompt --> systemPromptFn
  systemPromptFn --> phaseInstructionsFn
  getStudioPrompt --> responseSchemaFn
  systemPromptFn --> studioChat
  responseSchemaFn --> studioChat
  studioChat --> streamStudio
  streamStudio --> settle
  settle --> saveStudioMessage
  saveStudioMessage --> pushDraft
  pushDraft --> importStudio
  importStudio --> catalogFromStudio
  catalogFromStudio --> validateCourse
  importFile --> validateCourse
  seedCall --> validateCourse
  validateCourse --> replaceCourse
  replaceCourse --> openSession
  openSession --> kidChat
  kidChat --> gradeWidget
  gradeWidget --> getPrompt
  kidChat --> getPrompt
  getPrompt --> loadPrompt
  loadPrompt --> loadProfile
  loadPrompt --> questWalk
  loadPrompt --> assembleFn
  assembleFn --> responseSchemaTutor
  assembleFn --> streamTutor
  responseSchemaTutor --> streamTutor
  streamTutor --> storePrompt
  streamTutor --> turnScore
  turnScore --> criterionMet
  criterionMet --> advanceMove
  advanceMove --> completeQuest
  turnScore --> persistRows
  storePrompt --> persistRows
  gradeWidget --> persistRows
  persistRows --> viewer
  advanceMove --> getPrompt
```

### 7. One Sample Course Payload

This is the Ancient Rome seed course. `apps/api/app/curriculum/__init__.py` sets `COURSES = [rome_course(), geometry_course(), macro_course()]`. `seed()` passes each payload to `replace_course` or `update_course_in_place`. Both call `validate_course`. `rome_course()` still returns the legacy `units` shape from `apps/api/app/curriculum/rome.py`. `validate_course` detects `units` without `quests` and runs `_flatten`, which sets `description` and `audience` from `age_band`, `quest_count` from the flattened quest list, `goals_per_quest` from `goals_from_points`, `quiz_minutes` to 5, `goals` from `goals_from_points(learning_goal, success_criterion)`, and `close` from `close_from_beats`. There is no separate preferences object on this seed file. Those header fields are the kid-catalog course preferences. Studio tables are not seeded.

The JSON below is the full return value of `validate_course(rome_course())`. Geometry and Macro are separate seed functions and are not pasted here.

```json
{
  "code": "rome",
  "title": "Ancient Rome: From Seven Hills to the Fall of the Empire",
  "age_band": "9-11",
  "standards_alignment": "NCSS C3 Inquiry Arc, Tennessee AH.32, with UK KS2 as the age band.",
  "competency_dictionary": [
    {
      "code": "C3-inquiry",
      "description": "Ask a question, sort the evidence, and state what it can prove."
    },
    {
      "code": "AH.32",
      "description": "Explain Roman geography, the republic, expansion, empire, and decline."
    }
  ],
  "description": "NCSS C3 Inquiry Arc, Tennessee AH.32, with UK KS2 as the age band.",
  "audience": "9-11",
  "quest_count": 16,
  "goals_per_quest": 2,
  "quiz_minutes": 5,
  "quests": [
    {
      "code": "ROM-U1-Q1",
      "title": "The Wolf Myth vs. The Archaeology Clue",
      "quest_type": "core",
      "prerequisite_codes": [],
      "competency_tags": [
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask which tells you more when they disagree: the wolf story, or a wall dug out of the ground.",
      "learning_goal": "I can tell a legend from an archaeological clue.",
      "success_criterion": [
        {
          "id": "story",
          "text": "Says what a story can prove: a meaning the city wanted, not a dated fact.",
          "weight": 50
        },
        {
          "id": "find",
          "text": "Says what a find can prove: a checkable object from the ground.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "low",
          "prompt": "Which of these are archaeological clues rather than the wolf legend?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "poem",
              "trap": "A later poem that repeats the myth becomes a clue.",
              "note": "Repeating a story does not date an object."
            }
          ],
          "hint_ladder": {
            "nudge": "Which items could you dig up and date?",
            "analogy": "A team song is a story. A trophy you can hold is a find.",
            "scaffold": "A clue is an object from the ground, such as ____."
          },
          "widget": {
            "type": "multi",
            "prompt": "Which of these are archaeological clues rather than the wolf legend?",
            "choices": [
              {
                "id": "wolf",
                "text": "The wolf nursed the twins.",
                "misconception": "That is the legend, not an object from the ground."
              },
              {
                "id": "wall",
                "text": "A wall dated to early Rome.",
                "misconception": ""
              },
              {
                "id": "poem",
                "text": "A later poem that says the wolf was real.",
                "misconception": "A poem is still a story."
              },
              {
                "id": "pottery",
                "text": "Pottery found under the Forum.",
                "misconception": ""
              }
            ],
            "answer": [
              "wall",
              "pottery"
            ],
            "explain": false,
            "misconception": "Sort the objects you could dig up from the stories about them."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the sort to the idea: a story can carry a meaning, and a find can be checked again.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "same",
              "trap": "A famous story and a buried wall prove the same kind of fact.",
              "note": "A story can be loved and still not be evidence."
            }
          ],
          "hint_ladder": {
            "nudge": "Ask which pile a different person could measure.",
            "analogy": "A mascot is not the bricks of the clubhouse.",
            "scaffold": "The wolf is a ____. The wall is a ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "In one sentence, say what a story can prove and what a find can prove.",
          "rubric": [
            {
              "id": "story",
              "text": "Says what a story can prove: a meaning the city wanted, not a dated fact.",
              "weight": 50
            },
            {
              "id": "find",
              "text": "Says what a find can prove: a checkable object from the ground.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "erase",
              "trap": "If the wall is real, the story has to be thrown out.",
              "note": "The quest is about what each one is for."
            }
          ],
          "hint_ladder": {
            "nudge": "What can a story give you that a shovel cannot?",
            "analogy": "You can love a campfire story and still follow the map.",
            "scaffold": "The story gives ____. The buried wall gives ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "I can tell a legend from an archaeological clue.",
          "success_criterion": "Says what a story can prove: a meaning the city wanted, not a dated fact."
        },
        {
          "position": 2,
          "learning_goal": "Says what a find can prove: a checkable object from the ground.",
          "success_criterion": "Says what a find can prove: a checkable object from the ground."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 1
    },
    {
      "code": "ROM-U1-Q2",
      "title": "Why Pick Italy? The Alps Shield and Tiber Highway",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U1-Q1"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask how a mountain shield and a river highway could help the same city.",
      "learning_goal": "Italy's Alps and the Tiber made Rome safer and busier.",
      "success_criterion": [
        {
          "id": "shield",
          "text": "Names one advantage of the Alps as a shield against invasion.",
          "weight": 50
        },
        {
          "id": "river",
          "text": "Names one advantage of the Tiber for trade or travel.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "apply",
          "cognitive_load": "low",
          "prompt": "On a map of Italy, which feature is the shield to the north?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "same-job",
              "trap": "The river and the mountains do the same job.",
              "note": "One blocks. One connects."
            }
          ],
          "hint_ladder": {
            "nudge": "Which landmark blocks a march from the north?",
            "analogy": "A fence stops a rush. A path lets food in.",
            "scaffold": "The shield to the north is the ____."
          },
          "widget": {
            "type": "single",
            "prompt": "On a map of Italy, which feature is the shield to the north?",
            "choices": [
              {
                "id": "alps",
                "text": "The Alps.",
                "misconception": ""
              },
              {
                "id": "tiber",
                "text": "The Tiber.",
                "misconception": "The river is the highway, not the shield."
              },
              {
                "id": "sea",
                "text": "The sea on every side.",
                "misconception": "The sea is a coast, not the northern shield."
              }
            ],
            "answer": "alps",
            "explain": false,
            "misconception": "The shield is the mountain wall, not the water."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the map choice to two jobs: the Alps block, and the Tiber carries people and goods.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "same-job",
              "trap": "The river and the mountains do the same job.",
              "note": "One blocks. One connects."
            }
          ],
          "hint_ladder": {
            "nudge": "What does a shield stop, and what does a road carry?",
            "analogy": "A fence keeps a rush out. A path lets friends and food in.",
            "scaffold": "The Alps help by ____. The Tiber helps by ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Name one advantage of the shield and one advantage of the river.",
          "rubric": [
            {
              "id": "shield",
              "text": "Names one advantage of the Alps as a shield against invasion.",
              "weight": 50
            },
            {
              "id": "river",
              "text": "Names one advantage of the Tiber for trade or travel.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "pretty",
              "trap": "The land mattered because it looked grand.",
              "note": "The quest is about safety and traffic, not scenery."
            }
          ],
          "hint_ladder": {
            "nudge": "Say one thing the mountains stop and one thing the river moves.",
            "analogy": "A wall and a road help the same town in different ways.",
            "scaffold": "The Alps ____. The Tiber ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Italy's Alps and the Tiber made Rome safer and busier.",
          "success_criterion": "Names one advantage of the Alps as a shield against invasion."
        },
        {
          "position": 2,
          "learning_goal": "Names one advantage of the Tiber for trade or travel.",
          "success_criterion": "Names one advantage of the Tiber for trade or travel."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 2
    },
    {
      "code": "ROM-U1-Q3",
      "title": "Tarquin the Proud and Why Rome Fired Its Kings",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U1-Q2"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask why a king who ruled for life, in secret, made Romans hate crowns.",
      "learning_goal": "One ruler for life, with secret power, is what Rome refused.",
      "success_criterion": [
        {
          "id": "life",
          "text": "Says one ruler for life was the power Rome refused.",
          "weight": 50
        },
        {
          "id": "secret",
          "text": "Says secret power let that ruler hurt people without a public rule.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "low",
          "prompt": "Which power is the one Rome refused after Tarquin?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "vote",
              "trap": "Romans hated kings because elections are slow.",
              "note": "The fear was lifelong secret power, not the pace of a vote."
            }
          ],
          "hint_ladder": {
            "nudge": "Was the problem a one-year job, or a job with no ending?",
            "analogy": "A referee who can never be replaced starts making secret calls.",
            "scaffold": "Rome refused a ruler who served ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Which power is the one Rome refused after Tarquin?",
            "choices": [
              {
                "id": "year",
                "text": "Two leaders who serve one year and can stop each other.",
                "misconception": "That is the later fix, not the power they refused."
              },
              {
                "id": "life",
                "text": "One ruler for life, with secret power.",
                "misconception": ""
              },
              {
                "id": "law",
                "text": "A law posted where everyone can read it.",
                "misconception": "A public law is a check, not the crown."
              }
            ],
            "answer": "life",
            "explain": false,
            "misconception": "The refused power is one person ruling for life in secret."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the choice to Tarquin: a king for life could punish people without a rule the city could see.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "any-king",
              "trap": "Any single leader is the same as a king.",
              "note": "The fear was life tenure plus secret power."
            }
          ],
          "hint_ladder": {
            "nudge": "Who could check a king who never left office?",
            "analogy": "A captain who keeps the whistle forever can change the score in secret.",
            "scaffold": "The danger was a ruler for ____ who used ____ power."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Say what 'one ruler for life, with secret power' means, and why Rome refused it.",
          "rubric": [
            {
              "id": "life",
              "text": "Says one ruler for life was the power Rome refused.",
              "weight": 50
            },
            {
              "id": "secret",
              "text": "Says secret power let that ruler hurt people without a public rule.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "lazy",
              "trap": "Rome fired kings because they disliked work.",
              "note": "The quest is about unchecked power, not effort."
            }
          ],
          "hint_ladder": {
            "nudge": "What could that ruler do that a one-year leader could not?",
            "analogy": "A locked diary of punishments versus a rule on the wall.",
            "scaffold": "Rome refused a ruler for ____ because the power was ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "One ruler for life, with secret power, is what Rome refused.",
          "success_criterion": "Says one ruler for life was the power Rome refused."
        },
        {
          "position": 2,
          "learning_goal": "Says secret power let that ruler hurt people without a public rule.",
          "success_criterion": "Says secret power let that ruler hurt people without a public rule."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 3
    },
    {
      "code": "ROM-U1-BOSS",
      "title": "Vote Out the King",
      "quest_type": "capstone",
      "prerequisite_codes": [
        "ROM-U1-Q3"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask them to tell a younger cousin why Rome would not take another crown.",
      "learning_goal": "Rome rejected a crown because one ruler for life had used secret power.",
      "success_criterion": [
        {
          "id": "refuse",
          "text": "Says Rome refused another crown after a bad king.",
          "weight": 50
        },
        {
          "id": "why",
          "text": "Gives the secret, lifelong power as the reason.",
          "weight": 50
        }
      ],
      "requires_teach_back": true,
      "beats": [
        {
          "role": "engage",
          "bloom_level": "understand",
          "cognitive_load": "low",
          "prompt": "In one breath: would you give a team captain the whistle for life? Why or why not?",
          "rubric": [
            {
              "id": "choice",
              "text": "Takes a side about lifelong power.",
              "weight": 50
            },
            {
              "id": "reason",
              "text": "Gives one reason about checking that power.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "forever-fine",
              "trap": "A good captain should keep the whistle forever.",
              "note": "The quest is about the power, not about liking the person."
            }
          ],
          "hint_ladder": {
            "nudge": "What happens if nobody can take the whistle back?",
            "analogy": "A game with no substitutions.",
            "scaffold": "A captain for life can ____."
          },
          "widget": null
        },
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Which reason belongs in the vote against another king?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "weather",
              "trap": "Rome fired kings because of a bad harvest.",
              "note": "The political reason is the unchecked crown."
            }
          ],
          "hint_ladder": {
            "nudge": "Which reason is about secret lifelong power?",
            "analogy": "Cross out the reason that is only about weather or luck.",
            "scaffold": "The vote is about ____ power."
          },
          "widget": {
            "type": "single",
            "prompt": "Which reason belongs in the vote against another king?",
            "choices": [
              {
                "id": "secret",
                "text": "One ruler for life used secret power.",
                "misconception": ""
              },
              {
                "id": "hills",
                "text": "The seven hills were too steep.",
                "misconception": "The hills are geography, not the reason to refuse a crown."
              },
              {
                "id": "wolf",
                "text": "The wolf story was too short.",
                "misconception": "The myth is not the charge against the king."
              }
            ],
            "answer": "secret",
            "explain": false,
            "misconception": "The vote is about lifelong secret power."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the vote to Tarquin: the city refused the kind of power he had used.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "person",
              "trap": "They only disliked one man's name.",
              "note": "The refusal is about the kind of power."
            }
          ],
          "hint_ladder": {
            "nudge": "Whose power are they voting against?",
            "analogy": "Firing a coach after a season of secret punishments.",
            "scaffold": "They refused a crown because ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "evaluate",
          "cognitive_load": "medium",
          "prompt": "State the vote: what Rome refused, and why.",
          "rubric": [
            {
              "id": "refuse",
              "text": "Says Rome refused another crown after a bad king.",
              "weight": 50
            },
            {
              "id": "why",
              "text": "Gives the secret, lifelong power as the reason.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "forget",
              "trap": "The vote was to forget the city's past.",
              "note": "They were refusing a kind of rule, not erasing the city."
            }
          ],
          "hint_ladder": {
            "nudge": "Name the power, then the reason.",
            "analogy": "A sign on the clubhouse door: no coach for life.",
            "scaffold": "Rome refused ____ because ____."
          },
          "widget": null
        },
        {
          "role": "teach_back",
          "bloom_level": "evaluate",
          "cognitive_load": "high",
          "prompt": "Crown Bot says a city is safer with one ruler who never has to explain. Correct the bot using Tarquin's secret power.",
          "rubric": [
            {
              "id": "correct",
              "text": "Corrects the claim that an unexplained lifelong ruler is safer.",
              "weight": 50
            },
            {
              "id": "example",
              "text": "Uses secret lifelong power as the example.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "safer",
              "trap": "Never explaining makes a ruler safer.",
              "note": "Hidden power is the danger, not the safety."
            }
          ],
          "hint_ladder": {
            "nudge": "Ask the bot who checks a ruler that never leaves.",
            "analogy": "A referee who will not show the rulebook.",
            "scaffold": "Tell the bot: secret power for life lets a ruler ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Rome rejected a crown because one ruler for life had used secret power.",
          "success_criterion": "Says Rome refused another crown after a bad king."
        },
        {
          "position": 2,
          "learning_goal": "Gives the secret, lifelong power as the reason.",
          "success_criterion": "Gives the secret, lifelong power as the reason."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 4
    },
    {
      "code": "ROM-U2-Q1",
      "title": "The Two-Captain Rule: Consuls and Veto Power",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U1-BOSS"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask what is good and what gets stuck when two captains can each shout veto.",
      "learning_goal": "Two consuls serve for one year and can veto each other, which stops a new king and can also deadlock.",
      "success_criterion": [
        {
          "id": "veto",
          "text": "Two consuls serve one year and each can veto, which stops a new king.",
          "weight": 50
        },
        {
          "id": "deadlock",
          "text": "When the two captains disagree, a decision can stall.",
          "weight": 50
        }
      ],
      "requires_teach_back": true,
      "beats": [
        {
          "role": "engage",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Rome put two consuls in charge for one year, and each one could shout VETO at the other. That veto stops either captain from becoming a king, because neither can act alone. The same veto can freeze a decision when the two captains disagree, and that stall is a deadlock.",
          "rubric": [
            {
              "id": "advantage",
              "text": "Names an advantage that stops one bully or a king.",
              "weight": 50
            },
            {
              "id": "problem",
              "text": "Names deadlock or arguing in an emergency.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "solo-boss",
              "trap": "One boss is always safer because someone has to decide.",
              "note": "The veto is the point: neither captain can become a king."
            }
          ],
          "hint_ladder": {
            "nudge": "What happens when an enemy army attacks and the consuls disagree?",
            "analogy": "Picture two kids holding one video-game controller.",
            "scaffold": "Two consuls can stop a ____, but they can also ____."
          },
          "widget": null
        },
        {
          "role": "try",
          "bloom_level": "apply",
          "cognitive_load": "low",
          "prompt": "What fails when the two captains disagree?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "walkout",
              "trap": "The 494 BCE walkout is what fails when consuls disagree.",
              "note": "The walkout is a later quest. This try is about the two captains stalling."
            },
            {
              "id": "king",
              "trap": "Disagreement turns one consul into a king for life.",
              "note": "A veto stops that promotion. The failure is the stall."
            }
          ],
          "hint_ladder": {
            "nudge": "If neither captain can force the other, what happens to the decision?",
            "analogy": "Two hands on one controller, pulling opposite ways.",
            "scaffold": "The decision ____."
          },
          "widget": {
            "type": "single",
            "prompt": "What fails when the two captains disagree?",
            "choices": [
              {
                "id": "deadlock",
                "text": "The decision can stall, because each can veto the other.",
                "misconception": ""
              },
              {
                "id": "king",
                "text": "One consul becomes king for life.",
                "misconception": "A veto blocks that. The mess is the stall."
              },
              {
                "id": "walkout",
                "text": "The plebeians leave the city in 494 BCE.",
                "misconception": "That walkout is a later quest, not this disagreement."
              }
            ],
            "answer": "deadlock",
            "explain": false,
            "misconception": "When the two captains disagree, the decision can stall."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "A veto stops one consul from turning into a king, and the same veto can freeze a decision when the two captains disagree. The stall is the cost of that protection.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "only-good",
              "trap": "A veto has no cost.",
              "note": "The cost is deadlock."
            }
          ],
          "hint_ladder": {
            "nudge": "Which part of the rule stops a crown, and which part causes the stall?",
            "analogy": "A lock that keeps a bully out can also jam the door.",
            "scaffold": "The veto stops ____ and can cause ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Say how two consuls for one year, each able to veto, stop a new king and can deadlock.",
          "rubric": [
            {
              "id": "veto",
              "text": "Two consuls serve one year and each can veto, which stops a new king.",
              "weight": 50
            },
            {
              "id": "deadlock",
              "text": "When the two captains disagree, a decision can stall.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "one-job",
              "trap": "The veto only creates a new king.",
              "note": "The veto is the check, and the stall is the cost."
            }
          ],
          "hint_ladder": {
            "nudge": "Use both the stop and the stall.",
            "analogy": "Two captains, one year, one shared whistle.",
            "scaffold": "They stop a king because ____. They can deadlock because ____."
          },
          "widget": null
        },
        {
          "role": "teach_back",
          "bloom_level": "evaluate",
          "cognitive_load": "high",
          "prompt": "Bumbling Centurion Bot says the city should pick one consul for life so nobody can veto him. Correct the bot.",
          "rubric": [
            {
              "id": "stop",
              "text": "Shows that losing the veto brings back a king.",
              "weight": 50
            },
            {
              "id": "cost",
              "text": "Admits the veto can deadlock and still keeps it.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "faster",
              "trap": "Speed matters more than the check on a king.",
              "note": "The quest keeps the veto even though it can stall."
            }
          ],
          "hint_ladder": {
            "nudge": "Ask the bot what the veto was invented to stop.",
            "analogy": "A spare key that sometimes jams the lock and still keeps the bully out.",
            "scaffold": "Tell the bot: one consul for life is a ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Two consuls serve for one year and can veto each other, which stops a new king and can also deadlock.",
          "success_criterion": "Two consuls serve one year and each can veto, which stops a new king."
        },
        {
          "position": 2,
          "learning_goal": "When the two captains disagree, a decision can stall.",
          "success_criterion": "When the two captains disagree, a decision can stall."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 5
    },
    {
      "code": "ROM-U2-Q2",
      "title": "The Twelve Bronze Tables",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U2-Q1"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask why a law you can read in public protects you from a judge's friends.",
      "learning_goal": "Public bronze laws stop a judge from inventing the rule.",
      "success_criterion": [
        {
          "id": "secret",
          "text": "Secret law lets the judge favor friends.",
          "weight": 50
        },
        {
          "id": "posted",
          "text": "A posted law is the same rule for everyone.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Which rule protects ordinary people from a judge who plays favorites?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "memory",
              "trap": "A judge's memory is the same as a public law.",
              "note": "Memory can change for a friend. A posted law cannot."
            }
          ],
          "hint_ladder": {
            "nudge": "Can you argue with a rule you were never allowed to read?",
            "analogy": "A secret recipe versus the rules posted on the gym wall.",
            "scaffold": "Protection comes from a law that is ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Which rule protects ordinary people from a judge who plays favorites?",
            "choices": [
              {
                "id": "secret",
                "text": "The judge keeps the rule in his head.",
                "misconception": "A secret rule lets him favor friends."
              },
              {
                "id": "posted",
                "text": "The law is posted in bronze where everyone can read it.",
                "misconception": ""
              },
              {
                "id": "friend",
                "text": "The judge explains the rule only to his friends.",
                "misconception": "That is still a secret rule."
              }
            ],
            "answer": "posted",
            "explain": false,
            "misconception": "A secret law lets the judge invent the rule for his friends."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the posted bronze to fairness: the same words apply to a friend and to a stranger.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "rich",
              "trap": "Public laws only help people who already know the judge.",
              "note": "The point is that strangers can read the same words."
            }
          ],
          "hint_ladder": {
            "nudge": "Who can read a tablet in the forum?",
            "analogy": "A scoreboard everyone can see, not a score whispered to one team.",
            "scaffold": "A posted law is the same rule for ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Say why secret law lets a judge favor friends, and why a posted law is the same rule for everyone.",
          "rubric": [
            {
              "id": "secret",
              "text": "Secret law lets the judge favor friends.",
              "weight": 50
            },
            {
              "id": "posted",
              "text": "A posted law is the same rule for everyone.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "style",
              "trap": "The bronze mattered because it looked expensive.",
              "note": "The bronze mattered because the words were public."
            }
          ],
          "hint_ladder": {
            "nudge": "Contrast a hidden rule with a bronze tablet.",
            "analogy": "One rule in a pocket, one rule on the wall.",
            "scaffold": "Secret law ____. A posted law ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Public bronze laws stop a judge from inventing the rule.",
          "success_criterion": "Secret law lets the judge favor friends."
        },
        {
          "position": 2,
          "learning_goal": "A posted law is the same rule for everyone.",
          "success_criterion": "A posted law is the same rule for everyone."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 6
    },
    {
      "code": "ROM-U2-Q3",
      "title": "Hannibal's Elephants and the Punic Wars",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U2-Q2"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask how a republic can survive a long war without making one general king.",
      "learning_goal": "A republic can survive a military crisis without handing the army to one man for life.",
      "success_criterion": [
        {
          "id": "survive",
          "text": "The republic can outlast a military crisis.",
          "weight": 50
        },
        {
          "id": "no-crown",
          "text": "It does not have to hand the army to one man for life.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Hannibal is winning battles in Italy. What can the republic do without making one general king?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "crown",
              "trap": "A crisis means the general must become king.",
              "note": "The quest is that the republic can survive without that."
            }
          ],
          "hint_ladder": {
            "nudge": "Which choice keeps the one-year rule?",
            "analogy": "A team can change captains and still finish the season.",
            "scaffold": "The republic can ____ without a king."
          },
          "widget": {
            "type": "single",
            "prompt": "Hannibal is winning battles in Italy. What can the republic do without making one general king?",
            "choices": [
              {
                "id": "dictator-year",
                "text": "Appoint a temporary commander who must give the power back.",
                "misconception": ""
              },
              {
                "id": "crown",
                "text": "Hand the army to one man for life.",
                "misconception": "That ends the republic's check."
              },
              {
                "id": "quit",
                "text": "Disband the army and hope Hannibal leaves.",
                "misconception": "The republic fought on. It did not have to crown a king."
              }
            ],
            "answer": "dictator-year",
            "explain": false,
            "misconception": "A crisis does not require a king for life."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the temporary command to the idea: the city can fight a war and still take the power back.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "same",
              "trap": "A temporary dictator is the same as a king.",
              "note": "The difference is that the power is returned."
            }
          ],
          "hint_ladder": {
            "nudge": "What has to happen to the extra power when the crisis ends?",
            "analogy": "Borrowing a louder whistle for one game, then giving it back.",
            "scaffold": "The extra command is ____, not for life."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Explain how a republic can survive a military crisis without handing the army to one man for life.",
          "rubric": [
            {
              "id": "survive",
              "text": "The republic can outlast a military crisis.",
              "weight": 50
            },
            {
              "id": "no-crown",
              "text": "It does not have to hand the army to one man for life.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "elephants",
              "trap": "Elephants made a king legally necessary.",
              "note": "The animals are the crisis, not a reason to end the republic."
            }
          ],
          "hint_ladder": {
            "nudge": "Name the crisis and the limit on the commander.",
            "analogy": "A substitute captain with an expiration date.",
            "scaffold": "During the war the republic can ____. It does not have to ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "A republic can survive a military crisis without handing the army to one man for life.",
          "success_criterion": "The republic can outlast a military crisis."
        },
        {
          "position": 2,
          "learning_goal": "It does not have to hand the army to one man for life.",
          "success_criterion": "It does not have to hand the army to one man for life."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 7
    },
    {
      "code": "ROM-U2-BOSS",
      "title": "Debate in the Roman Forum",
      "quest_type": "capstone",
      "prerequisite_codes": [
        "ROM-U2-Q3"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask them to defend shared power and a public law in one argument.",
      "learning_goal": "Shared power and a public law can be defended out loud in the Forum.",
      "success_criterion": [
        {
          "id": "power",
          "text": "Defends shared power as the check on one ruler.",
          "weight": 50
        },
        {
          "id": "law",
          "text": "Defends a public law as the same rule for ordinary people.",
          "weight": 50
        }
      ],
      "requires_teach_back": true,
      "beats": [
        {
          "role": "engage",
          "bloom_level": "understand",
          "cognitive_load": "low",
          "prompt": "You have the Forum floor for one sentence. Which office would you defend first: the veto, or the posted law?",
          "rubric": [
            {
              "id": "pick",
              "text": "Picks the veto or the posted law.",
              "weight": 50
            },
            {
              "id": "why",
              "text": "Gives one reason ordinary people need it.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "neither",
              "trap": "Ordinary people do not need either check.",
              "note": "Both checks were built for them."
            }
          ],
          "hint_ladder": {
            "nudge": "Which one stops a single person from inventing the rules?",
            "analogy": "Two shields: one against a king, one against a secret judge.",
            "scaffold": "I would defend ____ because ____."
          },
          "widget": null
        },
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "A speaker says one consul for life would be simpler. Which reply fits the republic?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "simple",
              "trap": "Simpler government is always the republic's goal.",
              "note": "The goal is a check on one ruler."
            }
          ],
          "hint_ladder": {
            "nudge": "What did the veto exist to prevent?",
            "analogy": "Simpler is not the same as safe.",
            "scaffold": "The reply should protect ____."
          },
          "widget": {
            "type": "single",
            "prompt": "A speaker says one consul for life would be simpler. Which reply fits the republic?",
            "choices": [
              {
                "id": "veto",
                "text": "The veto is there so neither captain can become king.",
                "misconception": ""
              },
              {
                "id": "simple",
                "text": "Simpler is better, so drop the veto.",
                "misconception": "That gives back the crown the city refused."
              },
              {
                "id": "secret",
                "text": "Let the consul keep the law in his head.",
                "misconception": "That is the secret law the tablets were meant to stop."
              }
            ],
            "answer": "veto",
            "explain": false,
            "misconception": "Simpler one-man rule is the crown the republic refused."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the reply to both tools: the veto checks the man, and the tablet checks the rule.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "one-tool",
              "trap": "The veto also posts the law.",
              "note": "They are different checks."
            }
          ],
          "hint_ladder": {
            "nudge": "Which tool is about who decides, and which is about the words of the rule?",
            "analogy": "A spare captain and a rulebook on the wall.",
            "scaffold": "The veto checks ____. The tablet checks ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "evaluate",
          "cognitive_load": "medium",
          "prompt": "Make the Forum argument: how shared power and a public law protect ordinary people.",
          "rubric": [
            {
              "id": "power",
              "text": "Defends shared power as the check on one ruler.",
              "weight": 50
            },
            {
              "id": "law",
              "text": "Defends a public law as the same rule for ordinary people.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "army",
              "trap": "The argument is that the biggest army should rule.",
              "note": "The Forum argument is about law and shared office."
            }
          ],
          "hint_ladder": {
            "nudge": "Give one sentence for the veto and one for the tablet.",
            "analogy": "Speak as if the crowd can hear both checks.",
            "scaffold": "Shared power ____. A public law ____."
          },
          "widget": null
        },
        {
          "role": "teach_back",
          "bloom_level": "evaluate",
          "cognitive_load": "high",
          "prompt": "Forum Bot says ordinary people are safer when one expert makes secret decisions. Correct the bot with the veto and the bronze law.",
          "rubric": [
            {
              "id": "veto",
              "text": "Uses the veto as the check on one ruler.",
              "weight": 50
            },
            {
              "id": "bronze",
              "text": "Uses the posted law as the same rule for everyone.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "expert",
              "trap": "An expert's secret decision is the same as a public law.",
              "note": "Secrecy is what the tablet was built to end."
            }
          ],
          "hint_ladder": {
            "nudge": "Ask the bot who the secret decision is allowed to favor.",
            "analogy": "A coach who will not show the rulebook to the bench.",
            "scaffold": "Tell the bot: the veto stops ____, and the tablet stops ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Shared power and a public law can be defended out loud in the Forum.",
          "success_criterion": "Defends shared power as the check on one ruler."
        },
        {
          "position": 2,
          "learning_goal": "Defends a public law as the same rule for ordinary people.",
          "success_criterion": "Defends a public law as the same rule for ordinary people."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 8
    },
    {
      "code": "ROM-U3-Q1",
      "title": "Generals vs. The Senate",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U2-BOSS"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask what changes when soldiers obey a general instead of the Senate.",
      "learning_goal": "An army that obeys its general instead of the Senate no longer protects the republic.",
      "success_criterion": [
        {
          "id": "army",
          "text": "An army that follows its general is not obeying the Senate.",
          "weight": 50
        },
        {
          "id": "law",
          "text": "That loyalty ends the republic's claim that the law is in charge.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Who is in charge if the soldiers will march only when their general says so?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "senate-still",
              "trap": "The Senate is still in charge if it passes a speech.",
              "note": "A speech is not command if the army will not move."
            }
          ],
          "hint_ladder": {
            "nudge": "Whose order do the soldiers actually follow?",
            "analogy": "A team that listens to the star player and ignores the coach.",
            "scaffold": "The army is loyal to ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Who is in charge if the soldiers will march only when their general says so?",
            "choices": [
              {
                "id": "general",
                "text": "The general, because the army moves for him.",
                "misconception": ""
              },
              {
                "id": "senate",
                "text": "The Senate, because it still meets.",
                "misconception": "A meeting without the army is not control of the army."
              },
              {
                "id": "people",
                "text": "The voters, because they elected the consuls last year.",
                "misconception": "Last year's election does not command this army."
              }
            ],
            "answer": "general",
            "explain": false,
            "misconception": "An army that marches for its general is not obeying the Senate."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect that loyalty to the end of the republic: the law cannot rule if the swords belong to one man.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "pay",
              "trap": "The only issue is the general's salary.",
              "note": "The issue is who the army obeys."
            }
          ],
          "hint_ladder": {
            "nudge": "What does the Senate lack if the soldiers ignore it?",
            "analogy": "A rulebook with no one willing to enforce it.",
            "scaffold": "The republic ends when the army follows ____ instead of ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Explain how an army loyal to a general instead of the law ends the republic.",
          "rubric": [
            {
              "id": "army",
              "text": "An army that follows its general is not obeying the Senate.",
              "weight": 50
            },
            {
              "id": "law",
              "text": "That loyalty ends the republic's claim that the law is in charge.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "border",
              "trap": "The republic ends only when a foreign king arrives.",
              "note": "The break here is inside the army's loyalty."
            }
          ],
          "hint_ladder": {
            "nudge": "Name who the soldiers obey, then what the Senate loses.",
            "analogy": "The whistle moves from the rulebook to one player's pocket.",
            "scaffold": "The army obeys ____. The law ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "An army that obeys its general instead of the Senate no longer protects the republic.",
          "success_criterion": "An army that follows its general is not obeying the Senate."
        },
        {
          "position": 2,
          "learning_goal": "That loyalty ends the republic's claim that the law is in charge.",
          "success_criterion": "That loyalty ends the republic's claim that the law is in charge."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 9
    },
    {
      "code": "ROM-U3-Q2",
      "title": "Crossing the Rubicon",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U3-Q1"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask why marching an army across one river was an attack on the law.",
      "learning_goal": "Crossing the Rubicon with an army was the point where Caesar put his soldiers above the law.",
      "success_criterion": [
        {
          "id": "cross",
          "text": "Names the crossing as the moment the army entered Italy against the law.",
          "weight": 50
        },
        {
          "id": "man",
          "text": "Says the soldiers were serving Caesar, not the Senate.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "What made the Rubicon crossing different from moving troops in Gaul?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "bath",
              "trap": "The Rubicon mattered because the water was deep.",
              "note": "The river was the legal line, not a swimming test."
            }
          ],
          "hint_ladder": {
            "nudge": "Which side of the river was Italy, under the Senate's rule?",
            "analogy": "A player stepping over the sideline with the whole team behind him.",
            "scaffold": "Crossing into Italy with an army was ____."
          },
          "widget": {
            "type": "single",
            "prompt": "What made the Rubicon crossing different from moving troops in Gaul?",
            "choices": [
              {
                "id": "illegal",
                "text": "He brought an army into Italy, which a general was not allowed to do.",
                "misconception": ""
              },
              {
                "id": "far",
                "text": "Gaul was farther from the sea.",
                "misconception": "Distance is not the legal line."
              },
              {
                "id": "winter",
                "text": "It was too cold to march.",
                "misconception": "The quest is about the law, not the weather."
              }
            ],
            "answer": "illegal",
            "explain": false,
            "misconception": "The crossing put an army where the law said a general could not bring one."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the river to loyalty: the soldiers crossed for Caesar, not because the Senate ordered it.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "map",
              "trap": "The Rubicon was only a geography lesson.",
              "note": "It was the legal boundary of Italy."
            }
          ],
          "hint_ladder": {
            "nudge": "Who gave the order to cross?",
            "analogy": "A captain leading the team onto the field after the referee said stop.",
            "scaffold": "They crossed for ____, against ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Explain why crossing the Rubicon with an army put the soldiers above the law.",
          "rubric": [
            {
              "id": "cross",
              "text": "Names the crossing as the moment the army entered Italy against the law.",
              "weight": 50
            },
            {
              "id": "man",
              "text": "Says the soldiers were serving Caesar, not the Senate.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "bridge",
              "trap": "Any bridge is a crime.",
              "note": "The crime was an army crossing that legal line."
            }
          ],
          "hint_ladder": {
            "nudge": "Name the line and who the army was serving.",
            "analogy": "One step that turns a general into the government.",
            "scaffold": "The army entered Italy for ____. The Senate's law ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Crossing the Rubicon with an army was the point where Caesar put his soldiers above the law.",
          "success_criterion": "Names the crossing as the moment the army entered Italy against the law."
        },
        {
          "position": 2,
          "learning_goal": "Says the soldiers were serving Caesar, not the Senate.",
          "success_criterion": "Says the soldiers were serving Caesar, not the Senate."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 10
    },
    {
      "code": "ROM-U3-Q3",
      "title": "The Ides of March",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U3-Q2"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask why senators used daggers when they believed the law could not stop one man.",
      "learning_goal": "The Ides of March showed senators using murder because they saw no legal way to stop one man.",
      "success_criterion": [
        {
          "id": "murder",
          "text": "Senators killed Caesar because they feared one-man rule.",
          "weight": 50
        },
        {
          "id": "no-law",
          "text": "They saw no legal way left to stop him.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Why did the senators kill Caesar instead of voting him out of a one-year office?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "calendar",
              "trap": "They were confused about the date.",
              "note": "The date is the name of the event, not the cause."
            }
          ],
          "hint_ladder": {
            "nudge": "Did he still hold a normal one-year consulship they could simply wait out?",
            "analogy": "A team that no longer believes the rulebook can remove the captain.",
            "scaffold": "They used murder because they saw no ____ left."
          },
          "widget": {
            "type": "single",
            "prompt": "Why did the senators kill Caesar instead of voting him out of a one-year office?",
            "choices": [
              {
                "id": "no-law",
                "text": "They believed no legal check could remove him anymore.",
                "misconception": ""
              },
              {
                "id": "fun",
                "text": "They wanted a festival on that date.",
                "misconception": "The Ides was an assassination, not a party."
              },
              {
                "id": "gaul",
                "text": "He had never commanded an army.",
                "misconception": "He had an army. That is why the law felt powerless."
              }
            ],
            "answer": "no-law",
            "explain": false,
            "misconception": "They struck because they thought the republic's legal tools were already gone."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the assassination to a failed check: murder replaced a law that could no longer remove him.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "legal",
              "trap": "The Ides was an ordinary legal trial.",
              "note": "It was killing, which shows the trial no longer felt available."
            }
          ],
          "hint_ladder": {
            "nudge": "What tool did they no longer trust?",
            "analogy": "Breaking the whistle because nobody will blow it.",
            "scaffold": "They used ____ because the ____ could not stop him."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Explain the Ides as senators choosing murder because they saw no legal way to stop one man.",
          "rubric": [
            {
              "id": "murder",
              "text": "Senators killed Caesar because they feared one-man rule.",
              "weight": 50
            },
            {
              "id": "no-law",
              "text": "They saw no legal way left to stop him.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "prophecy",
              "trap": "A soothsayer's warning caused the politics.",
              "note": "The warning is a story around the political break."
            }
          ],
          "hint_ladder": {
            "nudge": "Name the act and the missing legal check.",
            "analogy": "A last play that is not in the rulebook.",
            "scaffold": "They killed him because ____. That shows the law ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "The Ides of March showed senators using murder because they saw no legal way to stop one man.",
          "success_criterion": "Senators killed Caesar because they feared one-man rule."
        },
        {
          "position": 2,
          "learning_goal": "They saw no legal way left to stop him.",
          "success_criterion": "They saw no legal way left to stop him."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 11
    },
    {
      "code": "ROM-U3-BOSS",
      "title": "Put Caesar on Trial",
      "quest_type": "capstone",
      "prerequisite_codes": [
        "ROM-U3-Q3"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask them to charge or defend Caesar using the army and the law.",
      "learning_goal": "Caesar can be judged by whether his army served the law or the man.",
      "success_criterion": [
        {
          "id": "charge",
          "text": "States a charge about the army and the law.",
          "weight": 50
        },
        {
          "id": "evidence",
          "text": "Uses one event, such as the Rubicon or the Ides, as evidence.",
          "weight": 50
        }
      ],
      "requires_teach_back": true,
      "beats": [
        {
          "role": "engage",
          "bloom_level": "understand",
          "cognitive_load": "low",
          "prompt": "You are on the jury. In one sentence, did the army serve the law or the man?",
          "rubric": [
            {
              "id": "side",
              "text": "Says law or man.",
              "weight": 50
            },
            {
              "id": "clue",
              "text": "Names one event as the clue.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "costume",
              "trap": "The trial is about what he wore.",
              "note": "The charge is about the army and the law."
            }
          ],
          "hint_ladder": {
            "nudge": "Which event would you hold up first?",
            "analogy": "A trial where the exhibit is a river crossing.",
            "scaffold": "The army served ____ when it ____."
          },
          "widget": null
        },
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Which exhibit best shows the army serving the man?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "ides-only",
              "trap": "Only the Ides shows loyalty, and the crossing does not count.",
              "note": "The crossing is the army acting for the man."
            }
          ],
          "hint_ladder": {
            "nudge": "Which act put soldiers where the Senate had forbidden them?",
            "analogy": "Pick the moment the team crossed the sideline together.",
            "scaffold": "The exhibit is the ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Which exhibit best shows the army serving the man?",
            "choices": [
              {
                "id": "rubicon",
                "text": "The Rubicon crossing.",
                "misconception": ""
              },
              {
                "id": "tables",
                "text": "The Twelve Tables.",
                "misconception": "Those are public laws from the republic, not Caesar's army."
              },
              {
                "id": "alps",
                "text": "The Alps.",
                "misconception": "That is geography, not the charge."
              }
            ],
            "answer": "rubicon",
            "explain": false,
            "misconception": "The army serving the man is the illegal crossing, not a landform or an old tablet."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the exhibit to the verdict: the soldiers moved for Caesar against the Senate's rule.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "neutral",
              "trap": "An army crossing a river is always neutral.",
              "note": "This crossing was against the rule."
            }
          ],
          "hint_ladder": {
            "nudge": "Who gave the order the Senate had refused?",
            "analogy": "The exhibit is the footprint across the line.",
            "scaffold": "The crossing shows the army served ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "evaluate",
          "cognitive_load": "medium",
          "prompt": "Give the verdict: one charge about the army and the law, with one event as evidence.",
          "rubric": [
            {
              "id": "charge",
              "text": "States a charge about the army and the law.",
              "weight": 50
            },
            {
              "id": "evidence",
              "text": "Uses one event, such as the Rubicon or the Ides, as evidence.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "personality",
              "trap": "The verdict is whether he was likable.",
              "note": "The verdict is about the army and the law."
            }
          ],
          "hint_ladder": {
            "nudge": "State the charge, then the evidence.",
            "analogy": "A lawyer holding up one river and one rule.",
            "scaffold": "The charge is ____. The evidence is ____."
          },
          "widget": null
        },
        {
          "role": "teach_back",
          "bloom_level": "evaluate",
          "cognitive_load": "high",
          "prompt": "Trial Bot says Caesar's army still served the law because the Senate continued to exist. Correct the bot.",
          "rubric": [
            {
              "id": "obey",
              "text": "Shows the army obeyed the general, not the Senate.",
              "weight": 50
            },
            {
              "id": "event",
              "text": "Uses the Rubicon or the Ides as the evidence.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "building",
              "trap": "A meeting room means the law still commands the army.",
              "note": "Command is who the soldiers obey."
            }
          ],
          "hint_ladder": {
            "nudge": "Ask the bot whose order the soldiers followed at the river.",
            "analogy": "A court that still has a building while the guards follow someone else.",
            "scaffold": "Tell the bot: the Senate can meet and still have lost ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Caesar can be judged by whether his army served the law or the man.",
          "success_criterion": "States a charge about the army and the law."
        },
        {
          "position": 2,
          "learning_goal": "Uses one event, such as the Rubicon or the Ides, as evidence.",
          "success_criterion": "Uses one event, such as the Rubicon or the Ides, as evidence."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 12
    },
    {
      "code": "ROM-U4-Q1",
      "title": "Augustus and Pax Romana",
      "quest_type": "core",
      "prerequisite_codes": [
        "ROM-U3-BOSS"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask how a man can keep the offices of a republic and still hold the army.",
      "learning_goal": "Augustus kept the look of shared power while one man held the army and the peace.",
      "success_criterion": [
        {
          "id": "look",
          "text": "Augustus kept the look of shared offices.",
          "weight": 50
        },
        {
          "id": "army",
          "text": "One man still held the army and the peace.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "What did Augustus keep, and what did he actually hold?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "ended-names",
              "trap": "He abolished every old office on day one.",
              "note": "He kept the look of the offices."
            }
          ],
          "hint_ladder": {
            "nudge": "Did the old offices disappear, or did they keep their names?",
            "analogy": "A club that still has co-captains on the poster while one person owns the bus.",
            "scaffold": "He kept the ____ and held the ____."
          },
          "widget": {
            "type": "single",
            "prompt": "What did Augustus keep, and what did he actually hold?",
            "choices": [
              {
                "id": "both",
                "text": "The look of shared offices, while he held the army.",
                "misconception": ""
              },
              {
                "id": "nothing",
                "text": "He kept no old titles at all.",
                "misconception": "The titles stayed. The army did not stay shared."
              },
              {
                "id": "vote",
                "text": "He held only a one-year veto and no army.",
                "misconception": "The peace rested on his control of the army."
              }
            ],
            "answer": "both",
            "explain": false,
            "misconception": "The offices remained as a look. The army was his."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the peaceful years to that split: the city saw shared titles, and the soldiers answered to one man.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "vote-back",
              "trap": "The old veto still commanded the legions.",
              "note": "The legions answered to Augustus."
            }
          ],
          "hint_ladder": {
            "nudge": "Who could end the peace if the army was his?",
            "analogy": "A quiet street with one person holding every key.",
            "scaffold": "The look was ____. The power was ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Explain how Augustus kept the look of shared power while one man held the army and the peace.",
          "rubric": [
            {
              "id": "look",
              "text": "Augustus kept the look of shared offices.",
              "weight": 50
            },
            {
              "id": "army",
              "text": "One man still held the army and the peace.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "war",
              "trap": "Pax Romana means the wars got bigger every year.",
              "note": "The name is a peace held by his power."
            }
          ],
          "hint_ladder": {
            "nudge": "Name the look, then the army.",
            "analogy": "A republic costume on a one-man army.",
            "scaffold": "People still saw ____. He held ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Augustus kept the look of shared power while one man held the army and the peace.",
          "success_criterion": "Augustus kept the look of shared offices."
        },
        {
          "position": 2,
          "learning_goal": "One man still held the army and the peace.",
          "success_criterion": "One man still held the army and the peace."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 13
    },
    {
      "code": "ROM-U4-Q2A",
      "title": "Aqueducts and Concrete",
      "quest_type": "branch",
      "prerequisite_codes": [
        "ROM-U4-Q1"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask how water and stone let one city serve a huge population.",
      "learning_goal": "Aqueducts and concrete let a large empire move water and build durable public works.",
      "success_criterion": [
        {
          "id": "water",
          "text": "Aqueducts moved water into a large city.",
          "weight": 50
        },
        {
          "id": "stone",
          "text": "Concrete let public buildings last.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Which pair is the engineering that held daily life in a large city?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "stories",
              "trap": "Myths and poems were the city's plumbing.",
              "note": "The quest is about water and stone."
            }
          ],
          "hint_ladder": {
            "nudge": "What brings water in, and what makes a big building last?",
            "analogy": "A hose uphill and a brick that does not wash away.",
            "scaffold": "The pair is ____ and ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Which pair is the engineering that held daily life in a large city?",
            "choices": [
              {
                "id": "works",
                "text": "Aqueducts and concrete.",
                "misconception": ""
              },
              {
                "id": "crowns",
                "text": "Crowns and secret trials.",
                "misconception": "Those are politics, not the water and the stone."
              },
              {
                "id": "elephants",
                "text": "Elephants and winter camps.",
                "misconception": "Those are the war, not the city works."
              }
            ],
            "answer": "works",
            "explain": false,
            "misconception": "The works in this branch are aqueducts and concrete."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the pair to size: water and durable stone let the city stay large.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "paint",
              "trap": "Concrete mattered because it was a color.",
              "note": "It mattered because the structure lasted."
            }
          ],
          "hint_ladder": {
            "nudge": "What fails in a huge city with no clean water?",
            "analogy": "A tower of blocks that can carry a road and a channel.",
            "scaffold": "Aqueducts move ____. Concrete lets buildings ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Give one job of the aqueduct and one job of the concrete.",
          "rubric": [
            {
              "id": "water",
              "text": "Aqueducts moved water into a large city.",
              "weight": 50
            },
            {
              "id": "stone",
              "text": "Concrete let public buildings last.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "army",
              "trap": "Aqueducts were only for moving soldiers.",
              "note": "This quest is the water and the buildings."
            }
          ],
          "hint_ladder": {
            "nudge": "Water first, then the lasting stone.",
            "analogy": "A channel and a wall that stays up.",
            "scaffold": "The aqueduct ____. The concrete ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Aqueducts and concrete let a large empire move water and build durable public works.",
          "success_criterion": "Aqueducts moved water into a large city."
        },
        {
          "position": 2,
          "learning_goal": "Concrete let public buildings last.",
          "success_criterion": "Concrete let public buildings last."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 14
    },
    {
      "code": "ROM-U4-Q2B",
      "title": "Pompeii and the Colosseum",
      "quest_type": "branch",
      "prerequisite_codes": [
        "ROM-U4-Q1"
      ],
      "competency_tags": [
        "AH.32",
        "C3-inquiry"
      ],
      "dinner_prompt": "Ask what a buried city and a giant arena each show about life in the empire.",
      "learning_goal": "Pompeii and the Colosseum show daily city life and public spectacle inside the empire.",
      "success_criterion": [
        {
          "id": "daily",
          "text": "Pompeii preserves daily city life.",
          "weight": 50
        },
        {
          "id": "show",
          "text": "The Colosseum shows public spectacle for a huge crowd.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Which source shows ordinary rooms, streets, and food rather than a staged show?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "same",
              "trap": "The arena and the buried town show the same kind of evidence.",
              "note": "One is a spectacle. One is a town stopped in place."
            }
          ],
          "hint_ladder": {
            "nudge": "Which place was a town, and which was an arena?",
            "analogy": "A buried house versus a stadium.",
            "scaffold": "Daily life is the clue from ____."
          },
          "widget": {
            "type": "single",
            "prompt": "Which source shows ordinary rooms, streets, and food rather than a staged show?",
            "choices": [
              {
                "id": "pompeii",
                "text": "Pompeii.",
                "misconception": ""
              },
              {
                "id": "colosseum",
                "text": "The Colosseum.",
                "misconception": "That is the public spectacle, not the kitchen and the street."
              },
              {
                "id": "rubicon",
                "text": "The Rubicon.",
                "misconception": "That is a political line, not daily city life."
              }
            ],
            "answer": "pompeii",
            "explain": false,
            "misconception": "Pompeii preserves daily life. The Colosseum is the show."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the two sites: one froze a town, and one held a crowd for a show.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "fake",
              "trap": "Pompeii is only a legend with no objects.",
              "note": "The ash kept real rooms."
            }
          ],
          "hint_ladder": {
            "nudge": "What can you learn from a kitchen that you cannot learn from an arena?",
            "analogy": "A photograph of a house and a ticket to a stadium.",
            "scaffold": "Pompeii shows ____. The Colosseum shows ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "analyze",
          "cognitive_load": "medium",
          "prompt": "Say what Pompeii can prove about daily life and what the Colosseum can prove about public spectacle.",
          "rubric": [
            {
              "id": "daily",
              "text": "Pompeii preserves daily city life.",
              "weight": 50
            },
            {
              "id": "show",
              "text": "The Colosseum shows public spectacle for a huge crowd.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "kings",
              "trap": "Both sites prove why Rome fired its kings.",
              "note": "This branch is city life and spectacle."
            }
          ],
          "hint_ladder": {
            "nudge": "One sentence, two places, two kinds of evidence.",
            "analogy": "A stopped town and a giant stage.",
            "scaffold": "Pompeii proves ____. The Colosseum proves ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "Pompeii and the Colosseum show daily city life and public spectacle inside the empire.",
          "success_criterion": "Pompeii preserves daily city life."
        },
        {
          "position": 2,
          "learning_goal": "The Colosseum shows public spectacle for a huge crowd.",
          "success_criterion": "The Colosseum shows public spectacle for a huge crowd."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 15
    },
    {
      "code": "ROM-U4-BOSS",
      "title": "Why Rome Split",
      "quest_type": "capstone",
      "prerequisite_codes": [
        "ROM-U4-Q2A",
        "ROM-U4-Q2B"
      ],
      "competency_tags": [
        "AH.32"
      ],
      "dinner_prompt": "Ask how the same size that the roads held together later pulled the empire apart.",
      "learning_goal": "The empire's size, which roads and water had held together, is also why it split into east and west.",
      "success_criterion": [
        {
          "id": "held",
          "text": "Roads, water, and concrete held a large empire together.",
          "weight": 50
        },
        {
          "id": "size",
          "text": "That same size is why the empire split into east and west.",
          "weight": 50
        }
      ],
      "requires_teach_back": false,
      "beats": [
        {
          "role": "try",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "What did the empire's size do at the end?",
          "rubric": [
            {
              "id": "choice",
              "text": "Selects the choice that matches this quest.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "smaller",
              "trap": "The empire split because it had become a single city again.",
              "note": "It split because it was too large to govern as one."
            }
          ],
          "hint_ladder": {
            "nudge": "Can one government stay close to every far edge?",
            "analogy": "A table so long that the two ends stop hearing each other.",
            "scaffold": "The size made the empire ____."
          },
          "widget": {
            "type": "single",
            "prompt": "What did the empire's size do at the end?",
            "choices": [
              {
                "id": "split",
                "text": "It became too large for one government, so it split into east and west.",
                "misconception": ""
              },
              {
                "id": "vanish",
                "text": "The roads disappeared and the land shrank to one hill.",
                "misconception": "The works had held it. The size then pulled it apart."
              },
              {
                "id": "vote",
                "text": "It split because the consuls vetoed each other in 494 BCE.",
                "misconception": "That is the republic, not the later split of the empire."
              }
            ],
            "answer": "split",
            "explain": false,
            "misconception": "The late empire split because one government could not hold the whole size."
          }
        },
        {
          "role": "name",
          "bloom_level": "understand",
          "cognitive_load": "medium",
          "prompt": "Connect the earlier works to the split: the same reach that carried water and roads made one capital too far from the other edge.",
          "rubric": [
            {
              "id": "link",
              "text": "Connects the try to the learning goal.",
              "weight": 100
            }
          ],
          "misconception_map": [
            {
              "id": "concrete-failed",
              "trap": "Concrete suddenly stopped working and that alone split the map.",
              "note": "The political split follows the size, not a single broken wall."
            }
          ],
          "hint_ladder": {
            "nudge": "What had the roads been holding?",
            "analogy": "A long bridge that finally needs two keepers.",
            "scaffold": "The works held ____. The size then ____."
          },
          "widget": null
        },
        {
          "role": "show",
          "bloom_level": "evaluate",
          "cognitive_load": "medium",
          "prompt": "Explain how roads, water, and concrete held a large empire, and how that same size split it.",
          "rubric": [
            {
              "id": "held",
              "text": "Roads, water, and concrete held a large empire together.",
              "weight": 50
            },
            {
              "id": "size",
              "text": "That same size is why the empire split into east and west.",
              "weight": 50
            }
          ],
          "misconception_map": [
            {
              "id": "wolf",
              "trap": "The wolf myth explains the split.",
              "note": "The split is about size and government, not the founding story."
            }
          ],
          "hint_ladder": {
            "nudge": "First the holding together, then the split.",
            "analogy": "One map, two jobs for the distance.",
            "scaffold": "The works held it by ____. It split because ____."
          },
          "widget": null
        }
      ],
      "goals": [
        {
          "position": 1,
          "learning_goal": "The empire's size, which roads and water had held together, is also why it split into east and west.",
          "success_criterion": "Roads, water, and concrete held a large empire together."
        },
        {
          "position": 2,
          "learning_goal": "That same size is why the empire split into east and west.",
          "success_criterion": "That same size is why the empire split into east and west."
        }
      ],
      "close": {
        "kind": "none",
        "question": "",
        "items": []
      },
      "position": 16
    }
  ]
}
```

# AI Tutor MVP

A quest tutor for one learner at a time. Next.js hosts the kid session, the course desk, and the streaming chat. FastAPI is the system of record for students, the four-tier syllabus, sessions, and transcripts. Postgres stores them. A browser refresh is not enough after this change: the API must be migrated and the database re-seeded.

There is no login. The kid page is a name picker. Admin is a separate URL.

## Layout

- `apps/web` — Next.js App Router. `/` is the kid session. `/admin` is the course tree. `/viewchats` reads transcripts. `POST /api/chat` streams the tutor with the Vercel AI SDK. Each turn asks FastAPI for the seven-layer prompt bundle and uses that system prompt, schema, and temperature.
- `apps/api` — FastAPI, SQLAlchemy, Alembic. The only writer to Postgres.
- `docker-compose.yml` — local Postgres.

The model is OpenAI through `@ai-sdk/openai`. The chat route reads `OPENAI_API_KEY` and returns a clear error when it is missing. Do not invent a key. The model id lives in `apps/web/lib/model.ts` and defaults to `gpt-4o-mini`. Set `OPENAI_MODEL` to override it. That uses the same key.

## Prerequisites

- Node.js 22+
- Python 3.12
- Docker, for Postgres

## Setup

From the repo root:

```bash
docker compose up -d
python3 -m venv apps/api/.venv
source apps/api/.venv/bin/activate
pip install -r apps/api/requirements.txt
cp .env.example .env
cp .env.example apps/web/.env.local
```

Put your real key in both copies:

```bash
OPENAI_API_KEY=sk-...
```

Leave it empty if you only want to boot the screens. Chat will fail with the missing-key message until you set it and restart Next.js.

`OPENAI_MODEL` is optional. When it is unset, the chat route uses `gpt-4o-mini`.

## Run

Terminal 1, API:

```bash
source apps/api/.venv/bin/activate
cd apps/api
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

`alembic upgrade head` and `python -m app.seed` are required. A local refresh of the Next.js page is not enough: revision `005_syllabus_quests` drops the old lesson tables, retargets sessions at a quest, and clears old test transcripts. Run both commands again after pulling this change.

The seed inserts Iron Man, Storm, Spider-Man, and Wolverine when they are missing, and fills an age or tutor settings only when the tutor persona is blank. It inserts three courses when their codes are missing and leaves an existing course code as edited: Ancient Rome (ages 9–11), Euclidean and coordinate geometry (ages 12–14), and AP Macroeconomics (ages 15–17). A second run does not rewrite those courses.

Terminal 2, web:

```bash
npm install
npm run dev --workspace web
```

- Kid session: http://localhost:3000
- Lesson desk: http://localhost:3000/admin
- Transcripts: http://localhost:3000/viewchats
- API docs: http://localhost:8000/docs

## Try a quest

1. Open `/` and choose Storm. On the right, open a class notebook or press + for a new class. The course list is filtered to Storm's age band (9–11), so Ancient Rome is offered and AP Macroeconomics is not. Wolverine (15–17) sees Macroeconomics and not Rome. Pick a course, then a quest. Prerequisite codes are shown and do not lock the quest.
2. Inside a class, the stepper shows the four beats: mystery hook, interactive toy, diagnostic gate, and Feynman flip. A choice widget sits under the tutor prompt when the beat has one. A wrong tap stores that choice's misconception before the model replies. The model writes the reply and grades a written explanation. It does not grade the taps.
3. Open `/viewchats`, filter to Storm, and open the class. The transcript and beat scores are the rows FastAPI stored. The prompt button on a turn opens the system prompt and the messages that turn sent to the model. `/admin` is the course tree and does not list transcripts.
4. On `/admin`, expand a course to its units and quests. Open a quest to edit the four beats, rubric, hints, and widget. Import and export move one Tier 1 course, including units, quests, and beats. Uploading a file replaces that course code. An invalid file is rejected with the field that failed.

Add child has a Student group and a Tutor agent settings group. Both start from the age band and can be changed before save. The chat route asks FastAPI for the prompt bundle on every turn, then asks the model for a turn score: rubric rows met, a misconception if any, the hint tier, and the tutor reply. Choice widgets are graded by FastAPI first. A beat does not advance until it has a passing result.

## Render

Not deployed from this repo. A later deploy would be three Render resources you create by hand: a web service for `apps/web`, a web service for `apps/api`, and a managed Postgres database. Set `OPENAI_API_KEY`, `API_URL`, and `NEXT_PUBLIC_API_URL` on the Next service. Set `DATABASE_URL` (`postgresql+psycopg://...`) on the API, and run `alembic upgrade head` plus `python -m app.seed` before it serves traffic.

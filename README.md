# AI Tutor MVP

A fractions tutor for one learner at a time. Next.js hosts the kid session, the lesson desk, and the streaming chat. FastAPI is the system of record for students, lesson plans, sessions, and transcripts. Postgres stores them.

There is no login. The kid page is a name picker. Admin is a separate URL.

## Layout

- `apps/web` — Next.js App Router. `/` is the kid session. `/admin` is the lesson desk. `POST /api/chat` streams the tutor with the Vercel AI SDK.
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

`alembic upgrade head` and `python -m app.seed` are safe to run again. The seed inserts Iron Man, Storm, Spider-Man, Wolverine, and the Fractions, Reading, and Science lessons only when those rows are missing. It does not overwrite edits you made in admin.

Terminal 2, web:

```bash
npm install
npm run dev --workspace web
```

- Kid session: http://localhost:3000
- Lesson desk: http://localhost:3000/admin
- API docs: http://localhost:8000/docs

## Try the lesson

1. Open `/` and choose Storm. On the right, open a class notebook or press + for a new class and pick Fractions, Reading, or Science. The tutor greets Storm and starts the first checkpoint of that lesson. On Fractions that is a teach step about a pizza cut into 4 slices. It should not dump the rest of the lesson. The lesson desk on the left shows the score so far at the top and the lesson goals at the bottom.
2. Answer the teach check, then the chocolate-bar practice, then the granola-bar quiz. Quiz scores show in the chat and in the lesson-desk score.
3. Open `/admin`, filter sessions to Storm, and open the session. The transcript and checkpoint scores are the rows FastAPI stored.
4. Edit that checkpoint's tutor prompt and save. Start a new session from the kid page. The next turn uses the new prompt.

Server tools, called from the Next.js route and stored by FastAPI:

- `get_current_step` — read the current checkpoint so the model cannot invent the syllabus
- `record_checkpoint_result` — score, feedback, and pass/fail for the current step
- `advance_checkpoint` — move on after a finished teach step, or after a passing practice or quiz. A quiz without a passing score cannot be skipped.

## Render

Not deployed from this repo. A later deploy would be three Render resources you create by hand: a web service for `apps/web`, a web service for `apps/api`, and a managed Postgres database. Set `OPENAI_API_KEY`, `API_URL`, and `NEXT_PUBLIC_API_URL` on the Next service. Set `DATABASE_URL` (`postgresql+psycopg://...`) on the API, and run `alembic upgrade head` plus `python -m app.seed` before it serves traffic.

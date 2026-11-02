# AI Tutor MVP

A fractions tutor for one learner at a time. Next.js hosts the kid session, the lesson desk, and the streaming chat. FastAPI is the system of record for students, lesson plans, sessions, and transcripts. Postgres stores them.

There is no login. The kid page is a name picker. Admin is a separate URL.

## Layout

- `apps/web` — Next.js App Router. `/` is the kid session. `/admin` edits lesson blocks. `/viewchats` reads transcripts. `POST /api/chat` streams the tutor with the Vercel AI SDK.
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

`alembic upgrade head` and `python -m app.seed` are safe to run again. The seed inserts Iron Man, Storm, Spider-Man, and Wolverine when they are missing, and fills an age only when it is blank. Lessons are Fractions, Reading, Science, Super prompts (ages 9–11), and Function shifts (ages 15–17). A new slug is inserted once. Fractions is rewritten into blocks only when no class uses it. Other existing plans are left as edited, aside from a blank age range.

Terminal 2, web:

```bash
npm install
npm run dev --workspace web
```

- Kid session: http://localhost:3000
- Lesson desk: http://localhost:3000/admin
- Transcripts: http://localhost:3000/viewchats
- API docs: http://localhost:8000/docs

## Try the lesson

1. Open `/` and choose Storm. On the right, open a class notebook or press + for a new class. Storm can start Fractions, Reading, Science, or Super prompts. Function shifts stays off that shelf because it is for ages 15–17. Wolverine can start Function shifts.
2. Inside a class, the block stepper shows the path. A choice widget sits under the tutor prompt. The rubric strip and the hint badge (nudge, analogy, or scaffold) sit above the composer. A wrong tap stores that choice's misconception before the model replies. The model writes the reply and grades a written explanation. It does not grade the taps.
3. Open `/viewchats`, filter to Storm, and open the class. The transcript and checkpoint scores are the rows FastAPI stored. `/admin` edits blocks and does not list transcripts.
4. Edit a block's objective, rubric rows, hint ladder, or widget and save. Start a new class from the kid page. The next turn uses the saved block.

The chat route asks the model for a turn score: rubric rows met, a misconception if any, the hint tier, and the tutor reply. Choice widgets are graded by FastAPI first. A scored block does not advance until it has a passing result.

## Render

Not deployed from this repo. A later deploy would be three Render resources you create by hand: a web service for `apps/web`, a web service for `apps/api`, and a managed Postgres database. Set `OPENAI_API_KEY`, `API_URL`, and `NEXT_PUBLIC_API_URL` on the Next service. Set `DATABASE_URL` (`postgresql+psycopg://...`) on the API, and run `alembic upgrade head` plus `python -m app.seed` before it serves traffic.

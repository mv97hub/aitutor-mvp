# AI Tutor MVP

A quest tutor for one learner at a time. Next.js hosts the kid session, the course desk, and the streaming chat. FastAPI is the system of record for students, the four-tier syllabus, sessions, and transcripts. Postgres stores them. A browser refresh is not enough after this change: the API must be migrated and the database re-seeded.

There is no login. The kid page is a name picker. Admin is a separate URL.

## Layout

- `apps/web` — Next.js App Router. `/` is the kid session. `/admin` is the course tree. `/viewchats` reads transcripts. `POST /api/chat` streams the tutor with the Vercel AI SDK. Each turn asks FastAPI for the seven-layer prompt bundle and uses that system prompt, schema, and temperature.
- `apps/api` — FastAPI, SQLAlchemy, Alembic. The only writer to Postgres.
- `docker-compose.yml` — local Postgres.

The model is OpenAI through `@ai-sdk/openai`. The chat route reads `OPENAI_API_KEY` and returns a clear error when it is missing. Do not invent a key. The model id lives in `apps/web/lib/model.ts` and defaults to `gpt-4o-mini`. Set `OPENAI_MODEL` to override it. That uses the same key.

## Syllabus

A course holds units, and a unit holds quests. A quest is one learning goal (one sentence the student could say back) plus a success criterion: two or three rubric rows that sum to 100. The path is a short ordered cycle of moves, only the ones that quest needs:

- **Engage.** Teach the idea in a few sentences the student could retell, then ask one question. No choice box.
- **Try.** One widget (`single`, `multi`, `flaw`, or `order`) or one short attempt. The choice box waits until the tutor has spoken for this move.
- **Name.** The tutor teaches the idea in plain language, then asks one question. This is not a separate graded task.
- **Show.** The student produces the evidence after the tutor has spoken for this move. Show holds the success criterion.
- **Teach-back.** Only when the quest is flagged “must explain.” The student corrects a sidekick.

The quest advances when the criterion is met on Try or Show. Later moves, including teach-back, are then skipped. It also advances when the struggle window ends and the tutor explains why the worked answer fits the criterion. The pass score stays 70. The opening reply states the goal, what finished work looks like, and a short teaching of the first idea. It does not ask the student to pick an answer, and it does not preview later answers. Kid chat stays on `/` and does not show move boxes. Age bands stay on the course. The kid course dropdown is not filtered by age. Prerequisite codes are shown and do not lock a quest.

## Prompt engine

Each turn, FastAPI builds one system prompt from seven layers (`apps/api/app/engine/assemble.py`). The loader (`apps/api/app/prompt_loader.py`) fills those layers from the current move, the student, and the tutor settings. The chat route uses that prompt, the response schema, and the temperature.

1. **Active move.** Course, unit, quest, learning goal, success criterion, and the current move: task, rubric, misconception traps, the live hint rung, and the widget when this move has one. The correct widget answer stays out of the prompt until the struggle window opens. The model stays on this move, marks the criterion, and advances when the move is done.
2. **Student.** Name, age band, reading level, modality, interests, the live attempt count on this move, and the zone of proximal development.
3. **Tutor agent.** Persona, lexicon, metaphor dictionary, and the teach-back sidekick.
4. **Discourse.** Socratic strictness, the productive-struggle window, the anti-spoiler ban, and pacing. Teach, then ask: one question per turn, and it comes last. On Engage and Name the reply is a few sentences the student could retell, with a picture from their interests, then the question. After a miss, the reply explains what they tried, what the idea is, and the next step, without saying hint and without the worked answer. After the window, the tutor explains why the worked answer fits the criterion and the move can end. On Show, that explanation finishes the quest. Interests, reading level, persona, and metaphors are used inside the explanation. They are not announced as labels.
5. **Affect.** Growth-mindset praise only. Praise the strategy, the effort, or the revision.
6. **Metacognition.** One self-explanation line. Not a second explanation in the same turn.
7. **Memory.** No live spaced-repetition drill, review card, or future practice set.

The model returns the student-facing reply plus a turn score: rubric rows met, a misconception if any, the hint tier, and whether to advance. FastAPI grades widget taps itself. The model does not grade those taps.

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

`alembic upgrade head` and `python -m app.seed` are required. A local refresh of the Next.js page is not enough: revision `006_quest_cycle` adds the learning goal, the success criterion, and the move roles, clears old class transcripts, and drops the old four-beat rows. Revision `007_tutor_profile` adds one tutor profile row and does not clear classes. Revision `008_stay_on_course` adds one boolean column, `stay_on_course`, default on. It does not clear classes, chats, or the profile row. Run `alembic upgrade head` after pulling this change. Re-seed only to refresh quest text on Rome, Geometry, and AP Macro. That update is in place and does not delete sessions or messages. Do not re-seed in order to add the course switch.

The seed inserts Iron Man, Storm, Spider-Man, and Wolverine when they are missing, and fills an age or tutor settings only when the tutor persona is blank. It updates Ancient Rome (ages 9–11), Euclidean and coordinate geometry (ages 12–14), and AP Macroeconomics (ages 15–17) in place and does not delete sessions or messages. Any other course code is left as edited.

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

1. Open `/` and choose Storm. On the right, open a class notebook or press + for a new class. Every course is in the dropdown for every age, so Storm can start Ancient Rome, Euclidean geometry, or AP Macroeconomics. The course still stores its age band. Pick a course, then a quest. Prerequisite codes are shown and do not lock the quest. On a narrow screen, the class list sits behind a Classes pulldown.
2. Inside a class, the chat and the composer fill the page. Move boxes and the score strip are not shown. A choice widget is one message in the chat. It shows up late: after the student has explained the idea in their own words, or as one structured try before the answer when they are stuck. It is not on the first tutor message, and it is not there just because the move is Try. After they submit, that message shows their choice and later talk continues past it. A later check is a new message. Engage, Name, and the opening lesson are chat only. A wrong tap stores that choice's misconception before the model replies. The model writes the reply and grades a written explanation. It does not grade the taps. The opening reply states the learning goal, what finished work looks like, and a short teaching of the first idea. It does not ask the student to pick an answer. One question per turn stays, and it comes last. When the student misses, the reply explains what they tried, what the idea is, and the next step, without saying hint. The correct widget answer stays out of the prompt until the struggle window opens. After that window, the tutor explains why the worked answer fits the criterion and the move can end. If the success criterion is already met on Try or Show, later moves are skipped.
3. Open `/viewchats`, filter to Storm, and open the class. The transcript and beat scores are the rows FastAPI stored. The prompt button on a turn opens the system prompt and the messages that turn sent to the model. `/admin` is the course tree and does not list transcripts.
4. On `/admin`, expand a course to its units and quests. Open a quest to edit the learning goal, the success criterion, the standard code, the teach-back flag, and the ordered moves. Import and export move one Tier 1 course, including those fields. Uploading a file replaces that course code. An invalid file is rejected with the field that failed.

Add child asks for a name and an age. Reading level, modality, and interests are edited from Settings after the child is selected, and they save on that student. Persona, reading voice, metaphors, sidekick, the instructive slider, the struggle window, and the tutor switches are on `/admin/agent-customizations`. That page saves one profile and every student uses it. The chat route asks FastAPI for the seven-layer prompt on every turn, then asks the model for a turn score: rubric rows met, a misconception if any, the hint tier, and the tutor reply. Choice widgets are graded by FastAPI first. A move advances when the success criterion is met, or after the struggle window when the tutor states the worked answer and sets advance so the student is not stuck.

## Render

Not deployed from this repo. A later deploy would be three Render resources you create by hand: a web service for `apps/web`, a web service for `apps/api`, and a managed Postgres database. Set `OPENAI_API_KEY`, `API_URL`, and `NEXT_PUBLIC_API_URL` on the Next service. Set `DATABASE_URL` (`postgresql+psycopg://...`) on the API. A fresh database still needs `alembic upgrade head` and `python -m app.seed`. Agent customizations add revision `007_tutor_profile`. Revision `008_stay_on_course` adds the Stay on the course column and does not clear chats. Deploy the web service and the API, then run `alembic upgrade head`. A re-seed is not required for that column. The seed updates Ancient Rome, Euclidean and coordinate geometry, and AP Macroeconomics in place and does not delete sessions or messages. It does not overwrite a saved tutor profile.

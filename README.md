# AI Tutor MVP

A quest tutor for one learner at a time. Next.js hosts the kid session, the course desk, and the streaming chat. FastAPI is the system of record for students, courses, sessions, and transcripts. Postgres stores them. A browser refresh is not enough after this change: the API must be migrated. The seed inserts learners and the default tutor profile. It does not write courses.

There is no login. The kid page is a name picker. Admin is a separate URL.

## Layout

- `apps/web` — Next.js App Router. `/` is the kid session. `/admin` is the course tree. `/viewchats` reads transcripts. `POST /api/chat` streams the tutor with the Vercel AI SDK. Each turn asks FastAPI for the seven-layer prompt bundle and uses that system prompt, schema, and temperature.
- `apps/api` — FastAPI, SQLAlchemy, Alembic. The only writer to Postgres.
- `docker-compose.yml` — local Postgres.

The model is OpenAI through `@ai-sdk/openai`. The chat route reads `OPENAI_API_KEY` and returns a clear error when it is missing. Do not invent a key. The model id lives in `apps/web/lib/model.ts` and defaults to `gpt-4o-mini`. Set `OPENAI_MODEL` to override it. That uses the same key.

## Syllabus

A course holds preferences, quests, goals, and one close per quest. Preferences are the description, the audience, the quest count, the goals per quest, and the quiz minutes. Every goal is a row, including the first, and each goal has one success criterion. The close is an essay, a single choice, a multi-choice, or no questions.

The tutor walks the goals in order, then the close. A goal is met when its criterion is marked or the struggle window ends and the tutor explains why the worked answer fits that criterion. The choice card appears only on the close, and only after the tutor has spoken for it. An empty essay close ends the quest. The pass score stays 70. The opening reply states the first goal, what finished work looks like, and a short teaching of that idea. It does not ask the student to pick an answer, and it does not preview later answers. Kid chat stays on `/`. The kid course dropdown is not filtered by age.

## Prompt engine

Each turn, FastAPI builds one system prompt from seven layers (`apps/api/app/engine/assemble.py`). The loader (`apps/api/app/prompt_loader.py`) fills those layers from the current move, the student, and the tutor settings. The chat route uses that prompt, the response schema, and the temperature.

1. **Current step.** Course, quest, the current goal and its success criterion, or the close. The choice card is described only when the close is asking it. The correct choice stays out of the prompt until the struggle window opens. The model stays on this step, marks the criterion, and advances when the step is done.
2. **Student.** Name, age band, reading level, modality, interests, the live attempt count on this step, and the zone of proximal development.
3. **Tutor agent.** Persona, lexicon, metaphor dictionary, and the sidekick. These come from the one tutor profile.
4. **Discourse.** Socratic strictness, the productive-struggle window, the anti-spoiler ban, and pacing. Teach, then ask: one question per turn, and it comes last. On a goal the reply is a few sentences the student could retell, with a picture from their interests, then the question. After a miss, the reply explains what they tried, what the idea is, and the next step, without saying hint and without the worked answer. After the window, the tutor explains why the worked answer fits the criterion and the step can end. On the close, that explanation finishes the quest. Interests, reading level, persona, and metaphors are used inside the explanation. They are not announced as labels.
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

`alembic upgrade head` and `python -m app.seed` stay the API pre-deploy. A local refresh of the Next.js page is not enough. Revision `014_one_course_model` removes the three seeded courses (Ancient Rome, Euclidean geometry, and AP Macroeconomics), their quests, goals, closes, and the class transcripts that belonged only to those courses. Sessions and messages for any other course stay, and an in-progress class on a rewritten quest restarts at that quest's first goal. The Render API pre-deploy remains `alembic upgrade head && python -m app.seed`.

The seed inserts Iron Man, Storm, Spider-Man, and Wolverine when they are missing, and inserts the default tutor profile when it is missing. It fills a missing age, and fills reading level, modality, and interests when those are blank. It does not copy a tutor voice onto the student, and it does not write courses. A saved tutor profile is not overwritten.

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

1. Open `/` and choose Storm. On the right, open a class notebook or press + for a new class. Courses come from Create course, then Import course. The dropdown lists every imported course for every age. Pick a course, then a quest. On a narrow screen, the class list sits behind a Classes pulldown.
2. Inside a class, the chat and the composer fill the page. The tutor walks each goal, then the close. An essay close is typed. A single or multi-choice close is a card on the turn that asks the question, and that sentence is the question on the card. The text box locks only while the card is up. An empty close ends the quest. A wrong choice gets one explanation, then another try, or the worked answer when the struggle window ends. A wrong tap stores that choice's misconception before the model replies. The model writes the reply and grades a written explanation. It does not grade the taps. The opening reply states the first goal, what finished work looks like, and a short teaching of that idea. It does not ask the student to pick an answer. One question per turn stays, and it comes last. When the student misses, the reply explains what they tried, what the idea is, and the next step, without saying hint. The correct choice stays out of the prompt until the struggle window opens. After that window, the tutor explains why the worked answer fits the criterion and the step can end.
3. Open `/viewchats`, filter to Storm, and open the class. The transcript and the goal and close results are the rows FastAPI stored. The prompt button on a turn opens the system prompt and the messages that turn sent to the model. `/admin` is the course tree and does not list transcripts.
4. On `/admin`, the course page is view only. Preferences sit at the top: description, quest count, goals per quest, quiz minutes, and audience. The tree lists each quest, its goals and criteria, and its close. Changes happen in Create course, then Import course copies that draft into the kid catalog and leaves the original. Remove course takes a catalog course off the list and keeps its kid chat history.

Add child asks for a name and an age. Reading level, modality, and interests are edited from Settings after the child is selected, and they save on that student. Persona, reading voice, metaphors, sidekick, the instructive slider, the struggle window, and the tutor switches are on `/admin/agent-customizations`. That page saves one profile and every student uses it. The chat route asks FastAPI for the seven-layer prompt on every turn, then asks the model for a turn score: the criterion met, a misconception if any, the hint tier, and the tutor reply. Choice cards are graded by FastAPI first, and only on the close. A goal advances when its criterion is met, or after the struggle window when the tutor states the worked answer and sets advance so the student is not stuck. The close comes after the last goal.

## Render

Not deployed from this repo. A later deploy would be three Render resources you create by hand: a web service for `apps/web`, a web service for `apps/api`, and a managed Postgres database. Set `OPENAI_API_KEY`, `API_URL`, and `NEXT_PUBLIC_API_URL` on the Next service. Set `DATABASE_URL` (`postgresql+psycopg://...`) on the API. The API pre-deploy stays `alembic upgrade head && python -m app.seed`. That seed inserts the four learners and the default tutor profile. It does not write courses and it does not overwrite a saved tutor profile. Revision `014_one_course_model` removes the three seeded courses and the class transcripts that belonged only to them.

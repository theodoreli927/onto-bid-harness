# Bid Document Analysis Harness

A standalone agent harness that runs evidence-backed scope-gap analysis over
construction bid documents, with a repeatable evaluation system and a minimal
viewer for inspecting findings against the source PDF pages.

Built for the Royal Oak (0 Indian Pipes Road) bid package as a candidate
evaluation project for Ontos Tech.

## Architecture at a glance

- **API** (FastAPI) — project/document/task/result endpoints
- **Worker** — polls for queued tasks and executes them independently of the
  browser session
- **Skill** (`bidgaps`) — calls Gemini to analyze bid documents for scope gaps
  that could lead to change orders
- **Postgres** — persists projects, documents, tasks, results, and findings
- **Evaluation runner** — reruns the skill against fixed test cases and
  produces a scored report
- **Viewer** — a minimal static HTML page for inspecting findings with
  highlighted evidence on the actual PDF page

See `ARCHITECTURE.md` for the full design writeup, tradeoffs, and limitations.

## Prerequisites

- Docker Desktop (or another Docker runtime) running locally
- A Google AI Studio API key ([aistudio.google.com](https://aistudio.google.com))
  — free tier works, but is capped at 20 requests/day per model; see
  `ARCHITECTURE.md` for notes on this limitation

## Setup

1. Clone the repo and enter it:
```bash
   git clone <this-repo-url>
   cd onto-bid-harness
```

2. Copy the environment template and fill in your API key:
```bash
   cp .env.example .env
```
   Edit `.env` and set `GOOGLE_API_KEY` to your real key. `DATABASE_URL` can be
   left as-is for local development — it points at the Postgres container
   defined in `docker-compose.yml`.

3. Build and start everything:
```bash
   make build
   make up
```
   This starts Postgres, the API, and the worker, in that order. The API is
   available at `http://localhost:8000`.

4. Confirm it's running:
```bash
   make curl-health
```
   Should return `{"status":"ok"}`.

## Using the harness

### Create a project and upload documents

```bash
curl -s -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Royal Oak"}'
```

Copy the returned `id`, then upload a document:

```bash
curl -s -X POST http://localhost:8000/projects/<PROJECT_ID>/documents \
  -F "file=@data/construction_contract.pdf"
```

### Create an analysis task

```bash
curl -s -X POST http://localhost:8000/projects/<PROJECT_ID>/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Identify potential scope gaps that could lead to change orders.",
    "skill_name": "bidgaps",
    "document_ids": ["<DOCUMENT_ID>"]
  }'
```

Copy the returned task `id`. The worker picks up queued tasks automatically —
poll for status:

```bash
curl -s http://localhost:8000/projects/<PROJECT_ID>/tasks/<TASK_ID>
```

Status moves through `queued` → `running` → `completed` (or `failed`, with
automatic retries in between).

### View results

Via API:
```bash
curl -s http://localhost:8000/projects/<PROJECT_ID>/tasks/<TASK_ID>/result | python3 -m json.tool
```

Via the viewer (recommended — shows findings with the actual highlighted
evidence on the source page):

Open `http://localhost:8000/static/viewer.html`, enter the project ID and
task ID, and click **Load Result**.

## Running the evaluation suite

```bash
make eval
```

This reruns the `bidgaps` skill against a fixed set of test cases (defined in
`app/eval/cases.py`) with known expected findings, applies deterministic
integrity checks and keyword-based match scoring, and writes a report to
`eval_report.json`. See `ARCHITECTURE.md` for what the eval measures, how
cases were chosen, and where the method may be misleading.

## Common commands

Run `make help` for the full list. The ones you'll use most:

| Command | What it does |
|---|---|
| `make up` | Start everything |
| `make down` | Stop everything |
| `make restart-worker` | Restart the worker (needed after changing harness/skill code — it doesn't auto-reload) |
| `make logs-worker` | Watch the worker process a task live |
| `make psql` | Open a database shell |
| `make eval` | Run the evaluation suite |
| `make reset` | Full reset — wipes the database and rebuilds from scratch |


## Sample evaluation report

A sample run's output is committed at `eval_report.json` for reference. Rerun
`make eval` to regenerate it against your own environment/API key.

## AI tools used

This project was built with assistance from Claude (Anthropic) for
architecture planning, debugging, and code generation, used interactively
throughout development. All generated code was reviewed and tested against
real Royal Oak documents before being accepted; several rounds of live
debugging (Docker networking, SQLAlchemy enum casing, PDF extraction,
evidence-highlight coordinate math) were verified against actual running
output, not accepted on faith. Approximate time spent: TBD.

## Notes on confidentiality

- Uploaded documents are stored in a Docker-managed volume, never in the git
  working directory or committed history.
- `.env` (containing real credentials) is gitignored; `.env.example` contains
  placeholders only.
- Task error messages are truncated and never include raw document content.

## Known limitations

See `ARCHITECTURE.md` for the full list, including:
- Evaluation uses keyword-based matching rather than an LLM judge, to avoid
  evaluator circularity and API cost — this trades some recall on
  unanticipated phrasing for full determinism and repeatability.
- The Postgres `taskstatus` enum stores member names in uppercase
  (`COMPLETED`) rather than the lowercase `.value` used in the Python code
  and API responses — a cosmetic inconsistency visible only in raw SQL
  queries, not through the ORM or API.
- Document ID scoping on `Task` uses a JSON column rather than a normalized
  join table — a reasonable simplification for this scope, noted as an
  enterprise change.

## Live deployment

- **API base URL**: https://onto-bid-harness.onrender.com
- **Viewer**: https://onto-bid-harness.onrender.com/static/viewer.html
- **Health check**: https://onto-bid-harness.onrender.com/health

The GitHub repository contains the full source for review (architecture,
harness design, evaluation system). The Render deployment is a separate,
live instance of that same code — it lets a reviewer test the running
application directly (upload a document, run an analysis, inspect
findings) without needing to clone the repo, install Docker, or provide
their own API key.

To run a full analysis against the live deployment, use the same curl
commands from "Using the harness" above, substituting the live URL for
`http://localhost:8000`.

### Known limitation: viewer is read-only

The viewer displays completed task results with evidence highlighting,
but project creation, document upload, and task creation currently
require direct API calls (see curl examples above) rather than UI forms.
This was deprioritized under the three-day constraint in favor of a
working core pipeline and evaluation system. A production version would
add these as simple forms calling the same existing API endpoints — no
backend changes needed.

### Deployment-specific note: single-process worker

The Render deployment runs the task-execution worker loop as a background
`asyncio` task within the same process as the API (see `app/main.py`),
rather than as the separate `worker` service used in local development
(`docker-compose.yml`). This was a deliberate adaptation to Render's free
tier, which does not include a free Background Worker service alongside a
free Web Service. The task lifecycle logic itself (`app/harness/lifecycle.py`)
is unchanged — only how the polling loop is started differs. See
`ARCHITECTURE.md` for the full tradeoff discussion.
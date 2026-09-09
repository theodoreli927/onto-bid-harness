
There is no chat layer in this submission — Part 2 was deprioritized under
the three-day constraint (see Scope Management below).

## End-to-end flow: uploaded document to trusted result

1. `POST /projects/{id}/documents` — file is written to a Docker-managed
   volume (never the git working tree), then `docproc.extract_document`
   runs synchronously (via `asyncio.to_thread`, since PyMuPDF has no async
   API) to get `page_count`, which is stored on the `Document` row.
   Extracted text itself is **not** persisted — it's cheap and deterministic
   to re-extract, so storing it separately would only risk staleness
   without benefit.

2. `POST /projects/{id}/tasks` — validates that every `document_id` in the
   request actually belongs to the given project (TR-06), then creates a
   `Task` row with `status=QUEUED`.

3. The worker (`app/worker.py`) polls every 2 seconds using
   `SELECT ... FOR UPDATE SKIP LOCKED`, which lets multiple worker processes
   run safely without two of them claiming the same task — a real Postgres
   row-lock, not an application-level mutex.

4. `lifecycle.execute_task` re-extracts text for the task's documents,
   builds a `SkillContext`, and calls the registered skill
   (`SKILL_REGISTRY["bidgaps"]`).

5. The skill calls Gemini with the extracted page text and returns a list of
   candidate `SkillFinding` objects — each with a claimed `evidence_quote`,
   `document_id`, and `page_number`, but no bounding box.

6. The harness — **not the skill** — validates each candidate against the
   real page text using `docproc.find_evidence_bbox`. This function does an
   exact (post-normalization) sliding-window match of the quote against
   the page's extracted words. A match yields real pixel coordinates; no
   match sets `rejected=True` with a `rejection_reason`, and the finding is
   still persisted (for auditability) but is excluded from every API
   response and the viewer (TR-04).

7. `Task.status` becomes `COMPLETED`, and `GET /tasks/{id}/result` returns
   only unrejected findings, each carrying a `highlight_bbox` that the
   viewer draws as an overlay on a server-rendered PNG of the cited page
   (`GET /documents/{id}/pages/{n}/image`, rendered on-demand from the
   PDF via PyMuPDF, never cached or pre-generated).

## Task persistence, lifecycle, and failure handling

- States: `QUEUED -> RUNNING -> COMPLETED | FAILED`, plus `QUEUED` again on
  a retryable failure.
- `execute_task` wraps the whole skill-call-and-validate sequence in a
  try/except. On exception, `retry_count` increments; if it's under
  `MAX_RETRIES` (2), the task goes back to `QUEUED` for the worker to pick
  up again; otherwise it's marked `FAILED` with a truncated
  `error_message` (capped at 500 chars, and never includes raw document
  text — only the exception message).
- This was exercised for real during development: a transient Gemini `503`
  caused one retry, and the task completed successfully on the second
  attempt. A separate, non-transient case — a Gemini `429` daily quota
  exhaustion — correctly exhausted retries and surfaced a `FAILED` status
  with a clear error message, since retrying doesn't help when the
  problem is a quota reset, not a hiccup.

## What the evaluation measures, how cases were chosen, and where it may mislead

The eval system (`app/eval/`) reruns the real `bidgaps` skill (not a mock)
against fixed PDF inputs with hand-authored expected findings, and produces
a JSON report with per-case and aggregate results.

**Two layers of checking, matching the requirement's own split:**

1. **Deterministic checks** (`app/eval/checks.py`) — verify every
   non-rejected finding has all required text fields, a confidence in
   [0,1], a valid document/page reference, and a well-formed
   `highlight_bbox`. These are exact and require no judgment call.

2. **Match scoring** (`app/eval/judge.py`) — for each expected finding
   (a list of required keywords + an expected page), checks whether any
   actual, non-rejected finding on that page contains all the keywords.
   This is a deterministic, zero-cost, fully repeatable check.

**How cases were chosen:** the two committed cases (`contract-001`,
`contract-addenda-001`) are built from scope gaps a human reviewer can
independently verify by reading the source PDFs: two explicit
non-inclusion clauses (surveys, screens), an excavation risk-shifting
clause, a proposal-date mismatch, and — in the multi-document case — the
allowance and soft-draw revisions that only become visible when the
contract is read alongside its addenda. That second case specifically
tests cross-document reasoning, which is otherwise unverified by the
single-document case.

**Where this may mislead:**

- **Keyword matching over semantic matching.** During development, the
  model surfaced the same real issue with meaningfully different wording
  across separate runs (e.g. "Exclusion of Site Surveys and Footer
  Pinning" vs. "Survey and Footer Pinning Scope Exclusion" vs. "Exclusion
  of Surveying and Footer Pinning Work"). Keyword matching handles this
  as long as the chosen keywords are present, but it can produce a false
  "missed" result if a future version phrases the same real issue without
  any of the anticipated keywords. An LLM-as-judge approach was
  prototyped and worked correctly in one live test, but was dropped in
  favor of keyword matching for two reasons: it doubles API calls per eval
  case against a very constrained free-tier daily quota (20
  requests/day), and it introduces evaluator noise from using the same
  model family to both produce and grade findings — a form of circularity
  that would itself need separate documentation and validation to trust.
- **Small case count.** Two cases is enough to prove the mechanism works
  end-to-end and to catch a regression in the two specific behaviors
  tested, but it is not broad coverage. A production version would grow
  this to a dozen-plus cases covering different bid-package structures,
  not just Royal Oak's.
- **No adversarial/negative cases.** All current cases test whether real
  issues are found; none specifically test that the skill *doesn't*
  fabricate findings on a clean document. Given TR-05's prohibition on
  hardcoding, a document with no real scope gaps would be a valuable
  addition to catch false-positive drift.

## One code path, one failure case, and the most consequential tradeoff

**One code path worth understanding:** `docproc.find_evidence_bbox` is the
single function standing between "the LLM said something" and "the system
displays it as a trusted, cited finding." It does an exact, normalized
word-sequence match — not a fuzzy or semantic match — against the real
page text. If the LLM's `evidence_quote` doesn't appear verbatim (modulo
punctuation/case normalization), it returns `None`, and the harness
converts that into a permanent rejection. Every trust guarantee in this
system (TR-02, TR-03, TR-04) ultimately reduces to this one function
returning a real answer or `None`, with no in-between.

**One failure case worth understanding:** during development, a Google
Gemini free-tier daily quota (20 requests/day/model) was exhausted mid-eval
run. The skill call for one case failed all three retry attempts (mixed
`429` quota and `503` overload errors) and was correctly reported as a
failed case rather than silently producing zero findings — the eval
runner distinguishes "the skill genuinely found nothing" from "the skill
never got to run," which matters for trusting a report that shows zero
findings.

**The most consequential tradeoff:** using an LLM (Gemini) as the analysis
engine, rather than a rules/regex-based approach. This was close to
unavoidable given the requirement for genuine "risk explanation" and
"confidence level" outputs and the prohibition on hardcoding
project-specific logic (TR-05) — but it means the system inherits LLM
failure modes (rate limits, transient unavailability, occasional
inexact-quote hallucination) that a deterministic rules engine would not
have. The evidence-validation boundary (`find_evidence_bbox`) exists
specifically to contain the blast radius of this tradeoff: the LLM is
free to be wrong or imprecise about
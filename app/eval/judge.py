# app/eval/judge.py
import json
import os
from google import genai
from google.genai import types

from app.harness.models import Finding
from app.eval.cases import ExpectedFinding

JUDGE_MODEL = "gemini-3.6-flash"

JUDGE_PROMPT = """You are checking whether a set of ACTUAL findings from an automated \
review correctly covers a list of EXPECTED real issues in a document.

For each EXPECTED issue, determine if any ACTUAL finding substantively covers the same \
underlying issue (even if worded very differently). Respond with JSON only:

{{
  "matches": [
    {{"expected_index": 0, "matched": true, "matched_actual_title": "...", "reasoning": "..."}},
    ...
  ]
}}

EXPECTED ISSUES:
{expected_json}

ACTUAL FINDINGS:
{actual_json}
"""


def judge_matches(
    expected: list[ExpectedFinding], actual: list[Finding]
) -> list[dict]:
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    expected_json = json.dumps(
        [{"index": i, "description": e.description, "page": e.expected_page} for i, e in enumerate(expected)]
    )
    actual_json = json.dumps(
        [
            {"title": f.title, "risk_explanation": f.risk_explanation, "page": f.page_number}
            for f in actual
            if not f.rejected
        ]
    )

    response = client.models.generate_content(
        model=JUDGE_MODEL,
        contents=JUDGE_PROMPT.format(expected_json=expected_json, actual_json=actual_json),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    try:
        return json.loads(response.text)["matches"]
    except (json.JSONDecodeError, KeyError):
        return []
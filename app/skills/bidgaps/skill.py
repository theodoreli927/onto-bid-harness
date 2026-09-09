import json
import os
from google import genai
from google.genai import types

from app.skills.base import Skill, SkillContext, SkillResult, SkillFinding

SKILL_VERSION = "0.1.0"
MODEL_NAME = "gemini-3.6-flash"

PROMPT_TEMPLATE = """You are analyzing a construction bid package to find potential SCOPE GAPS \
that could lead to change orders — places where the contract, addenda, or plans are ambiguous, \
contradictory, missing coverage, or where scope described in one document isn't priced or \
covered in another.

Objective: {objective}

You will be given the text of one or more project documents, each broken into pages. \
For each potential scope gap you find, respond with a finding that includes:
- title: short name for the issue
- risk_explanation: why this could lead to a change order or cost dispute
- recommended_action: what the reviewer should do about it
- confidence: a number between 0.0 and 1.0
- document_id: the exact document_id this evidence comes from
- page_number: the exact page number (integer, 1-indexed) where the evidence appears
- evidence_quote: an EXACT, VERBATIM short quote (under 25 words) copied directly from that \
page's text — this will be used to locate a highlight on the page, so it must match the source \
text exactly, not a paraphrase

Only report findings you can support with a real, exact quote from the provided text. \
Do not invent or paraphrase evidence. If you cannot find a real supporting quote, do not report \
the finding at all.

Respond ONLY with a JSON array of findings, no other text. Example format:
[
  {{
    "title": "...",
    "risk_explanation": "...",
    "recommended_action": "...",
    "confidence": 0.8,
    "document_id": "...",
    "page_number": 1,
    "evidence_quote": "..."
  }}
]

DOCUMENTS:
{documents_text}
"""


def _build_documents_text(document_texts: dict[str, list[str]]) -> str:
    parts = []
    for doc_id, pages in document_texts.items():
        for page_num, text in enumerate(pages, start=1):
            parts.append(f"--- document_id: {doc_id} | page: {page_num} ---\n{text}\n")
    return "\n".join(parts)


class BidGapsSkill(Skill):
    name = "bidgaps"

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        self.client = genai.Client(api_key=api_key)

    async def execute(self, context: SkillContext) -> SkillResult:
        documents_text = _build_documents_text(context.document_texts)
        prompt = PROMPT_TEMPLATE.format(
            objective=context.objective,
            documents_text=documents_text,
        )
  
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text
        findings = self._parse_findings(raw_text)

        return SkillResult(
            skill_version=SKILL_VERSION,
            model_used=MODEL_NAME,
            findings=findings,
            raw_metadata={"raw_model_output": raw_text},
        )

    def _parse_findings(self, raw_text: str) -> list[SkillFinding]:
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            return []

        findings = []
        for item in data:
            try:
                findings.append(
                    SkillFinding(
                        title=item["title"],
                        risk_explanation=item["risk_explanation"],
                        recommended_action=item["recommended_action"],
                        confidence=float(item["confidence"]),
                        document_id=item["document_id"],
                        page_number=int(item["page_number"]),
                        evidence_quote=item["evidence_quote"],
                        highlight_bbox={},
                    )
                )
            except (KeyError, ValueError, TypeError):
                continue

        return findings

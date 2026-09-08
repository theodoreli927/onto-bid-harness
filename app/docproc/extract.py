# app/docproc/extract.py
import fitz  # PyMuPDF
from dataclasses import dataclass


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class PageContent:
    page_number: int  # 1-indexed, matches how humans refer to pages
    text: str
    words: list[Word]


@dataclass
class DocumentContent:
    page_count: int
    pages: list[PageContent]


def extract_document(file_path: str) -> DocumentContent:
    """
    Extract per-page text and word bounding boxes from a PDF.
    Runs synchronously (PyMuPDF has no async API) — call this via
    asyncio.to_thread() from async code so it doesn't block the event loop.
    """
    doc = fitz.open(file_path)
    pages: list[PageContent] = []

    for i, page in enumerate(doc):
        page_number = i + 1
        text = page.get_text()

        words_raw = page.get_text("words")  # list of (x0, y0, x1, y1, word, block_no, line_no, word_no)
        words = [
            Word(text=w[4], x0=w[0], y0=w[1], x1=w[2], y1=w[3])
            for w in words_raw
        ]

        pages.append(PageContent(page_number=page_number, text=text, words=words))

    doc.close()
    return DocumentContent(page_count=len(pages), pages=pages)


def find_evidence_bbox(page: PageContent, evidence_quote: str) -> dict[str, float] | None:
    """
    Given a page's extracted words and a quote an LLM claims as evidence,
    find the bounding box on that page. Returns None if no match is found —
    callers MUST treat None as "reject this finding" (TR-03/TR-04), never
    fabricate a fallback box.
    """
    quote_words = evidence_quote.strip().split()
    if not quote_words:
        return None

    page_words = [w.text for w in page.words]

    # naive sliding-window match on the word sequence — good enough as a first pass;
    # a fuzzier match (e.g. rapidfuzz) is a documented improvement for later
    n = len(quote_words)
    for start in range(len(page_words) - n + 1):
        window = page_words[start:start + n]
        if _normalize(window) == _normalize(quote_words):
            matched = page.words[start:start + n]
            return {
                "x0": min(w.x0 for w in matched),
                "y0": min(w.y0 for w in matched),
                "x1": max(w.x1 for w in matched),
                "y1": max(w.y1 for w in matched),
            }

    return None


def _normalize(words: list[str]) -> list[str]:
    return [w.strip(".,;:()\"'").lower() for w in words]
"""Pure, dependency-free grounding + citation helpers.

This centralises the citation / trust-note formatting that used to live inside
``src/graph/rag_graph.py`` so the *logic* is importable and unit-testable
WITHOUT langchain / langgraph / any vector backend (same offline-first pattern
as ``src/eval/gates.py``).

Two consumers share this module:

* the **RAG subgraph** (``rag_graph.py``) - already had a full
  ``verify_grounding`` node; it now imports these helpers instead of defining
  private copies, so there is exactly one source of truth.
* the **mentor tool-calling agent** (``src/graph/tools.py``) - previously had
  NO citations at all; it now reuses ``citations_from_tool_messages`` +
  ``format_sources`` to append deterministic "Sources used" notes to every
  answer that was grounded in a tool call.

Everything here is pure Python (only ``re``): no network, no LLM, no heavy
imports, so it runs in CI with no API keys.
"""
from __future__ import annotations

import re

# Keep at most this many citations on any answer, so long tool runs do not
# produce an unreadable wall of sources.
MAX_CITATIONS = 5

# "(Source: https://...)" markers emitted by the web-search digest
# (_fetch_search_context / _duckduckgo_search in src/agents/mentor/graph.py).
_SOURCE_URL_RE = re.compile(r"\(Source:\s*(.*?)\)")


def source_label(chunk: dict) -> str:
    """Format one retrieved chunk as a user-facing citation label.

    Reads only metadata that actually exists on the chunk; never invents a
    title, page, or score.
    """
    metadata = (chunk.get("metadata") or {}) if isinstance(chunk, dict) else {}
    source_type = metadata.get("source_type") or "retrieved context"
    title = (
        metadata.get("source_title")
        or metadata.get("filename")
        or metadata.get("chapter")
        or "source"
    )
    chunk_index = metadata.get("chunk_index")
    score = chunk.get("score") if isinstance(chunk, dict) else None
    parts = [str(title)]
    if source_type:
        parts.append(f"type={source_type}")
    if chunk_index is not None:
        parts.append(f"chunk={chunk_index}")
    if score is not None:
        parts.append(f"score={score}")
    return " \u2014 ".join(parts)


def format_sources(citations, *, max_items: int = MAX_CITATIONS) -> str:
    """Create compact, user-facing source notes without inventing metadata.

    Accepts a mixed list of chunk dicts (from retrieval) and/or plain string
    labels (e.g. web/tool citations). Returns "" when there is nothing to cite.
    """
    cleaned = [c for c in (citations or []) if c]
    if not cleaned:
        return ""
    lines = ["\n\nSources used:"]
    for i, citation in enumerate(cleaned[:max_items], start=1):
        label = source_label(citation) if isinstance(citation, dict) else str(citation)
        lines.append(f"- {i}. {label}")
    return "\n".join(lines)


def format_trust_note(confidence: str, unsupported_claims) -> str:
    """Append a short reliability note only when the answer needs caution."""
    claims = list(unsupported_claims or [])
    if confidence == "high" and not claims:
        return ""
    note = f"\n\nReliability note: grounding confidence is {confidence}."
    if claims:
        note += " Potentially unsupported claim(s): " + "; ".join(claims[:3])
    return note


def derive_confidence(*, grounded: bool, relevant: bool, has_evidence: bool) -> str:
    """Heuristic pre-LLM confidence used before (or instead of) an LLM verifier.

    * no evidence at all              -> low
    * grounded retrieval + relevant   -> high
    * anything else (partial support) -> medium
    """
    if not has_evidence:
        return "low"
    if grounded and relevant:
        return "high"
    return "medium"


def _is_fence_or_guard(line: str) -> bool:
    """True for prompt-safety scaffolding lines that are NOT real content.

    ``harden_untrusted`` wraps untrusted text in ``<<<...>>>`` fence markers and
    a leading ``[UNTRUSTED ...]`` guard line. When we later mine a (hardened)
    tool result for citations we must skip that scaffolding, otherwise the guard
    banner would be mis-read as a source.
    """
    s = line.strip()
    if not s:
        return True
    if s.startswith("<<<") and s.endswith(">>>"):
        return True
    if s.startswith("[UNTRUSTED"):
        return True
    return False


def extract_web_citations(text: str, *, max_items: int = MAX_CITATIONS) -> list:
    """Pull "(Source: URL)" markers out of a web-search digest into labels.

    De-duplicates while preserving order and caps the count.
    """
    if not text:
        return []
    seen = set()
    out = []
    for match in _SOURCE_URL_RE.finditer(text):
        url = match.group(1).strip()
        if url and url not in seen:
            seen.add(url)
            out.append(f"web \u2014 {url}")
        if len(out) >= max_items:
            break
    return out


def citations_from_tool_messages(messages, *, max_items: int = MAX_CITATIONS) -> list:
    """Duck-typed scan of tool messages for citeable sources (web + KB).

    Works on any object exposing ``.type`` / ``.name`` / ``.content`` (the shape
    of a LangChain ``ToolMessage``), so it stays offline-testable with light
    fakes and never imports langchain.
    """
    out = []
    seen = set()
    for message in messages or []:
        if getattr(message, "type", "") != "tool":
            continue
        name = getattr(message, "name", "") or ""
        content = getattr(message, "content", "") or ""
        if not isinstance(content, str):
            content = str(content)
        if name == "web_search":
            for citation in extract_web_citations(content, max_items=max_items):
                if citation not in seen:
                    seen.add(citation)
                    out.append(citation)
        elif name == "knowledge_base_search":
            # knowledge_base_tool_fn prefixes passages with "[<source>] ".
            for line in content.splitlines():
                if _is_fence_or_guard(line):
                    continue
                stripped = line.strip()
                if stripped.startswith("[") and "]" in stripped:
                    src = stripped[1:stripped.index("]")].strip()
                    if src:
                        citation = f"knowledge base \u2014 {src}"
                        if citation not in seen:
                            seen.add(citation)
                            out.append(citation)
        if len(out) >= max_items:
            break
    return out[:max_items]


def compose_grounded_answer(
    answer,
    citations=None,
    *,
    confidence: str | None = None,
    unsupported_claims=None,
) -> str:
    """Single entry point: answer + "Sources used" + optional reliability note."""
    text = answer or ""
    text += format_sources(citations or [])
    if confidence is not None:
        text += format_trust_note(confidence, unsupported_claims or [])
    return text

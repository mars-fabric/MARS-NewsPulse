"""
Diff-based content patching service.

Instead of asking an LLM to regenerate an entire document, we ask it to return
a small JSON array of surgical find→replace edits.  This module:

  1. Builds a prompt that elicits structured JSON edits from the LLM.
  2. Parses and validates the JSON response (with lenient recovery).
  3. Applies each patch to the original content with fuzzy matching.
  4. Falls back to a full-document rewrite if patching fails.

Design principles
─────────────────
• Unchanged text is *never* re-generated — it stays byte-identical.
• Works at any document size (LLM output is proportional to the *edit*,
  not the document).
• Every public function is stateless and side-effect free.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class EditOperation:
    """A single find→replace edit returned by the LLM."""
    find: str
    replace: str


@dataclass
class PatchResult:
    """Outcome of applying edits to a document."""
    content: str
    applied: List[EditOperation] = field(default_factory=list)
    failed: List[EditOperation] = field(default_factory=list)
    method: str = "diff"  # "diff" | "fallback"


# ── Prompt construction ──────────────────────────────────────────────────────

DIFF_SYSTEM_PROMPT = """\
You are a precise document-editing assistant.

TASK: Given the user's full document and their edit request, produce a JSON
array of find-and-replace operations that, when applied sequentially to the
document, will satisfy the request.

RULES:
1. Return ONLY a valid JSON array — no markdown fences, no commentary.
2. Each element must be an object with exactly two keys:
   • "find"    — the EXACT substring to locate (copy-paste precision, including
                  whitespace and line breaks).
   • "replace" — the text that should replace it.
3. Use the MINIMUM number of edits. Do NOT touch text the user did not ask to
   change.
4. The "find" value MUST appear verbatim in the document. If you cannot locate
   an exact match, widen the "find" to include enough surrounding context to be
   unique.
5. For a deletion, set "replace" to "".
6. For an insertion, set "find" to the text immediately before the insertion
   point and set "replace" to that same text followed by the new content.

EXAMPLE response (two edits):
[
  {"find": "old paragraph text here", "replace": "new paragraph text here"},
  {"find": "## Section B\\n\\nOriginal intro.", "replace": "## Section B\\n\\nRevised intro."}
]
"""


def build_diff_prompt(content: str, user_request: str) -> str:
    """Return the user-role message for the diff-based refinement call."""
    return (
        f"--- DOCUMENT ---\n{content}\n\n"
        f"--- EDIT REQUEST ---\n{user_request}"
    )


FALLBACK_SYSTEM_PROMPT = """\
You are helping a researcher refine their work.

CRITICAL INSTRUCTIONS:
- You MUST return the COMPLETE document with the requested changes applied in-place.
- Do NOT return only the changed section or paragraph.
- Do NOT omit any part of the original content that was not requested to be removed.
- The output must be a full replacement of the entire document, preserving all \
unchanged sections exactly as they are while incorporating the requested edits.
"""


def build_fallback_prompt(content: str, user_request: str) -> str:
    """Prompt for the full-document fallback path."""
    return (
        f"--- CURRENT CONTENT (FULL DOCUMENT) ---\n{content}\n\n"
        f"--- USER REQUEST ---\n{user_request}\n\n"
        "Return the COMPLETE updated document with the changes applied. "
        "No explanations, no preamble, no commentary — just the full document."
    )


# ── JSON parsing (lenient) ───────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that LLMs sometimes add despite instructions."""
    text = text.strip()
    # Remove opening fence: ```json or ``` at start
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    # Remove closing fence: ``` at end
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def parse_edit_operations(raw_response: str) -> List[EditOperation]:
    """
    Parse the LLM's JSON response into a list of EditOperations.

    Handles common LLM quirks:
    - Markdown code fences around JSON
    - Trailing commas
    - Single-object responses (not wrapped in array)

    Raises ValueError if the response cannot be parsed at all.
    """
    cleaned = _strip_markdown_fences(raw_response)

    # Try parsing as-is first
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try fixing trailing commas:  ,] or ,}
        fixed = re.sub(r',\s*([}\]])', r'\1', cleaned)
        try:
            data = json.loads(fixed)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM response is not valid JSON after cleanup: {exc}\n"
                f"Raw (first 500 chars): {raw_response[:500]}"
            ) from exc

    # Normalise: single object → list
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    operations: List[EditOperation] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Edit #{i} is not an object: {type(item).__name__}")
        find_val = item.get("find")
        replace_val = item.get("replace")
        if find_val is None or replace_val is None:
            raise ValueError(
                f'Edit #{i} missing required key(s). '
                f'Keys present: {list(item.keys())}'
            )
        operations.append(EditOperation(find=str(find_val), replace=str(replace_val)))

    if not operations:
        raise ValueError("LLM returned an empty edit array")

    return operations


# ── Patch application ────────────────────────────────────────────────────────

def _normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces for fuzzy matching."""
    return re.sub(r'\s+', ' ', text).strip()


def _fuzzy_find(content: str, target: str) -> Optional[Tuple[int, int]]:
    """
    Locate *target* inside *content*.

    Strategy (ordered by precision):
      1. Exact substring match.
      2. Whitespace-normalised match — handles LLM adding/removing linebreaks.
      3. First-and-last-line anchor match — the LLM sometimes truncates the
         middle of long "find" blocks with "..." or similar.

    Returns (start, end) indices into *content*, or None.
    """
    # ── 1. Exact match ──
    idx = content.find(target)
    if idx != -1:
        return (idx, idx + len(target))

    # ── 2. Whitespace-normalised ──
    norm_target = _normalise_whitespace(target)
    # Build a regex that treats any whitespace run in target as \s+
    pattern_parts = [re.escape(tok) for tok in norm_target.split(' ') if tok]
    if pattern_parts:
        ws_pattern = re.compile(r'\s+'.join(pattern_parts), re.DOTALL)
        m = ws_pattern.search(content)
        if m:
            return (m.start(), m.end())

    # ── 3. First+last line anchor ──
    lines = [ln.strip() for ln in target.strip().splitlines() if ln.strip()]
    if len(lines) >= 2:
        first_esc = re.escape(lines[0])
        last_esc = re.escape(lines[-1])
        anchor_pat = re.compile(
            first_esc + r'.*?' + last_esc, re.DOTALL
        )
        m = anchor_pat.search(content)
        if m:
            return (m.start(), m.end())

    return None


def apply_patches(content: str, operations: List[EditOperation]) -> PatchResult:
    """
    Apply a list of find→replace operations to *content* sequentially.

    Each operation is attempted with fuzzy matching.  Successfully applied
    operations mutate the running content; failed ones are collected.
    """
    result = PatchResult(content=content, method="diff")

    for op in operations:
        span = _fuzzy_find(result.content, op.find)
        if span is not None:
            start, end = span
            result.content = result.content[:start] + op.replace + result.content[end:]
            result.applied.append(op)
        else:
            logger.warning(
                "diff_patch_miss find=%r (first 80 chars)",
                op.find[:80],
            )
            result.failed.append(op)

    return result


# ── Orchestrator (prompt → patch → fallback) ─────────────────────────────────

def refine_with_diff(
    content: str,
    user_request: str,
    *,
    llm_call,
    model: str = "gpt-4o",
    temperature: float = 0.4,
    fallback_temperature: float = 0.7,
) -> PatchResult:
    """
    End-to-end refinement using the diff-based approach with automatic fallback.

    Parameters
    ----------
    content : str
        The full original document.
    user_request : str
        The user's natural-language edit instruction.
    llm_call : callable
        A function with signature (messages, model, temperature, max_tokens) → str.
        Typically a thin wrapper around ``safe_completion``.
    model : str
        Model identifier for the LLM.
    temperature : float
        Temperature for the diff call (lower = more precise JSON).
    fallback_temperature : float
        Temperature for the full-document fallback.

    Returns
    -------
    PatchResult
        Always contains the final content.  ``method`` is "diff" if patching
        succeeded, "fallback" if we fell back to full-document regeneration.
    """
    # ── Phase 1: try diff-based patching ──
    try:
        diff_response = llm_call(
            messages=[
                {"role": "system", "content": DIFF_SYSTEM_PROMPT},
                {"role": "user", "content": build_diff_prompt(content, user_request)},
            ],
            model=model,
            temperature=temperature,
            max_tokens=4096,  # Diffs are small — 4K is plenty
        )

        operations = parse_edit_operations(diff_response)
        result = apply_patches(content, operations)

        # If every operation failed, the diff is useless — fall back.
        if result.applied and not result.failed:
            logger.info(
                "diff_patch_success edits_applied=%d", len(result.applied)
            )
            return result

        if result.applied and result.failed:
            # Partial success — still return the diff result but log a warning.
            # Some edits landed; better than a full rewrite that might hallucinate.
            logger.warning(
                "diff_patch_partial applied=%d failed=%d",
                len(result.applied), len(result.failed),
            )
            return result

        # All failed → fall through to fallback
        logger.warning("diff_patch_all_failed count=%d, falling back", len(result.failed))

    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("diff_parse_failed error=%s, falling back", exc)
    except Exception as exc:
        logger.error("diff_unexpected_error error=%s, falling back", exc)

    # ── Phase 2: full-document fallback ──
    estimated_tokens = len(content) // 3
    fallback_max_tokens = min(max(4096, int(estimated_tokens * 1.5)), 16384)

    try:
        fallback_response = llm_call(
            messages=[
                {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
                {"role": "user", "content": build_fallback_prompt(content, user_request)},
            ],
            model=model,
            temperature=fallback_temperature,
            max_tokens=fallback_max_tokens,
        )

        return PatchResult(
            content=fallback_response,
            method="fallback",
        )
    except Exception as exc:
        logger.error("diff_fallback_also_failed error=%s", exc)
        raise

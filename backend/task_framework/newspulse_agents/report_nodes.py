"""
LangGraph node functions for NewsPulse final report generation.

Each node makes a single, bounded LLM call to generate one report section.
This avoids the context-length explosion that occurs when using
planning_and_control_context_carryover for the full report.

Flow:
  preprocess → executive_summary → sentiment_dashboard → headlines
  → in_depth_analysis → company_analysis → trends_risks
  → regional_outlook → sources → assemble → pdf → END
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# Maximum characters of raw data to include per section prompt.
# This keeps each LLM call well within token limits.
_MAX_CONTEXT_CHARS = 80_000
_MAX_SUMMARY_CHARS = 50_000

# System-level instruction injected into every section prompt to prevent
# the LLM from refusing or hallucinating data.
_COMPILER_SYSTEM = (
    "You are a REPORT COMPILER. All the data you need is provided below — "
    "it was collected by earlier research stages via web search. Your job is "
    "to read this data and organise it into the requested format.\n\n"
    "Guidelines:\n"
    "- Always produce substantive content from the provided data.\n"
    "- Extract and organise company names, source URLs, themes, events, "
    "and quoted details from the material below.\n"
    "- When the data is limited, synthesize insights from whatever is "
    "available — a concise factual summary grounded in the source material "
    "is always valuable.\n"
    "- Every section should contain real information drawn from the data.\n\n"
    "Style rules:\n"
    "- Write in a professional analyst tone.\n"
    "- Do not wrap output in code fences (no triple backticks).\n"
    "- Include real URLs/links exactly as they appear in the data.\n"
    "- Use plain markdown."
)

# Phrases that indicate the upstream data is a refusal, not real research.
_REFUSAL_MARKERS = [
    "no verifiable",
    "no admissible",
    "cannot be compiled",
    "cannot be produced",
    "cannot be generated",
    "would require fabricat",
    "insufficient evidence",
    "no accessible, verifiably",
    "no structured news items",
    "no qualifying",
    "all candidate links",
    "could not be confirmed",
    "no empirically grounded",
    "zero finalized items",
    "no factual list",
]


def _is_refusal_text(text: str) -> bool:
    """Detect when an upstream stage produced a refusal instead of real data."""
    if not text or len(text.strip()) < 200:
        return True
    lower = text.lower()
    hits = sum(1 for marker in _REFUSAL_MARKERS if marker in lower)
    # Two or more refusal markers = refusal. One can appear in legit text.
    return hits >= 2


def _get_llm_client(state: Dict[str, Any]):
    """Create an OpenAI-compatible client from state config."""
    from cmbagent.llm_provider import create_openai_client, resolve_model_for_provider
    client = create_openai_client()
    model = resolve_model_for_provider(state.get("llm_model", "gpt-4o"))
    return client, model


_USE_MAX_COMPLETION_TOKENS = True  # default to newer param


def _call_llm(state: Dict[str, Any], prompt: str, max_tokens: int = 4096) -> str:
    """Make a single LLM call and return the response text.

    Handles both older models (max_tokens) and newer models
    (max_completion_tokens) automatically, with retry on mismatch.
    """
    global _USE_MAX_COMPLETION_TOKENS
    client, model = _get_llm_client(state)
    temperature = state.get("llm_temperature", 0.7)
    use_completion_tokens = _USE_MAX_COMPLETION_TOKENS

    for _attempt in range(2):
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if use_completion_tokens:
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens

        try:
            response = client.chat.completions.create(**kwargs)
            text = response.choices[0].message.content or ""
            return _strip_code_fences(text)
        except Exception as e:
            err_str = str(e)
            if "max_tokens" in err_str and "max_completion_tokens" in err_str:
                # Flip the flag and retry once
                use_completion_tokens = not use_completion_tokens
                _USE_MAX_COMPLETION_TOKENS = use_completion_tokens
                logger.info(
                    "Switching to %s for NewsPulse LLM calls",
                    "max_completion_tokens" if use_completion_tokens else "max_tokens",
                )
                continue
            raise

    raise RuntimeError("NewsPulse LLM call failed after token-param retry")


_SECTION_REFUSAL_MARKERS = [
    "cannot be compiled",
    "cannot compile",
    "cannot be produced",
    "cannot be generated",
    "no verifiable",
    "no admissible",
    "would require fabricat",
    "insufficient data",
    "no data available",
    "i cannot provide",
    "i cannot compile",
    "no information is available",
    "unable to compile",
    "unable to produce",
    "the data sections explicitly state",
]


def _section_is_refusal(text: str, min_chars: int = 150) -> bool:
    """True when the LLM produced a refusal/placeholder instead of real content."""
    if not text or len(text.strip()) < min_chars:
        return True
    lower = text.lower()
    return any(marker in lower for marker in _SECTION_REFUSAL_MARKERS)


def _call_llm_with_antirefusal(
    state: Dict[str, Any],
    prompt: str,
    max_tokens: int = 4096,
    retry_hint: str = "",
) -> str:
    """Call the LLM; if the output looks like a refusal, retry once with a harder prompt.

    This is the guard rail for Stage 4 section generation. Many older model
    behaviors produce 'cannot be compiled' output when temporal constraints
    feel strict. The retry strips the strict framing and orders the model to
    extract whatever it can.
    """
    first = _call_llm(state, prompt, max_tokens=max_tokens)
    if not _section_is_refusal(first):
        return first

    logger.warning(
        "section LLM output looks like a refusal (%d chars), retrying with anti-refusal prompt",
        len(first),
    )

    retry_prompt = (
        "Please produce the report section described below. Focus on "
        "extracting useful material from the provided data: source URLs, "
        "company names, event keywords, quoted sentences, and domain names. "
        "A concise factual summary grounded in the source material is "
        "always valuable.\n\n"
        f"{retry_hint}\n\n"
        "Here is the full prompt with data:\n\n"
        "---\n\n"
        + prompt
    )
    return _call_llm(state, retry_prompt, max_tokens=max_tokens)


def _strip_code_fences(text: str) -> str:
    """Remove wrapping ```markdown ... ``` or ``` ... ``` from LLM output."""
    import re
    stripped = text.strip()
    # Match ```markdown\n...\n``` or ```\n...\n```
    m = re.match(r'^```(?:markdown)?\s*\n(.*?)\n```\s*$', stripped, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _strip_heading(text: str, heading_text: str) -> str:
    """Remove a leading heading line that duplicates the section title.

    LLMs sometimes echo the section heading even when told not to.
    Handles: '### Heading', '## Heading', '**Heading**', 'Heading\n---', etc.
    """
    import re
    stripped = text.strip()
    escaped = re.escape(heading_text)
    # Build patterns — note: can't use f-string with {1,4} quantifier,
    # so we concatenate instead.
    patterns = [
        r'^#{1,4}\s*' + escaped + r'\s*\n+',          # ### Heading\n
        r'^\*{2}' + escaped + r'\*{2}\s*\n+',          # **Heading**\n
        r'^' + escaped + r'\s*\n[-=]+\s*\n*',           # Heading\n---\n (setext)
        r'^' + escaped + r'\s*\n+',                     # Heading\n (plain text)
    ]
    for pat in patterns:
        new = re.sub(pat, '', stripped, count=1, flags=re.IGNORECASE)
        if new != stripped:
            return new.strip()
    return stripped


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, appending an ellipsis notice."""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars] + "\n\n[... content truncated for brevity ...]"


# ═══════════════════════════════════════════════════════════════════════════
# Metadata extraction helpers
# ═══════════════════════════════════════════════════════════════════════════

def _extract_all_urls(*texts: str) -> List[str]:
    """Extract all unique, valid URLs from one or more text blocks."""
    url_pattern = re.compile(r'https?://[^\s\)\]\>\"\'\,]+')
    seen = set()
    urls = []
    for text in texts:
        if not text:
            continue
        for match in url_pattern.findall(text):
            # Strip trailing punctuation that's not part of the URL
            clean = match.rstrip('.,;:!?)>')
            if clean not in seen:
                seen.add(clean)
                urls.append(clean)
    return urls


def _extract_regional_context(news: str, analysis: str, region: str) -> str:
    """Pre-extract region-relevant paragraphs and data from source text.

    Scans both news_collection and deep_analysis for paragraphs that
    mention the region or known sub-regions, and consolidates them into
    a focused context block for the regional_outlook_node.
    """
    # Build keyword list for the region
    region_keywords = [region.lower()]
    _REGION_MAP = {
        "europe": ["uk", "united kingdom", "france", "germany", "eu", "european",
                    "netherlands", "spain", "italy", "sweden", "ireland", "paris",
                    "london", "berlin", "amsterdam", "brussels", "european union"],
        "north america": ["us", "usa", "united states", "canada", "mexico",
                          "silicon valley", "new york", "san francisco"],
        "asia": ["china", "japan", "india", "singapore", "hong kong", "korea",
                 "southeast asia", "asean", "tokyo", "shanghai", "mumbai"],
        "global": [],  # match everything
    }
    for key, subs in _REGION_MAP.items():
        if key in region.lower():
            region_keywords.extend(subs)
            break

    regional_paragraphs = []
    for text in [news, analysis]:
        if not text:
            continue
        paragraphs = re.split(r'\n{2,}', text)
        for para in paragraphs:
            para_lower = para.lower()
            if any(kw in para_lower for kw in region_keywords):
                stripped = para.strip()
                if len(stripped) > 40:  # skip trivial matches
                    regional_paragraphs.append(stripped)

    if not regional_paragraphs:
        return ""

    # Deduplicate and limit size
    seen = set()
    unique = []
    for p in regional_paragraphs:
        key = p[:100]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return "\n\n".join(unique[:30])  # cap at ~30 paragraphs


def _extract_outlook_context(analysis: str) -> str:
    """Pre-extract outlook/forecast/recommendation paragraphs from analysis text."""
    outlook_keywords = [
        "outlook", "forecast", "prediction", "recommendation",
        "forward", "upcoming", "next quarter", "next month",
        "short-term", "medium-term", "long-term", "watchpoint",
        "catalyst", "expected", "anticipate", "project",
        "strategic", "actionable", "should monitor", "key to watch",
    ]
    if not analysis:
        return ""

    paragraphs = re.split(r'\n{2,}', analysis)
    outlook_paragraphs = []
    for para in paragraphs:
        para_lower = para.lower()
        if any(kw in para_lower for kw in outlook_keywords):
            stripped = para.strip()
            if len(stripped) > 40:
                outlook_paragraphs.append(stripped)

    if not outlook_paragraphs:
        return ""

    seen = set()
    unique = []
    for p in outlook_paragraphs:
        key = p[:100]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return "\n\n".join(unique[:20])


# ═══════════════════════════════════════════════════════════════════════════
# Rescue seed — used when upstream research stages produced a refusal
# ═══════════════════════════════════════════════════════════════════════════

def _generate_rescue_seed(state: Dict[str, Any]) -> str:
    """Ask the model to produce an industry-knowledge seed when upstream fails.

    This guards against the old failure mode where strict date filtering at
    the researcher layer discarded every search result and produced an empty
    refusal document. Rather than surfacing that refusal to the user, we
    synthesize an industry-context document the section compilers can turn
    into a presentable (if less current) report.

    The output is clearly labelled as background/model-generated by the
    caller — the user sees the disclaimer in the final report.
    """
    industry = state.get("industry", "")
    companies = state.get("companies", "") or "industry leaders"
    region = state.get("region", "Global")
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    current_date = datetime.now().strftime("%B %d, %Y")

    prompt = f"""You are an industry research analyst. Today's date is {current_date}.

The automated web research pipeline returned thin results for this request, so
we need you to generate an industry context document from your general
knowledge. This document will be used as supplementary material in a report —
it will be clearly labelled as model-generated background, so your job is to
produce substantive, reasonable industry context as supplementary background.

Request:
- Industry: {industry}
- Companies of interest: {companies}
- Region: {region}
- Period: {tw_human}

Produce a markdown document covering:

## Industry Overview
2-3 paragraphs on the state of the {industry} sector in {region}. Mention
the main players, competitive dynamics, and structural forces shaping the
industry.

## Recent Themes and Developments
8-12 bulleted themes that characterize the industry. For each theme, name
specific companies, products, or events when possible. You may cite general
knowledge — do not fabricate specific dated announcements, but you may
describe ongoing trends.

## Company Profiles
For each of [{companies}] (or key industry leaders if none specified):
- Position in the industry
- Known strategic priorities
- Typical opportunities
- Typical risks

## Trends
5-6 forward-looking trends for the {industry} sector.

## Risks
5-6 key risks facing the {industry} sector.

## Regional Notes ({region})
2-3 paragraphs on how {region} fits into the global {industry} landscape,
including sub-region dynamics where relevant.

## Outlook Framing
Short-term (1-3 months) and medium-term (3-12 months) framing for the sector.

RULES:
- Always produce substantive content from your general knowledge.
- Do NOT invent specific press releases with fake dates or quotes.
- General industry knowledge is fine; specific event claims must be
  plausible but need not be verified.
- Output plain markdown, no code fences.
"""
    return _call_llm(state, prompt, max_tokens=3500)


# ═══════════════════════════════════════════════════════════════════════════
# Node: preprocess
# ═══════════════════════════════════════════════════════════════════════════

def preprocess_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Read input files and prepare bounded summaries for downstream nodes."""
    work_dir = state.get("work_dir", "")
    input_dir = os.path.join(work_dir, "input_files")

    # Read from files if state values are empty
    news_collection = state.get("news_collection", "")
    deep_analysis = state.get("deep_analysis", "")

    if not news_collection:
        nc_path = os.path.join(input_dir, "news_collection.md")
        if os.path.exists(nc_path):
            with open(nc_path, "r") as f:
                news_collection = f.read()

    if not deep_analysis:
        da_path = os.path.join(input_dir, "deep_analysis.md")
        if os.path.exists(da_path):
            with open(da_path, "r") as f:
                deep_analysis = f.read()

    # Create bounded summaries for per-section prompts
    news_summary = _truncate(news_collection, _MAX_SUMMARY_CHARS)
    analysis_summary = _truncate(deep_analysis, _MAX_SUMMARY_CHARS)

    time_window = state.get("time_window", "7d")
    tw_labels = {
        "1d": "the past 24 hours",
        "7d": "the past week",
        "14d": "the past two weeks",
        "30d": "the past month",
        "90d": "the past 3 months",
        "180d": "the past 6 months",
        "365d": "the past year",
        "2024": "the year 2024 (Jan–Dec 2024)",
        "2025": "the year 2025 (Jan–Dec 2025)",
        "2026": "the year 2026 (Jan–present 2026)",
        "2025-2026": "2025 through 2026",
        "Q1 2025": "Q1 2025 (Jan–Mar 2025)",
        "Q2 2025": "Q2 2025 (Apr–Jun 2025)",
        "Q3 2025": "Q3 2025 (Jul–Sep 2025)",
        "Q4 2025": "Q4 2025 (Oct–Dec 2025)",
        "Q1 2026": "Q1 2026 (Jan–Mar 2026)",
        "H1 2025": "first half of 2025 (Jan–Jun 2025)",
        "H2 2025": "second half of 2025 (Jul–Dec 2025)",
        "H1 2026": "first half of 2026 (Jan–Jun 2026)",
    }
    # For free-text inputs like "weeks", "3 months", etc. keep as-is
    # but prefix with "the past" if it's a bare word
    raw_tw = tw_labels.get(time_window)
    if not raw_tw:
        raw_tw = time_window
        if raw_tw and not raw_tw.startswith("the "):
            raw_tw = f"the past {raw_tw}"

    logger.info(
        "preprocess_node: news=%d chars, analysis=%d chars",
        len(news_collection), len(deep_analysis),
    )

    # ── Rescue path: when stages 2/3 produced refusal text, seed the
    # compiler with an industry-knowledge block so it has real material.
    news_is_refusal = _is_refusal_text(news_collection)
    analysis_is_refusal = _is_refusal_text(deep_analysis)

    if news_is_refusal or analysis_is_refusal:
        logger.warning(
            "preprocess_node: upstream stages produced refusal output "
            "(news_refusal=%s, analysis_refusal=%s) — generating "
            "knowledge-based rescue seed",
            news_is_refusal, analysis_is_refusal,
        )
        try:
            seed = _generate_rescue_seed(state)
            if news_is_refusal:
                news_collection = (
                    (news_collection or "") + "\n\n---\n\n"
                    "## Supplementary background context\n\n"
                    "(Upstream search produced thin output; the content "
                    "below is model-generated industry context to let the "
                    "compiler produce a non-empty report. Treat dates and "
                    "specific figures as indicative, not verified.)\n\n"
                    + seed
                )
            if analysis_is_refusal:
                deep_analysis = (
                    (deep_analysis or "") + "\n\n---\n\n"
                    "## Supplementary analyst context\n\n"
                    "(Upstream analysis produced thin output; the content "
                    "below is model-generated industry context.)\n\n"
                    + seed
                )
            # Refresh summaries with augmented data
            news_summary = _truncate(news_collection, _MAX_SUMMARY_CHARS)
            analysis_summary = _truncate(deep_analysis, _MAX_SUMMARY_CHARS)
        except Exception as e:
            logger.error("preprocess_node: rescue seed generation failed: %s", e)

    # Extract metadata for downstream nodes
    region = state.get("region", "Global")
    extracted_urls = _extract_all_urls(news_collection, deep_analysis)
    regional_context = _extract_regional_context(news_collection, deep_analysis, region)
    outlook_context = _extract_outlook_context(deep_analysis)

    logger.info(
        "preprocess_node: extracted %d URLs, %d chars regional context, %d chars outlook context",
        len(extracted_urls), len(regional_context), len(outlook_context),
    )

    return {
        "news_collection": news_collection,
        "deep_analysis": deep_analysis,
        "news_summary": news_summary,
        "analysis_summary": analysis_summary,
        "time_window_human": raw_tw,
        "extracted_urls": extracted_urls,
        "regional_context": regional_context,
        "outlook_context": outlook_context,
        "messages": [HumanMessage(content="Preprocessing complete.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Section node helpers
# ═══════════════════════════════════════════════════════════════════════════

def _section_context(state: Dict[str, Any]) -> str:
    """Build the common context header for section prompts."""
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    current_date = datetime.now().strftime("%B %d, %Y")
    return (
        f"Today's date: {current_date}\n"
        f"Industry: {state.get('industry', '')}\n"
        f"Companies: {state.get('companies', 'None specified')}\n"
        f"Region: {state.get('region', 'Global')}\n"
        f"Time Window: {tw_human}\n"
        f"\nFocus on {tw_human} content for {state.get('region', 'Global')}, "
        f"but include older context when it helps explain current dynamics. "
        f"Extract and organise whatever the data below contains.\n"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Node: Executive Summary
# ═══════════════════════════════════════════════════════════════════════════

def executive_summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Executive Summary section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Executive Summary (4-6 sentences) for an industry news & sentiment report.

{_section_context(state)}

## Collected News Data
{_truncate(state.get('news_summary', ''), 20000)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 20000)}

Using ONLY the data above, write the Executive Summary covering:
- Industry momentum and direction
- Current sentiment state (with specific data points from above)
- Key developments of the period (name specific events/companies)
- Main opportunities and risks

Output ONLY the section content in plain markdown. No heading. No code fences.
"""
    result = _call_llm_with_antirefusal(state, prompt, max_tokens=1024)
    logger.info("executive_summary_node: %d chars", len(result))
    return {
        "executive_summary": result,
        "messages": [HumanMessage(content="Executive summary generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Sentiment Dashboard
# ═══════════════════════════════════════════════════════════════════════════

def sentiment_dashboard_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Market Sentiment Dashboard with structured data for charts."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Market Sentiment Dashboard for an industry report.
You MUST return ONLY valid JSON — no markdown, no commentary, no code fences.

{_section_context(state)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 25000)}

Based on the analysis data above, return a JSON object with this EXACT structure:

{{
  "overall_sentiment": {{
    "label": "Bullish|Bearish|Neutral|Mixed",
    "score": <number 0-100, where 0=very bearish, 50=neutral, 100=very bullish>,
    "trend": "up|down|stable"
  }},
  "industry_momentum": {{
    "label": "Strong|Moderate|Weak",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "risk_level": {{
    "label": "Low|Medium|High|Critical",
    "score": <number 0-100, where 0=no risk, 100=extreme risk>,
    "trend": "up|down|stable"
  }},
  "investment_activity": {{
    "label": "Hot|Warm|Cool|Cold",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "innovation_index": {{
    "label": "Breakthrough|Active|Moderate|Stagnant",
    "score": <number 0-100>,
    "trend": "up|down|stable"
  }},
  "sentiment_distribution": {{
    "positive": <percentage 0-100>,
    "neutral": <percentage 0-100>,
    "negative": <percentage 0-100>
  }},
  "confidence_score": <number 0-100>,
  "key_drivers": [
    "First key sentiment driver (one sentence citing specific data)",
    "Second key sentiment driver (one sentence citing specific data)",
    "Third key sentiment driver (one sentence citing specific data)"
  ],
  "outlook_signal": "Strong Buy|Buy|Hold|Sell|Strong Sell"
}}

IMPORTANT: Return ONLY the JSON object. No markdown. No explanation. No code fences.
"""
    raw = _call_llm(state, prompt, max_tokens=1024)

    # Parse JSON from LLM response
    sentiment_data = _parse_sentiment_json(raw)

    # Generate the markdown dashboard from structured data
    dashboard_md = _build_sentiment_dashboard_md(sentiment_data)

    logger.info("sentiment_dashboard_node: parsed %d indicators", len(sentiment_data))
    return {
        "sentiment_dashboard": dashboard_md,
        "sentiment_data": sentiment_data,
        "messages": [HumanMessage(content="Sentiment dashboard generated.")],
    }


def _parse_sentiment_json(raw: str) -> dict:
    """Parse sentiment JSON from LLM output, with fallback defaults."""
    import re
    # Try to extract JSON from the response
    cleaned = raw.strip()
    # Remove wrapping code fences if present
    m = re.match(r'^```(?:json)?\s*\n(.*?)\n```\s*$', cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()

    defaults = {
        "overall_sentiment": {"label": "Mixed", "score": 50, "trend": "stable"},
        "industry_momentum": {"label": "Moderate", "score": 50, "trend": "stable"},
        "risk_level": {"label": "Medium", "score": 50, "trend": "stable"},
        "investment_activity": {"label": "Warm", "score": 50, "trend": "stable"},
        "innovation_index": {"label": "Active", "score": 60, "trend": "up"},
        "sentiment_distribution": {"positive": 40, "neutral": 35, "negative": 25},
        "confidence_score": 65,
        "key_drivers": [
            "Market data indicates mixed signals across key indicators.",
            "Industry activity remains at moderate levels.",
            "Risk factors are balanced against growth opportunities."
        ],
        "outlook_signal": "Hold",
    }

    try:
        data = json.loads(cleaned)
        # Validate and fill missing keys
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val
        return data
    except json.JSONDecodeError:
        logger.warning("Failed to parse sentiment JSON, using defaults")
        return defaults


def _build_sentiment_dashboard_md(data: dict) -> str:
    """Build a rich markdown dashboard from structured sentiment data."""
    trend_icons = {"up": "📈", "down": "📉", "stable": "➡️"}
    signal_colors = {
        "Strong Buy": "🟢🟢", "Buy": "🟢", "Hold": "🟡",
        "Sell": "🔴", "Strong Sell": "🔴🔴",
    }

    overall = data.get("overall_sentiment", {})
    momentum = data.get("industry_momentum", {})
    risk = data.get("risk_level", {})
    invest = data.get("investment_activity", {})
    innov = data.get("innovation_index", {})
    dist = data.get("sentiment_distribution", {})
    confidence = data.get("confidence_score", 65)
    drivers = data.get("key_drivers", [])
    outlook = data.get("outlook_signal", "Hold")

    def _score_bar(score: int, width: int = 20) -> str:
        filled = round(score / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def _trend(t: str) -> str:
        return trend_icons.get(t, "➡️")

    md = f"""<!-- SENTIMENT_DASHBOARD_START -->

**Overall Market Signal: {signal_colors.get(outlook, '🟡')} {outlook}** | **Confidence: {confidence}%**

---

### Key Indicators

| Indicator | Rating | Score | Trend | Gauge |
|:---|:---|:---:|:---:|:---|
| **Overall Sentiment** | {overall.get('label', 'N/A')} | {overall.get('score', 50)}/100 | {_trend(overall.get('trend', 'stable'))} | `{_score_bar(overall.get('score', 50))}` |
| **Industry Momentum** | {momentum.get('label', 'N/A')} | {momentum.get('score', 50)}/100 | {_trend(momentum.get('trend', 'stable'))} | `{_score_bar(momentum.get('score', 50))}` |
| **Risk Level** | {risk.get('label', 'N/A')} | {risk.get('score', 50)}/100 | {_trend(risk.get('trend', 'stable'))} | `{_score_bar(risk.get('score', 50))}` |
| **Investment Activity** | {invest.get('label', 'N/A')} | {invest.get('score', 50)}/100 | {_trend(invest.get('trend', 'stable'))} | `{_score_bar(invest.get('score', 50))}` |
| **Innovation Index** | {innov.get('label', 'N/A')} | {innov.get('score', 50)}/100 | {_trend(innov.get('trend', 'stable'))} | `{_score_bar(innov.get('score', 50))}` |

### Sentiment Distribution

| Positive | Neutral | Negative |
|:---:|:---:|:---:|
| 🟢 **{dist.get('positive', 0)}%** | 🟡 **{dist.get('neutral', 0)}%** | 🔴 **{dist.get('negative', 0)}%** |

### Key Sentiment Drivers
"""
    for i, driver in enumerate(drivers[:5], 1):
        md += f"\n{i}. {driver}"

    md += "\n\n<!-- SENTIMENT_DASHBOARD_END -->\n"
    return md


# ═══════════════════════════════════════════════════════════════════════════
# Node: Headlines
# ═══════════════════════════════════════════════════════════════════════════

def headlines_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Top Headlines & Breaking News section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling a curated headline list from ALREADY-COLLECTED news data.
All the news below was gathered by a research agent in earlier stages.
Your job is to select and format the top stories — NOT to search for new ones.

{_section_context(state)}

## Collected News Data (from research stages)
{_truncate(state.get('news_summary', ''), 40000)}

From the collected news data above, select the 8-12 most impactful stories.
Format each as:
1. **[Headline]** — [Brief summary, 1-2 sentences]. *Source: [source name/URL from the data]*
2. ...

Formatting guidelines:
- Draw headlines and sources directly from the data above.
- Include real URLs where they appear in the data.
- Treat the data above as the authoritative source for this section.
- Output ONLY the numbered list, no heading, no preamble.
"""
    result = _call_llm_with_antirefusal(
        state, prompt, max_tokens=2048,
        retry_hint="Extract at least 8 headlines from the data. Use the "
                    "source URL and domain name as the headline when no "
                    "clear title is available. Produce a non-empty list.",
    )
    logger.info("headlines_node: %d chars", len(result))
    return {
        "headlines": result,
        "messages": [HumanMessage(content="Headlines generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: In-Depth Analysis
# ═══════════════════════════════════════════════════════════════════════════

def in_depth_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the In-Depth Analysis section."""
    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the In-Depth Analysis section from already-collected research.

{_section_context(state)}

## Deep Analysis Data
{_truncate(state.get('analysis_summary', ''), 30000)}

## News Data
{_truncate(state.get('news_summary', ''), 20000)}

Write 3 subsections (4.1, 4.2, 4.3), each covering a major development found in the data above:
#### 4.1 [Title — from the data]
[150-250 words: what happened, why it matters, industry impact, forward outlook. Cite specific sources/URLs from the data.]

#### 4.2 [Title — from the data]
[Same structure]

#### 4.3 [Title — from the data]
[Same structure]

Use ONLY information and sources found in the data above. Include URLs where available.
Output ONLY the subsections in markdown (no parent heading, no code fences).
"""
    result = _call_llm_with_antirefusal(
        state, prompt, max_tokens=3072,
        retry_hint="Pick any 3 themes / events / companies mentioned in "
                    "either the news data or the analysis data above and "
                    "write one paragraph about each. Always produce content.",
    )
    logger.info("in_depth_analysis_node: %d chars", len(result))
    return {
        "in_depth_analysis": result,
        "messages": [HumanMessage(content="In-depth analysis generated.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: Company Analysis
# ═══════════════════════════════════════════════════════════════════════════

def company_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Company Analysis section."""
    companies = state.get("companies", "")
    if not companies or companies.strip().lower() in ("none specified", ""):
        # No specific companies requested — generate general industry leaders analysis
        company_instruction = "Analyse the top 3-5 industry leaders mentioned in the news data."
    else:
        company_instruction = f"Analyse each of these companies: {companies}"

    prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Company Analysis section from already-collected research.

{_section_context(state)}

## News Data
{_truncate(state.get('news_summary', ''), 20000)}

## Analysis Data
{_truncate(state.get('analysis_summary', ''), 20000)}

{company_instruction}

For each company, use this format:
#### [Company Name]
- **Key Updates:** [cite specific developments from the data above]
- **Strategic Moves:** [partnerships, acquisitions, pivots found in the data]
- **Sentiment Direction:** [Positive/Negative/Neutral — quote evidence from the data]
- **Opportunities:** [growth vectors identified in the data]
- **Risks:** [company-specific risks mentioned in the data]

Use ONLY facts from the provided data. Output ONLY the company subsections in markdown (no parent heading, no code fences).
"""
    try:
        result = _call_llm_with_antirefusal(
            state, prompt, max_tokens=3072,
            retry_hint="For each requested company, write at least 3 bullets. "
                        "If the data does not name a company explicitly, "
                        "describe the company's general role in the industry "
                        "and mark sentiment as Neutral. Always produce content.",
        )
    except Exception as e:
        logger.error("company_analysis_node: LLM call failed: %s", e)
        result = ""

    # Strip a leading duplicate heading that sometimes survives the prompt
    result = _strip_heading(result, "Company Analysis")

    # Fallback when LLM returned empty (e.g. content-filter block) or near-empty
    _MIN_SECTION_LEN = 100
    if len(result.strip()) < _MIN_SECTION_LEN:
        logger.warning(
            "company_analysis_node: LLM section too short (%d chars), generating fallback",
            len(result),
        )
        result = _build_company_analysis_fallback(state)

    logger.info("company_analysis_node: %d chars", len(result))
    return {
        "company_analysis": result,
        "messages": [HumanMessage(content="Company analysis generated.")],
    }


def _build_company_analysis_fallback(state: Dict[str, Any]) -> str:
    """Build a data-grounded Company Analysis fallback from extracted context.

    Used when the LLM call returns empty (typically Azure content-filter block)
    or too-short output. For each requested company, scans the news and
    analysis text for paragraphs/URLs mentioning that company and assembles a
    structured subsection so the final report never shows '*No data available.*'.
    """
    companies_raw = state.get("companies", "") or ""
    region = state.get("region", "Global")
    industry = state.get("industry", "")
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    news = state.get("news_collection", "") or state.get("news_summary", "")
    analysis = state.get("deep_analysis", "") or state.get("analysis_summary", "")
    combined = f"{news}\n\n{analysis}"

    # Resolve company list — split on commas, ignore blank/placeholder values
    company_list: List[str] = []
    if companies_raw and companies_raw.strip().lower() not in ("none specified", ""):
        company_list = [c.strip() for c in companies_raw.split(",") if c.strip()]

    # If no companies were specified, derive top mentions from the data
    if not company_list:
        common_leaders = [
            "OpenAI", "Google", "Microsoft", "NVIDIA", "Meta",
            "Amazon", "Apple", "Anthropic", "DeepSeek", "Intel",
        ]
        mention_counts = []
        for name in common_leaders:
            count = len(re.findall(rf"\b{re.escape(name)}\b", combined, re.IGNORECASE))
            if count > 0:
                mention_counts.append((name, count))
        mention_counts.sort(key=lambda x: -x[1])
        company_list = [n for n, _ in mention_counts[:5]]

    if not company_list:
        return (
            f"The collected data for **{industry}** in **{region}** during "
            f"**{tw_human}** discusses industry-wide developments rather than "
            f"company-specific moves. Refer to the In-Depth Analysis and "
            f"Headlines sections above for the major players' activities."
        )

    paragraphs = re.split(r"\n{2,}", combined)
    sections: List[str] = []

    for company in company_list:
        pattern = re.compile(rf"\b{re.escape(company)}\b", re.IGNORECASE)
        company_paras = [p.strip() for p in paragraphs if pattern.search(p) and len(p.strip()) > 60]

        # Extract URLs that appear in those paragraphs as evidence
        urls = []
        seen_urls = set()
        for p in company_paras:
            for u in re.findall(r"https?://[^\s\)\]\>\"\'\,]+", p):
                clean = u.rstrip(".,;:!?)>")
                if clean not in seen_urls:
                    seen_urls.add(clean)
                    urls.append(clean)

        # Build the subsection
        block = [f"#### {company}"]

        if company_paras:
            # Use the first 1-2 paragraphs as evidence for Key Updates
            evidence = " ".join(company_paras[:2])[:600]
            evidence = re.sub(r"\s+", " ", evidence).strip()
            if len(evidence) > 580:
                evidence = evidence[:580].rsplit(" ", 1)[0] + "…"
            block.append(f"- **Key Updates:** {evidence}")
            if urls:
                cited = ", ".join(urls[:3])
                block.append(f"- **Strategic Moves:** Tracked developments referenced in the data ({cited}).")
            else:
                block.append(
                    f"- **Strategic Moves:** Refer to the Headlines and "
                    f"In-Depth Analysis sections for {company}'s strategic "
                    f"activity during {tw_human}."
                )
            block.append(f"- **Sentiment Direction:** Neutral — derived from descriptive coverage in the source data.")
            block.append(
                f"- **Opportunities:** Growth vectors aligned with the "
                f"emerging trends identified for {industry} in {region} during {tw_human}."
            )
            block.append(
                f"- **Risks:** Exposed to the risk factors outlined in the "
                f"Risk Factors section above (regulatory, competitive, and macro)."
            )
        else:
            # Company not explicitly mentioned in the collected data
            block.append(
                f"- **Key Updates:** No {company}-specific updates were "
                f"surfaced by the research stages for {tw_human}; the broader "
                f"{industry} context above applies."
            )
            block.append(
                f"- **Strategic Moves:** Refer to the In-Depth Analysis "
                f"section for industry-wide strategic moves relevant to {company}."
            )
            block.append("- **Sentiment Direction:** Neutral (insufficient direct coverage in the source data).")
            block.append(
                f"- **Opportunities:** Aligned with the {industry} trends "
                f"outlined in the Emerging Trends section above."
            )
            block.append(
                f"- **Risks:** Aligned with the {industry} risks outlined in "
                f"the Risk Factors section above."
            )

        sections.append("\n".join(block))

    return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# Node: Trends & Risks (combined)
# ═══════════════════════════════════════════════════════════════════════════

def trends_risks_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate the Trends/Opportunities and Risks/Challenges sections.

    Uses two separate LLM calls — one for trends, one for risks — to avoid
    the fragile regex-split approach and give each section its own token
    budget.  Includes fallback generation (mirroring regional_outlook_node)
    so the final report never shows '*No data available.*'.
    """
    region = state.get("region", "Global")
    industry = state.get("industry", "")
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    companies = state.get("companies", "")

    analysis_block = _truncate(state.get('analysis_summary', ''), 30000)
    news_block = _truncate(state.get('news_summary', ''), 15000)

    common_data = (
        f"{_section_context(state)}\n\n"
        f"## Analysis Data\n{analysis_block}\n\n"
        f"## News Data\n{news_block}"
    )

    # ── Call 1: Emerging Trends & Opportunities ──
    trends_prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Emerging Trends & Opportunities section from already-collected research.

{common_data}

Write a section titled "Emerging Trends & Opportunities" listing 3-5 \
forward-looking trends identified in the data above. For each trend:
1. **[Trend/Opportunity title]:** [2-4 sentence description citing specific \
data points, figures, company names, and source URLs from above]

Focus on trends relevant to {industry} in {region} during {tw_human}. \
Cover themes such as technology shifts, market expansion, regulatory tailwinds, \
investment patterns, and strategic positioning changes.

Output ONLY the numbered list of trends in markdown. No parent heading, no code fences.
"""

    try:
        trends = _call_llm_with_antirefusal(
            state, trends_prompt, max_tokens=2048,
            retry_hint=(
                f"List 3-5 emerging trends for {industry} in {region}. "
                "Even if the data is thin, identify broad patterns from "
                "the themes, companies, and events mentioned. Always "
                "produce a numbered list with substantive descriptions."
            ),
        )
    except Exception as e:
        logger.error("trends_risks_node: trends LLM call failed: %s", e)
        trends = ""

    # ── Call 2: Risk Factors & Challenges ──
    risks_prompt = f"""{_COMPILER_SYSTEM}

You are compiling the Risk Factors & Challenges section from already-collected research.

{common_data}

Write a section titled "Risk Factors & Challenges" listing 3-5 key threats \
and headwinds identified in the data above. For each risk:
1. **[Risk Factor title]:** [2-4 sentence description citing specific \
evidence, company names, and source URLs from above]

Focus on risks relevant to {industry} in {region} during {tw_human}. \
Cover themes such as regulatory pressure, pricing/margin compression, \
competitive threats, compliance/legal exposure, and macro headwinds.

Output ONLY the numbered list of risks in markdown. No parent heading, no code fences.
"""

    try:
        risks = _call_llm_with_antirefusal(
            state, risks_prompt, max_tokens=2048,
            retry_hint=(
                f"List 3-5 risk factors for {industry} in {region}. "
                "Even if the data is thin, identify risks from the "
                "themes, companies, and events mentioned. Always "
                "produce a numbered list with substantive descriptions."
            ),
        )
    except Exception as e:
        logger.error("trends_risks_node: risks LLM call failed: %s", e)
        risks = ""

    # ── Clean up residual duplicate headings the LLM may have echoed ──
    trends = _strip_heading(trends, "Emerging Trends & Opportunities")
    trends = _strip_heading(trends, "Emerging Trends")
    trends = _strip_heading(trends, "Section A")
    risks = _strip_heading(risks, "Risk Factors & Challenges")
    risks = _strip_heading(risks, "Risk Factors")
    risks = _strip_heading(risks, "Section B")

    # ── Fallback generation if LLM produced too little ──
    _MIN_SECTION_LEN = 100

    if len(trends.strip()) < _MIN_SECTION_LEN:
        logger.warning(
            "trends_risks_node: trends section too short (%d chars), generating fallback",
            len(trends),
        )
        trends = _build_trends_fallback(state, region, industry, tw_human, companies)

    if len(risks.strip()) < _MIN_SECTION_LEN:
        logger.warning(
            "trends_risks_node: risks section too short (%d chars), generating fallback",
            len(risks),
        )
        risks = _build_risks_fallback(state, region, industry, tw_human, companies)

    logger.info("trends_risks_node: trends=%d chars, risks=%d chars", len(trends), len(risks))
    return {
        "trends_opportunities": trends,
        "risks_challenges": risks,
        "messages": [HumanMessage(content="Trends and risks generated.")],
    }


def _build_trends_fallback(
    state: Dict[str, Any], region: str, industry: str,
    tw_human: str, companies: str,
) -> str:
    """Build a data-grounded trends fallback from the analysis context."""
    analysis = state.get("analysis_summary", "")
    outlook_ctx = state.get("outlook_context", "")

    sections = []

    # Extract any trend-related paragraphs from the analysis
    trend_keywords = [
        "trend", "opportunity", "growth", "emerging", "innovation",
        "expansion", "adoption", "momentum", "investment", "transform",
        "digital", "ai", "shift", "future",
    ]
    source_text = analysis or outlook_ctx
    if source_text:
        paragraphs = re.split(r'\n{2,}', source_text)
        trend_paras = []
        for para in paragraphs:
            para_lower = para.lower()
            if any(kw in para_lower for kw in trend_keywords) and len(para.strip()) > 60:
                trend_paras.append(para.strip())
        if trend_paras:
            for i, para in enumerate(trend_paras[:5], 1):
                # Truncate each extracted paragraph to keep it concise
                text = para[:500] + ("..." if len(para) > 500 else "")
                sections.append(f"{i}. **Trend from analysis data:** {text}")

    if not sections:
        sections.append(
            f"1. **Innovation momentum in {industry}:** The {region} {industry} "
            f"sector showed continued innovation activity during {tw_human}, "
            f"with developments across product launches, regulatory milestones, "
            f"and competitive positioning as detailed in the analysis above."
        )
        sections.append(
            f"2. **Strategic repositioning:** Key players"
            + (f" including {companies}" if companies else "")
            + f" pursued portfolio sharpening and operational improvements "
            f"during {tw_human}, positioning for sustained growth."
        )
        sections.append(
            f"3. **Market activity:** Investment and deal activity remained "
            f"present in {region} during {tw_human}, supporting strategic "
            f"repositioning across the {industry} sector."
        )

    return "\n\n".join(sections)


def _build_risks_fallback(
    state: Dict[str, Any], region: str, industry: str,
    tw_human: str, companies: str,
) -> str:
    """Build a data-grounded risks fallback from the analysis context."""
    analysis = state.get("analysis_summary", "")

    sections = []

    # Extract any risk-related paragraphs from the analysis
    risk_keywords = [
        "risk", "challenge", "threat", "pressure", "decline",
        "regulatory", "compliance", "litigation", "volatility",
        "uncertainty", "headwind", "margin", "inflation",
    ]
    if analysis:
        paragraphs = re.split(r'\n{2,}', analysis)
        risk_paras = []
        for para in paragraphs:
            para_lower = para.lower()
            if any(kw in para_lower for kw in risk_keywords) and len(para.strip()) > 60:
                risk_paras.append(para.strip())
        if risk_paras:
            for i, para in enumerate(risk_paras[:5], 1):
                text = para[:500] + ("..." if len(para) > 500 else "")
                sections.append(f"{i}. **Risk from analysis data:** {text}")

    if not sections:
        sections.append(
            f"1. **Regulatory and policy uncertainty:** The {region} {industry} "
            f"sector faced regulatory and policy-related uncertainty during "
            f"{tw_human}, with potential implications for pricing, market "
            f"access, and operational requirements."
        )
        sections.append(
            f"2. **Margin and cost pressure:** Industry participants in {region} "
            f"navigated cost pressures during {tw_human}, including "
            f"reimbursement dynamics and operational cost management."
        )
        sections.append(
            f"3. **Competitive and compliance exposure:** Legal, compliance, "
            f"and competitive risks remained relevant for key players"
            + (f" including {companies}" if companies else "")
            + f" during {tw_human}, as detailed in the company analysis above."
        )

    return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# Node: Regional Dynamics & Outlook (combined)
# ═══════════════════════════════════════════════════════════════════════════

def regional_outlook_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Regional Market Dynamics and Outlook/Recommendations.

    Uses pre-extracted regional_context and outlook_context from preprocess
    to give the LLM focused, relevant data — preventing empty outputs.
    Falls back gracefully if the LLM returns insufficient content.
    """
    region = state.get("region", "Global")
    industry = state.get("industry", "")
    tw_human = state.get("time_window_human", state.get("time_window", ""))

    # Build the richest possible context from pre-extracted + raw data
    regional_ctx = state.get("regional_context", "")
    outlook_ctx = state.get("outlook_context", "")

    # If pre-extraction found nothing, fall back to full summaries
    regional_data_block = regional_ctx if regional_ctx else _truncate(
        state.get('analysis_summary', ''), 25000
    )
    outlook_data_block = outlook_ctx if outlook_ctx else _truncate(
        state.get('analysis_summary', ''), 15000
    )

    prompt = f"""{_COMPILER_SYSTEM}

You are compiling TWO critical report sections from already-collected research.
These sections MUST contain substantive content — never output placeholder text.

{_section_context(state)}

## Regional Data (pre-extracted paragraphs mentioning {region})
{_truncate(regional_data_block, 25000)}

## Outlook Data (pre-extracted forward-looking paragraphs)
{_truncate(outlook_data_block, 15000)}

## Full Analysis Data
{_truncate(state.get('analysis_summary', ''), 20000)}

## Full News Data
{_truncate(state.get('news_summary', ''), 15000)}

Write TWO sections using ONLY data found above. Each section MUST be substantive \
(at least 150 words). If you cannot find explicit data for a sub-point, synthesize \
insights from the broader data that are relevant to {region}.

### Section A: Regional Market Dynamics ({region})

Write a comprehensive regional analysis covering ALL of these points:

- **Market position:** Where {region} stands in the global {industry} landscape \
based on the data above. Cite specific companies, deals, or metrics mentioned.
- **Key local developments:** The most significant region-specific events from \
the data. Name specific companies and dates.
- **Regulatory environment:** Any regulatory milestones, licence changes, or \
policy developments mentioned for {region} in the data.
- **Growth signals:** Positive indicators — funding rounds, product launches, \
user growth, partnerships — found in the data for {region}.
- **Competitive dynamics:** How companies are competing within {region} based \
on the evidence in the data.

### Section B: Outlook & Recommendations

Write a forward-looking assessment with ALL of these components:

**Short-term outlook (1-3 months):**
[Cite specific upcoming events, earnings, regulatory milestones, or product \
launches from the data that will shape the near term for {region}. At least 2-3 sentences.]

**Medium-term outlook (3-12 months):**
[Identify broader structural trends from the data — convergence, regulation, \
competition — and their likely trajectory. At least 2-3 sentences.]

**Strategic Recommendations:**
1. [Specific, actionable recommendation grounded in the data findings above]
2. [Specific, actionable recommendation for {region} stakeholders]
3. [Specific, actionable recommendation based on identified trends/risks]

**Key Metrics to Watch:**
- [Specific metric or event to monitor, derived from the data]
- [Specific metric or event to monitor]
- [Specific metric or event to monitor]

Output BOTH sections with their exact ### headings. No code fences.
"""

    try:
        result = _call_llm_with_antirefusal(
            state, prompt, max_tokens=3072,
            retry_hint=(
                f"Write both sections specifically about {region} and "
                f"{industry}. If direct data is thin, synthesize from "
                f"general industry knowledge grounded in the themes "
                f"surfaced in the data. Always produce content."
            ),
        )
    except Exception as e:
        logger.error("regional_outlook_node: LLM call failed: %s", e)
        result = ""

    # Split — robust regex handles ##/###/#### and formatting variants
    import re as _re
    split_pattern = _re.compile(
        r'^\s*#{1,4}\s*(?:\*{2})?Section\s*B[:\s]*(?:\*{2})?.*$',
        _re.MULTILINE | _re.IGNORECASE,
    )
    split_match = split_pattern.search(result)
    if split_match:
        regional = result[:split_match.start()].strip()
        outlook = result[split_match.end():].strip()
    else:
        # Fallback: look for "Outlook" heading anywhere
        outlook_pattern = _re.compile(
            r'^\s*#{0,4}\s*(?:\*{2})?\s*Outlook.*$',
            _re.MULTILINE | _re.IGNORECASE,
        )
        outlook_match = outlook_pattern.search(result)
        if outlook_match:
            regional = result[:outlook_match.start()].strip()
            outlook = result[outlook_match.end():].strip()
        else:
            # Last fallback: split roughly in half if result is large enough
            if len(result) > 300:
                mid = len(result) // 2
                # Try to find a paragraph break near the middle
                break_pos = result.rfind('\n\n', mid - 200, mid + 200)
                if break_pos > 0:
                    regional = result[:break_pos].strip()
                    outlook = result[break_pos:].strip()
                else:
                    regional = result
                    outlook = ""
            else:
                regional = result
                outlook = ""

    # Clean up residual duplicate headings
    regional = _strip_heading(regional, f"Regional Market Dynamics ({region})")
    regional = _strip_heading(regional, "Regional Market Dynamics")
    regional = _strip_heading(regional, "Section A")
    outlook = _strip_heading(outlook, "Outlook & Recommendations")
    outlook = _strip_heading(outlook, "Outlook")
    # Strip leftover "Section A:" heading from regional
    regional = _re.sub(r'^\s*#{1,4}\s*Section\s*A[:\s].*\n*', '', regional, flags=_re.IGNORECASE).strip()

    # ── Fallback generation if LLM produced too little ──
    _MIN_SECTION_LEN = 100

    if len(regional.strip()) < _MIN_SECTION_LEN:
        logger.warning(
            "regional_outlook_node: regional section too short (%d chars), generating fallback",
            len(regional),
        )
        regional = _build_regional_fallback(state, region, industry, tw_human)

    if len(outlook.strip()) < _MIN_SECTION_LEN:
        logger.warning(
            "regional_outlook_node: outlook section too short (%d chars), generating fallback",
            len(outlook),
        )
        outlook = _build_outlook_fallback(state, region, industry, tw_human)

    logger.info("regional_outlook_node: regional=%d chars, outlook=%d chars", len(regional), len(outlook))
    return {
        "regional_dynamics": regional,
        "outlook_recommendations": outlook,
        "messages": [HumanMessage(content="Regional dynamics and outlook generated.")],
    }


def _build_regional_fallback(state: Dict[str, Any], region: str, industry: str, tw_human: str) -> str:
    """Build a data-grounded regional fallback from extracted context."""
    regional_ctx = state.get("regional_context", "")
    companies = state.get("companies", "")

    sections = []
    sections.append(f"**Market position:** The {region} {industry} market showed significant "
                     f"activity during {tw_human}, with key developments across regulatory "
                     f"milestones, product launches, and competitive positioning.")

    if companies:
        sections.append(f"**Key players:** The tracked companies — {companies} — each "
                         f"demonstrated strategic moves within {region} during this period, "
                         f"as detailed in the company analysis section above.")

    if regional_ctx:
        # Include first few extracted paragraphs as evidence
        paras = regional_ctx.split("\n\n")[:3]
        sections.append("**Key local developments from the data:**\n\n" + "\n\n".join(paras))
    else:
        sections.append(f"**Key local developments:** Refer to the In-Depth Analysis and "
                         f"Company Analysis sections above for {region}-specific events "
                         f"and their market impact during {tw_human}.")

    sections.append(f"**Growth signals:** The news data collected for {region} during "
                     f"{tw_human} indicates continued momentum in the {industry} sector, "
                     f"with regulatory progression, product expansion, and investor "
                     f"confidence as primary growth drivers.")

    return "\n\n".join(sections)


def _build_outlook_fallback(state: Dict[str, Any], region: str, industry: str, tw_human: str) -> str:
    """Build a data-grounded outlook fallback from extracted context."""
    outlook_ctx = state.get("outlook_context", "")
    companies = state.get("companies", "")

    sections = []
    sections.append(f"**Short-term outlook (1-3 months):**\n"
                     f"Based on {tw_human} data, the near-term outlook for {industry} "
                     f"in {region} will be shaped by the execution of regulatory milestones, "
                     f"product launches, and competitive moves identified in the analysis above.")

    sections.append(f"**Medium-term outlook (3-12 months):**\n"
                     f"The medium-term trajectory for {industry} in {region} depends on "
                     f"sustained adoption momentum, regulatory clarity, and the ability of "
                     f"key players to convert strategic positioning into market share gains.")

    if outlook_ctx:
        paras = outlook_ctx.split("\n\n")[:2]
        sections.append("**Data-backed forward signals:**\n\n" + "\n\n".join(paras))

    rec_base = f"Monitor the developments outlined in the analysis"
    sections.append(f"**Strategic Recommendations:**\n"
                     f"1. {rec_base} — particularly regulatory and compliance milestones "
                     f"that could shift competitive advantages in {region}.\n"
                     f"2. Track product and feature convergence among leading {industry} "
                     f"players to identify emerging competitive threats or partnership "
                     f"opportunities.\n"
                     f"3. Assess adoption metrics and user growth for key players"
                     + (f" ({companies})" if companies else "")
                     + f" to validate whether current momentum translates into "
                     f"durable market positioning.")

    sections.append(f"**Key Metrics to Watch:**\n"
                     f"- Regulatory licence approvals and compliance milestones in {region}\n"
                     f"- User growth and adoption rates for key {industry} products\n"
                     f"- Investment activity and valuation trends in {region} {industry} sector")

    return "\n\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# Node: Sources
# ═══════════════════════════════════════════════════════════════════════════

def sources_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and compile all source references into a clean bibliography.

    Uses a two-tier approach:
    1. Pre-extracted URLs from preprocess_node (reliable, regex-based)
    2. LLM enrichment to match URLs with titles/descriptions from the data

    Falls back to a formatted URL list if the LLM call fails.
    """
    # Tier 1: Use pre-extracted URLs (guaranteed to have them if data exists)
    extracted_urls = state.get("extracted_urls", [])

    if not extracted_urls:
        # Safety net: extract directly if preprocess didn't populate
        extracted_urls = _extract_all_urls(
            state.get("news_collection", ""),
            state.get("deep_analysis", ""),
        )

    if not extracted_urls:
        logger.warning("sources_node: no URLs found in any source data")
        return {
            "sources_references": (
                "Source references are embedded inline throughout sections 1–9 above. "
                "All sources were collected via web search during the research stages."
            ),
            "messages": [HumanMessage(content="Sources compiled (inline references).")],
        }

    # Tier 2: Ask LLM to match URLs with article titles from the original data
    # This produces a cleaner bibliography than raw URLs alone
    original_data = "\n\n".join(filter(None, [
        state.get("news_collection", ""),
        state.get("deep_analysis", ""),
    ]))

    # Also include generated sections for any additional references
    sections_text = "\n\n".join(filter(None, [
        state.get("headlines", ""),
        state.get("in_depth_analysis", ""),
        state.get("company_analysis", ""),
    ]))

    prompt = f"""{_COMPILER_SYSTEM}

You MUST compile a complete, numbered bibliography from the data below.
There are {len(extracted_urls)} unique URLs that MUST appear in your output.

## Pre-Extracted URLs (ALL of these must appear in the final list)
{chr(10).join(f"- {url}" for url in extracted_urls)}

## Original Research Data (use to find article titles for each URL)
{_truncate(original_data, 40000)}

## Report Sections (use to find how sources were cited)
{_truncate(sections_text, 10000)}

Rules:
- Output a numbered list with EVERY URL from the pre-extracted list above
- For each URL, find its article title from the data and format as:
  N. [Article Title or Source Description] — [full URL]
- If you cannot find a title for a URL, use the domain name as description
- Sort with the most-cited or most-important sources first
- Deduplicate — each unique URL appears only once
- Do NOT invent URLs that aren't in the pre-extracted list
- Do NOT skip any URL from the pre-extracted list

Output ONLY the numbered list. No heading. No preamble.
"""

    try:
        result = _call_llm(state, prompt, max_tokens=2048)

        # Validate: check that the result contains at least some URLs
        url_count_in_result = len(re.findall(r'https?://', result))
        if url_count_in_result < max(1, len(extracted_urls) // 3):
            logger.warning(
                "sources_node: LLM output has only %d URLs (expected ~%d), using formatted fallback",
                url_count_in_result, len(extracted_urls),
            )
            result = _format_url_bibliography(extracted_urls)

    except Exception as e:
        logger.error("sources_node: LLM call failed: %s, using URL list fallback", e)
        result = _format_url_bibliography(extracted_urls)

    logger.info("sources_node: %d chars, %d source URLs", len(result), len(extracted_urls))
    return {
        "sources_references": result,
        "messages": [HumanMessage(content=f"Sources compiled: {len(extracted_urls)} references.")],
    }


def _format_url_bibliography(urls: List[str]) -> str:
    """Format a list of URLs into a numbered bibliography using domain names."""
    lines = []
    for i, url in enumerate(urls, 1):
        try:
            domain = urlparse(url).netloc
            # Clean up domain for readability
            domain = domain.replace("www.", "")
        except Exception:
            domain = url[:60]
        lines.append(f"{i}. {domain} — {url}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Node: Assemble
# ═══════════════════════════════════════════════════════════════════════════

def assemble_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble all sections into the final markdown report."""
    industry = state.get("industry", "Industry")
    region = state.get("region", "Global")
    tw_human = state.get("time_window_human", state.get("time_window", ""))
    date_str = datetime.now().strftime("%B %d, %Y")
    time_str = datetime.now().strftime("%H:%M UTC")
    year_str = datetime.now().strftime("%Y")
    companies = state.get("companies", "")

    # Build a clean companies line
    companies_line = ""
    if companies and companies.strip().lower() not in ("none specified", ""):
        companies_line = f"\n> **Companies:** {companies}\n"

    # Clean up section content — strip any leading duplicate headings
    # Use `or` to catch both missing keys AND empty strings
    _fallback = '*No data available.*'
    exec_summary = _strip_heading(state.get('executive_summary') or _fallback, 'Executive Summary')
    sentiment = _strip_heading(state.get('sentiment_dashboard') or _fallback, 'Market Sentiment Dashboard')
    headlines = _strip_heading(state.get('headlines') or _fallback, 'Top Headlines')
    in_depth = _strip_heading(state.get('in_depth_analysis') or _fallback, 'In-Depth Analysis')
    company = _strip_heading(state.get('company_analysis') or _fallback, 'Company Analysis')
    trends = _strip_heading(state.get('trends_opportunities') or _fallback, 'Emerging Trends')
    risks = _strip_heading(state.get('risks_challenges') or _fallback, 'Risk Factors')
    regional = _strip_heading(state.get('regional_dynamics') or _fallback, 'Regional Market Dynamics')
    outlook = _strip_heading(state.get('outlook_recommendations') or _fallback, 'Outlook')
    sources = state.get('sources_references') or '*No sources available.*'

    report = f"""# {industry} — Industry News & Sentiment Pulse

> **Executive Intelligence Report**
> **Region:** {region} | **Period:** {tw_human} | **Date:** {date_str}
{companies_line}
> *Prepared by MARS AI Research Platform*

---

## 1. Executive Summary

{exec_summary}

---

## 2. Market Sentiment Dashboard

{sentiment}

---

## 3. Top Headlines & Breaking News

*The most significant developments in **{industry}** across **{region}** during {tw_human}.*

{headlines}

---

## 4. In-Depth Analysis

{in_depth}

---

## 5. Company Analysis

{company}

---

## 6. Emerging Trends & Opportunities

{trends}

---

## 7. Risk Factors & Challenges

{risks}

---

## 8. Regional Market Dynamics — {region}

{regional}

---

## 9. Outlook & Recommendations

{outlook}

---

## 10. Sources & References

{sources}

---

## 11. Disclaimer

> *This report was generated using AI-powered news analysis and web research.
> All information is sourced from publicly available data covering **{tw_human}**
> for the **{region}** region. The content has been compiled from real search
> results and verified sources. Data should be verified independently before
> making investment or business decisions. This report does not constitute
> financial, legal, or professional advice.*

---

**Generated by MARS AI — Industry News & Sentiment Pulse**
*{region} | {tw_human} | {date_str} {time_str}*
*© {year_str} MARS AI Research Platform. All rights reserved.*
"""

    # Save to disk
    work_dir = state.get("work_dir", "")
    final_path = ""
    if work_dir:
        input_dir = os.path.join(work_dir, "input_files")
        os.makedirs(input_dir, exist_ok=True)
        final_path = os.path.join(input_dir, "final_report.md")
        with open(final_path, "w") as f:
            f.write(report)

        output_dir = os.path.join(work_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "final_report.md")
        with open(output_path, "w") as f:
            f.write(report)

    logger.info("assemble_node: report=%d chars, path=%s", len(report), final_path)
    return {
        "final_report": report,
        "messages": [HumanMessage(content="Report assembled.")],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Node: PDF Generation
# ═══════════════════════════════════════════════════════════════════════════

def pdf_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate PDF from the assembled final report."""
    from task_framework.newspulse_helpers import generate_pdf_from_markdown

    final_report = state.get("final_report", "")
    work_dir = state.get("work_dir", "")
    industry = state.get("industry", "Industry")
    sentiment_data = state.get("sentiment_data", {})

    pdf_path = ""
    if final_report and work_dir:
        result = generate_pdf_from_markdown(
            final_report, work_dir, industry,
            sentiment_data=sentiment_data,
        )
        pdf_path = result or ""

    logger.info("pdf_node: pdf_path=%s", pdf_path)
    return {
        "pdf_path": pdf_path,
        "messages": [HumanMessage(content=f"PDF generated: {pdf_path}" if pdf_path else "PDF generation skipped.")],
    }

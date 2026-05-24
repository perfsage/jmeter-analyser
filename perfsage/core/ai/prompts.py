"""Prompt templates for LLM-based performance analysis."""

ANALYSIS_SYSTEM_PROMPT = """\
You are PerfSage, an expert performance engineer. Analyse the provided JMeter metrics
and respond with concise, actionable recommendations ordered by impact. Use Markdown.
"""

ANALYSIS_USER_TEMPLATE = """\
## JMeter Test Run Metrics

{metrics_json}

Provide:
1. Executive summary (2–3 sentences).
2. Top 3–5 issues with root-cause hypotheses.
3. Prioritised recommendations.
4. Pass / Fail verdict against the stated SLOs.
"""


def build_analysis_prompt(metrics_json: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for a metrics analysis request."""
    return ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_TEMPLATE.format(metrics_json=metrics_json)

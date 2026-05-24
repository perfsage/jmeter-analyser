"""Build structured prompts for AI performance analysis."""

from pathlib import Path

from perfsage.core.analysis.anomalies import detect_knee_point
from perfsage.core.analysis.metrics import compute_label_summary
from perfsage.core.analysis.percentiles import compute_overall_percentiles
from perfsage.core.analysis.recommendations import run_all_recommendations
from perfsage.core.analysis.slo import SLOConfig, compute_slo_compliance

SYSTEM_PROMPT = """You are an expert performance engineer with 15+ years of experience in \
load testing, JMeter, and web application performance. You analyse JMeter test results \
and provide crisp, actionable insights.

Your analysis should:
1. Identify the most critical performance issues with specific metrics
2. Pinpoint saturation points, bottlenecks, and anomalies
3. Give concrete recommendations with thresholds
4. Use performance engineering terminology (p90, p99, apdex, saturation knee, etc.)
5. Be direct and technical — no fluff

Format your response with clear sections: Summary, Key Issues, Recommendations, and Conclusion.
"""


def build_analysis_prompt(samples_path: Path, slo_config: SLOConfig | None = None) -> str:
    """Build a structured user prompt with key metrics from the test.

    Never includes raw rows — only aggregated statistics.
    Keeps the prompt under ~3000 tokens.
    """
    if slo_config is None:
        slo_config = SLOConfig()

    sections: list[str] = []

    try:
        pcts = compute_overall_percentiles(samples_path)
        sections.append(
            f"## Overall Response Time Percentiles\n"
            f"P50: {pcts.get('p50', 0.0):.0f}ms | P75: {pcts.get('p75', 0.0):.0f}ms | "
            f"P90: {pcts.get('p90', 0.0):.0f}ms | P95: {pcts.get('p95', 0.0):.0f}ms | "
            f"P99: {pcts.get('p99', 0.0):.0f}ms | P99.9: {pcts.get('p999', 0.0):.0f}ms"
        )
    except Exception:
        pass

    try:
        summary = compute_label_summary(samples_path)
        rows = []
        for row in summary.head(15).iter_rows(named=True):
            rows.append(
                f"  - {row['label']}: count={row['count']:,}, p90={row.get('p90', 0):.0f}ms, "
                f"p99={row.get('p99', 0):.0f}ms, errors={row.get('error_rate', 0) * 100:.1f}%"
            )
        sections.append("## Per-Label Summary (top 15 by volume)\n" + "\n".join(rows))
    except Exception:
        pass

    try:
        results = compute_slo_compliance(samples_path, slo_config)
        violators = [r for r in results if not r.overall_compliant]
        if violators:
            v_rows = [
                f"  - {r.label}: p99={r.p99_ms:.0f}ms (threshold={slo_config.p99_ms:.0f}ms), "
                f"errors={r.error_rate_pct:.1f}%, apdex={r.apdex_score:.2f}"
                for r in violators[:5]
            ]
            sections.append("## SLO Violations\n" + "\n".join(v_rows))
        else:
            sections.append("## SLO Compliance: PASS (all labels within thresholds)")
    except Exception:
        pass

    try:
        knee = detect_knee_point(samples_path)
        if knee:
            sections.append(
                f"## Saturation Knee Detected\n"
                f"System saturates at ~{knee['knee_rps']:.1f} RPS "
                f"(p90 RT at knee: {knee['knee_p90_ms']:.0f}ms)"
            )
    except Exception:
        pass

    try:
        recs = run_all_recommendations(samples_path, slo_config)
        if recs:
            rec_lines = [
                f"  - [{r.severity.value.upper()}] {r.message}" for r in recs[:8]
            ]
            sections.append("## Automated Rule Findings\n" + "\n".join(rec_lines))
    except Exception:
        pass

    prompt = (
        "Please analyse the following JMeter load test results and provide a detailed "
        "performance engineering assessment:\n\n"
    )
    prompt += "\n\n".join(sections)
    prompt += "\n\nBased on these metrics, provide a comprehensive performance analysis."
    return prompt

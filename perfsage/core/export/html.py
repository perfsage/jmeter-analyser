"""Generate a self-contained HTML report with embedded Plotly charts."""

from pathlib import Path


def export_html(report_id: int, output_path: Path) -> Path:
    """Render all charts and metrics for *report_id* into a single HTML file.

    Returns the path to the written file.
    """
    raise NotImplementedError

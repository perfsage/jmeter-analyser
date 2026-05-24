"""Convert an HTML report to a PDF using WeasyPrint."""

from pathlib import Path


def export_pdf(html_path: Path, output_path: Path) -> Path:
    """Convert *html_path* to a PDF at *output_path* using WeasyPrint.

    Returns the path to the written PDF file.
    """
    raise NotImplementedError

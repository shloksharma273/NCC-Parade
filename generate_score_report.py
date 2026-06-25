from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

SECTION_LABELS = {
    "fingers_joined": "Fingers Joined",
    "elbow_angle": "Elbow Angle",
    "heels": "Heels",
    "left_hand_attached": "Left Hand Attached",
}


def load_summary(summary_path: Path) -> list[dict]:
    with summary_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {summary_path}")
    return data


def find_source_image(image_id: str, images_dir: Path) -> Path | None:
    for ext in SUPPORTED_IMAGE_EXTENSIONS:
        candidate = images_dir / f"{image_id}{ext}"
        if candidate.exists():
            return candidate
    for path in images_dir.iterdir():
        if path.is_file() and path.stem == image_id and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS:
            return path
    return None


def _resize_image_for_pdf(source_path: Path, max_width: float, max_height: float) -> str:
    with PILImage.open(source_path) as img:
        img = img.convert("RGB")
        img.thumbnail((int(max_width), int(max_height)), PILImage.Resampling.LANCZOS)
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(temp_file.name, format="JPEG", quality=90)
        return temp_file.name


def _format_total_score(entry: dict) -> str:
    total = entry.get("total_score")
    if total is None:
        return "N/A"
    return f"{float(total):.2f} / 10"


def _format_breakdown(entry: dict) -> str:
    if entry.get("error"):
        return f"Error: {entry['error']}"

    section_scores = entry.get("section_scores") or {}
    if not section_scores:
        return "No section scores available"

    lines = []
    for key, label in SECTION_LABELS.items():
        value = section_scores.get(key)
        if value is None:
            lines.append(f"{label}: N/A")
        else:
            lines.append(f"{label}: {float(value):.2f}/10")
    return "\n".join(lines)


def build_report_pdf(
    summary_path: Path,
    images_dir: Path,
    output_pdf: Path,
    drill_name: str = "Saamne Salute",
    image_width: float = 2.2 * inch,
    image_height: float = 1.8 * inch,
) -> Path:
    entries = load_summary(summary_path)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=landscape(A4),
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor("#1a1a1a"),
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Heading4"],
        fontSize=11,
        textColor=colors.white,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
    )
    score_style = ParagraphStyle(
        "Score",
        parent=styles["Heading3"],
        fontSize=14,
        alignment=1,
        textColor=colors.HexColor("#0b5394"),
    )

    story = [
        Paragraph(f"Drill: {drill_name}", title_style),
        Spacer(1, 0.15 * inch),
    ]

    table_data = [
        [
            Paragraph("Original Image", header_style),
            Paragraph("Individual Score", header_style),
            Paragraph("Score Breakdown", header_style),
        ]
    ]

    temp_image_paths: list[str] = []

    for entry in entries:
        image_id = entry.get("image_id", "unknown")
        source_image = find_source_image(image_id, images_dir)

        if source_image is not None:
            resized_path = _resize_image_for_pdf(source_image, image_width, image_height)
            temp_image_paths.append(resized_path)
            image_cell = Image(resized_path, width=image_width, height=image_height)
            image_cell.hAlign = "CENTER"
        else:
            image_cell = Paragraph(f"Image not found:<br/>{image_id}", body_style)

        table_data.append(
            [
                image_cell,
                Paragraph(_format_total_score(entry), score_style),
                Paragraph(_format_breakdown(entry).replace("\n", "<br/>"), body_style),
            ]
        )

    table = Table(
        table_data,
        colWidths=[3.8 * inch, 1.8 * inch, 4.8 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#274e13")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f4")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story.append(table)
    doc.build(story)

    for temp_path in temp_image_paths:
        Path(temp_path).unlink(missing_ok=True)

    return output_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a PDF score report from summary.json.")
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("output/image_scores/summary.json"),
        help="Path to summary.json produced by score_images.py.",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=Path("data/test_images"),
        help="Folder containing original (unannotated) source images.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/image_scores/saamne_salute_report.pdf"),
        help="Output PDF path.",
    )
    parser.add_argument(
        "--drill-name",
        default="Saamne Salute",
        help="Drill title shown at the top of the report.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if not args.summary.exists():
        raise FileNotFoundError(f"Summary file not found: {args.summary}")
    if not args.images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {args.images_dir}")

    pdf_path = build_report_pdf(
        summary_path=args.summary,
        images_dir=args.images_dir,
        output_pdf=args.output,
        drill_name=args.drill_name,
    )
    print(f"PDF report generated: {pdf_path}")


if __name__ == "__main__":
    main()

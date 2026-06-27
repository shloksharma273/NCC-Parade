from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DEFAULT_PERSON_ID = "1234"

IMAGE_COL_WIDTH = 2.0 * inch
SCORE_COL_WIDTH = 1.6 * inch
PARAM_COL_WIDTH = 2.4 * inch
IMAGE_MAX_HEIGHT = 2.4 * inch


def _load_results(results_path: Path) -> dict:
    with results_path.open(encoding="utf-8") as f:
        return json.load(f)


def _resolve_image_path(output_dir: Path, image_rel_path: str) -> Path | None:
    if not image_rel_path:
        return None
    image_path = output_dir / image_rel_path
    return image_path if image_path.exists() else None


def _scaled_image(image_path: Path, max_width: float, max_height: float) -> Image:
    img = Image(str(image_path))
    width_scale = max_width / img.drawWidth
    height_scale = max_height / img.drawHeight
    scale = min(width_scale, height_scale, 1.0)
    img.drawWidth *= scale
    img.drawHeight *= scale
    img.hAlign = "CENTER"
    return img


def _score_cell(rank: int, frame_index: int, total_score: float, styles) -> Paragraph:
    body = (
        f"<b>Kadam Tal #{rank}</b><br/>"
        f"Frame: {frame_index}<br/>"
        f"<b>Score: {total_score:.2f}/10</b>"
    )
    return Paragraph(body, styles["CellBody"])


def _parameter_cell(score: dict, styles) -> Paragraph:
    body = (
        f"Peak Knee Angle: {score['peak_knee_angle']:.2f}/10<br/>"
        f"Peak Foot Angle: {score['peak_foot_angle']:.2f}/10<br/>"
        f"Grounded Leg: {score['grounded_leg']:.2f}/10<br/>"
        f"Hands: {score['hands']:.2f}/10"
    )
    return Paragraph(body, styles["CellBody"])


def generate_pdf_report(
    results_path: Path,
    output_path: Path,
    output_dir: Path | None = None,
    person_id: str = DEFAULT_PERSON_ID,
) -> Path:
    results = _load_results(results_path)
    if output_dir is None:
        output_dir = results_path.parent.parent

    peak_frames = results.get("peak_frames", [])
    summary = results.get("summary", {})
    kadam_tal_count = summary.get("kadam_tal_count", len(peak_frames))
    average_score = summary.get("average_score_per_kadam_tal", 0.0)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], fontSize=22, spaceAfter=8))
    styles.add(ParagraphStyle(name="ReportMeta", parent=styles["Normal"], fontSize=11, spaceAfter=4))
    styles.add(ParagraphStyle(name="CellBody", parent=styles["Normal"], fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="HeaderCell", parent=styles["Normal"], fontSize=11, leading=14, textColor=colors.white))

    story = [
        Paragraph("Kadam Tal", styles["ReportTitle"]),
        Paragraph(f"<b>Person ID:</b> {person_id}", styles["ReportMeta"]),
        Paragraph(f"<b>Kadam Tal Count:</b> {kadam_tal_count}", styles["ReportMeta"]),
        Paragraph(f"<b>Average Score:</b> {average_score:.2f}/10", styles["ReportMeta"]),
        Spacer(1, 0.25 * inch),
    ]

    table_data = [
        [
            Paragraph("<b>Frame Image</b>", styles["HeaderCell"]),
            Paragraph("<b>Individual Score</b>", styles["HeaderCell"]),
            Paragraph("<b>Parameter Scores</b>", styles["HeaderCell"]),
        ]
    ]

    for frame in peak_frames:
        rank = frame["rank"]
        image_path = _resolve_image_path(output_dir, frame.get("output_image_path", ""))

        if image_path:
            image_cell = _scaled_image(image_path, IMAGE_COL_WIDTH, IMAGE_MAX_HEIGHT)
        else:
            image_cell = Paragraph("Image not found", styles["CellBody"])

        score_cell = _score_cell(rank, frame["frame_index"], frame["score"]["total"], styles)
        param_cell = _parameter_cell(frame["score"], styles)
        table_data.append([image_cell, score_cell, param_cell])

    table = Table(
        table_data,
        colWidths=[IMAGE_COL_WIDTH, SCORE_COL_WIDTH, PARAM_COL_WIDTH],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F5597")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story.append(table)
    doc.build(story)
    return output_path

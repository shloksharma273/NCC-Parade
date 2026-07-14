from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from drill_detection.report_metadata import ReportMetadata, drill_type_label

# Adapted from kadam_tal/report.py; only the parameter labels and step wording differ.
IMAGE_COL_WIDTH = 2.0 * inch
SCORE_COL_WIDTH = 1.6 * inch
PARAM_COL_WIDTH = 2.4 * inch
IMAGE_MAX_HEIGHT = 2.4 * inch

# --- Overall verdict / grading (single source of truth; no magic numbers in the logic) ---
# Grade band = (min average score /10, letter, label, hex colour). First match from the top wins.
GRADE_BANDS = [
    (8.5, "A+", "Outstanding", "#1B7F3B"),
    (7.0, "A", "Excellent", "#2E9E4F"),
    (5.5, "B", "Good", "#5E8C1F"),
    (4.0, "C", "Satisfactory", "#C77F1A"),
    (0.0, "D", "Needs Improvement", "#C0392B"),
]
PASS_AVERAGE_THRESHOLD = 5.0   # average score /10 required for an overall PASS
PER_STEP_STANDARD = 5.0        # a step "meets the standard" at >= this /10 AND no mandatory-gate hit


def _grade(average_score: float) -> tuple[str, str, str]:
    """Map an average score (/10) to (letter, label, hex colour) via GRADE_BANDS."""
    for threshold, letter, label, color in GRADE_BANDS:
        if average_score >= threshold:
            return letter, label, color
    return GRADE_BANDS[-1][1], GRADE_BANDS[-1][2], GRADE_BANDS[-1][3]


def _steps_meeting_standard(key_frames: list[dict]) -> int:
    """Count steps scoring >= PER_STEP_STANDARD with the mandatory raised-foot gate NOT fired."""
    return sum(
        1
        for f in key_frames
        if f.get("score", {}).get("total", 0.0) >= PER_STEP_STANDARD
        and not f.get("score", {}).get("gated", False)
    )


def _load_results(results_path: Path) -> dict:
    with results_path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_metadata(results: dict, metadata: ReportMetadata | None) -> ReportMetadata:
    if metadata is not None:
        return metadata
    raw = results.get("report_metadata")
    if isinstance(raw, dict):
        return ReportMetadata(**{k: v for k, v in raw.items() if k in ReportMetadata.__dataclass_fields__})
    return ReportMetadata(drill_type="slow_march")


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


def _header_story(metadata: ReportMetadata, styles, extra_lines: list[str]) -> list:
    title = drill_type_label(metadata.drill_type)
    lines = [
        Paragraph(title, styles["ReportTitle"]),
        Paragraph(f"<b>Cadet Name:</b> {metadata.cadet_name}", styles["ReportMeta"]),
    ]
    if metadata.cadet_id:
        lines.append(Paragraph(f"<b>Cadet ID:</b> {metadata.cadet_id}", styles["ReportMeta"]))
    lines.extend(
        [
            Paragraph(f"<b>Session ID:</b> {metadata.session_id}", styles["ReportMeta"]),
            Paragraph(f"<b>Attempt:</b> #{metadata.attempt_number}", styles["ReportMeta"]),
        ]
    )
    if metadata.recorded_at:
        lines.append(Paragraph(f"<b>Recorded At:</b> {metadata.recorded_at}", styles["ReportMeta"]))
    for line in extra_lines:
        lines.append(Paragraph(line, styles["ReportMeta"]))
    lines.append(Spacer(1, 0.25 * inch))
    return lines


def _verdict_story(summary: dict, key_frames: list[dict], styles) -> list:
    """Prominent 'Overall Assessment' banner: grade + pass/fail + headline stats."""
    iteration_count = summary.get("iteration_count", len(key_frames))
    total_score = summary.get("total_score", 0.0)
    max_score = summary.get("max_possible_score", iteration_count * 10)
    average_score = summary.get("average_score_per_step", 0.0)

    letter, label, grade_color = _grade(average_score)
    passed = average_score >= PASS_AVERAGE_THRESHOLD
    result_text = "PASS" if passed else "NEEDS IMPROVEMENT"
    result_color = "#2E9E4F" if passed else "#C0392B"
    met = _steps_meeting_standard(key_frames)

    grade_cell = Paragraph(
        f"<b>GRADE</b><br/><font size='22'>{letter}</font><br/>{label}", styles["GradeCell"]
    )
    detail_cell = Paragraph(
        f"<b>Result:</b> <font color='{result_color}'><b>{result_text}</b></font><br/>"
        f"<b>Overall Score:</b> {total_score:.1f} / {max_score} "
        f"(avg {average_score:.2f}/10)<br/>"
        f"<b>Steps Detected:</b> {iteration_count}<br/>"
        f"<b>Steps Meeting Standard:</b> {met} / {iteration_count}",
        styles["CellBody"],
    )
    banner = Table([[grade_cell, detail_cell]], colWidths=[1.9 * inch, 4.5 * inch])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(grade_color)),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F5F7FA")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return [
        Paragraph("Overall Assessment", styles["SectionHeading"]),
        Spacer(1, 0.08 * inch),
        banner,
        Spacer(1, 0.28 * inch),
    ]


def _score_cell(rank: int, frame_index: int, total_score: float, gated: bool, styles) -> Paragraph:
    gate_note = "<br/><font color='red'>(raised-foot gate)</font>" if gated else ""
    body = (
        f"<b>Step #{rank}</b><br/>"
        f"Frame: {frame_index}<br/>"
        f"<b>Score: {total_score:.2f}/10</b>{gate_note}"
    )
    return Paragraph(body, styles["CellBody"])


def _parameter_cell(score: dict, styles) -> Paragraph:
    body = (
        f"Arms Straight: {score['hands']:.2f}/10<br/>"
        f"Look Front: {score['head_front']:.2f}/10<br/>"
        f"Grounded Leg: {score['grounded_leg']:.2f}/10<br/>"
        f"Raised Foot: {score['raised_foot']:.2f}/10"
    )
    return Paragraph(body, styles["CellBody"])


def generate_pdf_report(
    results_path: Path,
    output_path: Path,
    output_dir: Path | None = None,
    metadata: ReportMetadata | None = None,
) -> Path:
    results = _load_results(results_path)
    metadata = _load_metadata(results, metadata)
    if output_dir is None:
        output_dir = results_path.parent.parent

    key_frames = results.get("peak_frames", [])
    summary = results.get("summary", {})

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
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontSize=14, spaceAfter=6, textColor=colors.HexColor("#2F5597")))
    styles.add(ParagraphStyle(name="GradeCell", parent=styles["Normal"], fontSize=12, leading=24, alignment=1, textColor=colors.white))

    # Header (cadet metadata) -> Overall Assessment banner (grade + verdict) -> per-step table.
    story = _header_story(metadata, styles, extra_lines=[])
    story += _verdict_story(summary, key_frames, styles)
    story.append(Paragraph("Per-Step Breakdown", styles["SectionHeading"]))
    story.append(Spacer(1, 0.08 * inch))

    table_data = [
        [
            Paragraph("<b>Frame Image</b>", styles["HeaderCell"]),
            Paragraph("<b>Individual Score</b>", styles["HeaderCell"]),
            Paragraph("<b>Parameter Scores</b>", styles["HeaderCell"]),
        ]
    ]

    for frame in key_frames:
        rank = frame["rank"]
        image_path = _resolve_image_path(output_dir, frame.get("output_image_path", ""))

        if image_path:
            image_cell = _scaled_image(image_path, IMAGE_COL_WIDTH, IMAGE_MAX_HEIGHT)
        else:
            image_cell = Paragraph("Image not found", styles["CellBody"])

        score = frame["score"]
        score_cell = _score_cell(rank, frame["frame_index"], score["total"], score.get("gated", False), styles)
        param_cell = _parameter_cell(score, styles)
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

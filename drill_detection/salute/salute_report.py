from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from drill_detection.report_metadata import ReportMetadata
from drill_detection.kadam_tal.report import _header_story, _scaled_image


def generate_salute_pdf_report(
    posture_analyses: list[dict],
    output_path: Path,
    output_dir: Path,
    metadata: ReportMetadata,
    average_score: float,
    score_0_100: int,
) -> Path:
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

    story = _header_story(
        metadata,
        styles,
        extra_lines=[
            f"<b>Overall Score:</b> {score_0_100}/100",
            f"<b>Average Posture Score:</b> {average_score:.2f}/10",
            f"<b>Frames Analysed:</b> {len(posture_analyses)}",
        ],
    )

    table_data = [
        [
            Paragraph("<b>Frame Image</b>", styles["HeaderCell"]),
            Paragraph("<b>Score</b>", styles["HeaderCell"]),
            Paragraph("<b>Parameters</b>", styles["HeaderCell"]),
        ]
    ]

    for item in posture_analyses:
        image_path = output_dir / item.get("output_image_path", "")
        if image_path.exists():
            image_cell = _scaled_image(image_path, 2.0 * inch, 2.4 * inch)
        else:
            image_cell = Paragraph("Image not found", styles["CellBody"])

        score_cell = Paragraph(
            f"<b>Rank #{item['rank']}</b><br/>Frame: {item['frame_index']}<br/>"
            f"<b>{item['weighted_score']:.2f}/10</b>",
            styles["CellBody"],
        )
        param_cell = Paragraph(
            f"Fingers Joined: {item['fingers_joined_score']:.2f}/10<br/>"
            f"Elbow Angle: {item['elbow_angle_deg']:.1f}° ({item['elbow_angle_score']:.2f}/10)<br/>"
            f"Heels: {item['heels_score']:.2f}/10<br/>"
            f"Left Hand: {item['left_hand_attached_score']:.2f}/10",
            styles["CellBody"],
        )
        table_data.append([image_cell, score_cell, param_cell])

    table = Table(table_data, colWidths=[2.0 * inch, 1.6 * inch, 2.4 * inch], repeatRows=1)
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

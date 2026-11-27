import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle


root = Path.cwd()
work = root / "work"
output = root / "outputs"
font = "CourseHeiti"
bold_font = "CourseHeitiBold"
pdfmetrics.registerFont(TTFont(font, os.environ.get("COURSE_HEITI_LIGHT",
    "/System/Library/Fonts/STHeiti Light.ttc"), subfontIndex=1))
pdfmetrics.registerFont(TTFont(bold_font, os.environ.get("COURSE_HEITI_BOLD",
    "/System/Library/Fonts/STHeiti Medium.ttc"), subfontIndex=1))
pdfmetrics.registerFontFamily(font, normal=font, bold=bold_font, italic=font, boldItalic=bold_font)
ink = colors.black
muted = colors.black
accent = colors.black
rule = colors.HexColor("#D2DCE1")
page_width, page_height = A4
margin = 52
width = page_width - 2 * margin
title_style = ParagraphStyle("Title", fontName=bold_font, fontSize=21, leading=30, textColor=ink, spaceAfter=12)
subtitle_style = ParagraphStyle("Status", fontName=font, fontSize=10.5, leading=16, textColor=accent, spaceAfter=13)
heading_style = ParagraphStyle("Heading", fontName=bold_font, fontSize=14, leading=22, textColor=accent,
                               spaceBefore=11, spaceAfter=5, keepWithNext=True)
subheading_style = ParagraphStyle("Subheading", parent=heading_style, fontSize=11.5, leading=19,
                                 spaceBefore=8, spaceAfter=4)
body_style = ParagraphStyle("Body", fontName=font, fontSize=10.7, leading=17.2, alignment=TA_LEFT,
                            textColor=ink, spaceAfter=5, wordWrap="CJK")
cell_style = ParagraphStyle("Cell", parent=body_style, fontSize=9.4, leading=14, spaceAfter=0)
header_style = ParagraphStyle("HeaderCell", parent=cell_style, fontName=bold_font, textColor=accent)


def paragraph(value: str) -> Paragraph:
    text = escape(value)
    for key in ("75/75", "71/75", "73/75", "69/75", "30/30", "26/30", "8.0个百分点", "84.8%", "95.2%", "4/4", "6/6",
                "3/3", "2/2", "66.6%", "47.5%", "27.1%", "12.1%", "视频处理：", "查询优化：", "批处理调度：", "二进制提取："):
        text = text.replace(key, "<b>" + key + "</b>")
    return Paragraph(text, body_style)


def heading(value: str) -> Paragraph:
    return Paragraph(escape(value), heading_style)


def subheading(value: str) -> Paragraph:
    return Paragraph(escape(value), subheading_style)


def link(label: str, address: str) -> Paragraph:
    return Paragraph(f'<link href="{escape(address)}" color="black">{escape(label)}</link>', body_style)


def table(rows: list[list[str]], column_widths: list[float]) -> LongTable:
    data = [[Paragraph(escape(str(value)), header_style if index == 0 or row[0] in {"合计", "所选配置重复"} else cell_style) for value in row]
            for index, row in enumerate(rows)]
    result = LongTable(data, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    if len(rows) <= 8:
        result.splitByRow = False
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, accent),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, rule),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return result


def draw_page(canvas, doc, footer: str) -> None:
    canvas.setStrokeColor(rule)
    canvas.setLineWidth(0.6)
    canvas.line(margin, 40, page_width - margin, 40)
    canvas.setFont(font, 8.6)
    canvas.setFillColor(muted)
    canvas.drawString(margin, 25, footer)
    canvas.drawRightString(page_width - margin, 25, str(doc.page))


def build(filename: str, title: str, items: list, *, subtitle: str = "阶段稿   ·   2026 年 11 月 4 日",
          footer: str = "智能推理与规划 · 课程作业阶段稿") -> None:
    doc = SimpleDocTemplate(str(output / filename), pagesize=A4, title=title,
                            leftMargin=margin, rightMargin=margin, topMargin=50, bottomMargin=53)
    def on_page(canvas, document):
        draw_page(canvas, document, footer)

    doc.build([Paragraph(escape(title), title_style), Paragraph(escape(subtitle), subtitle_style), *items],
              onFirstPage=on_page, onLaterPages=on_page)



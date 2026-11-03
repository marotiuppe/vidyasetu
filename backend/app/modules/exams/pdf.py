"""Report card PDF (reportlab, A4 portrait), in two layouts:

- cbse: scholastic marks per term, the annual summary, co-scholastic grades, attendance, remarks,
  the grading key and signatures.
- hpc: the same marks, then one table per configured aspect section, a progress-across-terms
  table, and blank areas for the student's self-reflection and the parent's comment. It is
  labelled as the school's own layout.

Fonts and the logo come from the fee receipt module (Noto Sans and Noto Sans Devanagari, so
Marathi and Hindi names print correctly). Figures are formatted from Decimal; nothing is rounded
through float.
"""

import io
import textwrap
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from app.modules.exams.report_schemas import (
    AnnualOut,
    ReportOut,
    SubjectTermOut,
    TermReportOut,
)
from app.modules.exams.schemas import BandOut
from app.modules.fees.receipt import _draw_logo, _font_name, _text

WIDTH, HEIGHT = A4
LEFT = 14 * mm
RIGHT = WIDTH - 14 * mm
BOTTOM = 18 * mm
TOP = HEIGHT - 14 * mm
ROW = 6 * mm
Align = Literal["left", "center", "right"]

_ASPECT_LABELS = {
    "co_curricular": "Co-curricular activities",
    "behavioural": "Behavioural and attitude",
    "self_awareness": "Self-awareness",
    "health": "Health and wellness",
}


def _pct(value: Decimal | None) -> str:
    return "-" if value is None else f"{value:.2f}%"


def _num(value: Decimal | None) -> str:
    """A mark without trailing zeros: 38, 38.5 or 38.25."""
    return "-" if value is None else format(value.normalize(), "f")


def _fit(text: str, size: float, bold: bool, max_width: float) -> str:
    """Shorten text with an ellipsis so it fits one table cell."""
    if pdfmetrics.stringWidth(text, _font_name(text, bold), size) <= max_width:
        return text
    cut = text
    while cut and pdfmetrics.stringWidth(cut + "...", _font_name(cut, bold), size) > max_width:
        cut = cut[:-1]
    return cut + "..."


class _Sheet:
    """Writes down the page and starts a new one when the space runs out."""

    def __init__(self, c: Canvas) -> None:
        self.c = c
        self.y = TOP

    def need(self, space: float) -> None:
        if self.y - space < BOTTOM:
            self.c.showPage()
            self.y = TOP
            _text(self.c, LEFT, self.y, "Report card (continued)", 8)
            self.y -= 6 * mm

    def line(self, text: str, size: float = 9, *, bold: bool = False, gap: float = 5 * mm) -> None:
        self.need(gap)
        _text(self.c, LEFT, self.y, text, size, bold=bold)
        self.y -= gap

    def heading(self, text: str) -> None:
        self.need(12 * mm)
        self.y -= 2 * mm
        _text(self.c, LEFT, self.y, text, 11, bold=True)
        self.y -= 2 * mm
        self.c.setStrokeColorRGB(0.6, 0.6, 0.6)
        self.c.line(LEFT, self.y, RIGHT, self.y)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.y -= 5 * mm

    def row(
        self,
        cells: Sequence[tuple[str, float, str]],
        *,
        size: float = 8.5,
        bold: bool = False,
        shade: bool = False,
    ) -> None:
        self.need(ROW)
        x = LEFT
        if shade:
            self.c.setFillColorRGB(0.93, 0.93, 0.93)
            self.c.rect(LEFT, self.y - 1.5 * mm, RIGHT - LEFT, ROW, stroke=0, fill=1)
            self.c.setFillColorRGB(0, 0, 0)
        for text, width, align in cells:
            safe = _fit(text, size, bold, width * mm - 2 * mm)
            x_pos = {
                "left": x + 1 * mm,
                "center": x + width * mm / 2,
                "right": x + width * mm - 1 * mm,
            }[align]
            if align == "center":
                _text(self.c, x_pos, self.y, safe, size, bold=bold, align="center")
            elif align == "right":
                _text(self.c, x_pos, self.y, safe, size, bold=bold, align="right")
            else:
                _text(self.c, x_pos, self.y, safe, size, bold=bold)
            x += width * mm
        self.c.setStrokeColorRGB(0.8, 0.8, 0.8)
        self.c.line(LEFT, self.y - 1.5 * mm, RIGHT, self.y - 1.5 * mm)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.y -= ROW

    def paragraph(self, text: str, size: float = 8.5, width_chars: int = 115) -> None:
        for part in text.splitlines() or [""]:
            for line in textwrap.wrap(part, width_chars) or [""]:
                self.line(line, size, gap=4.5 * mm)


def _grade_text(grade: str | None, point: Decimal | None) -> str:
    if grade is None:
        return "-"
    return grade if point is None else f"{grade} ({point:.1f})"


def _result_text(result: str | None) -> str:
    return {"pass": "PASS", "fail": "FAIL"}.get(result or "", "-")


def _exam_columns(term: TermReportOut) -> list[str]:
    names: list[str] = []
    for subject in term.subjects:
        for entry in subject.exams:
            if entry.name not in names:
                names.append(entry.name)
    return names


def _mark_cell(subject: SubjectTermOut, exam_name: str) -> str:
    for entry in subject.exams:
        if entry.name == exam_name:
            if entry.absent:
                return "AB"
            if entry.marks is None:
                return "-"
            return f"{_num(entry.marks)}/{entry.max_marks}"
    return "-"


def _term_table(sheet: _Sheet, term: TermReportOut) -> None:
    exams = _exam_columns(term)
    subject_w = 46.0
    fixed = [18.0, 14.0, 18.0]
    room = 182.0 - subject_w - sum(fixed)
    exam_w = min(26.0, room / len(exams)) if exams else 0.0
    sheet.heading(f"{term.name}  (weight {term.weight_percent}%)")
    header: list[tuple[str, float, Align]] = [("Subject", subject_w, "left")]
    header += [(name, exam_w, "center") for name in exams]
    header += [
        ("Term %", fixed[0], "right"),
        ("Grade", fixed[1], "center"),
        ("Result", fixed[2], "center"),
    ]
    sheet.row(header, bold=True, shade=True, size=8)
    for subject in term.subjects:
        cells: list[tuple[str, float, Align]] = [(subject.name, subject_w, "left")]
        cells += [(_mark_cell(subject, name), exam_w, "center") for name in exams]
        cells += [
            (_pct(subject.percent), fixed[0], "right"),
            (subject.grade or "-", fixed[1], "center"),
            (_result_text(subject.result), fixed[2], "center"),
        ]
        sheet.row(cells)
    total = f"Term total {_pct(term.total)}   Grade {_grade_text(term.grade, term.grade_point)}"
    total += f"   Result {_result_text(term.result)}"
    if term.rank is not None:
        total += f"   Rank {term.rank}"
    sheet.line(total, 9, bold=True)
    if term.band_remark:
        sheet.line(f"Remark: {term.band_remark}", 8.5)
    if not term.complete:
        sheet.line("Some marks for this term are not entered yet.", 8)


def _annual_table(sheet: _Sheet, annual: AnnualOut) -> None:
    sheet.heading(
        "Annual summary" + ("" if annual.term_weighting == "weighted" else "  (equal term weights)")
    )
    sheet.row(
        [
            ("Subject", 110.0, "left"),
            ("Annual %", 30.0, "right"),
            ("Grade", 20.0, "center"),
            ("Result", 22.0, "center"),
        ],
        bold=True,
        shade=True,
        size=8,
    )
    for subject in annual.subjects:
        sheet.row(
            [
                (subject.name, 110.0, "left"),
                (_pct(subject.percent), 30.0, "right"),
                (subject.grade or "-", 20.0, "center"),
                (_result_text(subject.result), 22.0, "center"),
            ]
        )
    summary = (
        f"Annual total {_pct(annual.total)}   Grade {_grade_text(annual.grade, annual.grade_point)}"
    )
    summary += f"   Result {_result_text(annual.result)}"
    if annual.rank is not None:
        summary += f"   Rank {annual.rank}"
    sheet.line(summary, 9, bold=True)


def _aspect_rows(sheet: _Sheet, report: ReportOut, sections: list[str] | None) -> None:
    """One row per aspect, one column per term (grade and remark under the grade)."""
    terms = report.terms
    aspects: dict[int, tuple[str, str]] = {}
    for term in terms:
        for a in term.aspects:
            if sections is None or a.section.value in sections:
                aspects.setdefault(a.aspect_id, (a.section.value, a.name))
    if not aspects:
        sheet.line("No aspects are recorded.", 8.5)
        return
    name_w = 80.0
    term_w = min(34.0, (182.0 - name_w) / max(len(terms), 1))
    sheet.row(
        [("Aspect", name_w, "left")] + [(t.name, term_w, "center") for t in terms],
        bold=True,
        shade=True,
        size=8,
    )
    for aspect_id, (_, name) in aspects.items():
        cells: list[tuple[str, float, Align]] = [(name, name_w, "left")]
        for term in terms:
            found = next((a for a in term.aspects if a.aspect_id == aspect_id), None)
            grade = found.grade if found and found.grade else "-"
            cells.append((grade, term_w, "center"))
        sheet.row(cells)


def _grading_key(sheet: _Sheet, grading: list[BandOut], pass_percent: int) -> None:
    parts = []
    bands = sorted(grading, key=lambda b: b.min_percent, reverse=True)
    for index, band in enumerate(bands):
        upper = 100 if index == 0 else bands[index - 1].min_percent - 1
        point = "" if band.grade_point is None else f" ({band.grade_point:.1f})"
        parts.append(f"{band.grade}: {band.min_percent}-{upper}%{point}")
    sheet.need(16 * mm)
    sheet.line("Grading key", 8.5, bold=True, gap=4.5 * mm)
    sheet.paragraph("   ".join(parts) + f"   Pass mark: {pass_percent}% in each subject.", 8)


def _signatures(sheet: _Sheet, principal: str | None) -> None:
    sheet.need(32 * mm)
    sheet.y -= 14 * mm
    column = (RIGHT - LEFT) / 3
    labels = [("Class teacher", None), ("Principal", principal), ("Parent / guardian", None)]
    for index, (label, name) in enumerate(labels):
        x = LEFT + column * index + 4 * mm
        sheet.c.line(x, sheet.y, x + column - 12 * mm, sheet.y)
        _text(sheet.c, x, sheet.y - 4 * mm, label, 8.5, bold=True)
        if name:
            _text(sheet.c, x, sheet.y - 8 * mm, _fit(name, 8, False, column - 16 * mm), 8)
    sheet.y -= 14 * mm


def build_report_pdf(
    report: ReportOut, logo_png: bytes | None, layout: Literal["cbse", "hpc"]
) -> bytes:
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)
    title = "HOLISTIC PROGRESS CARD" if layout == "hpc" else "REPORT CARD"
    c.setTitle(f"{title} {report.academic_year_name}")
    c.setAuthor(report.school_name[:60])
    sheet = _Sheet(c)

    _draw_logo(c, logo_png, LEFT, TOP - 2 * mm)
    centre = WIDTH / 2
    sheet.y = TOP - 2 * mm
    _text(c, centre, sheet.y, report.school_name[:70], 15, bold=True, align="center")
    sheet.y -= 6 * mm
    _text(c, centre, sheet.y, report.branch_name[:70], 10, align="center")
    sheet.y -= 6 * mm
    _text(
        c,
        centre,
        sheet.y,
        f"{title}  |  Academic year {report.academic_year_name}",
        10,
        bold=True,
        align="center",
    )
    sheet.y -= 4 * mm
    c.line(LEFT, sheet.y, RIGHT, sheet.y)
    sheet.y -= 7 * mm

    left_pairs = [
        ("Student name", report.student.name),
        ("Admission no", report.student.admission_no),
        (
            "Class / section",
            " - ".join(x for x in (report.class_name, report.section_name) if x) or "-",
        ),
        ("Roll no", "-" if report.roll_no is None else str(report.roll_no)),
    ]
    right_pairs = [
        ("Date of birth", report.student.date_of_birth.strftime("%d-%m-%Y")),
        ("Guardian", report.student.guardian_name or "-"),
        ("Branch", report.branch_name or "-"),
        ("Pass mark", f"{report.pass_percent}%"),
    ]
    for (l_label, l_value), (r_label, r_value) in zip(left_pairs, right_pairs, strict=True):
        _text(c, LEFT, sheet.y, l_label, 8.5)
        _text(c, LEFT + 32 * mm, sheet.y, _fit(l_value, 9, True, 58 * mm), 9, bold=True)
        _text(c, LEFT + 100 * mm, sheet.y, r_label, 8.5)
        _text(c, LEFT + 132 * mm, sheet.y, _fit(r_value, 9, True, 52 * mm), 9, bold=True)
        sheet.y -= 5.5 * mm

    if layout == "hpc":
        sheet.line(
            "School-defined holistic progress card. Sections and wording vary by school.",
            7.5,
            gap=5 * mm,
        )
    sheet.heading("Scholastic")
    for term in report.terms:
        _term_table(sheet, term)
    if report.annual is not None:
        _annual_table(sheet, report.annual)

    if layout == "cbse":
        sheet.heading("Co-scholastic and aspects")
        _aspect_rows(sheet, report, [s.value for s in report.aspect_sections] or None)
    else:
        for section in report.aspect_sections:
            sheet.heading(_ASPECT_LABELS.get(section.value, section.value))
            _aspect_rows(sheet, report, [section.value])
        sheet.heading("Progress across terms")
        sheet.row(
            [
                ("Term", 90.0, "left"),
                ("Total %", 40.0, "right"),
                ("Grade", 26.0, "center"),
                ("Rank", 26.0, "center"),
            ],
            bold=True,
            shade=True,
            size=8,
        )
        for term in report.terms:
            sheet.row(
                [
                    (term.name, 90.0, "left"),
                    (_pct(term.total), 40.0, "right"),
                    (_grade_text(term.grade, None), 26.0, "center"),
                    ("-" if term.rank is None else str(term.rank), 26.0, "center"),
                ]
            )
        sheet.heading("Self-reflection and parent comment")
        for label in ("Student's self-reflection", "Parent's comment"):
            sheet.line(label, 8.5, bold=True, gap=5 * mm)
            sheet.need(24 * mm)
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.rect(LEFT, sheet.y - 20 * mm, RIGHT - LEFT, 20 * mm, stroke=1, fill=0)
            c.setStrokeColorRGB(0, 0, 0)
            sheet.y -= 25 * mm

    if report.attendance is not None:
        att = report.attendance
        sheet.heading("Attendance")
        sheet.line(
            f"Present {att.present} of {att.marked_days} recorded days"
            + ("" if att.percentage is None else f"  ({_pct(att.percentage)})"),
            9,
        )

    remarks = [(t.name, t.teacher_remark) for t in report.terms if t.teacher_remark]
    if remarks:
        sheet.heading("Remarks")
        for name, text in remarks:
            sheet.paragraph(f"{name}: {text}")

    sheet.heading("Grading")
    _grading_key(sheet, report.grading, report.pass_percent)
    _signatures(sheet, report.principal_name)

    footer = report.footer or ""
    if footer:
        _text(c, centre, BOTTOM - 4 * mm, _fit(footer, 8, False, RIGHT - LEFT), 8, align="center")
    _text(
        c,
        centre,
        BOTTOM - 8 * mm,
        "This is a computer generated report card. Figures are worked out from the marks "
        "recorded by the school.",
        7,
        align="center",
    )
    c.showPage()
    c.save()
    return buf.getvalue()

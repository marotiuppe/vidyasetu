"""One-page payment receipt PDF (reportlab).

Text is set in bundled fonts under SIL OFL (see fonts/): Noto Sans for Latin text and Noto Sans
Devanagari for any text with Devanagari (Marathi or Hindi names). Devanagari needs shaping
(conjuncts, matras, reph), which ReportLab does with uharfbuzz.
"""

import io
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

FONT_DIR = Path(__file__).resolve().parent / "fonts"
RUPEE_SIGN = "₹"
_LATIN = "NotoSans"
_LATIN_BOLD = "NotoSans-Bold"
_DEVA = "NotoSansDevanagari"
_DEVA_BOLD = "NotoSansDevanagari-Bold"
_FONT_FILES = {
    _LATIN: "NotoSans-Regular.ttf",
    _LATIN_BOLD: "NotoSans-Bold.ttf",
    _DEVA: "NotoSansDevanagari-Regular.ttf",
    _DEVA_BOLD: "NotoSansDevanagari-Bold.ttf",
}
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _register_fonts() -> None:
    """Register the bundled TrueType fonts once. A missing file fails at import, not on print."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, filename in _FONT_FILES.items():
        if name not in registered:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))


_register_fonts()


def _font_name(text: str, bold: bool) -> str:
    if _DEVANAGARI.search(text):
        return _DEVA_BOLD if bold else _DEVA
    return _LATIN_BOLD if bold else _LATIN


def _text(
    c: Canvas,
    x: float,
    y: float,
    text: str,
    size: float,
    *,
    bold: bool = False,
    align: Literal["left", "center", "right"] = "left",
) -> None:
    c.setFont(_font_name(text, bold), size)
    if align == "center":
        c.drawCentredString(x, y, text)
    elif align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawString(x, y, text)


def rupees(paise: int) -> str:
    """Format integer paise as e.g. '₹ 12,34,567.50' (Indian digit grouping)."""
    whole, frac = divmod(abs(paise), 100)
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    sign = "-" if paise < 0 else ""
    return f"{sign}{RUPEE_SIGN} {digits}.{frac:02d}"


def _fmt_date(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def _draw_logo(c: Canvas, png: bytes | None, x: float, top: float) -> None:
    """Draw the school logo top-left (max 18 mm high); a bad logo is skipped, never fatal."""
    if not png:
        return
    try:
        reader = ImageReader(io.BytesIO(png))
        iw, ih = reader.getSize()
        if iw <= 0 or ih <= 0:
            return
        scale = min(18 * mm / ih, 26 * mm / iw)
        w, h = iw * scale, ih * scale
        c.drawImage(reader, x, top - h, width=w, height=h, mask="auto")
    except Exception:  # noqa: BLE001 - a bad logo must never break the receipt
        return


def build_receipt_pdf(d: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    width, height = A5
    c = Canvas(buf, pagesize=A5)
    c.setTitle(f"Receipt {d['receipt_no']}")
    margin = 12 * mm
    c.setLineWidth(1)
    c.rect(margin / 2, margin / 2, width - margin, height - margin)

    _draw_logo(c, d.get("logo_png"), margin, height - margin - 2 * mm)

    y = height - margin - 4 * mm
    _text(c, width / 2, y, str(d["school_name"])[:60], 15, bold=True, align="center")
    y -= 7 * mm
    _text(c, width / 2, y, "FEE RECEIPT", 10, align="center")
    y -= 4 * mm
    c.line(margin, y, width - margin, y)
    y -= 8 * mm

    class_label = " - ".join(x for x in (d["class_name"], d["section_name"]) if x) or "-"
    method = str(d["method"]).upper()
    if d["reference"]:
        method += f"  ref: {d['reference']}"
    rows = [
        ("Receipt no", d["receipt_no"]),
        ("Date", _fmt_date(d["paid_on"])),
        ("Student", d["student_name"]),
        ("Admission no", d["admission_no"]),
        ("Class / Section", class_label),
        ("Invoice", f"{d['invoice_no']}  ({d['invoice_title']})"),
        ("Payment method", method),
        ("Received by", d["received_by"]),
    ]
    for label, value in rows:
        _text(c, margin, y, label, 9)
        _text(c, margin + 38 * mm, y, str(value)[:48], 10, bold=True)
        y -= 6.5 * mm

    y -= 2 * mm
    c.line(margin, y, width - margin, y)
    y -= 9 * mm
    _text(c, margin, y, "Amount received", 12, bold=True)
    _text(c, width - margin, y, rupees(d["amount_paise"]), 12, bold=True, align="right")
    y -= 8 * mm
    for label, key in (
        ("Invoice total (after discount)", "invoice_total_paise"),
        ("Paid so far on this invoice", "paid_so_far_paise"),
        ("Balance", "balance_paise"),
    ):
        _text(c, margin, y, label, 9)
        _text(c, width - margin, y, rupees(d[key]), 9, align="right")
        y -= 5.5 * mm
    if d["note"]:
        y -= 2 * mm
        _text(c, margin, y, f"Note: {str(d['note'])[:70]}", 9)

    if d["reversed"]:
        c.saveState()
        c.setFillColorRGB(0.8, 0.1, 0.1)
        c.translate(width / 2, height / 2 - 10 * mm)
        c.rotate(25)
        _text(c, 0, 0, "REVERSED", 44, bold=True, align="center")
        if d["reversed_reason"]:
            _text(c, 0, -8 * mm, str(d["reversed_reason"])[:60], 10, align="center")
        c.restoreState()

    c.setFillColorRGB(0.4, 0.4, 0.4)
    if d.get("footer"):
        _text(c, width / 2, margin + 5 * mm, str(d["footer"])[:150], 8, align="center")
    _text(c, width / 2, margin, "This is a computer generated receipt.", 8, align="center")
    c.showPage()
    c.save()
    return buf.getvalue()

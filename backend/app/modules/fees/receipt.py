"""One-page payment receipt PDF (reportlab, pure Python)."""

import io
from datetime import date
from typing import Any

from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


def rupees(paise: int) -> str:
    """Format integer paise as e.g. 'Rs. 12,34,567.50' (Indian digit grouping)."""
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
    return f"{sign}Rs. {digits}.{frac:02d}"


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
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, y, str(d["school_name"])[:60])
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, y, "FEE RECEIPT")
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
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, label)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 38 * mm, y, str(value)[:48])
        y -= 6.5 * mm

    y -= 2 * mm
    c.line(margin, y, width - margin, y)
    y -= 9 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Amount received")
    c.drawRightString(width - margin, y, rupees(d["amount_paise"]))
    y -= 8 * mm
    c.setFont("Helvetica", 9)
    for label, key in (
        ("Invoice total (after discount)", "invoice_total_paise"),
        ("Paid so far on this invoice", "paid_so_far_paise"),
        ("Balance", "balance_paise"),
    ):
        c.drawString(margin, y, label)
        c.drawRightString(width - margin, y, rupees(d[key]))
        y -= 5.5 * mm
    if d["note"]:
        y -= 2 * mm
        c.drawString(margin, y, f"Note: {str(d['note'])[:70]}")

    if d["reversed"]:
        c.saveState()
        c.setFillColorRGB(0.8, 0.1, 0.1)
        c.translate(width / 2, height / 2 - 10 * mm)
        c.rotate(25)
        c.setFont("Helvetica-Bold", 44)
        c.drawCentredString(0, 0, "REVERSED")
        c.setFont("Helvetica", 10)
        if d["reversed_reason"]:
            c.drawCentredString(0, -8 * mm, str(d["reversed_reason"])[:60])
        c.restoreState()

    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont("Helvetica", 8)
    if d.get("footer"):
        c.drawCentredString(width / 2, margin + 5 * mm, str(d["footer"])[:150])
    c.drawCentredString(width / 2, margin, "This is a computer generated receipt.")
    c.showPage()
    c.save()
    return buf.getvalue()

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QFont, QFontMetricsF, QPainter, QPageLayout, QPageSize, QPen
from PySide6.QtPrintSupport import QPrinter


@dataclass(frozen=True)
class VaccineLabelContent:
    """The minimum operator-selected data rendered on a single vaccine label."""

    vaccine_name: str
    patient_name: str
    chart_no: str
    resident_id: str
    phone: str
    printed_at: datetime
    count_summary: str = ""
    influenza_total_today: int | None = None


@dataclass(frozen=True)
class VaccineLabelPrintResult:
    success: bool
    message: str


def print_vaccine_label(
    content: VaccineLabelContent,
    *,
    printer_name: str,
) -> VaccineLabelPrintResult:
    """Render one 80 x 40 mm vaccine label through the Windows print spooler.

    This intentionally has no logging: label data contains patient identifiers.
    """

    normalized_printer_name = printer_name.strip()
    if not normalized_printer_name:
        return VaccineLabelPrintResult(False, "Vaccine label printer is not configured.")

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(normalized_printer_name)
    printer.setOutputFormat(QPrinter.OutputFormat.NativeFormat)
    printer.setFullPage(True)
    printer.setPageSize(
        QPageSize(QSizeF(80.0, 40.0), QPageSize.Unit.Millimeter)
    )
    printer.setPageMargins(
        QMarginsF(0.0, 0.0, 0.0, 0.0),
        QPageLayout.Unit.Millimeter,
    )
    if not printer.isValid():
        return VaccineLabelPrintResult(False, "Vaccine label printer is unavailable.")

    painter = QPainter()
    if not painter.begin(printer):
        return VaccineLabelPrintResult(False, "Vaccine label printing failed.")
    try:
        _paint_vaccine_label(
            painter,
            QRectF(printer.pageRect(QPrinter.Unit.DevicePixel)),
            content,
        )
    except Exception:
        return VaccineLabelPrintResult(False, "Vaccine label printing failed.")
    finally:
        painter.end()
    return VaccineLabelPrintResult(True, "Vaccine label printed.")


def _paint_vaccine_label(
    painter: QPainter,
    rect: QRectF,
    content: VaccineLabelContent,
) -> None:
    """Reuse the legacy Labeler visual hierarchy without rendering a UI widget."""

    margin = rect.width() * 0.07
    inner = rect.adjusted(margin, margin, -margin, -margin)
    pen = QPen(Qt.GlobalColor.black)
    pen.setWidthF(max(1.0, rect.width() / 450.0))
    painter.setPen(pen)

    _draw_label_text(
        painter,
        QRectF(inner.left(), inner.top(), inner.width() * 0.55, inner.height() * 0.15),
        (
            f"{content.printed_at.year}년{content.printed_at.month}월"
            f"{content.printed_at.day}일"
        ),
        rect.height() / 10.0,
        alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    _draw_label_text(
        painter,
        QRectF(inner.left() + inner.width() * 0.55, inner.top(), inner.width() * 0.45, inner.height() * 0.15),
        content.count_summary,
        rect.height() / 10.0,
        alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )

    top_line = inner.top() + inner.height() * 0.18
    bottom_line = inner.top() + inner.height() * 0.66
    painter.drawLine(inner.left(), top_line, inner.right(), top_line)
    painter.drawLine(inner.left(), bottom_line, inner.right(), bottom_line)

    padding = rect.height() * 0.025
    _draw_vaccine_title(
        painter,
        QRectF(inner.left(), top_line + padding, inner.width(), bottom_line - top_line - 2 * padding),
        content.vaccine_name,
        rect.height() / 4.9,
    )

    patient_text = " ".join(
        part for part in (content.patient_name, content.chart_no) if part
    )
    lower_height = inner.bottom() - bottom_line
    _draw_label_text(
        painter,
        QRectF(inner.left(), bottom_line, inner.width() * 0.45, lower_height * 0.5),
        patient_text,
        rect.height() / 11.0,
        alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    _draw_label_text(
        painter,
        QRectF(inner.left() + inner.width() * 0.5, bottom_line, inner.width() * 0.5, lower_height * 0.5),
        content.resident_id,
        rect.height() / 11.0,
        alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )
    footer_top = bottom_line + lower_height * 0.5
    if content.influenza_total_today is not None:
        _draw_label_text(
            painter,
            QRectF(inner.left(), footer_top, inner.width() * 0.49, lower_height * 0.5),
            f"오늘 총 독감: {content.influenza_total_today}",
            rect.height() / 14.0,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
    _draw_label_text(
        painter,
        QRectF(inner.left() + inner.width() * 0.51, footer_top, inner.width() * 0.49, lower_height * 0.5),
        content.phone,
        rect.height() / 11.0,
        alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )


def _draw_vaccine_title(painter: QPainter, rect: QRectF, text: str, pixel_size: float) -> None:
    manufacturers = {"코로나.화이자": "화이자", "코로나.모더나": "모더나"}
    manufacturer = manufacturers.get(text)
    if manufacturer is None:
        _draw_label_text(painter, rect, text, pixel_size, bold=True)
        return

    title_size = min(pixel_size, rect.height() * 0.64)
    _draw_label_text(
        painter,
        QRectF(rect.left(), rect.top(), rect.width() * 0.43, rect.height()),
        "코로나",
        title_size,
        bold=True,
    )
    pill = QRectF(
        rect.left() + rect.width() * 0.46, rect.top(), rect.width() * 0.54, rect.height()
    )
    filled = manufacturer == "모더나"
    painter.save()
    try:
        pen = QPen(Qt.GlobalColor.black)
        pen.setWidthF(max(1.0, rect.height() * 0.018))
        painter.setPen(pen)
        painter.setBrush(Qt.GlobalColor.black if filled else Qt.GlobalColor.white)
        painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)
        painter.setPen(Qt.GlobalColor.white if filled else Qt.GlobalColor.black)
        inset = rect.height() * 0.14
        _draw_label_text(
            painter, pill.adjusted(inset, inset, -inset, -inset), manufacturer,
            title_size, bold=True,
        )
    finally:
        painter.restore()


def _draw_label_text(
    painter: QPainter,
    rect: QRectF,
    text: str,
    pixel_size: float,
    *,
    bold: bool = False,
    alignment=Qt.AlignmentFlag.AlignCenter,
) -> None:
    if not text:
        return
    flags = alignment | Qt.TextFlag.TextSingleLine
    font = _label_font(pixel_size, bold=bold)
    # Measure on the same device as the print job, including its DPI/font metrics.
    lower, upper = 1, font.pixelSize()
    fitted_size = 1
    while lower <= upper:
        size = (lower + upper) // 2
        font.setPixelSize(size)
        bounds = QFontMetricsF(font, painter.device()).boundingRect(rect, int(flags), text)
        if bounds.width() <= rect.width() and bounds.height() <= rect.height():
            fitted_size = size
            lower = size + 1
        else:
            upper = size - 1
    font.setPixelSize(fitted_size)
    painter.setFont(font)
    painter.drawText(rect, flags, text)


def _label_font(pixel_size: float, *, bold: bool = False) -> QFont:
    """Use painter-coordinate pixels so high-DPI thermal drivers do not enlarge text."""

    font = QFont("Malgun Gothic")
    font.setPixelSize(max(1, round(pixel_size)))
    font.setBold(bold)
    return font

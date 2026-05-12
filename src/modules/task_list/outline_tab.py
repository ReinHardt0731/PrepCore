from __future__ import annotations

import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, replace
from io import BytesIO
from pathlib import Path

from PySide6.QtCore import (
    QBuffer,
    QByteArray,
    QEvent,
    QObject,
    QRunnable,
    QRectF,
    QSignalBlocker,
    QSize,
    QThreadPool,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextListFormat,
    QTextLength,
    QTransform,
    QTextTableFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFontComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QSlider,
    QSpinBox,
    QStyle,
    QSizePolicy,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.tree_font_utils import TreeFontConfig, apply_font_to_item, apply_hierarchical_font_to_item


EQUATION_FOREGROUND_COLOR = "#edf4ff"
EQUATION_TEXT_STYLE = (
    "font-family: 'Cambria Math', 'STIX Two Math', 'Times New Roman', serif;"
    f"color: {EQUATION_FOREGROUND_COLOR};"
)
NOTEBOOK_AUTOSAVE_DELAY_MS = 450
LATEX_AUTO_RECHECK_DELAY_SECONDS = 45
MATH_DELIMITER_PAIRS = (
    ("$$", "$$"),
    (r"\[", r"\]"),
    (r"\(", r"\)"),
    ("$", "$"),
)
EQUATION_COMMAND_MAP = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "delta": "delta",
    "theta": "theta",
    "lambda": "lambda",
    "mu": "mu",
    "pi": "pi",
    "sigma": "sigma",
    "phi": "phi",
    "omega": "omega",
    "Delta": "Delta",
    "Gamma": "Gamma",
    "Lambda": "Lambda",
    "Omega": "Omega",
    "Pi": "Pi",
    "Sigma": "Sigma",
    "Phi": "Phi",
    "infty": "infty",
    "int": "int",
    "oint": "oint",
    "sum": "sum",
    "prod": "prod",
    "pm": "pm",
    "times": "times",
    "div": "div",
    "neq": "neq",
    "leq": "leq",
    "geq": "geq",
    "approx": "approx",
    "rightarrow": "rightarrow",
    "leftarrow": "leftarrow",
}
EQUATION_SYMBOL_MAP = {
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "sigma": "σ",
    "phi": "φ",
    "omega": "ω",
    "Delta": "Δ",
    "Gamma": "Γ",
    "Lambda": "Λ",
    "Omega": "Ω",
    "Pi": "Π",
    "Sigma": "Σ",
    "Phi": "Φ",
    "infty": "∞",
    "int": "∫",
    "oint": "∮",
    "sum": "∑",
    "prod": "∏",
    "pm": "±",
    "times": "×",
    "div": "÷",
    "neq": "≠",
    "leq": "≤",
    "geq": "≥",
    "approx": "≈",
    "rightarrow": "→",
    "leftarrow": "←",
}
EQUATION_OPERATOR_COMMANDS = {"int", "oint", "sum", "prod"}


@dataclass(frozen=True)
class EquationRenderOptions:
    font_size: int = 20
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass(frozen=True)
class EquationMetadata:
    latex: str
    font_size: int = 20
    bold: bool = False
    italic: bool = False
    underline: bool = False

    def to_render_options(self) -> EquationRenderOptions:
        return EquationRenderOptions(
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
        )


@dataclass(frozen=True)
class EquationRenderPayload:
    image_html: str
    backend_name: str
    diagnostic: str = ""


@dataclass(frozen=True)
class NotebookCellMetadata:
    cell_id: str
    cell_type: str
    source: str
    rendered_html: str = ""
    is_editing: bool = False
    diagram_settings: "DiagramSettings | None" = None


@dataclass(frozen=True)
class DiagramTextStyle:
    font_family: str = ""
    font_size_pt: int = 12
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: str = "#edf4ff"

    def to_dict(self) -> dict[str, object]:
        return {
            "font_family": self.font_family,
            "font_size_pt": self.font_size_pt,
            "bold": self.bold,
            "italic": self.italic,
            "underline": self.underline,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, payload: object, *, defaults: "DiagramTextStyle") -> "DiagramTextStyle":
        if not isinstance(payload, dict):
            return defaults
        return cls(
            font_family=str(payload.get("font_family", defaults.font_family)),
            font_size_pt=max(8, int(payload.get("font_size_pt", defaults.font_size_pt))),
            bold=bool(payload.get("bold", defaults.bold)),
            italic=bool(payload.get("italic", defaults.italic)),
            underline=bool(payload.get("underline", defaults.underline)),
            color=str(payload.get("color", defaults.color)),
        )

    def resolved_font(self) -> QFont:
        font = QApplication.font()
        if self.font_family.strip():
            font.setFamily(self.font_family.strip())
        font.setPointSize(max(8, int(self.font_size_pt)))
        font.setBold(self.bold)
        font.setItalic(self.italic)
        font.setUnderline(self.underline)
        return font

    def resolved_color(self) -> QColor:
        color = QColor(self.color)
        return color if color.isValid() else QColor("#edf4ff")


@dataclass(frozen=True)
class TimelineDiagramStyle:
    title_style: DiagramTextStyle = field(
        default_factory=lambda: DiagramTextStyle(
            font_size_pt=12,
            bold=True,
            color="#edf4ff",
        )
    )
    detail_style: DiagramTextStyle = field(
        default_factory=lambda: DiagramTextStyle(
            font_size_pt=10,
            color="#93a8c7",
        )
    )
    row_gap_px: int = 28
    column_gap_px: int = 28

    def to_dict(self) -> dict[str, object]:
        return {
            "title_style": self.title_style.to_dict(),
            "detail_style": self.detail_style.to_dict(),
            "row_gap_px": self.row_gap_px,
            "column_gap_px": self.column_gap_px,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "TimelineDiagramStyle":
        defaults = cls()
        if not isinstance(payload, dict):
            return defaults
        return cls(
            title_style=DiagramTextStyle.from_dict(
                payload.get("title_style"),
                defaults=defaults.title_style,
            ),
            detail_style=DiagramTextStyle.from_dict(
                payload.get("detail_style"),
                defaults=defaults.detail_style,
            ),
            row_gap_px=max(12, int(payload.get("row_gap_px", defaults.row_gap_px))),
            column_gap_px=max(12, int(payload.get("column_gap_px", defaults.column_gap_px))),
        )


@dataclass(frozen=True)
class TreeDiagramLayout:
    node_positions: dict[str, dict[str, float]] = field(default_factory=dict)
    auto_layout_direction: str = "vertical"

    def to_dict(self) -> dict[str, object]:
        return {
            "node_positions": self.node_positions,
            "auto_layout_direction": self.auto_layout_direction,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "TreeDiagramLayout":
        defaults = cls()
        if not isinstance(payload, dict):
            return defaults
        normalized_positions: dict[str, dict[str, float]] = {}
        raw_positions = payload.get("node_positions", {})
        if isinstance(raw_positions, dict):
            for key, value in raw_positions.items():
                if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
                    continue
                x = value.get("x")
                y = value.get("y")
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    normalized_positions[key] = {"x": float(x), "y": float(y)}
        direction = str(payload.get("auto_layout_direction", defaults.auto_layout_direction)).strip() or "vertical"
        return cls(node_positions=normalized_positions, auto_layout_direction=direction)


@dataclass(frozen=True)
class DiagramSettings:
    display_height_px: int | None = None
    timeline_style: TimelineDiagramStyle = field(default_factory=TimelineDiagramStyle)
    tree_layout: TreeDiagramLayout = field(default_factory=TreeDiagramLayout)

    def to_dict(self) -> dict[str, object]:
        return {
            "display_height_px": self.display_height_px,
            "timeline_style": self.timeline_style.to_dict(),
            "tree_layout": self.tree_layout.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: object) -> "DiagramSettings":
        defaults = cls()
        if not isinstance(payload, dict):
            return defaults
        raw_height = payload.get("display_height_px")
        display_height_px = int(raw_height) if isinstance(raw_height, (int, float)) else None
        if display_height_px is not None:
            display_height_px = max(160, display_height_px)
        return cls(
            display_height_px=display_height_px,
            timeline_style=TimelineDiagramStyle.from_dict(payload.get("timeline_style")),
            tree_layout=TreeDiagramLayout.from_dict(payload.get("tree_layout")),
        )


class EquationRenderTaskSignals(QObject):
    finished = Signal(int, object)


class EquationRenderTask(QRunnable):
    def __init__(
        self,
        request_id: int,
        expression: str,
        options: EquationRenderOptions,
        *,
        force_recheck: bool = False,
    ):
        super().__init__()
        self.request_id = request_id
        self.expression = expression
        self.options = options
        self.force_recheck = force_recheck
        self.signals = EquationRenderTaskSignals()

    def run(self):
        try:
            payload = render_latex_equation_payload(
                self.expression,
                self.options,
                force_recheck=self.force_recheck,
            )
            self.signals.finished.emit(self.request_id, {"payload": payload})
        except Exception as exc:
            self.signals.finished.emit(self.request_id, {"error": str(exc)})


EQUATION_METADATA_PREFIX = "eqmeta:"
NOTEBOOK_CELL_METADATA_PREFIX = "nbcell:"
NOTEBOOK_CELL_ACTION_PREFIX = "nbcellaction:"
NOTEBOOK_CELL_TYPES = {"code", "markdown", "timeline", "tree"}


def _default_diagram_settings() -> DiagramSettings:
    return DiagramSettings()


def _ensure_diagram_settings(metadata_or_settings: NotebookCellMetadata | DiagramSettings | None) -> DiagramSettings:
    if isinstance(metadata_or_settings, NotebookCellMetadata):
        settings = metadata_or_settings.diagram_settings
    else:
        settings = metadata_or_settings
    return settings if isinstance(settings, DiagramSettings) else _default_diagram_settings()
LATEX_BACKEND_UNKNOWN = "unknown"
LATEX_BACKEND_READY = "ready"
LATEX_BACKEND_UNAVAILABLE = "unavailable"
LATEX_BACKEND_FALLBACK_ONLY = "fallback_only"
LATEX_COMPILE_TIMEOUT_SECONDS = 30
DVIPNG_TIMEOUT_SECONDS = 45

_LATEX_IMAGE_CACHE: dict[tuple[str, EquationRenderOptions, str], EquationRenderPayload] = {}
_LATEX_BACKEND_STATE = {
    "status": LATEX_BACKEND_UNKNOWN,
    "diagnostic": "",
    "retry_after": 0.0,
}


class _EquationNode:
    def __init__(self, html_text: str, *, operator_like: bool = False):
        self.html_text = html_text
        self.operator_like = operator_like


class _EquationParser:
    def __init__(self, source: str):
        self.source = source
        self.length = len(source)
        self.index = 0

    def parse(self) -> str:
        sequence = self._parse_sequence()
        return sequence.html_text or html.escape(self.source)

    def _peek(self) -> str:
        if self.index >= self.length:
            return ""
        return self.source[self.index]

    def _consume(self) -> str:
        character = self._peek()
        if character:
            self.index += 1
        return character

    def _parse_sequence(self, stop_char: str | None = None) -> _EquationNode:
        parts: list[str] = []
        while self.index < self.length:
            character = self._peek()
            if stop_char and character == stop_char:
                break
            if character.isspace():
                self._consume()
                parts.append("&nbsp;")
                continue
            atom = self._parse_atom()
            atom = self._apply_scripts(atom)
            parts.append(atom.html_text)
        return _EquationNode("".join(parts))

    def _parse_atom(self) -> _EquationNode:
        character = self._peek()
        if not character:
            return _EquationNode("")

        if character == "{":
            self._consume()
            content = self._parse_sequence("}")
            if self._peek() == "}":
                self._consume()
            return _EquationNode(content.html_text)

        if character == "\\":
            return self._parse_command()

        self._consume()
        return _EquationNode(html.escape(character))

    def _parse_command(self) -> _EquationNode:
        self._consume()
        command_parts: list[str] = []
        while self._peek().isalpha():
            command_parts.append(self._consume())
        command = "".join(command_parts)

        if not command:
            return _EquationNode(html.escape("\\"))

        if command == "frac":
            numerator = self._parse_group_or_atom().html_text or "&nbsp;"
            denominator = self._parse_group_or_atom().html_text or "&nbsp;"
            return _EquationNode(
                (
                    "<span style=\"display:inline-table; vertical-align:middle; "
                    "text-align:center; margin:0 3px;\">"
                    f"<span style=\"display:table-row; border-bottom:1px solid #edf4ff; "
                    f"padding:0 2px;\">{numerator}</span>"
                    f"<span style=\"display:table-row; padding:0 2px;\">{denominator}</span>"
                    "</span>"
                )
            )

        if command == "sqrt":
            radicand = self._parse_group_or_atom().html_text or "&nbsp;"
            return _EquationNode(
                (
                    "<span style=\"display:inline-flex; align-items:flex-start; margin:0 2px;\">"
                    "<span style=\"font-size:135%; line-height:1; padding-right:2px;\">√</span>"
                    f"<span style=\"border-top:1px solid #edf4ff; padding:1px 2px 0 2px;\">{radicand}</span>"
                    "</span>"
                )
            )

        symbol = EQUATION_SYMBOL_MAP.get(command)
        if symbol is None:
            return _EquationNode(html.escape(f"\\{command}"))
        return _EquationNode(
            f"<span>{html.escape(symbol)}</span>",
            operator_like=command in EQUATION_OPERATOR_COMMANDS,
        )

    def _parse_group_or_atom(self) -> _EquationNode:
        if self._peek() == "{":
            return self._parse_atom()
        atom = self._parse_atom()
        atom = self._apply_scripts(atom)
        return atom

    def _apply_scripts(self, base: _EquationNode) -> _EquationNode:
        superscript = ""
        subscript = ""
        while self._peek() in {"^", "_"}:
            marker = self._consume()
            node = self._parse_group_or_atom()
            if marker == "^":
                superscript = node.html_text or superscript
            else:
                subscript = node.html_text or subscript

        if not superscript and not subscript:
            return base

        if base.operator_like:
            top_html = superscript or "&nbsp;"
            bottom_html = subscript or "&nbsp;"
            return _EquationNode(
                (
                    "<span style=\"display:inline-table; vertical-align:middle; "
                    "text-align:center; margin:0 2px;\">"
                    f"<span style=\"display:table-row; font-size:60%; line-height:1;\">{top_html}</span>"
                    f"<span style=\"display:table-row; font-size:125%; line-height:1.1;\">{base.html_text}</span>"
                    f"<span style=\"display:table-row; font-size:60%; line-height:1;\">{bottom_html}</span>"
                    "</span>"
                )
            )

        html_text = base.html_text
        if subscript:
            html_text += f"<sub style=\"font-size:65%; vertical-align:-0.35em;\">{subscript}</sub>"
        if superscript:
            html_text += f"<sup style=\"font-size:65%; vertical-align:0.6em;\">{superscript}</sup>"
        return _EquationNode(html_text)


def render_equation_html(expression: str) -> str:
    parser = _EquationParser(expression)
    rendered = parser.parse()
    return (
        f"<span style=\"{EQUATION_TEXT_STYLE} font-size:12pt; white-space:nowrap;\">"
        f"{rendered}"
        "</span>"
    )


def render_equation_image_html(expression: str) -> str:
    if not expression.strip():
        return ""

    equation_html = render_equation_html(expression)
    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setHtml(f"<div style=\"padding:2px 4px;\">{equation_html}</div>")
    document.adjustSize()

    content_size = document.size().toSize()
    width = max(8, content_size.width() + 8)
    height = max(8, content_size.height() + 6)

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    document.drawContents(painter, QRectF(0, 0, width, height))
    painter.end()

    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()

    encoded = bytes(byte_array.toBase64()).decode("ascii")
    alt_text = html.escape(expression)
    return (
        f'<img src="data:image/png;base64,{encoded}" alt="{alt_text}" '
        'style="vertical-align:middle; margin:2px 0;">'
    )


def _build_latex_document(expression: str, options: EquationRenderOptions) -> str:
    baseline_skip = max(int(round(options.font_size * 1.2)), options.font_size + 2)
    return "\n".join(
        [
            r"\documentclass[12pt]{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage{amsmath,amssymb,amsfonts}",
            r"\pagestyle{empty}",
            r"\begin{document}",
            r"\begingroup",
            fr"\fontsize{{{options.font_size}}}{{{baseline_skip}}}\selectfont",
            r"\[",
            expression,
            r"\]",
            r"\endgroup",
            r"\end{document}",
            "",
        ]
    )


def _encode_equation_metadata(metadata: EquationMetadata) -> str:
    payload = {
        "version": 1,
        "latex": metadata.latex,
        "font_size": metadata.font_size,
        "bold": metadata.bold,
        "italic": metadata.italic,
        "underline": metadata.underline,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return f"{EQUATION_METADATA_PREFIX}{encoded.rstrip('=')}"


def _decode_equation_metadata(href: str | None) -> EquationMetadata | None:
    if not isinstance(href, str) or not href.startswith(EQUATION_METADATA_PREFIX):
        return None

    encoded = href[len(EQUATION_METADATA_PREFIX) :]
    if not encoded:
        return None

    padding = "=" * (-len(encoded) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    latex = payload.get("latex")
    if not isinstance(latex, str) or not latex.strip():
        return None

    font_size = payload.get("font_size", 20)
    if not isinstance(font_size, int):
        try:
            font_size = int(font_size)
        except (TypeError, ValueError):
            font_size = 20

    return EquationMetadata(
        latex=latex.strip(),
        font_size=max(8, min(font_size, 72)),
        bold=bool(payload.get("bold", False)),
        italic=bool(payload.get("italic", False)),
        underline=bool(payload.get("underline", False)),
    )


def _build_equation_insertion_html(metadata: EquationMetadata, payload: EquationRenderPayload) -> str:
    metadata_href = _encode_equation_metadata(metadata)
    return f'<a href="{metadata_href}">{payload.image_html}</a>'


def _normalize_latex_expression(expression: str) -> str:
    normalized = expression.strip()
    changed = True
    while normalized and changed:
        changed = False
        for opener, closer in MATH_DELIMITER_PAIRS:
            if (
                normalized.startswith(opener)
                and normalized.endswith(closer)
                and len(normalized) > len(opener) + len(closer)
            ):
                candidate = normalized[len(opener) : len(normalized) - len(closer)].strip()
                if candidate:
                    normalized = candidate
                    changed = True
                break
    return normalized


def _is_latex_backend_unavailable_error(message: str) -> bool:
    lowered = message.lower()
    signatures = (
        "fresh tex installation",
        "miktex",
        "access is denied",
        "please finish the setup",
        "create directoryw",
        "operating on the private",
    )
    return any(signature in lowered for signature in signatures)


def _classify_latex_backend_failure(message: str) -> tuple[str, str] | None:
    lowered = message.lower()

    if _is_latex_backend_unavailable_error(message):
        return (
            LATEX_BACKEND_UNAVAILABLE,
            "Fallback preview active because MiKTeX is not initialized yet.",
        )

    if "timed out after" in lowered and any(tool in lowered for tool in ("latex", "dvipng", "tex")):
        return (
            LATEX_BACKEND_FALLBACK_ONLY,
            "Fallback preview active because the local TeX renderer timed out.",
        )

    if (
        "winerror 2" in lowered
        or "no such file or directory" in lowered
        or "not recognized as an internal or external command" in lowered
    ) and any(tool in lowered for tool in ("latex", "dvipng", "tex")):
        return (
            LATEX_BACKEND_UNAVAILABLE,
            "Fallback preview active because the local TeX tools are unavailable.",
        )

    return None


def _set_latex_backend_state(status: str, diagnostic: str = ""):
    _LATEX_BACKEND_STATE["status"] = status
    _LATEX_BACKEND_STATE["diagnostic"] = diagnostic
    if status in {LATEX_BACKEND_UNAVAILABLE, LATEX_BACKEND_FALLBACK_ONLY}:
        _LATEX_BACKEND_STATE["retry_after"] = time.monotonic() + LATEX_AUTO_RECHECK_DELAY_SECONDS
    else:
        _LATEX_BACKEND_STATE["retry_after"] = 0.0


def _reset_latex_backend_state():
    _set_latex_backend_state(LATEX_BACKEND_UNKNOWN, "")


def _cached_equation_payload(
    expression: str,
    options: EquationRenderOptions,
    backend_name: str,
) -> EquationRenderPayload | None:
    return _LATEX_IMAGE_CACHE.get((expression, options, backend_name))


def _store_equation_payload(
    expression: str,
    options: EquationRenderOptions,
    payload: EquationRenderPayload,
):
    _LATEX_IMAGE_CACHE[(expression, options, payload.backend_name)] = payload


def _session_cached_equation_payload(
    expression: str,
    options: EquationRenderOptions,
) -> EquationRenderPayload | None:
    backend_status = _LATEX_BACKEND_STATE["status"]
    if backend_status == LATEX_BACKEND_READY:
        return _cached_equation_payload(expression, options, "latex")
    if backend_status in {LATEX_BACKEND_UNAVAILABLE, LATEX_BACKEND_FALLBACK_ONLY}:
        return _cached_equation_payload(expression, options, "fallback")
    return None


def _should_auto_recheck_latex_backend() -> bool:
    return (
        _LATEX_BACKEND_STATE["status"] in {LATEX_BACKEND_UNAVAILABLE, LATEX_BACKEND_FALLBACK_ONLY}
        and time.monotonic() >= float(_LATEX_BACKEND_STATE.get("retry_after", 0.0))
    )


def _fallback_payload_for_latex_failure(
    expression: str,
    options: EquationRenderOptions,
    error_message: str,
) -> EquationRenderPayload | None:
    classification = _classify_latex_backend_failure(error_message)
    if classification is None:
        return None

    status, diagnostic = classification
    _set_latex_backend_state(status, diagnostic)
    payload = _render_fallback_latex_payload(
        expression,
        options,
        diagnostic=diagnostic,
    )
    _store_equation_payload(expression, options, payload)
    return payload


def render_latex_equation_payload(
    expression: str,
    options: EquationRenderOptions = EquationRenderOptions(),
    *,
    force_recheck: bool = False,
) -> EquationRenderPayload:
    normalized_expression = _normalize_latex_expression(expression)
    if not normalized_expression:
        return EquationRenderPayload(image_html="", backend_name="none")

    if force_recheck:
        _reset_latex_backend_state()

    if _should_auto_recheck_latex_backend():
        _reset_latex_backend_state()

    backend_status = _LATEX_BACKEND_STATE["status"]
    if backend_status == LATEX_BACKEND_READY:
        cached = _cached_equation_payload(normalized_expression, options, "latex")
        if cached is not None:
            return cached
        try:
            payload = _render_true_latex_payload(normalized_expression, options)
        except Exception as exc:
            fallback_payload = _fallback_payload_for_latex_failure(
                normalized_expression,
                options,
                str(exc).strip(),
            )
            if fallback_payload is None:
                raise
            return fallback_payload
        _store_equation_payload(normalized_expression, options, payload)
        return payload

    if backend_status in {LATEX_BACKEND_UNAVAILABLE, LATEX_BACKEND_FALLBACK_ONLY}:
        cached = _cached_equation_payload(normalized_expression, options, "fallback")
        if cached is not None:
            return cached
        payload = _render_fallback_latex_payload(
            normalized_expression,
            options,
            diagnostic=_LATEX_BACKEND_STATE["diagnostic"],
        )
        _store_equation_payload(normalized_expression, options, payload)
        return payload

    try:
        payload = _render_true_latex_payload(normalized_expression, options)
        _set_latex_backend_state(LATEX_BACKEND_READY, "Using local TeX toolchain.")
        _store_equation_payload(normalized_expression, options, payload)
        return payload
    except Exception as exc:
        fallback_payload = _fallback_payload_for_latex_failure(
            normalized_expression,
            options,
            str(exc).strip(),
        )
        if fallback_payload is None:
            raise
        return fallback_payload


def render_latex_equation_image_html(
    expression: str,
    options: EquationRenderOptions = EquationRenderOptions(),
    *,
    force_recheck: bool = False,
) -> str:
    return render_latex_equation_payload(
        expression,
        options,
        force_recheck=force_recheck,
    ).image_html


def _render_true_latex_payload(expression: str, options: EquationRenderOptions) -> EquationRenderPayload:
    png_bytes = _render_true_latex_equation_png(expression, options)
    processed_bytes = _postprocess_equation_png(png_bytes, options)
    return EquationRenderPayload(
        image_html=_png_bytes_to_html(processed_bytes, expression),
        backend_name="latex",
        diagnostic="Using local TeX toolchain.",
    )


def _render_fallback_latex_payload(
    expression: str,
    options: EquationRenderOptions,
    *,
    diagnostic: str = "",
) -> EquationRenderPayload:
    png_bytes = _render_mathtext_equation_png(expression, options)
    processed_bytes = _postprocess_equation_png(png_bytes, options)
    fallback_note = diagnostic or "Fallback preview active."
    return EquationRenderPayload(
        image_html=_png_bytes_to_html(processed_bytes, expression),
        backend_name="fallback",
        diagnostic=fallback_note,
    )


def _run_tex_subprocess(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        tool_name = command[0] if command else "TeX command"
        raise RuntimeError(f"{tool_name} timed out after {timeout_seconds} seconds.") from exc


def _render_true_latex_equation_png(expression: str, options: EquationRenderOptions) -> bytes:
    document_source = _build_latex_document(expression, options)
    cache_root = Path(__file__).resolve().parents[1] / ".latex_preview_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    temp_path = cache_root / f"boardexam_latex_{uuid.uuid4().hex}"
    temp_path.mkdir(parents=True, exist_ok=True)
    try:
        tex_path = temp_path / "equation.tex"
        dvi_path = temp_path / "equation.dvi"
        png_path = temp_path / "equation.png"
        log_path = temp_path / "equation.log"

        tex_path.write_text(document_source, encoding="utf-8")

        latex_command = [
            "latex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_path.name,
        ]
        latex_result = _run_tex_subprocess(
            latex_command,
            cwd=temp_path,
            timeout_seconds=LATEX_COMPILE_TIMEOUT_SECONDS,
        )
        if latex_result.returncode != 0 or not dvi_path.exists():
            error_output = latex_result.stdout + "\n" + latex_result.stderr
            if log_path.exists():
                error_output = log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(error_output.strip() or "LaTeX failed to render the equation.")

        png_command = [
            "dvipng",
            "-D",
            "200",
            "-bg",
            "Transparent",
            "-T",
            "tight",
            "-o",
            png_path.name,
            dvi_path.name,
        ]
        png_result = _run_tex_subprocess(
            png_command,
            cwd=temp_path,
            timeout_seconds=DVIPNG_TIMEOUT_SECONDS,
        )
        if png_result.returncode != 0 or not png_path.exists():
            error_output = png_result.stdout + "\n" + png_result.stderr
            raise RuntimeError(error_output.strip() or "dvipng failed to render the equation.")

        return png_path.read_bytes()
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def _render_mathtext_equation_png(expression: str, options: EquationRenderOptions) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    figure = plt.figure(figsize=(0.01, 0.01), dpi=200, facecolor=(0, 0, 0, 0))
    text_artist = figure.text(
        0,
        0.5,
        f"${expression}$",
        fontsize=options.font_size,
        color=EQUATION_FOREGROUND_COLOR,
        va="center",
        ha="left",
        math_fontfamily="stix",
        fontweight="bold" if options.bold else "normal",
        fontstyle="italic" if options.italic else "normal",
    )
    output = BytesIO()
    try:
        figure.canvas.draw()
        bbox = text_artist.get_window_extent(figure.canvas.get_renderer()).expanded(1.12, 1.3)
        figure.savefig(
            output,
            format="png",
            transparent=True,
            bbox_inches=bbox.transformed(figure.dpi_scale_trans.inverted()),
            pad_inches=0.12,
        )
        return output.getvalue()
    finally:
        plt.close(figure)


def _postprocess_equation_png(png_bytes: bytes, options: EquationRenderOptions) -> bytes:
    image = QImage.fromData(png_bytes, "PNG")
    if image.isNull():
        raise RuntimeError("Rendered equation image could not be loaded.")

    working_image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    target_color = QColor(EQUATION_FOREGROUND_COLOR)
    target_red = target_color.red()
    target_green = target_color.green()
    target_blue = target_color.blue()
    for y in range(working_image.height()):
        for x in range(working_image.width()):
            pixel = working_image.pixelColor(x, y)
            alpha = pixel.alpha()
            if alpha == 0:
                continue
            working_image.setPixelColor(x, y, QColor(target_red, target_green, target_blue, alpha))

    if options.italic:
        transform = QTransform()
        transform.shear(-0.18, 0.0)
        working_image = working_image.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    margin_x = max(14, int(round(options.font_size * 0.7)))
    margin_top = max(12, int(round(options.font_size * 0.65)))
    margin_bottom = max(14, int(round(options.font_size * 0.75)))
    underline_space = max(0, options.font_size // 3 if options.underline else 0)
    bold_extra = 3 if options.bold else 0
    canvas = QImage(
        working_image.width() + margin_x * 2 + bold_extra,
        working_image.height() + margin_top + margin_bottom + underline_space,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    x = margin_x
    y = margin_top

    if options.bold:
        for dx in (0, 1):
            for dy in (0, 1):
                painter.drawImage(x + dx, y + dy, working_image)
    else:
        painter.drawImage(x, y, working_image)

    if options.underline:
        underline_pen = QPen(QColor(EQUATION_FOREGROUND_COLOR))
        underline_pen.setWidth(max(1, options.font_size // 10))
        painter.setPen(underline_pen)
        baseline_y = min(
            canvas.height() - max(3, options.font_size // 8),
            y + working_image.height() + max(2, options.font_size // 8),
        )
        painter.drawLine(x, baseline_y, x + working_image.width(), baseline_y)

    painter.end()

    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    canvas.save(buffer, "PNG")
    buffer.close()
    return bytes(byte_array)


def _png_bytes_to_html(png_bytes: bytes, expression: str) -> str:
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{encoded}" alt="{html.escape(expression)}" '
        'style="vertical-align:middle; margin:2px 0;">'
    )


def render_latex_equation_preview_html(
    payload: EquationRenderPayload,
) -> str:
    return (
        "<div style=\"background:#0f1728; border:1px solid #22314b; border-radius:8px; "
        "padding:14px; min-height:100px; display:flex; align-items:center;\">"
        f"{payload.image_html}"
        "</div>"
    )


def _encode_notebook_cell_metadata(metadata: NotebookCellMetadata) -> str:
    diagram_settings = None
    if metadata.cell_type in {"timeline", "tree"}:
        diagram_settings = _ensure_diagram_settings(metadata).to_dict()
    payload = {
        "version": 2,
        "cell_id": metadata.cell_id,
        "cell_type": metadata.cell_type,
        "source": metadata.source,
        "rendered_html": metadata.rendered_html,
        "is_editing": metadata.is_editing,
        "diagram_settings": diagram_settings,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return f"{NOTEBOOK_CELL_METADATA_PREFIX}{encoded.rstrip('=')}"


def _decode_notebook_cell_metadata(href: str | None) -> NotebookCellMetadata | None:
    if not isinstance(href, str) or not href.startswith(NOTEBOOK_CELL_METADATA_PREFIX):
        return None

    encoded = href[len(NOTEBOOK_CELL_METADATA_PREFIX) :]
    if not encoded:
        return None

    padding = "=" * (-len(encoded) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((encoded + padding).encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    version = payload.get("version", 1)
    if not isinstance(version, int) or version < 1 or version > 2:
        return None
    cell_id = payload.get("cell_id")
    cell_type = payload.get("cell_type")
    source = payload.get("source", "")
    rendered_html = payload.get("rendered_html", "")
    is_editing = bool(payload.get("is_editing", False))
    if not isinstance(cell_id, str) or not cell_id.strip():
        return None
    if not isinstance(cell_type, str) or cell_type not in NOTEBOOK_CELL_TYPES:
        return None
    if not isinstance(source, str):
        return None
    if not isinstance(rendered_html, str):
        rendered_html = ""
    diagram_settings = None
    if cell_type in {"timeline", "tree"}:
        diagram_settings = DiagramSettings.from_dict(payload.get("diagram_settings"))

    return NotebookCellMetadata(
        cell_id=cell_id.strip(),
        cell_type=cell_type,
        source=source,
        rendered_html=rendered_html,
        is_editing=is_editing,
        diagram_settings=diagram_settings,
    )


def _encode_notebook_cell_action_href(action: str, metadata: NotebookCellMetadata) -> str:
    if action not in {"run", "edit"}:
        raise ValueError(f"Unsupported notebook cell action: {action}")
    payload = _encode_notebook_cell_metadata(metadata)[len(NOTEBOOK_CELL_METADATA_PREFIX) :]
    return f"{NOTEBOOK_CELL_ACTION_PREFIX}{action}:{payload}"


def _decode_notebook_cell_action_href(href: str | None) -> tuple[str, NotebookCellMetadata] | None:
    if not isinstance(href, str) or not href.startswith(NOTEBOOK_CELL_ACTION_PREFIX):
        return None

    action_payload = href[len(NOTEBOOK_CELL_ACTION_PREFIX) :]
    action, separator, payload = action_payload.partition(":")
    if separator != ":" or not payload:
        return None
    metadata = _decode_notebook_cell_metadata(f"{NOTEBOOK_CELL_METADATA_PREFIX}{payload}")
    if metadata is None or action not in {"run", "edit"}:
        return None
    return action, metadata


def _decode_notebook_cell_metadata_from_html(document_html: str | None) -> NotebookCellMetadata | None:
    if not isinstance(document_html, str) or not document_html:
        return None

    href_matches = re.findall(r'href="([^"]+)"', document_html)
    for raw_href in href_matches:
        href = html.unescape(raw_href)
        metadata = _decode_notebook_cell_metadata(href)
        if metadata is not None:
            return metadata
        decoded_action = _decode_notebook_cell_action_href(href)
        if decoded_action is not None:
            _action, metadata = decoded_action
            return metadata
    return None


def _notebook_cell_label(cell_type: str) -> str:
    return {
        "code": "PY",
        "markdown": "MD",
        "timeline": "TL",
        "tree": "TREE",
    }.get(cell_type, "CELL")


def _html_body_fragment(document_html: str) -> str:
    match = re.search(r"<body[^>]*>(.*)</body>", document_html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    return document_html


def _render_markdown_cell_html(source: str) -> str:
    document = QTextDocument()
    document.setMarkdown(source)
    rendered = _html_body_fragment(document.toHtml()).strip()
    if rendered:
        return rendered
    return "<p style=\"color:#93a8c7;\"><i>Empty markdown cell.</i></p>"


def _render_code_output_html(source: str) -> str:
    if not source.strip():
        return "<p style=\"color:#93a8c7;\"><i>Empty code cell.</i></p>"

    try:
        result = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            "<div style=\"margin-top:8px; color:#ffb4b4;\">"
            "<b>Timed out:</b> The code cell exceeded the 10 second limit."
            "</div>"
        )

    stdout_html = html.escape(result.stdout.rstrip("\n"))
    stderr_html = html.escape(result.stderr.rstrip("\n"))
    sections: list[str] = []
    if stdout_html:
        sections.append(
            "<div style=\"margin-top:8px;\">"
            "<div style=\"color:#7ab0ff; font-weight:700; margin-bottom:4px;\">Output</div>"
            f"<pre style=\"margin:0; white-space:pre-wrap; color:#edf4ff;\">{stdout_html}</pre>"
            "</div>"
        )
    if stderr_html:
        sections.append(
            "<div style=\"margin-top:8px;\">"
            "<div style=\"color:#ff9b9b; font-weight:700; margin-bottom:4px;\">Errors</div>"
            f"<pre style=\"margin:0; white-space:pre-wrap; color:#ffcccc;\">{stderr_html}</pre>"
            "</div>"
        )
    if not sections:
        sections.append(
            "<div style=\"margin-top:8px; color:#93a8c7;\"><i>Code ran without console output.</i></div>"
        )
    return "".join(sections)


def _parse_timeline_entries(source: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            title, detail = line.split("|", 1)
        else:
            title, detail = line, ""
        title = title.strip()
        detail = detail.strip()
        if title:
            entries.append((title, detail))
    return entries


@dataclass
class _TreeNode:
    label: str
    path_id: str
    children: list["_TreeNode"]


def _parse_tree_source(source: str) -> list[_TreeNode]:
    roots: list[_TreeNode] = []
    stack: list[tuple[int, _TreeNode]] = []
    for raw_line in source.splitlines():
        if not raw_line.strip():
            continue
        stripped = raw_line.lstrip(" \t")
        indent_width = len(raw_line) - len(stripped)
        depth = max(0, indent_width // 2)
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            path_id = f"{parent.path_id}/{len(parent.children)}"
        else:
            path_id = str(len(roots))
        node = _TreeNode(label=stripped.strip(), path_id=path_id, children=[])
        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)
        stack.append((depth, node))
    return roots


def _sanitize_tree_layout_for_source(source: str, settings: DiagramSettings) -> DiagramSettings:
    roots = _parse_tree_source(source)
    valid_ids: set[str] = set()

    def collect(node: _TreeNode):
        valid_ids.add(node.path_id)
        for child in node.children:
            collect(child)

    for root in roots:
        collect(root)
    cleaned_positions = {
        path_id: value
        for path_id, value in settings.tree_layout.node_positions.items()
        if path_id in valid_ids
    }
    if cleaned_positions == settings.tree_layout.node_positions:
        return settings
    return replace(
        settings,
        tree_layout=replace(settings.tree_layout, node_positions=cleaned_positions),
    )


def _normalized_diagram_settings(diagram_type: str, source: str, settings: DiagramSettings | None) -> DiagramSettings:
    normalized = _ensure_diagram_settings(settings)
    if diagram_type == "tree":
        normalized = _sanitize_tree_layout_for_source(source, normalized)
    return normalized


def _diagram_settings_key(settings: DiagramSettings | None) -> str:
    normalized = _ensure_diagram_settings(settings)
    return json.dumps(normalized.to_dict(), sort_keys=True, separators=(",", ":"))


def _measure_tree_node_rect(label: str, font: QFont) -> QRectF:
    metrics = QFontMetrics(font)
    min_width = 120
    max_width = 320
    horizontal_padding = 12
    vertical_padding = 10
    inner_width = max_width - (horizontal_padding * 2)
    natural_width = metrics.horizontalAdvance(label) + (horizontal_padding * 2)
    width = min(max_width, max(min_width, natural_width))
    text_rect = metrics.boundingRect(
        QRectF(0, 0, max(10, width - (horizontal_padding * 2)), 10000).toRect(),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
        label,
    )
    height = max(48, text_rect.height() + (vertical_padding * 2))
    return QRectF(0, 0, width, height)


class TreeNodeGraphicsItem(QGraphicsObject):
    def __init__(
        self,
        *,
        path_id: str,
        label: str,
        font: QFont,
        fill_color: QColor,
        border_color: QColor,
        text_color: QColor,
        movable: bool,
        position_changed_callback=None,
    ):
        super().__init__()
        self.path_id = path_id
        self.label = label
        self.font = font
        self.fill_color = fill_color
        self.border_color = border_color
        self.text_color = text_color
        self._position_changed_callback = position_changed_callback
        self._rect = _measure_tree_node_rect(label, font)
        self._text_rect = self._rect.adjusted(12, 10, -12, -10)
        self._callback_enabled = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, movable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, movable)
        self.setCursor(Qt.CursorShape.OpenHandCursor if movable else Qt.CursorShape.ArrowCursor)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-1, -1, 1, 1)

    def set_position_callback_enabled(self, enabled: bool):
        self._callback_enabled = enabled

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(self.border_color, 1.6))
        painter.setBrush(self.fill_color)
        painter.drawRoundedRect(self._rect, 10, 10)
        painter.setPen(self.text_color)
        painter.setFont(self.font)
        painter.drawText(
            self._text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap),
            self.label,
        )

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and self._callback_enabled
            and callable(self._position_changed_callback)
        ):
            self._position_changed_callback(self.path_id, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)


def _create_text_item(scene: QGraphicsScene, text: str, style: DiagramTextStyle, *, width: float | None = None):
    item = scene.addText(text)
    item.setFont(style.resolved_font())
    item.setDefaultTextColor(style.resolved_color())
    if width is not None:
        item.setTextWidth(width)
    return item


def _populate_vertical_timeline_scene(scene: QGraphicsScene, source: str, settings: DiagramSettings):
    label_brush = QColor("#edf4ff")
    accent_pen = QPen(QColor("#4f6f99"))
    accent_pen.setWidthF(2.0)
    marker_pen = QPen(QColor("#7ab0ff"))
    marker_pen.setWidthF(1.6)

    entries = _parse_timeline_entries(source)
    if not entries:
        scene.addText("Add timeline items using: Title | details").setDefaultTextColor(label_brush)
        scene.setSceneRect(0, 0, 640, 180)
        return

    style = settings.timeline_style
    left_margin = 28.0
    top_margin = 24.0
    title_max_width = 260.0
    detail_max_width = 340.0
    marker_radius = 8.0
    column_gap = float(style.column_gap_px)
    spine_x = left_margin + title_max_width + (column_gap / 2.0)
    detail_x = spine_x + (column_gap / 2.0) + 18.0
    row_gap = float(style.row_gap_px)
    row_layouts: list[tuple[object, object | None, float, float]] = []
    y = top_margin

    for title, detail in entries:
        title_item = _create_text_item(scene, title, style.title_style, width=title_max_width)
        detail_item = _create_text_item(scene, detail, style.detail_style, width=detail_max_width) if detail else None
        title_rect = title_item.boundingRect()
        detail_rect = detail_item.boundingRect() if detail_item is not None else QRectF(0, 0, 0, 0)
        row_height = max(30.0, title_rect.height(), detail_rect.height())
        row_layouts.append((title_item, detail_item, y, row_height))
        y += row_height + row_gap

    first_center_y = row_layouts[0][2] + (row_layouts[0][3] / 2.0)
    last_center_y = row_layouts[-1][2] + (row_layouts[-1][3] / 2.0)
    scene.addLine(spine_x, first_center_y, spine_x, last_center_y, accent_pen)

    content_bottom = top_margin
    for title_item, detail_item, row_y, row_height in row_layouts:
        title_rect = title_item.boundingRect()
        title_item.setPos(left_margin, row_y + ((row_height - title_rect.height()) / 2.0))
        marker_center_y = row_y + (row_height / 2.0)
        scene.addEllipse(
            spine_x - marker_radius,
            marker_center_y - marker_radius,
            marker_radius * 2.0,
            marker_radius * 2.0,
            marker_pen,
            QColor("#19304d"),
        )
        if detail_item is not None:
            detail_rect = detail_item.boundingRect()
            detail_item.setPos(detail_x, row_y + ((row_height - detail_rect.height()) / 2.0))
            content_bottom = max(content_bottom, row_y + row_height, detail_item.pos().y() + detail_rect.height())
        else:
            content_bottom = max(content_bottom, row_y + row_height)

    scene.setSceneRect(0, 0, detail_x + detail_max_width + 28.0, content_bottom + top_margin)


def _auto_layout_tree_positions(
    roots: list[_TreeNode],
    node_rects: dict[str, QRectF],
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    sibling_gap = 40.0
    level_gap = 84.0
    top_margin = 24.0
    left_margin = 24.0
    max_height = max((rect.height() for rect in node_rects.values()), default=48.0)
    next_leaf_x = left_margin

    def layout(node: _TreeNode, depth: int) -> float:
        nonlocal next_leaf_x
        rect = node_rects[node.path_id]
        if not node.children:
            x = next_leaf_x
            next_leaf_x += rect.width() + sibling_gap
        else:
            child_centers = [layout(child, depth + 1) for child in node.children]
            x = ((child_centers[0] + child_centers[-1]) / 2.0) - (rect.width() / 2.0)
        y = top_margin + depth * (max_height + level_gap)
        positions[node.path_id] = (x, y)
        return x + (rect.width() / 2.0)

    for root in roots:
        layout(root, 0)
    return positions


def _populate_vertical_tree_scene(
    scene: QGraphicsScene,
    source: str,
    settings: DiagramSettings,
    *,
    interactive: bool = False,
    on_settings_changed=None,
):
    label_brush = QColor("#edf4ff")
    accent_pen = QPen(QColor("#4f6f99"))
    accent_pen.setWidthF(2.0)
    node_pen = QColor("#7ab0ff")
    node_fill = QColor("#19304d")

    roots = _parse_tree_source(source)
    if not roots:
        scene.addText("Add a tree using indentation for children").setDefaultTextColor(label_brush)
        scene.setSceneRect(0, 0, 640, 220)
        return

    node_font = QApplication.font()
    node_font.setPointSize(11)
    node_font.setBold(True)

    node_rects: dict[str, QRectF] = {}
    node_lookup: dict[str, _TreeNode] = {}

    def collect(node: _TreeNode):
        node_lookup[node.path_id] = node
        node_rects[node.path_id] = _measure_tree_node_rect(node.label, node_font)
        for child in node.children:
            collect(child)

    for root in roots:
        collect(root)

    auto_positions = _auto_layout_tree_positions(roots, node_rects)
    saved_positions = settings.tree_layout.node_positions
    positions: dict[str, tuple[float, float]] = {}
    for path_id, auto_pos in auto_positions.items():
        saved = saved_positions.get(path_id)
        if isinstance(saved, dict) and isinstance(saved.get("x"), (int, float)) and isinstance(saved.get("y"), (int, float)):
            positions[path_id] = (float(saved["x"]), float(saved["y"]))
        else:
            positions[path_id] = auto_pos

    def handle_item_moved(path_id: str, pos):
        if not interactive or not callable(on_settings_changed):
            return
        updated_positions = dict(settings.tree_layout.node_positions)
        updated_positions[path_id] = {"x": float(pos.x()), "y": float(pos.y())}
        on_settings_changed(
            replace(
                settings,
                tree_layout=replace(settings.tree_layout, node_positions=updated_positions),
            )
        )

    def draw_connectors(node: _TreeNode):
        parent_x, parent_y = positions[node.path_id]
        parent_rect = node_rects[node.path_id]
        parent_center_x = parent_x + (parent_rect.width() / 2.0)
        parent_bottom_y = parent_y + parent_rect.height()
        for child in node.children:
            child_x, child_y = positions[child.path_id]
            child_rect = node_rects[child.path_id]
            child_center_x = child_x + (child_rect.width() / 2.0)
            scene.addLine(parent_center_x, parent_bottom_y, child_center_x, child_y, accent_pen)
            draw_connectors(child)

    for root in roots:
        draw_connectors(root)

    for path_id, node in node_lookup.items():
        item = TreeNodeGraphicsItem(
            path_id=path_id,
            label=node.label,
            font=node_font,
            fill_color=node_fill,
            border_color=node_pen,
            text_color=label_brush,
            movable=interactive,
            position_changed_callback=handle_item_moved,
        )
        x, y = positions[path_id]
        item.setPos(x, y)
        item.set_position_callback_enabled(interactive)
        scene.addItem(item)

    bounds = scene.itemsBoundingRect().adjusted(-24, -24, 24, 24)
    if bounds.isNull():
        bounds = QRectF(0, 0, 640, 240)
    scene.setSceneRect(bounds)


def _populate_diagram_scene(
    scene: QGraphicsScene,
    diagram_type: str,
    source: str,
    settings: DiagramSettings | None = None,
    *,
    interactive: bool = False,
    on_settings_changed=None,
):
    scene.clear()
    scene.setBackgroundBrush(QColor("#0f1728"))
    normalized_settings = _normalized_diagram_settings(diagram_type, source, settings)
    if diagram_type == "timeline":
        _populate_vertical_timeline_scene(scene, source, normalized_settings)
        return
    _populate_vertical_tree_scene(
        scene,
        source,
        normalized_settings,
        interactive=interactive,
        on_settings_changed=on_settings_changed,
    )


def _render_diagram_html(diagram_type: str, source: str, settings: DiagramSettings | None = None) -> str:
    scene = QGraphicsScene()
    _populate_diagram_scene(scene, diagram_type, source, settings)
    rect = scene.sceneRect()
    image = QImage(int(max(1, rect.width())), int(max(1, rect.height())), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#0f1728"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scene.render(painter)
    painter.end()
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    encoded = bytes(byte_array.toBase64()).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{encoded}" alt="{html.escape(diagram_type)} diagram" '
        'style="max-width:100%; border-radius:6px;">'
    )


class EquationInputEdit(QPlainTextEdit):
    def insertFromMimeData(self, source):
        pasted_text = source.text()
        if pasted_text:
            self.textCursor().insertText(_normalize_latex_expression(pasted_text))
            return
        super().insertFromMimeData(source)


class NotebookRichTextEdit(QTextEdit):
    anchorActivated = Signal(str)

    def mouseReleaseEvent(self, event: QMouseEvent):
        anchor = self.anchorAt(event.position().toPoint())
        super().mouseReleaseEvent(event)
        if anchor:
            self.anchorActivated.emit(anchor)


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._zoom_factor = 1.0
        self._zoom_step = 1.15
        self._min_zoom_factor = 0.4
        self._max_zoom_factor = 6.0
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def fit_to_scene(self):
        scene = self.scene()
        if scene is None:
            return
        rect = scene.sceneRect()
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        padded_rect = rect.adjusted(-24, -24, 24, 24)
        self.resetTransform()
        self.fitInView(padded_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_factor = 1.0

    def zoom_in(self):
        self._apply_zoom_factor(self._zoom_step)

    def zoom_out(self):
        self._apply_zoom_factor(1 / self._zoom_step)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
            event.accept()
            return
        if event.angleDelta().y() < 0:
            self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def _apply_zoom_factor(self, factor: float):
        target_zoom = max(self._min_zoom_factor, min(self._max_zoom_factor, self._zoom_factor * factor))
        scale_factor = target_zoom / self._zoom_factor
        if abs(scale_factor - 1.0) < 0.001:
            return
        self.scale(scale_factor, scale_factor)
        self._zoom_factor = target_zoom


class ResizablePixmapItem(QGraphicsPixmapItem):
    """A QGraphicsPixmapItem with resizable handles (corner, side, and rotation)."""
    
    def __init__(self, pixmap: QPixmap):
        super().__init__(pixmap)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        # Resize handle data
        self.handle_size = 10
        self.handles = {}  # {position: QRectF}
        self.handle_positions = [
            "top-left", "top", "top-right",
            "left", "right",
            "bottom-left", "bottom", "bottom-right",
            "rotate"
        ]
        
        self.dragging_handle = None
        self.last_mouse_pos = None
        self.original_pixmap = pixmap.copy()
        self.original_size = pixmap.size()
        self.original_pos = self.pos()
        self.rotation_angle = 0
        
        self._update_handles()
    
    def _update_handles(self):
        """Update handle positions based on current pixmap bounds."""
        rect = self.boundingRect()
        h_size = self.handle_size
        center = rect.center()
        
        # Corner and side handles
        self.handles = {
            "top-left": QRectF(rect.left() - h_size/2, rect.top() - h_size/2, h_size, h_size),
            "top": QRectF(center.x() - h_size/2, rect.top() - h_size/2, h_size, h_size),
            "top-right": QRectF(rect.right() - h_size/2, rect.top() - h_size/2, h_size, h_size),
            "left": QRectF(rect.left() - h_size/2, center.y() - h_size/2, h_size, h_size),
            "right": QRectF(rect.right() - h_size/2, center.y() - h_size/2, h_size, h_size),
            "bottom-left": QRectF(rect.left() - h_size/2, rect.bottom() - h_size/2, h_size, h_size),
            "bottom": QRectF(center.x() - h_size/2, rect.bottom() - h_size/2, h_size, h_size),
            "bottom-right": QRectF(rect.right() - h_size/2, rect.bottom() - h_size/2, h_size, h_size),
            "rotate": QRectF(center.x() - h_size/2, rect.top() - 40, h_size, h_size),
        }
    
    def paint(self, painter: QPainter, option, widget=None):
        """Paint the pixmap and the resize handles."""
        super().paint(painter, option, widget)
        
        if self.isSelected():
            # Draw handles
            painter.save()
            
            for pos, rect in self.handles.items():
                if pos == "rotate":
                    # Draw rotation handle as a circle with arrow
                    painter.setPen(QPen(QColor(255, 100, 0), 2))
                    painter.setBrush(QColor(255, 100, 0, 180))
                    painter.drawEllipse(rect)
                    # Draw rotation arrow icon
                    center = rect.center()
                    painter.setFont(painter.font())
                    painter.drawText(int(center.x() - 3), int(center.y() + 3), "↻")
                else:
                    # Draw corner/side handles as squares
                    painter.setPen(QPen(QColor(0, 150, 255), 2))
                    painter.setBrush(QColor(0, 150, 255, 180))
                    painter.drawRect(rect)
            
            painter.restore()
    
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press on resize handles."""
        scene_pos = event.scenePos()
        
        for pos, rect in self.handles.items():
            if rect.contains(scene_pos):
                self.dragging_handle = pos
                self.last_mouse_pos = scene_pos
                self.original_pixmap = self.pixmap().copy()
                self.original_size = self.pixmap().size()
                self.original_pos = self.pos()
                event.accept()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse move for resizing."""
        if self.dragging_handle is None:
            super().mouseMoveEvent(event)
            return
        
        scene_pos = event.scenePos()
        delta = scene_pos - self.last_mouse_pos
        
        original_width = self.original_size.width()
        original_height = self.original_size.height()
        aspect_ratio = original_width / original_height if original_height > 0 else 1
        
        if self.dragging_handle == "rotate":
            # Rotation handle - rotate by mouse movement
            center = self.original_pos + self.boundingRect().center()
            angle_delta = (scene_pos - center).x() * 0.5
            self.rotation_angle += angle_delta
            self.setRotation(self.rotation_angle)
        
        elif self.dragging_handle == "top-left":
            # Proportional resize from top-left corner
            new_width = max(50, original_width - delta.x())
            new_height = int(new_width / aspect_ratio)
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
            self.setPos(self.original_pos.x() + delta.x(), self.original_pos.y() + delta.y())
        
        elif self.dragging_handle == "top-right":
            # Proportional resize from top-right corner
            new_width = max(50, original_width + delta.x())
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
            self.setPos(self.original_pos.x(), self.original_pos.y() + delta.y())
        
        elif self.dragging_handle == "bottom-left":
            # Proportional resize from bottom-left corner
            new_width = max(50, original_width - delta.x())
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
            self.setPos(self.original_pos.x() + delta.x(), self.original_pos.y())
        
        elif self.dragging_handle == "bottom-right":
            # Proportional resize from bottom-right corner
            new_width = max(50, original_width + delta.x())
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
        
        elif self.dragging_handle == "top":
            # Free vertical resize from top
            new_height = max(50, original_height - delta.y())
            self.setPixmap(self.original_pixmap.scaledToHeight(
                int(new_height), Qt.TransformationMode.SmoothTransformation
            ))
            self.setPos(self.original_pos.x(), self.original_pos.y() + delta.y())
        
        elif self.dragging_handle == "bottom":
            # Free vertical resize from bottom
            new_height = max(50, original_height + delta.y())
            self.setPixmap(self.original_pixmap.scaledToHeight(
                int(new_height), Qt.TransformationMode.SmoothTransformation
            ))
        
        elif self.dragging_handle == "left":
            # Free horizontal resize from left
            new_width = max(50, original_width - delta.x())
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
            self.setPos(self.original_pos.x() + delta.x(), self.original_pos.y())
        
        elif self.dragging_handle == "right":
            # Free horizontal resize from right
            new_width = max(50, original_width + delta.x())
            self.setPixmap(self.original_pixmap.scaledToWidth(
                int(new_width), Qt.TransformationMode.SmoothTransformation
            ))
        
        self._update_handles()
        self.update()
        event.accept()
    
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release."""
        self.dragging_handle = None
        self.last_mouse_pos = None
        self.original_pixmap = self.pixmap().copy()
        self.original_size = self.pixmap().size()
        self.original_pos = self.pos()
        super().mouseReleaseEvent(event)


class ImageEditorDialog(QDialog):
    """Modal dialog for editing image with resize handles."""
    
    def __init__(self, parent: QWidget | None = None, pixmap: QPixmap | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Image")
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # Create graphics scene and view
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("QGraphicsView { background-color: #2a2a2a; }")
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        layout.addWidget(self.view)
        
        # Instructions label
        instructions = QLabel(
            "Drag corner handles to resize proportionally | "
            "Drag side handles to stretch | "
            "Drag rotation handle (top center) to rotate"
        )
        instructions.setStyleSheet("color: #999; font-size: 11px; padding: 8px;")
        layout.addWidget(instructions)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Add resizable pixmap item
        if pixmap is not None:
            self.pixmap_item = ResizablePixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)
            self.pixmap_item.setSelected(True)
            
            # Fit view with margin to show handles (they extend outside the image bounds)
            scene_rect = self.scene.itemsBoundingRect()
            margin = 80  # Extra space for corner handles and rotation handle
            expanded_rect = scene_rect.adjusted(-margin, -margin, margin, margin)
            self.view.fitInView(expanded_rect, Qt.AspectRatioMode.KeepAspectRatio)
            self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.pixmap_item = None
    
    def get_edited_pixmap(self) -> QPixmap:
        """Return the edited pixmap."""
        if self.pixmap_item is None:
            return QPixmap()
        return self.pixmap_item.pixmap()


class ImageSizeDialog(QDialog):
    """Dialog for configuring image size and text wrapping options."""

    def __init__(self, parent: QWidget | None = None, default_width: int = 300, is_resize: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Resize Image" if is_resize else "Image Size and Wrapping")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.is_resize = is_resize

        layout = QVBoxLayout(self)

        # Width control with slider
        width_group = QGroupBox("Image Width", self)
        width_layout = QVBoxLayout(width_group)
        
        width_control_layout = QHBoxLayout()
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setMinimum(50)
        self.width_spinbox.setMaximum(2000)
        self.width_spinbox.setValue(default_width)
        self.width_spinbox.setSuffix(" px")
        
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setMinimum(50)
        self.width_slider.setMaximum(2000)
        self.width_slider.setValue(default_width)
        self.width_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.width_slider.setTickInterval(100)
        
        # Connect slider and spinbox to keep them in sync
        self.width_slider.valueChanged.connect(self.width_spinbox.setValue)
        self.width_spinbox.valueChanged.connect(self.width_slider.setValue)
        
        width_control_layout.addWidget(QLabel("Size:"))
        width_control_layout.addWidget(self.width_spinbox)
        width_control_layout.addStretch()
        width_layout.addLayout(width_control_layout)
        width_layout.addWidget(self.width_slider)
        
        layout.addWidget(width_group)

        # Text wrapping options (only show if not in resize mode)
        if not is_resize:
            wrap_group = QGroupBox("Text Wrapping", self)
            wrap_layout = QVBoxLayout(wrap_group)

            self.wrap_none = QRadioButton("Inline (no wrap)")
            self.wrap_left = QRadioButton("Wrap text to the left")
            self.wrap_right = QRadioButton("Wrap text to the right")
            self.wrap_both = QRadioButton("Center (no wrap)")

            self.wrap_none.setChecked(True)
            wrap_layout.addWidget(self.wrap_none)
            wrap_layout.addWidget(self.wrap_left)
            wrap_layout.addWidget(self.wrap_right)
            wrap_layout.addWidget(self.wrap_both)

            layout.addWidget(wrap_group)
        else:
            # For resize, create dummy wrap buttons set to current values
            self.wrap_none = QRadioButton()
            self.wrap_left = QRadioButton()
            self.wrap_right = QRadioButton()
            self.wrap_both = QRadioButton()
            self.wrap_none.setChecked(True)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_width(self) -> int:
        """Get the selected width in pixels."""
        return self.width_spinbox.value()

    def get_wrap_mode(self) -> str:
        """Get the selected text wrapping mode: 'none', 'left', 'right', or 'center'."""
        if self.wrap_left.isChecked():
            return "left"
        elif self.wrap_right.isChecked():
            return "right"
        elif self.wrap_both.isChecked():
            return "center"
        else:
            return "none"
    
    def set_wrap_mode(self, wrap_mode: str) -> None:
        """Set the wrap mode from current image."""
        if wrap_mode == "left":
            self.wrap_left.setChecked(True)
        elif wrap_mode == "right":
            self.wrap_right.setChecked(True)
        elif wrap_mode == "center":
            self.wrap_both.setChecked(True)
        else:
            self.wrap_none.setChecked(True)


class EquationBuilderDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_expression: str = "",
        initial_options: EquationRenderOptions | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Equation Builder")
        self.setModal(True)
        self.resize(720, 460)

        self._last_rendered_payload: EquationRenderPayload | None = None
        self._last_render_signature: tuple[str, EquationRenderOptions] | None = None
        self._next_force_recheck = False
        self._current_request_id = 0
        self._thread_pool = QThreadPool.globalInstance()
        self._initial_options = initial_options or EquationRenderOptions()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(700)
        self.preview_timer.timeout.connect(self._refresh_preview)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        intro = QLabel(
            "Type LaTeX math below. The preview prefers your local TeX toolchain and "
            "falls back automatically if MiKTeX is not ready.",
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        style_row = QWidget(self)
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        style_layout.setSpacing(8)

        self.style_font_size_label = QLabel("Size", style_row)
        style_layout.addWidget(self.style_font_size_label)

        self.style_font_size_combo = QComboBox(style_row)
        self.style_font_size_combo.setEditable(True)
        for size in ("12", "14", "16", "18", "20", "24", "28", "32", "36"):
            self.style_font_size_combo.addItem(size)
        self.style_font_size_combo.setCurrentText(str(self._initial_options.font_size))
        self.style_font_size_combo.currentTextChanged.connect(self._schedule_preview_refresh)
        style_layout.addWidget(self.style_font_size_combo)

        self.style_bold_button = QToolButton(style_row)
        self.style_bold_button.setText("B")
        self.style_bold_button.setCheckable(True)
        self.style_bold_button.setChecked(self._initial_options.bold)
        self.style_bold_button.clicked.connect(self._schedule_preview_refresh)
        style_layout.addWidget(self.style_bold_button)

        self.style_italic_button = QToolButton(style_row)
        self.style_italic_button.setText("I")
        self.style_italic_button.setCheckable(True)
        self.style_italic_button.setChecked(self._initial_options.italic)
        self.style_italic_button.clicked.connect(self._schedule_preview_refresh)
        style_layout.addWidget(self.style_italic_button)

        self.style_underline_button = QToolButton(style_row)
        self.style_underline_button.setText("U")
        self.style_underline_button.setCheckable(True)
        self.style_underline_button.setChecked(self._initial_options.underline)
        self.style_underline_button.clicked.connect(self._schedule_preview_refresh)
        style_layout.addWidget(self.style_underline_button)
        style_layout.addStretch(1)
        layout.addWidget(style_row)

        self.expression_edit = EquationInputEdit(self)
        self.expression_edit.setPlaceholderText(
            r"Example: \int_{0}^{\infty} \frac{e^{-x}}{1+x^2} dx"
        )
        expression_font = QFont("Cambria Math", 14)
        self.expression_edit.setFont(expression_font)
        self.expression_edit.setPlainText(initial_expression)
        self.expression_edit.textChanged.connect(self._schedule_preview_refresh)
        layout.addWidget(self.expression_edit, 1)

        preview_header = QWidget(self)
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(0, 0, 0, 0)
        preview_header_layout.setSpacing(8)

        preview_label = QLabel("LaTeX Preview", preview_header)
        preview_header_layout.addWidget(preview_label)

        preview_header_layout.addStretch(1)
        self.backend_status_label = QLabel("", preview_header)
        self.backend_status_label.setWordWrap(True)
        preview_header_layout.addWidget(self.backend_status_label)

        self.recheck_latex_button = QToolButton(preview_header)
        self.recheck_latex_button.setText("Recheck LaTeX")
        self.recheck_latex_button.clicked.connect(self._request_latex_recheck)
        self.recheck_latex_button.setVisible(False)
        preview_header_layout.addWidget(self.recheck_latex_button)
        layout.addWidget(preview_header)

        self.preview = QTextBrowser(self)
        self.preview.setOpenExternalLinks(False)
        self.preview.setMinimumHeight(140)
        layout.addWidget(self.preview, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._refresh_preview()

    def current_render_options(self) -> EquationRenderOptions:
        try:
            font_size = int(float(self.style_font_size_combo.currentText().strip()))
        except ValueError:
            font_size = 20
        font_size = max(8, min(font_size, 72))
        return EquationRenderOptions(
            font_size=font_size,
            bold=self.style_bold_button.isChecked(),
            italic=self.style_italic_button.isChecked(),
            underline=self.style_underline_button.isChecked(),
        )

    def current_metadata(self) -> EquationMetadata:
        options = self.current_render_options()
        return EquationMetadata(
            latex=self.expression(),
            font_size=options.font_size,
            bold=options.bold,
            italic=options.italic,
            underline=options.underline,
        )

    def _set_rendering_state(self, text: str = "Rendering preview..."):
        self.backend_status_label.setText(text)
        self.preview.setHtml(
            (
                "<div style=\"background:#0f1728; border:1px solid #22314b; border-radius:8px; "
                "padding:14px; min-height:100px; color:#8e9ab0;\">Rendering preview...</div>"
            )
        )

    def _schedule_preview_refresh(self):
        if not self.expression():
            self.preview_timer.stop()
            self._refresh_preview()
            return
        self._set_rendering_state()
        self.preview_timer.start()

    def _request_latex_recheck(self):
        self._next_force_recheck = True
        self._schedule_preview_refresh()

    def _refresh_preview(self):
        expression = self.expression()
        if not expression:
            self._last_rendered_payload = None
            self._last_render_signature = None
            self.backend_status_label.setText("")
            self.preview.setHtml(
                (
                    "<div style=\"background:#0f1728; border:1px solid #22314b; border-radius:8px; "
                    "padding:14px; min-height:100px; color:#8e9ab0;\">Enter a LaTeX expression to preview it.</div>"
                )
            )
            return

        options = self.current_render_options()
        signature = (expression, options)
        if not self._next_force_recheck and self._last_render_signature == signature and self._last_rendered_payload is not None:
            self.preview.setHtml(render_latex_equation_preview_html(self._last_rendered_payload))
            self._update_backend_status(self._last_rendered_payload)
            return

        if not self._next_force_recheck:
            cached_payload = _session_cached_equation_payload(expression, options)
            if cached_payload is not None:
                self._last_rendered_payload = cached_payload
                self._last_render_signature = signature
                self.preview.setHtml(render_latex_equation_preview_html(cached_payload))
                self._update_backend_status(cached_payload)
                return

        self._current_request_id += 1
        request_id = self._current_request_id
        task = EquationRenderTask(
            request_id,
            expression,
            options,
            force_recheck=self._next_force_recheck,
        )
        self._next_force_recheck = False
        task.signals.finished.connect(self._on_render_finished)
        self._thread_pool.start(task)

    def _update_backend_status(self, payload: EquationRenderPayload):
        if payload.backend_name == "latex":
            self.backend_status_label.setText("Using local TeX toolchain.")
            self.recheck_latex_button.setVisible(False)
            return

        if payload.backend_name == "fallback":
            self.backend_status_label.setText(payload.diagnostic or "Fallback preview active.")
            self.recheck_latex_button.setVisible(True)
            return

        self.backend_status_label.setText("")
        self.recheck_latex_button.setVisible(False)

    def _on_render_finished(self, request_id: int, result: object):
        if request_id != self._current_request_id:
            return

        if not isinstance(result, dict):
            return

        error = result.get("error")
        if isinstance(error, str) and error:
            self._last_rendered_payload = None
            self._last_render_signature = None
            self.backend_status_label.setText("")
            self.preview.setHtml(
                (
                    "<div style=\"background:#0f1728; border:1px solid #7a2f2f; border-radius:8px; "
                    "padding:14px; min-height:100px; color:#ffb4b4;\">"
                    f"<b>LaTeX render failed.</b><br><pre style=\"white-space:pre-wrap; "
                    f"font-family:Consolas, monospace;\">{html.escape(error)}</pre></div>"
                )
            )
            return

        payload = result.get("payload")
        if not isinstance(payload, EquationRenderPayload):
            return

        self._last_rendered_payload = payload
        self._last_render_signature = (self.expression(), self.current_render_options())
        self.preview.setHtml(render_latex_equation_preview_html(payload))
        self._update_backend_status(payload)

    def expression(self) -> str:
        return _normalize_latex_expression(self.expression_edit.toPlainText())

    def render_payload(self) -> EquationRenderPayload | None:
        expression = self.expression()
        if not expression:
            return None

        signature = (expression, self.current_render_options())
        if self._last_rendered_payload is not None and self._last_render_signature == signature:
            return self._last_rendered_payload

        try:
            payload = render_latex_equation_payload(
                expression,
                self.current_render_options(),
                force_recheck=self._next_force_recheck,
            )
        except Exception:
            return None

        self._last_rendered_payload = payload
        self._last_render_signature = signature
        self._next_force_recheck = False
        self._update_backend_status(payload)
        return payload

    def equation_html(self) -> str:
        payload = self.render_payload()
        if payload is None:
            return ""
        return _build_equation_insertion_html(self.current_metadata(), payload)


class NotebookCellEditDialog(QDialog):
    def __init__(self, parent: QWidget, *, title: str, initial_source: str, placeholder: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 460)
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(initial_source)
        self.editor.setPlaceholderText(placeholder)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def source_text(self) -> str:
        return self.editor.toPlainText()


class DiagramEditorDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        *,
        diagram_type: str,
        initial_source: str = "",
        initial_settings: DiagramSettings | None = None,
    ):
        super().__init__(parent)
        self.diagram_type = diagram_type
        self._diagram_settings = _normalized_diagram_settings(diagram_type, initial_source, initial_settings)
        self._tree_drag_commit_pending = False
        self.setWindowTitle("Timeline Editor" if diagram_type == "timeline" else "Tree Diagram Editor")
        self.resize(1040, 640)

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter, 1)

        editor_panel = QWidget(splitter)
        editor_layout = QVBoxLayout(editor_panel)
        hint = QLabel(
            "Timeline: `Title | details` per line." if diagram_type == "timeline"
            else "Tree: use two spaces for each child level.",
            editor_panel,
        )
        hint.setWordWrap(True)
        editor_layout.addWidget(hint)
        self.source_editor = QPlainTextEdit(editor_panel)
        self.source_editor.setPlainText(initial_source)
        editor_layout.addWidget(self.source_editor, 1)

        preview_panel = QWidget(splitter)
        preview_layout = QVBoxLayout(preview_panel)

        self.timeline_style_group: QGroupBox | None = None
        self.tree_reset_layout_button: QPushButton | None = None
        self._title_style_controls: dict[str, QWidget] = {}
        self._detail_style_controls: dict[str, QWidget] = {}

        if self.diagram_type == "timeline":
            self.timeline_style_group = QGroupBox("Timeline Style", preview_panel)
            style_layout = QFormLayout(self.timeline_style_group)
            self._title_style_controls = self._build_text_style_controls(
                self.timeline_style_group,
                self._diagram_settings.timeline_style.title_style,
            )
            self._detail_style_controls = self._build_text_style_controls(
                self.timeline_style_group,
                self._diagram_settings.timeline_style.detail_style,
            )
            style_layout.addRow("Title", self._title_style_controls["row"])
            style_layout.addRow("Details", self._detail_style_controls["row"])
            self.timeline_row_gap_spinbox = QSpinBox(self.timeline_style_group)
            self.timeline_row_gap_spinbox.setRange(12, 120)
            self.timeline_row_gap_spinbox.setValue(self._diagram_settings.timeline_style.row_gap_px)
            self.timeline_row_gap_spinbox.valueChanged.connect(self._on_timeline_style_changed)
            style_layout.addRow("Row gap", self.timeline_row_gap_spinbox)
            preview_layout.addWidget(self.timeline_style_group)
        else:
            tree_tools = QWidget(preview_panel)
            tree_tools_layout = QHBoxLayout(tree_tools)
            tree_tools_layout.setContentsMargins(0, 0, 0, 0)
            self.tree_reset_layout_button = QPushButton("Reset Layout", tree_tools)
            self.tree_reset_layout_button.clicked.connect(self._reset_tree_layout)
            tree_tools_layout.addWidget(self.tree_reset_layout_button)
            tree_tools_layout.addStretch(1)
            preview_layout.addWidget(tree_tools)

        zoom_row = QHBoxLayout()
        self.zoom_out_button = QPushButton("-", preview_panel)
        self.zoom_in_button = QPushButton("+", preview_panel)
        self.zoom_reset_button = QPushButton("Reset", preview_panel)
        zoom_row.addWidget(self.zoom_out_button)
        zoom_row.addWidget(self.zoom_in_button)
        zoom_row.addWidget(self.zoom_reset_button)
        zoom_row.addStretch(1)
        preview_layout.addLayout(zoom_row)

        self.scene = QGraphicsScene(preview_panel)
        self.view = ZoomableGraphicsView(preview_panel)
        self.view.setScene(self.scene)
        preview_layout.addWidget(self.view, 1)

        splitter.addWidget(editor_panel)
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([360, 680])

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.zoom_in_button.clicked.connect(self.view.zoom_in)
        self.zoom_out_button.clicked.connect(self.view.zoom_out)
        self.zoom_reset_button.clicked.connect(self._reset_zoom)
        self.source_editor.textChanged.connect(self.refresh_preview)
        self.refresh_preview()

    def _build_text_style_controls(self, parent: QWidget, style: DiagramTextStyle) -> dict[str, QWidget]:
        row = QWidget(parent)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        font_combo = QFontComboBox(row)
        if style.font_family.strip():
            font_combo.setCurrentFont(QFont(style.font_family))
        size_spinbox = QSpinBox(row)
        size_spinbox.setRange(8, 48)
        size_spinbox.setValue(style.font_size_pt)
        bold_checkbox = QCheckBox("B", row)
        bold_checkbox.setChecked(style.bold)
        italic_checkbox = QCheckBox("I", row)
        italic_checkbox.setChecked(style.italic)
        underline_checkbox = QCheckBox("U", row)
        underline_checkbox.setChecked(style.underline)
        color_button = QPushButton(row)
        color_button.setFixedWidth(58)
        self._apply_color_button(color_button, style.color)

        font_combo.currentFontChanged.connect(self._on_timeline_style_changed)
        size_spinbox.valueChanged.connect(self._on_timeline_style_changed)
        bold_checkbox.toggled.connect(self._on_timeline_style_changed)
        italic_checkbox.toggled.connect(self._on_timeline_style_changed)
        underline_checkbox.toggled.connect(self._on_timeline_style_changed)
        color_button.clicked.connect(lambda: self._pick_color(color_button))

        row_layout.addWidget(font_combo, 1)
        row_layout.addWidget(size_spinbox)
        row_layout.addWidget(bold_checkbox)
        row_layout.addWidget(italic_checkbox)
        row_layout.addWidget(underline_checkbox)
        row_layout.addWidget(color_button)

        return {
            "row": row,
            "font_combo": font_combo,
            "size_spinbox": size_spinbox,
            "bold_checkbox": bold_checkbox,
            "italic_checkbox": italic_checkbox,
            "underline_checkbox": underline_checkbox,
            "color_button": color_button,
        }

    def _apply_color_button(self, button: QPushButton, color_value: str):
        color = QColor(color_value)
        resolved = color.name() if color.isValid() else "#edf4ff"
        button.setText(resolved.upper())
        button.setProperty("diagramColor", resolved)
        button.setStyleSheet(
            f"QPushButton {{ background:{resolved}; color:{'#08101d' if color.lightness() > 140 else '#edf4ff'}; }}"
        )

    def _pick_color(self, button: QPushButton):
        chosen = QColorDialog.getColor(QColor(str(button.property("diagramColor") or "#edf4ff")), self)
        if not chosen.isValid():
            return
        self._apply_color_button(button, chosen.name())
        self._on_timeline_style_changed()

    def _text_style_from_controls(self, controls: dict[str, QWidget]) -> DiagramTextStyle:
        return DiagramTextStyle(
            font_family=controls["font_combo"].currentFont().family(),
            font_size_pt=controls["size_spinbox"].value(),
            bold=controls["bold_checkbox"].isChecked(),
            italic=controls["italic_checkbox"].isChecked(),
            underline=controls["underline_checkbox"].isChecked(),
            color=str(controls["color_button"].property("diagramColor") or "#edf4ff"),
        )

    def _on_timeline_style_changed(self):
        if self.diagram_type != "timeline":
            return
        self._diagram_settings = replace(
            self._diagram_settings,
            timeline_style=replace(
                self._diagram_settings.timeline_style,
                title_style=self._text_style_from_controls(self._title_style_controls),
                detail_style=self._text_style_from_controls(self._detail_style_controls),
                row_gap_px=self.timeline_row_gap_spinbox.value(),
            ),
        )
        self.refresh_preview(fit=False)

    def _reset_tree_layout(self):
        if self.diagram_type != "tree":
            return
        self._diagram_settings = replace(
            self._diagram_settings,
            tree_layout=replace(self._diagram_settings.tree_layout, node_positions={}),
        )
        self.refresh_preview()

    def _on_tree_layout_changed(self, settings: DiagramSettings):
        self._diagram_settings = settings
        self._tree_drag_commit_pending = True

    def _reset_zoom(self):
        self.view.fit_to_scene()

    def refresh_preview(self, *, fit: bool = True):
        self._diagram_settings = _normalized_diagram_settings(
            self.diagram_type,
            self.source_editor.toPlainText(),
            self._diagram_settings,
        )
        _populate_diagram_scene(
            self.scene,
            self.diagram_type,
            self.source_editor.toPlainText(),
            self._diagram_settings,
            interactive=self.diagram_type == "tree",
            on_settings_changed=self._on_tree_layout_changed if self.diagram_type == "tree" else None,
        )
        if fit or self._tree_drag_commit_pending:
            self.view.fit_to_scene()
            self._tree_drag_commit_pending = False

    def source_text(self) -> str:
        return self.source_editor.toPlainText()

    def diagram_settings(self) -> DiagramSettings:
        return _normalized_diagram_settings(self.diagram_type, self.source_text(), self._diagram_settings)


class NotebookTabController(QObject):
    def __init__(self, page: QWidget):
        super().__init__(page)
        self.page = page
        self.storage_root = Path(__file__).resolve().parent.parent / "notebooks"
        self.storage_root.mkdir(parents=True, exist_ok=True)

        self.subject_name: str | None = None
        self.chapter_titles: list[str] = []
        self.current_chapter: str | None = None
        self._notes_by_chapter: dict[str, str] = {}
        self._saved_selected_chapter: str | None = None
        self._loading_editor = False
        self._updating_toolbar = False
        self._toolbar_controls: list[QWidget] = []
        self._shortcuts: list[QShortcut] = []
        self._context_action_kind: str | None = None
        self._context_cell_table = None
        self._context_cell_metadata: NotebookCellMetadata | None = None
        self._context_equation_info = None
        self._active_cell_table = None
        self._active_cell_metadata: NotebookCellMetadata | None = None
        self._editor_state_dirty = False
        self._subject_payload_dirty = False
        self._rendering_notebook_cell = False
        self._active_diagram_preview_cell_id: str | None = None
        self._active_diagram_preview_type: str | None = None
        self._active_diagram_preview_source: str | None = None
        self._active_diagram_preview_settings_key: str | None = None
        self._active_diagram_preview_table = None
        self._diagram_settings_commit_timer = QTimer(self)
        self._diagram_settings_commit_timer.setSingleShot(True)
        self._diagram_settings_commit_timer.setInterval(160)
        self._diagram_settings_commit_timer.timeout.connect(self._commit_pending_diagram_settings)
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(NOTEBOOK_AUTOSAVE_DELAY_MS)
        self._autosave_timer.timeout.connect(self._flush_pending_subject_save)

        self._build_ui()
        self._refresh_chapter_tree()
        self._load_current_chapter_note()

    def set_storage_root(self, storage_root: str | Path):
        new_root = Path(storage_root)
        new_root.mkdir(parents=True, exist_ok=True)
        if new_root == self.storage_root:
            return

        self._flush_storage_save()
        self.storage_root = new_root
        if self.subject_name:
            payload = self._load_subject_payload(self.subject_name)
            self._notes_by_chapter = payload["notes"]
            saved_selected_chapter = payload.get("selected_chapter")
            self._saved_selected_chapter = (
                saved_selected_chapter if isinstance(saved_selected_chapter, str) else None
            )
            self._refresh_chapter_tree()
            self._load_current_chapter_note()

    def _clear_page(self):
        layout = self.page.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        else:
            layout = QVBoxLayout(self.page)
        return layout

    def _build_ui(self):
        root_layout = self._clear_page()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.root_splitter = QSplitter(Qt.Orientation.Horizontal, self.page)
        self.root_splitter.setChildrenCollapsible(False)
        self.root_splitter.setHandleWidth(6)

        self.editor_panel = QWidget(self.root_splitter)
        self.editor_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        editor_panel_layout = QVBoxLayout(self.editor_panel)
        editor_panel_layout.setContentsMargins(0, 0, 8, 0)
        editor_panel_layout.setSpacing(8)

        toolbar = QWidget(self.editor_panel)
        toolbar_container_layout = QVBoxLayout(toolbar)
        toolbar_container_layout.setContentsMargins(8, 8, 8, 0)
        toolbar_container_layout.setSpacing(6)

        primary_toolbar = QWidget(toolbar)
        primary_toolbar_layout = QHBoxLayout(primary_toolbar)
        primary_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        primary_toolbar_layout.setSpacing(8)

        self.font_family_combo = QFontComboBox(primary_toolbar)
        self.font_family_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.font_family_combo.currentFontChanged.connect(self._apply_font_family)
        primary_toolbar_layout.addWidget(self.font_family_combo, 2)
        self._toolbar_controls.append(self.font_family_combo)

        self.font_size_combo = QComboBox(primary_toolbar)
        self.font_size_combo.setEditable(True)
        for size in ("8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "36"):
            self.font_size_combo.addItem(size)
        self.font_size_combo.setCurrentText("12")
        self.font_size_combo.currentTextChanged.connect(self._apply_font_size)
        primary_toolbar_layout.addWidget(self.font_size_combo)
        self._toolbar_controls.append(self.font_size_combo)

        self.bold_button = self._make_format_button("B", "Bold", self._toggle_bold)
        self.italic_button = self._make_format_button("I", "Italic", self._toggle_italic)
        self.underline_button = self._make_format_button("U", "Underline", self._toggle_underline)
        self.code_button = self._make_action_button("` `", "Wrap the selection in backticks", self._insert_code)
        self.link_button = self._make_action_button("@", "Insert hyperlink", self._insert_hyperlink)
        self.image_button = self._make_action_button("[]", "Insert picture", self._insert_picture)
        self.image_resize_button = self._make_action_button("◈", "Resize image", self._resize_selected_image)
        self.equation_button = self._make_action_button("x²", "Insert equation", self._insert_equation)
        self.table_button = self._make_action_button("Tbl", "Insert table", self._insert_table)
        self.markdown_cell_button = self._make_action_button("MD", "Insert markdown cell", self._insert_markdown_cell)
        self.code_cell_button = self._make_action_button("Py", "Insert code cell", self._insert_code_cell)

        for button in (
            self.bold_button,
            self.italic_button,
            self.underline_button,
            self.code_button,
            self.link_button,
            self.image_button,
            self.image_resize_button,
            self.equation_button,
            self.table_button,
            self.markdown_cell_button,
            self.code_cell_button,
        ):
            primary_toolbar_layout.addWidget(button)
            self._toolbar_controls.append(button)
        primary_toolbar_layout.addStretch(1)
        toolbar_container_layout.addWidget(primary_toolbar)

        secondary_toolbar = QWidget(toolbar)
        secondary_toolbar_layout = QHBoxLayout(secondary_toolbar)
        secondary_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        secondary_toolbar_layout.setSpacing(8)

        self.bulleted_list_button = self._make_action_button("*", "Insert bullet points", self._apply_bulleted_list)
        self.numbered_list_button = self._make_action_button("1.", "Insert numbered list", self._apply_numbered_list)
        self.align_left_button = self._make_format_button("L", "Align left", self._align_left)
        self.align_center_button = self._make_format_button("C", "Align center", self._align_center)
        self.align_right_button = self._make_format_button("R", "Align right", self._align_right)
        self.align_justify_button = self._make_format_button("J", "Justify paragraph", self._align_justify)
        self.outdent_button = self._make_action_button("<<", "Decrease indentation", self._outdent_block)
        self.indent_button = self._make_action_button(">>", "Increase indentation", self._indent_block)
        self.timeline_button = self._make_action_button("TL", "Insert timeline", self._insert_timeline_cell)
        self.tree_diagram_button = self._make_action_button("Tree", "Insert tree diagram", self._insert_tree_cell)
        self.export_button = self._make_action_button("Export", "Export notebook", self._export_notebook)

        for button in (
            self.bulleted_list_button,
            self.numbered_list_button,
            self.align_left_button,
            self.align_center_button,
            self.align_right_button,
            self.align_justify_button,
            self.outdent_button,
            self.indent_button,
            self.timeline_button,
            self.tree_diagram_button,
            self.export_button,
        ):
            secondary_toolbar_layout.addWidget(button)
            self._toolbar_controls.append(button)
        secondary_toolbar_layout.addStretch(1)
        toolbar_container_layout.addWidget(secondary_toolbar)
        editor_panel_layout.addWidget(toolbar)

        self.page_context_label = QLabel("Choose a chapter to start writing.", self.editor_panel)
        self.page_context_label.setContentsMargins(8, 0, 8, 0)
        editor_panel_layout.addWidget(self.page_context_label)

        self.editor = NotebookRichTextEdit(self.editor_panel)
        self.editor.setAcceptRichText(True)
        self.editor.setPlaceholderText("Select a chapter on the right to start writing notes.")
        self.editor.textChanged.connect(self._on_editor_changed)
        self.editor.currentCharFormatChanged.connect(self._sync_toolbar_from_format)
        self.editor.cursorPositionChanged.connect(self._sync_toolbar_from_cursor)
        self.editor.anchorActivated.connect(self._on_editor_anchor_activated)
        editor_panel_layout.addWidget(self.editor, 1)

        self.context_action_bar = QWidget(self.editor.viewport())
        self.context_action_bar.setStyleSheet(
            "background:rgba(12, 21, 36, 0.96); border:1px solid #31435f; border-radius:4px;"
        )
        context_layout = QVBoxLayout(self.context_action_bar)
        context_layout.setContentsMargins(3, 3, 3, 3)
        context_layout.setSpacing(3)
        self.context_run_button = QToolButton(self.context_action_bar)
        self.context_edit_button = QToolButton(self.context_action_bar)
        self.context_run_button.setText("Run")
        self.context_edit_button.setText("Edit")
        self.context_run_button.setToolTip("Run")
        self.context_edit_button.setToolTip("Edit")
        for button in (self.context_run_button, self.context_edit_button):
            button.setAutoRaise(False)
            button.setFixedSize(44, 20)
            button.setStyleSheet(
                "QToolButton {"
                "background:#122338;"
                "border:1px solid #31435f;"
                "border-radius:3px;"
                "color:#dbe7f5;"
                "font-weight:700;"
                "padding:0;"
                "}"
                "QToolButton:hover {"
                "background:#1d3a5f;"
                "border-color:#7ab0ff;"
                "color:#ffffff;"
                "}"
                "QToolButton:pressed {"
                "background:#0d1a2b;"
                "border-color:#9ec5ff;"
                "}"
            )
        self.context_run_button.setStyleSheet(
            self.context_run_button.styleSheet()
            + "QToolButton { color:#edf4ff; border-color:#7ab0ff; }"
            + "QToolButton:hover { background:#20456e; border-color:#9ec5ff; }"
        )
        self.context_edit_button.setStyleSheet(
            self.context_edit_button.styleSheet()
            + "QToolButton:hover { background:#243247; border-color:#93a8c7; }"
        )
        self.context_run_button.clicked.connect(self._run_context_action)
        self.context_edit_button.clicked.connect(self._edit_context_action)
        context_layout.addWidget(self.context_run_button)
        context_layout.addWidget(self.context_edit_button)
        self.context_action_bar.setFixedWidth(50)
        self.context_action_bar.hide()

        self.diagram_preview_panel = QWidget(self.editor.viewport())
        self.diagram_preview_panel.setStyleSheet(
            "background:#101a2b; border:1px solid #617ea3; border-radius:4px;"
        )
        diagram_preview_layout = QVBoxLayout(self.diagram_preview_panel)
        diagram_preview_layout.setContentsMargins(4, 4, 4, 4)
        diagram_preview_layout.setSpacing(4)

        diagram_preview_header = QWidget(self.diagram_preview_panel)
        diagram_preview_header_layout = QHBoxLayout(diagram_preview_header)
        diagram_preview_header_layout.setContentsMargins(0, 0, 0, 0)
        diagram_preview_header_layout.setSpacing(8)
        self.diagram_preview_title = QLabel("Diagram Preview", diagram_preview_header)
        self.diagram_preview_title.setStyleSheet("color:#edf4ff; font-size:10.5pt; font-weight:700;")
        self.diagram_preview_hint = QLabel("Scroll to zoom. Drag to inspect.", diagram_preview_header)
        self.diagram_preview_hint.setStyleSheet("color:#93a8c7; font-size:9pt;")
        self.diagram_preview_fit_button = QToolButton(diagram_preview_header)
        self.diagram_preview_fit_button.setText("Fit")
        self.diagram_preview_fit_button.setToolTip("Fit the active diagram to the preview window")
        self.diagram_preview_fit_button.clicked.connect(lambda: self.diagram_preview_view.fit_to_scene())
        diagram_preview_header_layout.addWidget(self.diagram_preview_title)
        diagram_preview_header_layout.addStretch(1)
        diagram_preview_header_layout.addWidget(self.diagram_preview_hint)
        diagram_preview_header_layout.addWidget(self.diagram_preview_fit_button)
        diagram_preview_layout.addWidget(diagram_preview_header)
        diagram_preview_header.hide()

        self.diagram_preview_view = ZoomableGraphicsView(self.diagram_preview_panel)
        self.diagram_preview_view.setStyleSheet(
            "QGraphicsView { background-color:#0f1728; border:1px solid #243652; border-radius:6px; }"
        )
        self.diagram_preview_scene = QGraphicsScene(self.diagram_preview_view)
        self.diagram_preview_view.setScene(self.diagram_preview_scene)
        diagram_preview_layout.addWidget(self.diagram_preview_view, 1)
        self.diagram_preview_panel.hide()
        self.editor.installEventFilter(self)
        self.editor.viewport().installEventFilter(self)
        self.editor.verticalScrollBar().valueChanged.connect(self._layout_diagram_preview_panel)
        self.editor.horizontalScrollBar().valueChanged.connect(self._layout_diagram_preview_panel)

        self.chapter_panel = QWidget(self.root_splitter)
        self.chapter_panel.setMinimumWidth(220)
        self.chapter_panel.setMaximumWidth(320)
        chapter_panel_layout = QVBoxLayout(self.chapter_panel)
        chapter_panel_layout.setContentsMargins(8, 0, 0, 0)
        chapter_panel_layout.setSpacing(8)

        chapter_header_row = QWidget(self.chapter_panel)
        chapter_header_layout = QHBoxLayout(chapter_header_row)
        chapter_header_layout.setContentsMargins(0, 0, 0, 0)
        chapter_header_layout.setSpacing(8)

        self.chapter_title_label = QLabel("Chapters", chapter_header_row)
        self.chapter_status_label = QLabel("0 chapters", chapter_header_row)
        self.chapter_title_label.setStyleSheet("color: #7ab0ff; font-size: 10.5pt; font-weight: 700;")
        self.chapter_status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")
        self.chapter_status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        chapter_header_layout.addWidget(self.chapter_title_label)
        chapter_header_layout.addStretch(1)
        chapter_header_layout.addWidget(self.chapter_status_label)
        chapter_panel_layout.addWidget(chapter_header_row)

        self.chapter_list = QTreeWidget(self.chapter_panel)
        self.chapter_list.setHeaderHidden(True)
        self.chapter_list.setRootIsDecorated(True)
        self.chapter_list.setIndentation(16)
        self.chapter_list.setUniformRowHeights(True)
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_changed)
        chapter_panel_layout.addWidget(self.chapter_list, 1)

        self.chapter_hint_label = QLabel(
            "Right-click a subject in the subject tree to add more chapters.",
            self.chapter_panel,
        )
        self.chapter_hint_label.setContentsMargins(0, 0, 8, 8)
        self.chapter_hint_label.setWordWrap(True)
        chapter_panel_layout.addWidget(self.chapter_hint_label)

        self.root_splitter.addWidget(self.editor_panel)
        self.root_splitter.addWidget(self.chapter_panel)
        self.root_splitter.setStretchFactor(0, 5)
        self.root_splitter.setStretchFactor(1, 2)
        self.root_splitter.setSizes([900, 260])

        root_layout.addWidget(self.root_splitter, 1)

        self._apply_toolbar_icons()
        self._install_shortcuts()
        self._set_editor_enabled(False)
        self._sync_toolbar_from_cursor()

    def eventFilter(self, watched, event):
        if hasattr(self, "editor") and watched is self.editor.viewport() and event.type() == QEvent.Type.Resize:
            self._layout_diagram_preview_panel()
        elif hasattr(self, "editor") and watched is self.editor and event.type() == QEvent.Type.KeyPress:
            if self._handle_active_diagram_keypress(event):
                return True
        return super().eventFilter(watched, event)

    def _set_active_cell_metadata(self, metadata: NotebookCellMetadata):
        self._active_cell_metadata = metadata
        if self._context_cell_metadata is not None and self._context_cell_metadata.cell_id == metadata.cell_id:
            self._context_cell_metadata = metadata

    def _apply_active_diagram_settings(
        self,
        settings: DiagramSettings,
        *,
        commit_immediately: bool,
        fit_preview: bool = False,
    ) -> bool:
        if (
            self._active_cell_metadata is None
            or self._active_cell_metadata.cell_type not in {"timeline", "tree"}
            or not self._table_is_valid(self._active_cell_table)
        ):
            return False
        updated = replace(
            self._active_cell_metadata,
            diagram_settings=_normalized_diagram_settings(
                self._active_cell_metadata.cell_type,
                self._active_cell_metadata.source,
                settings,
            ),
        )
        self._set_active_cell_metadata(updated)
        if commit_immediately:
            self._commit_pending_diagram_settings(fit_preview=fit_preview)
        else:
            self._diagram_settings_commit_timer.start()
        return True

    def _commit_pending_diagram_settings(self, *, fit_preview: bool = False):
        if self._diagram_settings_commit_timer.isActive():
            self._diagram_settings_commit_timer.stop()
        if (
            self._active_cell_metadata is None
            or self._active_cell_metadata.cell_type not in {"timeline", "tree"}
            or not self._table_is_valid(self._active_cell_table)
        ):
            return
        self._render_notebook_cell_table(self._active_cell_table, self._active_cell_metadata, selected=True)
        if self._context_action_kind == "cell" and self._context_cell_metadata is not None:
            self._show_active_diagram_preview(self._active_cell_table, self._active_cell_metadata, fit=fit_preview)
        self._persist_current_editor_state()

    def _handle_active_diagram_keypress(self, event) -> bool:
        if event.key() != int(Qt.Key.Key_Space):
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return False
        if (
            self._active_cell_metadata is None
            or self._active_cell_metadata.cell_type not in {"timeline", "tree"}
            or self._active_cell_metadata.is_editing
        ):
            return False
        settings = _ensure_diagram_settings(self._active_cell_metadata)
        geometry = self._diagram_cell_content_geometry(self._active_cell_table, self._active_cell_metadata)
        auto_height = int(round(geometry.height())) if geometry is not None else 160
        current_height = max(160, settings.display_height_px or auto_height)
        delta = -24 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 24
        target_height = max(160, current_height + delta)
        updated_settings = replace(settings, display_height_px=target_height)
        return self._apply_active_diagram_settings(updated_settings, commit_immediately=True)

    def _diagram_cell_content_geometry(self, table, metadata: NotebookCellMetadata | None = None) -> QRectF | None:
        if not self._table_is_valid(table):
            return None

        try:
            content_cell = table.cellAt(0, 1)
            first_cursor = content_cell.firstCursorPosition()
            last_cursor = content_cell.lastCursorPosition()
            first_rect = self.editor.cursorRect(first_cursor)
            last_rect = self.editor.cursorRect(last_cursor)
            left = max(0, min(first_rect.left(), last_rect.left()) - 6)
            top = min(first_rect.top(), last_rect.top()) - 6
            bottom = max(first_rect.bottom(), last_rect.bottom()) + 6

            document_layout = self.editor.document().documentLayout()
            block = first_cursor.block()
            last_block = last_cursor.block()
            while block.isValid():
                block_cursor = QTextCursor(block)
                block_rect = self.editor.cursorRect(block_cursor)
                layout_rect = document_layout.blockBoundingRect(block)
                top = min(top, block_rect.top() - 6)
                bottom = max(bottom, block_rect.top() + layout_rect.height() + 6)
                if block == last_block:
                    break
                block = block.next()

            viewport = self.editor.viewport()
            right = viewport.width() - 8
            height = bottom - top
            if right <= left or height <= 0:
                return None
            if metadata is not None and metadata.cell_type in {"timeline", "tree"}:
                settings = _ensure_diagram_settings(metadata)
                if settings.display_height_px is not None:
                    height = max(float(settings.display_height_px), float(height))
            geometry = QRectF(left, top, right - left, height)
            if geometry.bottom() < 0 or geometry.top() > viewport.height():
                return None
            return geometry
        except (RuntimeError, SystemError):
            return None

    def _layout_diagram_preview_panel(self):
        if not hasattr(self, "diagram_preview_panel"):
            return
        geometry = self._diagram_cell_content_geometry(self._active_diagram_preview_table, self._active_cell_metadata)
        if geometry is None:
            self.diagram_preview_panel.hide()
            return
        self.diagram_preview_panel.setGeometry(
            int(round(geometry.left())),
            int(round(geometry.top())),
            int(round(geometry.width())),
            int(round(geometry.height())),
        )

    def _show_active_diagram_preview(self, table, metadata: NotebookCellMetadata, *, fit: bool = True):
        if metadata.cell_type not in {"timeline", "tree"}:
            self._hide_active_diagram_preview(reset_state=False)
            return

        settings_key = _diagram_settings_key(metadata.diagram_settings)
        if (
            metadata.cell_id != self._active_diagram_preview_cell_id
            or metadata.cell_type != self._active_diagram_preview_type
            or metadata.source != self._active_diagram_preview_source
            or settings_key != self._active_diagram_preview_settings_key
        ):
            _populate_diagram_scene(
                self.diagram_preview_scene,
                metadata.cell_type,
                metadata.source,
                metadata.diagram_settings,
                interactive=metadata.cell_type == "tree",
                on_settings_changed=self._on_active_preview_diagram_settings_changed if metadata.cell_type == "tree" else None,
            )
            if fit:
                self.diagram_preview_view.fit_to_scene()
            self._active_diagram_preview_cell_id = metadata.cell_id
            self._active_diagram_preview_type = metadata.cell_type
            self._active_diagram_preview_source = metadata.source
            self._active_diagram_preview_settings_key = settings_key

        self._active_diagram_preview_table = table
        self.diagram_preview_title.setText(
            "Timeline Preview" if metadata.cell_type == "timeline" else "Tree Preview"
        )
        self._layout_diagram_preview_panel()
        if not self.diagram_preview_panel.isHidden():
            self.diagram_preview_panel.raise_()
        elif self._diagram_cell_content_geometry(self._active_diagram_preview_table) is not None:
            self.diagram_preview_panel.show()
            self.diagram_preview_panel.raise_()

    def _on_active_preview_diagram_settings_changed(self, settings: DiagramSettings):
        self._apply_active_diagram_settings(settings, commit_immediately=False)

    def _hide_active_diagram_preview(self, *, reset_state: bool = True):
        if hasattr(self, "diagram_preview_panel"):
            self.diagram_preview_panel.hide()
        if reset_state:
            self._active_diagram_preview_cell_id = None
            self._active_diagram_preview_type = None
            self._active_diagram_preview_source = None
            self._active_diagram_preview_settings_key = None
            self._active_diagram_preview_table = None

    def _make_format_button(self, text: str, tooltip: str, handler):
        button = QToolButton(self.page)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.clicked.connect(handler)
        return button

    def _make_action_button(self, text: str, tooltip: str, handler):
        button = QToolButton(self.page)
        button.setText(text)
        button.setToolTip(tooltip)
        button.clicked.connect(handler)
        return button

    def _configure_icon_button(self, button: QToolButton, icon: QIcon):
        button.setText("")
        button.setIcon(icon)
        icon_extent = self.page.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        button.setIconSize(QSize(icon_extent, icon_extent))
        button.setMinimumWidth(30)
        button.setAutoRaise(True)

    def _make_toolbar_icon(self, kind: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#dbe7f5"))
        pen.setWidthF(1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind in {"align_left", "align_center", "align_right", "align_justify"}:
            left_edges = [2, 2, 2, 2]
            widths = [11, 9, 13, 8]
            if kind == "align_center":
                left_edges = [4, 5, 2, 6]
            elif kind == "align_right":
                left_edges = [5, 7, 1, 8]
            elif kind == "align_justify":
                left_edges = [2, 2, 2, 2]
                widths = [13, 13, 13, 13]
            for row, (left, width) in enumerate(zip(left_edges, widths)):
                y = 4 + row * 3.5
                painter.drawLine(left, int(y), left + width, int(y))
        elif kind == "bullet_list":
            for row in range(3):
                y = 4 + row * 5
                painter.setBrush(QColor("#dbe7f5"))
                painter.drawEllipse(2, y - 1, 3, 3)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(7, y, 15, y)
        elif kind == "number_list":
            font = painter.font()
            font.setPointSizeF(6.5)
            painter.setFont(font)
            painter.drawText(1, 7, "1.")
            painter.drawText(1, 13, "2.")
            painter.drawLine(7, 5, 15, 5)
            painter.drawLine(7, 11, 15, 11)
        elif kind == "hyperlink":
            path = QPainterPath()
            path.addRoundedRect(2.5, 7.0, 6.0, 4.0, 2.0, 2.0)
            path.addRoundedRect(9.5, 7.0, 6.0, 4.0, 2.0, 2.0)
            painter.drawPath(path)
            painter.drawLine(7, 9, 11, 9)
        elif kind == "image":
            painter.drawRoundedRect(2.0, 3.0, 14.0, 11.0, 1.8, 1.8)
            painter.drawEllipse(11.5, 5.0, 2.0, 2.0)
            painter.drawLine(4, 12, 8, 8)
            painter.drawLine(8, 8, 10, 10)
            painter.drawLine(10, 10, 14, 6)
        elif kind == "equation":
            font = painter.font()
            font.setPointSizeF(9.0)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), "x²")
        elif kind == "indent":
            painter.drawLine(6, 4, 15, 4)
            painter.drawLine(6, 8, 15, 8)
            painter.drawLine(6, 12, 15, 12)
            painter.drawLine(3, 9, 7, 5)
            painter.drawLine(3, 9, 7, 13)
        elif kind == "outdent":
            painter.drawLine(3, 4, 12, 4)
            painter.drawLine(3, 8, 12, 8)
            painter.drawLine(3, 12, 12, 12)
            painter.drawLine(15, 9, 11, 5)
            painter.drawLine(15, 9, 11, 13)
        elif kind == "code":
            font = painter.font()
            font.setPointSizeF(9.0)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), "</>")

        painter.end()
        return QIcon(pixmap)

    def _apply_toolbar_icons(self):
        self._configure_icon_button(self.link_button, self._make_toolbar_icon("hyperlink"))
        self._configure_icon_button(self.image_button, self._make_toolbar_icon("image"))
        self._configure_icon_button(self.equation_button, self._make_toolbar_icon("equation"))
        self._configure_icon_button(self.code_button, self._make_toolbar_icon("code"))
        self._configure_icon_button(self.bulleted_list_button, self._make_toolbar_icon("bullet_list"))
        self._configure_icon_button(self.numbered_list_button, self._make_toolbar_icon("number_list"))
        self._configure_icon_button(self.align_left_button, self._make_toolbar_icon("align_left"))
        self._configure_icon_button(self.align_center_button, self._make_toolbar_icon("align_center"))
        self._configure_icon_button(self.align_right_button, self._make_toolbar_icon("align_right"))
        self._configure_icon_button(self.align_justify_button, self._make_toolbar_icon("align_justify"))
        self._configure_icon_button(self.indent_button, self._make_toolbar_icon("indent"))
        self._configure_icon_button(self.outdent_button, self._make_toolbar_icon("outdent"))

    def _install_shortcuts(self):
        self._shortcuts.clear()
        self._bind_shortcut("Ctrl+B", self.bold_button.click, "Bold")
        self._bind_shortcut("Ctrl+I", self.italic_button.click, "Italic")
        self._bind_shortcut("Ctrl+U", self.underline_button.click, "Underline")
        self._bind_shortcut("Ctrl+K", self.link_button.click, "Insert hyperlink")
        self._bind_shortcut("Ctrl+Shift+L", self.bulleted_list_button.click, "Bullet list")
        self._bind_shortcut("Ctrl+Shift+7", self.numbered_list_button.click, "Numbered list")
        self._bind_shortcut("Ctrl+L", self.align_left_button.click, "Align left")
        self._bind_shortcut("Ctrl+E", self.align_center_button.click, "Align center")
        self._bind_shortcut("Ctrl+R", self.align_right_button.click, "Align right")
        self._bind_shortcut("Ctrl+J", self.align_justify_button.click, "Justify")
        self._bind_shortcut("Ctrl+M", self.indent_button.click, "Indent")
        self._bind_shortcut("Ctrl+Shift+M", self.outdent_button.click, "Outdent")
        self._bind_shortcut("Ctrl+`", self.code_button.click, "Inline code")
        self._bind_shortcut("Ctrl+Shift+P", self.image_button.click, "Insert picture")
        self._bind_shortcut("Alt+=", self.equation_button.click, "Insert equation")

        self.bold_button.setToolTip("Bold (Ctrl+B)")
        self.italic_button.setToolTip("Italic (Ctrl+I)")
        self.underline_button.setToolTip("Underline (Ctrl+U)")
        self.code_button.setToolTip("Inline code (Ctrl+`)")
        self.link_button.setToolTip("Insert hyperlink (Ctrl+K)")
        self.image_button.setToolTip("Insert picture (Ctrl+Shift+P)")
        self.image_resize_button.setToolTip("Resize selected image")
        self.equation_button.setToolTip("Insert equation (Alt+=)")
        self.bulleted_list_button.setToolTip("Bullet list (Ctrl+Shift+L)")
        self.numbered_list_button.setToolTip("Numbered list (Ctrl+Shift+7)")
        self.align_left_button.setToolTip("Align left (Ctrl+L)")
        self.align_center_button.setToolTip("Align center (Ctrl+E)")
        self.align_right_button.setToolTip("Align right (Ctrl+R)")
        self.align_justify_button.setToolTip("Justify (Ctrl+J)")
        self.indent_button.setToolTip("Indent (Ctrl+M)")
        self.outdent_button.setToolTip("Outdent (Ctrl+Shift+M)")

    def _bind_shortcut(self, key: str, handler, description: str):
        shortcut = QShortcut(QKeySequence(key), self.page)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.setWhatsThis(description)
        shortcut.activated.connect(handler)
        self._shortcuts.append(shortcut)
        return shortcut

    def _set_editor_enabled(self, enabled: bool):
        self.editor.setEnabled(enabled)
        for control in self._toolbar_controls:
            control.setEnabled(enabled)
        if not enabled:
            self._hide_active_diagram_preview()

    def _normalize_chapters(self, chapter_titles: list[str]) -> list[str]:
        normalized_titles: list[str] = []
        for chapter in chapter_titles:
            if not isinstance(chapter, str):
                continue
            normalized = chapter.strip()
            if not normalized:
                continue
            if any(saved.lower() == normalized.lower() for saved in normalized_titles):
                continue
            normalized_titles.append(normalized)
        return normalized_titles

    def _slugify_subject(self, value: str) -> str:
        """Generate a filesystem-safe slug from subject name, preserving emoji."""
        import unicodedata
        
        value = value.strip()
        if not value:
            return "subject"
        
        # Preserve emoji and alphanumeric, convert other problematic characters
        cleaned = []
        for ch in value.lower():
            if ch.isalnum():
                # ASCII letters and digits
                cleaned.append(ch)
            elif ord(ch) > 127:
                # Preserve emoji and other Unicode symbols
                category = unicodedata.category(ch)
                if category[0] in ('L', 'N', 'S', 'P') or category in ('Po', 'Pc'):
                    # Keep letters, numbers, symbols, and punctuation (including emoji)
                    cleaned.append(ch)
                else:
                    cleaned.append('_')
            elif ch in ('-', '_', '.'):
                # Keep safe punctuation
                cleaned.append(ch)
            else:
                cleaned.append('_')
        
        slug = ''.join(cleaned)
        while '__' in slug:
            slug = slug.replace('__', '_')
        return slug.strip('_.-') or 'subject'

    def _legacy_slugify_subject(self, value: str) -> str:
        value = value.strip()
        if not value:
            return "subject"

        import unicodedata

        cleaned: list[str] = []
        for ch in value.lower():
            if ch.isalnum():
                cleaned.append(ch)
            elif ord(ch) > 127:
                category = unicodedata.category(ch)
                if category[0] in ('L', 'N', 'S', 'P'):
                    cleaned.append(ch)
                else:
                    cleaned.append('_')
            else:
                cleaned.append('_')

        slug = ''.join(cleaned)
        while '__' in slug:
            slug = slug.replace('__', '_')
        slug = "_".join(part for part in slug.split("_") if part)
        return slug or "subject"

    def _subject_file_path(self, subject_name: str) -> Path:
        return self.storage_root / f"{self._slugify_subject(subject_name)}.json"

    def _subject_file_candidates(self, subject_name: str) -> list[Path]:
        primary = self._subject_file_path(subject_name)
        candidates = [primary]
        legacy = self.storage_root / f"{self._legacy_slugify_subject(subject_name)}.json"
        if legacy != primary:
            candidates.append(legacy)
        return candidates

    def _load_subject_payload(self, subject_name: str):
        payload = {
            "subject": subject_name,
            "selected_chapter": None,
            "notes": {},
        }
        loaded = None
        for subject_file in self._subject_file_candidates(subject_name):
            if not subject_file.exists():
                continue
            try:
                with subject_file.open("r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                break
            except (OSError, json.JSONDecodeError):
                continue

        if loaded is None:
            return payload

        if not isinstance(loaded, dict):
            return payload

        notes = loaded.get("notes", {})
        normalized_notes = {
            chapter: content
            for chapter, content in notes.items()
            if isinstance(chapter, str) and isinstance(content, str)
        }

        return {
            "subject": subject_name,
            "selected_chapter": loaded.get("selected_chapter"),
            "notes": normalized_notes,
        }

    def _save_subject_payload(self):
        if not self.subject_name:
            return

        payload = {
            "subject": self.subject_name,
            "selected_chapter": self.current_chapter,
            "notes": self._notes_by_chapter,
        }
        subject_file = self._subject_file_path(self.subject_name)
        try:
            subject_file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = subject_file.with_suffix(f"{subject_file.suffix}.tmp")
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            temp_path.replace(subject_file)
        except OSError:
            pass

    def _flush_storage_save(self):
        """Ensure all notebook data is persisted to disk. Called during app shutdown."""
        self._persist_current_editor_state(immediate=True)
        self._mark_subject_payload_dirty(immediate=True)

    def set_subject_structure(self, subject_name: str | None, chapter_titles: list[str]):
        self._persist_current_editor_state(immediate=True)

        self.subject_name = subject_name.strip() if isinstance(subject_name, str) and subject_name.strip() else None
        self.chapter_titles = self._normalize_chapters(chapter_titles)
        self.current_chapter = None
        self._notes_by_chapter = {}
        self._saved_selected_chapter = None

        if self.subject_name:
            payload = self._load_subject_payload(self.subject_name)
            self._notes_by_chapter = payload["notes"]
            saved_selected_chapter = payload.get("selected_chapter")
            if isinstance(saved_selected_chapter, str):
                self._saved_selected_chapter = saved_selected_chapter

        if self.chapter_titles:
            if isinstance(self._saved_selected_chapter, str):
                for chapter in self.chapter_titles:
                    if chapter.lower() == self._saved_selected_chapter.lower():
                        self.current_chapter = chapter
                        break

        self._refresh_chapter_tree()
        self._load_current_chapter_note()

    def focus_chapter(self, chapter_name: str):
        normalized = chapter_name.strip().lower()
        item = self._find_chapter_tree_item(normalized)
        if item is not None:
            self.chapter_list.setCurrentItem(item)

    def _split_leaf_path(self, chapter_path: str) -> tuple[str, str | None]:
        normalized = chapter_path.strip()
        if " / " not in normalized:
            return normalized, None
        chapter_title, subchapter_title = normalized.split(" / ", 1)
        return chapter_title.strip(), subchapter_title.strip() or None

    def _split_leaf_parts(self, chapter_path: str) -> list[str]:
        return [part.strip() for part in chapter_path.strip().split(" / ") if part.strip()]

    def _find_chapter_tree_item(self, normalized_path: str) -> QTreeWidgetItem | None:
        for index in range(self.chapter_list.topLevelItemCount()):
            item = self._find_tree_item_by_leaf_path(self.chapter_list.topLevelItem(index), normalized_path)
            if item is not None:
                return item
        return None

    def _find_tree_item_by_leaf_path(self, item: QTreeWidgetItem, normalized_path: str) -> QTreeWidgetItem | None:
        stored_path = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(stored_path, str) and stored_path.lower() == normalized_path:
            return item
        for child_index in range(item.childCount()):
            found = self._find_tree_item_by_leaf_path(item.child(child_index), normalized_path)
            if found is not None:
                return found
        return None

    def _refresh_chapter_tree(self):
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        for chapter_path in self.chapter_titles:
            self._ensure_leaf_path_item(chapter_path)
        self.chapter_list.blockSignals(False)

        self.chapter_status_label.setText(f"{len(self.chapter_titles)} chapters")
        self.chapter_title_label.setText("Chapters")

        self.chapter_list.blockSignals(True)
        if self.current_chapter is None:
            self.chapter_list.clearSelection()
            self.chapter_list.setCurrentItem(None)
            self.chapter_list.blockSignals(False)
            return

        item = self._find_chapter_tree_item(self.current_chapter.lower())
        if item is not None:
            self.chapter_list.setCurrentItem(item)
        self.chapter_list.blockSignals(False)

    def _ensure_leaf_path_item(self, chapter_path: str) -> QTreeWidgetItem | None:
        parts = self._split_leaf_parts(chapter_path)
        if not parts:
            return None

        parent_item: QTreeWidgetItem | None = None
        for depth, part in enumerate(parts):
            existing = self._find_child_item(parent_item, part)
            if existing is None:
                existing = QTreeWidgetItem([part])
                if parent_item is None:
                    self.chapter_list.addTopLevelItem(existing)
                    apply_font_to_item(existing, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                else:
                    parent_item.addChild(existing)
                    apply_font_to_item(existing, TreeFontConfig.QUIZ_SUBCHAPTER_SIZE)
                    parent_item.setExpanded(True)
            parent_item = existing

        if parent_item is not None:
            parent_item.setData(0, Qt.ItemDataRole.UserRole, chapter_path)
        return parent_item

    def _find_child_item(self, parent_item: QTreeWidgetItem | None, title: str) -> QTreeWidgetItem | None:
        count = self.chapter_list.topLevelItemCount() if parent_item is None else parent_item.childCount()
        for index in range(count):
            item = self.chapter_list.topLevelItem(index) if parent_item is None else parent_item.child(index)
            if item.text(0).lower() == title.lower():
                return item
        return None

    def _set_editor_html(self, html: str):
        self._loading_editor = True
        self.editor.setHtml(html)
        self._loading_editor = False
        self._sync_toolbar_from_cursor()

    def _load_current_chapter_note(self):
        if not self.subject_name:
            self._set_editor_enabled(False)
            self.page_context_label.setText("Select a subject to load its chapter notebook.")
            self._set_editor_html("")
            return

        if not self.current_chapter:
            self._set_editor_enabled(False)
            self.page_context_label.setText("Choose a chapter from the right panel.")
            self._set_editor_html("")
            return

        self._set_editor_enabled(True)
        self.page_context_label.setText(self.current_chapter)
        html = self._notes_by_chapter.get(self.current_chapter, "")
        self._set_editor_html(html)

    def _mark_subject_payload_dirty(self, *, immediate: bool = False):
        if not self.subject_name:
            return
        self._subject_payload_dirty = True
        if immediate:
            self._autosave_timer.stop()
            self._flush_pending_subject_save()
        else:
            self._autosave_timer.start()

    def _sync_current_editor_to_notes(self):
        if self._loading_editor or not self.subject_name or not self.current_chapter:
            return
        self._notes_by_chapter[self.current_chapter] = self.editor.toHtml()

    def _flush_pending_subject_save(self):
        if self._loading_editor or not self.subject_name:
            return
        if self._editor_state_dirty:
            self._sync_current_editor_to_notes()
            self._editor_state_dirty = False
        if not self._subject_payload_dirty:
            return
        self._save_subject_payload()
        self._subject_payload_dirty = False

    def _persist_current_editor_state(self, *, immediate: bool = False):
        if self._loading_editor or not self.subject_name or not self.current_chapter:
            return
        self._editor_state_dirty = True
        self._mark_subject_payload_dirty(immediate=immediate)

    def _on_chapter_changed(self):
        self._persist_current_editor_state(immediate=True)

        current_item = self.chapter_list.currentItem()
        chapter_path = current_item.data(0, Qt.ItemDataRole.UserRole) if current_item is not None else None
        self.current_chapter = chapter_path if isinstance(chapter_path, str) else None

        self._mark_subject_payload_dirty(immediate=True)
        self._load_current_chapter_note()

    def _on_editor_changed(self):
        if self._loading_editor or self._rendering_notebook_cell:
            return
        if self._active_cell_table is not None and self._active_cell_metadata is not None:
            updated = self._sync_notebook_cell_metadata_from_table(
                self._active_cell_table,
                self._active_cell_metadata,
            )
            self._active_cell_metadata = updated
            if (
                self._context_cell_metadata is not None
                and self._context_cell_metadata.cell_id == updated.cell_id
            ):
                self._context_cell_metadata = updated
        self._persist_current_editor_state()

    def _merge_format_on_selection(self, char_format: QTextCharFormat):
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            self.editor.setTextCursor(cursor)
        cursor.mergeCharFormat(char_format)
        self.editor.mergeCurrentCharFormat(char_format)

    def _merge_block_format(self, block_format: QTextBlockFormat):
        cursor = self.editor.textCursor()
        cursor.mergeBlockFormat(block_format)
        self.editor.mergeCurrentCharFormat(self.editor.currentCharFormat())

    def _set_alignment(self, alignment: Qt.AlignmentFlag):
        if not self.editor.isEnabled():
            return
        self.editor.setAlignment(alignment)
        self._sync_toolbar_from_cursor()

    def _apply_font_family(self, font: QFont):
        if self._updating_toolbar or not self.editor.isEnabled():
            return
        char_format = QTextCharFormat()
        char_format.setFontFamilies([font.family()])
        self._merge_format_on_selection(char_format)

    def _apply_font_size(self, text: str):
        if self._updating_toolbar or not self.editor.isEnabled():
            return
        try:
            size = float(text)
        except ValueError:
            return
        if size <= 0:
            return
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        self._merge_format_on_selection(char_format)

    def _toggle_bold(self):
        if not self.editor.isEnabled():
            return
        char_format = QTextCharFormat()
        weight = QFont.Weight.Bold if self.bold_button.isChecked() else QFont.Weight.Normal
        char_format.setFontWeight(weight)
        self._merge_format_on_selection(char_format)

    def _toggle_italic(self):
        if not self.editor.isEnabled():
            return
        char_format = QTextCharFormat()
        char_format.setFontItalic(self.italic_button.isChecked())
        self._merge_format_on_selection(char_format)

    def _toggle_underline(self):
        if not self.editor.isEnabled():
            return
        char_format = QTextCharFormat()
        char_format.setFontUnderline(self.underline_button.isChecked())
        self._merge_format_on_selection(char_format)

    def _insert_code(self):
        if not self.editor.isEnabled():
            return

        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        if selected_text:
            cursor.insertText(f"`{selected_text}`")
            return

        cursor.insertText("``")
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.editor.setTextCursor(cursor)

    def _insert_table(self):
        if not self.editor.isEnabled():
            return

        rows, accepted = QInputDialog.getInt(self.page, "Insert Table", "Rows:", 2, 1, 20)
        if not accepted:
            return
        columns, accepted = QInputDialog.getInt(self.page, "Insert Table", "Columns:", 2, 1, 10)
        if not accepted:
            return

        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setCellPadding(6)
        fmt.setCellSpacing(0)
        fmt.setBorderBrush(QColor("#31435f"))
        self.editor.textCursor().insertTable(rows, columns, fmt)

    def _insert_markdown_cell(self):
        self._create_notebook_cell("markdown")

    def _insert_code_cell(self):
        self._create_notebook_cell("code")

    def _insert_timeline_cell(self):
        self._create_notebook_cell("timeline")

    def _insert_tree_cell(self):
        self._create_notebook_cell("tree")

    def _create_notebook_cell(self, cell_type: str, *, initial_source: str = ""):
        if not self.editor.isEnabled():
            return

        source = initial_source
        is_editing = cell_type in {"code", "markdown"}
        diagram_settings = None
        rendered_html = ""
        if cell_type not in {"code", "markdown"}:
            dialog = DiagramEditorDialog(
                self.page,
                diagram_type=cell_type,
                initial_source=initial_source,
                initial_settings=_default_diagram_settings(),
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            source = dialog.source_text()
            diagram_settings = dialog.diagram_settings()
            rendered_html = _render_diagram_html(cell_type, source, diagram_settings)

        metadata = NotebookCellMetadata(
            cell_id=f"{cell_type}-{uuid.uuid4().hex}",
            cell_type=cell_type,
            source=source,
            rendered_html=rendered_html,
            is_editing=is_editing,
            diagram_settings=diagram_settings,
        )
        table = self._insert_notebook_cell_table(metadata)
        self._active_cell_table = table
        self._set_active_cell_metadata(metadata)
        self._persist_current_editor_state()

    def _insert_notebook_cell_table(self, metadata: NotebookCellMetadata):
        cursor = self.editor.textCursor()
        table_format = QTextTableFormat()
        table_format.setBorder(1)
        table_format.setCellPadding(0)
        table_format.setCellSpacing(0)
        table_format.setBorderBrush(QColor("#31435f"))
        table_format.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        table_format.setColumnWidthConstraints(
            [
                QTextLength(QTextLength.Type.FixedLength, 64),
                QTextLength(QTextLength.Type.PercentageLength, 100),
            ]
        )
        table = cursor.insertTable(1, 2, table_format)
        self._render_notebook_cell_table(
            table,
            metadata,
            selected=metadata.cell_type in NOTEBOOK_CELL_TYPES,
        )
        self.editor.setTextCursor(self._table_cell_cursor_at_end(table, 0, 1))
        return table

    def _render_notebook_cell_table(self, table, metadata: NotebookCellMetadata, *, selected: bool = False):
        if not self._table_is_valid(table):
            return
        self._rendering_notebook_cell = True
        blocker = QSignalBlocker(self.editor)
        metadata_href = _encode_notebook_cell_metadata(metadata)
        cell_label = _notebook_cell_label(metadata.cell_type)
        accent = {
            "code": "#f4d06f",
            "markdown": "#7ab0ff",
            "timeline": "#7ce0c3",
            "tree": "#b09dff",
        }.get(metadata.cell_type, "#7ab0ff")
        is_source_cell = metadata.cell_type in {"code", "markdown"}
        is_editing = is_source_cell and metadata.is_editing
        block_background = "#10233a" if is_editing else ("#08101d" if selected else "#101a2b")
        block_border = accent if is_editing else ("#4b6486" if selected else "#243652")
        wrapper_border = "#88bfff" if is_editing else ("#617ea3" if selected else "#31435f")
        gutter_background = "#122338" if is_editing else ("#0c1524" if selected else "#131f31")
        button_background = "#163254" if selected or is_editing else "#122338"
        diagram_settings = _ensure_diagram_settings(metadata) if metadata.cell_type in {"timeline", "tree"} else None
        diagram_min_height = (
            f" min-height:{int(diagram_settings.display_height_px)}px;"
            if diagram_settings is not None and diagram_settings.display_height_px is not None
            else ""
        )

        source_html = html.escape(metadata.source.strip() or "")
        if is_editing and metadata.cell_type == "code":
            preview_html = (
                f"<div style=\"background:{block_background}; border:1px solid {block_border}; border-radius:0; "
                "padding:12px;\">"
                f"<pre style=\"margin:0; white-space:pre-wrap; color:#f9fbff; font-family:'Cascadia Code','Consolas',monospace;\">"
                f"{source_html or '<br>'}</pre>"
                "</div>"
            )
        elif is_editing and metadata.cell_type == "markdown":
            preview_html = (
                f"<div style=\"background:{block_background}; border:1px solid {block_border}; border-radius:0; "
                "padding:12px;\">"
                f"<pre style=\"margin:0; white-space:pre-wrap; color:#edf4ff; font-family:'Cascadia Code','Consolas',monospace;\">"
                f"{source_html or '<br>'}</pre>"
                "</div>"
            )
        elif metadata.cell_type == "code":
            preview_html = (
                f"<div style=\"background:{block_background}; border:1px solid {block_border}; border-radius:0; padding:12px;\">"
                f"<pre style=\"margin:0; white-space:pre-wrap; color:#edf4ff;\">{source_html or '# Write Python here'}</pre>"
                f"{metadata.rendered_html}"
                "</div>"
            )
        elif metadata.cell_type == "markdown":
            preview_html = (
                f"<div style=\"background:{block_background}; border:1px solid {block_border}; border-radius:0; padding:12px;\">"
                f"{metadata.rendered_html or '<p style=\"color:#93a8c7;\"><i>Run the markdown cell to render it.</i></p>'}"
                "</div>"
            )
        else:
            preview_html = (
                f"<div style=\"background:{block_background}; border:1px solid {block_border}; border-radius:0; padding:12px;{diagram_min_height}\">"
                f"{metadata.rendered_html or '<p style=\"color:#93a8c7;\"><i>Open or run the diagram cell to render it.</i></p>'}"
                "</div>"
            )

        self._set_table_cell_html(
            table,
            0,
            0,
            (
                f'<div style="background:{gutter_background}; min-height:96px; padding:10px 6px; text-align:center;">'
                f'<div style="width:48px; min-height:76px; margin:0 auto; border:1px solid {wrapper_border}; '
                f'background:{button_background}; box-shadow: inset 0 1px 0 {block_border};">'
                "<p style=\"margin:28px 0 0 0; text-align:center;\">"
                f'<span style="color:{accent}; font-size:8pt; font-weight:700; letter-spacing:0.08em;">{cell_label}</span>'
                "</p>"
                "</div>"
                f'<a href="{metadata_href}" '
                f'style="font-size:0; line-height:0; color:{gutter_background}; text-decoration:none;">&#8203;</a>'
                "</div>"
            ),
        )
        self._set_table_cell_html(
            table,
            0,
            1,
            (
                f'<div style="background:{block_background}; border:1px solid {wrapper_border}; padding:4px;">'
                f"{preview_html}"
                "</div>"
            ),
        )
        del blocker
        self._rendering_notebook_cell = False

    def _table_cell_cursor_at_end(self, table, row: int, column: int):
        if not self._table_is_valid(table):
            return self.editor.textCursor()
        return table.cellAt(row, column).lastCursorPosition()

    def _table_is_valid(self, table) -> bool:
        if table is None:
            return False
        try:
            return table.rows() > 0 and table.columns() > 0
        except (RuntimeError, SystemError):
            return False

    def _table_cell_html(self, table, row: int, column: int) -> str:
        if not self._table_is_valid(table):
            return ""
        try:
            cell = table.cellAt(row, column)
            cursor = cell.firstCursorPosition()
            end_position = cell.lastCursorPosition().position()
            if end_position < cursor.position():
                return ""
            cursor.setPosition(end_position, QTextCursor.MoveMode.KeepAnchor)
            return cursor.selection().toHtml()
        except (RuntimeError, SystemError):
            return ""

    def _set_table_cell_html(self, table, row: int, column: int, content_html: str):
        if not self._table_is_valid(table):
            return
        cell = table.cellAt(row, column)
        cursor = cell.firstCursorPosition()
        cursor.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
        if cursor.hasSelection():
            cursor.removeSelectedText()
        cursor.insertHtml(content_html)

    def _extract_notebook_cell_source(self, table) -> str:
        if not self._table_is_valid(table):
            return ""
        source_cell = table.cellAt(0, 1)
        cursor = source_cell.firstCursorPosition()
        cursor.setPosition(source_cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
        return cursor.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")

    def _sync_notebook_cell_metadata_from_table(self, table, metadata: NotebookCellMetadata) -> NotebookCellMetadata:
        if not self._table_is_valid(table):
            return metadata
        if metadata.cell_type not in {"code", "markdown"} or not metadata.is_editing:
            return metadata
        source = self._extract_notebook_cell_source(table)
        if source == metadata.source:
            return metadata
        return NotebookCellMetadata(
            cell_id=metadata.cell_id,
            cell_type=metadata.cell_type,
            source=source,
            rendered_html=metadata.rendered_html,
            is_editing=True,
            diagram_settings=metadata.diagram_settings,
        )

    def _current_notebook_cell_context(self):
        table = self.editor.textCursor().currentTable()
        if not self._table_is_valid(table) or table.rows() < 1 or table.columns() < 2:
            return None

        metadata = _decode_notebook_cell_metadata_from_html(self._table_cell_html(table, 0, 0))
        if metadata is None:
            return None
        return table, metadata

    def _run_notebook_cell(self, table, metadata: NotebookCellMetadata):
        metadata = self._sync_notebook_cell_metadata_from_table(table, metadata)
        diagram_settings = (
            _normalized_diagram_settings(metadata.cell_type, metadata.source, metadata.diagram_settings)
            if metadata.cell_type in {"timeline", "tree"}
            else metadata.diagram_settings
        )
        if metadata.cell_type == "code":
            rendered_html = _render_code_output_html(metadata.source)
        elif metadata.cell_type == "markdown":
            rendered_html = _render_markdown_cell_html(metadata.source)
        else:
            rendered_html = _render_diagram_html(
                metadata.cell_type,
                metadata.source,
                diagram_settings,
            )

        updated = NotebookCellMetadata(
            cell_id=metadata.cell_id,
            cell_type=metadata.cell_type,
            source=metadata.source,
            rendered_html=rendered_html,
            is_editing=False,
            diagram_settings=diagram_settings,
        )
        self._render_notebook_cell_table(table, updated, selected=False)
        self._active_cell_table = table
        self._set_active_cell_metadata(updated)
        self.editor.setTextCursor(self._table_cell_cursor_at_end(table, 0, 1))
        self._persist_current_editor_state()

    def _edit_notebook_cell(self, table, metadata: NotebookCellMetadata):
        metadata = self._sync_notebook_cell_metadata_from_table(table, metadata)
        if metadata.cell_type in {"code", "markdown"}:
            updated = NotebookCellMetadata(
                cell_id=metadata.cell_id,
                cell_type=metadata.cell_type,
                source=metadata.source,
                rendered_html=metadata.rendered_html,
                is_editing=True,
                diagram_settings=metadata.diagram_settings,
            )
            self._render_notebook_cell_table(table, updated, selected=True)
            self._active_cell_table = table
            self._set_active_cell_metadata(updated)
            self._context_cell_table = table
            self._context_cell_metadata = updated
            self.editor.setTextCursor(self._table_cell_cursor_at_end(table, 0, 1))
            self._persist_current_editor_state()
            return
        else:
            dialog = DiagramEditorDialog(
                self.page,
                diagram_type=metadata.cell_type,
                initial_source=metadata.source,
                initial_settings=_ensure_diagram_settings(metadata),
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            source = dialog.source_text()
            settings = dialog.diagram_settings()

        updated = NotebookCellMetadata(
            cell_id=metadata.cell_id,
            cell_type=metadata.cell_type,
            source=source,
            rendered_html=metadata.rendered_html,
            is_editing=metadata.is_editing,
            diagram_settings=settings if metadata.cell_type in {"timeline", "tree"} else metadata.diagram_settings,
        )
        self._run_notebook_cell(table, updated)

    def _on_editor_anchor_activated(self, href: str):
        decoded = _decode_notebook_cell_action_href(href)
        if decoded is None:
            return

        action, metadata = decoded
        context = self._current_notebook_cell_context()
        if context is None:
            table = self._active_cell_table
            active_metadata = self._active_cell_metadata
            if table is None or active_metadata is None or active_metadata.cell_id != metadata.cell_id:
                return
        else:
            table, active_metadata = context

        if action == "run":
            self._run_notebook_cell(table, metadata)
        elif action == "edit":
            self._edit_notebook_cell(table, metadata)
        self._update_context_action_bar()

    def _export_notebook(self):
        if not self.subject_name:
            QMessageBox.information(self.page, "Export Notebook", "Select a subject first.")
            return

        default_name = f"{self._slugify_subject(self.subject_name)}_notebook.html"
        file_path, _ = QFileDialog.getSaveFileName(
            self.page,
            "Export Notebook",
            str(self.storage_root / default_name),
            "HTML Files (*.html);;All Files (*)",
        )
        if not file_path:
            return

        self._persist_current_editor_state()
        sections: list[str] = [
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(self.subject_name)} Notebook</title>"
            "<style>body{font-family:'Segoe UI',sans-serif;background:#0f1728;color:#edf4ff;padding:24px;} "
            "h1,h2{color:#7ab0ff;} section{margin-bottom:32px;} table{border-collapse:collapse;} "
            "td,th{border:1px solid #31435f;padding:6px;vertical-align:top;} a{color:#7ab0ff;}</style></head><body>"
        ]
        sections.append(f"<h1>{html.escape(self.subject_name)} Notebook</h1>")
        chapter_names = [self.current_chapter] if self.current_chapter else list(self.chapter_titles)
        seen: set[str] = set()
        for chapter in chapter_names:
            if not isinstance(chapter, str) or not chapter.strip():
                continue
            key = chapter.lower()
            if key in seen:
                continue
            seen.add(key)
            sections.append(f"<section><h2>{html.escape(chapter)}</h2>")
            sections.append(self._notes_by_chapter.get(chapter, "<p><i>No notes.</i></p>"))
            sections.append("</section>")
        sections.append("</body></html>")
        try:
            Path(file_path).write_text("".join(sections), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self.page, "Export Failed", str(exc))
            return
        QMessageBox.information(self.page, "Export Complete", f"Notebook exported to:\n{file_path}")

    def _insert_picture(self):
        if not self.editor.isEnabled():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self.page,
            "Insert Picture",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)",
        )
        if not file_path:
            return

        image_path = Path(file_path)
        try:
            # Load image and scale it to the desired width BEFORE embedding
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                raise OSError("Failed to load image")
        except Exception as exc:
            QMessageBox.warning(self.page, "Insert Picture Failed", str(exc))
            return

        mime_type, _ = mimetypes.guess_type(image_path.name)
        if not isinstance(mime_type, str) or not mime_type.startswith("image/"):
            mime_type = "image/png"

        # Show size and wrapping dialog
        size_dialog = ImageSizeDialog(self.page, default_width=300)
        if size_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        width = size_dialog.get_width()
        wrap_mode = size_dialog.get_wrap_mode()
        
        # Scale image to target width BEFORE embedding (reduces file size)
        if pixmap.width() > width:
            scaled_pixmap = pixmap.scaledToWidth(
                width, Qt.TransformationMode.SmoothTransformation
            )
        else:
            scaled_pixmap = pixmap
        
        # Encode the scaled image as PNG
        img_buffer = QBuffer()
        img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
        scaled_pixmap.save(img_buffer, "PNG")
        img_data = img_buffer.data()
        encoded_image = base64.b64encode(img_data).decode("ascii")

        # Build CSS style based on wrapping mode
        if wrap_mode == "left":
            style = f'style="float: left;"'
        elif wrap_mode == "right":
            style = f'style="float: right;"'
        elif wrap_mode == "center":
            # For center: use text-align since display:block gets stripped by QTextEdit
            style = f'style="text-align: center;"'
        else:  # none - inline
            style = f'style="vertical-align: middle;"'

        alt_text = html.escape(image_path.stem)
        
        # Add wrap mode marker to title (QTextEdit preserves title attribute)
        # Using Unicode markers: ◈ = center, ◊ = left, ◆ = right, (none) = inline
        wrap_marker = {
            "left": "◊",
            "right": "◆", 
            "center": "◈",
            "none": ""
        }.get(wrap_mode, "")
        
        title = f"Double-click to resize{wrap_marker}"
        
        image_html = (
            f'<img src="data:{mime_type};base64,{encoded_image}" '
            f'width="{width}" '
            f'{style} '
            f'alt="{alt_text}" '
            f'title="{title}">'
        )
        self.editor.textCursor().insertHtml(image_html)

    def _resize_selected_image(self):
        """Resize the image at the current cursor position using an interactive editor."""
        if not self.editor.isEnabled():
            return

        cursor = self.editor.textCursor()
        html = self.editor.toHtml()
        
        # Extract image info from HTML using more flexible regex
        import re
        # Match img tags more flexibly (attributes can be in any order)
        img_pattern = r'<img\s+([^>]*?)src="([^"]*?)"([^>]*?)>'
        matches = list(re.finditer(img_pattern, html, re.IGNORECASE | re.DOTALL))
        
        if not matches:
            QMessageBox.information(self.page, "No Image", "No images found in document. Please insert an image first.")
            return
        
        # Try to find image near cursor position, otherwise use the last one
        match = None
        cursor_pos = cursor.position()
        cursor_in_block = cursor.positionInBlock()
        
        # Find match closest to cursor
        for m in matches:
            match_start = m.start()
            # If we find a match at or near cursor position, use it
            if match_start <= html.find(cursor.block().text()) + 500:  # Rough proximity check
                match = m
                break
        
        # If no nearby match found, use the last one
        if match is None:
            match = matches[-1]
        
        # Extract the full img tag
        img_tag = match.group(0)
        
        # Extract src using separate regex
        src_match = re.search(r'src="([^"]*?)"', img_tag, re.IGNORECASE)
        if not src_match:
            QMessageBox.warning(self.page, "Parse Error", "Could not find image source.")
            return
        src = src_match.group(1)
        
        # Extract width attribute (this is more reliable than CSS style width)
        width_match = re.search(r'width="?(\d+)"?', img_tag, re.IGNORECASE)
        current_width = int(width_match.group(1)) if width_match else 300
        
        # Extract style
        style_match = re.search(r'style="([^"]*?)"', img_tag, re.IGNORECASE)
        style = style_match.group(1) if style_match else ""
        
        # Extract alt
        alt_match = re.search(r'alt="([^"]*?)"', img_tag, re.IGNORECASE)
        alt = alt_match.group(1) if alt_match else "image"
        
        # Extract wrap mode from title marker (QTextEdit preserves title attribute)
        # Markers: ◈ = center, ◊ = left, ◆ = right, (none) = inline
        title_match = re.search(r'title="([^"]*?)"', img_tag, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""
        
        # Check for wrap mode markers in title
        wrap_mode = "none"  # default
        if "◈" in title:
            wrap_mode = "center"
        elif "◊" in title:
            wrap_mode = "left"
        elif "◆" in title:
            wrap_mode = "right"
        else:
            # Fallback: detect from CSS (for images without markers)
            if "float: left" in style:
                wrap_mode = "left"
            elif "float: right" in style:
                wrap_mode = "right"
            elif "text-align: center" in style or "display: block" in style:
                wrap_mode = "center"
            else:
                wrap_mode = "none"  # inline
        
        # Extract base64 image data
        pixmap = None
        if src.startswith("data:"):
            try:
                # Parse data URL: data:image/png;base64,<data>
                header, data = src.split(",", 1)
                image_data = base64.b64decode(data)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                if pixmap.isNull():
                    raise ValueError("Failed to load pixmap from data")
            except Exception as exc:
                QMessageBox.warning(self.page, "Load Image Failed", f"Could not load image: {exc}")
                return
        else:
            QMessageBox.warning(self.page, "Unsupported Image", "Only embedded base64 images are supported.")
            return
        
        # Show image editor dialog
        editor_dialog = ImageEditorDialog(self.page, pixmap)
        if editor_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        # Get the edited pixmap
        edited_pixmap = editor_dialog.get_edited_pixmap()
        
        # Re-encode to base64
        try:
            img_buffer = QBuffer()
            img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
            edited_pixmap.save(img_buffer, "PNG")
            img_data = img_buffer.data()
            encoded_image = base64.b64encode(img_data).decode("ascii")
        except Exception as exc:
            QMessageBox.warning(self.page, "Encode Image Failed", f"Could not encode image: {exc}")
            return
        
        # Extract MIME type
        mime_type = "image/png"
        if src.startswith("data:"):
            mime_header = src.split(",")[0]
            if "image/" in mime_header:
                mime_match = re.search(r'image/[a-z]+', mime_header)
                if mime_match:
                    mime_type = mime_match.group(0)
        
        # Build new style (without width, since we'll use the width attribute)
        if wrap_mode == "left":
            new_style = f'style="float: left; margin: 8px 12px 8px 0; cursor: move;"'
        elif wrap_mode == "right":
            new_style = f'style="float: right; margin: 8px 0 8px 12px; cursor: move;"'
        elif wrap_mode == "center":
            new_style = f'style="display: block; margin: 8px auto; cursor: move;"'
        else:  # none - inline
            new_style = f'style="margin: 2px 4px; vertical-align: middle; cursor: move;"'
        
        # Build new img tag with width attribute and data-wrap
        new_width = edited_pixmap.width()
        new_img = (
            f'<img src="data:{mime_type};base64,{encoded_image}" '
            f'width="{new_width}" '
            f'{new_style} '
            f'alt="{alt}" '
            f'data-wrap="{wrap_mode}" '
            'title="Double-click to resize or change wrapping">'
        )
        
        # Replace old img tag with new one in HTML
        old_img = match.group(0)
        new_html = html.replace(old_img, new_img)
        
        # Restore HTML without losing formatting
        doc = self.editor.document()
        doc.setHtml(new_html)
        self.editor.setTextCursor(cursor)

    def _equation_cursor_info(self):
        document = self.editor.document()
        current_cursor = self.editor.textCursor()
        max_position = max(0, document.characterCount() - 1)
        candidate_positions = []
        for position in (
            current_cursor.position(),
            max(0, current_cursor.position() - 1),
            min(max_position, current_cursor.position() + 1),
        ):
            if position not in candidate_positions:
                candidate_positions.append(position)

        for position in candidate_positions:
            probe = QTextCursor(document)
            probe.setPosition(position)
            fmt = probe.charFormat()
            href = fmt.anchorHref() if fmt.isAnchor() else ""
            metadata = _decode_equation_metadata(href)
            if metadata is None or not fmt.isImageFormat():
                continue

            replacement_cursor = QTextCursor(document)
            replacement_cursor.setPosition(position)
            if replacement_cursor.position() > 0:
                replacement_cursor.movePosition(
                    QTextCursor.MoveOperation.Left,
                    QTextCursor.MoveMode.KeepAnchor,
                    1,
                )
                return replacement_cursor, metadata

        return None

    def _insert_equation(self):
        if not self.editor.isEnabled():
            return

        current_equation = self._equation_cursor_info()
        if current_equation is not None:
            replacement_cursor, metadata = current_equation
            initial_expression = metadata.latex
            initial_options = metadata.to_render_options()
        else:
            replacement_cursor = None
            metadata = None
            initial_expression = self.editor.textCursor().selectedText().strip()
            initial_options = None

        dialog = EquationBuilderDialog(
            self.page,
            initial_expression=initial_expression,
            initial_options=initial_options,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        equation_html = dialog.equation_html()
        if not equation_html:
            QMessageBox.warning(
                self.page,
                "Equation Not Inserted",
                "The LaTeX expression could not be rendered. Check the preview window for errors.",
            )
            return

        target_cursor = replacement_cursor if replacement_cursor is not None else self.editor.textCursor()
        if replacement_cursor is not None:
            target_cursor.removeSelectedText()
        target_cursor.insertHtml(equation_html)
        self.editor.setTextCursor(target_cursor)
        self._persist_current_editor_state()

    def _rerender_current_equation(self):
        current_equation = self._equation_cursor_info()
        if current_equation is None:
            return
        replacement_cursor, metadata = current_equation
        try:
            payload = render_latex_equation_payload(metadata.latex, metadata.to_render_options())
        except Exception as exc:
            QMessageBox.warning(self.page, "Equation Render Failed", str(exc))
            return
        replacement_cursor.removeSelectedText()
        replacement_cursor.insertHtml(_build_equation_insertion_html(metadata, payload))
        self.editor.setTextCursor(replacement_cursor)
        self._persist_current_editor_state()

    def _edit_current_equation(self):
        self._insert_equation()

    def _apply_bulleted_list(self):
        if not self.editor.isEnabled():
            return

        cursor = self.editor.textCursor()
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.Style.ListDisc)
        cursor.createList(list_format)

    def _apply_numbered_list(self):
        if not self.editor.isEnabled():
            return

        cursor = self.editor.textCursor()
        list_format = QTextListFormat()
        list_format.setStyle(QTextListFormat.Style.ListDecimal)
        cursor.createList(list_format)

    def _align_left(self):
        self._set_alignment(Qt.AlignmentFlag.AlignLeft)

    def _align_center(self):
        self._set_alignment(Qt.AlignmentFlag.AlignHCenter)

    def _align_right(self):
        self._set_alignment(Qt.AlignmentFlag.AlignRight)

    def _align_justify(self):
        self._set_alignment(Qt.AlignmentFlag.AlignJustify)

    def _indent_block(self):
        if not self.editor.isEnabled():
            return

        block_format = self.editor.textCursor().blockFormat()
        block_format.setIndent(block_format.indent() + 1)
        self._merge_block_format(block_format)

    def _outdent_block(self):
        if not self.editor.isEnabled():
            return

        block_format = self.editor.textCursor().blockFormat()
        block_format.setIndent(max(0, block_format.indent() - 1))
        self._merge_block_format(block_format)

    def _insert_hyperlink(self):
        if not self.editor.isEnabled():
            return

        url, accepted = QInputDialog.getText(self.page, "Insert Hyperlink", "Link URL:")
        if not accepted:
            return

        normalized_url = url.strip()
        if not normalized_url:
            QMessageBox.information(self.page, "Missing URL", "Enter a link URL first.")
            return

        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText().strip()
        if not selected_text:
            selected_text, accepted = QInputDialog.getText(
                self.page,
                "Insert Hyperlink",
                "Link text:",
            )
            if not accepted:
                return
            selected_text = selected_text.strip()

        if not selected_text:
            QMessageBox.information(self.page, "Missing Text", "Enter text for the hyperlink.")
            return

        link_format = QTextCharFormat()
        link_format.setAnchor(True)
        link_format.setAnchorHref(normalized_url)
        link_format.setFontUnderline(True)
        cursor.insertText(selected_text, link_format)

    def _sync_toolbar_from_cursor(self):
        if self._rendering_notebook_cell:
            return
        self._sync_toolbar_from_format(self.editor.currentCharFormat())
        self._update_context_action_bar()

    def _update_context_action_bar(self):
        previous_table = self._active_cell_table
        previous_metadata = self._active_cell_metadata
        if self._table_is_valid(previous_table) and previous_metadata is not None:
            previous_metadata = self._sync_notebook_cell_metadata_from_table(previous_table, previous_metadata)
        else:
            previous_table = None
            previous_metadata = None
        self._context_action_kind = None
        self._context_cell_table = None
        self._context_cell_metadata = None
        self._context_equation_info = None
        self._active_cell_table = None
        self._active_cell_metadata = None

        if not self.editor.isEnabled():
            if self._table_is_valid(previous_table) and previous_metadata is not None:
                self._render_notebook_cell_table(previous_table, previous_metadata, selected=False)
            self._hide_active_diagram_preview()
            self.context_action_bar.hide()
            return

        cell_context = self._current_notebook_cell_context()
        if cell_context is not None:
            table, metadata = cell_context
            metadata = self._sync_notebook_cell_metadata_from_table(table, metadata)
            if (
                self._table_is_valid(previous_table)
                and previous_metadata is not None
                and previous_metadata.cell_id != metadata.cell_id
            ):
                self._render_notebook_cell_table(previous_table, previous_metadata, selected=False)
            should_highlight = metadata.cell_type in NOTEBOOK_CELL_TYPES
            if should_highlight and (
                previous_metadata is None
                or previous_metadata.cell_id != metadata.cell_id
                or previous_metadata.is_editing != metadata.is_editing
            ):
                self._render_notebook_cell_table(table, metadata, selected=True)
            self._context_action_kind = "cell"
            self._context_cell_table = table
            self._context_cell_metadata = metadata
            self._active_cell_table = table
            self._active_cell_metadata = metadata
            if not self._table_is_valid(table):
                self._hide_active_diagram_preview()
                self.context_action_bar.hide()
                return
            gutter_cursor = table.cellAt(0, 0).firstCursorPosition()
            gutter_rect = self.editor.cursorRect(gutter_cursor)
            if metadata.cell_type in {"timeline", "tree"}:
                self._show_active_diagram_preview(table, metadata)
                self.context_run_button.setText("Fit")
                self.context_run_button.setToolTip("Fit the active diagram to the preview window")
                self.context_edit_button.setToolTip("Edit the active diagram")
            else:
                self._hide_active_diagram_preview()
                self.context_run_button.setText("Run")
                self.context_run_button.setToolTip("Run")
                self.context_edit_button.setToolTip("Edit")
            self.context_edit_button.setText("Edit")
            self.context_action_bar.adjustSize()
            self.context_action_bar.move(gutter_rect.left() + 3, max(6, gutter_rect.top() + 8))
            self.context_action_bar.show()
            self.context_action_bar.raise_()
            return

        if self._table_is_valid(previous_table) and previous_metadata is not None:
            self._render_notebook_cell_table(previous_table, previous_metadata, selected=False)
        self._hide_active_diagram_preview()

        equation_context = self._equation_cursor_info()
        if equation_context is not None:
            self._context_action_kind = "equation"
            self._context_equation_info = equation_context
            rect = self.editor.cursorRect()
            self.context_run_button.setText("Run")
            self.context_edit_button.setText("Edit")
            self.context_run_button.setToolTip("Run")
            self.context_edit_button.setToolTip("Edit")
            self.context_action_bar.adjustSize()
            self.context_action_bar.move(4, max(6, rect.top() + 4))
            self.context_action_bar.show()
            self.context_action_bar.raise_()
            return

        self._hide_active_diagram_preview()
        self.context_action_bar.hide()

    def _run_context_action(self):
        if self._context_action_kind == "cell" and self._context_cell_table is not None and self._context_cell_metadata is not None:
            if self._context_cell_metadata.cell_type in {"timeline", "tree"}:
                self.diagram_preview_view.fit_to_scene()
            else:
                self._run_notebook_cell(self._context_cell_table, self._context_cell_metadata)
            self._update_context_action_bar()
        elif self._context_action_kind == "equation":
            self._rerender_current_equation()
            self._update_context_action_bar()

    def _edit_context_action(self):
        if self._context_action_kind == "cell" and self._context_cell_table is not None and self._context_cell_metadata is not None:
            self._edit_notebook_cell(self._context_cell_table, self._context_cell_metadata)
            self._update_context_action_bar()
        elif self._context_action_kind == "equation":
            self._edit_current_equation()
            self._update_context_action_bar()

    def _sync_toolbar_from_format(self, char_format: QTextCharFormat):
        self._updating_toolbar = True
        font = char_format.font()
        if font.family():
            self.font_family_combo.setCurrentFont(font)

        point_size = char_format.fontPointSize()
        if point_size <= 0:
            point_size = self.editor.fontPointSize() or self.editor.font().pointSizeF() or 12.0
        self.font_size_combo.setCurrentText(str(int(round(point_size))))

        self.bold_button.setChecked(char_format.fontWeight() >= QFont.Weight.Bold)
        self.italic_button.setChecked(char_format.fontItalic())
        self.underline_button.setChecked(char_format.fontUnderline())

        alignment_value = int(self.editor.alignment())
        self.align_left_button.setChecked(bool(alignment_value & int(Qt.AlignmentFlag.AlignLeft)))
        self.align_center_button.setChecked(bool(alignment_value & int(Qt.AlignmentFlag.AlignHCenter)))
        self.align_right_button.setChecked(bool(alignment_value & int(Qt.AlignmentFlag.AlignRight)))
        self.align_justify_button.setChecked(bool(alignment_value & int(Qt.AlignmentFlag.AlignJustify)))
        self._updating_toolbar = False


OutlineTabController = NotebookTabController

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QDate, QEvent, QObject, QSize, QTimer, Qt, Signal, QUrl, QRect
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QAbstractScrollArea,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

try:
    import winsound
except ImportError:  # pragma: no cover - only unavailable on non-Windows platforms
    winsound = None


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[3]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "subject"


@dataclass
class TimeTask:
    title: str
    start_date: str
    end_date: str
    notes: str = ""
    subject: str = ""
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "notes": self.notes,
            "subject": self.subject,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TimeTask":
        return cls(
            title=str(payload.get("title", "")).strip(),
            start_date=str(payload.get("start_date", "")).strip(),
            end_date=str(payload.get("end_date", "")).strip(),
            notes=str(payload.get("notes", "")).strip(),
            subject=str(payload.get("subject", "")).strip(),
            done=bool(payload.get("done", False)),
        )

    def start_qdate(self) -> QDate:
        return QDate.fromString(self.start_date, Qt.DateFormat.ISODate)

    def end_qdate(self) -> QDate:
        return QDate.fromString(self.end_date, Qt.DateFormat.ISODate)


@dataclass
class TodoItem:
    text: str
    done: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TodoItem":
        return cls(
            text=str(payload.get("text", "")).strip(),
            done=bool(payload.get("done", False)),
        )


@dataclass
class ActivityRecord:
    """Record of a timer activity completion."""
    date: str  # ISO format date (YYYY-MM-DD)
    activity_type: str  # "pomodoro", "short_break", "long_break", "short_quiz", "long_quiz", "custom"
    duration_seconds: int  # How long the timer was set for

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "activity_type": self.activity_type,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActivityRecord":
        return cls(
            date=str(payload.get("date", "")).strip(),
            activity_type=str(payload.get("activity_type", "pomodoro")).strip(),
            duration_seconds=int(payload.get("duration_seconds", 0)),
        )


class GanttChartWidget(QAbstractScrollArea):
    rowClicked = Signal(int, int)
    selectionChanged = Signal()
    taskColumnWidthChanged = Signal(int)
    horizontalScrollChanged = Signal(int)

    MIN_TASK_COLUMN_WIDTH = 180
    DEFAULT_TASK_COLUMN_WIDTH = 220
    HEADER_HEIGHT = 48
    ROW_HEIGHT = 40
    RESIZE_HANDLE_WIDTH = 10

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._tasks: list[TimeTask] = []
        self._periods: list[tuple[str, QDate, QDate]] = []
        self._selected_row: int | None = None
        self._view_mode = "month"
        self._task_column_width = self.DEFAULT_TASK_COLUMN_WIDTH
        self._resizing_task_column = False
        self._resize_anchor_x = 0
        self._resize_start_width = self._task_column_width

        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.horizontalScrollBar().valueChanged.connect(self._on_horizontal_scroll_changed)
        self.verticalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())

    def set_data(
        self,
        tasks: list[TimeTask],
        periods: list[tuple[str, QDate, QDate]],
        *,
        selected_row: int | None,
        view_mode: str,
        task_column_width: int | None = None,
        horizontal_scroll_value: int | None = None,
    ):
        self._tasks = list(tasks)
        self._periods = list(periods)
        self._view_mode = view_mode if view_mode in {"month", "week"} else "month"
        if task_column_width is not None:
            self._task_column_width = max(self.MIN_TASK_COLUMN_WIDTH, int(task_column_width))
        self._selected_row = self._normalize_row(selected_row)
        self._update_scrollbars()
        if horizontal_scroll_value is not None:
            self.set_horizontal_scroll_value(horizontal_scroll_value)
        self.viewport().update()

    def current_row(self) -> int | None:
        return self._selected_row

    def set_selected_row(self, row: int | None):
        normalized = self._normalize_row(row)
        if normalized == self._selected_row:
            return
        self._selected_row = normalized
        self._ensure_row_visible(normalized)
        self.viewport().update()
        self.selectionChanged.emit()

    def clear_selection(self):
        self.set_selected_row(None)

    def task_column_width(self) -> int:
        return self._task_column_width

    def set_task_column_width(self, width: int):
        normalized = max(self.MIN_TASK_COLUMN_WIDTH, int(width))
        if normalized == self._task_column_width:
            return
        self._task_column_width = normalized
        self._update_scrollbars()
        self.viewport().update()
        self.taskColumnWidthChanged.emit(normalized)

    def horizontal_scroll_value(self) -> int:
        return self.horizontalScrollBar().value()

    def set_horizontal_scroll_value(self, value: int):
        bar = self.horizontalScrollBar()
        clamped = max(bar.minimum(), min(int(value), bar.maximum()))
        if clamped != bar.value():
            bar.setValue(clamped)
        else:
            self.viewport().update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scrollbars()

    def leaveEvent(self, event):
        if not self._resizing_task_column:
            self.viewport().unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        x = int(event.position().x())
        y = int(event.position().y())
        if self._is_on_resize_handle(x):
            self._resizing_task_column = True
            self._resize_anchor_x = x
            self._resize_start_width = self._task_column_width
            self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            event.accept()
            return

        row = self._row_at(y)
        if row is None:
            self.clear_selection()
            event.accept()
            return

        self.set_selected_row(row)
        self.rowClicked.emit(row, self._timeline_column_at(x))
        event.accept()

    def mouseMoveEvent(self, event):
        x = int(event.position().x())
        if self._resizing_task_column:
            self.set_task_column_width(self._resize_start_width + (x - self._resize_anchor_x))
            event.accept()
            return

        if self._is_on_resize_handle(x):
            self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._resizing_task_column and event.button() == Qt.MouseButton.LeftButton:
            self._resizing_task_column = False
            if self._is_on_resize_handle(int(event.position().x())):
                self.viewport().setCursor(Qt.CursorShape.SplitHCursor)
            else:
                self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.viewport().rect(), QColor("#101a2e"))

        self._paint_headers(painter)
        self._paint_rows(painter)
        self._paint_resize_handle(painter)

        if not self._tasks:
            painter.setPen(QColor("#8e9ab0"))
            painter.drawText(
                self.viewport().rect().adjusted(16, self.HEADER_HEIGHT + 16, -16, -16),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                "No tasks yet. Add one to populate the Gantt chart.",
            )

        super().paintEvent(event)

    def _paint_headers(self, painter: QPainter):
        painter.save()
        header_pen = QPen(QColor("#2f74ff"))
        painter.setPen(header_pen)

        task_header_rect = self.viewport().rect()
        task_header_rect.setLeft(0)
        task_header_rect.setTop(0)
        task_header_rect.setWidth(self._task_column_width)
        task_header_rect.setHeight(self.HEADER_HEIGHT)
        painter.fillRect(task_header_rect, QColor("#173158"))
        painter.drawRect(task_header_rect.adjusted(0, 0, -1, -1))
        painter.setPen(QColor("#edf4ff"))
        painter.drawText(
            task_header_rect.adjusted(12, 0, -12, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "Tasks",
        )

        timeline_header_rect = self.viewport().rect()
        timeline_header_rect.setLeft(self._task_column_width)
        timeline_header_rect.setTop(0)
        timeline_header_rect.setHeight(self.HEADER_HEIGHT)
        painter.setClipRect(timeline_header_rect)

        painter.setPen(header_pen)
        period_width = self._period_width()
        scroll_x = self.horizontalScrollBar().value()
        viewport_width = self.viewport().width()
        start_column = max(0, scroll_x // period_width)
        end_column = min(
            len(self._periods),
            ((scroll_x + max(0, viewport_width - self._task_column_width)) // period_width) + 2,
        )

        for column in range(start_column, end_column):
            label, _, _ = self._periods[column]
            x = self._task_column_width + (column * period_width) - scroll_x
            rect = self.viewport().rect()
            rect.setLeft(x)
            rect.setTop(0)
            rect.setWidth(period_width)
            rect.setHeight(self.HEADER_HEIGHT)
            painter.fillRect(rect, QColor("#173158"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setPen(QColor("#edf4ff"))
            painter.drawText(
                rect.adjusted(6, 4, -6, -4),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
            painter.setPen(header_pen)
        painter.restore()

    def _paint_rows(self, painter: QPainter):
        painter.save()
        scroll_y = self.verticalScrollBar().value()
        scroll_x = self.horizontalScrollBar().value()
        period_width = self._period_width()
        viewport_width = self.viewport().width()
        body_top = self.HEADER_HEIGHT
        visible_body_width = max(0, viewport_width - self._task_column_width)
        start_column = max(0, scroll_x // period_width)
        end_column = min(
            len(self._periods),
            ((scroll_x + visible_body_width) // period_width) + 2,
        )

        for row, task in enumerate(self._tasks):
            y = body_top + (row * self.ROW_HEIGHT) - scroll_y
            if y + self.ROW_HEIGHT < body_top:
                continue
            if y > self.viewport().height():
                break

            is_selected = row == self._selected_row
            task_rect = self.viewport().rect()
            task_rect.setLeft(0)
            task_rect.setTop(y)
            task_rect.setWidth(self._task_column_width)
            task_rect.setHeight(self.ROW_HEIGHT)

            task_fill = QColor("#1f4c7a") if is_selected else QColor("#1b3d61")
            painter.fillRect(task_rect, task_fill)
            painter.setPen(QColor("#2f74ff"))
            painter.drawRect(task_rect.adjusted(0, 0, -1, -1))
            painter.setPen(QColor("#edf4ff"))
            painter.drawText(
                task_rect.adjusted(12, 0, -12, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._elided_text(painter, task.title, task_rect.width() - 24),
            )

            painter.save()
            timeline_row_clip = self.viewport().rect()
            timeline_row_clip.setLeft(self._task_column_width)
            timeline_row_clip.setTop(y)
            timeline_row_clip.setHeight(self.ROW_HEIGHT)
            painter.setClipRect(timeline_row_clip)

            bar_color = self._task_bar_color(row)
            for column in range(start_column, end_column):
                _label, period_start, period_end_exclusive = self._periods[column]
                x = self._task_column_width + (column * period_width) - scroll_x
                cell_rect = self.viewport().rect()
                cell_rect.setLeft(x)
                cell_rect.setTop(y)
                cell_rect.setWidth(period_width)
                cell_rect.setHeight(self.ROW_HEIGHT)
                fill = QColor("#24496d") if is_selected else QColor("#173158")
                if self._task_overlaps_period(task, period_start, period_end_exclusive):
                    fill = bar_color
                painter.fillRect(cell_rect, fill)
                painter.setPen(QColor("#2f74ff"))
                painter.drawRect(cell_rect.adjusted(0, 0, -1, -1))
            painter.restore()

            if is_selected:
                painter.setPen(QPen(QColor("#dbe7f5"), 2))
                selection_rect = self.viewport().rect()
                selection_rect.setLeft(0)
                selection_rect.setTop(y)
                selection_rect.setWidth(self.viewport().width())
                selection_rect.setHeight(self.ROW_HEIGHT)
                painter.drawRect(selection_rect.adjusted(1, 1, -2, -2))
        painter.restore()

    def _paint_resize_handle(self, painter: QPainter):
        painter.save()
        x = self._task_column_width
        line_color = QColor("#8fb6ff") if self._resizing_task_column else QColor("#2f74ff")
        painter.setPen(QPen(line_color, 2))
        painter.drawLine(x, 0, x, self.viewport().height())
        painter.restore()

    def _period_width(self) -> int:
        return 82 if self._view_mode == "week" else 92

    def _normalize_row(self, row: int | None) -> int | None:
        if row is None:
            return None
        if 0 <= row < len(self._tasks):
            return row
        return None

    def _rows_content_height(self) -> int:
        return len(self._tasks) * self.ROW_HEIGHT

    def _timeline_content_width(self) -> int:
        return len(self._periods) * self._period_width()

    def _update_scrollbars(self):
        timeline_viewport_width = max(0, self.viewport().width() - self._task_column_width)
        body_viewport_height = max(0, self.viewport().height() - self.HEADER_HEIGHT)

        horizontal_max = max(0, self._timeline_content_width() - timeline_viewport_width)
        vertical_max = max(0, self._rows_content_height() - body_viewport_height)

        self.horizontalScrollBar().setPageStep(max(1, timeline_viewport_width))
        self.horizontalScrollBar().setRange(0, horizontal_max)
        self.verticalScrollBar().setPageStep(max(1, body_viewport_height))
        self.verticalScrollBar().setRange(0, vertical_max)
        self._ensure_row_visible(self._selected_row)

    def _ensure_row_visible(self, row: int | None):
        if row is None:
            return
        bar = self.verticalScrollBar()
        row_top = row * self.ROW_HEIGHT
        row_bottom = row_top + self.ROW_HEIGHT
        visible_top = bar.value()
        visible_bottom = visible_top + max(0, self.viewport().height() - self.HEADER_HEIGHT)
        if row_top < visible_top:
            bar.setValue(row_top)
        elif row_bottom > visible_bottom:
            bar.setValue(row_bottom - max(0, self.viewport().height() - self.HEADER_HEIGHT))

    def _row_at(self, y: int) -> int | None:
        if y < self.HEADER_HEIGHT:
            return None
        adjusted_y = y - self.HEADER_HEIGHT + self.verticalScrollBar().value()
        row = adjusted_y // self.ROW_HEIGHT
        if 0 <= row < len(self._tasks):
            return row
        return None

    def _timeline_column_at(self, x: int) -> int:
        if x < self._task_column_width:
            return -1
        adjusted_x = x - self._task_column_width + self.horizontalScrollBar().value()
        column = adjusted_x // self._period_width()
        if 0 <= column < len(self._periods):
            return column
        return -1

    def _is_on_resize_handle(self, x: int) -> bool:
        return abs(x - self._task_column_width) <= self.RESIZE_HANDLE_WIDTH

    def _task_bar_color(self, row: int) -> QColor:
        hue = (row * 41) % 360
        saturation = 150 + ((row * 17) % 60)
        value = 210 + ((row * 11) % 35)
        return QColor.fromHsv(hue, min(saturation, 255), min(value, 255))

    def _task_overlaps_period(
        self,
        task: TimeTask,
        period_start: QDate,
        period_end_exclusive: QDate,
    ) -> bool:
        start = task.start_qdate()
        end = task.end_qdate()
        if not start.isValid() or not end.isValid():
            return False
        return start < period_end_exclusive and end >= period_start

    def _elided_text(self, painter: QPainter, text: str, width: int) -> str:
        return painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(0, width))

    def _on_horizontal_scroll_changed(self, value: int):
        self.viewport().update()
        self.horizontalScrollChanged.emit(value)


class GithubCalendarWidget(QCalendarWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._status_by_date: dict[str, str] = {}

    def set_day_statuses(self, statuses: dict[str, str]):
        self._status_by_date = dict(statuses)
        self.updateCells()

    def paintCell(self, painter: QPainter, rect, date: QDate):
        super().paintCell(painter, rect, date)
        status = self._status_by_date.get(date.toString(Qt.DateFormat.ISODate))
        if status not in {"pending", "done"}:
            return

        dot_color = QColor("#ffffff") if status == "pending" else QColor("#34d399")
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        dot_diameter = 7
        dot_x = rect.right() - dot_diameter - 4
        dot_y = rect.bottom() - dot_diameter - 4
        painter.drawEllipse(dot_x, dot_y, dot_diameter, dot_diameter)
        painter.restore()


class ActivityOverviewWidget(QWidget):
    """Widget displaying activity overview as a stacked bar chart."""
    
    VIEW_MODES = {
        "week": ("Week", 7),
        "month": ("Month", 30),
        "3months": ("3 Months", 90),
    }
    
    # Activity colors
    ACTIVITY_COLORS = {
        "pomodoro": QColor("#3b82f6"),      # Blue
        "short_break": QColor("#34d399"),   # Green
        "long_break": QColor("#a78bfa"),    # Purple
        "short_quiz": QColor("#f59e0b"),    # Amber
        "long_quiz": QColor("#ef4444"),     # Red
        "custom": QColor("#8b5cf6"),        # Violet
    }
    
    HEADER_HEIGHT = 48
    LEFT_MARGIN = 60
    RIGHT_MARGIN = 20
    TOP_MARGIN = 60
    BOTTOM_MARGIN = 120  # Increased for horizontal legend
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.activities: list[ActivityRecord] = []
        self.view_mode = "month"  # Default view mode
        self.setMinimumHeight(400)
        self.setStyleSheet("background-color: #101a2e;")
    
    def set_view_mode(self, mode: str):
        """Set the view mode for the chart."""
        if mode in self.VIEW_MODES:
            self.view_mode = mode
            self.update()
    
    def set_activities(self, activities: list[ActivityRecord]):
        """Update the displayed activities."""
        self.activities = list(activities)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#101a2e"))
        
        if not self.activities:
            painter.setPen(QColor("#8e9ab0"))
            painter.setFont(painter.font())
            painter.drawText(
                self.rect().adjusted(16, 48 + 16, -16, -16),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                "No activity records yet. Complete some timers to see your activity overview.",
            )
            return
        
        self._draw_chart(painter)
    
    def _draw_chart(self, painter: QPainter):
        """Draw the stacked bar chart."""
        # Get number of days to show based on view mode
        _, days_to_show = self.VIEW_MODES.get(self.view_mode, ("Month", 30))
        
        # Get date range
        end_date = QDate.currentDate()
        start_date = end_date.addDays(-days_to_show + 1)
        
        # Group activities by date
        activities_by_date: dict[str, dict[str, int]] = {}
        for i in range(days_to_show):
            date = start_date.addDays(i)
            date_key = date.toString(Qt.DateFormat.ISODate)
            activities_by_date[date_key] = {
                "pomodoro": 0,
                "short_break": 0,
                "long_break": 0,
                "short_quiz": 0,
                "long_quiz": 0,
                "custom": 0,
            }
        
        # Sum up activities by date and type
        for activity in self.activities:
            if activity.date in activities_by_date:
                if activity.activity_type in activities_by_date[activity.date]:
                    activities_by_date[activity.date][activity.activity_type] += activity.duration_seconds
        
        # Find max total for scaling
        max_total_seconds = 0
        for day_activities in activities_by_date.values():
            total = sum(day_activities.values())
            if total > max_total_seconds:
                max_total_seconds = total
        
        if max_total_seconds == 0:
            max_total_seconds = 3600  # 1 hour default
        
        # Draw title
        title_font = painter.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#edf4ff"))
        mode_label, _ = self.VIEW_MODES[self.view_mode]
        painter.drawText(10, 20, f"Activity Overview ({mode_label} View)")
        
        # Draw y-axis labels
        self._draw_y_axis(painter, max_total_seconds)
        
        # Draw grid and bars
        chart_width = self.width() - self.LEFT_MARGIN - self.RIGHT_MARGIN
        bar_width = max(4, chart_width // days_to_show - 2)
        bar_spacing = (chart_width - (bar_width * days_to_show)) / days_to_show if days_to_show > 0 else 0
        
        chart_height = self.height() - self.TOP_MARGIN - (self.BOTTOM_MARGIN - 80)
        
        # Draw bars
        for i, date_key in enumerate(sorted(activities_by_date.keys())):
            x = self.LEFT_MARGIN + i * (bar_width + bar_spacing)
            day_activities = activities_by_date[date_key]
            self._draw_stacked_bar(painter, x, day_activities, max_total_seconds, bar_width, chart_height)
        
        # Draw x-axis labels
        self._draw_x_axis_labels(painter, start_date, days_to_show, bar_width, bar_spacing)
        
        # Draw legend below (horizontal)
        self._draw_legend_horizontal(painter)
    
    def _draw_x_axis_labels(self, painter: QPainter, start_date: QDate, days_to_show: int, bar_width: int, bar_spacing: float):
        """Draw x-axis labels."""
        painter.setFont(QFont())
        painter.setPen(QColor("#8e9ab0"))
        
        # Determine label interval based on days to show
        if days_to_show <= 7:
            interval = 1  # Every day for week
        elif days_to_show <= 30:
            interval = 5  # Every 5 days for month
        else:
            interval = 15  # Every 15 days for 3 months
        
        for i in range(0, days_to_show, interval):
            date = start_date.addDays(i)
            x = self.LEFT_MARGIN + i * (bar_width + bar_spacing)
            y = self.height() - 90
            date_str = date.toString("MM-dd")
            painter.drawText(int(x - 20), int(y), 40, 20, Qt.AlignmentFlag.AlignCenter, date_str)
    
    def _draw_legend_horizontal(self, painter: QPainter):
        """Draw legend horizontally below the chart."""
        types_to_show = ["pomodoro", "short_break", "long_break", "short_quiz", "long_quiz", "custom"]
        
        # Calculate legend position (below x-axis)
        legend_y = self.height() - 50
        legend_start_x = self.LEFT_MARGIN
        
        # Draw legend items horizontally
        painter.setFont(QFont())
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        x_offset = legend_start_x
        item_spacing = 120
        
        for activity_type in types_to_show:
            # Draw color box
            color = self.ACTIVITY_COLORS.get(activity_type, QColor("#ffffff"))
            painter.fillRect(int(x_offset), int(legend_y - 6), 12, 12, color)
            painter.setPen(QColor("#ffffff"))
            painter.drawRect(int(x_offset), int(legend_y - 6), 12, 12)
            
            # Draw label
            label = activity_type.replace("_", " ").title()
            painter.setPen(QColor("#dbe7f5"))
            painter.drawText(int(x_offset + 18), int(legend_y), label)
            
            x_offset += item_spacing
    
    def _draw_y_axis(self, painter: QPainter, max_seconds: int):
        """Draw y-axis with time labels."""
        chart_height = self.height() - self.TOP_MARGIN - (self.BOTTOM_MARGIN - 80)
        
        # Draw y-axis line
        painter.setPen(QColor("#23314a"))
        painter.drawLine(
            self.LEFT_MARGIN - 5,
            self.TOP_MARGIN,
            self.LEFT_MARGIN - 5,
            self.height() - (self.BOTTOM_MARGIN - 80)
        )
        
        # Draw labels and grid lines
        painter.setPen(QColor("#8e9ab0"))
        painter.setFont(QFont())
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        
        for i in range(5):
            ratio = i / 4
            hours = (max_seconds / 3600) * ratio
            y = self.TOP_MARGIN + (1 - ratio) * chart_height
            
            # Grid line
            painter.setPen(QColor("#1a2844"))
            painter.drawLine(
                self.LEFT_MARGIN - 5,
                int(y),
                self.width() - self.RIGHT_MARGIN,
                int(y)
            )
            
            # Label
            painter.setPen(QColor("#8e9ab0"))
            label = f"{hours:.1f}h"
            painter.drawText(5, int(y - 10), 50, 20, Qt.AlignmentFlag.AlignRight, label)
    
    def _draw_stacked_bar(self, painter: QPainter, x: float, day_activities: dict[str, int], 
                          max_seconds: int, bar_width: int, chart_height: float):
        """Draw a stacked bar for a single day."""
        y_base = self.height() - (self.BOTTOM_MARGIN - 80)
        total_seconds = sum(day_activities.values())
        
        # Order of activities in the stack (bottom to top)
        activity_order = ["pomodoro", "short_break", "long_break", "short_quiz", "long_quiz", "custom"]
        
        y_offset = 0
        for activity_type in activity_order:
            seconds = day_activities.get(activity_type, 0)
            if seconds <= 0:
                continue
            
            # Calculate height based on proportion of max
            height = (seconds / max_seconds) * chart_height
            
            # Draw rectangle
            rect = QRect(
                int(x),
                int(y_base - y_offset - height),
                bar_width,
                int(height)
            )
            
            color = self.ACTIVITY_COLORS.get(activity_type, QColor("#ffffff"))
            painter.fillRect(rect, color)
            painter.setPen(QColor("#ffffff"))
            painter.drawRect(rect)
            
            y_offset += height


class TimeTaskDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, task: TimeTask | None = None):
        super().__init__(parent)
        self.setWindowTitle("Task")
        self.setMinimumWidth(520)
        self._build_ui(task)

    def _build_ui(self, task: TimeTask | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("Task title")

        self.start_edit = QDateEdit(self)
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd")

        self.end_edit = QDateEdit(self)
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd")

        self.notes_edit = QPlainTextEdit(self)
        self.notes_edit.setPlaceholderText("Optional notes")
        self.done_checkbox = QCheckBox("Mark this task as done", self)

        form.addRow("Title", self.title_edit)
        form.addRow("Start", self.start_edit)
        form.addRow("End", self.end_edit)
        form.addRow("Notes", self.notes_edit)
        form.addRow("", self.done_checkbox)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        today = QDate.currentDate()
        self.start_edit.setDate(today)
        self.end_edit.setDate(today)

        if task is not None:
            self.title_edit.setText(task.title)
            start_date = task.start_qdate()
            end_date = task.end_qdate()
            if start_date.isValid():
                self.start_edit.setDate(start_date)
            if end_date.isValid():
                self.end_edit.setDate(end_date)
            self.notes_edit.setPlainText(task.notes)
            self.done_checkbox.setChecked(task.done)

    def to_task(self, *, subject: str = "") -> TimeTask:
        title = self.title_edit.text().strip()
        if not title:
            raise ValueError("Please enter a task title.")

        start_date = self.start_edit.date()
        end_date = self.end_edit.date()
        if start_date > end_date:
            raise ValueError("Start date must be on or before the end date.")

        return TimeTask(
            title=title,
            start_date=start_date.toString(Qt.DateFormat.ISODate),
            end_date=end_date.toString(Qt.DateFormat.ISODate),
            notes=self.notes_edit.toPlainText().strip(),
            subject=subject,
            done=self.done_checkbox.isChecked(),
        )


class TimeOrganizerController(QObject):
    TIMER_PANEL_MIN_WIDTH = 320
    GANTT_WEEK_VIEW_DAYS = 28
    GANTT_MONTH_VIEW_MONTHS = 12
    TIMER_PRESETS = {
        "pomodoro": ("Pomodoro", 25 * 60),
        "short_break": ("Short Break", 5 * 60),
        "long_break": ("Long Break", 15 * 60),
        "custom": ("Custom", 30 * 60),
        "short_quiz": ("Short Quiz", 15 * 60),
        "long_quiz": ("Long Quiz", 60 * 60),
    }

    def __init__(self, time_tabs, gant_page: QWidget, calendar_page: QWidget, todo_page: QWidget, activity_overview_page: QWidget | None = None):
        super().__init__(gant_page)
        self.time_tabs = time_tabs
        self.gant_page = gant_page
        self.calendar_page = calendar_page
        self.todo_page = todo_page
        self.activity_overview_page = activity_overview_page
        self.subject_name: str | None = None
        self.storage_root = Path(__file__).resolve().parent
        self.storage_path: Path | None = None
        self.tasks: list[TimeTask] = []
        self.todo_items: list[TodoItem] = []
        self.activities: list[ActivityRecord] = []
        self.selected_date = QDate.currentDate()
        self._month_dates: list[QDate] = []
        self.selected_task_key: tuple[str, str, str] | None = None
        self.selected_timer_mode = "pomodoro"
        self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]
        self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
        self._loading_todo_list = False
        self._loading_calendar_task_list = False
        self.gantt_view_mode = "month"
        self._gantt_clear_targets: list[QObject] = []
        self._syncing_gantt_selection = False
        self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
        self.gantt_horizontal_scroll = 0
        self.long_quiz_timeout_handler = None

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._tick_timer)
        self.gantt_state_save_timer = QTimer(self)
        self.gantt_state_save_timer.setSingleShot(True)
        self.gantt_state_save_timer.timeout.connect(self._save)
        
        # Initialize audio player for alarm
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.media_player = QMediaPlayer(self)
        self.media_player.setAudioOutput(self.audio_output)
        self._alarm_fallback_armed = False
        if hasattr(self.media_player, "errorOccurred"):
            self.media_player.errorOccurred.connect(self._on_alarm_media_error)
        
        self.time_tabs.setMinimumWidth(self.TIMER_PANEL_MIN_WIDTH)

        self._build_gant_ui()
        self._build_calendar_ui()
        self._build_todo_ui()
        self._build_activity_overview_ui()
        self._wire_signals()
        self._refresh_all()

    def set_storage_root(self, storage_root: str | Path):
        new_root = Path(storage_root)
        new_root.mkdir(parents=True, exist_ok=True)
        if new_root == self.storage_root:
            return

        self._flush_gantt_state_save()
        self.storage_root = new_root
        if self.subject_name is None:
            self.storage_path = None
            return

        self.storage_path = self.storage_root / f"{slugify(self.subject_name)}.json"
        self._load()

    def set_long_quiz_timeout_handler(self, handler):
        self.long_quiz_timeout_handler = handler

    def _build_gant_ui(self):
        layout = self.gant_page.layout()
        if layout is None:
            layout = QVBoxLayout(self.gant_page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)
        else:
            self._clear_layout(layout)

        toolbar = QWidget(self.gant_page)
        self.gant_toolbar = toolbar
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.gant_title = QLabel("Gantt Chart", toolbar)
        self.gant_title.setStyleSheet("color: #f8fbff; font-size: 16pt; font-weight: 700;")
        self.gant_prev_button = QPushButton("<", toolbar)
        self.gant_next_button = QPushButton(">", toolbar)
        self.gant_view_mode_combo = QComboBox(toolbar)
        self.gant_view_mode_combo.addItem("Month View", "month")
        self.gant_view_mode_combo.addItem("Week View", "week")
        self.gant_add_button = QPushButton("Add Task", toolbar)
        self.gant_edit_button = QPushButton("Edit", toolbar)
        self.gant_delete_button = QPushButton("Delete", toolbar)
        self.gant_month_label = QLabel(toolbar)
        self.gant_status_label = QLabel(toolbar)
        self.gant_month_label.setStyleSheet("color: #7ab0ff; font-size: 10.5pt; font-weight: 700;")
        self.gant_status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")

        toolbar_layout.addWidget(self.gant_title)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(self.gant_prev_button)
        toolbar_layout.addWidget(self.gant_next_button)
        toolbar_layout.addWidget(self.gant_view_mode_combo)
        toolbar_layout.addWidget(self.gant_month_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.gant_status_label)
        toolbar_layout.addWidget(self.gant_add_button)
        toolbar_layout.addWidget(self.gant_edit_button)
        toolbar_layout.addWidget(self.gant_delete_button)

        self.gantt_chart_widget = GanttChartWidget(self.gant_page)

        self.gant_details = QLabel("Select a task to see its details.", self.gant_page)
        self.gant_details.setWordWrap(True)

        layout.addWidget(toolbar)
        layout.addWidget(self.gantt_chart_widget, 1)
        layout.addWidget(self.gant_details)

        self._gantt_clear_targets = [
            self.gant_page,
            self.gant_toolbar,
            self.gant_details,
            self.gant_title,
            self.gant_month_label,
            self.gant_status_label,
        ]
        for widget in self._gantt_clear_targets:
            widget.installEventFilter(self)

    def _build_calendar_ui(self):
        layout = self.calendar_page.layout()
        if layout is None:
            layout = QVBoxLayout(self.calendar_page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)
        else:
            self._clear_layout(layout)

        toolbar = QWidget(self.calendar_page)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        self.calendar_title = QLabel("Calendar", toolbar)
        self.calendar_status_label = QLabel(toolbar)
        self.calendar_title.setStyleSheet("color: #f8fbff; font-size: 16pt; font-weight: 700;")
        self.calendar_status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")
        self.calendar_add_button = QPushButton("Add Task", toolbar)
        self.calendar_edit_button = QPushButton("Edit", toolbar)
        self.calendar_delete_button = QPushButton("Delete", toolbar)

        toolbar_layout.addWidget(self.calendar_title)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.calendar_status_label)
        toolbar_layout.addWidget(self.calendar_add_button)
        toolbar_layout.addWidget(self.calendar_edit_button)
        toolbar_layout.addWidget(self.calendar_delete_button)

        body = QWidget(self.calendar_page)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        self.calendar_widget = GithubCalendarWidget(body)
        self.calendar_widget.setGridVisible(True)
        self.calendar_widget.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar_widget.setStyleSheet(
            "QCalendarWidget QWidget#qt_calendar_navigationbar {"
            " background-color: #101a2e;"
            " border: 1px solid #23314a;"
            " border-radius: 10px;"
            "}"
            "QCalendarWidget QToolButton {"
            " min-width: 28px;"
            " padding: 6px 10px;"
            "}"
            "QCalendarWidget QAbstractItemView:enabled {"
            " selection-background-color: #173158;"
            " selection-color: #ffffff;"
            "}"
        )

        side = QWidget(body)
        side.setMinimumWidth(320)
        side.setMaximumWidth(440)
        side.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)

        self.calendar_selected_label = QLabel("Selected day", side)
        self.calendar_selected_label.setStyleSheet(
            "font-size: 18pt; font-weight: 700; color: #edf4ff;"
        )
        self.calendar_summary_label = QLabel("No tasks scheduled.", side)
        self.calendar_summary_label.setWordWrap(True)
        self.calendar_summary_label.setStyleSheet(
            "color: #9fb2cc; font-size: 10.5pt; line-height: 1.4em;"
        )

        self.calendar_task_panel = QFrame(side)
        self.calendar_task_panel.setObjectName("CalendarTaskPanel")
        self.calendar_task_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.calendar_task_panel.setStyleSheet(
            "#CalendarTaskPanel {"
            " background-color: #101a2e;"
            " border: 1px solid #23314a;"
            " border-radius: 16px;"
            "}"
        )
        task_panel_layout = QVBoxLayout(self.calendar_task_panel)
        task_panel_layout.setContentsMargins(14, 14, 14, 14)
        task_panel_layout.setSpacing(10)

        task_header = QWidget(self.calendar_task_panel)
        task_header.setStyleSheet("background: transparent;")
        task_header_layout = QHBoxLayout(task_header)
        task_header_layout.setContentsMargins(0, 0, 0, 0)
        self.calendar_task_header_label = QLabel("Tasks for the day", task_header)
        self.calendar_task_header_label.setStyleSheet(
            "font-size: 11pt; font-weight: 700; color: #edf4ff;"
        )
        self.calendar_task_count_label = QLabel("0 items", task_header)
        self.calendar_task_count_label.setStyleSheet(
            "color: #9fb2cc; font-size: 10pt;"
        )
        task_header_layout.addWidget(self.calendar_task_header_label)
        task_header_layout.addStretch(1)
        task_header_layout.addWidget(self.calendar_task_count_label)

        self.calendar_task_list = QListWidget(self.calendar_task_panel)
        self.calendar_task_list.setFrameShape(QFrame.Shape.NoFrame)
        self.calendar_task_list.setSpacing(8)
        self.calendar_task_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.calendar_task_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.calendar_task_list.setStyleSheet(
            "QListWidget, QListWidget::viewport { background-color: #101a2e; border: none; }"
            "QListWidget::item { border: none; padding: 0px; }"
            "QListWidget::item:selected { background: transparent; outline: 0; }"
        )
        self.calendar_task_list.viewport().installEventFilter(self)

        task_panel_layout.addWidget(task_header)
        task_panel_layout.addWidget(self.calendar_task_list, 1)

        side_layout.addWidget(self.calendar_selected_label)
        side_layout.addWidget(self.calendar_summary_label)
        side_layout.addWidget(self.calendar_task_panel, 1)

        body_layout.addWidget(self.calendar_widget, 3)
        body_layout.addWidget(side, 2)

        layout.addWidget(toolbar)
        layout.addWidget(body, 1)

    def _build_todo_ui(self):
        layout = self.todo_page.layout()
        if layout is None:
            layout = QVBoxLayout(self.todo_page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)
        else:
            self._clear_layout(layout)

        toolbar = QWidget(self.todo_page)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.todo_title = QLabel("Todo List", toolbar)
        self.todo_status_label = QLabel(toolbar)
        self.todo_title.setStyleSheet("color: #f8fbff; font-size: 16pt; font-weight: 700;")
        self.todo_status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")
        toolbar_layout.addWidget(self.todo_title)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.todo_status_label)

        todo_body = QWidget(self.todo_page)
        todo_body_layout = QHBoxLayout(todo_body)
        todo_body_layout.setContentsMargins(0, 0, 0, 0)
        todo_body_layout.setSpacing(12)

        self.timer_panel = QWidget(todo_body)
        self.timer_panel.setMinimumWidth(self.TIMER_PANEL_MIN_WIDTH)
        self.timer_panel.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        timer_layout = QVBoxLayout(self.timer_panel)
        timer_layout.setContentsMargins(0, 0, 8, 0)
        timer_layout.setSpacing(10)

        self.timer_mode_label = QLabel(self.timer_panel)
        self.timer_mode_label.setStyleSheet("color: #dbe7f5; font-size: 14pt; font-weight: 600;")
        timer_layout.addWidget(self.timer_mode_label)

        self.timer_display = QLabel("25:00", self.timer_panel)
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_display.setMinimumHeight(120)
        self.timer_display.setStyleSheet(
            "font-size: 34pt; font-weight: 700; color: #ffffff;"
            "background-color: #101a2e; border: 1px solid #23314a; border-radius: 12px;"
        )
        timer_layout.addWidget(self.timer_display)

        self.timer_mode_combo = QComboBox(self.timer_panel)
        for mode_key, (label, _seconds) in self.TIMER_PRESETS.items():
            self.timer_mode_combo.addItem(label, mode_key)
        timer_layout.addWidget(self.timer_mode_combo)

        control_row = QWidget(self.timer_panel)
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(6)
        self.timer_toggle_button = QPushButton(control_row)
        self.timer_reset_button = QPushButton(control_row)
        self._configure_timer_icon_button(self.timer_toggle_button)
        self._configure_timer_icon_button(
            self.timer_reset_button,
            QStyle.StandardPixmap.SP_BrowserReload,
            "Reset timer",
        )
        control_layout.addWidget(self.timer_toggle_button)
        control_layout.addWidget(self.timer_reset_button)
        timer_layout.addWidget(control_row)

        self.timer_helper_label = QLabel(self.timer_panel)
        self.timer_helper_label.setWordWrap(True)
        timer_layout.addWidget(self.timer_helper_label)
        timer_layout.addStretch(1)

        self.todo_checklist_panel = QWidget(todo_body)
        self.todo_checklist_panel.setMinimumWidth(0)
        self.todo_checklist_panel.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        todo_layout = QVBoxLayout(self.todo_checklist_panel)
        todo_layout.setContentsMargins(8, 0, 0, 0)
        todo_layout.setSpacing(8)

        todo_header = QLabel("Checklist", self.todo_checklist_panel)
        todo_header.setStyleSheet("color: #7ab0ff; font-size: 10.5pt; font-weight: 700;")
        todo_layout.addWidget(todo_header)

        input_row = QWidget(self.todo_checklist_panel)
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        self.todo_input = QLineEdit(input_row)
        self.todo_input.setPlaceholderText("Add a todo item")
        self.todo_add_button = QPushButton("Add", input_row)
        input_layout.addWidget(self.todo_input, 1)
        input_layout.addWidget(self.todo_add_button)
        todo_layout.addWidget(input_row)

        self.todo_list_widget = QListWidget(self.todo_checklist_panel)
        self.todo_list_widget.setAlternatingRowColors(True)
        self.todo_list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        todo_layout.addWidget(self.todo_list_widget, 1)

        remove_row = QWidget(self.todo_checklist_panel)
        remove_layout = QHBoxLayout(remove_row)
        remove_layout.setContentsMargins(0, 0, 0, 0)
        remove_layout.addStretch(1)
        self.todo_remove_button = QPushButton("Remove Selected", remove_row)
        remove_layout.addWidget(self.todo_remove_button)
        todo_layout.addWidget(remove_row)

        layout.addWidget(toolbar)
        todo_body_layout.addWidget(self.timer_panel, 0)
        todo_body_layout.addWidget(self.todo_checklist_panel, 1)
        layout.addWidget(todo_body, 1)

    def _build_activity_overview_ui(self):
        """Build the Activity Overview tab UI."""
        if self.activity_overview_page is None:
            return
        
        layout = self.activity_overview_page.layout()
        if layout is None:
            layout = QVBoxLayout(self.activity_overview_page)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)
        else:
            self._clear_layout(layout)
        
        # Create toolbar with view mode selector
        toolbar = QWidget(self.activity_overview_page)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Activity Overview", toolbar)
        title_label.setStyleSheet("color: #f8fbff; font-size: 16pt; font-weight: 700;")
        self.activity_view_mode_combo = QComboBox(toolbar)
        for mode_key, (label, _) in ActivityOverviewWidget.VIEW_MODES.items():
            self.activity_view_mode_combo.addItem(label, mode_key)
        self.activity_view_mode_combo.setCurrentIndex(1)  # Default to Month
        self.activity_view_mode_combo.currentIndexChanged.connect(self._on_activity_view_mode_changed)
        
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addSpacing(8)
        toolbar_layout.addWidget(QLabel("View:", toolbar))
        toolbar_layout.addWidget(self.activity_view_mode_combo)
        toolbar_layout.addStretch(1)
        
        # Create chart widget
        self.activity_overview_widget = ActivityOverviewWidget(self.activity_overview_page)
        
        layout.addWidget(toolbar)
        layout.addWidget(self.activity_overview_widget, 1)

    def _on_activity_view_mode_changed(self):
        """Handle activity view mode change."""
        mode = self.activity_view_mode_combo.currentData()
        if isinstance(mode, str) and hasattr(self, 'activity_overview_widget'):
            self.activity_overview_widget.set_view_mode(mode)

    def _configure_timer_icon_button(
        self,
        button: QPushButton,
        icon_kind: QStyle.StandardPixmap | None = None,
        tooltip: str = "",
    ):
        if icon_kind is not None:
            button.setIcon(button.style().standardIcon(icon_kind))
        button.setIconSize(QSize(20, 20))
        button.setText("")
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(44, 44)

    def _update_timer_toggle_icon(self):
        running = self.countdown_timer.isActive()
        icon_kind = (
            QStyle.StandardPixmap.SP_MediaPause
            if running
            else QStyle.StandardPixmap.SP_MediaPlay
        )
        tooltip = "Pause timer" if running else "Start timer"
        self.timer_toggle_button.setIcon(self.timer_toggle_button.style().standardIcon(icon_kind))
        self.timer_toggle_button.setToolTip(tooltip)
        self.timer_toggle_button.setAccessibleName(tooltip)

    def _wire_signals(self):
        self.gant_prev_button.clicked.connect(lambda: self._shift_gantt_window(-1))
        self.gant_next_button.clicked.connect(lambda: self._shift_gantt_window(1))
        self.gant_view_mode_combo.currentIndexChanged.connect(self._on_gantt_view_mode_changed)
        self.gant_add_button.clicked.connect(self.add_task)
        self.gant_edit_button.clicked.connect(self.edit_task)
        self.gant_delete_button.clicked.connect(self.delete_task)
        self.gantt_chart_widget.rowClicked.connect(self._on_gant_cell_clicked)
        self.gantt_chart_widget.selectionChanged.connect(self._on_gant_selection_changed)
        self.gantt_chart_widget.taskColumnWidthChanged.connect(self._on_gantt_task_width_changed)
        self.gantt_chart_widget.horizontalScrollChanged.connect(self._on_gantt_horizontal_scroll_changed)

        self.calendar_widget.selectionChanged.connect(self._on_calendar_date_changed)
        self.calendar_add_button.clicked.connect(self.add_task)
        self.calendar_edit_button.clicked.connect(self.edit_task)
        self.calendar_delete_button.clicked.connect(self.delete_task)
        self.calendar_widget.clicked.connect(self._jump_to_date)
        self.calendar_task_list.itemSelectionChanged.connect(self._on_calendar_task_selection_changed)

        self.timer_mode_combo.currentIndexChanged.connect(self._on_timer_mode_combo_changed)
        self.timer_toggle_button.clicked.connect(self.toggle_timer)
        self.timer_reset_button.clicked.connect(self.reset_timer)
        self.todo_input.returnPressed.connect(self.add_todo_item)
        self.todo_add_button.clicked.connect(self.add_todo_item)
        self.todo_remove_button.clicked.connect(self.remove_selected_todo_item)
        self.todo_list_widget.itemChanged.connect(self._on_todo_item_changed)
        self.todo_list_widget.itemSelectionChanged.connect(self._refresh_timer_controls)

    def _preset_seconds(self, mode: str) -> int:
        if mode == "custom":
            return max(60, int(self.custom_timer_seconds))
        return self.TIMER_PRESETS.get(mode, self.TIMER_PRESETS["pomodoro"])[1]

    def _preset_label(self, mode: str) -> str:
        if mode in {"short_quiz", "long_quiz"} and self.subject_name:
            suffix = "Short Quiz" if mode == "short_quiz" else "Long Quiz"
            return f"{self.subject_name} ({suffix})"
        return self.TIMER_PRESETS.get(mode, self.TIMER_PRESETS["pomodoro"])[0]

    def _combo_label_for_mode(self, mode: str) -> str:
        if mode == "short_quiz" and self.subject_name:
            return f"{self.subject_name} (Short Quiz)"
        if mode == "long_quiz" and self.subject_name:
            return f"{self.subject_name} (Long Quiz)"
        return self.TIMER_PRESETS.get(mode, self.TIMER_PRESETS["pomodoro"])[0]

    def _refresh_timer_mode_combo_labels(self):
        for index in range(self.timer_mode_combo.count()):
            mode = self.timer_mode_combo.itemData(index)
            if isinstance(mode, str):
                self.timer_mode_combo.setItemText(index, self._combo_label_for_mode(mode))

    def _on_gantt_task_width_changed(self, width: int):
        self.gantt_task_column_width = max(GanttChartWidget.MIN_TASK_COLUMN_WIDTH, int(width))
        self._schedule_gantt_state_save()

    def _on_gantt_horizontal_scroll_changed(self, value: int):
        self.gantt_horizontal_scroll = max(0, int(value))
        self._schedule_gantt_state_save()

    def _schedule_gantt_state_save(self):
        if self.subject_name is None:
            return
        self.gantt_state_save_timer.start(250)

    def _flush_gantt_state_save(self):
        if self.gantt_state_save_timer.isActive():
            self.gantt_state_save_timer.stop()
            self._save()

    def _sync_gantt_row_selection(self, row: int | None):
        if self._syncing_gantt_selection:
            return

        self._syncing_gantt_selection = True
        try:
            self.gantt_chart_widget.set_selected_row(row)
        finally:
            self._syncing_gantt_selection = False

    def set_subject(
        self,
        subject_name: str | None,
        *,
        preserve_timer_state: bool = False,
    ):
        previous_timer_mode = self.selected_timer_mode
        previous_custom_seconds = self.custom_timer_seconds
        previous_remaining_seconds = self.remaining_seconds
        previous_running_state = self.countdown_timer.isActive()

        if self.subject_name is not None:
            self._flush_gantt_state_save()

        self.subject_name = (
            subject_name.strip() if isinstance(subject_name, str) and subject_name.strip() else None
        )
        self.countdown_timer.stop()

        if self.subject_name is None:
            self.storage_path = None
            self.tasks = []
            self.todo_items = []
            self.activities = []
            self.selected_date = QDate.currentDate()
            self.selected_task_key = None
            self.selected_timer_mode = "pomodoro"
            self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]
            self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
            self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
            self.gantt_horizontal_scroll = 0
            self._refresh_all()
            return

        self.storage_path = self.storage_root / f"{slugify(self.subject_name)}.json"
        self._load()

        if preserve_timer_state:
            self.selected_timer_mode = previous_timer_mode
            self.custom_timer_seconds = previous_custom_seconds
            self.remaining_seconds = previous_remaining_seconds
            if previous_running_state:
                self.countdown_timer.start()
            self._refresh_timer_controls()
            self._refresh_timer_display()

    def _load(self):
        if self.storage_path is None or not self.storage_path.exists():
            self.tasks = []
            self.todo_items = []
            self.activities = []
            self.selected_date = QDate.currentDate()
            self.selected_task_key = None
            self.selected_timer_mode = "pomodoro"
            self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]
            self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
            self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
            self.gantt_horizontal_scroll = 0
            self._refresh_all()
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self.tasks = []
            self.todo_items = []
            self.activities = []
            self.selected_date = QDate.currentDate()
            self.selected_task_key = None
            self.selected_timer_mode = "pomodoro"
            self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]
            self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
            self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
            self.gantt_horizontal_scroll = 0
            self._refresh_all()
            return

        self.selected_date = self._parse_date(payload.get("selected_date")) or QDate.currentDate()

        raw_tasks = payload.get("tasks", [])
        self.tasks = []
        if isinstance(raw_tasks, list):
            for entry in raw_tasks:
                if isinstance(entry, dict):
                    task = TimeTask.from_dict(entry)
                    if task.title and task.start_date and task.end_date:
                        self.tasks.append(task)

        raw_todo_items = payload.get("todo_items", [])
        self.todo_items = []
        if isinstance(raw_todo_items, list):
            for entry in raw_todo_items:
                if isinstance(entry, dict):
                    todo_item = TodoItem.from_dict(entry)
                    if todo_item.text:
                        self.todo_items.append(todo_item)

        raw_activities = payload.get("activities", [])
        self.activities = []
        if isinstance(raw_activities, list):
            for entry in raw_activities:
                if isinstance(entry, dict):
                    activity = ActivityRecord.from_dict(entry)
                    if activity.date and activity.activity_type and activity.duration_seconds > 0:
                        self.activities.append(activity)

        stored_custom_seconds = payload.get("custom_timer_seconds")
        if isinstance(stored_custom_seconds, int) and stored_custom_seconds >= 60:
            self.custom_timer_seconds = stored_custom_seconds
        else:
            self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]

        timer_mode = payload.get("selected_timer_mode")
        if isinstance(timer_mode, str) and timer_mode in self.TIMER_PRESETS:
            self.selected_timer_mode = timer_mode
        else:
            self.selected_timer_mode = "pomodoro"
        self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
        stored_task_width = payload.get("gantt_task_column_width")
        if isinstance(stored_task_width, int):
            self.gantt_task_column_width = max(
                GanttChartWidget.MIN_TASK_COLUMN_WIDTH,
                stored_task_width,
            )
        else:
            self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
        stored_horizontal_scroll = payload.get("gantt_horizontal_scroll")
        self.gantt_horizontal_scroll = stored_horizontal_scroll if isinstance(stored_horizontal_scroll, int) else 0
        self.selected_task_key = self._task_key(self.tasks[0]) if self.tasks else None
        self._refresh_all()

    def _save(self):
        if self.storage_path is None:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "subject": self.subject_name,
            "selected_date": self.selected_date.toString(Qt.DateFormat.ISODate),
            "tasks": [task.to_dict() for task in self.tasks],
            "todo_items": [item.to_dict() for item in self.todo_items],
            "activities": [activity.to_dict() for activity in self.activities],
            "selected_timer_mode": self.selected_timer_mode,
            "custom_timer_seconds": self.custom_timer_seconds,
            "gantt_task_column_width": self.gantt_task_column_width,
            "gantt_horizontal_scroll": self.gantt_horizontal_scroll,
        }
        try:
            with self.storage_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError:
            pass

    def _parse_date(self, value: Any) -> QDate | None:
        if not isinstance(value, str) or not value.strip():
            return None
        date = QDate.fromString(value.strip(), Qt.DateFormat.ISODate)
        return date if date.isValid() else None

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_all(self):
        self.calendar_widget.blockSignals(True)
        self.calendar_widget.setSelectedDate(self.selected_date)
        self.calendar_widget.blockSignals(False)
        self._refresh_status()
        self._refresh_calendar_summary()
        self._refresh_gantt()
        self._refresh_todo_ui()
        self._refresh_activity_overview()

    def _refresh_status(self):
        subject = self.subject_name or "No subject selected"
        self.gant_status_label.setText(f"{len(self.tasks)} tasks")
        self.calendar_status_label.setText(subject)
        self.todo_status_label.setText(f"{subject} | {len(self.todo_items)} items")

    def _refresh_calendar_summary(self):
        self.calendar_selected_label.setText(self.selected_date.toString("dddd, dd MMM yyyy"))
        matches = [task for task in self.tasks if self._task_overlaps_date(task, self.selected_date)]
        if not matches:
            self.calendar_summary_label.setText("No tasks scheduled for this day.")
            self.calendar_task_count_label.setText("0 items")
            self._loading_calendar_task_list = True
            self.calendar_task_list.clear()
            self._loading_calendar_task_list = False
            self._refresh_calendar_markers()
            return

        done_count = sum(1 for task in matches if task.done)
        pending_count = len(matches) - done_count
        if pending_count and done_count:
            summary = f"{len(matches)} tasks scheduled, {done_count} completed and {pending_count} still active."
        elif pending_count:
            summary = f"{len(matches)} tasks scheduled and ready to work on."
        else:
            summary = f"Everything scheduled for this day is complete."
        self.calendar_summary_label.setText(summary)
        self.calendar_task_count_label.setText(
            f"{len(matches)} item{'s' if len(matches) != 1 else ''}"
        )
        self._populate_calendar_task_list(matches)
        self._refresh_calendar_markers()

    def _populate_calendar_task_list(self, tasks: list[TimeTask]):
        selected_task = self._selected_task()
        selected_key = self._task_key(selected_task) if selected_task is not None else None
        self._loading_calendar_task_list = True
        self.calendar_task_list.clear()

        for task in tasks:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, self._task_key(task))
            item.setData(Qt.ItemDataRole.UserRole + 1, task.done)
            self.calendar_task_list.addItem(item)
            card = self._build_calendar_task_card(task)
            self.calendar_task_list.setItemWidget(item, card)
            if selected_key is not None and self._task_key(task) == selected_key:
                self.calendar_task_list.setCurrentItem(item)

        self._loading_calendar_task_list = False
        self._refresh_calendar_task_card_selection()
        self._schedule_calendar_task_card_resize()

    def _build_calendar_task_card(self, task: TimeTask) -> QWidget:
        card = QFrame(self.calendar_task_list)
        card.setObjectName("CalendarTaskCard")
        self._apply_calendar_task_card_style(card, task.done, selected=False)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        header = QWidget(card)
        header.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        dot = QLabel(header)
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(
            f"background-color: {'#34d399' if task.done else '#ffffff'}; border-radius: 5px;"
        )

        title = QLabel(task.title, header)
        title.setWordWrap(True)
        title.setStyleSheet("background: transparent; font-size: 11pt; font-weight: 700; color: #edf4ff;")

        badge = QLabel("Done" if task.done else "Active", header)
        badge.setStyleSheet(
            "padding: 3px 8px; border-radius: 999px; font-size: 9pt; font-weight: 700;"
            f"color: {'#052e26' if task.done else '#111827'};"
            f"background-color: {'#34d399' if task.done else '#ffffff'};"
        )

        header_layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        schedule = QLabel(f"{task.start_date} to {task.end_date}", card)
        schedule.setStyleSheet("color: #9fb2cc; font-size: 9.8pt;")

        layout.addWidget(header)
        layout.addWidget(schedule)

        if task.notes:
            notes = QLabel(task.notes, card)
            notes.setWordWrap(True)
            notes.setStyleSheet("color: #d4ddeb; font-size: 9.8pt;")
            layout.addWidget(notes)

        return card

    def _apply_calendar_task_card_style(self, card: QFrame, task_done: bool, *, selected: bool):
        background = "#152033" if task_done else "#132136"
        border = "#ffffff" if selected else ("#1f6d57" if task_done else "#23314a")
        card.setStyleSheet(
            f"#CalendarTaskCard {{"
            f" background-color: {background};"
            f" border: {2 if selected else 1}px solid {border};"
            f" border-radius: 14px;"
            "}"
        )

    def _refresh_calendar_markers(self):
        statuses: dict[str, str] = {}
        for task in self.tasks:
            start = task.start_qdate()
            end = task.end_qdate()
            if not start.isValid() or not end.isValid():
                continue
            current = start
            while current <= end:
                key = current.toString(Qt.DateFormat.ISODate)
                existing = statuses.get(key)
                if not task.done:
                    statuses[key] = "pending"
                elif existing is None:
                    statuses[key] = "done"
                current = current.addDays(1)
        self.calendar_widget.set_day_statuses(statuses)

    def _schedule_calendar_task_card_resize(self):
        if not hasattr(self, "calendar_task_list"):
            return
        QTimer.singleShot(0, self._refresh_calendar_task_card_sizes)

    def _refresh_calendar_task_card_sizes(self):
        if not hasattr(self, "calendar_task_list"):
            return
        viewport_width = self.calendar_task_list.viewport().width()
        if viewport_width <= 0:
            return
        available_width = max(220, viewport_width - 6)
        for index in range(self.calendar_task_list.count()):
            item = self.calendar_task_list.item(index)
            widget = self.calendar_task_list.itemWidget(item)
            if item is None or widget is None:
                continue
            widget.setFixedWidth(available_width)
            widget.layout().activate()
            widget.adjustSize()
            item.setSizeHint(QSize(available_width, widget.sizeHint().height() + 4))

    def _refresh_calendar_task_card_selection(self):
        if not hasattr(self, "calendar_task_list"):
            return
        current_item = self.calendar_task_list.currentItem()
        for index in range(self.calendar_task_list.count()):
            item = self.calendar_task_list.item(index)
            card = self.calendar_task_list.itemWidget(item)
            if not isinstance(card, QFrame):
                continue
            task_done = bool(item.data(Qt.ItemDataRole.UserRole + 1))
            self._apply_calendar_task_card_style(card, task_done, selected=item is current_item)

    def _refresh_gantt(self):
        window_start = self._gantt_window_start()
        if self.gantt_view_mode == "week":
            periods = self._build_gantt_week_periods(window_start)
        else:
            periods = self._build_gantt_month_periods(window_start)

        window_end = periods[-1][2].addDays(-1) if periods else window_start
        if self.gantt_view_mode == "week":
            self.gant_month_label.setText(
                f"{window_start.toString('dd MMM yyyy')} - {window_end.toString('dd MMM yyyy')}"
            )
        else:
            self.gant_month_label.setText(
                f"{window_start.toString('MMM yyyy')} - {window_end.toString('MMM yyyy')}"
            )

        restored_row = self._row_for_selected_key()
        current_row = self._current_gantt_row()
        if restored_row is not None:
            target_row = restored_row
        elif self.tasks and current_row is None:
            target_row = 0
            self.selected_task_key = self._task_key(self.tasks[0])
        else:
            target_row = current_row

        self.gantt_chart_widget.set_data(
            self.tasks,
            periods,
            selected_row=target_row,
            view_mode=self.gantt_view_mode,
            task_column_width=self.gantt_task_column_width,
            horizontal_scroll_value=self.gantt_horizontal_scroll,
        )
        self.gantt_task_column_width = self.gantt_chart_widget.task_column_width()
        self.gantt_horizontal_scroll = self.gantt_chart_widget.horizontal_scroll_value()
        self._sync_gantt_row_selection(target_row)
        self._refresh_details()

    def _gantt_window_start(self) -> QDate:
        if self.gantt_view_mode == "week":
            return self._start_of_week(self.selected_date)
        return QDate(self.selected_date.year(), self.selected_date.month(), 1)

    def _start_of_week(self, date: QDate) -> QDate:
        return date.addDays(1 - date.dayOfWeek())

    def _build_gantt_month_periods(self, start_month: QDate):
        periods: list[tuple[str, QDate, QDate]] = []
        current = start_month
        for _ in range(self.GANTT_MONTH_VIEW_MONTHS):
            next_month = current.addMonths(1)
            periods.append((current.toString("MMM\nyyyy"), current, next_month))
            current = next_month
        return periods

    def _build_gantt_week_periods(self, week_start: QDate):
        periods: list[tuple[str, QDate, QDate]] = []
        current = week_start
        for _ in range(self.GANTT_WEEK_VIEW_DAYS):
            next_day = current.addDays(1)
            periods.append((current.toString("ddd\ndd MMM"), current, next_day))
            current = next_day
        return periods

    def _refresh_details(self):
        task = self._selected_task()
        if task is None:
            self.gant_details.setText("Select a task to see its details.")
            return

        detail = f"{task.title}\n{task.start_date} to {task.end_date}"
        if task.notes:
            detail += f"\n\n{task.notes}"
        self.gant_details.setText(detail)

    def _refresh_todo_ui(self):
        self._refresh_timer_controls()
        self._refresh_timer_display()
        self._refresh_todo_list()

    def _refresh_timer_controls(self):
        has_subject = self.subject_name is not None
        self.timer_mode_combo.blockSignals(True)
        self._refresh_timer_mode_combo_labels()
        combo_index = self.timer_mode_combo.findData(self.selected_timer_mode)
        if combo_index >= 0:
            self.timer_mode_combo.setCurrentIndex(combo_index)
        self.timer_mode_combo.setEnabled(has_subject)
        self.timer_mode_combo.blockSignals(False)

        self.timer_toggle_button.setEnabled(has_subject)
        self.timer_reset_button.setEnabled(has_subject)
        self.todo_input.setEnabled(has_subject)
        self.todo_add_button.setEnabled(has_subject)
        self.todo_remove_button.setEnabled(
            has_subject and self.todo_list_widget.currentRow() >= 0 and bool(self.todo_items)
        )
        self._update_timer_toggle_icon()

        if has_subject:
            custom_minutes = max(1, self.custom_timer_seconds // 60)
            self.timer_helper_label.setText(
                "Choose Pomodoro, Custom, or one of the subject quiz timers, then start, pause, or reset the countdown. "
                f"Custom is currently set to {custom_minutes} minute{'s' if custom_minutes != 1 else ''}."
            )
        else:
            self.timer_helper_label.setText("Select a subject to use the Pomodoro timer and checklist.")

    def _refresh_timer_display(self):
        minutes, seconds = divmod(max(self.remaining_seconds, 0), 60)
        self.timer_mode_label.setText(self._preset_label(self.selected_timer_mode))
        self.timer_display.setText(f"{minutes:02d}:{seconds:02d}")

    def _on_timer_mode_combo_changed(self):
        mode = self.timer_mode_combo.currentData()
        if isinstance(mode, str):
            self._select_timer_mode(mode)

    def _refresh_todo_list(self):
        self._loading_todo_list = True
        self.todo_list_widget.blockSignals(True)
        self.todo_list_widget.clear()
        for todo_item in self.todo_items:
            item = QListWidgetItem(todo_item.text)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Checked if todo_item.done else Qt.CheckState.Unchecked)
            
            # Set green color for completed items
            if todo_item.done:
                item.setForeground(QColor("#34d399"))  # Green color
            else:
                item.setForeground(QColor("#dbe7f5"))  # Default light color
            
            self.todo_list_widget.addItem(item)
        self.todo_list_widget.blockSignals(False)
        self._loading_todo_list = False
        self._refresh_timer_controls()

    def _task_overlaps_date(self, task: TimeTask, date: QDate) -> bool:
        start = task.start_qdate()
        end = task.end_qdate()
        return start.isValid() and end.isValid() and start <= date <= end

    def _current_gantt_row(self) -> int | None:
        return self.gantt_chart_widget.current_row()

    def _selected_task_index(self) -> int | None:
        row = self._current_gantt_row()
        if row is not None:
            return row
        restored_row = self._row_for_selected_key()
        if restored_row is not None:
            return restored_row
        return None

    def _task_key(self, task: TimeTask) -> tuple[str, str, str]:
        return (task.title, task.start_date, task.end_date)

    def _row_for_selected_key(self) -> int | None:
        if self.selected_task_key is None:
            return None
        for index, task in enumerate(self.tasks):
            if self._task_key(task) == self.selected_task_key:
                return index
        return None

    def _selected_task(self) -> TimeTask | None:
        index = self._selected_task_index()
        if index is None:
            return None
        return self.tasks[index]

    def _shift_gantt_window(self, delta: int):
        if self.gantt_view_mode == "week":
            self.selected_date = self._start_of_week(self.selected_date).addDays(delta * 7)
        else:
            self.selected_date = QDate(self.selected_date.year(), self.selected_date.month(), 1).addMonths(delta)
        self.calendar_widget.setSelectedDate(self.selected_date)
        self._refresh_all()
        self._save()

    def _on_gantt_view_mode_changed(self):
        mode = self.gant_view_mode_combo.currentData()
        if mode not in {"month", "week"}:
            mode = "month"
        self.gantt_view_mode = mode
        if mode == "week":
            self.selected_date = self._start_of_week(self.selected_date)
        self._refresh_gantt()

    def _on_calendar_date_changed(self):
        self.selected_date = self.calendar_widget.selectedDate()
        self._refresh_all()
        self._save()

    def _jump_to_date(self, date: QDate):
        self.selected_date = date
        self.calendar_widget.setSelectedDate(date)
        self._refresh_all()
        self._save()

    def _on_gant_cell_clicked(self, row: int, column: int):
        if row < 0 or row >= len(self.tasks):
            return
        self.selected_task_key = self._task_key(self.tasks[row])
        self._sync_gantt_row_selection(row)
        self._refresh_details()

    def _on_gant_selection_changed(self):
        if self._syncing_gantt_selection:
            return

        current = self._current_gantt_row()
        if current is not None:
            self.selected_task_key = self._task_key(self.tasks[current])
            self._sync_gantt_row_selection(current)
        else:
            self.selected_task_key = None
        self._refresh_details()
        self._sync_calendar_task_selection()

    def _clear_gantt_selection(self):
        self._sync_gantt_row_selection(None)
        self.selected_task_key = None
        self._refresh_details()
        self._sync_calendar_task_selection()

    def _sync_calendar_task_selection(self):
        if not hasattr(self, "calendar_task_list"):
            return
        selected_task = self._selected_task()
        selected_key = self._task_key(selected_task) if selected_task is not None else None
        self._loading_calendar_task_list = True
        if selected_key is None:
            self.calendar_task_list.clearSelection()
            self._refresh_calendar_task_card_selection()
            self._loading_calendar_task_list = False
            return

        for index in range(self.calendar_task_list.count()):
            item = self.calendar_task_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == selected_key:
                self.calendar_task_list.setCurrentItem(item)
                self._refresh_calendar_task_card_selection()
                self._loading_calendar_task_list = False
                return
        self.calendar_task_list.clearSelection()
        self._refresh_calendar_task_card_selection()
        self._loading_calendar_task_list = False

    def _on_calendar_task_selection_changed(self):
        if self._loading_calendar_task_list:
            return
        self._refresh_calendar_task_card_selection()
        item = self.calendar_task_list.currentItem()
        if item is None:
            return
        task_key = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(task_key, tuple):
            return
        for row, task in enumerate(self.tasks):
            if self._task_key(task) == task_key:
                self.selected_task_key = task_key
                self._sync_gantt_row_selection(row)
                self._refresh_details()
                return

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        try:
            if hasattr(self, "calendar_task_list") and self.calendar_task_list is not None:
                calendar_viewport = self.calendar_task_list.viewport()
                if watched is calendar_viewport and event.type() == QEvent.Type.Resize:
                    self._schedule_calendar_task_card_resize()
                    return super().eventFilter(watched, event)
        except RuntimeError:
            # Object already deleted
            pass
            
        if watched in self._gantt_clear_targets and event.type() == QEvent.Type.MouseButtonPress:
            if watched is self.gant_page:
                child = self.gant_page.childAt(event.position().toPoint())
                if child is self.gantt_chart_widget or child is self.gantt_chart_widget.viewport():
                    return super().eventFilter(watched, event)
                if child is not None and (
                    self.gantt_chart_widget.isAncestorOf(child)
                ):
                    return super().eventFilter(watched, event)
            self._clear_gantt_selection()
        return super().eventFilter(watched, event)

    def _select_timer_mode(self, mode: str):
        if self.subject_name is None or mode not in self.TIMER_PRESETS:
            return

        previous_mode = self.selected_timer_mode
        if mode == "custom":
            current_minutes = max(1, self.custom_timer_seconds // 60)
            minutes, accepted = QInputDialog.getInt(
                self.todo_page,
                "Custom Timer",
                "Set custom timer length (minutes):",
                current_minutes,
                1,
                24 * 60,
                1,
            )
            if not accepted:
                revert_index = self.timer_mode_combo.findData(previous_mode)
                if revert_index >= 0:
                    self.timer_mode_combo.blockSignals(True)
                    self.timer_mode_combo.setCurrentIndex(revert_index)
                    self.timer_mode_combo.blockSignals(False)
                return
            self.custom_timer_seconds = minutes * 60

        self.countdown_timer.stop()
        self.selected_timer_mode = mode
        self.remaining_seconds = self._preset_seconds(mode)
        self._refresh_todo_ui()
        self._save()

    def start_timer(self):
        if self.subject_name is None:
            QMessageBox.information(self.todo_page, "Select Subject", "Choose a subject first.")
            return
        if self.remaining_seconds <= 0:
            self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
            self._refresh_timer_display()
        self.countdown_timer.start()
        self._refresh_timer_controls()

    def pause_timer(self):
        self.countdown_timer.stop()
        self._refresh_timer_controls()

    def toggle_timer(self):
        if self.countdown_timer.isActive():
            self.pause_timer()
            return
        self.start_timer()

    def reset_timer(self):
        self.countdown_timer.stop()
        self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
        self._refresh_todo_ui()

    def _tick_timer(self):
        if self.remaining_seconds <= 0:
            self.countdown_timer.stop()
            self._refresh_todo_ui()
            return

        self.remaining_seconds -= 1
        self._refresh_timer_display()

        if self.remaining_seconds > 0:
            return

        self.countdown_timer.stop()
        self._refresh_timer_controls()
        auto_submitted = False
        if self.selected_timer_mode == "long_quiz" and callable(self.long_quiz_timeout_handler):
            try:
                auto_submitted = bool(self.long_quiz_timeout_handler())
            except Exception:
                auto_submitted = False
        
        # Record the activity
        self._record_activity(self.selected_timer_mode)
        
        self._play_alarm_sound()
        message = f"{self._preset_label(self.selected_timer_mode)} is done."
        if auto_submitted:
            message += " The current long quiz was auto-submitted and unanswered questions were marked wrong."
        QMessageBox.information(self.todo_page, "Timer Complete", message)

    def _play_alarm_sound(self):
        """Play the alarm sound when timer completes."""
        self._alarm_fallback_armed = True
        alarm_path = self._resolve_alarm_sound_path()
        if alarm_path is None:
            self._play_platform_alarm_fallback()
            return

        try:
            source = QUrl.fromLocalFile(str(alarm_path))
            self.media_player.stop()
            if self.media_player.source() == source:
                self.media_player.setPosition(0)
            else:
                self.media_player.setSource(source)
            self.media_player.play()
            # Some Windows/packaged Qt builds accept the source but never start playback.
            QTimer.singleShot(250, self._ensure_alarm_playback_started)
        except Exception:
            self._play_platform_alarm_fallback()

    def _resolve_alarm_sound_path(self) -> Path | None:
        audio_root = _runtime_root() / "assets" / "audio"
        preferred_names = [
            "Classic Alarm Clock - Sound Effect  ProSounds.wav",
            "Classic Alarm Clock - Sound Effect  ProSounds.mp3",
        ]
        candidates: list[Path] = [audio_root / name for name in preferred_names]
        candidates.extend(sorted(audio_root.glob("*.wav")))
        candidates.extend(sorted(audio_root.glob("*.mp3")))

        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.exists():
                return candidate
        return None

    def _ensure_alarm_playback_started(self):
        if not self._alarm_fallback_armed:
            return
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._alarm_fallback_armed = False
            return
        self._play_platform_alarm_fallback()

    def _on_alarm_media_error(self, *args):
        self._play_platform_alarm_fallback()

    def _play_platform_alarm_fallback(self):
        if not self._alarm_fallback_armed:
            return
        self._alarm_fallback_armed = False

        if sys.platform.startswith("win") and winsound is not None:
            try:
                winsound.PlaySound(
                    "SystemExclamation",
                    winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                return
            except Exception:
                pass
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return
            except Exception:
                pass

        QApplication.beep()

    def _record_activity(self, activity_type: str):
        """Record a completed activity."""
        today = QDate.currentDate().toString(Qt.DateFormat.ISODate)
        duration = self._preset_seconds(activity_type)
        activity = ActivityRecord(date=today, activity_type=activity_type, duration_seconds=duration)
        self.activities.append(activity)
        self._refresh_activity_overview()
        self._save()

    def _refresh_activity_overview(self):
        """Refresh the activity overview display."""
        if self.activity_overview_page is not None and hasattr(self, 'activity_overview_widget'):
            self.activity_overview_widget.set_activities(self.activities)

    def add_todo_item(self):
        if self.subject_name is None:
            QMessageBox.information(self.todo_page, "Select Subject", "Choose a subject first.")
            return

        text = self.todo_input.text().strip()
        if not text:
            QMessageBox.warning(self.todo_page, "Invalid Todo", "Please enter a todo item.")
            return

        self.todo_items.append(TodoItem(text=text))
        self.todo_input.clear()
        self._refresh_all()
        self._save()

    def remove_selected_todo_item(self):
        row = self.todo_list_widget.currentRow()
        if row < 0 or row >= len(self.todo_items):
            QMessageBox.information(self.todo_page, "Select Todo", "Choose a todo item to remove.")
            return

        del self.todo_items[row]
        self._refresh_all()
        self._save()

    def _on_todo_item_changed(self, item: QListWidgetItem):
        if self._loading_todo_list:
            return

        row = self.todo_list_widget.row(item)
        if row < 0 or row >= len(self.todo_items):
            return

        self.todo_items[row].done = item.checkState() == Qt.CheckState.Checked
        self._refresh_status()
        self._save()

    def add_task(self):
        if self.subject_name is None:
            QMessageBox.information(self.gant_page, "Select Subject", "Choose a subject first.")
            return

        dialog = TimeTaskDialog(self.gant_page)
        dialog.start_edit.setDate(self.selected_date)
        dialog.end_edit.setDate(self.selected_date)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            task = dialog.to_task(subject=self.subject_name)
        except ValueError as exc:
            QMessageBox.warning(self.gant_page, "Invalid Task", str(exc))
            return

        self.tasks.append(task)
        self.tasks.sort(key=lambda item: (item.start_date, item.end_date, item.title.lower()))
        self.selected_task_key = self._task_key(task)
        self._refresh_all()
        self._save()

    def edit_task(self):
        index = self._selected_task_index()
        if index is None:
            QMessageBox.information(self.gant_page, "Select Task", "Choose a task to edit.")
            return

        task = self.tasks[index]
        dialog = TimeTaskDialog(self.gant_page, task)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            updated = dialog.to_task(subject=self.subject_name or "")
        except ValueError as exc:
            QMessageBox.warning(self.gant_page, "Invalid Task", str(exc))
            return

        self.tasks[index] = updated
        self.tasks.sort(key=lambda item: (item.start_date, item.end_date, item.title.lower()))
        self.selected_task_key = self._task_key(updated)
        self._refresh_all()
        self._save()

    def delete_task(self):
        index = self._selected_task_index()
        if index is None:
            QMessageBox.information(self.gant_page, "Select Task", "Choose a task to delete.")
            return

        confirm = QMessageBox.question(
            self.gant_page,
            "Delete Task",
            "Delete the selected task?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        del self.tasks[index]
        self.selected_task_key = (
            self._task_key(self.tasks[min(index, len(self.tasks) - 1)]) if self.tasks else None
        )
        self._refresh_all()
        self._save()

    def import_backup(self, payload: dict[str, Any]):
        self._flush_gantt_state_save()
        if not isinstance(payload, dict):
            return

        raw_tasks = payload.get("tasks", [])
        self.tasks = []
        if isinstance(raw_tasks, list):
            for entry in raw_tasks:
                if isinstance(entry, dict):
                    task = TimeTask.from_dict(entry)
                    if task.title and task.start_date and task.end_date:
                        self.tasks.append(task)

        raw_todo_items = payload.get("todo_items", [])
        self.todo_items = []
        if isinstance(raw_todo_items, list):
            for entry in raw_todo_items:
                if isinstance(entry, dict):
                    todo_item = TodoItem.from_dict(entry)
                    if todo_item.text:
                        self.todo_items.append(todo_item)

        stored_custom_seconds = payload.get("custom_timer_seconds")
        if isinstance(stored_custom_seconds, int) and stored_custom_seconds >= 60:
            self.custom_timer_seconds = stored_custom_seconds
        else:
            self.custom_timer_seconds = self.TIMER_PRESETS["custom"][1]

        timer_mode = payload.get("selected_timer_mode")
        if isinstance(timer_mode, str) and timer_mode in self.TIMER_PRESETS:
            self.selected_timer_mode = timer_mode
        else:
            self.selected_timer_mode = "pomodoro"
        self.remaining_seconds = self._preset_seconds(self.selected_timer_mode)
        stored_task_width = payload.get("gantt_task_column_width")
        if isinstance(stored_task_width, int):
            self.gantt_task_column_width = max(
                GanttChartWidget.MIN_TASK_COLUMN_WIDTH,
                stored_task_width,
            )
        else:
            self.gantt_task_column_width = GanttChartWidget.DEFAULT_TASK_COLUMN_WIDTH
        stored_horizontal_scroll = payload.get("gantt_horizontal_scroll")
        self.gantt_horizontal_scroll = stored_horizontal_scroll if isinstance(stored_horizontal_scroll, int) else 0

        self.selected_date = self._parse_date(payload.get("selected_date")) or QDate.currentDate()
        self.selected_task_key = self._task_key(self.tasks[0]) if self.tasks else None
        self.countdown_timer.stop()
        self._refresh_all()
        self._save()

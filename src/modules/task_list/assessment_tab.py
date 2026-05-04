import json
import math
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QTabWidget,
    QFrame,
    QHeaderView,
)

from .quiz_tab import QuizAttempt, QuestionResult, load_quiz_bank_from_path, slugify


class TagPieChartWidget(QWidget):
    tagSelected = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._segments: list[tuple[str, int, QColor]] = []
        self._selected_tag: str | None = None
        self._pie_rect = QRectF()
        self._segment_ranges: list[tuple[str, float, float]] = []
        self._legend_rects: list[tuple[str, QRectF]] = []
        self.setMinimumHeight(280)

    def set_segments(self, segments: list[tuple[str, int, QColor]]):
        self._segments = [(tag, max(0, value), color) for tag, value, color in segments if value > 0]
        available_tags = {tag for tag, _value, _color in self._segments}
        if self._selected_tag not in available_tags:
            self._selected_tag = self._segments[0][0] if self._segments else None
        self.update()

    def set_selected_tag(self, tag: str | None):
        self._selected_tag = tag
        self.update()

    def selected_tag(self) -> str | None:
        return self._selected_tag

    def mousePressEvent(self, event):
        point = event.position()

        for tag, rect in self._legend_rects:
            if rect.contains(point):
                self._selected_tag = tag
                self.update()
                self.tagSelected.emit(tag)
                return

        if not self._pie_rect.contains(point):
            return

        center = self._pie_rect.center()
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        radius = self._pie_rect.width() / 2
        distance = math.hypot(dx, dy)
        if distance > radius or distance <= 0:
            return

        angle = math.degrees(math.atan2(center.y() - point.y(), point.x() - center.x()))
        if angle < 0:
            angle += 360
        relative_angle = (90 - angle) % 360

        for tag, start_angle, end_angle in self._segment_ranges:
            if start_angle <= relative_angle < end_angle:
                self._selected_tag = tag
                self.update()
                self.tagSelected.emit(tag)
                return

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if not self._segments:
            painter.setPen(QColor("#9fb2cc"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No weak-area tag data yet.")
            self._pie_rect = QRectF()
            self._segment_ranges = []
            self._legend_rects = []
            return

        margin = 16
        legend_width = min(240, max(180, self.width() // 3))
        pie_size = min(
            max(160, self.height() - margin * 2),
            max(160, self.width() - legend_width - margin * 3),
        )
        pie_size = min(pie_size, self.height() - margin * 2)
        pie_x = margin
        pie_y = max(margin, (self.height() - pie_size) / 2)
        self._pie_rect = QRectF(pie_x, pie_y, pie_size, pie_size)
        self._segment_ranges = []
        self._legend_rects = []

        total = sum(value for _tag, value, _color in self._segments)
        current_angle = 0.0
        for tag, value, color in self._segments:
            span = (value / total) * 360 if total else 0
            is_selected = tag == self._selected_tag
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#f8fbff") if is_selected else QColor("#0b1220"), 3 if is_selected else 1))
            painter.drawPie(
                self._pie_rect,
                int((90 - current_angle) * 16),
                int(-span * 16),
            )
            self._segment_ranges.append((tag, current_angle, current_angle + span))
            current_angle += span

        legend_x = self._pie_rect.right() + 24
        legend_y = margin + 8
        painter.setPen(QColor("#edf4ff"))
        painter.drawText(int(legend_x), int(legend_y), "Tags")
        legend_y += 16

        for tag, value, color in self._segments:
            row_rect = QRectF(legend_x - 8, legend_y - 12, legend_width - 8, 24)
            is_selected = tag == self._selected_tag
            if is_selected:
                painter.fillRect(row_rect, QColor("#132136"))
                painter.setPen(QPen(QColor("#2f74ff"), 1))
                painter.drawRoundedRect(row_rect, 8, 8)
            painter.fillRect(int(legend_x), int(legend_y - 6), 14, 14, color)
            painter.setPen(QColor("#edf4ff"))
            painter.drawText(
                int(legend_x + 24),
                int(legend_y + 6),
                f"{tag} ({value})",
            )
            self._legend_rects.append((tag, row_rect))
            legend_y += 28


class AssessmentTabController:
    """Manages the Assessment tab for analyzing quiz results."""

    WEAK_AREA_TAG_COLORS = [
        QColor("#2f74ff"),
        QColor("#34d399"),
        QColor("#f59e0b"),
        QColor("#ef4444"),
        QColor("#a78bfa"),
        QColor("#22d3ee"),
        QColor("#f472b6"),
        QColor("#84cc16"),
    ]

    def __init__(self, page: QWidget):
        self.page = page
        self.subject_name: str | None = None
        self.storage_path: Path | None = None
        self.results_root = Path(__file__).resolve().parent.parent / "gant_chart"
        self.quiz_bank_root = Path(__file__).resolve().parent.parent / "quiz_banks"
        self.attempts: list[QuizAttempt] = []
        self.subject_resolver: Callable[[], str | None] | None = None
        self._selected_weak_tag: str | None = None
        self._weak_area_questions_by_tag: dict[str, list[dict[str, Any]]] = {}

        self._build_ui()
        self._wire_signals()
        self._refresh_ui()

    def _build_ui(self):
        """Build the assessment UI."""
        layout = QVBoxLayout(self.page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header
        header = QLabel("Assessment & Analytics", self.page)
        header.setStyleSheet("font-size: 16pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(header)

        # Main tabs
        self.tabs = QTabWidget(self.page)

        # Overview tab
        self.overview_tab = QWidget()
        self._build_overview_tab()
        self.tabs.addTab(self.overview_tab, "Overview")

        # History tab
        self.history_tab = QWidget()
        self._build_history_tab()
        self.tabs.addTab(self.history_tab, "Attempt History")

        # Chapter Performance tab
        self.chapter_tab = QWidget()
        self._build_chapter_tab()
        self.tabs.addTab(self.chapter_tab, "Chapter Performance")

        # Weak Areas tab
        self.weak_areas_tab = QWidget()
        self._build_weak_areas_tab()
        self.tabs.addTab(self.weak_areas_tab, "Weak Areas")

        layout.addWidget(self.tabs, 1)

        # Bottom toolbar
        toolbar = QFrame(self.page)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.export_button = QPushButton("Export Results (JSON)", toolbar)
        self.clear_button = QPushButton("Clear All Results", toolbar)
        self.refresh_button = QPushButton("Refresh", toolbar)

        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.refresh_button)
        toolbar_layout.addWidget(self.export_button)
        toolbar_layout.addWidget(self.clear_button)

        layout.addWidget(toolbar)

    def _build_overview_tab(self):
        """Build overview statistics tab."""
        layout = QVBoxLayout(self.overview_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Stats cards
        stats_frame = QFrame(self.overview_tab)
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)

        self.total_attempts_label = QLabel("Total Attempts: 0")
        self.overall_accuracy_label = QLabel("Overall Accuracy: 0%")
        self.avg_score_label = QLabel("Average Score: 0/0")
        self.total_time_label = QLabel("Total Time Spent: 0h 0m")

        for label in [
            self.total_attempts_label,
            self.overall_accuracy_label,
            self.avg_score_label,
            self.total_time_label,
        ]:
            label.setStyleSheet(
                "padding: 16px; background-color: #132136; border: 1px solid #23314a; "
                "border-radius: 8px; color: #edf4ff; font-weight: 600;"
            )
            stats_layout.addWidget(label, 1)

        layout.addWidget(stats_frame, 0)

        # Progress section
        progress_label = QLabel("Recent Progress (Last 5 Attempts)")
        progress_label.setStyleSheet("font-size: 11pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(progress_label)

        self.progress_list = QListWidget(self.overview_tab)
        self.progress_list.setMaximumHeight(250)
        layout.addWidget(self.progress_list)

        layout.addStretch(1)

    def _build_history_tab(self):
        """Build attempt history tab."""
        layout = QVBoxLayout(self.history_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        label = QLabel("All Attempts")
        label.setStyleSheet("font-size: 11pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(label)

        self.history_table = QTableWidget(self.history_tab)
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["Date & Time", "Quiz Type", "Chapter", "Score", "Duration", "Accuracy"]
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.history_table)

    def _build_chapter_tab(self):
        """Build chapter performance tab."""
        layout = QVBoxLayout(self.chapter_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        label = QLabel("Performance by Chapter")
        label.setStyleSheet("font-size: 11pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(label)

        self.chapter_table = QTableWidget(self.chapter_tab)
        self.chapter_table.setColumnCount(5)
        self.chapter_table.setHorizontalHeaderLabels(
            ["Chapter", "Attempts", "Avg Score", "Avg Accuracy", "Best Score"]
        )
        self.chapter_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self.chapter_table)

    def _build_weak_areas_tab(self):
        """Build weak areas (frequently missed questions) tab."""
        layout = QVBoxLayout(self.weak_areas_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        label = QLabel("Weak Areas by Tag")
        label.setStyleSheet("font-size: 11pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(label)

        helper_label = QLabel(
            "Select a pie slice or legend tag to view the missed questions grouped under that tag."
        )
        helper_label.setWordWrap(True)
        helper_label.setStyleSheet("color: #9fb2cc;")
        layout.addWidget(helper_label)

        self.weak_area_chart = TagPieChartWidget(self.weak_areas_tab)
        layout.addWidget(self.weak_area_chart)

        self.weak_area_selection_label = QLabel("Questions")
        self.weak_area_selection_label.setStyleSheet("font-size: 10.5pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(self.weak_area_selection_label)

        self.weak_areas_list = QListWidget(self.weak_areas_tab)
        self.weak_areas_list.setAlternatingRowColors(True)
        layout.addWidget(self.weak_areas_list)

    def _wire_signals(self):
        """Connect signals to slots."""
        self.export_button.clicked.connect(self.export_results)
        self.clear_button.clicked.connect(self.clear_all_results)
        self.refresh_button.clicked.connect(self._refresh_ui)
        self.weak_area_chart.tagSelected.connect(self._on_weak_area_tag_selected)

    def set_subject(self, subject_name: str | None):
        """Set the current subject and load its assessment data."""
        self.subject_name = (
            subject_name.strip() if isinstance(subject_name, str) and subject_name.strip() else None
        )

        if self.subject_name is None:
            self.storage_path = None
            self.attempts = []
            self._refresh_ui()
            return

        self.storage_path = self.results_root / f"{slugify(self.subject_name)}.json"
        self._load_attempts()

    def set_subject_resolver(self, resolver: Callable[[], str | None]):
        """Set a function that resolves the current subject."""
        self.subject_resolver = resolver

    def set_storage_roots(self, *, results_root: str | Path, quiz_bank_root: str | Path):
        """Configure persistent storage roots for results and quiz-bank lookups."""
        self.results_root = Path(results_root)
        self.quiz_bank_root = Path(quiz_bank_root)
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.quiz_bank_root.mkdir(parents=True, exist_ok=True)
        if self.subject_name:
            self.storage_path = self.results_root / f"{slugify(self.subject_name)}.json"
            self._load_attempts()

    def _load_attempts(self):
        """Load quiz attempts from storage."""
        if self.storage_path is None or not self.storage_path.exists():
            self.attempts = []
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self.attempts = []
            return

        self.attempts = []
        attempts_payload = payload.get("quiz_attempts", [])
        if isinstance(attempts_payload, list):
            for entry in attempts_payload:
                attempt = QuizAttempt.from_dict(entry)
                if attempt is not None:
                    self.attempts.append(attempt)

        # Sort by timestamp (newest first)
        self.attempts.sort(key=lambda a: a.timestamp, reverse=True)
        self._refresh_ui()

    def _save_attempts(self):
        """Save quiz attempts to storage."""
        if self.storage_path is None:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing data to preserve non-attempt data
        existing_payload = {}
        if self.storage_path.exists():
            try:
                with self.storage_path.open("r", encoding="utf-8") as handle:
                    existing_payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                pass

        existing_payload["quiz_attempts"] = [attempt.to_dict() for attempt in self.attempts]

        try:
            with self.storage_path.open("w", encoding="utf-8") as handle:
                json.dump(existing_payload, handle, indent=2)
        except OSError:
            pass

    def save_quiz_attempt(self, attempt: QuizAttempt):
        """Save a new quiz attempt."""
        self.attempts.insert(0, attempt)
        self._save_attempts()
        self._refresh_ui()

    def _refresh_ui(self):
        """Refresh all UI elements with current data."""
        self._refresh_overview()
        self._refresh_history()
        self._refresh_chapter_performance()
        self._refresh_weak_areas()

    def _refresh_overview(self):
        """Refresh overview statistics."""
        if not self.attempts:
            self.total_attempts_label.setText("Total Attempts: 0")
            self.overall_accuracy_label.setText("Overall Accuracy: 0%")
            self.avg_score_label.setText("Average Score: 0/0")
            self.total_time_label.setText("Total Time Spent: 0h 0m")
            self.progress_list.clear()
            return

        total_attempts = len(self.attempts)
        total_correct = sum(a.correct_count for a in self.attempts)
        total_answered = sum(a.answered_count for a in self.attempts)
        total_questions = sum(a.total_questions for a in self.attempts)
        total_seconds = sum(a.duration_seconds for a in self.attempts)

        overall_accuracy = (total_correct / total_answered * 100) if total_answered > 0 else 0
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        self.total_attempts_label.setText(f"Total Attempts: {total_attempts}")
        self.overall_accuracy_label.setText(f"Overall Accuracy: {overall_accuracy:.1f}%")
        self.avg_score_label.setText(f"Average Score: {total_correct}/{total_questions}")
        self.total_time_label.setText(f"Total Time Spent: {hours}h {minutes}m")

        # Recent progress
        self.progress_list.clear()
        for attempt in self.attempts[:5]:
            item_text = (
                f"{attempt.timestamp} - {attempt.chapter_title}: "
                f"{attempt.correct_count}/{attempt.answered_count} ({attempt.accuracy_percent:.1f}%)"
            )
            item = QListWidgetItem(item_text)
            self.progress_list.addItem(item)

    def _refresh_history(self):
        """Refresh attempt history table."""
        self.history_table.setRowCount(len(self.attempts))

        for row, attempt in enumerate(self.attempts):
            # Date & Time
            date_item = QTableWidgetItem(attempt.timestamp)
            self.history_table.setItem(row, 0, date_item)

            # Quiz Type
            type_item = QTableWidgetItem(attempt.quiz_type)
            self.history_table.setItem(row, 1, type_item)

            # Chapter
            chapter_item = QTableWidgetItem(attempt.chapter_title)
            self.history_table.setItem(row, 2, chapter_item)

            # Score
            score_item = QTableWidgetItem(f"{attempt.correct_count}/{attempt.total_questions}")
            self.history_table.setItem(row, 3, score_item)

            # Duration
            mins = attempt.duration_seconds // 60
            secs = attempt.duration_seconds % 60
            duration_item = QTableWidgetItem(f"{mins}m {secs}s")
            self.history_table.setItem(row, 4, duration_item)

            # Accuracy
            accuracy_item = QTableWidgetItem(f"{attempt.accuracy_percent:.1f}%")
            accuracy_color = (
                QColor("#34d399") if attempt.accuracy_percent >= 70 else QColor("#f87171")
            )
            accuracy_item.setForeground(accuracy_color)
            self.history_table.setItem(row, 5, accuracy_item)

    def _refresh_chapter_performance(self):
        """Refresh chapter performance table."""
        chapter_stats: dict[str, list[QuizAttempt]] = {}
        for attempt in self.attempts:
            if attempt.chapter_title not in chapter_stats:
                chapter_stats[attempt.chapter_title] = []
            chapter_stats[attempt.chapter_title].append(attempt)

        self.chapter_table.setRowCount(len(chapter_stats))

        for row, (chapter, attempts_list) in enumerate(sorted(chapter_stats.items())):
            avg_score = sum(a.correct_count for a in attempts_list) / len(attempts_list)
            avg_accuracy = sum(a.accuracy_percent for a in attempts_list) / len(attempts_list)
            best_score = max(a.correct_count for a in attempts_list)

            # Chapter name
            self.chapter_table.setItem(row, 0, QTableWidgetItem(chapter))
            # Attempts
            self.chapter_table.setItem(row, 1, QTableWidgetItem(str(len(attempts_list))))
            # Avg Score
            self.chapter_table.setItem(row, 2, QTableWidgetItem(f"{avg_score:.1f}"))
            # Avg Accuracy
            accuracy_item = QTableWidgetItem(f"{avg_accuracy:.1f}%")
            accuracy_color = (
                QColor("#34d399") if avg_accuracy >= 70 else QColor("#f87171")
            )
            accuracy_item.setForeground(accuracy_color)
            self.chapter_table.setItem(row, 3, accuracy_item)
            # Best Score
            self.chapter_table.setItem(row, 4, QTableWidgetItem(str(best_score)))

    def _refresh_weak_areas(self):
        """Refresh weak areas as a tag pie chart and question list."""
        tag_counts: dict[str, int] = {}
        questions_by_tag: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
        question_lookup = self._load_question_metadata_lookup()

        for attempt in self.attempts:
            for qr in attempt.question_results:
                if qr.is_correct:
                    continue

                lookup_key = self._question_lookup_key(qr.chapter_title, qr.question_text)
                question_meta = question_lookup.get(lookup_key)
                tags = question_meta["tags"] if question_meta else []
                if not tags:
                    tags = ["Untagged"]

                chapter_title = question_meta["chapter_title"] if question_meta else qr.chapter_title
                question_text = question_meta["question_text"] if question_meta else qr.question_text
                question_index = question_meta["index"] if question_meta else "?"

                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                    tag_questions = questions_by_tag.setdefault(tag, {})
                    question_key = self._question_lookup_key(chapter_title, question_text)
                    if question_key not in tag_questions:
                        tag_questions[question_key] = {
                            "chapter_title": chapter_title,
                            "index": question_index,
                            "question_text": question_text,
                            "miss_count": 0,
                        }
                    tag_questions[question_key]["miss_count"] += 1

        sorted_tags = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)
        self._weak_area_questions_by_tag = {
            tag: sorted(
                questions.values(),
                key=lambda entry: (-entry["miss_count"], str(entry["chapter_title"]).lower(), str(entry["index"])),
            )
            for tag, questions in questions_by_tag.items()
        }

        segments = [
            (tag, count, self.WEAK_AREA_TAG_COLORS[index % len(self.WEAK_AREA_TAG_COLORS)])
            for index, (tag, count) in enumerate(sorted_tags)
        ]
        self.weak_area_chart.set_segments(segments)

        available_tags = [tag for tag, _count in sorted_tags]
        if self._selected_weak_tag not in available_tags:
            self._selected_weak_tag = available_tags[0] if available_tags else None
        self.weak_area_chart.set_selected_tag(self._selected_weak_tag)
        self._refresh_weak_area_question_list()

    def _question_lookup_key(self, chapter_title: str, question_text: str) -> tuple[str, str]:
        return chapter_title.strip().casefold(), question_text.strip().casefold()

    def _quiz_bank_root(self) -> Path:
        return self.quiz_bank_root

    def _load_question_metadata_lookup(self) -> dict[tuple[str, str], dict[str, Any]]:
        if not self.subject_name:
            return {}

        subject_dir = self._quiz_bank_root() / slugify(self.subject_name)
        lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for quiz_filename in ("short_quiz.json", "long_quiz.json"):
            quiz_path = subject_dir / quiz_filename
            if not quiz_path.exists():
                continue
            try:
                bank = load_quiz_bank_from_path(quiz_path)
            except Exception:
                continue
            for chapter in bank.chapters:
                for index, question in enumerate(chapter.questions, start=1):
                    key = self._question_lookup_key(chapter.title, question.question)
                    lookup.setdefault(
                        key,
                        {
                            "chapter_title": chapter.title,
                            "question_text": question.question,
                            "index": index,
                            "tags": [tag.strip() for tag in question.tags if tag.strip()],
                        },
                    )
        return lookup

    def _refresh_weak_area_question_list(self):
        self.weak_areas_list.clear()

        if not self._selected_weak_tag:
            self.weak_area_selection_label.setText("Questions")
            self.weak_areas_list.addItem("No weak-area data available yet.")
            return

        questions = self._weak_area_questions_by_tag.get(self._selected_weak_tag, [])
        self.weak_area_selection_label.setText(f"Questions for {self._selected_weak_tag}")
        if not questions:
            self.weak_areas_list.addItem("No missed questions found for this tag.")
            return

        for entry in questions:
            item_text = f"{entry['chapter_title']} : {entry['index']}, {entry['question_text']}"
            item = QListWidgetItem(item_text)
            if int(entry["miss_count"]) >= 3:
                item.setForeground(QColor("#f87171"))
            item.setToolTip(f"Missed {entry['miss_count']} time(s)")
            self.weak_areas_list.addItem(item)

    def _on_weak_area_tag_selected(self, tag: str):
        self._selected_weak_tag = tag
        self._refresh_weak_area_question_list()

    def export_results(self):
        """Export all results to JSON file."""
        if not self.attempts:
            QMessageBox.information(
                self.page,
                "No Results",
                "No quiz results to export.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self.page,
            "Export Assessment Results",
            f"{self.subject_name or 'assessment'}_results.json",
            "JSON Files (*.json)",
        )

        if not file_path:
            return

        try:
            export_data = {
                "subject": self.subject_name,
                "exported_at": datetime.now().isoformat(),
                "total_attempts": len(self.attempts),
                "quiz_attempts": [attempt.to_dict() for attempt in self.attempts],
            }
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(export_data, handle, indent=2)

            QMessageBox.information(
                self.page,
                "Export Success",
                f"Results exported to {Path(file_path).name}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self.page,
                "Export Failed",
                f"Failed to export: {str(exc)}",
            )

    def clear_all_results(self):
        """Clear all quiz results."""
        confirm = QMessageBox.warning(
            self.page,
            "Clear All Results",
            "Are you sure you want to delete all quiz attempts? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            self.attempts = []
            self._save_attempts()
            self._refresh_ui()
            QMessageBox.information(
                self.page,
                "Cleared",
                "All quiz results have been deleted.",
            )

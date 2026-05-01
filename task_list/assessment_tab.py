import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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

from .quiz_tab import QuizAttempt, QuestionResult


class AssessmentTabController:
    """Manages the Assessment tab for analyzing quiz results."""

    def __init__(self, page: QWidget):
        self.page = page
        self.subject_name: str | None = None
        self.storage_path: Path | None = None
        self.attempts: list[QuizAttempt] = []
        self.subject_resolver: Callable[[], str | None] | None = None

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

        label = QLabel("Frequently Missed Questions (Review These!)")
        label.setStyleSheet("font-size: 11pt; font-weight: 700; color: #edf4ff;")
        layout.addWidget(label)

        self.weak_areas_list = QListWidget(self.weak_areas_tab)
        layout.addWidget(self.weak_areas_list)

    def _wire_signals(self):
        """Connect signals to slots."""
        self.export_button.clicked.connect(self.export_results)
        self.clear_button.clicked.connect(self.clear_all_results)
        self.refresh_button.clicked.connect(self._refresh_ui)

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

        base_dir = Path(__file__).resolve().parent.parent / "gant_chart"
        from .quiz_tab import slugify

        self.storage_path = base_dir / f"{slugify(self.subject_name)}.json"
        self._load_attempts()

    def set_subject_resolver(self, resolver: Callable[[], str | None]):
        """Set a function that resolves the current subject."""
        self.subject_resolver = resolver

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
        """Refresh weak areas (frequently missed questions)."""
        missed_questions: dict[str, int] = {}

        for attempt in self.attempts:
            for qr in attempt.question_results:
                if not qr.is_correct:
                    key = f"{qr.chapter_title}: {qr.question_text[:60]}..."
                    missed_questions[key] = missed_questions.get(key, 0) + 1

        self.weak_areas_list.clear()

        # Sort by frequency
        sorted_questions = sorted(missed_questions.items(), key=lambda x: x[1], reverse=True)
        for question, count in sorted_questions[:20]:  # Show top 20
            item_text = f"[Missed {count}x] {question}"
            item = QListWidgetItem(item_text)
            if count >= 3:
                item.setForeground(QColor("#f87171"))  # Red for frequently missed
            self.weak_areas_list.addItem(item)

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

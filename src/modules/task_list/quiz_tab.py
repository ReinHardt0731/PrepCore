import json
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QUrl, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QIntValidator, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QSizePolicy,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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
    QProgressBar,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from app.tree_font_utils import (
    TreeFontConfig,
    apply_font_to_item,
    apply_font_to_widget,
    apply_hierarchical_font_to_item,
)


class QuizFormatError(ValueError):
    pass


QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
QUESTION_TYPE_NUMERIC = "numeric"


def _normalize_question_type(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {QUESTION_TYPE_MULTIPLE_CHOICE, "mcq", "multiple choice"}:
            return QUESTION_TYPE_MULTIPLE_CHOICE
        if normalized in {QUESTION_TYPE_NUMERIC, "field", "numeric field", "integer"}:
            return QUESTION_TYPE_NUMERIC
    return QUESTION_TYPE_MULTIPLE_CHOICE


def _parse_expected_answer(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _format_expected_answer(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _normalized_numeric_user_answer(raw_value: str | None) -> str | None:
    if not isinstance(raw_value, str):
        return None
    stripped = raw_value.strip()
    if not stripped:
        return None
    try:
        return str(int(stripped))
    except ValueError:
        return None


def _numeric_answer_matches(question: "QuizQuestion", raw_value: str | None) -> bool:
    if question.expected_answer is None:
        return False
    normalized = _normalized_numeric_user_answer(raw_value)
    if normalized is None:
        return False
    return abs(int(normalized) - question.expected_answer) <= max(0, question.accepted_deviation)


def slugify(value: str) -> str:
    """Generate a filesystem-safe slug from subject name, preserving emoji."""
    import unicodedata
    
    value = value.strip()
    if not value:
        return "subject"
    
    # Preserve emoji and alphanumeric, convert other problematic characters
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ord(ch) > 127:
            # Preserve emoji and other Unicode symbols
            category = unicodedata.category(ch)
            if category[0] in ('L', 'N', 'S', 'P'):
                # Keep letters, numbers, symbols (including emoji), and punctuation
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


BRANCH_ITEM_KIND_ROLE = int(Qt.ItemDataRole.UserRole)
BRANCH_CHAPTER_TITLE_ROLE = BRANCH_ITEM_KIND_ROLE + 1
TREE_LEAF_PATH_ROLE = BRANCH_ITEM_KIND_ROLE + 2


def split_leaf_path(chapter_path: str) -> tuple[str, str | None]:
    normalized = chapter_path.strip()
    if " / " not in normalized:
        return normalized, None
    chapter_title, subchapter_title = normalized.split(" / ", 1)
    return chapter_title.strip(), subchapter_title.strip() or None


def split_leaf_parts(chapter_path: str) -> list[str]:
    return [part.strip() for part in chapter_path.strip().split(" / ") if part.strip()]


@dataclass
class QuizQuestion:
    question: str
    choices: list[str]
    answer_index: int
    answer_text: str
    explanation: str = ""
    tags: list[str] = field(default_factory=list)
    question_type: str = QUESTION_TYPE_MULTIPLE_CHOICE
    expected_answer: float | None = None
    accepted_deviation: int = 0
    solution_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "question_type": self.question_type,
            "choices": self.choices,
            "answer_index": self.answer_index,
            "answer_text": self.answer_text,
            "explanation": self.explanation,
            "tags": self.tags,
            "expected_answer": self.expected_answer,
            "accepted_deviation": self.accepted_deviation,
            "solution_file": self.solution_file,
        }


@dataclass
class QuizChapter:
    title: str
    questions: list[QuizQuestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "questions": [question.to_dict() for question in self.questions],
        }


@dataclass
class QuizBank:
    quiz_type: str
    subject: str | None = None
    selected_chapter: str = ""
    chapters: list[QuizChapter] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "quiz_type": self.quiz_type,
            "subject": self.subject,
            "selected_chapter": self.selected_chapter,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


@dataclass(frozen=True)
class LongQuizQuestionRef:
    chapter_title: str
    question_text: str

    def to_dict(self) -> dict[str, str]:
        return {
            "chapter_title": self.chapter_title,
            "question_text": self.question_text,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "LongQuizQuestionRef | None":
        if not isinstance(payload, dict):
            return None
        chapter_title = payload.get("chapter_title")
        question_text = payload.get("question_text")
        if not isinstance(chapter_title, str) or not chapter_title.strip():
            return None
        if not isinstance(question_text, str) or not question_text.strip():
            return None
        return cls(
            chapter_title=chapter_title.strip(),
            question_text=question_text.strip(),
        )


@dataclass
class QuestionResult:
    """Result for a single question in a quiz attempt."""
    question_text: str
    chapter_title: str
    correct_answer: str
    user_answer: str | None
    is_correct: bool
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_text": self.question_text,
            "chapter_title": self.chapter_title,
            "correct_answer": self.correct_answer,
            "user_answer": self.user_answer,
            "is_correct": self.is_correct,
            "explanation": self.explanation,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "QuestionResult | None":
        if not isinstance(payload, dict):
            return None
        return cls(
            question_text=str(payload.get("question_text", "")).strip(),
            chapter_title=str(payload.get("chapter_title", "")).strip(),
            correct_answer=str(payload.get("correct_answer", "")).strip(),
            user_answer=payload.get("user_answer"),
            is_correct=bool(payload.get("is_correct", False)),
            explanation=str(payload.get("explanation", "")).strip(),
        )


@dataclass
class QuizAttempt:
    """Records a single quiz attempt with all results and metadata."""
    attempt_id: str
    timestamp: str  # ISO format datetime
    quiz_type: str  # "short_quiz" or "long_quiz"
    chapter_title: str
    total_questions: int
    correct_count: int
    answered_count: int
    duration_seconds: int = 0
    question_results: list[QuestionResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "timestamp": self.timestamp,
            "quiz_type": self.quiz_type,
            "chapter_title": self.chapter_title,
            "total_questions": self.total_questions,
            "correct_count": self.correct_count,
            "answered_count": self.answered_count,
            "duration_seconds": self.duration_seconds,
            "question_results": [qr.to_dict() for qr in self.question_results],
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "QuizAttempt | None":
        if not isinstance(payload, dict):
            return None
        question_results = []
        for qr_payload in payload.get("question_results", []):
            qr = QuestionResult.from_dict(qr_payload)
            if qr is not None:
                question_results.append(qr)
        return cls(
            attempt_id=str(payload.get("attempt_id", "")).strip(),
            timestamp=str(payload.get("timestamp", "")).strip(),
            quiz_type=str(payload.get("quiz_type", "")).strip(),
            chapter_title=str(payload.get("chapter_title", "")).strip(),
            total_questions=int(payload.get("total_questions", 0)),
            correct_count=int(payload.get("correct_count", 0)),
            answered_count=int(payload.get("answered_count", 0)),
            duration_seconds=int(payload.get("duration_seconds", 0)),
            question_results=question_results,
        )

    @property
    def accuracy_percent(self) -> float:
        if self.answered_count == 0:
            return 0.0
        return (self.correct_count / self.answered_count) * 100

    @property
    def unanswered_count(self) -> int:
        return self.total_questions - self.answered_count


def _normalize_question_payload(entry: Any, position: int) -> QuizQuestion:
    if not isinstance(entry, dict):
        raise QuizFormatError(f"Question {position} must be an object.")

    question = entry.get("question")
    question_type = _normalize_question_type(
        entry.get("question_type", QUESTION_TYPE_NUMERIC if "expected_answer" in entry else QUESTION_TYPE_MULTIPLE_CHOICE)
    )
    choices = entry.get("choices")
    answer_index = entry.get("answer_index", entry.get("answer"))
    answer_text = entry.get("answer_text")
    explanation = entry.get("explanation", "")
    tags = entry.get("tags", [])
    expected_answer = entry.get("expected_answer", entry.get("numeric_answer"))
    accepted_deviation = entry.get("accepted_deviation", entry.get("deviation", 0))
    solution_file = entry.get("solution_file", entry.get("solution_path", ""))

    if not isinstance(question, str) or not question.strip():
        raise QuizFormatError(f"Question {position} is missing a valid 'question' field.")

    normalized_explanation = ""
    if explanation is not None:
        if not isinstance(explanation, str):
            raise QuizFormatError(f"Question {position} explanation must be text if provided.")
        normalized_explanation = explanation.strip()

    normalized_tags: list[str] = []
    if tags is not None:
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise QuizFormatError(f"Question {position} tags must be a list of strings.")
        normalized_tags = [tag.strip() for tag in tags if tag.strip()]

    normalized_solution_file = ""
    if solution_file is not None:
        if not isinstance(solution_file, str):
            raise QuizFormatError(f"Question {position} solution file must be text if provided.")
        normalized_solution_file = solution_file.strip()

    if question_type == QUESTION_TYPE_NUMERIC:
        parsed_expected_answer = _parse_expected_answer(expected_answer)
        if parsed_expected_answer is None:
            raise QuizFormatError(
                f"Question {position} must include a valid numeric 'expected_answer'."
            )
        if not isinstance(accepted_deviation, int):
            if isinstance(accepted_deviation, str) and accepted_deviation.strip().lstrip("-").isdigit():
                accepted_deviation = int(accepted_deviation.strip())
            else:
                raise QuizFormatError(
                    f"Question {position} accepted deviation must be an integer."
                )
        if int(accepted_deviation) < 0:
            raise QuizFormatError(
                f"Question {position} accepted deviation cannot be negative."
            )
        normalized_answer_text = (
            answer_text.strip()
            if isinstance(answer_text, str) and answer_text.strip()
            else _format_expected_answer(parsed_expected_answer)
        )
        return QuizQuestion(
            question=question.strip(),
            choices=[],
            answer_index=-1,
            answer_text=normalized_answer_text,
            explanation=normalized_explanation,
            tags=normalized_tags,
            question_type=QUESTION_TYPE_NUMERIC,
            expected_answer=parsed_expected_answer,
            accepted_deviation=int(accepted_deviation),
            solution_file=normalized_solution_file,
        )

    if not isinstance(choices, list) or len(choices) < 2:
        raise QuizFormatError(f"Question {position} must include at least two choices.")

    normalized_choices: list[str] = []
    for choice_index, choice in enumerate(choices, start=1):
        if not isinstance(choice, str) or not choice.strip():
            raise QuizFormatError(
                f"Question {position} choice {choice_index} must be a non-empty string."
            )
        normalized_choices.append(choice.strip())

    resolved_answer_index: int | None = None
    if isinstance(answer_index, int):
        resolved_answer_index = answer_index
    elif isinstance(answer_index, str):
        stripped_answer = answer_index.strip()
        if stripped_answer.isdigit():
            resolved_answer_index = int(stripped_answer)
        elif stripped_answer in normalized_choices:
            resolved_answer_index = normalized_choices.index(stripped_answer)

    if resolved_answer_index is None:
        if isinstance(answer_text, str) and answer_text.strip() in normalized_choices:
            resolved_answer_index = normalized_choices.index(answer_text.strip())
        else:
            raise QuizFormatError(
                f"Question {position} must include an 'answer_index' or matching 'answer_text'."
            )

    if resolved_answer_index < 0 or resolved_answer_index >= len(normalized_choices):
        raise QuizFormatError(f"Question {position} answer index is out of range.")

    normalized_answer_text = (
        answer_text.strip()
        if isinstance(answer_text, str) and answer_text.strip()
        else normalized_choices[resolved_answer_index]
    )

    return QuizQuestion(
        question=question.strip(),
        choices=normalized_choices,
        answer_index=resolved_answer_index,
        answer_text=normalized_answer_text,
        explanation=normalized_explanation,
        tags=normalized_tags,
        question_type=QUESTION_TYPE_MULTIPLE_CHOICE,
        solution_file=normalized_solution_file,
    )


def _normalize_chapter_payload(entry: Any, position: int) -> QuizChapter:
    if not isinstance(entry, dict):
        raise QuizFormatError(f"Chapter {position} must be an object.")

    title = entry.get("title") or entry.get("chapter")
    if not isinstance(title, str) or not title.strip():
        raise QuizFormatError(f"Chapter {position} is missing a valid 'title' field.")

    questions = entry.get("questions", [])
    if not isinstance(questions, list):
        raise QuizFormatError(f"Chapter {position} questions must be a list.")

    return QuizChapter(
        title=title.strip(),
        questions=[
            _normalize_question_payload(question_entry, question_position + 1)
            for question_position, question_entry in enumerate(questions)
        ],
    )


def _parse_payload(payload: Any) -> tuple[str | None, str, list[QuizChapter]]:
    if isinstance(payload, dict):
        if "questions" in payload and any(key in payload for key in ("title", "chapter", "name")):
            single_chapter = _normalize_chapter_payload(payload, 1)
            return None, "", [single_chapter]

        subject = payload.get("subject")
        selected_chapter = payload.get("selected_chapter", "")
        chapters_payload = payload.get("chapters", [])

        if not isinstance(chapters_payload, list):
            raise QuizFormatError("Top-level 'chapters' must be a list.")

        chapters = [
            _normalize_chapter_payload(entry, index + 1)
            for index, entry in enumerate(chapters_payload)
        ]
        return (
            subject if isinstance(subject, str) and subject.strip() else None,
            selected_chapter if isinstance(selected_chapter, str) else "",
            chapters,
        )

    if isinstance(payload, list):
        if payload and all(isinstance(entry, dict) and "questions" in entry for entry in payload):
            chapters = [
                _normalize_chapter_payload(entry, index + 1)
                for index, entry in enumerate(payload)
            ]
            return None, "", chapters

        if payload and all(isinstance(entry, dict) and "chapter" in entry for entry in payload):
            chapters_by_title: dict[str, QuizChapter] = {}
            for index, entry in enumerate(payload):
                question = _normalize_question_payload(entry, index + 1)
                chapter_title = str(entry.get("chapter", "Imported")).strip() or "Imported"
                chapters_by_title.setdefault(chapter_title, QuizChapter(title=chapter_title))
                chapters_by_title[chapter_title].questions.append(question)
            return None, "", list(chapters_by_title.values())

        raise QuizFormatError(
            "Array imports must contain chapters or question objects with a 'chapter' field."
        )

    raise QuizFormatError("Top-level JSON value must be an object or array.")


def load_quiz_bank_from_path(path: str | Path) -> QuizBank:
    quiz_path = Path(path)
    with quiz_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    _, selected_chapter, chapters = _parse_payload(payload)
    return QuizBank(quiz_type="imported", selected_chapter=selected_chapter, chapters=chapters)


def load_question_list_from_path(path: str | Path) -> list[QuizQuestion]:
    quiz_path = Path(path)
    with quiz_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise QuizFormatError(
            "Quiz-tab import expects a JSON array of question objects. "
            "Use the menu-bar import for full backups like AELE.json."
        )

    if not payload:
        raise QuizFormatError("The question file is empty.")

    return [
        _normalize_question_payload(entry, index + 1)
        for index, entry in enumerate(payload)
    ]


class QuestionEditorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, question: QuizQuestion | None = None):
        super().__init__(parent)
        self.setWindowTitle("Question")
        self.setMinimumWidth(620)
        self.solution_file = question.solution_file if question is not None else ""
        self._build_ui(question)

    def _build_ui(self, question: QuizQuestion | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_combo = QComboBox(self)
        self.type_combo.addItem("Multiple Choice", QUESTION_TYPE_MULTIPLE_CHOICE)
        self.type_combo.addItem("Numeric Field", QUESTION_TYPE_NUMERIC)

        self.question_edit = QLineEdit(self)
        self.question_edit.setPlaceholderText("Enter the question text")

        self.choices_edit = QPlainTextEdit(self)
        self.choices_edit.setPlaceholderText("One choice per line")

        self.answer_edit = QLineEdit(self)
        self.answer_edit.setPlaceholderText("Choice text or zero-based index")

        self.expected_answer_edit = QLineEdit(self)
        self.expected_answer_edit.setPlaceholderText("Enter the expected numeric answer")

        self.accepted_deviation_spinbox = QSpinBox(self)
        self.accepted_deviation_spinbox.setMinimum(0)
        self.accepted_deviation_spinbox.setMaximum(999999)
        self.accepted_deviation_spinbox.setPrefix("+/- ")

        self.explanation_edit = QPlainTextEdit(self)
        self.explanation_edit.setPlaceholderText("Optional explanation")

        self.tags_edit = QLineEdit(self)
        self.tags_edit.setPlaceholderText("Comma-separated tags")

        solution_row = QWidget(self)
        solution_layout = QHBoxLayout(solution_row)
        solution_layout.setContentsMargins(0, 0, 0, 0)
        solution_layout.setSpacing(6)
        self.solution_file_edit = QLineEdit(solution_row)
        self.solution_file_edit.setReadOnly(True)
        self.solution_file_edit.setPlaceholderText("Optional solution file")
        self.solution_browse_button = QPushButton("Browse", solution_row)
        self.solution_clear_button = QPushButton("Clear", solution_row)
        solution_layout.addWidget(self.solution_file_edit, 1)
        solution_layout.addWidget(self.solution_browse_button)
        solution_layout.addWidget(self.solution_clear_button)

        form.addRow("Type", self.type_combo)
        form.addRow("Question", self.question_edit)
        form.addRow("Choices", self.choices_edit)
        form.addRow("Answer", self.answer_edit)
        form.addRow("Expected Answer", self.expected_answer_edit)
        form.addRow("Accepted Deviation", self.accepted_deviation_spinbox)
        form.addRow("Explanation", self.explanation_edit)
        form.addRow("Tags", self.tags_edit)
        form.addRow("Solution File", solution_row)
        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.type_combo.currentIndexChanged.connect(self._update_question_type_ui)
        self.solution_browse_button.clicked.connect(self._choose_solution_file)
        self.solution_clear_button.clicked.connect(self._clear_solution_file)

        if question is not None:
            self.question_edit.setText(question.question)
            question_type_index = self.type_combo.findData(
                _normalize_question_type(question.question_type)
            )
            if question_type_index >= 0:
                self.type_combo.setCurrentIndex(question_type_index)
            self.choices_edit.setPlainText("\n".join(question.choices))
            if question.question_type == QUESTION_TYPE_NUMERIC:
                self.expected_answer_edit.setText(_format_expected_answer(question.expected_answer))
                self.accepted_deviation_spinbox.setValue(max(0, question.accepted_deviation))
            else:
                self.answer_edit.setText(str(question.answer_index))
            self.explanation_edit.setPlainText(question.explanation)
            self.tags_edit.setText(", ".join(question.tags))
            self.solution_file_edit.setText(self.solution_file)
        else:
            self.type_combo.setCurrentIndex(0)

        self._update_question_type_ui()

    def _current_question_type(self) -> str:
        return _normalize_question_type(self.type_combo.currentData())

    def _update_question_type_ui(self):
        is_numeric = self._current_question_type() == QUESTION_TYPE_NUMERIC
        self.choices_edit.setVisible(not is_numeric)
        self.answer_edit.setVisible(not is_numeric)
        self.expected_answer_edit.setVisible(is_numeric)
        self.accepted_deviation_spinbox.setVisible(is_numeric)
        self.setLabelForFieldVisibility(is_numeric)

    def setLabelForFieldVisibility(self, is_numeric: bool):
        form_layout = self.layout().itemAt(0).layout()
        if not isinstance(form_layout, QFormLayout):
            return
        for row in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if label_item is None or field_item is None:
                continue
            label_widget = label_item.widget()
            field_widget = field_item.widget()
            if field_widget in {self.choices_edit, self.answer_edit}:
                if label_widget is not None:
                    label_widget.setVisible(not is_numeric)
            elif field_widget in {self.expected_answer_edit, self.accepted_deviation_spinbox}:
                if label_widget is not None:
                    label_widget.setVisible(is_numeric)

    def _choose_solution_file(self):
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Choose Solution File",
            "",
            "All Supported Files (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.txt *.md *.json);;All Files (*)",
        )
        if not file_path:
            return
        self.solution_file = file_path
        self.solution_file_edit.setText(file_path)

    def _clear_solution_file(self):
        self.solution_file = ""
        self.solution_file_edit.clear()

    def to_question(self) -> QuizQuestion:
        question_text = self.question_edit.text().strip()
        if not question_text:
            raise QuizFormatError("Please enter a question.")

        question_type = self._current_question_type()
        explanation = self.explanation_edit.toPlainText().strip()
        tags = [tag.strip() for tag in self.tags_edit.text().split(",") if tag.strip()]

        if question_type == QUESTION_TYPE_NUMERIC:
            expected_answer = _parse_expected_answer(self.expected_answer_edit.text())
            if expected_answer is None:
                raise QuizFormatError("Please enter a valid numeric expected answer.")
            accepted_deviation = self.accepted_deviation_spinbox.value()
            return QuizQuestion(
                question=question_text,
                choices=[],
                answer_index=-1,
                answer_text=_format_expected_answer(expected_answer),
                explanation=explanation,
                tags=tags,
                question_type=QUESTION_TYPE_NUMERIC,
                expected_answer=expected_answer,
                accepted_deviation=accepted_deviation,
                solution_file=self.solution_file_edit.text().strip(),
            )

        choices = [
            choice.strip()
            for choice in self.choices_edit.toPlainText().splitlines()
            if choice.strip()
        ]
        if len(choices) < 2:
            raise QuizFormatError("Please enter at least two choices, one per line.")

        answer_raw = self.answer_edit.text().strip()
        answer_index: int | None = None
        if answer_raw in choices:
            answer_index = choices.index(answer_raw)
        elif answer_raw.isdigit():
            answer_index = int(answer_raw)

        if answer_index is None or answer_index < 0 or answer_index >= len(choices):
            raise QuizFormatError(
                "Answer must be a valid zero-based choice index or exactly match one choice."
            )

        return QuizQuestion(
            question=question_text,
            choices=choices,
            answer_index=answer_index,
            answer_text=choices[answer_index],
            explanation=explanation,
            tags=tags,
            question_type=QUESTION_TYPE_MULTIPLE_CHOICE,
            solution_file=self.solution_file_edit.text().strip(),
        )


class LongQuizSetupDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        chapters: list[QuizChapter],
        selected_titles: list[str],
        requested_count: int,
    ):
        super().__init__(parent)
        self.setWindowTitle("Configure Long Quiz")
        self.setMinimumWidth(460)
        self._chapters = chapters
        self._preferred_count = max(0, requested_count)
        self._build_ui(selected_titles)

    def _build_ui(self, selected_titles: list[str]):
        layout = QVBoxLayout(self)

        intro_label = QLabel(
            "Choose the chapters to include, then set how many shuffled questions to generate.",
            self,
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        self.chapter_list = QTreeWidget(self)
        self.chapter_list.setHeaderHidden(True)
        self.chapter_list.setRootIsDecorated(True)
        self.chapter_list.setIndentation(16)
        self.chapter_list.setUniformRowHeights(True)
        selected_keys = {title.lower() for title in selected_titles}
        roots: dict[str, QTreeWidgetItem] = {}
        for chapter in self._chapters:
            chapter_title, subchapter_title = split_leaf_path(chapter.title)
            parent_item = roots.get(chapter_title.lower())
            if parent_item is None:
                aggregate_count = self._question_total_for_selection([chapter_title])
                parent_item = QTreeWidgetItem(
                    [
                        f"{chapter_title} ({aggregate_count} question{'s' if aggregate_count != 1 else ''})"
                    ]
                )
                parent_item.setData(0, Qt.ItemDataRole.UserRole, chapter_title)
                parent_item.setFlags(parent_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                parent_item.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if chapter_title.lower() in selected_keys
                    else Qt.CheckState.Unchecked,
                )
                roots[chapter_title.lower()] = parent_item
                self.chapter_list.addTopLevelItem(parent_item)
            if subchapter_title is None:
                continue
            item = QTreeWidgetItem(
                [f"{subchapter_title} ({len(chapter.questions)} question{'s' if len(chapter.questions) != 1 else ''})"]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, chapter.title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0,
                Qt.CheckState.Checked
                if chapter.title.lower() in selected_keys
                else Qt.CheckState.Unchecked,
            )
            parent_item.addChild(item)
            parent_item.setExpanded(True)
        self.chapter_list.itemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.chapter_list)

        form = QFormLayout()
        self.available_label = QLabel(self)
        self.question_count_spinbox = QSpinBox(self)
        self.question_count_spinbox.setMinimum(0)
        self.question_count_spinbox.valueChanged.connect(self._on_count_changed)
        form.addRow("Available questions", self.available_label)
        form.addRow("Generate count", self.question_count_spinbox)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._refresh_state()

    def selected_chapter_titles(self) -> list[str]:
        titles: list[str] = []
        for index in range(self.chapter_list.topLevelItemCount()):
            item = self.chapter_list.topLevelItem(index)
            title = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(title, str) and item.checkState(0) == Qt.CheckState.Checked:
                titles.append(title)
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                title = child.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(title, str) and child.checkState(0) == Qt.CheckState.Checked:
                    titles.append(title)
        return titles

    def selection(self) -> tuple[list[str], int]:
        return self.selected_chapter_titles(), self.question_count_spinbox.value()

    def _selected_question_total(self) -> int:
        return self._question_total_for_selection(self.selected_chapter_titles())

    def _question_total_for_selection(self, selected_titles: list[str]) -> int:
        selected_keys = {title.lower() for title in selected_titles}
        expanded_keys: set[str] = set()
        for chapter in self._chapters:
            chapter_title, _subchapter_title = split_leaf_path(chapter.title)
            if chapter.title.lower() in selected_keys or chapter_title.lower() in selected_keys:
                expanded_keys.add(chapter.title.lower())

        total = 0
        for chapter in self._chapters:
            if chapter.title.lower() in expanded_keys:
                total += len(chapter.questions)
        return total

    def _refresh_state(self):
        selected_titles = self.selected_chapter_titles()
        available_questions = self._selected_question_total()
        selected_count = len(selected_titles)
        self.available_label.setText(
            f"{available_questions} from {selected_count} selected chapter"
            f"{'s' if selected_count != 1 else ''}"
        )

        if available_questions <= 0:
            next_value = 0
        elif self.question_count_spinbox.value() > 0:
            next_value = min(self.question_count_spinbox.value(), available_questions)
        else:
            next_value = min(self._preferred_count or available_questions, available_questions)

        self.question_count_spinbox.blockSignals(True)
        self.question_count_spinbox.setMaximum(max(0, available_questions))
        self.question_count_spinbox.setValue(next_value)
        self.question_count_spinbox.blockSignals(False)

        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(selected_titles) and available_questions > 0 and next_value > 0)

    def _on_selection_changed(self, _item):
        self._refresh_state()

    def _on_count_changed(self, value: int):
        if value > 0:
            self._preferred_count = value
        self._refresh_state()


class PieChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._segments: list[tuple[str, int, QColor]] = []
        self.setMinimumHeight(240)

    def set_segments(self, segments: list[tuple[str, int, QColor]]):
        self._segments = [(label, max(0, value), color) for label, value, color in segments]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#0f1728"))

        total = sum(value for _label, value, _color in self._segments)
        if total <= 0:
            painter.setPen(QColor("#9fb2cc"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No flashcard results yet.")
            return

        margin = 18
        diameter = min(self.width() - (margin * 2), self.height() - 96)
        diameter = max(120, diameter)
        pie_rect = QRectF(
            margin,
            margin,
            diameter,
            diameter,
        )

        start_angle = 90 * 16
        for _label, value, color in self._segments:
            if value <= 0:
                continue
            span_angle = -round((value / total) * 360 * 16)
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#0f1728"), 2))
            painter.drawPie(pie_rect, start_angle, span_angle)
            start_angle += span_angle

        legend_x = int(pie_rect.right()) + 20
        legend_y = margin + 4
        painter.setPen(QColor("#edf4ff"))
        for label, value, color in self._segments:
            painter.fillRect(legend_x, legend_y, 14, 14, color)
            painter.drawText(
                legend_x + 24,
                legend_y + 12,
                f"{label}: {value}",
            )
            legend_y += 24

class QuestionCardWidget(QFrame):
    def __init__(
        self,
        chapter_title: str,
        question_number: int,
        question: QuizQuestion,
        *,
        reveal_answers: bool = True,
        flashcard_mode: bool = False,
    ):
        super().__init__()
        self.question = question
        self.question_number = question_number
        self.chapter_title = chapter_title
        self.selected_choice = -1
        self.numeric_answer_input: QLineEdit | None = None
        self.numeric_answer_checked = False
        self.reveal_answers = reveal_answers
        self.flashcard_mode = flashcard_mode
        self.choice_group: QButtonGroup | None = None

        self.setObjectName("quizQuestionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setProperty("cardState", "idle")
        self.setStyleSheet(
            """
            QFrame#quizQuestionCard {
                background-color: #101a2e;
                border: 1px solid #23314a;
                border-radius: 10px;
            }
            """
        )
        if self.flashcard_mode:
            self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.setMinimumHeight(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        chapter_label = QLabel(f"{chapter_title}  |  Question {question_number}", self)
        chapter_label.setWordWrap(True)
        chapter_label.setStyleSheet("color: #ffffff;")

        question_label = QLabel(question.question, self)
        question_label.setWordWrap(True)
        question_label.setStyleSheet("color: #ffffff;")
        apply_font_to_widget(question_label, TreeFontConfig.QUESTION_TEXT_SIZE)

        if self.flashcard_mode:
            layout.addStretch(1)
            chapter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chapter_label.setStyleSheet("color: #9fb2cc; font-size: 11pt; font-weight: 600;")
            question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            question_label.setStyleSheet("color: #ffffff; font-size: 18pt; font-weight: 700;")

        layout.addWidget(chapter_label)
        layout.addWidget(question_label)

        if self.flashcard_mode:
            self._build_flashcard_ui(layout)
        elif self.question.question_type == QUESTION_TYPE_NUMERIC:
            self._build_numeric_ui(layout)
        else:
            self._build_multiple_choice_ui(layout)

        self.feedback_label = QLabel(self._default_feedback_text(), self)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet("color: #7e8ca8;")
        if self.flashcard_mode:
            self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.feedback_label)

        if self.question.solution_file:
            self.solution_button = QPushButton("Open Solution", self)
            self.solution_button.clicked.connect(self._open_solution_file)
            if self.flashcard_mode:
                self.solution_button.setMaximumWidth(220)
            layout.addWidget(self.solution_button)
        else:
            self.solution_button = None
        layout.addStretch(1)

    def _build_flashcard_ui(self, layout: QVBoxLayout):
        self.reveal_card_button = QPushButton("Reveal Answer", self)
        self.reveal_card_button.setMaximumWidth(240)
        self.reveal_card_button.setStyleSheet(
            """
            QPushButton {
                background-color: #173158;
                color: #ffffff;
                border: 1px solid #2f74ff;
                border-radius: 12px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1f4275;
            }
            """
        )
        self.reveal_card_button.clicked.connect(self._toggle_flashcard_answer)
        layout.addWidget(self.reveal_card_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.flashcard_answer_label = QLabel("", self)
        self.flashcard_answer_label.setWordWrap(True)
        self.flashcard_answer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flashcard_answer_label.setStyleSheet(
            """
            color: #f8fbff;
            background-color: #173158;
            border: 1px solid #2f74ff;
            border-radius: 14px;
            padding: 18px;
            font-size: 15pt;
            """
        )
        self.flashcard_answer_label.hide()
        layout.addWidget(self.flashcard_answer_label)

        self.flashcard_explanation_label = QLabel("", self)
        self.flashcard_explanation_label.setWordWrap(True)
        self.flashcard_explanation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flashcard_explanation_label.setStyleSheet(
            "color: #c5d2e6; font-size: 11pt;"
        )
        self.flashcard_explanation_label.hide()
        layout.addWidget(self.flashcard_explanation_label)

    def _build_multiple_choice_ui(self, layout: QVBoxLayout):
        self.choice_group = QButtonGroup(self)
        self.choice_group.setExclusive(True)
        self.choice_group.buttonToggled.connect(self._on_choice_toggled)

        for index, choice in enumerate(self.question.choices):
            button = QRadioButton(choice, self)
            button.setProperty("choiceIndex", index)
            button.setStyleSheet("color: #ffffff;")
            apply_font_to_widget(button, TreeFontConfig.CHOICE_TEXT_SIZE)
            self.choice_group.addButton(button, index)
            layout.addWidget(button)

    def _build_numeric_ui(self, layout: QVBoxLayout):
        numeric_row = QWidget(self)
        numeric_layout = QHBoxLayout(numeric_row)
        numeric_layout.setContentsMargins(0, 0, 0, 0)
        numeric_layout.setSpacing(8)

        self.numeric_answer_input = QLineEdit(numeric_row)
        self.numeric_answer_input.setPlaceholderText("Enter an integer answer")
        self.numeric_answer_input.setValidator(QIntValidator(-1_000_000_000, 1_000_000_000, self))
        self.numeric_answer_input.textChanged.connect(self._on_numeric_answer_changed)
        numeric_layout.addWidget(self.numeric_answer_input, 1)

        if self.reveal_answers:
            self.numeric_check_button = QPushButton("Check", numeric_row)
            self.numeric_check_button.clicked.connect(self._check_numeric_answer)
            numeric_layout.addWidget(self.numeric_check_button)
        else:
            self.numeric_check_button = None

        layout.addWidget(numeric_row)

    def _default_feedback_text(self) -> str:
        if self.flashcard_mode:
            return "Reveal the card to study the answer."
        if self.question.question_type == QUESTION_TYPE_NUMERIC:
            if self.reveal_answers:
                return "Enter an integer answer, then click Check."
            return "Enter an integer answer, then submit for a score."
        if not self.reveal_answers:
            return "Answer first, then submit for a score."
        return "Select an answer"

    def _on_choice_toggled(self, button: QRadioButton, checked: bool):
        if not checked:
            return

        choice_index = self.choice_group.id(button)
        self.selected_choice = choice_index

        if not self.reveal_answers:
            return

        if choice_index == self.question.answer_index:
            self.setProperty("cardState", "correct")
            self.feedback_label.setText(self._build_feedback_text(True))
            self.feedback_label.setStyleSheet("color: #8de2b1;")
        else:
            self.setProperty("cardState", "incorrect")
            self.feedback_label.setText(self._build_feedback_text(False))
            self.feedback_label.setStyleSheet("color: #ff9b9b;")

    def _on_numeric_answer_changed(self, _text: str):
        self.numeric_answer_checked = False
        if not self.reveal_answers:
            return
        self.setProperty("cardState", "idle")
        self.feedback_label.setText(self._default_feedback_text())
        self.feedback_label.setStyleSheet("color: #7e8ca8;")

    def _check_numeric_answer(self):
        user_answer = self.user_answer_text()
        self.numeric_answer_checked = True
        if _numeric_answer_matches(self.question, user_answer):
            self.setProperty("cardState", "correct")
            self.feedback_label.setText(self._build_feedback_text(True))
            self.feedback_label.setStyleSheet("color: #8de2b1;")
        else:
            self.setProperty("cardState", "incorrect")
            self.feedback_label.setText(self._build_feedback_text(False, unanswered=user_answer is None))
            self.feedback_label.setStyleSheet("color: #ff9b9b;")

    def _toggle_flashcard_answer(self):
        showing_answer = self.flashcard_answer_label.isVisible()
        if showing_answer:
            self.flashcard_answer_label.hide()
            self.flashcard_explanation_label.hide()
            self.reveal_card_button.setText("Reveal Answer")
            self.feedback_label.setText(self._default_feedback_text())
            self.feedback_label.setStyleSheet("color: #7e8ca8;")
            return

        self.flashcard_answer_label.setText(f"Answer: {self.question.answer_text}")
        self.flashcard_answer_label.show()
        if self.question.explanation:
            self.flashcard_explanation_label.setText(f"Explanation: {self.question.explanation}")
            self.flashcard_explanation_label.show()
        else:
            self.flashcard_explanation_label.hide()
        self.reveal_card_button.setText("Hide Answer")
        self.feedback_label.setText("Use this card for recall practice.")
        self.feedback_label.setStyleSheet("color: #8de2b1;")

    def user_answer_text(self) -> str | None:
        if self.question.question_type == QUESTION_TYPE_NUMERIC:
            if self.numeric_answer_input is None:
                return None
            return _normalized_numeric_user_answer(self.numeric_answer_input.text())
        if self.selected_choice < 0 or self.selected_choice >= len(self.question.choices):
            return None
        return self.question.choices[self.selected_choice]

    def has_response(self) -> bool:
        if self.flashcard_mode:
            return False
        if self.question.question_type == QUESTION_TYPE_NUMERIC:
            return self.user_answer_text() is not None
        return self.selected_choice >= 0

    def is_correct_response(self) -> bool:
        if self.flashcard_mode:
            return False
        if self.question.question_type == QUESTION_TYPE_NUMERIC:
            return _numeric_answer_matches(self.question, self.user_answer_text())
        return self.selected_choice == self.question.answer_index

    def _build_feedback_text(self, correct: bool, *, unanswered: bool = False) -> str:
        if correct:
            base_text = f"Correct: {self.question.answer_text}"
        elif self.question.question_type == QUESTION_TYPE_NUMERIC:
            base_text = (
                f"{'Not answered' if unanswered else 'Incorrect'}. "
                f"Accepted answer: {self.question.answer_text} (+/- {max(0, self.question.accepted_deviation)})"
            )
        else:
            base_text = (
                f"{'Not answered' if unanswered else 'Incorrect'}. "
                f"Correct answer: {self.question.answer_text}"
            )
        if self.question.explanation:
            return f"{base_text}\n\nExplanation: {self.question.explanation}"
        return base_text

    def reveal_review(self, correct: bool):
        if self.choice_group is not None:
            for button in self.choice_group.buttons():
                button.setEnabled(False)
        if self.numeric_answer_input is not None:
            self.numeric_answer_input.setEnabled(False)
        if getattr(self, "numeric_check_button", None) is not None:
            self.numeric_check_button.setEnabled(False)
        if self.flashcard_mode:
            return

        if correct:
            self.setProperty("cardState", "correct")
            self.feedback_label.setText(self._build_feedback_text(True))
            self.feedback_label.setStyleSheet("color: #8de2b1;")
        else:
            self.setProperty("cardState", "incorrect")
            self.feedback_label.setText(
                self._build_feedback_text(False, unanswered=not self.has_response())
            )
            self.feedback_label.setStyleSheet("color: #ff9b9b;")

    def _open_solution_file(self):
        solution_path = self.question.solution_file.strip()
        if not solution_path:
            QMessageBox.information(self, "No Solution", "This question has no uploaded solution file.")
            return

        path = Path(solution_path)
        if not path.exists():
            QMessageBox.warning(self, "Missing Solution", f"Could not find solution file:\n{solution_path}")
            return

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve()))):
            QMessageBox.warning(self, "Open Failed", f"Could not open solution file:\n{solution_path}")


class ChapterQuizTabController(QObject):
    def __init__(
        self,
        page: QWidget,
        *,
        prefix: str,
        title: str,
        show_branch_viewer: bool = True,
    ):
        super().__init__(page)
        self.page = page
        self.prefix = prefix
        self.title = title
        self.show_branch_viewer = show_branch_viewer
        self.subject_name: str | None = None
        self.shared_chapter_titles: list[str] = []
        self.bank = QuizBank(quiz_type=prefix)
        self.storage_root = Path(__file__).resolve().parents[1] / "quiz_banks"
        self.storage_path: Path | None = None
        self.answer_cards: list[QuestionCardWidget] = []
        self.subject_resolver: Callable[[], str | None] | None = None
        self.review_submitted = False
        self.long_quiz_selected_chapters: list[str] = []
        self.long_quiz_requested_count = 0
        self.long_quiz_generated_refs: list[LongQuizQuestionRef] = []
        self.quiz_start_time: datetime | None = None
        self.assessment_tab_controller: Any = None
        self.sister_controller: Any = None  # Reference to the other quiz type (short <-> long)
        self.flashcard_mode_enabled = False
        self.flashcard_session_chapter: str | None = None
        self.flashcard_queue_keys: list[str] = []
        self.flashcard_mastered_keys: set[str] = set()
        self.flashcard_review_needed_keys: set[str] = set()
        self.flashcard_last_review_needed_keys: set[str] = set()
        self.flashcard_total_cards = 0
        self.flashcard_review_only_mode = False
        self.flashcard_assessment_ready = False
        self.flashcard_mastered_shortcut: QShortcut | None = None
        self.flashcard_review_shortcut: QShortcut | None = None

        self._build_ui()
        self._wire_signals()
        self._refresh_ui()

    def set_storage_root(self, storage_root: str | Path):
        new_root = Path(storage_root)
        new_root.mkdir(parents=True, exist_ok=True)
        if new_root == self.storage_root:
            return

        self._flush_storage_save()
        self.storage_root = new_root
        if self.subject_name is None:
            self.storage_path = None
            return

        self.storage_path = self.storage_root / slugify(self.subject_name) / f"{self.prefix}.json"
        self._load_from_storage()

    def _widget(self, name: str, cls):
        widget = self.page.findChild(cls, name)
        if widget is None:
            raise RuntimeError(f"Missing required widget: {name}")
        return widget

    def _optional_widget(self, name: str, cls):
        return self.page.findChild(cls, name)

    def _build_ui(self):
        self.title_label = self._widget(f"{self.prefix}_title_label", QLabel)
        self.status_label = self._widget(f"{self.prefix}_status_label", QLabel)
        self.add_chapter_button = self._widget(f"{self.prefix}_add_chapter_button", QPushButton)
        self.import_button = self._widget(f"{self.prefix}_import_button", QPushButton)
        self.export_button = self._widget(f"{self.prefix}_export_button", QPushButton)
        original_chapter_list = self._widget(f"{self.prefix}_chapter_list", QListWidget)
        self.chapter_header_label = self._widget(f"{self.prefix}_chapter_header_label", QLabel)
        self.question_header_label = self._widget(f"{self.prefix}_question_header_label", QLabel)
        self.question_status_label = self._widget(f"{self.prefix}_question_status_label", QLabel)
        self.add_question_button = self._widget(f"{self.prefix}_add_question_button", QPushButton)
        self.edit_question_button = self._widget(f"{self.prefix}_edit_question_button", QPushButton)
        self.delete_question_button = self._widget(f"{self.prefix}_delete_question_button", QPushButton)
        self.question_list = self._widget(f"{self.prefix}_question_list", QListWidget)
        self.answer_header_label = self._widget(f"{self.prefix}_answer_header_label", QLabel)
        self.answer_scroll = self._widget(f"{self.prefix}_answer_scroll", QScrollArea)
        self.answer_container = self._widget(f"{self.prefix}_answer_container", QWidget)
        self.answer_cards_layout = self._widget(
            f"verticalLayout_{self.prefix}_answer_cards", QVBoxLayout
        )
        self.submit_button = self._optional_widget(f"{self.prefix}_submit_button", QPushButton)
        self.score_label = self._optional_widget(f"{self.prefix}_score_label", QLabel)

        chapter_parent = original_chapter_list.parentWidget()
        chapter_layout = chapter_parent.layout() if chapter_parent is not None else None
        self.chapter_list = QTreeWidget(chapter_parent)
        self.chapter_list.setObjectName(f"{self.prefix}_chapter_tree")
        self.chapter_list.setHeaderHidden(True)
        self.chapter_list.setRootIsDecorated(True)
        self.chapter_list.setIndentation(16)
        self.chapter_list.setUniformRowHeights(True)
        self.chapter_list.setAlternatingRowColors(True)
        if chapter_layout is not None:
            insert_index = chapter_layout.indexOf(original_chapter_list)
            chapter_layout.insertWidget(insert_index, self.chapter_list)
            chapter_layout.removeWidget(original_chapter_list)
        original_chapter_list.deleteLater()

        self.answer_scroll.setWidgetResizable(True)
        self.chapter_list.setAlternatingRowColors(True)
        self.question_list.setAlternatingRowColors(True)
        self.add_chapter_button.hide()
        self._apply_header_theme()

        answer_panel_layout = self.answer_header_label.parentWidget().layout()
        answer_panel_layout.removeWidget(self.answer_header_label)

        self.answer_header_toolbar = QWidget(self.answer_header_label.parentWidget())
        header_toolbar_layout = QHBoxLayout(self.answer_header_toolbar)
        header_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        header_toolbar_layout.setSpacing(8)
        header_toolbar_layout.addWidget(self.answer_header_label, 1)

        self.branch_toggle_button: QToolButton | None = None
        self.flashcard_toggle_button: QToolButton | None = None
        self.branch_viewer: QWidget | None = None
        self.branch_tree: QTreeWidget | None = None
        if self.prefix == "short_quiz":
            self.flashcard_toggle_button = QToolButton(self.answer_header_toolbar)
            self.flashcard_toggle_button.setText("Flashcards")
            self.flashcard_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            self.flashcard_toggle_button.setCheckable(True)
            self.flashcard_toggle_button.setChecked(self.flashcard_mode_enabled)
            self.flashcard_toggle_button.setStyleSheet(
                """
                QToolButton {
                    background-color: #132136;
                    color: #edf4ff;
                    border: 1px solid #23314a;
                    border-radius: 10px;
                    padding: 6px 12px;
                    font-weight: 600;
                }
                QToolButton:hover {
                    background-color: #173158;
                    border-color: #2f74ff;
                }
                QToolButton:checked {
                    background-color: #173158;
                    border-color: #2f74ff;
                }
                """
            )
            header_toolbar_layout.addWidget(self.flashcard_toggle_button)
            self.flashcard_mastered_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self.page)
            self.flashcard_review_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self.page)
            self.flashcard_mastered_shortcut.activated.connect(
                lambda: self._handle_flashcard_shortcut(mastered=True)
            )
            self.flashcard_review_shortcut.activated.connect(
                lambda: self._handle_flashcard_shortcut(mastered=False)
            )
        if self.show_branch_viewer and not self._is_long_quiz():
            self.branch_toggle_button = QToolButton(self.answer_header_toolbar)
            self.branch_toggle_button.setText("Options")
            self.branch_toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            self.branch_toggle_button.setCheckable(True)
            self.branch_toggle_button.setChecked(True)
            self.branch_toggle_button.setStyleSheet(
                """
                QToolButton {
                    background-color: #132136;
                    color: #edf4ff;
                    border: 1px solid #23314a;
                    border-radius: 10px;
                    padding: 6px 12px;
                    font-weight: 600;
                }
                QToolButton:hover {
                    background-color: #173158;
                    border-color: #2f74ff;
                }
                QToolButton:checked {
                    background-color: #173158;
                    border-color: #2f74ff;
                }
                """
            )
            header_toolbar_layout.addWidget(self.branch_toggle_button)

        answer_panel_layout.insertWidget(0, self.answer_header_toolbar)

        if self.show_branch_viewer and not self._is_long_quiz():
            self.branch_viewer = QWidget(self.answer_header_label.parentWidget())
            self.branch_viewer.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            self.branch_viewer.setStyleSheet(
                """
                QWidget {
                    background-color: #0f1728;
                    border: 1px solid #22314b;
                    border-radius: 12px;
                }
                """
            )
            branch_layout = QVBoxLayout(self.branch_viewer)
            branch_layout.setContentsMargins(8, 8, 8, 8)
            branch_layout.setSpacing(8)

            self.branch_tree = QTreeWidget(self.branch_viewer)
            self.branch_tree.setHeaderHidden(True)
            self.branch_tree.setRootIsDecorated(True)
            self.branch_tree.setIndentation(16)
            self.branch_tree.setUniformRowHeights(True)
            self.branch_tree.setMaximumHeight(180)
            self.branch_tree.setStyleSheet(
                """
                QTreeWidget {
                    background-color: transparent;
                    border: none;
                    color: #edf4ff;
                }
                QTreeWidget::item {
                    padding: 6px 8px;
                    border-radius: 6px;
                }
                QTreeWidget::item:selected {
                    background-color: #173158;
                }
                """
            )
            branch_layout.addWidget(self.branch_tree)
            answer_panel_layout.insertWidget(1, self.branch_viewer)

        self.long_quiz_setup_toolbar: QWidget | None = None
        self.long_quiz_options_button: QPushButton | None = None
        self.long_quiz_generate_button: QPushButton | None = None
        if self._is_long_quiz():
            self._build_long_quiz_setup_ui(answer_panel_layout)

        self._update_branch_toggle()

    def _apply_header_theme(self):
        self.title_label.setStyleSheet("color: #f8fbff; font-size: 16pt; font-weight: 700;")
        self.status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")
        self.chapter_header_label.setStyleSheet("color: #7ab0ff; font-size: 10.5pt; font-weight: 700;")
        self.question_header_label.setStyleSheet("color: #7ab0ff; font-size: 10.5pt; font-weight: 700;")
        self.question_status_label.setStyleSheet("color: #93a8c7; font-size: 10pt; font-weight: 500;")
        self.answer_header_label.setStyleSheet("color: #edf4ff; font-size: 12pt; font-weight: 700;")

    def _build_long_quiz_setup_ui(self, answer_panel_layout):
        review_toolbar = self.submit_button.parentWidget() if self.submit_button is not None else None
        insert_index = answer_panel_layout.indexOf(review_toolbar) if review_toolbar is not None else 1
        if insert_index < 0:
            insert_index = 1

        self.long_quiz_setup_toolbar = QWidget(self.answer_header_label.parentWidget())
        setup_layout = QHBoxLayout(self.long_quiz_setup_toolbar)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(8)

        self.long_quiz_options_button = QPushButton("Quiz Options", self.long_quiz_setup_toolbar)
        self.long_quiz_generate_button = QPushButton("Generate Test", self.long_quiz_setup_toolbar)

        setup_layout.addWidget(self.long_quiz_options_button)
        setup_layout.addStretch(1)
        setup_layout.addWidget(self.long_quiz_generate_button)

        answer_panel_layout.insertWidget(insert_index, self.long_quiz_setup_toolbar)

    def _wire_signals(self):
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_changed)
        self.question_list.currentRowChanged.connect(self._on_question_changed)
        self.add_chapter_button.clicked.connect(self.add_chapter)
        self.import_button.clicked.connect(self.import_chapters)
        self.export_button.clicked.connect(self.export_bank)
        self.add_question_button.clicked.connect(self.add_question)
        self.edit_question_button.clicked.connect(self.edit_question)
        self.delete_question_button.clicked.connect(self.delete_question)
        if self.flashcard_toggle_button is not None:
            self.flashcard_toggle_button.toggled.connect(self._on_flashcard_mode_toggled)
        if self.branch_toggle_button is not None:
            self.branch_toggle_button.toggled.connect(self._on_branch_toggle_toggled)
        if self.branch_tree is not None:
            self.branch_tree.itemSelectionChanged.connect(self._on_branch_tree_selection_changed)
        if self.submit_button is not None:
            self.submit_button.clicked.connect(self.submit_long_quiz)
        if self.long_quiz_options_button is not None:
            self.long_quiz_options_button.clicked.connect(self.open_long_quiz_setup_dialog)
        if self.long_quiz_generate_button is not None:
            self.long_quiz_generate_button.clicked.connect(self.generate_long_quiz)

    def set_subject(self, subject_name: str | None):
        normalized_subject = (
            subject_name.strip() if isinstance(subject_name, str) and subject_name.strip() else None
        )
        if normalized_subject != self.subject_name:
            self.shared_chapter_titles = []

        self.subject_name = normalized_subject
        if self.subject_name is None:
            self.shared_chapter_titles = []
            self.bank = QuizBank(quiz_type=self.prefix)
            self.storage_path = None
            self.review_submitted = False
            self._reset_flashcard_session()
            self._reset_long_quiz_state()
            self._refresh_ui()
            return

        self.storage_path = self.storage_root / slugify(self.subject_name) / f"{self.prefix}.json"
        self._load_from_storage()

    def set_subject_structure(self, subject_name: str | None, chapter_titles: list[str]):
        normalized_subject = (
            subject_name.strip() if isinstance(subject_name, str) and subject_name.strip() else None
        )
        if self.subject_name is None or normalized_subject != self.subject_name:
            self.shared_chapter_titles = []
            self._refresh_branch_tree()
            return

        seen_titles: list[str] = []
        for chapter_title in chapter_titles:
            if not isinstance(chapter_title, str):
                continue
            normalized = chapter_title.strip()
            if not normalized:
                continue
            if any(saved.lower() == normalized.lower() for saved in seen_titles):
                continue
            seen_titles.append(normalized)

        self.shared_chapter_titles = seen_titles
        changed = self._apply_shared_chapter_structure()
        if self._is_long_quiz():
            changed = self._reconcile_long_quiz_state() or changed
        self._refresh_ui()
        if changed:
            self._save_to_storage()

    def set_subject_resolver(self, resolver: Callable[[], str | None] | None):
        self.subject_resolver = resolver

    def _load_from_storage(self):
        self._reset_long_quiz_state()
        if self.storage_path is None or not self.storage_path.exists():
            self.bank = QuizBank(quiz_type=self.prefix, subject=self.subject_name)
            self.review_submitted = False
            changed = self._apply_shared_chapter_structure()
            if self._is_long_quiz():
                changed = self._reconcile_long_quiz_state() or changed
            self._refresh_ui()
            if changed:
                self._save_to_storage()
            return

        try:
            with self.storage_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            _, selected_chapter, chapters = _parse_payload(payload)
            self.bank = QuizBank(
                quiz_type=self.prefix,
                subject=self.subject_name,
                selected_chapter=selected_chapter,
                chapters=chapters,
            )
            if self._is_long_quiz() and isinstance(payload, dict):
                self._load_long_quiz_state(payload.get("long_quiz_state"))
        except (OSError, json.JSONDecodeError, QuizFormatError) as exc:
            QMessageBox.warning(self.page, "Load Failed", str(exc))
            self.bank = QuizBank(quiz_type=self.prefix, subject=self.subject_name)
            self.review_submitted = False

        changed = self._apply_shared_chapter_structure()
        if self._is_long_quiz():
            changed = self._reconcile_long_quiz_state() or changed
        self._refresh_ui()
        if changed:
            self._save_to_storage()

    def _save_to_storage(self):
        if self.storage_path is None:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.bank.to_dict()
        payload["subject"] = self.subject_name
        if self._is_long_quiz():
            payload["long_quiz_state"] = self._long_quiz_state_payload()
        try:
            with self.storage_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()  # Explicitly flush buffer to file
        except OSError as exc:
            QMessageBox.warning(self.page, "Save Failed", str(exc))

    def _flush_storage_save(self):
        """Ensure all quiz data is persisted to disk. Called during app shutdown."""
        if self.storage_path is None:
            return
        # Force save to ensure all changes are written
        self._save_to_storage()
        # Sync the file to disk using fsync
        import os
        try:
            if self.storage_path.exists():
                with self.storage_path.open("r", encoding="utf-8") as f:
                    os.fsync(f.fileno())
        except (OSError, ValueError):
            # File might not support fsync (e.g., temporary files), but that's okay
            pass

    def _selected_chapter(self) -> QuizChapter | None:
        current_item = self.chapter_list.currentItem()
        if current_item is not None:
            leaf_path = current_item.data(0, TREE_LEAF_PATH_ROLE)
            if isinstance(leaf_path, str):
                return next(
                    (chapter for chapter in self.bank.chapters if chapter.title.lower() == leaf_path.lower()),
                    None,
                )
        if self.bank.selected_chapter:
            return next(
                (chapter for chapter in self.bank.chapters if chapter.title.lower() == self.bank.selected_chapter.lower()),
                None,
            )
        return None

    def _selected_question(self) -> QuizQuestion | None:
        chapter = self._selected_chapter()
        if chapter is None:
            return None
        row = self.question_list.currentRow()
        if 0 <= row < len(chapter.questions):
            return chapter.questions[row]
        return None

    def _apply_shared_chapter_structure(self) -> bool:
        if self.subject_name is None:
            return False

        ordered_titles = list(self.shared_chapter_titles)
        existing_by_title = {chapter.title.lower(): chapter for chapter in self.bank.chapters}
        reordered_chapters: list[QuizChapter] = []
        changed = False

        for title in ordered_titles:
            key = title.lower()
            chapter = existing_by_title.pop(key, None)
            if chapter is None:
                chapter = QuizChapter(title=title)
                changed = True
            reordered_chapters.append(chapter)

        # Preserve any remaining chapters that have questions (user data)
        # Only discard empty chapters that are not in the subject structure
        for chapter in existing_by_title.values():
            if chapter.questions:  # Has questions - preserve it
                reordered_chapters.append(chapter)
                changed = True
            else:  # Empty chapter removed from subject structure - discard it
                changed = True

        if [chapter.title for chapter in self.bank.chapters] != [chapter.title for chapter in reordered_chapters]:
            changed = True

        self.bank.chapters = reordered_chapters

        if self.bank.selected_chapter and self._chapter_row_for_title(self.bank.selected_chapter) >= 0:
            return changed

        if self.bank.chapters:
            self.bank.selected_chapter = self.bank.chapters[0].title
            changed = True
        else:
            if self.bank.selected_chapter:
                changed = True
            self.bank.selected_chapter = ""

        return changed

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _is_long_quiz(self) -> bool:
        return self.prefix == "long_quiz"

    def _question_flashcard_key(self, chapter_title: str, question: QuizQuestion) -> str:
        return f"{chapter_title.strip().lower()}::{question.question.strip().lower()}"

    def _reset_flashcard_session(self):
        self.flashcard_session_chapter = None
        self.flashcard_queue_keys = []
        self.flashcard_mastered_keys = set()
        self.flashcard_review_needed_keys = set()
        self.flashcard_total_cards = 0
        self.flashcard_review_only_mode = False
        self.flashcard_assessment_ready = False

    def _flashcard_questions_for_session(
        self,
        chapter: QuizChapter,
        *,
        review_only: bool = False,
    ) -> list[tuple[str, QuizQuestion]]:
        if not review_only:
            return [(self._question_flashcard_key(chapter.title, question), question) for question in chapter.questions]
        return [
            (self._question_flashcard_key(chapter.title, question), question)
            for question in chapter.questions
            if self._question_flashcard_key(chapter.title, question) in self.flashcard_last_review_needed_keys
        ]

    def _start_flashcard_session(
        self,
        chapter: QuizChapter,
        *,
        review_only: bool = False,
    ):
        deck = self._flashcard_questions_for_session(chapter, review_only=review_only)
        self.flashcard_session_chapter = chapter.title
        self.flashcard_queue_keys = [key for key, _question in deck]
        self.flashcard_mastered_keys = set()
        self.flashcard_review_needed_keys = set()
        self.flashcard_total_cards = len(deck)
        self.flashcard_review_only_mode = review_only
        self.flashcard_assessment_ready = False

    def _ensure_flashcard_session(self, chapter: QuizChapter):
        if (
            self.flashcard_session_chapter != chapter.title
            or self.flashcard_total_cards <= 0
            or (
                self.flashcard_review_only_mode
                and not any(
                    self._question_flashcard_key(chapter.title, question) in self.flashcard_last_review_needed_keys
                    for question in chapter.questions
                )
            )
        ):
            self._start_flashcard_session(chapter, review_only=False)

    def _find_flashcard_question(
        self,
        chapter: QuizChapter,
        question_key: str,
    ) -> QuizQuestion | None:
        for question in chapter.questions:
            if self._question_flashcard_key(chapter.title, question) == question_key:
                return question
        return None

    def _current_flashcard_key(self) -> str | None:
        if not self.flashcard_queue_keys:
            return None
        return self.flashcard_queue_keys[0]

    def _current_flashcard_question(self, chapter: QuizChapter) -> QuizQuestion | None:
        question_key = self._current_flashcard_key()
        if question_key is None:
            return None
        return self._find_flashcard_question(chapter, question_key)

    def _flashcard_progress_text(self) -> str:
        total = max(0, self.flashcard_total_cards)
        mastered = len(self.flashcard_mastered_keys)
        remaining = len(self.flashcard_queue_keys)
        review_count = len(self.flashcard_review_needed_keys)
        if total <= 0:
            return "No cards in this flashcard deck yet."
        mode_label = "Review deck" if self.flashcard_review_only_mode else "Learn deck"
        current_number = min(total, mastered + 1) if remaining else total
        return (
            f"{mode_label} | Card {current_number}/{total} | "
            f"Mastered: {mastered} | Study again: {review_count} | Remaining: {remaining}"
        )

    def _flashcard_progress_value(self) -> tuple[int, int]:
        total = max(0, self.flashcard_total_cards)
        if total <= 0:
            return 0, 1
        if self.flashcard_assessment_ready:
            return total, total
        current_step = total - len(self.flashcard_queue_keys) + 1
        return max(1, min(current_step, total)), total

    def _sync_flashcard_question_selection(self, chapter: QuizChapter):
        current_key = self._current_flashcard_key()
        if current_key is None:
            return
        for row, question in enumerate(chapter.questions):
            if self._question_flashcard_key(chapter.title, question) == current_key:
                self.question_list.blockSignals(True)
                self.question_list.setCurrentRow(row)
                self.question_list.blockSignals(False)
                return

    def _jump_flashcard_to_question(self, chapter: QuizChapter, row: int):
        if row < 0 or row >= len(chapter.questions):
            return
        target_key = self._question_flashcard_key(chapter.title, chapter.questions[row])
        if target_key not in self.flashcard_queue_keys:
            return
        while self.flashcard_queue_keys and self.flashcard_queue_keys[0] != target_key:
            self.flashcard_queue_keys.append(self.flashcard_queue_keys.pop(0))

    def _advance_flashcard(self, chapter: QuizChapter, *, mastered: bool):
        current_key = self._current_flashcard_key()
        if current_key is None:
            return

        self.flashcard_queue_keys.pop(0)
        if mastered:
            self.flashcard_mastered_keys.add(current_key)
        else:
            self.flashcard_review_needed_keys.add(current_key)
            self.flashcard_queue_keys.append(current_key)

        if not self.flashcard_queue_keys:
            self.flashcard_assessment_ready = True
            self.flashcard_last_review_needed_keys = set(self.flashcard_review_needed_keys)

        self._refresh_answer_cards()
        if not self.flashcard_assessment_ready:
            self._sync_flashcard_question_selection(chapter)

    def _handle_flashcard_shortcut(self, *, mastered: bool):
        if not self.flashcard_mode_enabled or self._is_long_quiz():
            return
        chapter = self._selected_chapter()
        if chapter is None:
            return
        self._ensure_flashcard_session(chapter)
        if self.flashcard_assessment_ready:
            return
        self._advance_flashcard(chapter, mastered=mastered)

    def _start_flashcard_review_deck(self):
        chapter = self._selected_chapter()
        if chapter is None:
            return
        if not self.flashcard_last_review_needed_keys:
            QMessageBox.information(
                self.page,
                "Nothing To Review",
                "There are no flashcards marked for more study yet.",
            )
            return
        self._start_flashcard_session(chapter, review_only=True)
        self._refresh_answer_cards()
        self._sync_flashcard_question_selection(chapter)

    def _restart_flashcard_learn_mode(self):
        chapter = self._selected_chapter()
        if chapter is None:
            return
        self._start_flashcard_session(chapter, review_only=False)
        self._refresh_answer_cards()
        self._sync_flashcard_question_selection(chapter)

    def _switch_to_quiz_mode(self):
        self.flashcard_mode_enabled = False
        if self.flashcard_toggle_button is not None:
            self.flashcard_toggle_button.blockSignals(True)
            self.flashcard_toggle_button.setChecked(False)
            self.flashcard_toggle_button.blockSignals(False)
        self._refresh_answer_cards()

    def _update_branch_toggle(self):
        if (
            not self.show_branch_viewer
            or self.branch_toggle_button is None
            or self.branch_viewer is None
        ):
            return

        has_subject = self.subject_name is not None
        self.branch_toggle_button.setEnabled(has_subject)

        show_branch_viewer = has_subject and self.branch_toggle_button.isChecked()
        self.branch_viewer.setVisible(show_branch_viewer)
        self.branch_viewer.setMinimumHeight(0)
        self.branch_viewer.setMaximumHeight(196 if show_branch_viewer else 0)

    def _refresh_branch_tree(self):
        if self.branch_tree is None:
            return

        self.branch_tree.blockSignals(True)
        self.branch_tree.clear()

        if self.subject_name is not None:
            root = QTreeWidgetItem([self.subject_name])
            root.setData(0, BRANCH_ITEM_KIND_ROLE, "subject")
            apply_hierarchical_font_to_item(root, level=0)  # Subject - largest font
            self.branch_tree.addTopLevelItem(root)

            for chapter in self.bank.chapters:
                self._ensure_branch_tree_item(root, chapter.title)

            root.setExpanded(True)
            self._sync_branch_tree_selection()

        self.branch_tree.blockSignals(False)
        self._update_branch_toggle()

    def _sync_branch_tree_selection(self):
        if self.branch_tree is None or self.branch_tree.topLevelItemCount() == 0:
            return

        root = self.branch_tree.topLevelItem(0)
        selected_chapter = self._selected_chapter()
        self.branch_tree.blockSignals(True)
        if selected_chapter is None:
            self.branch_tree.setCurrentItem(root)
        else:
            target_key = selected_chapter.title.lower()
            matched_item = self._find_branch_tree_item(root, target_key)
            self.branch_tree.setCurrentItem(matched_item or root)
        self.branch_tree.blockSignals(False)

    def _ensure_branch_tree_item(self, root: QTreeWidgetItem, chapter_path: str) -> QTreeWidgetItem | None:
        parts = split_leaf_parts(chapter_path)
        if not parts:
            return None

        parent = root
        for depth, part in enumerate(parts):
            existing = None
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child.text(0).lower() == part.lower():
                    existing = child
                    break
            if existing is None:
                existing = QTreeWidgetItem([part])
                existing.setData(0, BRANCH_ITEM_KIND_ROLE, "group")
                apply_font_to_item(
                    existing,
                    TreeFontConfig.QUIZ_CHAPTER_SIZE if depth == 0 else TreeFontConfig.QUIZ_SUBCHAPTER_SIZE,
                )
                parent.addChild(existing)
                parent.setExpanded(True)
            parent = existing

        parent.setData(0, BRANCH_ITEM_KIND_ROLE, "chapter")
        parent.setData(0, BRANCH_CHAPTER_TITLE_ROLE, chapter_path)
        return parent

    def _find_branch_tree_item(self, root: QTreeWidgetItem, target_key: str) -> QTreeWidgetItem | None:
        chapter_title = root.data(0, BRANCH_CHAPTER_TITLE_ROLE)
        if isinstance(chapter_title, str) and chapter_title.lower() == target_key:
            return root
        for index in range(root.childCount()):
            found = self._find_branch_tree_item(root.child(index), target_key)
            if found is not None:
                return found
        return None

    def _refresh_ui(self):
        if self._is_long_quiz():
            self._reconcile_long_quiz_state()

        self.question_list.blockSignals(True)
        self.question_list.clear()
        self._clear_layout(self.answer_cards_layout)
        self.answer_cards = []
        self._reset_review_state()

        self._refresh_chapter_tree()

        if self.bank.chapters:
            if self._chapter_row_for_title(self.bank.selected_chapter) < 0:
                self.bank.selected_chapter = self.bank.chapters[0].title
            self._sync_chapter_tree_selection()
            self._refresh_questions()
            self._refresh_answer_cards()
        else:
            self.question_status_label.setText("0 questions")
            if self._is_long_quiz():
                self.answer_header_label.setText("Generated Test")
                empty_text = "Add a chapter from the subject tree, then import or write questions here."
            else:
                self.answer_header_label.setText("Flashcards" if self.flashcard_mode_enabled else "Answer Board")
                empty_text = "Add a chapter from the subject tree, then import or write questions here."
            empty_label = QLabel(empty_text, self.answer_container)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.answer_cards_layout.addWidget(empty_label)

        self.question_list.blockSignals(False)
        self._refresh_branch_tree()
        self._update_status_labels()
        self._update_long_quiz_controls()

    def _update_status_labels(self):
        chapter_count = len(self.bank.chapters)
        question_count = sum(len(chapter.questions) for chapter in self.bank.chapters)
        self.status_label.setText(f"{chapter_count} chapters loaded")
        self.question_status_label.setText(f"{question_count} questions")
        self.title_label.setText(self.title)
        self.chapter_header_label.setText(self.subject_name or "Chapters")

    def _reset_review_state(self):
        self.review_submitted = False
        if self.score_label is not None:
            self.score_label.setText("")
        if self.submit_button is not None and self._is_long_quiz():
            self.submit_button.setEnabled(bool(self.long_quiz_generated_refs))
            self.submit_button.setText("Submit")

    def _chapter_row_for_title(self, title: str) -> int:
        for index, chapter in enumerate(self.bank.chapters):
            if chapter.title.lower() == title.lower():
                return index
        return -1

    def _find_chapter_tree_item(self, normalized_path: str) -> QTreeWidgetItem | None:
        for index in range(self.chapter_list.topLevelItemCount()):
            item = self._find_tree_item_by_leaf_path(self.chapter_list.topLevelItem(index), normalized_path)
            if item is not None:
                return item
        return None

    def _find_tree_item_by_leaf_path(self, item: QTreeWidgetItem, normalized_path: str) -> QTreeWidgetItem | None:
        stored_path = item.data(0, TREE_LEAF_PATH_ROLE)
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
        for chapter in self.bank.chapters:
            self._ensure_leaf_path_item(self.chapter_list, chapter.title)
        self.chapter_list.blockSignals(False)

    def _ensure_leaf_path_item(self, tree: QTreeWidget, chapter_path: str) -> QTreeWidgetItem | None:
        parts = split_leaf_parts(chapter_path)
        if not parts:
            return None

        parent_item: QTreeWidgetItem | None = None
        for depth, part in enumerate(parts):
            existing = self._find_child_item(tree, parent_item, part)
            if existing is None:
                existing = QTreeWidgetItem([part])
                if parent_item is None:
                    tree.addTopLevelItem(existing)
                    apply_font_to_item(existing, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                else:
                    parent_item.addChild(existing)
                    apply_font_to_item(existing, TreeFontConfig.QUIZ_SUBCHAPTER_SIZE)
                    parent_item.setExpanded(True)
            parent_item = existing

        if parent_item is not None:
            parent_item.setData(0, TREE_LEAF_PATH_ROLE, chapter_path)
        return parent_item

    def _find_child_item(
        self,
        tree: QTreeWidget,
        parent_item: QTreeWidgetItem | None,
        title: str,
    ) -> QTreeWidgetItem | None:
        count = tree.topLevelItemCount() if parent_item is None else parent_item.childCount()
        for index in range(count):
            item = tree.topLevelItem(index) if parent_item is None else parent_item.child(index)
            if item.text(0).lower() == title.lower():
                return item
        return None

    def _sync_chapter_tree_selection(self):
        self.chapter_list.blockSignals(True)
        if not self.bank.selected_chapter:
            self.chapter_list.clearSelection()
            self.chapter_list.setCurrentItem(None)
        else:
            item = self._find_chapter_tree_item(self.bank.selected_chapter.lower())
            self.chapter_list.setCurrentItem(item)
        self.chapter_list.blockSignals(False)

    def _refresh_questions(self):
        chapter = self._selected_chapter()
        self.question_list.blockSignals(True)
        self.question_list.clear()

        if chapter is None:
            self.question_list.blockSignals(False)
            self._update_status_labels()
            return

        for index, question in enumerate(chapter.questions, start=1):
            type_marker = "[Field]" if question.question_type == QUESTION_TYPE_NUMERIC else "[MCQ]"
            item = QListWidgetItem(f"{index}. {type_marker} {question.question}")
            self.question_list.addItem(item)

        self.question_list.blockSignals(False)
        self.bank.selected_chapter = chapter.title
        self._update_status_labels()

        if chapter.questions:
            self.question_list.setCurrentRow(0)
        elif not self._is_long_quiz():
            header_title = "Flashcards" if self.flashcard_mode_enabled else "Answer Board"
            self.answer_header_label.setText(f"{header_title} - {chapter.title}")
            self._clear_layout(self.answer_cards_layout)
            empty_label = QLabel(
                f"{chapter.title}\n\nAdd a question to begin this chapter.",
                self.answer_container,
            )
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.answer_cards_layout.addWidget(empty_label)

    def _refresh_answer_cards(self):
        if self._is_long_quiz():
            self._refresh_long_quiz_answer_cards()
            return

        chapter = self._selected_chapter()
        self._clear_layout(self.answer_cards_layout)
        self.answer_cards = []

        if chapter is None:
            self.answer_header_label.setText("Flashcards" if self.flashcard_mode_enabled else "Answer Board")
            return

        header_title = "Flashcards" if self.flashcard_mode_enabled else "Answer Board"
        self.answer_header_label.setText(f"{header_title} - {chapter.title}")

        if not chapter.questions:
            empty_label = QLabel(
                f"{chapter.title}\n\nAdd a question to begin this chapter.",
                self.answer_container,
            )
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.answer_cards_layout.addWidget(empty_label)
            return

        if self.flashcard_mode_enabled:
            self._ensure_flashcard_session(chapter)
            if self.flashcard_assessment_ready:
                self._render_flashcard_assessment_view(chapter)
                return

            current_question = self._current_flashcard_question(chapter)
            if current_question is None:
                self._start_flashcard_session(chapter, review_only=False)
                current_question = self._current_flashcard_question(chapter)
                if current_question is None:
                    return

            progress_value, progress_total = self._flashcard_progress_value()
            progress_bar = QProgressBar(self.answer_container)
            progress_bar.setRange(0, progress_total)
            progress_bar.setValue(progress_value)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"Card {progress_value}/{progress_total}")
            progress_bar.setStyleSheet(
                """
                QProgressBar {
                    background-color: #0f1728;
                    color: #edf4ff;
                    border: 1px solid #22314b;
                    border-radius: 10px;
                    text-align: center;
                    min-height: 22px;
                    font-weight: 700;
                }
                QProgressBar::chunk {
                    background-color: #2f74ff;
                    border-radius: 9px;
                }
                """
            )
            self.answer_cards_layout.addWidget(progress_bar)

            progress_label = QLabel(self._flashcard_progress_text(), self.answer_container)
            progress_label.setWordWrap(True)
            progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            progress_label.setStyleSheet("color: #9fb2cc;")
            self.answer_cards_layout.addWidget(progress_label)

            current_card = QuestionCardWidget(
                chapter.title,
                min(self.flashcard_total_cards, len(self.flashcard_mastered_keys) + 1),
                current_question,
                reveal_answers=True,
                flashcard_mode=True,
            )
            current_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.answer_cards.append(current_card)
            self.answer_cards_layout.addWidget(current_card)
            self.answer_cards_layout.setStretchFactor(current_card, 1)

            action_row = QWidget(self.answer_container)
            action_layout = QHBoxLayout(action_row)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)

            mastered_button = QPushButton("Swipe Left: Mastered", action_row)
            review_button = QPushButton("Swipe Right: Study Again", action_row)
            mastered_button.clicked.connect(lambda: self._advance_flashcard(chapter, mastered=True))
            review_button.clicked.connect(lambda: self._advance_flashcard(chapter, mastered=False))
            action_layout.addWidget(mastered_button)
            action_layout.addWidget(review_button)
            self.answer_cards_layout.addWidget(action_row)

            helper_label = QLabel(
                "Focus on one card at a time. Reveal the answer, then mark it mastered or send it back for more study.",
                self.answer_container,
            )
            helper_label.setWordWrap(True)
            helper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            helper_label.setStyleSheet("color: #9fb2cc;")
            self.answer_cards_layout.addWidget(helper_label)
            self._sync_flashcard_question_selection(chapter)
            return

        for index, question in enumerate(chapter.questions, start=1):
            card = QuestionCardWidget(
                chapter.title,
                index,
                question,
                reveal_answers=True,
                flashcard_mode=self.flashcard_mode_enabled,
            )
            self.answer_cards.append(card)
            self.answer_cards_layout.addWidget(card)

        self.answer_cards_layout.addStretch(1)

    def _render_flashcard_assessment_view(self, chapter: QuizChapter):
        mastered_count = max(0, self.flashcard_total_cards - len(self.flashcard_last_review_needed_keys))
        review_count = len(self.flashcard_last_review_needed_keys)
        mastered_label = "Mastered this round" if self.flashcard_review_only_mode else "Mastered on first pass"
        review_label = "Need another review round" if self.flashcard_review_only_mode else "Need more study"

        summary_label = QLabel(
            (
                f"Flashcard assessment for {chapter.title}\n\n"
                f"{mastered_label}: {mastered_count}/{self.flashcard_total_cards}\n"
                f"{review_label}: {review_count}/{self.flashcard_total_cards}"
            ),
            self.answer_container,
        )
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: #edf4ff; font-weight: 600;")
        self.answer_cards_layout.addWidget(summary_label)

        chart = PieChartWidget(self.answer_container)
        chart.set_segments(
            [
                ("Mastered", mastered_count, QColor("#34d399")),
                ("Study Again", review_count, QColor("#f59e0b")),
            ]
        )
        self.answer_cards_layout.addWidget(chart)

        action_row = QWidget(self.answer_container)
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        quiz_mode_button = QPushButton("Switch to Quiz Mode", action_row)
        review_button = QPushButton(
            f"Flashcards To Review ({review_count})",
            action_row,
        )
        learn_mode_button = QPushButton("Learn Mode", action_row)

        quiz_mode_button.clicked.connect(self._switch_to_quiz_mode)
        review_button.clicked.connect(self._start_flashcard_review_deck)
        learn_mode_button.clicked.connect(self._restart_flashcard_learn_mode)
        review_button.setEnabled(review_count > 0)

        action_layout.addWidget(quiz_mode_button)
        action_layout.addWidget(review_button)
        action_layout.addWidget(learn_mode_button)
        self.answer_cards_layout.addWidget(action_row)

        helper_label = QLabel(
            "Use Quiz Mode for regular testing, Flashcards To Review for the cards you pushed right, or Learn Mode to run the full deck again.",
            self.answer_container,
        )
        helper_label.setWordWrap(True)
        helper_label.setStyleSheet("color: #9fb2cc;")
        self.answer_cards_layout.addWidget(helper_label)
        self.answer_cards_layout.addStretch(1)

    def _refresh_long_quiz_answer_cards(self):
        self._clear_layout(self.answer_cards_layout)
        self.answer_cards = []
        self.answer_header_label.setText("Generated Test")

        generated_items = self._generated_long_quiz_items()
        if generated_items is None:
            if self.long_quiz_generated_refs:
                self.long_quiz_generated_refs = []
            generated_items = []

        if not generated_items:
            if self.subject_name is None:
                message = "Choose a subject first."
            elif not self._available_long_quiz_chapters():
                message = "Add questions to one or more chapters to generate a long quiz."
            elif not self.long_quiz_selected_chapters:
                message = "Open Quiz Options and choose the chapters to include in the long quiz."
            else:
                message = (
                    "Open Quiz Options, choose your chapters, set a question count, then click Generate Test "
                    "to build a shuffled long quiz."
                )

            empty_label = QLabel(message, self.answer_container)
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.answer_cards_layout.addWidget(empty_label)
            self.answer_cards_layout.addStretch(1)
            return

        self.answer_header_label.setText(
            f"Generated Test - {len(generated_items)} question{'s' if len(generated_items) != 1 else ''}"
        )
        for index, (chapter_title, question) in enumerate(generated_items, start=1):
            card = QuestionCardWidget(
                chapter_title,
                index,
                question,
                reveal_answers=False,
            )
            self.answer_cards.append(card)
            self.answer_cards_layout.addWidget(card)

        self.answer_cards_layout.addStretch(1)

    def _on_chapter_changed(self):
        chapter = self._selected_chapter()
        if chapter is None:
            self.bank.selected_chapter = ""
            self._reset_flashcard_session()
            self.question_list.clear()
            self._clear_layout(self.answer_cards_layout)
            self.answer_header_label.setText(
                "Generated Test"
                if self._is_long_quiz()
                else ("Flashcards" if self.flashcard_mode_enabled else "Answer Board")
            )
            self._reset_review_state()
            self._refresh_branch_tree()
            self._save_to_storage()
            self._update_status_labels()
            self._update_long_quiz_controls()
            return

        self.bank.selected_chapter = chapter.title
        if self.flashcard_session_chapter != chapter.title:
            self._reset_flashcard_session()
        self._refresh_questions()
        self._refresh_answer_cards()
        self._sync_branch_tree_selection()
        self._save_to_storage()
        self._update_long_quiz_controls()

    def _on_question_changed(self, row: int):
        if self._is_long_quiz():
            return
        if self.flashcard_mode_enabled:
            chapter = self._selected_chapter()
            if chapter is None:
                return
            self._ensure_flashcard_session(chapter)
            if self.flashcard_assessment_ready:
                return
            self._jump_flashcard_to_question(chapter, row)
            self._refresh_answer_cards()
            return
        if row < 0 or row >= len(self.answer_cards):
            return

        card = self.answer_cards[row]
        self.answer_scroll.ensureWidgetVisible(card)

    def _on_branch_toggle_toggled(self, checked: bool):
        self._update_branch_toggle()

    def _on_flashcard_mode_toggled(self, checked: bool):
        self.flashcard_mode_enabled = bool(checked)
        if self.flashcard_mode_enabled:
            self._reset_flashcard_session()
        self._refresh_answer_cards()

    def _on_branch_tree_selection_changed(self):
        if self.branch_tree is None:
            return

        current_item = self.branch_tree.currentItem()
        if current_item is None:
            return

        item_kind = current_item.data(0, BRANCH_ITEM_KIND_ROLE)
        if item_kind != "chapter":
            return

        chapter_title = current_item.data(0, BRANCH_CHAPTER_TITLE_ROLE)
        if isinstance(chapter_title, str):
            self.focus_chapter(chapter_title)

    def focus_chapter(self, chapter_title: str) -> bool:
        item = self._find_chapter_tree_item(chapter_title.strip().lower())
        if item is None:
            return False
        self.chapter_list.setCurrentItem(item)
        return True

    def add_chapter(self):
        QMessageBox.information(
            self.page,
            "Manage Chapters",
            "Add chapters from the subject tree by right-clicking a subject.",
        )

    def import_chapters(self, checked: bool = False, file_path: str | None = None):
        if isinstance(checked, (str, Path)) and file_path is None:
            file_path = str(checked)

        if file_path is None:
            file_path, _ = QFileDialog.getOpenFileName(
                self.page,
                f"Import {self.title}",
                "",
                "Quiz JSON (*.json);;All Files (*)",
            )
            if not file_path:
                return

        if self.subject_name is None:
            if self.subject_resolver is None:
                QMessageBox.information(self.page, "Select Subject", "Choose a subject first.")
                return

            resolved_subject = self.subject_resolver()
            if not resolved_subject:
                return

            self.set_subject(resolved_subject)

        try:
            imported_questions = load_question_list_from_path(file_path)
        except (OSError, json.JSONDecodeError, QuizFormatError) as exc:
            QMessageBox.warning(self.page, "Import Failed", str(exc))
            return

        target_chapter = self._selected_chapter()
        if target_chapter is None:
            target_chapter = self._resolve_target_chapter_for_import()
            if target_chapter is None:
                return

        self._merge_questions(target_chapter, imported_questions)
        self._after_question_bank_mutation()
        
        # Sync questions to the sister quiz controller if available
        self._sync_questions_to_sister_controller(target_chapter.title, imported_questions)
        
        QMessageBox.information(
            self.page,
            "Import Complete",
            f"Imported {len(imported_questions)} questions into '{target_chapter.title}'.",
        )

    def _resolve_target_chapter_for_import(self) -> QuizChapter | None:
        if not self.bank.chapters:
            QMessageBox.information(
                self.page,
                "Add Chapter First",
                "Add a chapter from the subject tree before importing questions.",
            )
            return None

        titles = [chapter.title for chapter in self.bank.chapters]
        chosen_title, accepted = QInputDialog.getItem(
            self.page,
            f"Import {self.title}",
            "Choose the chapter to receive the questions:",
            titles,
            0,
            False,
        )
        if not accepted:
            return None

        for chapter in self.bank.chapters:
            if chapter.title == chosen_title:
                self.bank.selected_chapter = chapter.title
                return chapter

        return None

    def _sync_questions_to_sister_controller(self, chapter_title: str, questions: list[QuizQuestion]):
        """Sync imported questions to the other quiz type (short <-> long)."""
        if self.sister_controller is None:
            return
        
        # Find or create the same chapter in the sister controller
        sister_chapter = None
        for chapter in self.sister_controller.bank.chapters:
            if chapter.title.lower() == chapter_title.lower():
                sister_chapter = chapter
                break
        
        if sister_chapter is None:
            # Chapter doesn't exist in sister controller, create it
            sister_chapter = QuizChapter(title=chapter_title)
            self.sister_controller.bank.chapters.append(sister_chapter)
        
        # Merge questions into the sister chapter
        self._merge_questions(sister_chapter, questions)
        
        # Save the sister controller's data
        if self.sister_controller.storage_path is not None:
            self.sister_controller._save_to_storage()

    def _merge_questions(self, target: QuizChapter, incoming_questions: list[QuizQuestion]):
        question_map = {question.question.lower(): question for question in target.questions}
        for incoming_question in incoming_questions:
            key = incoming_question.question.lower()
            if key in question_map:
                existing = question_map[key]
                existing.choices = incoming_question.choices
                existing.answer_index = incoming_question.answer_index
                existing.answer_text = incoming_question.answer_text
                existing.explanation = incoming_question.explanation
                existing.tags = incoming_question.tags
                existing.question_type = incoming_question.question_type
                existing.expected_answer = incoming_question.expected_answer
                existing.accepted_deviation = incoming_question.accepted_deviation
                existing.solution_file = incoming_question.solution_file
            else:
                target.questions.append(incoming_question)

    def _merge_bank(self, incoming: QuizBank):
        chapter_map = {chapter.title.lower(): chapter for chapter in self.bank.chapters}
        for incoming_chapter in incoming.chapters:
            key = incoming_chapter.title.lower()
            if key in chapter_map:
                target_chapter = chapter_map[key]
                self._merge_chapter(target_chapter, incoming_chapter)
            else:
                self.bank.chapters.append(incoming_chapter)

        if incoming.selected_chapter and self._chapter_row_for_title(incoming.selected_chapter) >= 0:
            self.bank.selected_chapter = incoming.selected_chapter
        elif not self.bank.selected_chapter and self.bank.chapters:
            self.bank.selected_chapter = self.bank.chapters[0].title

    def _merge_chapter(self, target: QuizChapter, incoming: QuizChapter):
        question_map = {question.question.lower(): question for question in target.questions}
        for incoming_question in incoming.questions:
            key = incoming_question.question.lower()
            if key in question_map:
                existing = question_map[key]
                existing.choices = incoming_question.choices
                existing.answer_index = incoming_question.answer_index
                existing.answer_text = incoming_question.answer_text
                existing.explanation = incoming_question.explanation
                existing.tags = incoming_question.tags
                existing.question_type = incoming_question.question_type
                existing.expected_answer = incoming_question.expected_answer
                existing.accepted_deviation = incoming_question.accepted_deviation
                existing.solution_file = incoming_question.solution_file
            else:
                target.questions.append(incoming_question)

    def export_bank(self, checked: bool = False, file_path: str | None = None):
        if isinstance(checked, (str, Path)) and file_path is None:
            file_path = str(checked)

        if self.subject_name is None:
            if self.subject_resolver is None:
                QMessageBox.information(self.page, "Select Subject", "Choose a subject first.")
                return

            resolved_subject = self.subject_resolver()
            if not resolved_subject:
                return

            self.set_subject(resolved_subject)

        if file_path is None:
            file_path, _ = QFileDialog.getSaveFileName(
                self.page,
                f"Export {self.title}",
                "",
                "Quiz JSON (*.json)",
            )
            if not file_path:
                return

        payload = self.bank.to_dict()
        payload["subject"] = self.subject_name
        if self._is_long_quiz():
            payload["long_quiz_state"] = self._long_quiz_state_payload()
        try:
            with Path(file_path).open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as exc:
            QMessageBox.warning(self.page, "Export Failed", str(exc))
            return

        QMessageBox.information(self.page, "Export Complete", f"Saved quiz bank to {file_path}.")

    def add_question(self):
        chapter = self._selected_chapter()
        if chapter is None:
            QMessageBox.information(self.page, "Select Chapter", "Add or select a chapter first.")
            return

        dialog = QuestionEditorDialog(self.page)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            question = dialog.to_question()
        except QuizFormatError as exc:
            QMessageBox.warning(self.page, "Invalid Question", str(exc))
            return

        chapter.questions.append(question)
        self._after_question_bank_mutation()

    def edit_question(self):
        chapter = self._selected_chapter()
        question = self._selected_question()
        if chapter is None or question is None:
            QMessageBox.information(self.page, "Select Question", "Choose a question to edit.")
            return

        dialog = QuestionEditorDialog(self.page, question)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            updated = dialog.to_question()
        except QuizFormatError as exc:
            QMessageBox.warning(self.page, "Invalid Question", str(exc))
            return

        row = self.question_list.currentRow()
        chapter.questions[row] = updated
        self._after_question_bank_mutation()
        self.question_list.setCurrentRow(row)

    def delete_question(self):
        chapter = self._selected_chapter()
        question = self._selected_question()
        if chapter is None or question is None:
            QMessageBox.information(self.page, "Select Question", "Choose a question to delete.")
            return

        confirm = QMessageBox.question(
            self.page,
            "Delete Question",
            "Delete the selected question?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        row = self.question_list.currentRow()
        del chapter.questions[row]
        self._after_question_bank_mutation()

    def _after_question_bank_mutation(self):
        self._reset_review_state()
        self._reset_flashcard_session()
        if self._is_long_quiz():
            self.long_quiz_generated_refs = []
            self._reconcile_long_quiz_state()
        self._refresh_ui()
        self._save_to_storage()

    def open_long_quiz_setup_dialog(self):
        if not self._is_long_quiz():
            return
        if self.subject_name is None:
            QMessageBox.information(self.page, "Select Subject", "Choose a subject first.")
            return

        chapters = self._available_long_quiz_chapters()
        if not chapters:
            QMessageBox.information(
                self.page,
                "No Questions Available",
                "Add questions to one or more chapters before building a long quiz.",
            )
            return

        dialog = LongQuizSetupDialog(
            self.page,
            chapters,
            self.long_quiz_selected_chapters,
            self.long_quiz_requested_count,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected_titles, requested_count = dialog.selection()
        if (
            selected_titles == self.long_quiz_selected_chapters
            and requested_count == self.long_quiz_requested_count
        ):
            return

        self.long_quiz_selected_chapters = selected_titles
        self.long_quiz_requested_count = requested_count
        self.long_quiz_generated_refs = []
        self._reconcile_long_quiz_state()
        self._reset_review_state()
        self._refresh_answer_cards()
        self._update_long_quiz_controls()
        self._save_to_storage()

    def generate_long_quiz(self):
        if not self._is_long_quiz():
            return
        if self.subject_name is None:
            QMessageBox.information(self.page, "Select Subject", "Choose a subject first.")
            return

        self._reconcile_long_quiz_state()
        pool = self._long_quiz_question_pool()
        if not pool:
            QMessageBox.information(
                self.page,
                "No Questions Available",
                "Choose one or more chapters that contain questions.",
            )
            return

        requested_count = self.long_quiz_requested_count
        if requested_count <= 0:
            QMessageBox.information(
                self.page,
                "Set Question Count",
                "Set how many questions to generate before starting the test.",
            )
            return

        actual_count = min(requested_count, len(pool))
        generated_items = random.sample(pool, actual_count)
        self.long_quiz_generated_refs = [
            LongQuizQuestionRef(chapter_title=chapter_title, question_text=question.question)
            for chapter_title, question in generated_items
        ]
        self.long_quiz_requested_count = actual_count
        self._reset_review_state()
        self.quiz_start_time = datetime.now()
        self._refresh_answer_cards()
        self._update_long_quiz_controls()
        self._save_to_storage()

    def set_assessment_controller(self, controller: Any):
        """Set reference to assessment tab controller for saving results."""
        self.assessment_tab_controller = controller

    def set_sister_controller(self, controller: Any):
        """Set reference to the other quiz type (short_quiz <-> long_quiz) for sync."""
        self.sister_controller = controller

    def submit_long_quiz(self, *, show_missing_generation_message: bool = True) -> bool:
        if not self._is_long_quiz():
            return False

        if not self.answer_cards:
            if show_missing_generation_message:
                QMessageBox.information(
                    self.page,
                    "Generate Test First",
                    "Generate a long quiz before submitting it.",
                )
            return False

        if self.review_submitted:
            return False

        total = len(self.answer_cards)
        correct = 0
        answered = 0
        question_results: list[QuestionResult] = []

        for card in self.answer_cards:
            if card.has_response():
                answered += 1
            is_correct = card.is_correct_response()
            if is_correct:
                correct += 1
            card.reveal_review(is_correct)
            
            # Build question result for assessment
            user_answer = card.user_answer_text()
            question_results.append(
                QuestionResult(
                    question_text=card.question.question,
                    chapter_title=card.chapter_title,
                    correct_answer=card.question.answer_text,
                    user_answer=user_answer,
                    is_correct=is_correct,
                    explanation=card.question.explanation,
                )
            )

        score_text = f"Score: {correct}/{total}"
        if answered != total:
            score_text += f" | Answered: {answered}/{total}"

        if self.score_label is not None:
            self.score_label.setText(score_text)
        self.answer_header_label.setText("Review Board - Generated Test")
        self.review_submitted = True
        if self.submit_button is not None:
            self.submit_button.setEnabled(False)
            self.submit_button.setText("Submitted")
        
        # Calculate duration
        duration_seconds = 0
        if self.quiz_start_time is not None:
            duration = datetime.now() - self.quiz_start_time
            duration_seconds = int(duration.total_seconds())
        
        # Create and save quiz attempt
        if self.assessment_tab_controller is not None:
            chapter_title = self.long_quiz_selected_chapters[0] if self.long_quiz_selected_chapters else "Unknown"
            attempt = QuizAttempt(
                attempt_id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat(),
                quiz_type="long_quiz",
                chapter_title=chapter_title,
                total_questions=total,
                correct_count=correct,
                answered_count=answered,
                duration_seconds=duration_seconds,
                question_results=question_results,
            )
            self.assessment_tab_controller.save_quiz_attempt(attempt)
        
        self._update_long_quiz_controls()
        self._save_to_storage()
        return True

    def auto_submit_long_quiz_on_timeout(self) -> bool:
        if not self._is_long_quiz():
            return False
        return self.submit_long_quiz(show_missing_generation_message=False)

    def _reset_long_quiz_state(self):
        self.long_quiz_selected_chapters = []
        self.long_quiz_requested_count = 0
        self.long_quiz_generated_refs = []

    def _load_long_quiz_state(self, payload: Any):
        self._reset_long_quiz_state()
        if not isinstance(payload, dict):
            return

        selected_titles = payload.get("selected_chapters", [])
        if isinstance(selected_titles, list):
            seen: set[str] = set()
            for entry in selected_titles:
                if not isinstance(entry, str) or not entry.strip():
                    continue
                normalized = entry.strip()
                key = normalized.lower()
                if key in seen:
                    continue
                seen.add(key)
                self.long_quiz_selected_chapters.append(normalized)

        requested_count = payload.get("requested_question_count")
        if isinstance(requested_count, int) and requested_count >= 0:
            self.long_quiz_requested_count = requested_count

        refs_payload = payload.get("generated_question_refs", [])
        if isinstance(refs_payload, list):
            for entry in refs_payload:
                ref = LongQuizQuestionRef.from_dict(entry)
                if ref is not None:
                    self.long_quiz_generated_refs.append(ref)

    def _long_quiz_state_payload(self) -> dict[str, Any]:
        return {
            "selected_chapters": self.long_quiz_selected_chapters,
            "requested_question_count": self.long_quiz_requested_count,
            "generated_question_refs": [ref.to_dict() for ref in self.long_quiz_generated_refs],
        }

    def _available_long_quiz_chapters(self) -> list[QuizChapter]:
        return [chapter for chapter in self.bank.chapters if chapter.questions]

    def _long_quiz_selectable_titles(self) -> list[str]:
        titles: list[str] = []
        for chapter in self._available_long_quiz_chapters():
            chapter_title, subchapter_title = split_leaf_path(chapter.title)
            candidates = [chapter.title]
            if subchapter_title is not None:
                candidates.insert(0, chapter_title)
            for candidate in candidates:
                if any(saved.lower() == candidate.lower() for saved in titles):
                    continue
                titles.append(candidate)
        return titles

    def _expanded_long_quiz_selection_keys(
        self,
        selected_titles: list[str] | None = None,
    ) -> set[str]:
        if selected_titles is None:
            selected_titles = self.long_quiz_selected_chapters
        selected_keys = {title.lower() for title in selected_titles}
        expanded_keys: set[str] = set()
        for chapter in self.bank.chapters:
            chapter_title, _subchapter_title = split_leaf_path(chapter.title)
            if chapter.title.lower() in selected_keys or chapter_title.lower() in selected_keys:
                expanded_keys.add(chapter.title.lower())
        return expanded_keys

    def _canonical_chapter_title(self, title: str) -> str | None:
        normalized = title.strip().lower()
        for chapter_title in self._long_quiz_selectable_titles():
            if chapter_title.lower() == normalized:
                return chapter_title
        return None

    def _default_long_quiz_chapter_selection(self) -> list[str]:
        available_titles = self._long_quiz_selectable_titles()
        if not available_titles:
            return []

        selected_chapter = self._selected_chapter()
        if selected_chapter is not None:
            chapter_title, _subchapter_title = split_leaf_path(selected_chapter.title)
            for candidate in (selected_chapter.title, chapter_title):
                if any(title.lower() == candidate.lower() for title in available_titles):
                    return [candidate]

        if self.bank.selected_chapter:
            canonical = self._canonical_chapter_title(self.bank.selected_chapter)
            if canonical is not None:
                return [canonical]

        return [available_titles[0]]

    def _reconcile_long_quiz_state(self) -> bool:
        if not self._is_long_quiz():
            return False

        changed = False
        available_titles = self._long_quiz_selectable_titles()
        available_by_key = {title.lower(): title for title in available_titles}

        selected_titles: list[str] = []
        seen_keys: set[str] = set()
        for title in self.long_quiz_selected_chapters:
            key = title.strip().lower()
            canonical = available_by_key.get(key)
            if canonical is None or key in seen_keys:
                continue
            seen_keys.add(key)
            selected_titles.append(canonical)

        if not selected_titles and available_titles:
            selected_titles = self._default_long_quiz_chapter_selection()

        if selected_titles != self.long_quiz_selected_chapters:
            self.long_quiz_selected_chapters = selected_titles
            changed = True

        available_count = self._long_quiz_available_question_count(selected_titles)
        normalized_count = self.long_quiz_requested_count
        if available_count <= 0:
            normalized_count = 0
        elif normalized_count <= 0:
            normalized_count = available_count
        else:
            normalized_count = min(normalized_count, available_count)

        valid_refs: list[LongQuizQuestionRef] = []
        generated_items_valid = True
        selected_keys = self._expanded_long_quiz_selection_keys()
        for ref in self.long_quiz_generated_refs:
            resolved = self._resolve_long_quiz_ref(ref)
            if resolved is None or resolved[0].lower() not in selected_keys:
                generated_items_valid = False
                break
            valid_refs.append(ref)

        if not generated_items_valid:
            valid_refs = []

        if valid_refs and len(valid_refs) != normalized_count:
            normalized_count = len(valid_refs)
            changed = True

        if normalized_count != self.long_quiz_requested_count:
            self.long_quiz_requested_count = normalized_count
            changed = True

        if valid_refs != self.long_quiz_generated_refs:
            self.long_quiz_generated_refs = valid_refs
            changed = True

        return changed

    def _long_quiz_question_pool(
        self,
        selected_titles: list[str] | None = None,
    ) -> list[tuple[str, QuizQuestion]]:
        if selected_titles is None:
            selected_titles = self.long_quiz_selected_chapters
        selected_keys = self._expanded_long_quiz_selection_keys(selected_titles)
        pool: list[tuple[str, QuizQuestion]] = []
        for chapter in self.bank.chapters:
            if chapter.title.lower() not in selected_keys:
                continue
            for question in chapter.questions:
                pool.append((chapter.title, question))
        return pool

    def _long_quiz_available_question_count(self, selected_titles: list[str] | None = None) -> int:
        return len(self._long_quiz_question_pool(selected_titles))

    def _resolve_long_quiz_ref(
        self,
        ref: LongQuizQuestionRef,
    ) -> tuple[str, QuizQuestion] | None:
        chapter = next(
            (item for item in self.bank.chapters if item.title.lower() == ref.chapter_title.lower()),
            None,
        )
        if chapter is None:
            return None

        for question in chapter.questions:
            if question.question == ref.question_text:
                return chapter.title, question
        for question in chapter.questions:
            if question.question.lower() == ref.question_text.lower():
                return chapter.title, question
        return None

    def _generated_long_quiz_items(self) -> list[tuple[str, QuizQuestion]] | None:
        generated_items: list[tuple[str, QuizQuestion]] = []
        for ref in self.long_quiz_generated_refs:
            resolved = self._resolve_long_quiz_ref(ref)
            if resolved is None:
                return None
            generated_items.append(resolved)
        return generated_items

    def _long_quiz_generated_coverage(
        self,
        generated_items: list[tuple[str, QuizQuestion]],
    ) -> list[tuple[str, int]]:
        counts = {title: 0 for title in self.long_quiz_selected_chapters}
        for chapter_title, _question in generated_items:
            chapter_key = chapter_title.lower()
            for selected_title in self.long_quiz_selected_chapters:
                selected_key = selected_title.lower()
                if chapter_key == selected_key:
                    counts[selected_title] = counts.get(selected_title, 0) + 1
                    continue
                parent_title, subchapter_title = split_leaf_path(chapter_title)
                if subchapter_title is not None and parent_title.lower() == selected_key:
                    counts[selected_title] = counts.get(selected_title, 0) + 1
        return [(title, counts.get(title, 0)) for title in self.long_quiz_selected_chapters]

    def _update_long_quiz_controls(self):
        if not self._is_long_quiz():
            return

        available_chapters = self._available_long_quiz_chapters()
        available_count = self._long_quiz_available_question_count()
        has_subject = self.subject_name is not None

        if self.long_quiz_options_button is not None:
            self.long_quiz_options_button.setEnabled(has_subject and bool(available_chapters))
            selected_count = len(self.long_quiz_selected_chapters)
            count_label = (
                f"{self.long_quiz_requested_count} question"
                f"{'s' if self.long_quiz_requested_count != 1 else ''}"
            )
            if selected_count > 0 and self.long_quiz_requested_count > 0:
                self.long_quiz_options_button.setText(
                    f"Quiz Options ({selected_count} chapters, {count_label})"
                )
            else:
                self.long_quiz_options_button.setText("Quiz Options")

        if self.long_quiz_generate_button is not None:
            self.long_quiz_generate_button.setEnabled(
                has_subject and available_count > 0 and self.long_quiz_requested_count > 0
            )
            self.long_quiz_generate_button.setText(
                "Regenerate Test" if self.long_quiz_generated_refs else "Generate Test"
            )

        if self.submit_button is not None:
            self.submit_button.setEnabled(bool(self.long_quiz_generated_refs) and not self.review_submitted)


class ShortQuizTabController(ChapterQuizTabController):
    def __init__(self, page: QWidget):
        super().__init__(
            page,
            prefix="short_quiz",
            title="Short Quiz",
            show_branch_viewer=False,
        )


class LongQuizTabController(ChapterQuizTabController):
    def __init__(self, page: QWidget):
        super().__init__(
            page,
            prefix="long_quiz",
            title="Long Quiz",
            show_branch_viewer=True,
        )

import json
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QSizePolicy,
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

from tree_font_utils import apply_hierarchical_font_to_item, apply_font_to_item, TreeFontConfig, apply_font_to_widget


class QuizFormatError(ValueError):
    pass


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


@dataclass
class QuizQuestion:
    question: str
    choices: list[str]
    answer_index: int
    answer_text: str
    explanation: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "choices": self.choices,
            "answer_index": self.answer_index,
            "answer_text": self.answer_text,
            "explanation": self.explanation,
            "tags": self.tags,
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
    choices = entry.get("choices")
    answer_index = entry.get("answer_index", entry.get("answer"))
    answer_text = entry.get("answer_text")
    explanation = entry.get("explanation", "")
    tags = entry.get("tags", [])

    if not isinstance(question, str) or not question.strip():
        raise QuizFormatError(f"Question {position} is missing a valid 'question' field.")

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

    return QuizQuestion(
        question=question.strip(),
        choices=normalized_choices,
        answer_index=resolved_answer_index,
        answer_text=normalized_answer_text,
        explanation=normalized_explanation,
        tags=normalized_tags,
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
        self.setMinimumWidth(520)
        self._build_ui(question)

    def _build_ui(self, question: QuizQuestion | None):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.question_edit = QLineEdit(self)
        self.question_edit.setPlaceholderText("Enter the question text")

        self.choices_edit = QPlainTextEdit(self)
        self.choices_edit.setPlaceholderText("One choice per line")

        self.answer_edit = QLineEdit(self)
        self.answer_edit.setPlaceholderText("Choice text or zero-based index")

        self.explanation_edit = QPlainTextEdit(self)
        self.explanation_edit.setPlaceholderText("Optional explanation")

        self.tags_edit = QLineEdit(self)
        self.tags_edit.setPlaceholderText("Comma-separated tags")

        form.addRow("Question", self.question_edit)
        form.addRow("Choices", self.choices_edit)
        form.addRow("Answer", self.answer_edit)
        form.addRow("Explanation", self.explanation_edit)
        form.addRow("Tags", self.tags_edit)
        layout.addLayout(form)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if question is not None:
            self.question_edit.setText(question.question)
            self.choices_edit.setPlainText("\n".join(question.choices))
            self.answer_edit.setText(str(question.answer_index))
            self.explanation_edit.setPlainText(question.explanation)
            self.tags_edit.setText(", ".join(question.tags))

    def to_question(self) -> QuizQuestion:
        question_text = self.question_edit.text().strip()
        if not question_text:
            raise QuizFormatError("Please enter a question.")

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

        explanation = self.explanation_edit.toPlainText().strip()
        tags = [tag.strip() for tag in self.tags_edit.text().split(",") if tag.strip()]

        return QuizQuestion(
            question=question_text,
            choices=choices,
            answer_index=answer_index,
            answer_text=choices[answer_index],
            explanation=explanation,
            tags=tags,
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
            label = (
                f"{subchapter_title} ({len(chapter.questions)} question{'s' if len(chapter.questions) != 1 else ''})"
                if subchapter_title is not None
                else f"{chapter_title} ({len(chapter.questions)} question{'s' if len(chapter.questions) != 1 else ''})"
            )
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.ItemDataRole.UserRole, chapter.title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if chapter.title.lower() in selected_keys else Qt.CheckState.Unchecked)
            if subchapter_title is None:
                self.chapter_list.addTopLevelItem(item)
                continue
            parent_item = roots.get(chapter_title.lower())
            if parent_item is None:
                parent_item = QTreeWidgetItem([chapter_title])
                roots[chapter_title.lower()] = parent_item
                self.chapter_list.addTopLevelItem(parent_item)
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
        selected_keys = {title.lower() for title in self.selected_chapter_titles()}
        total = 0
        for chapter in self._chapters:
            if chapter.title.lower() in selected_keys:
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


class QuestionCardWidget(QFrame):
    def __init__(
        self,
        chapter_title: str,
        question_number: int,
        question: QuizQuestion,
        *,
        reveal_answers: bool = True,
    ):
        super().__init__()
        self.question = question
        self.question_number = question_number
        self.chapter_title = chapter_title
        self.selected_choice = -1
        self.reveal_answers = reveal_answers

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

        layout.addWidget(chapter_label)
        layout.addWidget(question_label)

        self.choice_group = QButtonGroup(self)
        self.choice_group.setExclusive(True)
        self.choice_group.buttonToggled.connect(self._on_choice_toggled)

        for index, choice in enumerate(question.choices):
            button = QRadioButton(choice, self)
            button.setProperty("choiceIndex", index)
            button.setStyleSheet("color: #ffffff;")
            apply_font_to_widget(button, TreeFontConfig.CHOICE_TEXT_SIZE)
            self.choice_group.addButton(button, index)
            layout.addWidget(button)

        self.feedback_label = QLabel("Select an answer", self)
        self.feedback_label.setWordWrap(True)
        if not self.reveal_answers:
            self.feedback_label.setText("Answer first, then submit for a score.")
            self.feedback_label.setStyleSheet("color: #7e8ca8;")
        layout.addWidget(self.feedback_label)
        layout.addStretch(1)

    def _on_choice_toggled(self, button: QRadioButton, checked: bool):
        if not checked:
            return

        choice_index = self.choice_group.id(button)
        self.selected_choice = choice_index

        if not self.reveal_answers:
            return

        if choice_index == self.question.answer_index:
            self.setProperty("cardState", "correct")
            self.feedback_label.setText(f"Correct: {self.question.answer_text}")
            self.feedback_label.setStyleSheet("color: #8de2b1;")
        else:
            self.setProperty("cardState", "incorrect")
            self.feedback_label.setText(f"Incorrect. Correct answer: {self.question.answer_text}")
            self.feedback_label.setStyleSheet("color: #ff9b9b;")

    def reveal_review(self, correct: bool):
        for button in self.choice_group.buttons():
            button.setEnabled(False)

        if correct:
            self.setProperty("cardState", "correct")
            self.feedback_label.setText(f"Correct: {self.question.answer_text}")
            self.feedback_label.setStyleSheet("color: #8de2b1;")
        else:
            self.setProperty("cardState", "incorrect")
            if self.selected_choice < 0:
                self.feedback_label.setText(
                    f"Not answered. Correct answer: {self.question.answer_text}"
                )
            else:
                self.feedback_label.setText(
                    f"Incorrect. Correct answer: {self.question.answer_text}"
                )
            self.feedback_label.setStyleSheet("color: #ff9b9b;")


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

        answer_panel_layout = self.answer_header_label.parentWidget().layout()
        answer_panel_layout.removeWidget(self.answer_header_label)

        self.answer_header_toolbar = QWidget(self.answer_header_label.parentWidget())
        header_toolbar_layout = QHBoxLayout(self.answer_header_toolbar)
        header_toolbar_layout.setContentsMargins(0, 0, 0, 0)
        header_toolbar_layout.setSpacing(8)
        header_toolbar_layout.addWidget(self.answer_header_label, 1)

        self.branch_toggle_button: QToolButton | None = None
        self.branch_viewer: QWidget | None = None
        self.branch_tree: QTreeWidget | None = None
        if self.show_branch_viewer:
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

        if self.show_branch_viewer:
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
        self.long_quiz_summary_label: QLabel | None = None
        self.long_quiz_choose_chapters_button: QPushButton | None = None
        self.long_quiz_question_count_spinbox: QSpinBox | None = None
        self.long_quiz_generate_button: QPushButton | None = None
        if self._is_long_quiz():
            self._build_long_quiz_setup_ui(answer_panel_layout)

        self._update_branch_toggle()

    def _build_long_quiz_setup_ui(self, answer_panel_layout):
        review_toolbar = self.submit_button.parentWidget() if self.submit_button is not None else None
        insert_index = answer_panel_layout.indexOf(review_toolbar) if review_toolbar is not None else 1
        if insert_index < 0:
            insert_index = 1

        self.long_quiz_setup_toolbar = QWidget(self.answer_header_label.parentWidget())
        setup_layout = QHBoxLayout(self.long_quiz_setup_toolbar)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(8)

        self.long_quiz_choose_chapters_button = QPushButton("Choose Chapters", self.long_quiz_setup_toolbar)
        self.long_quiz_question_count_spinbox = QSpinBox(self.long_quiz_setup_toolbar)
        self.long_quiz_question_count_spinbox.setMinimum(0)
        self.long_quiz_question_count_spinbox.setMaximum(0)
        self.long_quiz_question_count_spinbox.setPrefix("Questions: ")
        self.long_quiz_generate_button = QPushButton("Generate Test", self.long_quiz_setup_toolbar)

        setup_layout.addWidget(self.long_quiz_choose_chapters_button)
        setup_layout.addWidget(self.long_quiz_question_count_spinbox)
        setup_layout.addStretch(1)
        setup_layout.addWidget(self.long_quiz_generate_button)

        self.long_quiz_summary_label = QLabel(self.answer_header_label.parentWidget())
        self.long_quiz_summary_label.setWordWrap(True)
        self.long_quiz_summary_label.setStyleSheet("color: #9fb2cc;")

        answer_panel_layout.insertWidget(insert_index, self.long_quiz_setup_toolbar)
        answer_panel_layout.insertWidget(insert_index + 1, self.long_quiz_summary_label)

    def _wire_signals(self):
        self.chapter_list.itemSelectionChanged.connect(self._on_chapter_changed)
        self.question_list.currentRowChanged.connect(self._on_question_changed)
        self.add_chapter_button.clicked.connect(self.add_chapter)
        self.import_button.clicked.connect(self.import_chapters)
        self.export_button.clicked.connect(self.export_bank)
        self.add_question_button.clicked.connect(self.add_question)
        self.edit_question_button.clicked.connect(self.edit_question)
        self.delete_question_button.clicked.connect(self.delete_question)
        if self.branch_toggle_button is not None:
            self.branch_toggle_button.toggled.connect(self._on_branch_toggle_toggled)
        if self.branch_tree is not None:
            self.branch_tree.itemSelectionChanged.connect(self._on_branch_tree_selection_changed)
        if self.submit_button is not None:
            self.submit_button.clicked.connect(self.submit_long_quiz)
        if self.long_quiz_choose_chapters_button is not None:
            self.long_quiz_choose_chapters_button.clicked.connect(self.open_long_quiz_setup_dialog)
        if self.long_quiz_question_count_spinbox is not None:
            self.long_quiz_question_count_spinbox.valueChanged.connect(self._on_long_quiz_count_changed)
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
                chapter_title, subchapter_title = split_leaf_path(chapter.title)
                if subchapter_title is None:
                    child = QTreeWidgetItem([chapter_title])
                    child.setData(0, BRANCH_ITEM_KIND_ROLE, "chapter")
                    child.setData(0, BRANCH_CHAPTER_TITLE_ROLE, chapter.title)
                    apply_font_to_item(child, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                    root.addChild(child)
                    continue

                parent_item = None
                for index in range(root.childCount()):
                    existing = root.child(index)
                    if existing.text(0).lower() == chapter_title.lower() and existing.data(0, BRANCH_ITEM_KIND_ROLE) == "group":
                        parent_item = existing
                        break
                if parent_item is None:
                    parent_item = QTreeWidgetItem([chapter_title])
                    parent_item.setData(0, BRANCH_ITEM_KIND_ROLE, "group")
                    apply_font_to_item(parent_item, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                    root.addChild(parent_item)
                child = QTreeWidgetItem([subchapter_title])
                child.setData(0, BRANCH_ITEM_KIND_ROLE, "chapter")
                child.setData(0, BRANCH_CHAPTER_TITLE_ROLE, chapter.title)
                apply_font_to_item(child, TreeFontConfig.QUIZ_SUBCHAPTER_SIZE)
                parent_item.addChild(child)
                parent_item.setExpanded(True)

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
            matched_item = None
            for index in range(root.childCount()):
                child = root.child(index)
                chapter_title = child.data(0, BRANCH_CHAPTER_TITLE_ROLE)
                if isinstance(chapter_title, str) and chapter_title.lower() == target_key:
                    matched_item = child
                    break
                for child_index in range(child.childCount()):
                    grandchild = child.child(child_index)
                    chapter_title = grandchild.data(0, BRANCH_CHAPTER_TITLE_ROLE)
                    if isinstance(chapter_title, str) and chapter_title.lower() == target_key:
                        matched_item = grandchild
                        break
                if matched_item is not None:
                    break
            self.branch_tree.setCurrentItem(matched_item or root)
        self.branch_tree.blockSignals(False)

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
                self.answer_header_label.setText("Answer Board")
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
            item = self.chapter_list.topLevelItem(index)
            stored_path = item.data(0, TREE_LEAF_PATH_ROLE)
            if isinstance(stored_path, str) and stored_path.lower() == normalized_path:
                return item
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                stored_path = child.data(0, TREE_LEAF_PATH_ROLE)
                if isinstance(stored_path, str) and stored_path.lower() == normalized_path:
                    return child
        return None

    def _refresh_chapter_tree(self):
        self.chapter_list.blockSignals(True)
        self.chapter_list.clear()
        roots: dict[str, QTreeWidgetItem] = {}
        for chapter in self.bank.chapters:
            chapter_title, subchapter_title = split_leaf_path(chapter.title)
            if subchapter_title is None:
                item = QTreeWidgetItem([chapter_title])
                item.setData(0, TREE_LEAF_PATH_ROLE, chapter.title)
                apply_font_to_item(item, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                self.chapter_list.addTopLevelItem(item)
                continue

            parent_item = roots.get(chapter_title.lower())
            if parent_item is None:
                parent_item = QTreeWidgetItem([chapter_title])
                roots[chapter_title.lower()] = parent_item
                apply_font_to_item(parent_item, TreeFontConfig.QUIZ_CHAPTER_SIZE)
                self.chapter_list.addTopLevelItem(parent_item)
            child_item = QTreeWidgetItem([subchapter_title])
            child_item.setData(0, TREE_LEAF_PATH_ROLE, chapter.title)
            apply_font_to_item(child_item, TreeFontConfig.QUIZ_SUBCHAPTER_SIZE)
            parent_item.addChild(child_item)
            parent_item.setExpanded(True)
        self.chapter_list.blockSignals(False)

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
            item = QListWidgetItem(f"{index}. {question.question}")
            self.question_list.addItem(item)

        self.question_list.blockSignals(False)
        self.bank.selected_chapter = chapter.title
        self._update_status_labels()

        if chapter.questions:
            self.question_list.setCurrentRow(0)
        elif not self._is_long_quiz():
            self.answer_header_label.setText(f"Answer Board - {chapter.title}")
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
            self.answer_header_label.setText("Answer Board")
            return

        self.answer_header_label.setText(f"Answer Board - {chapter.title}")

        if not chapter.questions:
            empty_label = QLabel(
                f"{chapter.title}\n\nAdd a question to begin this chapter.",
                self.answer_container,
            )
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setWordWrap(True)
            self.answer_cards_layout.addWidget(empty_label)
            return

        for index, question in enumerate(chapter.questions, start=1):
            card = QuestionCardWidget(
                chapter.title,
                index,
                question,
                reveal_answers=True,
            )
            self.answer_cards.append(card)
            self.answer_cards_layout.addWidget(card)

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
                message = "Choose chapters to include in the long quiz."
            else:
                message = (
                    "Choose your chapters, set a question count, then click Generate Test "
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
            self.question_list.clear()
            self._clear_layout(self.answer_cards_layout)
            self.answer_header_label.setText("Generated Test" if self._is_long_quiz() else "Answer Board")
            self._reset_review_state()
            self._refresh_branch_tree()
            self._save_to_storage()
            self._update_status_labels()
            self._update_long_quiz_controls()
            return

        self.bank.selected_chapter = chapter.title
        self._refresh_questions()
        self._refresh_answer_cards()
        self._sync_branch_tree_selection()
        self._save_to_storage()
        self._update_long_quiz_controls()

    def _on_question_changed(self, row: int):
        if self._is_long_quiz():
            return
        if row < 0 or row >= len(self.answer_cards):
            return

        card = self.answer_cards[row]
        self.answer_scroll.ensureWidgetVisible(card)

    def _on_branch_toggle_toggled(self, checked: bool):
        self._update_branch_toggle()

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

    def _on_long_quiz_count_changed(self, value: int):
        if not self._is_long_quiz():
            return

        available_count = self._long_quiz_available_question_count()
        clamped_value = min(max(0, value), available_count)
        if clamped_value != value and self.long_quiz_question_count_spinbox is not None:
            self.long_quiz_question_count_spinbox.blockSignals(True)
            self.long_quiz_question_count_spinbox.setValue(clamped_value)
            self.long_quiz_question_count_spinbox.blockSignals(False)

        if clamped_value == self.long_quiz_requested_count:
            return

        self.long_quiz_requested_count = clamped_value
        self.long_quiz_generated_refs = []
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
            if card.selected_choice >= 0:
                answered += 1
            is_correct = card.selected_choice == card.question.answer_index
            if is_correct:
                correct += 1
            card.reveal_review(is_correct)
            
            # Build question result for assessment
            user_answer = (
                card.question.choices[card.selected_choice]
                if card.selected_choice >= 0
                else None
            )
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

    def _canonical_chapter_title(self, title: str) -> str | None:
        normalized = title.strip().lower()
        for chapter in self.bank.chapters:
            if chapter.title.lower() == normalized:
                return chapter.title
        return None

    def _default_long_quiz_chapter_selection(self) -> list[str]:
        available_titles = [chapter.title for chapter in self._available_long_quiz_chapters()]
        if not available_titles:
            return []

        selected_chapter = self._selected_chapter()
        if selected_chapter is not None and selected_chapter.questions:
            return [selected_chapter.title]

        if self.bank.selected_chapter:
            canonical = self._canonical_chapter_title(self.bank.selected_chapter)
            if canonical is not None:
                for chapter in self._available_long_quiz_chapters():
                    if chapter.title == canonical:
                        return [canonical]

        return [available_titles[0]]

    def _reconcile_long_quiz_state(self) -> bool:
        if not self._is_long_quiz():
            return False

        changed = False
        available_chapters = self._available_long_quiz_chapters()
        available_by_key = {chapter.title.lower(): chapter.title for chapter in available_chapters}

        selected_titles: list[str] = []
        seen_keys: set[str] = set()
        for title in self.long_quiz_selected_chapters:
            key = title.strip().lower()
            canonical = available_by_key.get(key)
            if canonical is None or key in seen_keys:
                continue
            seen_keys.add(key)
            selected_titles.append(canonical)

        if not selected_titles and available_chapters:
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
        selected_keys = {title.lower() for title in self.long_quiz_selected_chapters}
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
        selected_keys = {title.lower() for title in selected_titles}
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
            counts[chapter_title] = counts.get(chapter_title, 0) + 1
        return [(title, counts.get(title, 0)) for title in self.long_quiz_selected_chapters]

    def _long_quiz_summary_text(self) -> str:
        if self.subject_name is None:
            return "Select a subject to configure a shuffled long quiz."

        available_chapters = self._available_long_quiz_chapters()
        if not available_chapters:
            return "Add questions to one or more chapters to enable long-quiz generation."

        selected_count = len(self.long_quiz_selected_chapters)
        available_count = self._long_quiz_available_question_count()
        generated_items = self._generated_long_quiz_items() or []

        if not generated_items:
            return (
                f"Selected chapters: {selected_count} | "
                f"Question pool: {available_count} | "
                f"Requested: {self.long_quiz_requested_count} | "
                "Generate a shuffled test to preview coverage."
            )

        coverage = ", ".join(
            f"{chapter_title} ({count})"
            for chapter_title, count in self._long_quiz_generated_coverage(generated_items)
        )
        return (
            f"Generated {len(generated_items)} shuffled question"
            f"{'s' if len(generated_items) != 1 else ''} | Coverage: {coverage}"
        )

    def _update_long_quiz_controls(self):
        if not self._is_long_quiz():
            return
        if self.long_quiz_summary_label is not None:
            self.long_quiz_summary_label.setText(self._long_quiz_summary_text())

        available_chapters = self._available_long_quiz_chapters()
        available_count = self._long_quiz_available_question_count()
        has_subject = self.subject_name is not None

        if self.long_quiz_choose_chapters_button is not None:
            self.long_quiz_choose_chapters_button.setEnabled(has_subject and bool(available_chapters))

        if self.long_quiz_question_count_spinbox is not None:
            self.long_quiz_question_count_spinbox.blockSignals(True)
            self.long_quiz_question_count_spinbox.setMaximum(max(0, available_count))
            self.long_quiz_question_count_spinbox.setValue(min(self.long_quiz_requested_count, available_count))
            self.long_quiz_question_count_spinbox.setEnabled(has_subject and available_count > 0)
            self.long_quiz_question_count_spinbox.blockSignals(False)

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

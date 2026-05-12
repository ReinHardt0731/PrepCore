import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QTreeWidget

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from app.main_window import MainWindow
from modules.task_list.outline_tab import NotebookTabController
from modules.task_list.quiz_tab import ChapterQuizTabController, QuizBank, QuizChapter


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def test_subject_leaf_paths_round_trip_with_sub_subchapters():
    window = MainWindow.__new__(MainWindow)
    leaf_paths = [
        "Chapter 1",
        "Chapter 1 / Sub 1",
        "Chapter 1 / Sub 1 / Detail A",
        "Chapter 2",
    ]

    subject = window._subject_from_leaf_paths("Biology", leaf_paths)

    assert [chapter.title for chapter in subject.chapters] == ["Chapter 1", "Chapter 2"]
    assert [chapter.title for chapter in subject.chapters[0].subchapters] == ["Sub 1"]
    assert [chapter.title for chapter in subject.chapters[0].subchapters[0].subchapters] == ["Detail A"]
    assert window._subject_leaf_paths(subject) == leaf_paths


def test_load_subject_records_reads_nested_subchapters():
    window = MainWindow.__new__(MainWindow)
    raw_subjects = [
        {
            "name": "Physics",
            "chapters": [
                {
                    "title": "Mechanics",
                    "subchapters": [
                        {
                            "title": "Kinematics",
                            "subchapters": [{"title": "Vectors"}],
                        }
                    ],
                }
            ],
        }
    ]

    subjects = window._load_subject_records(raw_subjects, backup_quiz_banks=None, derive_from_storage=False)

    assert len(subjects) == 1
    assert window._subject_leaf_paths(subjects[0]) == [
        "Mechanics",
        "Mechanics / Kinematics",
        "Mechanics / Kinematics / Vectors",
    ]


def test_outline_tree_renders_deep_leaf_paths():
    _app()
    controller = NotebookTabController.__new__(NotebookTabController)
    controller.chapter_list = QTreeWidget()
    controller.chapter_status_label = QLabel()
    controller.chapter_title_label = QLabel()
    controller.chapter_titles = ["Root / Branch / Leaf"]
    controller.current_chapter = None

    controller._refresh_chapter_tree()

    root = controller.chapter_list.topLevelItem(0)
    assert root.text(0) == "Root"
    assert root.child(0).text(0) == "Branch"
    assert root.child(0).child(0).text(0) == "Leaf"


def test_quiz_tree_renders_deep_leaf_paths():
    _app()
    controller = ChapterQuizTabController.__new__(ChapterQuizTabController)
    controller.chapter_list = QTreeWidget()
    controller.bank = QuizBank(
        quiz_type="short_quiz",
        chapters=[QuizChapter(title="Root / Branch / Leaf")],
    )

    controller._refresh_chapter_tree()

    root = controller.chapter_list.topLevelItem(0)
    assert root.text(0) == "Root"
    assert root.child(0).text(0) == "Branch"
    assert root.child(0).child(0).text(0) == "Leaf"

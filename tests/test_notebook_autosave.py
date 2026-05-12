import json
import shutil
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.task_list.outline_tab import NotebookTabController


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def test_notebook_edits_are_debounced_until_flush():
    app = _app()
    storage_root = ROOT / "_tmp_notebook_autosave_test"
    if storage_root.exists():
        shutil.rmtree(storage_root)

    page = QWidget()
    try:
        controller = NotebookTabController(page)
        controller.set_storage_root(storage_root)
        controller.set_subject_structure("Autosave Subject", ["Chapter 1"])

        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        app.processEvents()

        notebook_path = storage_root / "autosave_subject.json"
        assert notebook_path.exists()

        with notebook_path.open("r", encoding="utf-8") as handle:
            before_edit = json.load(handle)

        controller.editor.setPlainText("Hello from the editor")
        app.processEvents()

        with notebook_path.open("r", encoding="utf-8") as handle:
            while_typing = json.load(handle)

        assert while_typing == before_edit
        assert controller._editor_state_dirty is True

        controller._flush_storage_save()

        with notebook_path.open("r", encoding="utf-8") as handle:
            after_flush = json.load(handle)

        assert "Hello from the editor" in after_flush["notes"]["Chapter 1"]
        assert controller._editor_state_dirty is False
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)

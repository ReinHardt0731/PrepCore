import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QGraphicsScene, QApplication, QWidget

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.task_list.outline_tab import (
    DiagramSettings,
    DiagramTextStyle,
    NotebookCellMetadata,
    NotebookTabController,
    TimelineDiagramStyle,
    TreeNodeGraphicsItem,
    _decode_notebook_cell_metadata,
    _encode_notebook_cell_metadata,
    _populate_diagram_scene,
    _render_code_output_html,
    _render_diagram_html,
    _render_markdown_cell_html,
)


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def _build_controller(storage_dir_name: str):
    page = QWidget()
    storage_root = ROOT / storage_dir_name
    shutil.rmtree(storage_root, ignore_errors=True)
    controller = NotebookTabController(page)
    controller.set_storage_root(storage_root)
    return controller, storage_root


def _insert_diagram_cell(controller: NotebookTabController, cell_type: str, source: str):
    settings = DiagramSettings()
    metadata = NotebookCellMetadata(
        cell_id=f"{cell_type}-test-cell",
        cell_type=cell_type,
        source=source,
        rendered_html=_render_diagram_html(cell_type, source, settings),
        is_editing=False,
        diagram_settings=settings,
    )
    table = controller._insert_notebook_cell_table(metadata)
    controller._active_cell_table = table
    controller._set_active_cell_metadata(metadata)
    return metadata


def test_notebook_cell_metadata_round_trip():
    metadata = NotebookCellMetadata(
        cell_id="cell-1",
        cell_type="markdown",
        source="# Title",
        rendered_html="<h1>Title</h1>",
        is_editing=True,
    )
    encoded = _encode_notebook_cell_metadata(metadata)
    decoded = _decode_notebook_cell_metadata(encoded)
    assert decoded == metadata


def test_diagram_metadata_round_trip_preserves_settings():
    metadata = NotebookCellMetadata(
        cell_id="timeline-1",
        cell_type="timeline",
        source="Start | first",
        rendered_html="<img>",
        is_editing=False,
        diagram_settings=DiagramSettings(
            display_height_px=208,
            timeline_style=TimelineDiagramStyle(
                title_style=DiagramTextStyle(font_size_pt=14, bold=True, color="#ffffff"),
                detail_style=DiagramTextStyle(font_size_pt=11, color="#88ccff"),
                row_gap_px=36,
                column_gap_px=42,
            ),
        ),
    )
    decoded = _decode_notebook_cell_metadata(_encode_notebook_cell_metadata(metadata))
    assert decoded == metadata


def test_version_1_diagram_metadata_decodes_with_default_settings():
    import base64
    import json

    payload = {
        "version": 1,
        "cell_id": "tree-1",
        "cell_type": "tree",
        "source": "Root\n  Child",
        "rendered_html": "<img>",
        "is_editing": False,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    decoded = _decode_notebook_cell_metadata(f"nbcell:{encoded}")

    assert decoded is not None
    assert decoded.diagram_settings is not None
    assert decoded.diagram_settings.display_height_px is None
    assert decoded.diagram_settings.tree_layout.auto_layout_direction == "vertical"


def test_markdown_cell_renders_html():
    _app()
    html = _render_markdown_cell_html("# Hello")
    assert "Hello" in html


def test_code_cell_runs_python():
    html = _render_code_output_html("print('hello')")
    assert "hello" in html


def test_diagram_cell_renders_image():
    _app()
    html = _render_diagram_html("timeline", "Start | first\nEnd | done")
    assert "data:image/png;base64" in html


def test_timeline_scene_renders_vertically_with_title_left_and_detail_right():
    _app()
    scene = QGraphicsScene()
    settings = DiagramSettings(
        timeline_style=TimelineDiagramStyle(
            title_style=DiagramTextStyle(font_size_pt=16, bold=True, color="#ffffff"),
            detail_style=DiagramTextStyle(font_size_pt=11, color="#99ccff"),
            row_gap_px=32,
            column_gap_px=36,
        )
    )
    _populate_diagram_scene(scene, "timeline", "Start | first\nEnd | done", settings)

    text_items = {item.toPlainText(): item for item in scene.items() if hasattr(item, "toPlainText")}
    assert text_items["Start"].pos().y() < text_items["End"].pos().y()
    assert text_items["first"].pos().x() > text_items["Start"].pos().x()
    assert text_items["Start"].font().pointSize() == 16


def test_tree_scene_wraps_long_labels_and_expands_node_boxes():
    _app()
    scene = QGraphicsScene()
    source = "Root node with a very long label that should wrap across multiple lines\n  Child"
    _populate_diagram_scene(scene, "tree", source, DiagramSettings(), interactive=True)

    tree_items = [item for item in scene.items() if isinstance(item, TreeNodeGraphicsItem)]
    assert tree_items
    long_item = next(item for item in tree_items if "very long label" in item.label)
    assert long_item.boundingRect().width() > 120
    assert long_item.boundingRect().height() > 48


def test_notebook_cell_context_is_available_immediately_after_insert():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_cells_context")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])

        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        controller._create_notebook_cell("markdown", initial_source="# Hello")
        app.processEvents()

        cursor = controller.editor.textCursor()
        assert cursor.currentTable() is not None

        context = controller._current_notebook_cell_context()
        assert context is not None
        _table, metadata = context
        assert metadata.cell_type == "markdown"
        assert metadata.source == "# Hello"
        assert metadata.is_editing is True
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_running_notebook_cell_replaces_gutter_markup_without_bloating_html():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_cells_run")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])

        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        controller._create_notebook_cell("markdown", initial_source="# Hello\n\nworld")
        app.processEvents()

        context = controller._current_notebook_cell_context()
        assert context is not None
        controller._run_notebook_cell(*context)
        app.processEvents()

        html = controller.editor.toHtml()
        updated_context = controller._current_notebook_cell_context()

        assert updated_context is not None
        assert updated_context[1].is_editing is False
        assert "nbcellaction:" not in html
        assert html.count('href="nbcell:') == 1
        assert len(html) < 10000
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_active_timeline_cell_shows_live_preview_panel():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_timeline_preview")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])

        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        _insert_diagram_cell(controller, "timeline", "Start | first\nEnd | done")
        app.processEvents()
        controller._update_context_action_bar()

        assert controller._context_cell_metadata is not None
        assert controller._context_cell_metadata.cell_type == "timeline"
        assert controller.diagram_preview_panel.isHidden() is False
        assert controller.diagram_preview_title.text() == "Timeline Preview"
        assert controller.diagram_preview_scene.items()
        assert controller.context_run_button.text() == "Fit"
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_diagram_preview_hides_when_cursor_leaves_active_diagram_cell():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_preview_hide")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])

        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        _insert_diagram_cell(controller, "timeline", "Start | first\nEnd | done")
        app.processEvents()
        controller._update_context_action_bar()
        assert controller.diagram_preview_panel.isHidden() is False

        cursor = controller.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        controller.editor.setTextCursor(cursor)
        app.processEvents()
        controller._update_context_action_bar()

        assert controller._context_cell_metadata is None
        assert controller.diagram_preview_panel.isHidden() is True
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_space_and_shift_space_persist_diagram_preview_height():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_preview_height")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])
        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        _insert_diagram_cell(controller, "timeline", "Start | first\nEnd | done")
        app.processEvents()
        controller._update_context_action_bar()

        initial_height = controller.diagram_preview_panel.height()
        QApplication.sendEvent(
            controller.editor,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier),
        )
        app.processEvents()
        increased_height = controller.diagram_preview_panel.height()

        QApplication.sendEvent(
            controller.editor,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.ShiftModifier),
        )
        app.processEvents()
        decreased_height = controller.diagram_preview_panel.height()

        assert increased_height >= initial_height + 20
        assert decreased_height <= increased_height - 20
        assert controller._active_cell_metadata is not None
        assert controller._active_cell_metadata.diagram_settings is not None
        assert controller._active_cell_metadata.diagram_settings.display_height_px == decreased_height
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_tree_node_move_persists_in_metadata_and_after_reselection():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_tree_positions")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])
        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        _insert_diagram_cell(controller, "tree", "Root\n  Child A\n  Child B")
        app.processEvents()
        controller._update_context_action_bar()
        table = controller._active_cell_table

        tree_items = [item for item in controller.diagram_preview_scene.items() if isinstance(item, TreeNodeGraphicsItem)]
        root_item = next(item for item in tree_items if item.path_id == "0")
        original_pos = root_item.pos()
        root_item.setPos(QPointF(original_pos.x() + 32, original_pos.y() + 18))
        controller._commit_pending_diagram_settings()
        app.processEvents()

        settings = controller._active_cell_metadata.diagram_settings
        assert settings is not None
        assert settings.tree_layout.node_positions["0"]["x"] >= original_pos.x() + 30

        cursor = controller.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        controller.editor.setTextCursor(cursor)
        app.processEvents()
        controller._update_context_action_bar()

        controller.editor.setTextCursor(controller._table_cell_cursor_at_end(table, 0, 1))
        app.processEvents()
        controller._update_context_action_bar()

        assert controller._active_cell_metadata is not None
        assert "0" in controller._active_cell_metadata.diagram_settings.tree_layout.node_positions
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)


def test_context_action_bar_stays_inside_gutter():
    app = _app()
    controller, storage_root = _build_controller("_tmp_notebook_action_bar")
    try:
        controller.set_subject_structure("Notebook Subject", ["Chapter 1"])
        first_item = controller.chapter_list.topLevelItem(0)
        controller.chapter_list.setCurrentItem(first_item)
        _insert_diagram_cell(controller, "timeline", "Start | first\nEnd | done")
        app.processEvents()
        controller._update_context_action_bar()

        table = controller._active_cell_table
        gutter_cursor = table.cellAt(0, 0).firstCursorPosition()
        gutter_left = controller.editor.cursorRect(gutter_cursor).left()
        assert controller.context_action_bar.geometry().left() >= gutter_left
        assert controller.context_action_bar.geometry().right() <= gutter_left + 54
    finally:
        controller._autosave_timer.stop()
        controller.subject_name = None
        controller.current_chapter = None
        controller.page.deleteLater()
        app.processEvents()
        shutil.rmtree(storage_root, ignore_errors=True)

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QSize, QStandardPaths, Qt
from PySide6.QtGui import QFont, QIcon, QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app_theme import apply_midnight_blue_theme
from board_exam import Ui_MainWindow
from gant_chart import TimeOrganizerController
from subject_emoji import SubjectEmojiManager, get_subject_display_name
from subject_emoji_dialog import SubjectEmojiDialog
from tree_font_utils import apply_hierarchical_font_to_item
from task_list import (
    AssessmentTabController,
    LongQuizTabController,
    NotebookTabController,
    ShortQuizTabController,
    load_quiz_bank_from_path,
)


ROLE_BASE = int(Qt.ItemDataRole.UserRole)
ITEM_KIND_ROLE = ROLE_BASE
SUBJECT_NAME_ROLE = ROLE_BASE + 1
CHAPTER_NAME_ROLE = ROLE_BASE + 2
PARENT_CHAPTER_ROLE = ROLE_BASE + 3
LEAF_PATH_ROLE = ROLE_BASE + 4
APP_NAME = "PrepCore"
APP_ICON_FILENAME = "icon.png"  # Taskbar icon
APP_LOGO_FILENAME = "Logo_rounded.png"  # App window icon (rounded corners)


@dataclass
class ChapterRecord:
    title: str
    subchapters: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "subchapters": self.subchapters,
        }


@dataclass
class SubjectRecord:
    name: str
    chapters: list[ChapterRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


class MainWindow(QMainWindow):
    APP_STATE_VERSION = 1
    PREFERENCES_VERSION = 1

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.scrollArea.hide()
        self.ui.Subject.setFloating(False)
        self.ui.Subject.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setDockNestingEnabled(True)

        # Application bundle root (where bundled data is stored)
        self.bundle_root = Path(__file__).resolve().parent
        
        # User data directory (persistent across sessions) - stored in user's AppData
        self.user_data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.app_state_dir = self.user_data_dir / APP_NAME
        self.bootstrap_preferences_path = self.app_state_dir / "preferences.json"
        
        # Initialize emoji manager for subject names
        self.emoji_manager = SubjectEmojiManager(self.app_state_dir)
        
        # Legacy paths for migration
        self.legacy_subject_store_path = self.bundle_root / "subjects.json"
        self.legacy_app_state_path = self.bundle_root / "app_state.json"
        
        # User data paths
        self.subject_store_path = self.app_state_dir / "subjects.json"
        self.app_state_path = self.app_state_dir / "window_state.json"
        self.preferences_path = self.app_state_dir / "preferences.json"
        
        # App assets (stored in bundle)
        self.app_icon_path = self.bundle_root / APP_ICON_FILENAME
        self.app_logo_path = self.bundle_root / APP_LOGO_FILENAME
        self.subjects: list[SubjectRecord] = []
        self.selected_subject: str | None = None
        
        # Check if this is first run BEFORE loading preferences
        # (since _load_preferences will create the file if it doesn't exist)
        is_first_run = not self.bootstrap_preferences_path.exists()
        
        if is_first_run:
            # First run - show setup wizard to configure data path
            self._show_first_time_setup()
        
        # Now load preferences (which will apply custom path if set)
        self.preferences = self._load_preferences()
        self.is_first_run = self._detect_first_run()

        if self.app_icon_path.exists():
            self.setWindowIcon(QIcon(str(self.app_icon_path)))

        self.time_tab_base_titles = [
            self.ui.time_organizer.tabText(index) for index in range(self.ui.time_organizer.count())
        ]

        self._build_subject_panel()
        self._build_task_tabs()
        self._build_time_pages()
        self._ensure_data_storage_dirs()
        self._migrate_legacy_storage()
        self._configure_controller_storage_roots()
        self._load_subjects()
        self._wire_actions()
        self._restore_app_state()
        self._refresh_subject_views()

    def _ensure_app_state_dir(self):
        self.app_state_dir.mkdir(parents=True, exist_ok=True)

    def _quiz_banks_root(self) -> Path:
        return self.app_state_dir / "quiz_banks"

    def _notebooks_root(self) -> Path:
        return self.app_state_dir / "notebooks"

    def _time_organizer_root(self) -> Path:
        return self.app_state_dir / "gant_chart"

    def _ensure_data_storage_dirs(self):
        self._ensure_app_state_dir()
        self._quiz_banks_root().mkdir(parents=True, exist_ok=True)
        self._notebooks_root().mkdir(parents=True, exist_ok=True)
        self._time_organizer_root().mkdir(parents=True, exist_ok=True)

    def _copy_missing_storage(self, source_path: Path, destination_path: Path):
        if not source_path.exists():
            return

        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            for child in source_path.iterdir():
                self._copy_missing_storage(child, destination_path / child.name)
            return

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if not destination_path.exists():
            shutil.copy2(source_path, destination_path)

    def _migrate_legacy_storage(self):
        legacy_roots = (
            (self.bundle_root / "quiz_banks", self._quiz_banks_root()),
            (self.bundle_root / "notebooks", self._notebooks_root()),
            (self.bundle_root / "gant_chart", self._time_organizer_root()),
        )
        for source_path, destination_path in legacy_roots:
            try:
                self._copy_missing_storage(source_path, destination_path)
            except OSError:
                continue

    def _configure_controller_storage_roots(self):
        self._ensure_data_storage_dirs()
        if hasattr(self, "notebook_tab"):
            self.notebook_tab.set_storage_root(self._notebooks_root())
        if hasattr(self, "short_quiz_tab"):
            self.short_quiz_tab.set_storage_root(self._quiz_banks_root())
        if hasattr(self, "long_quiz_tab"):
            self.long_quiz_tab.set_storage_root(self._quiz_banks_root())
        if hasattr(self, "time_organizer_tab"):
            self.time_organizer_tab.set_storage_root(self._time_organizer_root())

    def _read_json_payload(self, path: Path):
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def _load_json_payload_with_legacy_fallback(self, primary_path: Path, legacy_path: Path | None = None):
        payload = self._read_json_payload(primary_path) if primary_path.exists() else None
        if payload is not None:
            return payload, primary_path

        if legacy_path is not None and legacy_path.exists():
            legacy_payload = self._read_json_payload(legacy_path)
            if legacy_payload is not None:
                return legacy_payload, legacy_path

        return None, None

    def _default_preferences(self) -> dict[str, object]:
        return {
            "schema_version": self.PREFERENCES_VERSION,
            "theme": "midnight_blue",
            "app_state_dir": self.app_state_dir.name,
            "app_name": APP_NAME,
            "app_icon": APP_ICON_FILENAME,
            "app_logo": APP_LOGO_FILENAME,
            "custom_data_path": None,
            "timer_follows_subject_selection": True,
            "planner_follows_subject_selection": True,
            "subject_navigation_style": "tree",
        }

    def _load_preferences(self) -> dict[str, object]:
        self._ensure_app_state_dir()
        payload = self._read_json_payload(self.preferences_path)
        if isinstance(payload, dict):
            merged_payload = {
                **self._default_preferences(),
                **payload,
            }
            if merged_payload != payload:
                try:
                    with self.preferences_path.open("w", encoding="utf-8") as handle:
                        json.dump(merged_payload, handle, indent=2)
                except OSError:
                    pass
            
            # Apply custom data path if set
            if merged_payload.get("custom_data_path"):
                custom_path = Path(merged_payload["custom_data_path"])
                if custom_path.exists() and custom_path.is_dir():
                    # Update app_state_dir to use custom path
                    self.app_state_dir = custom_path
                    self.subject_store_path = self.app_state_dir / "subjects.json"
                    self.app_state_path = self.app_state_dir / "window_state.json"
                    self.preferences_path = self.app_state_dir / "preferences.json"
                    self._ensure_data_storage_dirs()
            
            return merged_payload

        payload = self._default_preferences()
        try:
            with self.preferences_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError:
            pass
        return payload

    def _wire_actions(self):
        self.ui.actionNew.triggered.connect(self.prompt_add_subject)
        self.ui.actionImport.triggered.connect(self.import_full_app_backup)
        self.ui.actionPreference.triggered.connect(self.show_preferences_dialog)

    def _write_preferences_file(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.preferences, handle, indent=2)

    def _save_preferences(self):
        """Save current preferences to file."""
        self._ensure_app_state_dir()
        try:
            self._write_preferences_file(self.preferences_path)
            if self.bootstrap_preferences_path != self.preferences_path:
                self._write_preferences_file(self.bootstrap_preferences_path)
        except OSError as e:
            QMessageBox.warning(self, "Warning", f"Could not save preferences: {e}")

    def _set_custom_data_path(self, new_path: str) -> bool:
        """Change the data storage path. Returns True if successful."""
        path = Path(new_path)
        previous_app_state_dir = self.app_state_dir
        
        # Validate the path exists or can be created
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Cannot create directory:\n{e}")
                return False
        
        # Test write permission
        test_file = path / ".prepcore_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Path is not writable:\n{e}")
            return False
        
        # Save preference
        self.preferences["custom_data_path"] = str(path)

        # Update internal paths
        self.app_state_dir = path
        self.subject_store_path = self.app_state_dir / "subjects.json"
        self.app_state_path = self.app_state_dir / "window_state.json"
        self.preferences_path = self.app_state_dir / "preferences.json"
        self._ensure_data_storage_dirs()
        for folder_name in ("quiz_banks", "notebooks", "gant_chart"):
            try:
                self._copy_missing_storage(
                    previous_app_state_dir / folder_name,
                    self.app_state_dir / folder_name,
                )
            except OSError:
                continue
        self._migrate_legacy_storage()
        self._configure_controller_storage_roots()
        self._save_subjects()
        self._save_app_state()
        self._save_preferences()
        
        QMessageBox.information(
            self, 
            "Success", 
            f"Data path changed to:\n{path}\n\nThe app will use this location for all saved data."
        )
        return True

    def _show_change_data_path_dialog(self):
        """Show dialog to change data storage path."""
        current = self.preferences.get("custom_data_path") or str(self.app_state_dir)
        
        new_path = QFileDialog.getExistingDirectory(
            self,
            "Select Data Storage Location",
            current,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if new_path and new_path != current:
            self._set_custom_data_path(new_path)

    def _open_data_folder(self):
        """Open the data folder in the file explorer."""
        import subprocess
        import os
        
        try:
            if sys.platform == "win32":
                os.startfile(str(self.app_state_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.app_state_dir)])
            else:  # Linux
                subprocess.Popen(["xdg-open", str(self.app_state_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder:\n{e}")

    def _build_subject_panel(self):
        container = self.ui.subject_list
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.subject_panel_layout = layout

        self.subject_header_row = QWidget(container)
        header_layout = QHBoxLayout(self.subject_header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        subject_header_label = QLabel("Subjects", self.subject_header_row)
        subject_header_label.setStyleSheet("color: #edf4ff; font-size: 13pt; font-weight: 700;")
        header_layout.addWidget(subject_header_label)
        header_layout.addStretch(1)

        self.subject_vertical_rail_width = 92
        self.subject_vertical_button_size = 64
        self.subject_vertical_emoji_font_size =25
        self.subject_vertical_compact_width = 94
        self.subject_vertical_compact_threshold = 220
        self._subject_vertical_compact_active = False

        self.subject_navigation_toggle = QToolButton(self.subject_header_row)
        self.subject_navigation_toggle.setCheckable(True)
        self.subject_navigation_toggle.setStyleSheet(
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
        self.subject_navigation_toggle.toggled.connect(self._on_subject_navigation_mode_toggled)
        self.subject_navigation_toggle.hide()
        layout.addWidget(self.subject_header_row, 0)
        self.ui.Subject.setMinimumWidth(self.subject_vertical_compact_width)

        self.subject_tree = QTreeWidget(container)
        self.subject_tree.setHeaderHidden(True)
        self.subject_tree.setRootIsDecorated(True)
        self.subject_tree.setIndentation(20)
        self.subject_tree.setUniformRowHeights(True)
        self.subject_tree.setExpandsOnDoubleClick(True)
        self.subject_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Apply simple styling with default expand/collapse arrows
        self.subject_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0f1728;
                color: #ffffff;
                border: 1px solid #22314b;
                border-radius: 8px;
                selection-background-color: #2f74ff;
                outline: none;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background-color: #1c3d6b;
                color: #ffffff;
            }
        """)
        
        # Set palette for visibility
        palette = self.subject_tree.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor("#0f1728"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#2f74ff"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.subject_tree.setPalette(palette)
        
        self.subject_tree.customContextMenuRequested.connect(self.show_subject_context_menu)
        self.subject_tree.itemSelectionChanged.connect(self.on_subject_selection_changed)
        layout.addWidget(self.subject_tree, 1)

        self.subject_server_panel = QWidget(container)
        server_panel_layout = QHBoxLayout(self.subject_server_panel)
        server_panel_layout.setContentsMargins(0, 0, 0, 0)
        server_panel_layout.setSpacing(10)

        self.subject_vertical_rail_panel = QWidget(self.subject_server_panel)
        rail_layout = QVBoxLayout(self.subject_vertical_rail_panel)
        rail_layout.setContentsMargins(0, 0, 0, 0)
        rail_layout.setSpacing(8)

        self.subject_server_list = QListWidget(self.subject_vertical_rail_panel)
        self.subject_server_list.setFixedWidth(self.subject_vertical_rail_width)
        self.subject_server_list.setSpacing(6)
        self.subject_server_list.setAlternatingRowColors(False)
        self.subject_server_list.setViewMode(QListView.ViewMode.IconMode)
        self.subject_server_list.setFlow(QListView.Flow.TopToBottom)
        self.subject_server_list.setMovement(QListView.Movement.Static)
        self.subject_server_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.subject_server_list.setWrapping(False)
        self.subject_server_list.setUniformItemSizes(True)
        self.subject_server_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.subject_server_list.setGridSize(self._subject_vertical_slot_size())
        self.subject_server_list.setFont(self._subject_vertical_emoji_font())
        self.subject_server_list.setStyleSheet(
            """
            QListWidget {
                background-color: #0f1728;
                border: 1px solid #22314b;
                border-radius: 14px;
                padding: 8px 8px;
            }
            QListWidget::item {
                padding: 0px;
                margin: 0px 0px 2px 0px;
                border-radius: 14px;
                color: #edf4ff;
            }
            QListWidget::item:selected {
                background-color: #173158;
                border: 1px solid #2f74ff;
            }
            QListWidget::item:hover {
                background-color: #132136;
            }
            """
        )
        self._apply_subject_vertical_emoji_styling()
        self.subject_server_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subject_server_list.customContextMenuRequested.connect(
            self._show_subject_server_context_menu
        )
        self.subject_server_list.itemSelectionChanged.connect(
            self._on_subject_server_selection_changed
        )
        self.subject_server_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rail_layout.addWidget(self.subject_server_list, 1)

        self.subject_vertical_add_button = QToolButton(self.subject_vertical_rail_panel)
        self.subject_vertical_add_button.setText("+")
        self.subject_vertical_add_button.setFixedSize(self._subject_vertical_slot_size())
        self.subject_vertical_add_button.setStyleSheet(
            f"""
            QToolButton {{
                background-color: #132136;
                color: #edf4ff;
                border: 1px solid #23314a;
                border-radius: 14px;
                font-size: {max(22, self.subject_vertical_emoji_font_size)}px;
                font-weight: 700;
            }}
            QToolButton:hover {{
                background-color: #173158;
                border-color: #2f74ff;
            }}
            QToolButton:pressed {{
                background-color: #102545;
            }}
            """
        )
        self.subject_vertical_add_button.setToolTip("Add Subject")
        self.subject_vertical_add_button.clicked.connect(self.prompt_add_subject)
        rail_layout.addWidget(self.subject_vertical_add_button, 0, Qt.AlignmentFlag.AlignHCenter)
        server_panel_layout.addWidget(self.subject_vertical_rail_panel, 0)

        self.subject_vertical_chapter_panel = QWidget(self.subject_server_panel)
        chapter_panel_layout = QVBoxLayout(self.subject_vertical_chapter_panel)
        chapter_panel_layout.setContentsMargins(0, 0, 0, 0)
        chapter_panel_layout.setSpacing(8)

        self.subject_server_header_label = QLabel("Select a subject", self.subject_vertical_chapter_panel)
        self.subject_server_header_label.setStyleSheet(
            "color: #edf4ff; font-size: 12pt; font-weight: 700;"
        )
        chapter_panel_layout.addWidget(self.subject_server_header_label)

        self.subject_server_chapter_tree = QTreeWidget(self.subject_vertical_chapter_panel)
        self.subject_server_chapter_tree.setHeaderHidden(True)
        self.subject_server_chapter_tree.setRootIsDecorated(True)
        self.subject_server_chapter_tree.setIndentation(18)
        self.subject_server_chapter_tree.setUniformRowHeights(True)
        self.subject_server_chapter_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.subject_server_chapter_tree.setStyleSheet(
            """
            QTreeWidget {
                background-color: #0f1728;
                color: #edf4ff;
                border: 1px solid #22314b;
                border-radius: 14px;
                selection-background-color: #2f74ff;
                outline: none;
            }
            QTreeWidget::item {
                padding: 6px 8px;
                border-radius: 8px;
            }
            QTreeWidget::item:selected {
                background-color: #173158;
                color: #ffffff;
            }
            """
        )
        self.subject_server_chapter_tree.customContextMenuRequested.connect(
            self._show_subject_server_chapter_context_menu
        )
        self.subject_server_chapter_tree.itemSelectionChanged.connect(
            self._on_subject_server_chapter_selection_changed
        )
        chapter_panel_layout.addWidget(self.subject_server_chapter_tree, 1)
        server_panel_layout.addWidget(self.subject_vertical_chapter_panel, 1)
        layout.addWidget(self.subject_server_panel, 1)

        self.subject_add_row = QFrame(container)
        self.subject_add_row.setFrameShape(QFrame.Shape.NoFrame)
        add_layout = QHBoxLayout(self.subject_add_row)
        add_layout.setContentsMargins(0, 0, 0, 0)
        add_layout.setSpacing(6)

        self.subject_input = QLineEdit(self.subject_add_row)
        self.subject_input.setPlaceholderText("Add a subject")
        self.subject_input.returnPressed.connect(self.add_subject_from_input)
        add_layout.addWidget(self.subject_input, 1)

        self.add_subject_button = QPushButton("Add", self.subject_add_row)
        self.add_subject_button.clicked.connect(self.add_subject_from_input)
        add_layout.addWidget(self.add_subject_button)

        layout.addWidget(self.subject_add_row, 0)
        self.ui.Subject.installEventFilter(self)
        container.installEventFilter(self)
        self._apply_subject_navigation_mode()

    def _subject_navigation_style(self) -> str:
        style = str(self.preferences.get("subject_navigation_style", "tree")).strip().lower()
        return "vertical_widgets" if style in {"servers", "vertical_widgets"} else "tree"

    def _subject_vertical_slot_size(self) -> QSize:
        return QSize(self.subject_vertical_button_size, self.subject_vertical_button_size)

    def _subject_vertical_emoji_font(self) -> QFont:
        font = QFont(self.subject_server_list.font())
        font.setPixelSize(self.subject_vertical_emoji_font_size)
        font.setWeight(QFont.Weight.DemiBold)
        return font

    def _apply_subject_vertical_emoji_styling(self):
        if not hasattr(self, "subject_server_list"):
            return
        self.subject_server_list.setFont(self._subject_vertical_emoji_font())
        for index in range(self.subject_server_list.count()):
            item = self.subject_server_list.item(index)
            if item is not None:
                item.setFont(self._subject_vertical_emoji_font())

    def _apply_subject_navigation_mode(self):
        vertical_widgets_mode = self._subject_navigation_style() == "vertical_widgets"
        if hasattr(self, "subject_navigation_toggle"):
            self.subject_navigation_toggle.blockSignals(True)
            self.subject_navigation_toggle.setChecked(vertical_widgets_mode)
            self.subject_navigation_toggle.setText(
                "Vertical Widgets" if vertical_widgets_mode else "Tree"
            )
            self.subject_navigation_toggle.setToolTip(
                "Toggle between the classic subject tree and the vertical-widgets subject rail."
            )
            self.subject_navigation_toggle.blockSignals(False)
        if hasattr(self, "subject_tree"):
            self.subject_tree.setVisible(not vertical_widgets_mode)
        if hasattr(self, "subject_server_panel"):
            self.subject_server_panel.setVisible(vertical_widgets_mode)
        self._refresh_subject_server_chapters()
        self._update_subject_vertical_widgets_layout()

    def _on_subject_navigation_mode_toggled(self, checked: bool):
        self.preferences["subject_navigation_style"] = "vertical_widgets" if checked else "tree"
        self._save_preferences()
        self._apply_subject_navigation_mode()

    def _update_subject_vertical_widgets_layout(self):
        if not hasattr(self, "subject_vertical_chapter_panel"):
            return

        vertical_widgets_mode = self._subject_navigation_style() == "vertical_widgets"
        dock_width = self.ui.Subject.width() if hasattr(self, "ui") else 0
        compact_mode = vertical_widgets_mode and dock_width <= self.subject_vertical_compact_threshold

        if vertical_widgets_mode:
            if compact_mode != self._subject_vertical_compact_active:
                self._subject_vertical_compact_active = compact_mode
                if compact_mode:
                    self.resizeDocks(
                        [self.ui.Subject],
                        [self.subject_vertical_compact_width],
                        Qt.Orientation.Horizontal,
                    )

            self.subject_header_row.setVisible(not compact_mode)
            self.subject_add_row.setVisible(False)
            self.subject_vertical_chapter_panel.setVisible(not compact_mode)
            self.subject_server_header_label.setVisible(not compact_mode)
            self.subject_vertical_add_button.setVisible(True)
            self.subject_server_panel.layout().setSpacing(0 if compact_mode else 10)
            self.subject_server_panel.setMinimumWidth(self.subject_vertical_compact_width)
            self.subject_server_list.setFixedWidth(
                self.subject_vertical_compact_width - 16 if compact_mode else self.subject_vertical_rail_width
            )
            self.subject_vertical_rail_panel.setFixedWidth(
                self.subject_vertical_compact_width - 8 if compact_mode else self.subject_vertical_rail_width
            )
            self.subject_panel_layout.setContentsMargins(
                4 if compact_mode else 8,
                4 if compact_mode else 8,
                4 if compact_mode else 8,
                4 if compact_mode else 8,
            )
            self.subject_panel_layout.setSpacing(4 if compact_mode else 8)
        else:
            self._subject_vertical_compact_active = False
            self.subject_header_row.setVisible(True)
            self.subject_add_row.setVisible(True)
            self.subject_vertical_chapter_panel.setVisible(False)
            self.subject_server_header_label.setVisible(False)
            self.subject_vertical_add_button.setVisible(False)
            self.subject_server_panel.setMinimumWidth(0)
            self.subject_server_list.setFixedWidth(self.subject_vertical_rail_width)
            self.subject_vertical_rail_panel.setFixedWidth(self.subject_vertical_rail_width)
            self.subject_panel_layout.setContentsMargins(8, 8, 8, 8)
            self.subject_panel_layout.setSpacing(8)

    def eventFilter(self, watched, event):
        if watched in {self.ui.Subject, self.ui.subject_list} and event.type() == QEvent.Type.Resize:
            self._update_subject_vertical_widgets_layout()
        return super().eventFilter(watched, event)

    def _build_task_tabs(self):
        self.notebook_tab = NotebookTabController(self.ui.todo_list)
        self.short_quiz_tab = ShortQuizTabController(self.ui.short_quiz)
        self.long_quiz_tab = LongQuizTabController(self.ui.long_quiz)
        
        # Create assessment tab widget if it doesn't exist
        if not hasattr(self.ui, 'assessment'):
            self.ui.assessment = QWidget()
            self.ui.TaskTabs.addTab(self.ui.assessment, "Assessment")
        
        self.assessment_tab = AssessmentTabController(self.ui.assessment)
        self.long_quiz_tab.set_assessment_controller(self.assessment_tab)
        
        # Wire up cross-quiz synchronization
        self.short_quiz_tab.set_sister_controller(self.long_quiz_tab)
        self.long_quiz_tab.set_sister_controller(self.short_quiz_tab)
        
        notebook_index = self.ui.TaskTabs.indexOf(self.ui.todo_list)
        if notebook_index >= 0:
            self.ui.TaskTabs.setTabText(notebook_index, "Notebook")
        self.short_quiz_tab.set_subject_resolver(self.resolve_subject_for_quiz_import)
        self.long_quiz_tab.set_subject_resolver(self.resolve_subject_for_quiz_import)
        self._dock_task_tabs()
        self._sync_task_tabs()

    def _sync_task_tabs(self):
        chapter_titles = self._selected_subject_chapters()
        self.notebook_tab.set_subject_structure(self.selected_subject, chapter_titles)
        self.short_quiz_tab.set_subject(self.selected_subject)
        self.long_quiz_tab.set_subject(self.selected_subject)
        self.assessment_tab.set_subject(self.selected_subject)
        self.short_quiz_tab.set_subject_structure(self.selected_subject, chapter_titles)
        self.long_quiz_tab.set_subject_structure(self.selected_subject, chapter_titles)

    def _build_time_pages(self):
        # Create activity overview page
        activity_overview_page = QWidget()
        activity_overview_page.setObjectName("activity_overview")
        self.ui.time_organizer.addTab(activity_overview_page, "Activity Overview")
        
        self.time_organizer_tab = TimeOrganizerController(
            self.ui.time_organizer,
            self.ui.gant_chart,
            self.ui.calendar,
            self.ui.todo_list_2,
            activity_overview_page,
        )
        self.time_organizer_tab.set_long_quiz_timeout_handler(
            self.long_quiz_tab.auto_submit_long_quiz_on_timeout
        )
        self._dock_time_organizer()
        self._replace_empty_central_area()
        self.ui.time_organizer.setCurrentWidget(self.ui.gant_chart)
        todo_index = self.ui.time_organizer.indexOf(self.ui.todo_list_2)
        if todo_index >= 0:
            self.ui.time_organizer.setTabText(todo_index, "Todo List")
        self._sync_time_organizer()

    def _dock_task_tabs(self):
        self.task_tabs_dock = QDockWidget("Task Tabs", self)
        self.task_tabs_dock.setObjectName("TaskTabsDock")
        self.task_tabs_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.task_tabs_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.task_tabs_dock.setWidget(self.ui.TaskTabs)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.task_tabs_dock)
        self.task_tabs_dock.setFloating(False)

        toggle_action = self.task_tabs_dock.toggleViewAction()
        toggle_action.setText("Task Tabs")
        self.ui.menuView.addAction(toggle_action)

    def _dock_time_organizer(self):
        self.time_organizer_dock = QDockWidget("Time Organizer", self)
        self.time_organizer_dock.setObjectName("TimeOrganizerDock")
        self.time_organizer_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.time_organizer_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.time_organizer_dock.setWidget(self.ui.time_organizer)
        self.time_organizer_dock.setMinimumWidth(self.time_organizer_tab.TIMER_PANEL_MIN_WIDTH)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.time_organizer_dock)
        self.time_organizer_dock.setFloating(False)
        self.splitDockWidget(self.ui.Subject, self.time_organizer_dock, Qt.Orientation.Horizontal)
        self.splitDockWidget(self.time_organizer_dock, self.task_tabs_dock, Qt.Orientation.Vertical)
        self.resizeDocks(
            [self.ui.Subject, self.time_organizer_dock],
            [220, 700],
            Qt.Orientation.Horizontal,
        )
        self.resizeDocks(
            [self.time_organizer_dock, self.task_tabs_dock],
            [240, 420],
            Qt.Orientation.Vertical,
        )

        toggle_action = self.time_organizer_dock.toggleViewAction()
        toggle_action.setText("Time Organizer")
        self.ui.menuView.addAction(toggle_action)

    def _replace_empty_central_area(self):
        placeholder = QWidget(self)
        placeholder.setObjectName("CentralPlaceholder")
        placeholder.setMinimumSize(0, 0)
        self.setCentralWidget(placeholder)

    def _sync_time_organizer(self):
        if self.selected_subject is None:
            self.time_organizer_tab.set_subject(None)
            return

        planner_follows_subject = bool(
            self.preferences.get("planner_follows_subject_selection", True)
        )
        timer_follows_subject = bool(
            self.preferences.get("timer_follows_subject_selection", True)
        )
        current_timer_mode = getattr(self.time_organizer_tab, "selected_timer_mode", "pomodoro")
        is_quiz_timer_mode = current_timer_mode in {"short_quiz", "long_quiz"}
        has_time_manager_subject = bool(getattr(self.time_organizer_tab, "subject_name", None))

        should_switch_subject = (
            planner_follows_subject
            or timer_follows_subject
            or is_quiz_timer_mode
            or not has_time_manager_subject
        )
        if not should_switch_subject:
            return

        preserve_timer_state = bool(
            has_time_manager_subject and (is_quiz_timer_mode or not timer_follows_subject)
        )
        self.time_organizer_tab.set_subject(
            self.selected_subject,
            preserve_timer_state=preserve_timer_state,
        )

    def _encode_byte_array(self, value: QByteArray) -> str:
        return bytes(value.toBase64()).decode("ascii")

    def _decode_byte_array(self, value) -> QByteArray | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return QByteArray.fromBase64(value.encode("ascii"))
        except Exception:
            return None

    def _restore_app_state(self):
        payload, source_path = self._load_json_payload_with_legacy_fallback(
            self.app_state_path,
            self.legacy_app_state_path,
        )
        if not isinstance(payload, dict):
            return

        geometry = self._decode_byte_array(payload.get("geometry"))
        if geometry is not None and not geometry.isEmpty():
            self.restoreGeometry(geometry)

        window_state = self._decode_byte_array(payload.get("window_state"))
        if window_state is not None and not window_state.isEmpty():
            self.restoreState(window_state, self.APP_STATE_VERSION)

        task_tabs_index = payload.get("task_tabs_index")
        if isinstance(task_tabs_index, int) and 0 <= task_tabs_index < self.ui.TaskTabs.count():
            self.ui.TaskTabs.setCurrentIndex(task_tabs_index)

        time_organizer_index = payload.get("time_organizer_index")
        if (
            isinstance(time_organizer_index, int)
            and 0 <= time_organizer_index < self.ui.time_organizer.count()
        ):
            self.ui.time_organizer.setCurrentIndex(time_organizer_index)

        if source_path == self.legacy_app_state_path and not self.app_state_path.exists():
            self._save_app_state()

    def _save_app_state(self):
        self._ensure_app_state_dir()
        payload = {
            "schema_version": self.APP_STATE_VERSION,
            "geometry": self._encode_byte_array(self.saveGeometry()),
            "window_state": self._encode_byte_array(self.saveState(self.APP_STATE_VERSION)),
            "task_tabs_index": self.ui.TaskTabs.currentIndex(),
            "time_organizer_index": self.ui.time_organizer.currentIndex(),
        }
        try:
            with self.app_state_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError:
            pass

    def _subject_names(self) -> list[str]:
        return [subject.name for subject in self.subjects]

    def _find_subject(self, subject_name: str | None) -> SubjectRecord | None:
        if not isinstance(subject_name, str):
            return None

        normalized = subject_name.strip().lower()
        if not normalized:
            return None

        for subject in self.subjects:
            if subject.name.lower() == normalized:
                return subject
        return None

    def _chapter_path(self, chapter_title: str, subchapter_title: str | None = None) -> str:
        chapter = chapter_title.strip()
        if not subchapter_title:
            return chapter
        return f"{chapter} / {subchapter_title.strip()}"

    def _split_leaf_path(self, leaf_path: str) -> tuple[str, str | None]:
        normalized = leaf_path.strip()
        if " / " not in normalized:
            return normalized, None
        chapter_title, subchapter_title = normalized.split(" / ", 1)
        return chapter_title.strip(), subchapter_title.strip() or None

    def _subject_leaf_paths(self, subject: SubjectRecord | None) -> list[str]:
        if subject is None:
            return []
        leaf_paths: list[str] = []
        for chapter in subject.chapters:
            leaf_paths.append(chapter.title)
            if chapter.subchapters:
                leaf_paths.extend(
                    self._chapter_path(chapter.title, subchapter)
                    for subchapter in chapter.subchapters
                )
        return leaf_paths

    def _selected_subject_chapters(self) -> list[str]:
        return self._subject_leaf_paths(self._find_subject(self.selected_subject))

    def _find_chapter_record(self, subject: SubjectRecord | None, chapter_title: str) -> ChapterRecord | None:
        if subject is None:
            return None
        normalized = chapter_title.strip().lower()
        for chapter in subject.chapters:
            if chapter.title.lower() == normalized:
                return chapter
        return None

    def _leaf_path_exists(self, subject: SubjectRecord | None, leaf_path: str, *, excluding_path: str | None = None) -> bool:
        normalized = leaf_path.strip().lower()
        excluded = excluding_path.strip().lower() if isinstance(excluding_path, str) else None
        for existing_path in self._subject_leaf_paths(subject):
            key = existing_path.lower()
            if excluded is not None and key == excluded:
                continue
            if key == normalized:
                return True
        return False

    def _subject_storage_slug(self, subject_name: str) -> str:
        return self._slugify_subject(subject_name)

    def _quiz_bank_dir(self, subject_name: str) -> Path:
        return self._quiz_banks_root() / self._subject_storage_slug(subject_name)

    def _notebook_storage_path(self, subject_name: str) -> Path:
        return self._notebooks_root() / f"{self._subject_storage_slug(subject_name)}.json"

    def _time_organizer_storage_path(self, subject_name: str) -> Path:
        return self._time_organizer_root() / f"{self._subject_storage_slug(subject_name)}.json"

    def _merge_leaf_paths(self, existing: list[str], incoming: list[str]) -> list[str]:
        merged = list(existing)
        for leaf_path in incoming:
            if any(saved.lower() == leaf_path.lower() for saved in merged):
                continue
            merged.append(leaf_path)
        return merged

    def _subject_from_leaf_paths(self, name: str, leaf_paths: list[str]) -> SubjectRecord:
        chapters: list[ChapterRecord] = []
        for leaf_path in leaf_paths:
            chapter_title, subchapter_title = self._split_leaf_path(leaf_path)
            if not chapter_title:
                continue
            chapter = next(
                (item for item in chapters if item.title.lower() == chapter_title.lower()),
                None,
            )
            if chapter is None:
                chapter = ChapterRecord(title=chapter_title)
                chapters.append(chapter)
            if subchapter_title:
                if any(saved.lower() == subchapter_title.lower() for saved in chapter.subchapters):
                    continue
                chapter.subchapters.append(subchapter_title)
        return SubjectRecord(name=name, chapters=chapters)

    def _collect_chapters_from_bank_payload(self, bank_payload) -> list[str]:
        if not isinstance(bank_payload, dict):
            return []

        chapters = []
        chapters_payload = bank_payload.get("chapters", [])
        if not isinstance(chapters_payload, list):
            return chapters

        for entry in chapters_payload:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title") or entry.get("chapter")
            if not isinstance(title, str):
                continue
            normalized = title.strip()
            if not normalized:
                continue
            if any(existing.lower() == normalized.lower() for existing in chapters):
                continue
            chapters.append(normalized)

        return chapters

    def _collect_chapters_from_storage(self, subject_name: str) -> list[str]:
        subject_dir = self._quiz_bank_dir(subject_name)
        chapters: list[str] = []
        for quiz_key in ("short_quiz", "long_quiz"):
            bank_path = subject_dir / f"{quiz_key}.json"
            if not bank_path.exists():
                continue
            try:
                bank = load_quiz_bank_from_path(bank_path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            chapters = self._merge_leaf_paths(chapters, [chapter.title for chapter in bank.chapters])
        return chapters

    def _load_subject_records(
        self,
        raw_subjects,
        *,
        backup_quiz_banks=None,
        derive_from_storage: bool,
    ) -> list[SubjectRecord]:
        records: list[SubjectRecord] = []
        if not isinstance(raw_subjects, list):
            raw_subjects = []

        for entry in raw_subjects:
            name = None
            leaf_paths: list[str] = []

            if isinstance(entry, str):
                name = entry.strip()
            elif isinstance(entry, dict):
                raw_name = entry.get("name")
                if isinstance(raw_name, str):
                    name = raw_name.strip()
                raw_chapters = entry.get("chapters", [])
                if isinstance(raw_chapters, list):
                    for chapter in raw_chapters:
                        if isinstance(chapter, str):
                            normalized = chapter.strip()
                            if normalized:
                                leaf_paths = self._merge_leaf_paths(leaf_paths, [normalized])
                            continue
                        if not isinstance(chapter, dict):
                            continue
                        chapter_title = chapter.get("title") or chapter.get("chapter")
                        if not isinstance(chapter_title, str) or not chapter_title.strip():
                            continue
                        normalized_title = chapter_title.strip()
                        raw_subchapters = chapter.get("subchapters", [])
                        if isinstance(raw_subchapters, list) and raw_subchapters:
                            normalized_subchapters: list[str] = []
                            for subchapter in raw_subchapters:
                                if not isinstance(subchapter, str) or not subchapter.strip():
                                    continue
                                normalized_subchapter = subchapter.strip()
                                if any(saved.lower() == normalized_subchapter.lower() for saved in normalized_subchapters):
                                    continue
                                normalized_subchapters.append(normalized_subchapter)
                            if normalized_subchapters:
                                leaf_paths = self._merge_leaf_paths(
                                    leaf_paths,
                                    [self._chapter_path(normalized_title, subchapter) for subchapter in normalized_subchapters],
                                )
                                continue
                        leaf_paths = self._merge_leaf_paths(leaf_paths, [normalized_title])

            if not name:
                continue

            if any(subject.name.lower() == name.lower() for subject in records):
                continue

            records.append(self._subject_from_leaf_paths(name, leaf_paths))

        if isinstance(backup_quiz_banks, dict):
            for subject_name, subject_payload in backup_quiz_banks.items():
                if not isinstance(subject_name, str) or not subject_name.strip():
                    continue
                subject = next(
                    (item for item in records if item.name.lower() == subject_name.strip().lower()),
                    None,
                )
                if subject is None:
                    subject = SubjectRecord(name=subject_name.strip())
                    records.append(subject)

                if isinstance(subject_payload, dict):
                    chapters = []
                    for quiz_key in ("short_quiz", "long_quiz"):
                        chapters = self._merge_leaf_paths(
                            chapters,
                            self._collect_chapters_from_bank_payload(subject_payload.get(quiz_key)),
                        )
                    merged_leaf_paths = self._merge_leaf_paths(self._subject_leaf_paths(subject), chapters)
                    subject.chapters = self._subject_from_leaf_paths(subject.name, merged_leaf_paths).chapters

        if derive_from_storage:
            for subject in records:
                merged_leaf_paths = self._merge_leaf_paths(
                    self._subject_leaf_paths(subject),
                    self._collect_chapters_from_storage(subject.name),
                )
                subject.chapters = self._subject_from_leaf_paths(subject.name, merged_leaf_paths).chapters

        return records

    def _make_subject_item(self, subject: SubjectRecord) -> QTreeWidgetItem:
        # Get subject display name with monochrome emoji
        display_name = get_subject_display_name(subject.name, self.emoji_manager, use_monochrome=True)
        item = QTreeWidgetItem([display_name])
        item.setData(0, ITEM_KIND_ROLE, "subject")
        item.setData(0, SUBJECT_NAME_ROLE, subject.name)
        apply_hierarchical_font_to_item(item, level=0)  # Subject - largest font
        
        for chapter in subject.chapters:
            item.addChild(self._make_chapter_item(subject.name, chapter))
        item.setExpanded(True)
        return item

    def _make_chapter_item(self, subject_name: str, chapter: ChapterRecord) -> QTreeWidgetItem:
        child = QTreeWidgetItem([chapter.title])
        child.setData(0, ITEM_KIND_ROLE, "chapter")
        child.setData(0, SUBJECT_NAME_ROLE, subject_name)
        child.setData(0, CHAPTER_NAME_ROLE, chapter.title)
        child.setData(0, LEAF_PATH_ROLE, chapter.title)
        apply_hierarchical_font_to_item(child, level=1)

        if chapter.subchapters:
            for subchapter_name in chapter.subchapters:
                leaf_path = self._chapter_path(chapter.title, subchapter_name)
                grandchild = QTreeWidgetItem([subchapter_name])
                grandchild.setData(0, ITEM_KIND_ROLE, "subchapter")
                grandchild.setData(0, SUBJECT_NAME_ROLE, subject_name)
                grandchild.setData(0, CHAPTER_NAME_ROLE, subchapter_name)
                grandchild.setData(0, PARENT_CHAPTER_ROLE, chapter.title)
                grandchild.setData(0, LEAF_PATH_ROLE, leaf_path)
                apply_hierarchical_font_to_item(grandchild, level=2)
                child.addChild(grandchild)
            child.setExpanded(True)
        return child

    def _server_glyph_for_subject(self, subject_name: str) -> str:
        emoji = self.emoji_manager.get_emoji_for_subject(subject_name, use_monochrome=True)
        if emoji:
            return emoji
        return subject_name[:1].upper() if subject_name else "?"

    def _rebuild_subject_tree(self):
        self.subject_tree.blockSignals(True)
        self.subject_tree.clear()
        for subject in self.subjects:
            self.subject_tree.addTopLevelItem(self._make_subject_item(subject))
        self.subject_tree.blockSignals(False)
        self._rebuild_subject_server_list()
        self._refresh_subject_server_chapters()
        if self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)

    def _rebuild_subject_server_list(self):
        if not hasattr(self, "subject_server_list"):
            return
        self.subject_server_list.blockSignals(True)
        self.subject_server_list.clear()
        for subject in self.subjects:
            item = QListWidgetItem(self._server_glyph_for_subject(subject.name))
            item.setData(SUBJECT_NAME_ROLE, subject.name)
            item.setToolTip(get_subject_display_name(subject.name, self.emoji_manager, use_monochrome=True))
            item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
            item.setSizeHint(self._subject_vertical_slot_size())
            item.setFont(self._subject_vertical_emoji_font())
            self.subject_server_list.addItem(item)
        self.subject_server_list.blockSignals(False)

    def _refresh_subject_server_chapters(self):
        if not hasattr(self, "subject_server_chapter_tree"):
            return

        subject = self._find_subject(self.selected_subject)
        if subject is None:
            self.subject_server_header_label.setText("Select a subject")
            self.subject_server_chapter_tree.blockSignals(True)
            self.subject_server_chapter_tree.clear()
            self.subject_server_chapter_tree.blockSignals(False)
            return

        self.subject_server_header_label.setText(
            get_subject_display_name(subject.name, self.emoji_manager, use_monochrome=True)
        )
        self.subject_server_chapter_tree.blockSignals(True)
        self.subject_server_chapter_tree.clear()
        for chapter in subject.chapters:
            self.subject_server_chapter_tree.addTopLevelItem(
                self._make_chapter_item(subject.name, chapter)
            )
        self.subject_server_chapter_tree.blockSignals(False)

    def _find_server_subject_row(self, subject_name: str) -> int:
        normalized = subject_name.strip().lower()
        for index in range(self.subject_server_list.count()):
            item = self.subject_server_list.item(index)
            stored_name = item.data(SUBJECT_NAME_ROLE)
            if isinstance(stored_name, str) and stored_name.lower() == normalized:
                return index
        return -1

    def _set_current_server_subject(self, subject_name: str):
        if not hasattr(self, "subject_server_list"):
            return
        row = self._find_server_subject_row(subject_name)
        self.subject_server_list.blockSignals(True)
        if row >= 0:
            self.subject_server_list.setCurrentRow(row)
        else:
            self.subject_server_list.clearSelection()
        self.subject_server_list.blockSignals(False)

    def _find_subject_server_chapter_item(self, normalized_path: str) -> QTreeWidgetItem | None:
        for index in range(self.subject_server_chapter_tree.topLevelItemCount()):
            item = self.subject_server_chapter_tree.topLevelItem(index)
            stored_path = item.data(0, LEAF_PATH_ROLE)
            if isinstance(stored_path, str) and stored_path.lower() == normalized_path:
                return item
            for child_index in range(item.childCount()):
                child = item.child(child_index)
                stored_path = child.data(0, LEAF_PATH_ROLE)
                if isinstance(stored_path, str) and stored_path.lower() == normalized_path:
                    return child
        return None

    def _set_current_server_chapter(self, subject_name: str, chapter_name: str):
        if not hasattr(self, "subject_server_chapter_tree"):
            return
        self._set_current_server_subject(subject_name)
        if not self.selected_subject or self.selected_subject.lower() != subject_name.strip().lower():
            self.selected_subject = subject_name
            self._refresh_subject_server_chapters()
        item = self._find_subject_server_chapter_item(chapter_name.strip().lower())
        self.subject_server_chapter_tree.blockSignals(True)
        self.subject_server_chapter_tree.setCurrentItem(item)
        self.subject_server_chapter_tree.blockSignals(False)

    def _find_subject_item(self, subject_name: str) -> QTreeWidgetItem | None:
        normalized = subject_name.strip().lower()
        for index in range(self.subject_tree.topLevelItemCount()):
            item = self.subject_tree.topLevelItem(index)
            stored_name = item.data(0, SUBJECT_NAME_ROLE)
            if isinstance(stored_name, str) and stored_name.lower() == normalized:
                return item
        return None

    def _set_current_tree_subject(self, subject_name: str):
        item = self._find_subject_item(subject_name)
        self.subject_tree.blockSignals(True)
        self.subject_tree.setCurrentItem(item)
        self.subject_tree.blockSignals(False)

    def _set_current_tree_chapter(self, subject_name: str, chapter_name: str):
        subject_item = self._find_subject_item(subject_name)
        if subject_item is None:
            self._set_current_server_chapter(subject_name, chapter_name)
            return

        normalized = chapter_name.strip().lower()
        for index in range(subject_item.childCount()):
            child = subject_item.child(index)
            stored_leaf = child.data(0, LEAF_PATH_ROLE)
            if isinstance(stored_leaf, str) and stored_leaf.lower() == normalized:
                self.subject_tree.blockSignals(True)
                self.subject_tree.setCurrentItem(child)
                self.subject_tree.blockSignals(False)
                self._set_current_server_chapter(subject_name, chapter_name)
                return
            for sub_index in range(child.childCount()):
                grandchild = child.child(sub_index)
                stored_leaf = grandchild.data(0, LEAF_PATH_ROLE)
                if isinstance(stored_leaf, str) and stored_leaf.lower() == normalized:
                    self.subject_tree.blockSignals(True)
                    self.subject_tree.setCurrentItem(grandchild)
                    self.subject_tree.blockSignals(False)
                    self._set_current_server_chapter(subject_name, chapter_name)
                    return
        self._set_current_server_chapter(subject_name, chapter_name)

    def _show_first_time_setup(self):
        """Show first-time setup wizard to configure data path."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("PrepCore - First Time Setup")
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText(
            "<b>Welcome to PrepCore!</b><br><br>"
            "This appears to be your first time running the app.<br><br>"
            "Please choose where you'd like to store your data "
            "(subjects, preferences, and notes).<br><br>"
            "<i>You can change this location anytime from Preferences.</i>"
        )
        
        browse_btn = dialog.addButton("Choose Location", QMessageBox.ButtonRole.ActionRole)
        default_btn = dialog.addButton("Use Default", QMessageBox.ButtonRole.AcceptRole)
        
        result = dialog.exec()
        
        if dialog.clickedButton() == browse_btn:
            # Let user browse for a location
            initial_path = str(self.app_state_dir.parent)
            new_path = QFileDialog.getExistingDirectory(
                self,
                "Select Data Storage Location",
                initial_path,
                QFileDialog.Option.ShowDirsOnly
            )
            
            if new_path:
                self._apply_first_time_path(new_path)
            else:
                # User cancelled, use default
                self._apply_first_time_path(str(self.app_state_dir))
        else:
            # Use default path
            self._apply_first_time_path(str(self.app_state_dir))

    def _apply_first_time_path(self, path_str: str):
        """Apply the path chosen during first-time setup."""
        path = Path(path_str)
        
        # Create the directory
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Could not create directory:\n{e}\n\nUsing default location."
            )
            path = self.app_state_dir
            path.mkdir(parents=True, exist_ok=True)
        
        # Update app_state_dir
        self.app_state_dir = path
        self.subject_store_path = self.app_state_dir / "subjects.json"
        self.app_state_path = self.app_state_dir / "window_state.json"
        self.preferences_path = self.app_state_dir / "preferences.json"
        self._ensure_data_storage_dirs()
        self._migrate_legacy_storage()
        
        # Save preference for future runs
        self.preferences = self._default_preferences()
        self.preferences["custom_data_path"] = str(path)
        self._save_preferences()

    def _detect_first_run(self) -> bool:
        """Detect if this is the first time the app is being run."""
        first_run_marker = self.app_state_dir / ".firstrun"
        if not first_run_marker.exists():
            # First run detected
            self.app_state_dir.mkdir(parents=True, exist_ok=True)
            try:
                first_run_marker.touch()
                return True
            except OSError:
                return True
        return False

    def _load_subjects(self):
        # On first run, start with blank slate (no existing data)
        if self.is_first_run:
            self.subjects = []
            self._rebuild_subject_tree()
            return
        
        payload, source_path = self._load_json_payload_with_legacy_fallback(
            self.subject_store_path,
            self.legacy_subject_store_path,
        )
        if not isinstance(payload, dict):
            return

        self._restore_embedded_quiz_banks(payload.get("quiz_banks"))

        self.subjects = self._load_subject_records(
            payload.get("subjects", []),
            backup_quiz_banks=payload.get("quiz_banks", {}),
            derive_from_storage=True,
        )
        self._rebuild_subject_tree()

        stored_selected = payload.get("selected_subject")
        stored_subject = self._find_subject(stored_selected)
        if stored_subject is not None:
            self.select_subject(stored_subject.name)
        elif self.subjects:
            self.select_subject(self.subjects[0].name)

        if source_path == self.legacy_subject_store_path and not self.subject_store_path.exists():
            self._save_subjects()

    def _save_subjects(self):
        self._ensure_app_state_dir()
        payload = {
            "schema_version": 2,
            "subjects": [subject.to_dict() for subject in self.subjects],
            "selected_subject": self.selected_subject,
            "quiz_banks": self._collect_quiz_banks_snapshot(),
        }
        try:
            with self.subject_store_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError:
            pass

    def _collect_quiz_banks_snapshot(self) -> dict[str, dict[str, object]]:
        snapshot: dict[str, dict[str, object]] = {}
        for subject in self.subjects:
            subject_payload: dict[str, object] = {}
            subject_dir = self._quiz_bank_dir(subject.name)
            for quiz_key in ("short_quiz", "long_quiz"):
                bank_path = subject_dir / f"{quiz_key}.json"
                payload = self._read_json_payload(bank_path) if bank_path.exists() else None
                if isinstance(payload, dict):
                    subject_payload[quiz_key] = payload
            if subject_payload:
                snapshot[subject.name] = subject_payload
        return snapshot

    def _restore_embedded_quiz_banks(self, payload):
        if not isinstance(payload, dict):
            return

        for subject_name, subject_payload in payload.items():
            if not isinstance(subject_name, str) or not isinstance(subject_payload, dict):
                continue
            subject_dir = self._quiz_bank_dir(subject_name)
            subject_dir.mkdir(parents=True, exist_ok=True)
            for quiz_key in ("short_quiz", "long_quiz"):
                bank_payload = subject_payload.get(quiz_key)
                if not isinstance(bank_payload, dict):
                    continue
                bank_path = subject_dir / f"{quiz_key}.json"
                if bank_path.exists():
                    continue
                try:
                    with bank_path.open("w", encoding="utf-8") as handle:
                        json.dump(bank_payload, handle, indent=2)
                except OSError:
                    continue

    def prompt_add_subject(self):
        text, accepted = QInputDialog.getText(
            self,
            "Add Subject",
            "Enter a subject name:",
            QLineEdit.EchoMode.Normal,
        )
        if accepted:
            self._add_subject(text)

    def prompt_add_chapter(self, subject_name: str):
        text, accepted = QInputDialog.getText(
            self,
            "Add Chapter",
            f"Enter a chapter name for {subject_name}:",
            QLineEdit.EchoMode.Normal,
        )
        if accepted:
            self._add_chapter(subject_name, text)

    def prompt_add_subchapter(self, subject_name: str, chapter_name: str):
        text, accepted = QInputDialog.getText(
            self,
            "Add Subchapter",
            f"Enter a subchapter name for {chapter_name}:",
            QLineEdit.EchoMode.Normal,
        )
        if accepted:
            self._add_subchapter(subject_name, chapter_name, text)

    def prompt_rename_subject(self, subject_name: str):
        subject = self._find_subject(subject_name)
        if subject is None:
            return

        text, accepted = QInputDialog.getText(
            self,
            "Rename Subject",
            "Enter a new subject name:",
            QLineEdit.EchoMode.Normal,
            subject.name,
        )
        if accepted:
            self._rename_subject(subject.name, text)

    def prompt_rename_chapter(
        self,
        subject_name: str,
        chapter_name: str,
        *,
        parent_chapter_name: str | None = None,
    ):
        subject = self._find_subject(subject_name)
        if subject is None:
            return

        if parent_chapter_name is None:
            chapter = self._find_chapter_record(subject, chapter_name)
            current_title = chapter.title if chapter is not None else None
            dialog_title = "Rename Chapter"
            prompt_text = f"Enter a new chapter name for {subject.name}:"
        else:
            chapter = self._find_chapter_record(subject, parent_chapter_name)
            if chapter is None:
                return
            current_title = next(
                (item for item in chapter.subchapters if item.lower() == chapter_name.strip().lower()),
                None,
            )
            dialog_title = "Rename Subchapter"
            prompt_text = f"Enter a new subchapter name for {parent_chapter_name}:"

        if current_title is None:
            return

        text, accepted = QInputDialog.getText(
            self,
            dialog_title,
            prompt_text,
            QLineEdit.EchoMode.Normal,
            current_title,
        )
        if accepted:
            if parent_chapter_name is None:
                self._rename_chapter(subject.name, current_title, text)
            else:
                self._rename_subchapter(subject.name, parent_chapter_name, current_title, text)

    def resolve_subject_for_quiz_import(self):
        if self.selected_subject:
            return self.selected_subject

        subject_names = self._subject_names()
        if subject_names:
            choice, accepted = QInputDialog.getItem(
                self,
                "Select Subject",
                "Choose a subject for this import:",
                subject_names,
                0,
                True,
            )
        else:
            choice, accepted = QInputDialog.getText(
                self,
                "Create Subject",
                "Enter a subject name for this import:",
                QLineEdit.EchoMode.Normal,
            )

        if not accepted:
            return None

        normalized = choice.strip()
        if not normalized:
            return None

        subject = self._find_subject(normalized)
        if subject is not None:
            self.select_subject(subject.name)
        else:
            self._add_subject(normalized)

        return self.selected_subject

    def add_subject_from_input(self):
        self._add_subject(self.subject_input.text())

    def _add_subject(
        self,
        subject_name,
        *,
        save=True,
        select=True,
        show_errors=True,
    ):
        normalized = subject_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Subject", "Please enter a subject name.")
            return False

        if self._find_subject(normalized) is not None:
            if show_errors:
                QMessageBox.information(self, "Duplicate Subject", "That subject already exists.")
            return False

        self.subjects.append(SubjectRecord(name=normalized))
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        self.subject_input.clear()

        if select:
            self.select_subject(normalized)

        return True

    def _add_chapter(self, subject_name: str, chapter_name: str, *, save=True, show_errors=True):
        subject = self._find_subject(subject_name)
        if subject is None:
            return False

        normalized = chapter_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Chapter", "Please enter a chapter name.")
            return False

        if self._find_chapter_record(subject, normalized) is not None:
            if show_errors:
                QMessageBox.information(self, "Duplicate Chapter", "That chapter already exists.")
            return False

        subject.chapters.append(ChapterRecord(title=normalized))
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        self.select_subject(subject.name, update_tree=False, force_refresh=True)
        self._set_current_tree_chapter(subject.name, normalized)
        return True

    def _leaf_has_saved_content(self, subject_name: str, leaf_path: str) -> bool:
        normalized = leaf_path.strip().lower()
        notebook_path = self._notebook_storage_path(subject_name)
        payload = self._read_json_payload(notebook_path) if notebook_path.exists() else None
        if isinstance(payload, dict):
            notes = payload.get("notes", {})
            if isinstance(notes, dict):
                for key, content in notes.items():
                    if isinstance(key, str) and key.strip().lower() == normalized and isinstance(content, str) and content.strip():
                        return True

        for quiz_key in ("short_quiz", "long_quiz"):
            bank_path = self._quiz_bank_dir(subject_name) / f"{quiz_key}.json"
            payload = self._read_json_payload(bank_path) if bank_path.exists() else None
            if not isinstance(payload, dict):
                continue
            chapters = payload.get("chapters", [])
            if not isinstance(chapters, list):
                continue
            for entry in chapters:
                if not isinstance(entry, dict):
                    continue
                title = entry.get("title")
                questions = entry.get("questions", [])
                if (
                    isinstance(title, str)
                    and title.strip().lower() == normalized
                    and isinstance(questions, list)
                    and len(questions) > 0
                ):
                    return True
        return False

    def _add_subchapter(
        self,
        subject_name: str,
        chapter_name: str,
        subchapter_name: str,
        *,
        save=True,
        show_errors=True,
    ):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            return False

        normalized = subchapter_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Subchapter", "Please enter a subchapter name.")
            return False

        new_leaf_path = self._chapter_path(chapter.title, normalized)
        if self._leaf_path_exists(subject, new_leaf_path):
            if show_errors:
                QMessageBox.information(self, "Duplicate Subchapter", "That subchapter already exists.")
            return False

        chapter.subchapters.append(normalized)
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        self.select_subject(subject.name, update_tree=False, force_refresh=True)
        self._set_current_tree_chapter(subject.name, new_leaf_path)
        return True

    def _delete_subject_storage(self, subject_name: str):
        quiz_bank_dir = self._quiz_bank_dir(subject_name)
        if quiz_bank_dir.exists():
            try:
                shutil.rmtree(quiz_bank_dir)
            except OSError:
                pass

        for path in (
            self._notebook_storage_path(subject_name),
            self._time_organizer_storage_path(subject_name),
        ):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass

    def _storage_slug_in_use(self, subject_name: str, *, excluding_subject: str | None = None) -> bool:
        target_slug = self._subject_storage_slug(subject_name)
        excluded = excluding_subject.strip().lower() if isinstance(excluding_subject, str) else None
        for subject in self.subjects:
            if excluded is not None and subject.name.lower() == excluded:
                continue
            if self._subject_storage_slug(subject.name) == target_slug:
                return True
        return False

    def _move_storage_path(self, source_path: Path, destination_path: Path) -> bool:
        if source_path == destination_path or not source_path.exists():
            return True
        if destination_path.exists():
            return False
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        return True

    def _update_quiz_bank_subject_name(self, bank_path: Path, subject_name: str):
        if not bank_path.exists():
            return True
        try:
            with bank_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return True
            payload["subject"] = subject_name
            with bank_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except (OSError, json.JSONDecodeError):
            return False
        return True

    def _update_notebook_subject_name(self, notebook_path: Path, subject_name: str):
        if not notebook_path.exists():
            return True
        try:
            with notebook_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return True
            payload["subject"] = subject_name
            with notebook_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except (OSError, json.JSONDecodeError):
            return False
        return True

    def _update_time_organizer_subject_name(self, organizer_path: Path, subject_name: str):
        if not organizer_path.exists():
            return True
        try:
            with organizer_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return True
            payload["subject"] = subject_name
            tasks = payload.get("tasks", [])
            if isinstance(tasks, list):
                for entry in tasks:
                    if isinstance(entry, dict):
                        entry["subject"] = subject_name
            with organizer_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except (OSError, json.JSONDecodeError):
            return False
        return True

    def _rename_subject_storage(self, old_subject_name: str, new_subject_name: str):
        old_quiz_bank_dir = self._quiz_bank_dir(old_subject_name)
        new_quiz_bank_dir = self._quiz_bank_dir(new_subject_name)
        old_notebook_path = self._notebook_storage_path(old_subject_name)
        new_notebook_path = self._notebook_storage_path(new_subject_name)
        old_time_path = self._time_organizer_storage_path(old_subject_name)
        new_time_path = self._time_organizer_storage_path(new_subject_name)

        try:
            if not self._move_storage_path(old_quiz_bank_dir, new_quiz_bank_dir):
                return False, "A quiz bank already exists for that subject name."
            if not self._move_storage_path(old_notebook_path, new_notebook_path):
                return False, "A notebook already exists for that subject name."
            if not self._move_storage_path(old_time_path, new_time_path):
                return False, "A time organizer file already exists for that subject name."
        except OSError as exc:
            return False, str(exc)

        for quiz_key in ("short_quiz", "long_quiz"):
            bank_path = new_quiz_bank_dir / f"{quiz_key}.json"
            if not self._update_quiz_bank_subject_name(bank_path, new_subject_name):
                return False, f"Unable to update {quiz_key.replace('_', ' ')} storage."

        if not self._update_notebook_subject_name(new_notebook_path, new_subject_name):
            return False, "Unable to update notebook storage."
        if not self._update_time_organizer_subject_name(new_time_path, new_subject_name):
            return False, "Unable to update time organizer storage."
        return True, ""

    def _replace_leaf_paths_in_notebook(self, notebook_path: Path, rename_map: dict[str, str], delete_paths: set[str]):
        payload = self._read_json_payload(notebook_path) if notebook_path.exists() else None
        if not isinstance(payload, dict):
            return True, ""

        notes = payload.get("notes", {})
        updated_notes: dict[str, str] = {}
        if isinstance(notes, dict):
            for key, content in notes.items():
                if not isinstance(key, str) or not isinstance(content, str):
                    continue
                lowered = key.strip().lower()
                if lowered in delete_paths:
                    continue
                updated_notes[rename_map.get(lowered, key)] = content

        selected_chapter = payload.get("selected_chapter")
        if isinstance(selected_chapter, str):
            lowered = selected_chapter.strip().lower()
            if lowered in delete_paths:
                payload["selected_chapter"] = None
            elif lowered in rename_map:
                payload["selected_chapter"] = rename_map[lowered]

        payload["notes"] = updated_notes
        try:
            with notebook_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as exc:
            return False, str(exc)
        return True, ""

    def _replace_leaf_paths_in_quiz_bank(self, bank_path: Path, rename_map: dict[str, str], delete_paths: set[str]):
        payload = self._read_json_payload(bank_path) if bank_path.exists() else None
        if not isinstance(payload, dict):
            return True, ""

        chapters = payload.get("chapters", [])
        updated_chapters = []
        if isinstance(chapters, list):
            for entry in chapters:
                if not isinstance(entry, dict):
                    continue
                title = entry.get("title")
                if not isinstance(title, str):
                    continue
                lowered = title.strip().lower()
                if lowered in delete_paths:
                    continue
                if lowered in rename_map:
                    entry["title"] = rename_map[lowered]
                updated_chapters.append(entry)
        payload["chapters"] = updated_chapters

        selected_chapter = payload.get("selected_chapter")
        if isinstance(selected_chapter, str):
            lowered = selected_chapter.strip().lower()
            if lowered in delete_paths:
                payload["selected_chapter"] = updated_chapters[0].get("title", "") if updated_chapters else ""
            elif lowered in rename_map:
                payload["selected_chapter"] = rename_map[lowered]
            elif not any(
                isinstance(entry, dict)
                and isinstance(entry.get("title"), str)
                and entry["title"].strip().lower() == lowered
                for entry in updated_chapters
            ):
                payload["selected_chapter"] = updated_chapters[0].get("title", "") if updated_chapters else ""

        long_quiz_state = payload.get("long_quiz_state")
        if isinstance(long_quiz_state, dict):
            selected_chapters = long_quiz_state.get("selected_chapters", [])
            if isinstance(selected_chapters, list):
                long_quiz_state["selected_chapters"] = [
                    rename_map.get(title.strip().lower(), title)
                    for title in selected_chapters
                    if isinstance(title, str) and title.strip().lower() not in delete_paths
                ]
            generated_refs = long_quiz_state.get("generated_question_refs", [])
            if isinstance(generated_refs, list):
                updated_refs = []
                for entry in generated_refs:
                    if not isinstance(entry, dict):
                        continue
                    chapter_title = entry.get("chapter_title")
                    if not isinstance(chapter_title, str):
                        continue
                    lowered = chapter_title.strip().lower()
                    if lowered in delete_paths:
                        continue
                    if lowered in rename_map:
                        entry["chapter_title"] = rename_map[lowered]
                    updated_refs.append(entry)
                long_quiz_state["generated_question_refs"] = updated_refs

        try:
            with bank_path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except OSError as exc:
            return False, str(exc)
        return True, ""

    def _apply_leaf_storage_changes(self, subject_name: str, rename_map: dict[str, str], delete_paths: set[str]):
        notebook_path = self._notebook_storage_path(subject_name)
        if notebook_path.exists():
            success, message = self._replace_leaf_paths_in_notebook(notebook_path, rename_map, delete_paths)
            if not success:
                return False, message

        for quiz_key in ("short_quiz", "long_quiz"):
            bank_path = self._quiz_bank_dir(subject_name) / f"{quiz_key}.json"
            if not bank_path.exists():
                continue
            success, message = self._replace_leaf_paths_in_quiz_bank(bank_path, rename_map, delete_paths)
            if not success:
                return False, message
        return True, ""

    def _rename_chapter_storage(self, subject_name: str, rename_map: dict[str, str], delete_paths: set[str] | None = None):
        normalized_map = {old.strip().lower(): new for old, new in rename_map.items() if old.strip() and new.strip()}
        normalized_delete = {item.strip().lower() for item in (delete_paths or set()) if item.strip()}
        if not normalized_map and not normalized_delete:
            return True, ""
        return self._apply_leaf_storage_changes(subject_name, normalized_map, normalized_delete)

    def _delete_chapter_storage(self, subject_name: str, leaf_paths: list[str]):
        delete_paths = {leaf_path.strip().lower() for leaf_path in leaf_paths if leaf_path.strip()}
        if not delete_paths:
            return
        self._apply_leaf_storage_changes(subject_name, {}, delete_paths)

    def _rename_subject(
        self,
        subject_name: str,
        new_subject_name: str,
        *,
        save=True,
        select=True,
        show_errors=True,
    ):
        subject = self._find_subject(subject_name)
        if subject is None:
            return False

        normalized = new_subject_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Subject", "Please enter a subject name.")
            return False

        if any(
            item.name.lower() == normalized.lower() and item.name.lower() != subject.name.lower()
            for item in self.subjects
        ):
            if show_errors:
                QMessageBox.information(self, "Duplicate Subject", "That subject already exists.")
            return False

        if (
            self._subject_storage_slug(subject.name) != self._subject_storage_slug(normalized)
            and self._storage_slug_in_use(normalized, excluding_subject=subject.name)
        ):
            if show_errors:
                QMessageBox.warning(
                    self,
                    "Rename Subject",
                    "That subject name would reuse another subject's storage path. Choose a more distinct name.",
                )
            return False

        old_name = subject.name
        success, error_message = self._rename_subject_storage(old_name, normalized)
        if not success:
            if show_errors:
                QMessageBox.warning(self, "Rename Subject Failed", error_message or "Unable to rename subject.")
            return False

        subject.name = normalized
        if self.selected_subject and self.selected_subject.lower() == old_name.lower():
            self.selected_subject = normalized
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        if select:
            self.select_subject(normalized)
        elif self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)

        return True

    def _rename_chapter(
        self,
        subject_name: str,
        chapter_name: str,
        new_chapter_name: str,
        *,
        save=True,
        show_errors=True,
    ):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            if show_errors:
                QMessageBox.information(self, "Missing Chapter", "That chapter no longer exists.")
            return False

        normalized = new_chapter_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Chapter", "Please enter a chapter name.")
            return False

        if any(item.title.lower() == normalized.lower() and item.title.lower() != chapter.title.lower() for item in subject.chapters):
            if show_errors:
                QMessageBox.information(self, "Duplicate Chapter", "That chapter already exists.")
            return False

        rename_map = {}
        for leaf_path in self._leaf_paths_for_chapter(chapter):
            _old_parent, subchapter_title = self._split_leaf_path(leaf_path)
            if subchapter_title is None:
                rename_map[leaf_path] = normalized
            else:
                rename_map[leaf_path] = self._chapter_path(normalized, subchapter_title)

        success, error_message = self._rename_chapter_storage(subject.name, rename_map)
        if not success:
            if show_errors:
                QMessageBox.warning(self, "Rename Chapter Failed", error_message or "Unable to rename chapter.")
            return False

        chapter.title = normalized
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            self.select_subject(subject.name, update_tree=False, force_refresh=True)
            if chapter.subchapters:
                self._set_current_tree_subject(subject.name)
            else:
                self._set_current_tree_chapter(subject.name, normalized)
                active_chapter_tab = self._active_chapter_tab()
                if active_chapter_tab is not None:
                    active_chapter_tab.focus_chapter(normalized)
        elif self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)

        return True

    def _leaf_paths_for_chapter(self, chapter: ChapterRecord) -> list[str]:
        return self._subject_leaf_paths(SubjectRecord(name="", chapters=[chapter]))

    def _rename_subchapter(
        self,
        subject_name: str,
        chapter_name: str,
        subchapter_name: str,
        new_subchapter_name: str,
        *,
        save=True,
        show_errors=True,
    ):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            return False

        subchapter_index = next(
            (index for index, item in enumerate(chapter.subchapters) if item.lower() == subchapter_name.strip().lower()),
            -1,
        )
        if subchapter_index < 0:
            if show_errors:
                QMessageBox.information(self, "Missing Subchapter", "That subchapter no longer exists.")
            return False

        normalized = new_subchapter_name.strip()
        if not normalized:
            if show_errors:
                QMessageBox.warning(self, "Invalid Subchapter", "Please enter a subchapter name.")
            return False

        old_leaf_path = self._chapter_path(chapter.title, chapter.subchapters[subchapter_index])
        new_leaf_path = self._chapter_path(chapter.title, normalized)
        if self._leaf_path_exists(subject, new_leaf_path, excluding_path=old_leaf_path):
            if show_errors:
                QMessageBox.information(self, "Duplicate Subchapter", "That subchapter already exists.")
            return False

        success, error_message = self._rename_chapter_storage(subject.name, {old_leaf_path: new_leaf_path})
        if not success:
            if show_errors:
                QMessageBox.warning(self, "Rename Subchapter Failed", error_message or "Unable to rename subchapter.")
            return False

        chapter.subchapters[subchapter_index] = normalized
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            self.select_subject(subject.name, update_tree=False, force_refresh=True)
            self._set_current_tree_chapter(subject.name, new_leaf_path)
            active_chapter_tab = self._active_chapter_tab()
            if active_chapter_tab is not None:
                active_chapter_tab.focus_chapter(new_leaf_path)
        elif self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)

        return True

    def _delete_subject(self, subject_name: str, *, save=True, show_errors=True):
        subject = self._find_subject(subject_name)
        if subject is None:
            return False

        confirm = QMessageBox.question(
            self,
            "Delete Subject",
            f"Delete '{subject.name}' and its saved notebook, quiz, and time-organizer data?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return False

        deleted_index = next(
            (index for index, item in enumerate(self.subjects) if item.name.lower() == subject.name.lower()),
            -1,
        )
        if deleted_index < 0:
            return False

        deleted_selected_subject = (
            isinstance(self.selected_subject, str) and self.selected_subject.lower() == subject.name.lower()
        )
        del self.subjects[deleted_index]
        self._delete_subject_storage(subject.name)
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        if not self.subjects:
            self.selected_subject = None
            self.subject_tree.blockSignals(True)
            self.subject_tree.clearSelection()
            self.subject_tree.setCurrentItem(None)
            self.subject_tree.blockSignals(False)
            self._refresh_subject_views()
            self._sync_task_tabs()
            self._sync_time_organizer()
            if save:
                self._save_subjects()
            return True

        if deleted_selected_subject:
            replacement_index = min(deleted_index, len(self.subjects) - 1)
            self.select_subject(self.subjects[replacement_index].name)
        elif self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)

        return True

    def _delete_chapter(self, subject_name: str, chapter_name: str, *, save=True, show_errors=True):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            if show_errors:
                QMessageBox.information(self, "Missing Chapter", "That chapter no longer exists.")
            return False

        chapter_index = next(
            (index for index, item in enumerate(subject.chapters) if item.title.lower() == chapter.title.lower()),
            -1,
        )
        actual_title = chapter.title
        confirm = QMessageBox.question(
            self,
            "Delete Chapter",
            f"Delete '{actual_title}' and its notebook and quiz content?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return False

        del subject.chapters[chapter_index]
        self._delete_chapter_storage(subject.name, self._leaf_paths_for_chapter(chapter))
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            self.select_subject(subject.name, update_tree=False, force_refresh=True)
            if subject.chapters:
                next_index = min(chapter_index, len(subject.chapters) - 1)
                next_chapter = subject.chapters[next_index]
                next_leaf = self._leaf_paths_for_chapter(next_chapter)[0]
                self._set_current_tree_chapter(subject.name, next_leaf)
                active_chapter_tab = self._active_chapter_tab()
                if active_chapter_tab is not None:
                    active_chapter_tab.focus_chapter(next_leaf)
            else:
                self._set_current_tree_subject(subject.name)
        elif self.selected_subject:
            self._set_current_tree_subject(self.selected_subject)
        return True

    def _delete_subchapter(self, subject_name: str, chapter_name: str, subchapter_name: str, *, save=True, show_errors=True):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            return False

        subchapter_index = next(
            (index for index, item in enumerate(chapter.subchapters) if item.lower() == subchapter_name.strip().lower()),
            -1,
        )
        if subchapter_index < 0:
            if show_errors:
                QMessageBox.information(self, "Missing Subchapter", "That subchapter no longer exists.")
            return False

        actual_title = chapter.subchapters[subchapter_index]
        leaf_path = self._chapter_path(chapter.title, actual_title)
        confirm = QMessageBox.question(
            self,
            "Delete Subchapter",
            f"Delete '{actual_title}' and its notebook and quiz content?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return False

        del chapter.subchapters[subchapter_index]
        self._delete_chapter_storage(subject.name, [leaf_path])
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        self.select_subject(subject.name, update_tree=False, force_refresh=True)
        if chapter.subchapters:
            next_index = min(subchapter_index, len(chapter.subchapters) - 1)
            next_leaf = self._chapter_path(chapter.title, chapter.subchapters[next_index])
            self._set_current_tree_chapter(subject.name, next_leaf)
            active_chapter_tab = self._active_chapter_tab()
            if active_chapter_tab is not None:
                active_chapter_tab.focus_chapter(next_leaf)
        else:
            self._set_current_tree_subject(subject.name)
        return True

    def _move_chapter_up(self, subject_name: str, chapter_name: str, *, save=True):
        subject = self._find_subject(subject_name)
        if subject is None:
            return False

        chapter_index = next(
            (index for index, item in enumerate(subject.chapters) if item.title.lower() == chapter_name.strip().lower()),
            -1,
        )
        if chapter_index <= 0:
            return False

        # Swap with previous chapter
        subject.chapters[chapter_index], subject.chapters[chapter_index - 1] = (
            subject.chapters[chapter_index - 1],
            subject.chapters[chapter_index],
        )
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        # Restore selection
        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            target = self._leaf_paths_for_chapter(subject.chapters[chapter_index - 1])[0]
            self._set_current_tree_chapter(subject.name, target)

        return True

    def _move_chapter_down(self, subject_name: str, chapter_name: str, *, save=True):
        subject = self._find_subject(subject_name)
        if subject is None:
            return False

        chapter_index = next(
            (index for index, item in enumerate(subject.chapters) if item.title.lower() == chapter_name.strip().lower()),
            -1,
        )
        if chapter_index < 0 or chapter_index >= len(subject.chapters) - 1:
            return False

        # Swap with next chapter
        subject.chapters[chapter_index], subject.chapters[chapter_index + 1] = (
            subject.chapters[chapter_index + 1],
            subject.chapters[chapter_index],
        )
        self._rebuild_subject_tree()

        if save:
            self._save_subjects()

        # Restore selection
        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            target = self._leaf_paths_for_chapter(subject.chapters[chapter_index + 1])[0]
            self._set_current_tree_chapter(subject.name, target)

        return True

    def _move_subchapter_up(self, subject_name: str, chapter_name: str, subchapter_name: str, *, save=True):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            return False

        subchapter_index = next(
            (index for index, item in enumerate(chapter.subchapters) if item.lower() == subchapter_name.strip().lower()),
            -1,
        )
        if subchapter_index <= 0:
            return False

        chapter.subchapters[subchapter_index], chapter.subchapters[subchapter_index - 1] = (
            chapter.subchapters[subchapter_index - 1],
            chapter.subchapters[subchapter_index],
        )
        self._rebuild_subject_tree()
        if save:
            self._save_subjects()
        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            self._set_current_tree_chapter(subject.name, self._chapter_path(chapter.title, subchapter_name))
        return True

    def _move_subchapter_down(self, subject_name: str, chapter_name: str, subchapter_name: str, *, save=True):
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        if subject is None or chapter is None:
            return False

        subchapter_index = next(
            (index for index, item in enumerate(chapter.subchapters) if item.lower() == subchapter_name.strip().lower()),
            -1,
        )
        if subchapter_index < 0 or subchapter_index >= len(chapter.subchapters) - 1:
            return False

        chapter.subchapters[subchapter_index], chapter.subchapters[subchapter_index + 1] = (
            chapter.subchapters[subchapter_index + 1],
            chapter.subchapters[subchapter_index],
        )
        self._rebuild_subject_tree()
        if save:
            self._save_subjects()
        if self.selected_subject and self.selected_subject.lower() == subject.name.lower():
            self._set_current_tree_chapter(subject.name, self._chapter_path(chapter.title, subchapter_name))
        return True

    def _show_subject_menu_for_name(self, subject_name: str, global_position, parent_widget: QWidget):
        menu = QMenu(parent_widget)
        add_chapter_action = menu.addAction("Add Chapter...")
        rename_subject_action = menu.addAction("Rename Subject...")
        delete_subject_action = menu.addAction("Delete Subject...")
        chosen = menu.exec(global_position)
        if chosen == add_chapter_action:
            self.prompt_add_chapter(subject_name)
        elif chosen == rename_subject_action:
            self.prompt_rename_subject(subject_name)
        elif chosen == delete_subject_action:
            self._delete_subject(subject_name)

    def _show_chapter_menu_for_name(self, subject_name: str, chapter_name: str, global_position, parent_widget: QWidget):
        menu = QMenu(parent_widget)
        subject = self._find_subject(subject_name)
        chapter_index = -1
        if subject is not None:
            chapter_index = next(
                (index for index, ch in enumerate(subject.chapters) if ch.title.lower() == chapter_name.strip().lower()),
                -1,
            )

        add_subchapter_action = menu.addAction("Add Subchapter...")
        move_up_action = menu.addAction("Move Up")
        move_up_action.setEnabled(chapter_index > 0)
        move_down_action = menu.addAction("Move Down")
        move_down_action.setEnabled(
            chapter_index >= 0 and chapter_index < (len(subject.chapters) - 1) if subject else False
        )
        menu.addSeparator()
        rename_chapter_action = menu.addAction("Rename Chapter...")
        delete_chapter_action = menu.addAction("Delete Chapter...")
        chosen = menu.exec(global_position)
        if chosen == add_subchapter_action:
            self.prompt_add_subchapter(subject_name, chapter_name)
        elif chosen == move_up_action:
            self._move_chapter_up(subject_name, chapter_name)
        elif chosen == move_down_action:
            self._move_chapter_down(subject_name, chapter_name)
        elif chosen == rename_chapter_action:
            self.prompt_rename_chapter(subject_name, chapter_name)
        elif chosen == delete_chapter_action:
            self._delete_chapter(subject_name, chapter_name)

    def _show_subchapter_menu_for_name(
        self,
        subject_name: str,
        chapter_name: str,
        subchapter_name: str,
        global_position,
        parent_widget: QWidget,
    ):
        menu = QMenu(parent_widget)
        subject = self._find_subject(subject_name)
        chapter = self._find_chapter_record(subject, chapter_name)
        subchapter_index = -1
        if chapter is not None:
            subchapter_index = next(
                (index for index, ch in enumerate(chapter.subchapters) if ch.lower() == subchapter_name.strip().lower()),
                -1,
            )

        move_up_action = menu.addAction("Move Up")
        move_up_action.setEnabled(subchapter_index > 0)
        move_down_action = menu.addAction("Move Down")
        move_down_action.setEnabled(
            subchapter_index >= 0 and chapter is not None and subchapter_index < (len(chapter.subchapters) - 1)
        )
        menu.addSeparator()
        rename_subchapter_action = menu.addAction("Rename Subchapter...")
        delete_subchapter_action = menu.addAction("Delete Subchapter...")

        chosen = menu.exec(global_position)
        if chosen == move_up_action:
            self._move_subchapter_up(subject_name, chapter_name, subchapter_name)
        elif chosen == move_down_action:
            self._move_subchapter_down(subject_name, chapter_name, subchapter_name)
        elif chosen == rename_subchapter_action:
            self.prompt_rename_chapter(subject_name, subchapter_name, parent_chapter_name=chapter_name)
        elif chosen == delete_subchapter_action:
            self._delete_subchapter(subject_name, chapter_name, subchapter_name)

    def show_subject_context_menu(self, position):
        item = self.subject_tree.itemAt(position)
        if item is None:
            menu = QMenu(self.subject_tree)
            add_subject_action = menu.addAction("Add Subject...")
            chosen = menu.exec(self.subject_tree.viewport().mapToGlobal(position))
            if chosen == add_subject_action:
                self.prompt_add_subject()
            return

        item_kind = item.data(0, ITEM_KIND_ROLE)
        subject_name = item.data(0, SUBJECT_NAME_ROLE)
        global_position = self.subject_tree.viewport().mapToGlobal(position)
        if item_kind == "subject" and isinstance(subject_name, str):
            self._show_subject_menu_for_name(subject_name, global_position, self.subject_tree)
        elif item_kind == "chapter" and isinstance(subject_name, str):
            chapter_name = item.data(0, CHAPTER_NAME_ROLE)
            if isinstance(chapter_name, str):
                self._show_chapter_menu_for_name(
                    subject_name,
                    chapter_name,
                    global_position,
                    self.subject_tree,
                )
        elif item_kind == "subchapter" and isinstance(subject_name, str):
            chapter_name = item.data(0, PARENT_CHAPTER_ROLE)
            subchapter_name = item.data(0, CHAPTER_NAME_ROLE)
            if isinstance(chapter_name, str) and isinstance(subchapter_name, str):
                self._show_subchapter_menu_for_name(
                    subject_name,
                    chapter_name,
                    subchapter_name,
                    global_position,
                    self.subject_tree,
                )

    def _show_subject_server_context_menu(self, position):
        item = self.subject_server_list.itemAt(position)
        if item is None:
            menu = QMenu(self.subject_server_list)
            add_subject_action = menu.addAction("Add Subject...")
            chosen = menu.exec(self.subject_server_list.viewport().mapToGlobal(position))
            if chosen == add_subject_action:
                self.prompt_add_subject()
            return
        subject_name = item.data(SUBJECT_NAME_ROLE)
        if isinstance(subject_name, str):
            self._show_subject_menu_for_name(
                subject_name,
                self.subject_server_list.viewport().mapToGlobal(position),
                self.subject_server_list,
            )

    def _show_subject_server_chapter_context_menu(self, position):
        item = self.subject_server_chapter_tree.itemAt(position)
        global_position = self.subject_server_chapter_tree.viewport().mapToGlobal(position)
        if item is None:
            if isinstance(self.selected_subject, str):
                menu = QMenu(self.subject_server_chapter_tree)
                add_chapter_action = menu.addAction("Add Chapter...")
                chosen = menu.exec(global_position)
                if chosen == add_chapter_action:
                    self.prompt_add_chapter(self.selected_subject)
            return
        item_kind = item.data(0, ITEM_KIND_ROLE)
        subject_name = item.data(0, SUBJECT_NAME_ROLE)
        if item_kind == "chapter" and isinstance(subject_name, str):
            chapter_name = item.data(0, CHAPTER_NAME_ROLE)
            if isinstance(chapter_name, str):
                self._show_chapter_menu_for_name(
                    subject_name,
                    chapter_name,
                    global_position,
                    self.subject_server_chapter_tree,
                )
        elif item_kind == "subchapter" and isinstance(subject_name, str):
            chapter_name = item.data(0, PARENT_CHAPTER_ROLE)
            subchapter_name = item.data(0, CHAPTER_NAME_ROLE)
            if isinstance(chapter_name, str) and isinstance(subchapter_name, str):
                self._show_subchapter_menu_for_name(
                    subject_name,
                    chapter_name,
                    subchapter_name,
                    global_position,
                    self.subject_server_chapter_tree,
                )

    def _active_chapter_tab(self):
        current_widget = self.ui.TaskTabs.currentWidget()
        if current_widget is self.ui.todo_list:
            return self.notebook_tab
        if current_widget is self.ui.short_quiz:
            return self.short_quiz_tab
        if current_widget is self.ui.long_quiz:
            return self.long_quiz_tab
        return None

    def on_subject_selection_changed(self):
        current_item = self.subject_tree.currentItem()
        if current_item is None:
            return

        item_kind = current_item.data(0, ITEM_KIND_ROLE)
        subject_name = current_item.data(0, SUBJECT_NAME_ROLE)
        if not isinstance(subject_name, str):
            return

        self.select_subject(subject_name, update_tree=False)

        leaf_path = current_item.data(0, LEAF_PATH_ROLE)
        if not isinstance(leaf_path, str):
            return

        self._set_current_server_chapter(subject_name, leaf_path)
        active_chapter_tab = self._active_chapter_tab()
        if active_chapter_tab is not None:
            active_chapter_tab.focus_chapter(leaf_path)

    def _on_subject_server_selection_changed(self):
        current_item = self.subject_server_list.currentItem()
        if current_item is None:
            return
        subject_name = current_item.data(SUBJECT_NAME_ROLE)
        if not isinstance(subject_name, str):
            return
        self.select_subject(subject_name, update_tree=False)

    def _on_subject_server_chapter_selection_changed(self):
        current_item = self.subject_server_chapter_tree.currentItem()
        if current_item is None:
            return

        subject_name = current_item.data(0, SUBJECT_NAME_ROLE)
        if isinstance(subject_name, str):
            self.select_subject(subject_name, update_tree=False)

        leaf_path = current_item.data(0, LEAF_PATH_ROLE)
        if not isinstance(leaf_path, str):
            return

        if isinstance(subject_name, str):
            self._set_current_tree_chapter(subject_name, leaf_path)
        active_chapter_tab = self._active_chapter_tab()
        if active_chapter_tab is not None:
            active_chapter_tab.focus_chapter(leaf_path)

    def select_subject(self, subject_name, *, update_tree=True, force_refresh=False):
        subject = self._find_subject(subject_name)
        if subject is None:
            return

        subject_changed = (
            not isinstance(self.selected_subject, str)
            or self.selected_subject.lower() != subject.name.lower()
        )
        self.selected_subject = subject.name

        self._set_current_tree_subject(subject.name)
        self._set_current_server_subject(subject.name)
        if subject_changed or force_refresh:
            self._refresh_subject_server_chapters()

        self._refresh_subject_views()
        if subject_changed or force_refresh:
            self._sync_task_tabs()
            self._sync_time_organizer()
            self._save_subjects()

    def _refresh_subject_views(self):
        self.setWindowTitle(
            APP_NAME
            if not self.selected_subject
            else f"{APP_NAME} - {self.selected_subject}"
        )

    def show_preferences_dialog(self):
        """Show preferences dialog with option to change data path."""
        current_path = self.preferences.get("custom_data_path") or str(self.app_state_dir)

        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        layout = QVBoxLayout(dialog)

        info_label = QLabel(
            f"<b>Data Storage Location:</b><br>{current_path}<br><br>"
            f"<b>Preferences file:</b><br>{self.preferences_path}<br><br>"
            f"<b>Subjects & chapters:</b><br>{self.subject_store_path}<br><br>"
            f"<b>Window layout:</b><br>{self.app_state_path}"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        sync_frame = QFrame(dialog)
        sync_layout = QFormLayout(sync_frame)
        sync_layout.setContentsMargins(0, 0, 0, 0)

        timer_sync_checkbox = QCheckBox("Keep timer synced with subject selection", sync_frame)
        timer_sync_checkbox.setChecked(
            bool(self.preferences.get("timer_follows_subject_selection", True))
        )
        planner_sync_checkbox = QCheckBox(
            "Keep Gantt, Calendar, and Activity Overview synced with subject selection",
            sync_frame,
        )
        planner_sync_checkbox.setChecked(
            bool(self.preferences.get("planner_follows_subject_selection", True))
        )
        subject_navigation_combo = QComboBox(sync_frame)
        subject_navigation_combo.addItem("Tree", "tree")
        subject_navigation_combo.addItem("Vertical Widgets", "vertical_widgets")
        subject_navigation_index = subject_navigation_combo.findData(self._subject_navigation_style())
        subject_navigation_combo.setCurrentIndex(subject_navigation_index if subject_navigation_index >= 0 else 0)

        sync_layout.addRow("Timer", timer_sync_checkbox)
        sync_layout.addRow("Planner", planner_sync_checkbox)
        sync_layout.addRow("Subjects", subject_navigation_combo)
        layout.addWidget(sync_frame)

        action_row = QHBoxLayout()
        change_path_btn = QPushButton("Change Data Path", dialog)
        emoji_btn = QPushButton("Manage Subject Emoji", dialog)
        open_folder_btn = QPushButton("Open Folder", dialog)
        action_row.addWidget(change_path_btn)
        action_row.addWidget(emoji_btn)
        action_row.addWidget(open_folder_btn)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        layout.addWidget(button_box)

        change_path_btn.clicked.connect(self._show_change_data_path_dialog)
        emoji_btn.clicked.connect(self.show_emoji_dialog)
        open_folder_btn.clicked.connect(self._open_data_folder)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        previous_timer_sync = bool(self.preferences.get("timer_follows_subject_selection", True))
        previous_planner_sync = bool(self.preferences.get("planner_follows_subject_selection", True))
        previous_subject_navigation_style = self._subject_navigation_style()
        self.preferences["timer_follows_subject_selection"] = timer_sync_checkbox.isChecked()
        self.preferences["planner_follows_subject_selection"] = planner_sync_checkbox.isChecked()
        self.preferences["subject_navigation_style"] = str(subject_navigation_combo.currentData())
        self._save_preferences()
        if previous_subject_navigation_style != self._subject_navigation_style():
            self._apply_subject_navigation_mode()

        if (
            self.selected_subject
            and (
                previous_timer_sync != timer_sync_checkbox.isChecked()
                or previous_planner_sync != planner_sync_checkbox.isChecked()
            )
        ):
            self._sync_time_organizer()

    def show_emoji_dialog(self):
        """Show dialog for managing subject emoji assignments."""
        dialog = SubjectEmojiDialog(self.emoji_manager, self.subjects, self)
        dialog.exec()
        # Refresh the subject tree to show updated emoji
        self._rebuild_subject_tree()

    def import_full_app_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import App Backup",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with Path(file_path).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return

        if not isinstance(payload, dict):
            QMessageBox.warning(
                self,
                "Import Failed",
                "The backup file must be a JSON object with subjects and quiz data.",
            )
            return

        self._apply_app_backup(payload)

    def _apply_app_backup(self, payload: dict):
        quiz_banks = payload.get("quiz_banks", {})
        self.subjects = self._load_subject_records(
            payload.get("subjects", []),
            backup_quiz_banks=quiz_banks,
            derive_from_storage=False,
        )

        if isinstance(quiz_banks, dict):
            for subject_name, subject_payload in quiz_banks.items():
                if not isinstance(subject_name, str) or not isinstance(subject_payload, dict):
                    continue

                subject = self._find_subject(subject_name)
                if subject is None:
                    subject = SubjectRecord(name=subject_name.strip())
                    self.subjects.append(subject)

                chapters = []
                for quiz_key in ("short_quiz", "long_quiz"):
                    chapters = self._merge_leaf_paths(
                        chapters,
                        self._collect_chapters_from_bank_payload(subject_payload.get(quiz_key)),
                    )
                merged_leaf_paths = self._merge_leaf_paths(self._subject_leaf_paths(subject), chapters)
                subject.chapters = self._subject_from_leaf_paths(subject.name, merged_leaf_paths).chapters

                subject_dir = self._quiz_bank_dir(subject.name)
                subject_dir.mkdir(parents=True, exist_ok=True)
                for quiz_key in ("short_quiz", "long_quiz"):
                    bank_payload = subject_payload.get(quiz_key)
                    if isinstance(bank_payload, dict):
                        bank_path = subject_dir / f"{quiz_key}.json"
                        try:
                            with bank_path.open("w", encoding="utf-8") as handle:
                                json.dump(bank_payload, handle, indent=2)
                        except OSError:
                            continue

        self._rebuild_subject_tree()

        stored_selected = payload.get("selected_subject")
        stored_subject = self._find_subject(stored_selected)
        if stored_subject is not None:
            self.select_subject(stored_subject.name)
        elif self.subjects:
            self.select_subject(self.subjects[0].name)
        else:
            self.selected_subject = None
            self._sync_task_tabs()

        self._save_subjects()
        self._refresh_subject_views()
        self._sync_task_tabs()
        self._sync_time_organizer()
        self._apply_time_organizer_backup(payload.get("time_organizer", {}))
        QMessageBox.information(self, "Import Complete", "App backup imported successfully.")

    def _apply_time_organizer_backup(self, payload):
        if not isinstance(payload, dict):
            return

        base_dir = self._time_organizer_root()
        base_dir.mkdir(parents=True, exist_ok=True)

        for subject_name, subject_payload in payload.items():
            if not isinstance(subject_name, str) or not isinstance(subject_payload, dict):
                continue

            subject = self._find_subject(subject_name)
            if subject is None:
                subject = SubjectRecord(name=subject_name.strip())
                self.subjects.append(subject)
                self._rebuild_subject_tree()

            subject_file = base_dir / f"{self._slugify_subject(subject.name)}.json"
            try:
                with subject_file.open("w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "subject": subject.name,
                            "selected_date": subject_payload.get("selected_date"),
                            "tasks": subject_payload.get("tasks", []),
                            "todo_items": subject_payload.get("todo_items", []),
                            "selected_timer_mode": subject_payload.get("selected_timer_mode"),
                            "custom_timer_seconds": subject_payload.get("custom_timer_seconds"),
                        },
                        handle,
                        indent=2,
                    )
            except OSError:
                continue

        self._save_subjects()
        self._sync_time_organizer()

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
                    # Replace other Unicode with underscore
                    cleaned.append('_')
            elif ch in ('-', '_', '.'):
                # Keep safe punctuation
                cleaned.append(ch)
            else:
                # Convert spaces and other characters to underscore
                cleaned.append('_')
        
        slug = ''.join(cleaned)
        # Remove multiple underscores
        while '__' in slug:
            slug = slug.replace('__', '_')
        # Remove leading/trailing underscores and dots
        return slug.strip('_.-') or 'subject'

    def closeEvent(self, event):
        if hasattr(self, "time_organizer_tab"):
            self.time_organizer_tab._flush_gantt_state_save()
        # Flush all quiz tab data to ensure persistence
        if hasattr(self, "notebook_tab") and hasattr(self.notebook_tab, "_flush_storage_save"):
            self.notebook_tab._flush_storage_save()
        if hasattr(self, "short_quiz_tab") and hasattr(self.short_quiz_tab, "_flush_storage_save"):
            self.short_quiz_tab._flush_storage_save()
        if hasattr(self, "long_quiz_tab") and hasattr(self.long_quiz_tab, "_flush_storage_save"):
            self.long_quiz_tab._flush_storage_save()
        self._save_subjects()
        self._save_app_state()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app_icon_path = Path(__file__).resolve().with_name(APP_ICON_FILENAME)
    if app_icon_path.exists():
        app.setWindowIcon(QIcon(str(app_icon_path)))
    apply_midnight_blue_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

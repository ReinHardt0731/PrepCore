"""
Dialog for managing subject emoji assignments.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
)
from app.emoji_picker_dialog import EmojiPickerDialog
from app.subject_emoji import SubjectEmojiManager, DEFAULT_SUBJECT_EMOJI


class SubjectEmojiDialog(QDialog):
    """Dialog to customize emoji assignments for subjects."""
    
    def __init__(self, emoji_manager: SubjectEmojiManager, subjects: list, parent=None):
        """
        Initialize the emoji customization dialog.
        
        Args:
            emoji_manager: SubjectEmojiManager instance
            subjects: List of SubjectRecord objects
            parent: Parent widget
        """
        super().__init__(parent)
        self.emoji_manager = emoji_manager
        self.subjects = subjects
        self.current_subject = None
        
        self.setWindowTitle("Manage Subject Emoji")
        self.setGeometry(100, 100, 500, 400)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()
        
        # Subject list
        list_label = QLabel("Subjects:")
        layout.addWidget(list_label)
        
        self.subject_list = QListWidget()
        self.subject_list.itemClicked.connect(self.on_subject_selected)
        for subject in self.subjects:
            emoji = self.emoji_manager.get_emoji_for_subject(subject.name)
            default_emoji = next(
                (v for k, v in DEFAULT_SUBJECT_EMOJI.items() if k.lower() == subject.name.lower()),
                "❓"
            )
            display = f"{emoji} {subject.name}" if emoji else f"(no emoji) {subject.name}"
            hint = f"Current: {emoji or 'none'} | Default: {default_emoji}"
            item = QListWidgetItem(display)
            item.setToolTip(hint)
            item.setData(Qt.ItemDataRole.UserRole, subject.name)
            self.subject_list.addItem(item)
        
        layout.addWidget(self.subject_list)
        
        # Emoji display and picker section
        display_layout = QHBoxLayout()
        display_layout.addWidget(QLabel("Emoji:"))
        
        # Editable emoji field
        self.emoji_display = QLineEdit()
        self.emoji_display.setPlaceholderText("Paste emoji here or pick one")
        self.emoji_display.setMaxLength(2)
        self.emoji_display.setMaximumWidth(80)
        emoji_font = QFont()
        emoji_font.setPointSize(14)
        self.emoji_display.setFont(emoji_font)
        display_layout.addWidget(self.emoji_display)
        
        pick_button = QPushButton("Pick Emoji...")
        pick_button.clicked.connect(self.pick_emoji)
        display_layout.addWidget(pick_button)
        
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_emoji_from_field)
        display_layout.addWidget(apply_button)
        
        reset_button = QPushButton("Reset to Default")
        reset_button.clicked.connect(self.reset_emoji)
        display_layout.addWidget(reset_button)
        
        display_layout.addStretch()
        layout.addLayout(display_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        reset_all_button = QPushButton("Reset All to Defaults")
        reset_all_button.clicked.connect(self.reset_all_emoji)
        button_layout.addWidget(reset_all_button)
        
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_subject_selected(self, item: QListWidgetItem):
        """Handle subject selection."""
        self.current_subject = item.data(Qt.ItemDataRole.UserRole)
        emoji = self.emoji_manager.get_emoji_for_subject(self.current_subject)
        self.emoji_display.blockSignals(True)
        self.emoji_display.setText(emoji if emoji else "")
        self.emoji_display.blockSignals(False)
    
    def pick_emoji(self):
        """Open emoji picker dialog."""
        if not self.current_subject:
            QMessageBox.warning(self, "No Subject", "Please select a subject first.")
            return
        
        current_emoji = self.emoji_manager.get_emoji_for_subject(self.current_subject)
        picker = EmojiPickerDialog(self, current_emoji)
        
        if picker.exec() == QDialog.DialogCode.Accepted:
            emoji = picker.get_selected_emoji()
            if emoji:
                self.set_emoji_for_subject(emoji)
    
    def set_emoji_for_subject(self, emoji: str):
        """Set emoji for the selected subject."""
        if not self.current_subject:
            return
        
        if self.emoji_manager.set_emoji_for_subject(self.current_subject, emoji):
            self.emoji_display.blockSignals(True)
            self.emoji_display.setText(emoji)
            self.emoji_display.blockSignals(False)
            self.refresh_list()
        else:
            QMessageBox.warning(self, "Error", "Failed to set emoji.")
    
    def apply_emoji_from_field(self):
        """Apply emoji from the editable field (copy/paste support)."""
        if not self.current_subject:
            QMessageBox.warning(self, "No Subject", "Please select a subject first.")
            return
        
        emoji = self.emoji_display.text().strip()
        
        if not emoji:
            QMessageBox.warning(self, "Empty Emoji", "Please enter or paste an emoji.")
            return
        
        # Validate emoji length (should be 1-2 characters)
        if len(emoji) > 2:
            QMessageBox.warning(self, "Invalid Emoji", "Emoji should be 1-2 characters. Please paste a single emoji.")
            self.emoji_display.clear()
            return
        
        self.set_emoji_for_subject(emoji)
    
    def reset_emoji(self):
        """Reset emoji for selected subject to default."""
        if not self.current_subject:
            QMessageBox.warning(self, "No Subject", "Please select a subject first.")
            return
        
        self.emoji_manager.remove_custom_emoji(self.current_subject)
        self.emoji_display.blockSignals(True)
        self.emoji_display.setText("")
        self.emoji_display.blockSignals(False)
        QMessageBox.information(self, "Success", f"Emoji reset to default for {self.current_subject}")
        self.refresh_list()
    
    def reset_all_emoji(self):
        """Reset all emoji to defaults."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "Reset all subject emoji to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.emoji_manager.reset_to_defaults()
            self.emoji_display.blockSignals(True)
            self.emoji_display.setText("")
            self.emoji_display.blockSignals(False)
            self.current_subject = None
            self.refresh_list()
            QMessageBox.information(self, "Success", "All emoji reset to defaults.")
    
    def refresh_list(self):
        """Refresh the subject list display."""
        self.subject_list.clear()
        for subject in self.subjects:
            emoji = self.emoji_manager.get_emoji_for_subject(subject.name)
            default_emoji = next(
                (v for k, v in DEFAULT_SUBJECT_EMOJI.items() if k.lower() == subject.name.lower()),
                "❓"
            )
            display = f"{emoji} {subject.name}" if emoji else f"(no emoji) {subject.name}"
            hint = f"Current: {emoji or 'none'} | Default: {default_emoji}"
            item = QListWidgetItem(display)
            item.setToolTip(hint)
            item.setData(Qt.ItemDataRole.UserRole, subject.name)
            self.subject_list.addItem(item)

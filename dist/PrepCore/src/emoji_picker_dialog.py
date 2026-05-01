"""
Emoji picker dialog for easy emoji selection.
Provides a visual grid of emoji to choose from.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGridLayout,
    QPushButton,
    QWidget,
    QScrollArea,
    QSpacerItem,
)
from PySide6.QtGui import QFont

# Comprehensive outline/symbol emoji collection organized by category
# Using outline and symbol emoji for clean monochrome appearance
EMOJI_CATEGORIES = {
    "Travel & Places": [
        "✈", "🛩", "🛫", "🛬", "🚁", "🚂", "🚃", "🚄",
        "🚅", "🚆", "🚇", "🚈", "⛴", "🚢", "🚤", "⛵",
        "🛥", "🛳", "🚀", "🛸", "🚁", "⛑", "🛴", "🛵",
        "🏎", "🏍", "🛺", "🚲", "🚚", "🚛", "🚜", "⛽",
        "🚧", "⛺", "🏕", "⛺", "🏖", "🏝", "🗺", "🧭",
        "🌍", "🌎", "🌏", "🗼", "🗽", "🗿", "⛩", "🕌",
    ],
    "Objects & Tools": [
        "⚙", "⚒", "🛠", "⛏", "⚒", "🔨", "⚒", "🔩",
        "⚖", "⛓", "🧰", "🔧", "🪛", "🪚", "⚒", "🪓",
        "🔗", "⛓", "🧱", "⛓", "🧲", "🔫", "💣", "🧨",
        "🪃", "🎯", "🎲", "♠", "♥", "♦", "♣", "♟",
        "🎭", "🎨", "🎬", "🎤", "🎧", "🎼", "🎹", "🥁",
        "🎷", "🎺", "🎸", "🎻", "🎲", "♟", "🎯", "🎳",
    ],
    "Science & Tech": [
        "⚗", "⚗", "🧪", "⚗", "🔍", "🔎", "💡", "🔦",
        "🕯", "📔", "📕", "📖", "📗", "📘", "📙", "📚",
        "📓", "📒", "📰", "📑", "📜", "🧾", "📄", "📃",
        "📂", "📁", "📧", "📨", "📩", "📤", "📥", "💻",
        "🖥", "🖨", "⌨", "🖱", "🖲", "💾", "💿", "📀",
        "🧮", "🎥", "🎞", "📽", "📺", "📷", "📸", "📹",
    ],
    "Nature & Animals": [
        "🌿", "☘", "🍀", "🌾", "🌱", "🌿", "☘", "🍀",
        "🌳", "🌲", "🌴", "🌵", "🌷", "🌹", "🥀", "🌺",
        "🌻", "🌼", "🌸", "💐", "🦁", "🐯", "🐻", "🐼",
        "🐨", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻",
        "🐮", "🐷", "🐽", "🐸", "🐵", "🙈", "🙉", "🙊",
        "🐒", "🐔", "🐧", "🦆", "🦅", "🦉", "🦇", "🐛",
    ],
    "Food & Drink": [
        "🍎", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈",
        "🍒", "🍑", "🥭", "🍍", "🥥", "🥑", "🍆", "🍅",
        "🌶", "🌽", "🥕", "🥔", "🍠", "🥐", "🥯", "🍞",
        "🥖", "🥨", "🧀", "🍗", "🍖", "🌭", "🍔", "🍟",
        "🍕", "🥪", "🥙", "🧆", "🌮", "🌯", "🥗", "🥘",
        "🍝", "🍜", "🍲", "🍛", "🍣", "🍱", "🥟", "🦪",
    ],
    "Activity & Sports": [
        "⚽", "🏀", "🏈", "⚾", "🥎", "🎾", "🏐", "🏉",
        "🥏", "🎳", "🏓", "🏸", "🏒", "🏑", "🥍", "🏌",
        "⛳", "🌾", "⛸", "🎣", "🎽", "🎿", "⛷", "🏂",
        "🪂", "🏋", "🤼", "🤸", "⛹", "🏌", "🏇", "🧘",
        "🏄", "🏊", "🤽", "🚣", "🧗", "🚴", "🚵", "🎯",
        "🎪", "🎨", "🎭", "🎬", "🎤", "🎧", "🎼", "🎹",
    ],
    "Weather & Symbols": [
        "☀", "🌤", "⛅", "🌥", "☁", "🌦", "🌧", "⛈",
        "🌩", "🌨", "❄", "☃", "⛄", "🌬", "💨", "💧",
        "💦", "☔", "☂", "🌊", "🌫", "⚡", "🌪", "🌈",
        "☄", "💥", "🔥", "⭐", "✨", "⚠", "🚨", "🚧",
        "☢", "☣", "🛑", "⛔", "🚫", "🚷", "🚯", "🚱",
        "🚳", "↔", "↕", "🔄", "➡", "⬅", "⬆", "⬇",
    ],
    "Smileys & People": [
        "☺", "☹", "🙂", "🙃", "😐", "😑", "😶", "🤫",
        "😏", "😒", "🙁", "☹", "😲", "😞", "😖", "😢",
        "😭", "😤", "😠", "😡", "🤬", "😈", "👿", "💀",
        "☠", "💩", "🤡", "👹", "👺", "👻", "👽", "👾",
        "🤖", "😺", "😸", "😹", "😻", "😼", "😽", "😾",
        "😿", "🙀", "👋", "🤚", "🖐", "✋", "🖖", "👌",
    ],
}

class EmojiPickerDialog(QDialog):
    """Dialog for visually selecting emoji from categories."""
    
    emoji_selected = Signal(str)  # Signal emitted when emoji is selected
    
    def __init__(self, parent=None, selected_emoji: str = ""):
        """
        Initialize the emoji picker dialog.
        
        Args:
            parent: Parent widget
            selected_emoji: Currently selected emoji (optional)
        """
        super().__init__(parent)
        self.selected_emoji = selected_emoji
        
        self.setWindowTitle("Pick an Emoji")
        self.setGeometry(100, 100, 600, 600)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout()
        
        # Category buttons
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Categories:"))
        
        self.category_buttons = {}
        for category in EMOJI_CATEGORIES.keys():
            btn = QPushButton(category)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, c=category: self.show_category(c))
            self.category_buttons[category] = btn
            category_layout.addWidget(btn)
        
        category_layout.addStretch()
        layout.addLayout(category_layout)
        
        # Emoji grid (scrollable)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.emoji_container = QWidget()
        self.emoji_grid = QGridLayout(self.emoji_container)
        self.emoji_grid.setSpacing(5)
        
        self.scroll_area.setWidget(self.emoji_container)
        layout.addWidget(self.scroll_area)
        
        # Selected emoji display
        display_layout = QHBoxLayout()
        display_layout.addWidget(QLabel("Selected:"))
        self.emoji_display = QLabel(self.selected_emoji or "None")
        display_font = QFont()
        display_font.setPointSize(24)
        self.emoji_display.setFont(display_font)
        display_layout.addWidget(self.emoji_display)
        display_layout.addStretch()
        layout.addLayout(display_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Show first category by default
        if EMOJI_CATEGORIES:
            first_category = list(EMOJI_CATEGORIES.keys())[0]
            self.show_category(first_category)
    
    def show_category(self, category: str):
        """Display emoji for the selected category."""
        # Clear previous layout
        while self.emoji_grid.count():
            child = self.emoji_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Update button states
        for cat, btn in self.category_buttons.items():
            btn.setChecked(cat == category)
        
        # Add emoji buttons for this category
        emoji_list = EMOJI_CATEGORIES.get(category, [])
        col = 0
        row = 0
        
        for emoji in emoji_list:
            btn = QPushButton(emoji)
            btn.setFixedSize(50, 50)
            font = QFont()
            font.setPointSize(20)
            btn.setFont(font)
            btn.clicked.connect(lambda checked, e=emoji: self.select_emoji(e))
            
            # Highlight if this emoji is selected
            if emoji.rstrip('\uFE0E\uFE0F') == self.selected_emoji.rstrip('\uFE0E\uFE0F'):
                btn.setStyleSheet("background-color: #4a9eff; border: 2px solid #2a7edf;")
            
            self.emoji_grid.addWidget(btn, row, col)
            
            col += 1
            if col >= 8:
                col = 0
                row += 1
        
        # Add stretch to expand empty space below
        self.emoji_grid.setRowStretch(row + 1, 1)
    
    def select_emoji(self, emoji: str):
        """Handle emoji selection."""
        self.selected_emoji = emoji
        self.emoji_display.setText(emoji)
        
        # Update button highlights in current category
        for i in range(self.emoji_grid.count()):
            item = self.emoji_grid.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QPushButton):
                btn = item.widget()
                if btn.text().rstrip('\uFE0E\uFE0F') == emoji.rstrip('\uFE0E\uFE0F'):
                    btn.setStyleSheet("background-color: #4a9eff; border: 2px solid #2a7edf;")
                else:
                    btn.setStyleSheet("")
        
        self.emoji_selected.emit(emoji)
    
    def get_selected_emoji(self) -> str:
        """Get the selected emoji."""
        return self.selected_emoji

"""
Tree Font Utilities
Provides helper functions to apply dynamic font sizing to tree items based on hierarchy level.
Creates a modern, visually hierarchical tree structure.
"""

import re
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTreeWidgetItem
from PySide6.QtCore import Qt


class TreeFontConfig:
    """Configuration for tree font sizes and styles."""
    
    # Font sizes for different hierarchy levels
    LEVEL_0_SIZE = 11.5  # Subjects/roots - largest
    LEVEL_1_SIZE = 11  # Chapters/groups - medium
    LEVEL_2_SIZE = 10  # Subchapters/items - smallest
    
    # Specialized sizes for quiz and notebook
    QUIZ_CHAPTER_SIZE = 10.5      # Chapter in quiz/notebook
    QUIZ_SUBCHAPTER_SIZE = 9.5  # Subchapter in quiz/notebook
    
    # Question and choice sizes for quizzes
    QUESTION_TEXT_SIZE = 12   # Question text - larger
    CHOICE_TEXT_SIZE = 9.5     # Answer choice text - smaller
    
    # Font weight for hierarchy emphasis (all normal, no bold)
    LEVEL_0_WEIGHT = QFont.Weight.Bold
    LEVEL_1_WEIGHT = QFont.Weight.Normal
    LEVEL_2_WEIGHT = QFont.Weight.Normal
    
    # Font family (system default)
    FONT_FAMILY = "Segoe UI"  # Professional, clean font


def apply_hierarchical_font_to_item(item: QTreeWidgetItem, level: int = 0) -> None:
    """
    Apply font styling to a tree item based on its hierarchy level.
    
    Args:
        item: The QTreeWidgetItem to style
        level: The hierarchy level (0 = root/subject, 1 = chapter, 2 = subchapter)
    """
    font = QFont()
    
    if level == 0:
        font.setPointSize(TreeFontConfig.LEVEL_0_SIZE)
        font.setWeight(TreeFontConfig.LEVEL_0_WEIGHT)
    elif level == 1:
        font.setPointSize(TreeFontConfig.LEVEL_1_SIZE)
        font.setWeight(TreeFontConfig.LEVEL_1_WEIGHT)
    else:  # level 2 or deeper
        font.setPointSize(TreeFontConfig.LEVEL_2_SIZE)
        font.setWeight(TreeFontConfig.LEVEL_2_WEIGHT)
    
    item.setFont(0, font)


def apply_fonts_to_tree_item_and_children(root_item: QTreeWidgetItem) -> None:
    """
    Recursively apply hierarchical fonts to an item and all its children.
    Automatically determines hierarchy level based on depth.
    
    Args:
        root_item: The root QTreeWidgetItem to style (treated as level 0)
    """
    def apply_recursive(item: QTreeWidgetItem, level: int = 0) -> None:
        apply_hierarchical_font_to_item(item, level)
        for i in range(item.childCount()):
            child = item.child(i)
            apply_recursive(child, level + 1)
    
    apply_recursive(root_item, level=0)


def set_item_level_font(item: QTreeWidgetItem, level: int) -> None:
    """
    Wrapper function for apply_hierarchical_font_to_item for cleaner API.
    
    Args:
        item: The QTreeWidgetItem to style
        level: The hierarchy level (0 = root/subject, 1 = chapter, 2 = subchapter)
    """
    apply_hierarchical_font_to_item(item, level)


def apply_font_to_item(item: QTreeWidgetItem, size_pt: float) -> None:
    """
    Apply a specific font size to a tree item with normal weight.
    
    Args:
        item: The QTreeWidgetItem to style
        size_pt: Font size in points
    """
    font = QFont()
    font.setPointSize(size_pt)
    font.setWeight(QFont.Weight.Normal)
    item.setFont(0, font)


def apply_font_to_widget(widget, size_pt: float, weight: QFont.Weight = QFont.Weight.Normal) -> None:
    """
    Apply a specific font size to a widget (QLabel, QRadioButton, etc.) with specified weight.
    Uses stylesheet to override global stylesheet font-size.
    
    Args:
        widget: The widget to style (QLabel, QRadioButton, QPushButton, etc.)
        size_pt: Font size in points
        weight: Font weight (default: Normal)
    """
    font = QFont()
    font.setPointSize(size_pt)
    font.setWeight(weight)
    widget.setFont(font)
    
    # Override global stylesheet by setting font-size via stylesheet
    # This ensures the font size is applied despite global stylesheets
    current_stylesheet = widget.styleSheet()
    weight_str = "bold" if weight == QFont.Weight.Bold else "normal"
    
    # Remove any existing font-size and font-weight to avoid duplication
    cleaned_stylesheet = re.sub(r'font-size:\s*[\d.]+pt;?', '', current_stylesheet)
    cleaned_stylesheet = re.sub(r'font-weight:\s*\w+;?', '', cleaned_stylesheet)
    
    # Append new font properties
    new_stylesheet = f"{cleaned_stylesheet} font-size: {int(size_pt)}pt; font-weight: {weight_str};"
    widget.setStyleSheet(new_stylesheet)

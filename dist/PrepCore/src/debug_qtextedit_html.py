#!/usr/bin/env python3
"""Debug: Show the complete HTML that QTextEdit produces."""

import sys
import base64
from pathlib import Path
from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QBuffer

app = QApplication.instance() or QApplication(sys.argv)

# Create a test editor
editor = QTextEdit()

# Create test image
test_pixmap = QPixmap(200, 150)
test_pixmap.fill(Qt.GlobalColor.red)

# Encode to base64
img_buffer = QBuffer()
img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
test_pixmap.save(img_buffer, "PNG")
img_data = img_buffer.data()
encoded = base64.b64encode(img_data).decode("ascii")[:100]  # Just first 100 chars for display

# Create test image HTML
test_html = (
    f'<img src="data:image/png;base64,{encoded}..." '
    f'style="width: 150px; float: left; margin: 8px 12px 8px 0; cursor: move;" '
    f'alt="testimage" '
    f'title="Double-click to resize">'
)

print("="*80)
print("INPUT HTML (what we send to QTextEdit):")
print("="*80)
print(test_html)
print()

# Insert the HTML
editor.clear()
editor.insertHtml("Text before ")
editor.insertHtml(test_html)
editor.insertHtml(" Text after")

# Get the HTML back
output_html = editor.toHtml()

# Find the img tag
img_start = output_html.find("<img")
if img_start >= 0:
    img_end = output_html.find(">", img_start) + 1
    img_tag = output_html[img_start:img_end]
    
    print("="*80)
    print("OUTPUT HTML (what QTextEdit produces):")
    print("="*80)
    print(img_tag)
    print()
    
    # Show the full HTML for analysis
    print("="*80)
    print("FULL HTML DOCUMENT:")
    print("="*80)
    print(output_html[:2000])
else:
    print("No img tag found!")

sys.exit(0)

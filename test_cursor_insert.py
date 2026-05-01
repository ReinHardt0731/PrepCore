#!/usr/bin/env python3
"""Test CSS preservation when using textCursor().insertHtml() like the real code."""

import sys
import re
from PySide6.QtWidgets import QApplication, QTextEdit

def test_real_scenario():
    """Test CSS preservation using the actual insertion method."""
    app = QApplication.instance() or QApplication(sys.argv)
    editor = QTextEdit()
    
    test_cases = [
        ("left float", 'style="float: left; margin: 8px 12px 8px 0; cursor: move;"'),
        ("center display", 'style="display: block; margin: 8px auto; cursor: move;"'),
        ("inline margin", 'style="margin: 2px 4px; vertical-align: middle; cursor: move;"'),
    ]
    
    print("\n" + "="*70)
    print("Testing CSS Preservation with textCursor().insertHtml()")
    print("="*70)
    
    for name, style_attr in test_cases:
        editor.clear()
        cursor = editor.textCursor()
        
        # Create HTML like the real code does
        img_html = (
            f'<img src="data:image/png;base64,iVBORw0KG..." '
            f'width="100" '
            f'{style_attr} '
            f'alt="test" '
            f'title="Double-click to resize">'
        )
        
        cursor.insertHtml(img_html)
        
        # Get the HTML
        html = editor.toHtml()
        
        # Find the img tag
        img_match = re.search(r'<img[^>]*?>', html, re.IGNORECASE | re.DOTALL)
        if img_match:
            img_tag = img_match.group(0)
            
            # Extract style
            style_match = re.search(r'style="([^"]*?)"', img_tag, re.IGNORECASE)
            output_style = style_match.group(1) if style_match else "[NO STYLE]"
        else:
            img_tag = "[IMG NOT FOUND]"
            output_style = "[IMG NOT FOUND]"
        
        print(f"\n{name}:")
        print(f"  Input style:  {style_attr}")
        print(f"  Output style: {output_style}")
        print(f"  Full img tag: {img_tag[:120]}...")

if __name__ == "__main__":
    test_real_scenario()

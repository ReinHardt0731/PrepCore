#!/usr/bin/env python3
"""Test which CSS properties QTextEdit preserves."""

import sys
from PySide6.QtWidgets import QApplication, QTextEdit

def test_css_preservation():
    """Test what CSS properties survive QTextEdit's HTML parsing."""
    app = QApplication.instance() or QApplication(sys.argv)
    editor = QTextEdit()
    
    test_styles = [
        ("float: left", 'style="float: left;"'),
        ("display: block", 'style="display: block;"'),
        ("text-align: center", 'style="text-align: center;"'),
        ("margin: auto", 'style="margin: auto;"'),
        ("combined float+display", 'style="float: left; display: block;"'),
        ("combined text-align+display", 'style="text-align: center; display: block;"'),
        ("margin with units", 'style="margin: 8px auto 8px;"'),
    ]
    
    print("\n" + "="*70)
    print("Testing CSS Property Preservation in QTextEdit")
    print("="*70)
    
    for name, style_attr in test_styles:
        editor.clear()
        # Insert a test element
        test_html = f'<img src="test.png" alt="test" {style_attr} />'
        editor.insertHtml(test_html)
        
        # Get the HTML back
        html = editor.toHtml()
        
        # Extract the style attribute
        import re
        style_match = re.search(r'style="([^"]*?)"', html)
        preserved_style = style_match.group(1) if style_match else "[NO STYLE FOUND]"
        
        print(f"\n{name}:")
        print(f"  Input:  {style_attr}")
        print(f"  Output: style=\"{preserved_style}\"")
        print(f"  Preserved: {preserved_style == style_attr.strip('style=\"').rstrip('\"')}")

if __name__ == "__main__":
    test_css_preservation()

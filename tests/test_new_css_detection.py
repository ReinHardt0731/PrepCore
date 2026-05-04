#!/usr/bin/env python3
"""Test CSS preservation with the NEW CSS properties (float, text-align, vertical-align)."""

import sys
import re
from PySide6.QtWidgets import QApplication, QTextEdit

def test_new_css_preservation():
    """Test CSS preservation using the NEW styles."""
    app = QApplication.instance() or QApplication(sys.argv)
    editor = QTextEdit()
    
    test_cases = [
        ("left", 'style="float: left;"', "left"),
        ("right", 'style="float: right;"', "right"),
        ("center", 'style="text-align: center;"', "center"),
        ("inline", 'style="vertical-align: middle;"', "none"),
    ]
    
    print("\n" + "="*70)
    print("Testing NEW CSS Properties - Wrap Mode Detection")
    print("="*70)
    
    all_passed = True
    
    for name, style_attr, expected_wrap in test_cases:
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
            output_style = style_match.group(1) if style_match else ""
        else:
            img_tag = "[IMG NOT FOUND]"
            output_style = ""
            all_passed = False
        
        # Detect wrap mode using the same logic as outline_tab.py
        detected_wrap = "none"  # default
        if "float: left" in output_style:
            detected_wrap = "left"
        elif "float: right" in output_style:
            detected_wrap = "right"
        elif "text-align: center" in output_style:
            detected_wrap = "center"
        elif "vertical-align: middle" in output_style:
            detected_wrap = "none"
        
        passed = detected_wrap == expected_wrap
        status = "✓" if passed else "✗"
        
        print(f"\n{status} {name}:")
        print(f"    CSS preserved: {output_style}")
        print(f"    Expected wrap: {expected_wrap}")
        print(f"    Detected wrap: {detected_wrap}")
        
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Wrap mode detection is working!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_new_css_preservation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

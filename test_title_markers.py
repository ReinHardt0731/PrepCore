#!/usr/bin/env python3
"""Test wrap mode detection using Unicode markers in title attribute."""

import sys
import re
from PySide6.QtWidgets import QApplication, QTextEdit

def test_marker_detection():
    """Test wrap mode detection using title markers."""
    app = QApplication.instance() or QApplication(sys.argv)
    editor = QTextEdit()
    
    test_cases = [
        ("left", 'title="Double-click to resize◊"', "◊", "left"),
        ("right", 'title="Double-click to resize◆"', "◆", "right"),
        ("center", 'title="Double-click to resize◈"', "◈", "center"),
        ("inline", 'title="Double-click to resize"', "", "none"),
    ]
    
    print("\n" + "="*70)
    print("Testing Wrap Mode Detection with Unicode Markers in Title")
    print("="*70)
    
    all_passed = True
    
    for name, title_attr, marker, expected_wrap in test_cases:
        editor.clear()
        cursor = editor.textCursor()
        
        # Create HTML like the real code does
        img_html = (
            f'<img src="data:image/png;base64,iVBORw0KG..." '
            f'width="100" '
            f'style="float: left;" '
            f'alt="test" '
            f'{title_attr}>'
        )
        
        cursor.insertHtml(img_html)
        
        # Get the HTML
        html = editor.toHtml()
        
        # Find the img tag
        img_match = re.search(r'<img[^>]*?>', html, re.IGNORECASE | re.DOTALL)
        if img_match:
            img_tag = img_match.group(0)
            
            # Extract title
            title_match = re.search(r'title="([^"]*?)"', img_tag, re.IGNORECASE)
            extracted_title = title_match.group(1) if title_match else ""
        else:
            img_tag = "[IMG NOT FOUND]"
            extracted_title = ""
            all_passed = False
        
        # Detect wrap mode using title markers
        detected_wrap = "none"  # default
        if "◈" in extracted_title:
            detected_wrap = "center"
        elif "◊" in extracted_title:
            detected_wrap = "left"
        elif "◆" in extracted_title:
            detected_wrap = "right"
        
        passed = detected_wrap == expected_wrap
        status = "✓" if passed else "✗"
        
        print(f"\n{status} {name}:")
        print(f"    Marker in title: {marker if marker else '(none)'}")
        print(f"    Extracted title: {extracted_title}")
        print(f"    Expected wrap: {expected_wrap}")
        print(f"    Detected wrap: {detected_wrap}")
        
        if not passed:
            all_passed = False
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Title marker detection is working!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_marker_detection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

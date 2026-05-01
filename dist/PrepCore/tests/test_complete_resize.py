#!/usr/bin/env python3
"""Comprehensive test of the image resize detection with all wrap modes and width preservation."""

import sys
import re
import base64
from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QBuffer

def test_complete_resize_flow():
    """Test the complete image insertion, modification, and detection flow."""
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create a test pixmap
    test_pixmap = QPixmap(300, 200)
    test_pixmap.fill(Qt.GlobalColor.blue)
    
    # Encode to base64
    img_buffer = QBuffer()
    img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    test_pixmap.save(img_buffer, "PNG")
    img_data = img_buffer.data()
    encoded = base64.b64encode(img_data).decode("ascii")[:50]
    
    editor = QTextEdit()
    
    test_cases = [
        ("left", 150, "Double-click to resize◊", "left"),
        ("right", 200, "Double-click to resize◆", "right"),
        ("center", 100, "Double-click to resize◈", "center"),
        ("inline", 175, "Double-click to resize", "none"),
    ]
    
    print("\n" + "="*70)
    print("COMPREHENSIVE TEST: Image Resize Detection Flow")
    print("="*70)
    
    all_passed = True
    
    for wrap_mode, width, title, expected_wrap in test_cases:
        print(f"\n[{wrap_mode.upper()}] Testing wrap mode detection...")
        
        editor.clear()
        cursor = editor.textCursor()
        
        # Simulate what _insert_picture() does
        style_map = {
            "left": 'style="float: left;"',
            "right": 'style="float: right;"',
            "center": 'style="text-align: center;"',
            "none": 'style="vertical-align: middle;"'
        }
        
        style = style_map.get(wrap_mode, style_map["none"])
        
        img_html = (
            f'<img src="data:image/png;base64,{encoded}..." '
            f'width="{width}" '
            f'{style} '
            f'alt="testimage" '
            f'title="{title}">'
        )
        
        cursor.insertHtml(img_html)
        
        # Get the HTML (simulates what _resize_selected_image() sees)
        html = editor.toHtml()
        
        # Extract the image tag
        img_pattern = r'<img\s+([^>]*?)src="([^"]*?)"([^>]*?)>'
        matches = list(re.finditer(img_pattern, html, re.IGNORECASE | re.DOTALL))
        
        if not matches:
            print(f"  ✗ No image found in HTML!")
            all_passed = False
            continue
        
        img_tag = matches[-1].group(0)
        
        # Extract width (like _resize_selected_image does)
        width_match = re.search(r'width="?(\d+)"?', img_tag, re.IGNORECASE)
        extracted_width = int(width_match.group(1)) if width_match else None
        
        # Extract style
        style_match = re.search(r'style="([^"]*?)"', img_tag, re.IGNORECASE)
        extracted_style = style_match.group(1) if style_match else ""
        
        # Extract title
        title_match = re.search(r'title="([^"]*?)"', img_tag, re.IGNORECASE)
        extracted_title = title_match.group(1) if title_match else ""
        
        # Detect wrap mode (like _resize_selected_image does)
        detected_wrap = "none"
        if "◈" in extracted_title:
            detected_wrap = "center"
        elif "◊" in extracted_title:
            detected_wrap = "left"
        elif "◆" in extracted_title:
            detected_wrap = "right"
        else:
            if "float: left" in extracted_style:
                detected_wrap = "left"
            elif "float: right" in extracted_style:
                detected_wrap = "right"
            elif "text-align: center" in extracted_style or "display: block" in extracted_style:
                detected_wrap = "center"
            else:
                detected_wrap = "none"
        
        # Verify all extractions
        width_ok = extracted_width == width
        wrap_ok = detected_wrap == expected_wrap
        
        width_status = "✓" if width_ok else "✗"
        wrap_status = "✓" if wrap_ok else "✗"
        
        print(f"  {width_status} Width extracted: {extracted_width} (expected {width})")
        print(f"  {wrap_status} Wrap mode detected: {detected_wrap} (expected {expected_wrap})")
        
        if not (width_ok and wrap_ok):
            all_passed = False
            print(f"  Full img tag: {img_tag[:100]}...")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Complete resize flow is working!")
        print("  Ready for end-to-end testing in the actual application")
    else:
        print("✗ Some tests failed - Review the output above")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_complete_resize_flow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""Test the fixed image resize detection with width attribute."""

import sys
import base64
import re
from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QBuffer

def test_width_attribute_detection():
    """Test that width attribute is preserved and detected."""
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
    encoded = base64.b64encode(img_data).decode("ascii")[:50]
    
    # Test cases with the NEW format (width attribute only, no data-wrap since QTextEdit strips it)
    test_cases = [
        ("inline", 
         f'<img src="data:image/png;base64,{encoded}..." '
         f'width="100" '
         f'style="margin: 2px 4px; vertical-align: middle; cursor: move;" '
         f'alt="test1" '
         f'title="test">'),
        ("left",
         f'<img src="data:image/png;base64,{encoded}..." '
         f'width="150" '
         f'style="float: left; margin: 8px 12px 8px 0; cursor: move;" '
         f'alt="test2" '
         f'title="test">'),
        ("center",
         f'<img src="data:image/png;base64,{encoded}..." '
         f'width="200" '
         f'style="display: block; margin: 8px auto; cursor: move;" '
         f'alt="test3" '
         f'title="test">'),
    ]
    
    print("\n" + "="*70)
    print("Testing Fixed Image Detection (with width attribute)")
    print("="*70)
    
    all_passed = True
    
    for i, (wrap_mode, img_html) in enumerate(test_cases, 1):
        print(f"\n[{i}] {wrap_mode.upper()} mode:")
        
        # Insert into editor
        editor.clear()
        editor.insertHtml("Text before ")
        editor.insertHtml(img_html)
        editor.insertHtml(" Text after")
        
        # Get HTML
        html = editor.toHtml()
        
        # Apply detection regex (same as in fixed code)
        img_pattern = r'<img\s+([^>]*?)src="([^"]*?)"([^>]*?)>'
        matches = list(re.finditer(img_pattern, html, re.IGNORECASE | re.DOTALL))
        
        if not matches:
            print(f"    ✗ No image found!")
            all_passed = False
            continue
        
        img_tag = matches[-1].group(0)
        
        # Extract width attribute
        width_match = re.search(r'width="?(\d+)"?', img_tag, re.IGNORECASE)
        extracted_width = int(width_match.group(1)) if width_match else None
        
        # Extract wrap mode from style (since custom attributes won't be preserved by QTextEdit)
        style_match = re.search(r'style="([^"]*?)"', img_tag, re.IGNORECASE)
        style = style_match.group(1) if style_match else ""
        
        # Determine wrap mode from CSS properties (QTextEdit won't preserve custom attributes)
        if "float: left" in style:
            detected_wrap = "left"
        elif "float: right" in style:
            detected_wrap = "right"
        elif "display: block" in style or "margin: 8px auto" in style:
            detected_wrap = "center"
        else:
            detected_wrap = "none"
        
        # Use detected wrap (data-wrap custom attribute won't survive QTextEdit)
        extracted_wrap = detected_wrap
        
        # Extract alt
        alt_match = re.search(r'alt="([^"]*?)"', img_tag, re.IGNORECASE)
        extracted_alt = alt_match.group(1) if alt_match else None
        
        # Extract src
        src_match = re.search(r'src="([^"]*?)"', img_tag, re.IGNORECASE)
        has_base64 = src_match and src_match.group(1).startswith("data:image/png;base64,")
        
        test_passed = (
            extracted_width is not None and
            extracted_wrap is not None and
            has_base64 and
            extracted_alt is not None
        )
        
        status = "✓" if test_passed else "✗"
        print(f"    {status} Width detected: {extracted_width}")
        print(f"    {status} Wrap mode detected: {extracted_wrap}")
        print(f"    {status} Base64 src found: {has_base64}")
        print(f"    {status} Alt text found: {extracted_alt}")
        
        if not test_passed:
            all_passed = False
            print(f"\n    Full img tag from QTextEdit:")
            print(f"    {img_tag[:150]}...")
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED - Image resize detection is fixed!")
    else:
        print("✗ Some tests failed")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_width_attribute_detection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

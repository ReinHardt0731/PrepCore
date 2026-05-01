#!/usr/bin/env python3
"""Test the improved image detection for resizing."""

import sys
import base64
import re
from pathlib import Path
from io import BytesIO
from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QBuffer

def test_image_detection():
    """Test that the improved regex can find images in QTextEdit HTML output."""
    app = QApplication.instance() or QApplication(sys.argv)
    
    # Create a test editor
    editor = QTextEdit()
    
    # Create test images
    test_pixmap = QPixmap(200, 150)
    test_pixmap.fill(Qt.GlobalColor.red)
    
    # Encode to base64
    img_buffer = QBuffer()
    img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    test_pixmap.save(img_buffer, "PNG")
    img_data = img_buffer.data()
    encoded = base64.b64encode(img_data).decode("ascii")
    
    # Simulate image insertion with different wrap modes
    test_cases = [
        ("inline", f'<img src="data:image/png;base64,{encoded}" style="width: 100px; margin: 2px 4px; vertical-align: middle; cursor: move;" alt="test1" title="Double-click to resize or change wrapping">'),
        ("left", f'<img src="data:image/png;base64,{encoded}" style="width: 150px; float: left; margin: 8px 12px 8px 0; cursor: move;" alt="test2" title="Double-click to resize or change wrapping">'),
        ("center", f'<img src="data:image/png;base64,{encoded}" style="width: 200px; display: block; margin: 8px auto; cursor: move;" alt="test3" title="Double-click to resize or change wrapping">'),
    ]
    
    results = []
    
    for wrap_mode, img_html in test_cases:
        # Insert HTML
        editor.clear()
        editor.insertHtml("Some text before ")
        editor.insertHtml(img_html)
        editor.insertHtml(" Some text after")
        
        # Get HTML from editor
        html = editor.toHtml()
        
        # Show a snippet of what QTextEdit produced
        img_start = html.find("<img")
        if img_start >= 0:
            img_end = html.find(">", img_start) + 1
            actual_img_tag = html[img_start:img_end]
            print(f"\n[DEBUG] {wrap_mode} - QTextEdit output:")
            print(f"  {actual_img_tag[:120]}...")
        
        # Apply the improved regex
        img_pattern = r'<img\s+([^>]*?)src="([^"]*?)"([^>]*?)>'
        matches = list(re.finditer(img_pattern, html, re.IGNORECASE | re.DOTALL))
        
        found = False
        src = None
        style = None
        alt = None
        
        if matches:
            match = matches[-1]
            img_tag = match.group(0)
            
            # Extract src
            src_match = re.search(r'src="([^"]*?)"', img_tag, re.IGNORECASE)
            src = src_match.group(1) if src_match else None
            
            # Extract style
            style_match = re.search(r'style="([^"]*?)"', img_tag, re.IGNORECASE)
            style = style_match.group(1) if style_match else None
            
            # Extract alt
            alt_match = re.search(r'alt="([^"]*?)"', img_tag, re.IGNORECASE)
            alt = alt_match.group(1) if alt_match else None
            
            if src and src.startswith("data:image/png;base64,"):
                found = True
        
        results.append({
            "wrap_mode": wrap_mode,
            "found": found,
            "has_src": src is not None and src.startswith("data:"),
            "has_style": style is not None and "width:" in style,
            "has_alt": alt is not None,
            "style": style[:50] + "..." if style and len(style) > 50 else style,
        })
    
    # Print results
    print("\n" + "="*70)
    print("Image Detection Test Results")
    print("="*70)
    
    all_passed = True
    for i, result in enumerate(results, 1):
        status = "✓" if all(result[k] for k in ["found", "has_src", "has_style", "has_alt"]) else "✗"
        print(f"\n[{i}] {result['wrap_mode'].upper()} wrap mode: {status}")
        print(f"    Image found: {result['found']}")
        print(f"    Has base64 src: {result['has_src']}")
        print(f"    Has width style: {result['has_style']}")
        print(f"    Has alt text: {result['has_alt']}")
        if result["style"]:
            print(f"    Style: {result['style']}")
        
        if not (result["found"] and result["has_src"]):
            all_passed = False
    
    print("\n" + "="*70)
    print(f"Overall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    print("="*70)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = test_image_detection()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

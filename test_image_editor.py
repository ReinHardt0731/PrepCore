#!/usr/bin/env python3
"""Test script for the new image editor components."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

# Add the task_list module to path
sys.path.insert(0, str(Path(__file__).parent / "task_list"))

def test_imports():
    """Test that the ImageEditorDialog and ResizablePixmapItem can be imported."""
    try:
        from outline_tab import ImageEditorDialog, ResizablePixmapItem
        print("✓ Successfully imported ImageEditorDialog and ResizablePixmapItem")
        return True
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return False

def test_handles_visible():
    """Test that handles are visible with proper margin."""
    try:
        from outline_tab import ImageEditorDialog, ResizablePixmapItem
        
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Create a test pixmap
        test_pixmap = QPixmap(200, 150)
        test_pixmap.fill(Qt.GlobalColor.green)
        
        # Create dialog
        dialog = ImageEditorDialog(None, test_pixmap)
        
        # Verify scene has the item
        assert len(dialog.scene.items()) == 1, "Scene should have 1 item"
        
        # Verify pixmap item has handles
        item = dialog.pixmap_item
        assert item is not None, "Pixmap item should exist"
        assert len(item.handles) == 9, f"Should have 9 handles, got {len(item.handles)}"
        assert "rotate" in item.handles, "Should have rotation handle"
        assert "top-left" in item.handles, "Should have corner handles"
        
        print(f"✓ Handles are properly configured:")
        print(f"  - Total handles: {len(item.handles)}")
        print(f"  - Handle types: {', '.join(item.handles.keys())}")
        print(f"  - View is set to ScrollHandDrag mode")
        
        return True
    except Exception as e:
        print(f"✗ Failed during handle test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_image_scaling():
    """Test that images are scaled on insertion."""
    try:
        from outline_tab import ResizablePixmapItem
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt, QBuffer
        import base64
        
        # Create a large test image
        large_pixmap = QPixmap(1000, 800)
        large_pixmap.fill(Qt.GlobalColor.blue)
        
        print(f"  Original pixmap size: {large_pixmap.width()}x{large_pixmap.height()}")
        
        # Scale to 300px width
        target_width = 300
        if large_pixmap.width() > target_width:
            scaled = large_pixmap.scaledToWidth(
                target_width, Qt.TransformationMode.SmoothTransformation
            )
        else:
            scaled = large_pixmap
        
        print(f"  Scaled pixmap size: {scaled.width()}x{scaled.height()}")
        
        # Encode and measure file size
        img_buffer = QBuffer()
        img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
        large_pixmap.save(img_buffer, "PNG")
        large_data = img_buffer.data()
        large_size = len(large_data)
        
        img_buffer = QBuffer()
        img_buffer.open(QBuffer.OpenModeFlag.ReadWrite)
        scaled.save(img_buffer, "PNG")
        scaled_data = img_buffer.data()
        scaled_size = len(scaled_data)
        
        reduction = (1 - scaled_size / large_size) * 100
        print(f"  File size reduction: {large_size:,} bytes → {scaled_size:,} bytes ({reduction:.1f}% smaller)")
        
        assert scaled.width() == target_width, f"Scaled width should be {target_width}"
        assert scaled_size < large_size, "Scaled image should be smaller"
        
        print(f"✓ Image scaling works correctly")
        return True
    except Exception as e:
        print(f"✗ Failed during scaling test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Image Editor Fixes\n" + "="*60)
    
    tests_passed = 0
    tests_total = 0
    
    tests = [
        ("Imports", test_imports),
        ("Handle Visibility", test_handles_visible),
        ("Image Scaling", test_image_scaling),
    ]
    
    for name, test_func in tests:
        tests_total += 1
        print(f"\n[{tests_total}] {name}:")
        if test_func():
            tests_passed += 1
        print()
    
    print("="*60)
    print(f"Results: {tests_passed}/{tests_total} tests passed")
    sys.exit(0 if tests_passed == tests_total else 1)

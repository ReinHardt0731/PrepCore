#!/usr/bin/env python3
"""
Generate tree indicator PNG images for the subject tree.
Creates symbols for branch indicators and expand/collapse arrows.
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Image dimensions
SIZE = 16
PADDING = 2

def create_indicator_png(symbol: str, filename: str):
    """Create a PNG image with the given symbol."""
    img = Image.new('RGBA', (SIZE, SIZE), color=(0, 0, 0, 0))  # Transparent background
    draw = ImageDraw.Draw(img)
    
    # Try to use a system font, fallback to default
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
    
    # White color for the symbol
    color = (255, 255, 255, 255)
    
    # Calculate text position to center it
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (SIZE - text_width) // 2
    y = (SIZE - text_height) // 2 - 2
    
    draw.text((x, y), symbol, fill=color, font=font)
    img.save(filename)
    print(f"Created: {filename}")

def main():
    """Generate all tree indicator images."""
    base_path = Path(__file__).parent
    
    # Create indicators directory if it doesn't exist
    indicators_dir = base_path / "tree_indicators"
    indicators_dir.mkdir(exist_ok=True)
    
    # Generate indicator symbols
    indicators = {
        "branch_closed.png": "▶",    # Expand arrow
        "branch_open.png": "▼",      # Collapse arrow
        "branch_more.png": "├──",    # Non-last item
        "branch_end.png": "└──",     # Last item
    }
    
    for filename, symbol in indicators.items():
        create_indicator_png(symbol, indicators_dir / filename)
    
    print(f"\n✓ Tree indicator images created in: {indicators_dir}")
    print("Update main.py to reference these images")

if __name__ == "__main__":
    main()

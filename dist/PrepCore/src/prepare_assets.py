#!/usr/bin/env python3
"""
Prepare app assets: Round the corners of Logo.png for the app icon.
This script creates a version with rounded corners suitable for app icons.
"""

from PIL import Image, ImageDraw
from pathlib import Path


def round_image_corners(image_path: str | Path, output_path: str | Path, radius: int = 40):
    """
    Round the corners of an image.
    
    Args:
        image_path: Path to the input image
        output_path: Path to save the output image
        radius: Corner radius in pixels (default 40)
    """
    image_path = Path(image_path)
    output_path = Path(output_path)
    
    if not image_path.exists():
        print(f"[ERROR] Image not found: {image_path}")
        return False
    
    # Open the image
    img = Image.open(image_path).convert('RGBA')
    
    # Create a new image for the rounded version
    width, height = img.size
    
    # Create a mask with rounded corners
    mask = Image.new('L', (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [(0, 0), (width, height)],
        radius=radius,
        fill=255
    )
    
    # Apply the mask
    img.putalpha(mask)
    
    # Save the output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'PNG')
    print(f"[OK] Created rounded icon: {output_path}")
    return True


if __name__ == "__main__":
    logo_path = Path(__file__).resolve().parent / "Logo.png"
    rounded_logo_path = Path(__file__).resolve().parent / "Logo_rounded.png"
    
    print("[PROCESS] Rounding Logo.png corners...")
    if round_image_corners(logo_path, rounded_logo_path, radius=300):
        print("[SUCCESS] Logo with rounded corners created!")
    else:
        print("[ERROR] Failed to create rounded logo")

#!/usr/bin/env python3
"""Test emoji support in subject names."""

import unicodedata

def slugify_test(value: str) -> str:
    """Generate a filesystem-safe slug from subject name, preserving emoji."""
    value = value.strip()
    if not value:
        return "subject"
    
    # Preserve emoji and alphanumeric, convert other problematic characters
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ord(ch) > 127:
            # Preserve emoji and other Unicode symbols
            category = unicodedata.category(ch)
            if category[0] in ('L', 'N', 'S', 'P'):
                # Keep letters, numbers, symbols (including emoji), and punctuation
                cleaned.append(ch)
            else:
                cleaned.append('_')
        else:
            # Convert all other characters (spaces, hyphens, etc.) to underscore
            cleaned.append('_')
    
    slug = ''.join(cleaned)
    while '__' in slug:
        slug = slug.replace('__', '_')
    slug = "_".join(part for part in slug.split("_") if part)
    return slug or "subject"

# Test cases
test_cases = [
    ("📚 Physics", "expected: 📚_physics"),
    ("Chemistry 🧪", "expected: chemistry_🧪"),
    ("Biology", "expected: biology"),
    ("📖 Literature & Arts", "expected: 📖_literature_arts"),
    ("🎓 Advanced Math", "expected: 🎓_advanced_math"),
    ("History (2025)", "expected: history_2025"),
    ("Art - Drawing", "expected: art_drawing"),
]

print("\n" + "="*70)
print("Testing Emoji Support in Subject Name Slugs")
print("="*70)

all_passed = True
for subject_name, expected in test_cases:
    slug = slugify_test(subject_name)
    # Extract the expected value
    expected_slug = expected.split(": ")[1] if ": " in expected else expected
    passed = slug == expected_slug
    
    status = "✓" if passed else "✗"
    print(f"\n{status} Input: {subject_name}")
    print(f"  Slug output: {slug}")
    print(f"  Expected: {expected_slug}")
    
    if not passed:
        all_passed = False

print("\n" + "="*70)
if all_passed:
    print("✓ ALL TESTS PASSED - Emoji support is working!")
else:
    print("✗ Some tests failed - Check output above")
print("="*70)

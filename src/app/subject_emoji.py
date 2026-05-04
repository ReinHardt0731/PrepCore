"""
Subject emoji mapping and utilities for displaying emoji in the subject tree.
Supports customizable emoji assignments for each subject.
"""

import json
from pathlib import Path
from typing import Dict

# Default emoji assignments by subject name (case-insensitive matching)
# Using outline/symbol emoji for cleaner, more monochrome appearance
DEFAULT_SUBJECT_EMOJI = {
    "aerodynamics": "✈",
    "air law": "⚖",
    "aviation": "🛩",
    "maintenance": "⚒",
    "technical": "⚙",
    "math": "🔢",
    "physics": "⚡",
    "chemistry": "⚗",
    "english": "📝",
    "history": "📜",
    "geography": "🧭",
    "biology": "🧬",
    "economics": "📊",
    "civics": "🏛",
    "computer science": "⌨",
    "programming": "💾",
}

# Unicode emoji to monochrome variants (outline/symbol emoji don't need variant selector)
# These are already in their cleanest form
EMOJI_MONOCHROME_MAP = {
    "✈": "✈",
    "⚖": "⚖",
    "🛩": "🛩",
    "⚒": "⚒",
    "⚙": "⚙",
    "🔢": "🔢",
    "⚡": "⚡",
    "⚗": "⚗",
    "📝": "📝",
    "📜": "📜",
    "🧭": "🧭",
    "🧬": "🧬",
    "📊": "📊",
    "🏛": "🏛",
    "⌨": "⌨",
    "💾": "💾",
}


class SubjectEmojiManager:
    """Manages emoji assignments for subjects with persistence."""
    
    def __init__(self, app_state_dir: Path):
        """
        Initialize the emoji manager.
        
        Args:
            app_state_dir: Directory to store emoji configuration
        """
        self.app_state_dir = app_state_dir
        self.emoji_config_path = app_state_dir / "subject_emoji_config.json"
        self.emoji_map: Dict[str, str] = {}
        self._load_emoji_config()
    
    def _load_emoji_config(self):
        """Load emoji configuration from file or create default."""
        if self.emoji_config_path.exists():
            try:
                with open(self.emoji_config_path, 'r', encoding='utf-8') as f:
                    self.emoji_map = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.emoji_map = {}
        else:
            self.emoji_map = {}
    
    def _save_emoji_config(self):
        """Save emoji configuration to file."""
        self.app_state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.emoji_config_path, 'w', encoding='utf-8') as f:
            json.dump(self.emoji_map, f, ensure_ascii=False, indent=2)
    
    def get_emoji_for_subject(self, subject_name: str, use_monochrome: bool = False) -> str:
        """
        Get emoji for a subject, with fallback to default mapping.
        
        Args:
            subject_name: Name of the subject
            use_monochrome: If True, return monochrome variant
        
        Returns:
            Emoji string (or empty string if no mapping)
        """
        # Check custom mapping first
        if subject_name in self.emoji_map:
            emoji = self.emoji_map[subject_name]
        else:
            # Try default mapping (case-insensitive)
            emoji = next(
                (v for k, v in DEFAULT_SUBJECT_EMOJI.items() if k.lower() == subject_name.lower()),
                ""
            )
        
        # Convert to monochrome if requested
        if emoji and use_monochrome:
            emoji = EMOJI_MONOCHROME_MAP.get(emoji, emoji)
        
        return emoji
    
    def set_emoji_for_subject(self, subject_name: str, emoji: str) -> bool:
        """
        Set custom emoji for a subject.
        
        Args:
            subject_name: Name of the subject
            emoji: Single emoji character
        
        Returns:
            True if successful, False if invalid emoji
        """
        # Basic validation - emoji should be 1-2 characters
        if not emoji or len(emoji) > 2:
            return False
        
        self.emoji_map[subject_name] = emoji
        self._save_emoji_config()
        return True
    
    def remove_custom_emoji(self, subject_name: str):
        """Remove custom emoji for a subject (will use default)."""
        if subject_name in self.emoji_map:
            del self.emoji_map[subject_name]
            self._save_emoji_config()
    
    def reset_to_defaults(self):
        """Reset all custom emoji to defaults."""
        self.emoji_map = {}
        if self.emoji_config_path.exists():
            self.emoji_config_path.unlink()


def get_subject_display_name(subject_name: str, emoji_manager: SubjectEmojiManager = None, 
                            use_monochrome: bool = False) -> str:
    """
    Get display name for a subject with emoji prefix.
    
    Args:
        subject_name: Name of the subject
        emoji_manager: SubjectEmojiManager instance (optional)
        use_monochrome: If True, use monochrome emoji
    
    Returns:
        Subject name with emoji prefix (e.g., "✈️ Aerodynamics")
    """
    if emoji_manager is None:
        # Fallback to default if no manager provided
        emoji = next(
            (v for k, v in DEFAULT_SUBJECT_EMOJI.items() if k.lower() == subject_name.lower()),
            ""
        )
    else:
        emoji = emoji_manager.get_emoji_for_subject(subject_name, use_monochrome)
    
    if emoji:
        return f"{emoji} {subject_name}"
    return subject_name

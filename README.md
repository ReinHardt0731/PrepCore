# PrepCore - Board Exam Preparation Application

## Features

- 📚 **Subject Management**: Organize studies by subject and chapter
- 🎯 **Multiple Quiz Types**: Long quizzes, short quizzes, and notebooks
- ⏱️ **Time Management**: Gantt charts, calendar, and Pomodoro timer
- 🎨 **Modern UI**: Midnight blue theme with intuitive design
- 💾 **Data Persistence**: All progress saved locally

## First-Run Setup

When you first launch PrepCore:
- The application starts with no pre-loaded subjects
- Create subjects and add chapters manually, or use the Import feature
- Your data is saved in: `%APPDATA%/Local/PrepCore/`

## System Requirements

- Windows 7 or later
- No additional software required (all dependencies bundled)

## Support

For issues or questions, refer to the documentation in the `docs/` folder.

## Data Storage

User data is automatically saved to:
```
%APPDATA%\Local\PrepCore\
├── subjects.json         # Your subjects and chapters
├── preferences.json      # App preferences
└── window_state.json     # Window size and position
```

## Files Included

The `assets/` folder contains:
- Application runtime libraries
- Icons and images
- Alarm sound for timer notifications
- Configuration schemas

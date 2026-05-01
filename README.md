# PrepCore - Board Exam Preparation Application

A powerful desktop application designed to help students prepare effectively for board exams. **PrepCore** provides an organized study environment with comprehensive tools for managing subjects, taking quizzes, organizing study schedules, and tracking progress.

## 🎯 Features

### 📚 Subject & Study Management
- Organize subjects into chapters and subchapters
- Create and manage study outlines/notebooks for each subject
- Import and export study materials
- Persistent subject database with version control

### 📝 Multiple Quiz Types
- **Short Quizzes**: Quick self-assessment tests
- **Long Quizzes**: Comprehensive exam-style assessments
- **Notebook/Outline Tab**: Rich-text note-taking with markdown support
- Quiz performance tracking and analytics

### ⏰ Time & Task Organization
- **Gantt Chart View**: Visualize study timeline and task dependencies
- **Calendar View**: Schedule study sessions and exams
- **Todo List**: Track study tasks with completion status
- **Pomodoro Timer**: Built-in timer with audio alerts for focused study sessions

### 🎨 User Experience
- Professional midnight blue theme
- Responsive dock-based UI layout
- Persistent window state and preferences
- First-run guided setup

## 🔧 System Requirements

- **Python**: 3.10 or higher
- **OS**: Windows 10 or later (for .exe builds)
- **RAM**: Minimum 4 GB
- **Disk Space**: 500 MB for application + dependencies

### Dependencies
- PySide6 (Qt framework)
- Pillow (image processing)
- PyInstaller (for executable builds)

## 📦 Installation

### Option 1: Run from Source (Development)

1. **Clone or download the repository**
   ```bash
   cd BOARDEXAMAPP
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install manually:
   ```bash
   pip install PySide6 Pillow
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

### Option 2: Use Pre-built Executable

Download the latest `PrepCore.exe` from the releases section and run it directly. No Python installation required!

## 🚀 Quick Start

1. **Launch PrepCore**
2. **Create Your First Subject**
   - Click "New" in the menu or use the subject panel
   - Name your subject (e.g., "Aerodynamics", "Air Law")
   - Add chapters and subchapters

3. **Import Quiz Banks**
   - Use the "Import" menu option to load quiz banks
   - Quiz data is stored in `quiz_banks/` directory

4. **Add Study Notes**
   - Use the "Outline" tab to create and organize study notes
   - Supports rich text formatting

5. **Schedule Your Study**
   - Use the Gantt chart to plan your study timeline
   - Set tasks and track progress with the todo list

6. **Take Quizzes**
   - Switch between Short Quiz and Long Quiz tabs
   - Review answers and track your performance

## 📁 Project Structure

```
BOARDEXAMAPP/
├── main.py                      # Application entry point
├── board_exam.py               # Auto-generated UI file
├── board_exam.ui               # Qt Designer UI file
├── app_theme.py                # Theme and styling
│
├── task_list/                  # Quiz and notebook functionality
│   ├── quiz_tab.py            # Quiz data models and logic
│   ├── short_quiz_tab.py       # Short quiz UI controller
│   ├── long_quiz_tab.py        # Long quiz UI controller
│   ├── outline_tab.py          # Notebook/outline controller
│   └── assessment_tab.py       # Assessment tracking
│
├── gant_chart/                 # Time management and scheduling
│   ├── time_organizer_tab.py   # Gantt chart, calendar, todo UI
│   └── __init__.py
│
├── subject_list_dock/          # Subject selection panel
│   └── __init__.py
│
├── app_state/                  # User data (persistent)
│   ├── preferences.json        # User preferences
│   ├── subjects.json           # Subject structure
│   └── window_state.json       # Window geometry and state
│
├── quiz_banks/                 # Quiz data
│   └── {subject}/
│       ├── short_quiz.json
│       └── long_quiz.json
│
├── notebooks/                  # Study notes and equation data
│   ├── equation_metadata.json
│   ├── notebook_layout.json
│   └── *.json
│
├── build/                      # Build artifacts
├── dist/                       # Compiled executables
│
└── [Build Configuration Files]
    ├── build.py               # Python build script
    ├── build.bat              # Batch build script
    ├── build.exe.spec         # PyInstaller spec for .exe
    └── BUILD_README.md        # Build instructions
```

## 🔨 Building the Executable

### Quick Build (Recommended)

```bash
python build.py
```

Or on Windows:
```bash
build.bat
```

The executable will be created in the `dist/` folder as `PrepCore.exe`.

### Manual Build with PyInstaller

```bash
pip install pyinstaller

# Prepare assets
python prepare_assets.py

# Build the executable
pyinstaller build.exe.spec
```

For detailed build instructions, see [BUILD_README.md](BUILD_README.md).

## 📊 Data Storage

All application data is stored in:
- **Windows**: `C:\Users\{YourUsername}\AppData\Local\PrepCore\`
- **Location**: User AppData directory (not in the application folder)

This ensures data persists across application updates and reinstalls.

### Data Files
- `preferences.json` - User settings and preferences
- `subjects.json` - Subject and chapter structure
- `window_state.json` - Window size and position
- Quiz banks: Stored in `quiz_banks/` (relative to app directory)
- Notebooks: Stored in `notebooks/` (relative to app directory)

## 🎮 Usage Examples

### Create a New Subject
1. Click "New" from the menu
2. Enter subject name
3. Add chapters and subchapters via the left panel
4. Subject is automatically saved

### Import Quiz Bank
1. Click "Import" from the menu
2. Select quiz JSON file
3. Choose the subject to associate with
4. Quiz questions are loaded into the database

### Take a Short Quiz
1. Select a subject and chapter
2. Go to "Short Quiz" tab
3. Answer questions
4. Review results and correct answers

### Schedule Study Session
1. Go to "Time Organizer" → "Gantt" tab
2. Create study tasks with dates and duration
3. Use the built-in Pomodoro timer for focused sessions

## 🔧 Development

### Code Structure
- **MVC Pattern**: Separation of UI (views), data (models), and logic (controllers)
- **PySide6/PyQt6**: Qt framework for cross-platform GUI
- **JSON Storage**: Human-readable data persistence
- **Modular Design**: Each feature (quiz, timer, notes) in separate modules

### Adding a New Feature
1. Create a new module in the appropriate subdirectory
2. Implement the controller class
3. Add UI integration in `main.py` or relevant tab
4. Update data models in `task_list/` as needed

### Running Tests
```bash
# Test individual components
python test_qtextedit_html.py
python test_image_editor.py
python test_title_markers.py
```

## 🐛 Troubleshooting

### Application won't start
- Ensure Python 3.10+ is installed
- Check if all dependencies are installed: `pip install -r requirements.txt`
- Verify Windows is up to date

### Quiz data not loading
- Check that quiz JSON files are in the correct format
- Ensure quiz banks are placed in `quiz_banks/` directory
- Verify file permissions

### Preferences not saving
- Check if `app_state/` directory exists and is writable
- On Windows, ensure AppData folder is accessible
- Try clearing preferences and restarting

### Build fails
- Ensure PyInstaller is installed: `pip install pyinstaller`
- Check Python version: `python --version`
- Run `prepare_assets.py` before building

## 📄 License

[Add your license information here]

## 👤 Author

[Add your information here]

## 📞 Support & Feedback

For issues, suggestions, or contributions, please:
- Check existing issues and documentation
- Contact the development team
- Submit bug reports with detailed steps to reproduce

## 🎓 Board Exam Subjects Supported

PrepCore is designed to work with various board exam subjects including:
- Aerodynamics
- Air Law
- Aviation Maintenance
- Technical subjects for professional board exams
- *And many more - fully customizable*

---

**Happy studying with PrepCore!** 📚✈️

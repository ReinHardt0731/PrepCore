import sys
from pathlib import Path

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from modules.gant_chart.time_organizer_tab import TimeOrganizerController


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def _build_controller():
    tabs = QTabWidget()
    gant_page = QWidget()
    calendar_page = QWidget()
    todo_page = QWidget()
    activity_page = QWidget()
    tabs.addTab(gant_page, "Gantt")
    tabs.addTab(calendar_page, "Calendar")
    tabs.addTab(todo_page, "Todo")
    tabs.addTab(activity_page, "Activity")
    controller = TimeOrganizerController(tabs, gant_page, calendar_page, todo_page, activity_page)
    return controller, tabs


def test_alarm_falls_back_when_audio_file_is_missing():
    app = _app()
    controller, tabs = _build_controller()
    fallback_calls: list[str] = []
    try:
        controller._resolve_alarm_sound_path = lambda: None
        controller._play_platform_alarm_fallback = lambda: fallback_calls.append("fallback")

        controller._play_alarm_sound()

        assert fallback_calls == ["fallback"]
    finally:
        controller.countdown_timer.stop()
        controller.gantt_state_save_timer.stop()
        tabs.deleteLater()
        app.processEvents()


def test_alarm_uses_fallback_if_qt_playback_never_starts():
    app = _app()
    controller, tabs = _build_controller()
    fallback_calls: list[str] = []

    class FakeMediaPlayer:
        def playbackState(self):
            return QMediaPlayer.PlaybackState.StoppedState

    try:
        controller.media_player = FakeMediaPlayer()
        controller._alarm_fallback_armed = True
        controller._play_platform_alarm_fallback = lambda: fallback_calls.append("fallback")

        controller._ensure_alarm_playback_started()

        assert fallback_calls == ["fallback"]
    finally:
        controller.countdown_timer.stop()
        controller.gantt_state_save_timer.stop()
        tabs.deleteLater()
        app.processEvents()

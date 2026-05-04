from PySide6.QtWidgets import QWidget

from .quiz_tab import ChapterQuizTabController


class ShortQuizTabController(ChapterQuizTabController):
    def __init__(self, page: QWidget):
        super().__init__(
            page,
            prefix="short_quiz",
            title="Short Quiz",
            show_branch_viewer=False,
        )

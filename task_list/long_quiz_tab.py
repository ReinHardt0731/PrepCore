from PySide6.QtWidgets import QWidget

from .quiz_tab import ChapterQuizTabController


class LongQuizTabController(ChapterQuizTabController):
    def __init__(self, page: QWidget):
        super().__init__(
            page,
            prefix="long_quiz",
            title="Long Quiz",
            show_branch_viewer=False,
        )

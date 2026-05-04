# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'board_exam.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QDockWidget, QGridLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMenuBar, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSplitter,
    QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(918, 665)
        self.actionPreference = QAction(MainWindow)
        self.actionPreference.setObjectName(u"actionPreference")
        self.actionNew = QAction(MainWindow)
        self.actionNew.setObjectName(u"actionNew")
        self.actionImport = QAction(MainWindow)
        self.actionImport.setObjectName(u"actionImport")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.scrollArea = QScrollArea(self.centralwidget)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setMaximumSize(QSize(20, 16777215))
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 18, 623))
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.gridLayout.addWidget(self.scrollArea, 0, 1, 5, 1)

        self.center_splitter = QSplitter(self.centralwidget)
        self.center_splitter.setObjectName(u"center_splitter")
        self.center_splitter.setOrientation(Qt.Orientation.Vertical)
        self.center_splitter.setChildrenCollapsible(False)
        self.center_splitter.setHandleWidth(6)

        self.time_organizer = QTabWidget(self.center_splitter)
        self.time_organizer.setObjectName(u"time_organizer")
        self.time_organizer.setMinimumSize(QSize(0, 200))
        self.gant_chart = QWidget()
        self.gant_chart.setObjectName(u"gant_chart")
        self.time_organizer.addTab(self.gant_chart, "")
        self.calendar = QWidget()
        self.calendar.setObjectName(u"calendar")
        self.time_organizer.addTab(self.calendar, "")
        self.todo_list_2 = QWidget()
        self.todo_list_2.setObjectName(u"todo_list_2")
        self.time_organizer.addTab(self.todo_list_2, "")

        self.center_splitter.addWidget(self.time_organizer)

        self.TaskTabs = QTabWidget(self.center_splitter)
        self.TaskTabs.setObjectName(u"TaskTabs")
        self.TaskTabs.setTabShape(QTabWidget.TabShape.Rounded)
        self.todo_list = QWidget()
        self.todo_list.setObjectName(u"todo_list")
        self.verticalLayout_outline = QVBoxLayout(self.todo_list)
        self.verticalLayout_outline.setObjectName(u"verticalLayout_outline")
        self.horizontalLayout_outline_toolbar = QHBoxLayout()
        self.horizontalLayout_outline_toolbar.setObjectName(u"horizontalLayout_outline_toolbar")
        self.outline_mode_label = QLabel(self.todo_list)
        self.outline_mode_label.setObjectName(u"outline_mode_label")

        self.horizontalLayout_outline_toolbar.addWidget(self.outline_mode_label)

        self.horizontalSpacer_outline_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_outline_toolbar.addItem(self.horizontalSpacer_outline_toolbar)

        self.outline_toggle_button = QPushButton(self.todo_list)
        self.outline_toggle_button.setObjectName(u"outline_toggle_button")

        self.horizontalLayout_outline_toolbar.addWidget(self.outline_toggle_button)


        self.verticalLayout_outline.addLayout(self.horizontalLayout_outline_toolbar)

        self.outline_stack = QStackedWidget(self.todo_list)
        self.outline_stack.setObjectName(u"outline_stack")
        self.outline_editor_page = QWidget()
        self.outline_editor_page.setObjectName(u"outline_editor_page")
        self.verticalLayout_outline_editor = QVBoxLayout(self.outline_editor_page)
        self.verticalLayout_outline_editor.setObjectName(u"verticalLayout_outline_editor")
        self.outline_editor = QPlainTextEdit(self.outline_editor_page)
        self.outline_editor.setObjectName(u"outline_editor")

        self.verticalLayout_outline_editor.addWidget(self.outline_editor)

        self.outline_stack.addWidget(self.outline_editor_page)
        self.outline_reader_page = QWidget()
        self.outline_reader_page.setObjectName(u"outline_reader_page")
        self.verticalLayout_outline_reader = QVBoxLayout(self.outline_reader_page)
        self.verticalLayout_outline_reader.setObjectName(u"verticalLayout_outline_reader")
        self.outline_reader = QTextBrowser(self.outline_reader_page)
        self.outline_reader.setObjectName(u"outline_reader")

        self.verticalLayout_outline_reader.addWidget(self.outline_reader)

        self.outline_stack.addWidget(self.outline_reader_page)

        self.verticalLayout_outline.addWidget(self.outline_stack)

        self.TaskTabs.addTab(self.todo_list, "")
        self.short_quiz = QWidget()
        self.short_quiz.setObjectName(u"short_quiz")
        self.verticalLayout_short_quiz_root = QVBoxLayout(self.short_quiz)
        self.verticalLayout_short_quiz_root.setObjectName(u"verticalLayout_short_quiz_root")
        self.horizontalSplitter_short_quiz_root = QSplitter(self.short_quiz)
        self.horizontalSplitter_short_quiz_root.setObjectName(u"horizontalSplitter_short_quiz_root")
        self.horizontalSplitter_short_quiz_root.setOrientation(Qt.Orientation.Horizontal)
        self.short_quiz_left_panel = QWidget(self.horizontalSplitter_short_quiz_root)
        self.short_quiz_left_panel.setObjectName(u"short_quiz_left_panel")
        self.verticalLayout_short_quiz_left = QVBoxLayout(self.short_quiz_left_panel)
        self.verticalLayout_short_quiz_left.setObjectName(u"verticalLayout_short_quiz_left")
        self.verticalLayout_short_quiz_left.setContentsMargins(0, 0, 8, 0)
        self.short_quiz_toolbar = QWidget(self.short_quiz_left_panel)
        self.short_quiz_toolbar.setObjectName(u"short_quiz_toolbar")
        self.horizontalLayout_short_quiz_toolbar = QHBoxLayout(self.short_quiz_toolbar)
        self.horizontalLayout_short_quiz_toolbar.setObjectName(u"horizontalLayout_short_quiz_toolbar")
        self.horizontalLayout_short_quiz_toolbar.setContentsMargins(0, 0, 0, 0)
        self.short_quiz_title_label = QLabel(self.short_quiz_toolbar)
        self.short_quiz_title_label.setObjectName(u"short_quiz_title_label")

        self.horizontalLayout_short_quiz_toolbar.addWidget(self.short_quiz_title_label)

        self.horizontalSpacer_short_quiz_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_short_quiz_toolbar.addItem(self.horizontalSpacer_short_quiz_toolbar)

        self.short_quiz_status_label = QLabel(self.short_quiz_toolbar)
        self.short_quiz_status_label.setObjectName(u"short_quiz_status_label")

        self.horizontalLayout_short_quiz_toolbar.addWidget(self.short_quiz_status_label)

        self.short_quiz_add_chapter_button = QPushButton(self.short_quiz_toolbar)
        self.short_quiz_add_chapter_button.setObjectName(u"short_quiz_add_chapter_button")

        self.horizontalLayout_short_quiz_toolbar.addWidget(self.short_quiz_add_chapter_button)

        self.short_quiz_import_button = QPushButton(self.short_quiz_toolbar)
        self.short_quiz_import_button.setObjectName(u"short_quiz_import_button")

        self.horizontalLayout_short_quiz_toolbar.addWidget(self.short_quiz_import_button)

        self.short_quiz_export_button = QPushButton(self.short_quiz_toolbar)
        self.short_quiz_export_button.setObjectName(u"short_quiz_export_button")

        self.horizontalLayout_short_quiz_toolbar.addWidget(self.short_quiz_export_button)


        self.verticalLayout_short_quiz_left.addWidget(self.short_quiz_toolbar)

        self.short_quiz_chapter_header_label = QLabel(self.short_quiz_left_panel)
        self.short_quiz_chapter_header_label.setObjectName(u"short_quiz_chapter_header_label")

        self.verticalLayout_short_quiz_left.addWidget(self.short_quiz_chapter_header_label)

        self.short_quiz_chapter_list = QListWidget(self.short_quiz_left_panel)
        self.short_quiz_chapter_list.setObjectName(u"short_quiz_chapter_list")

        self.verticalLayout_short_quiz_left.addWidget(self.short_quiz_chapter_list)

        self.short_quiz_question_toolbar = QWidget(self.short_quiz_left_panel)
        self.short_quiz_question_toolbar.setObjectName(u"short_quiz_question_toolbar")
        self.horizontalLayout_short_quiz_question_toolbar = QHBoxLayout(self.short_quiz_question_toolbar)
        self.horizontalLayout_short_quiz_question_toolbar.setObjectName(u"horizontalLayout_short_quiz_question_toolbar")
        self.horizontalLayout_short_quiz_question_toolbar.setContentsMargins(0, 0, 0, 0)
        self.short_quiz_question_header_label = QLabel(self.short_quiz_question_toolbar)
        self.short_quiz_question_header_label.setObjectName(u"short_quiz_question_header_label")

        self.horizontalLayout_short_quiz_question_toolbar.addWidget(self.short_quiz_question_header_label)

        self.horizontalSpacer_short_quiz_question_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_short_quiz_question_toolbar.addItem(self.horizontalSpacer_short_quiz_question_toolbar)

        self.short_quiz_question_status_label = QLabel(self.short_quiz_question_toolbar)
        self.short_quiz_question_status_label.setObjectName(u"short_quiz_question_status_label")

        self.horizontalLayout_short_quiz_question_toolbar.addWidget(self.short_quiz_question_status_label)

        self.short_quiz_add_question_button = QPushButton(self.short_quiz_question_toolbar)
        self.short_quiz_add_question_button.setObjectName(u"short_quiz_add_question_button")

        self.horizontalLayout_short_quiz_question_toolbar.addWidget(self.short_quiz_add_question_button)

        self.short_quiz_edit_question_button = QPushButton(self.short_quiz_question_toolbar)
        self.short_quiz_edit_question_button.setObjectName(u"short_quiz_edit_question_button")

        self.horizontalLayout_short_quiz_question_toolbar.addWidget(self.short_quiz_edit_question_button)

        self.short_quiz_delete_question_button = QPushButton(self.short_quiz_question_toolbar)
        self.short_quiz_delete_question_button.setObjectName(u"short_quiz_delete_question_button")

        self.horizontalLayout_short_quiz_question_toolbar.addWidget(self.short_quiz_delete_question_button)


        self.verticalLayout_short_quiz_left.addWidget(self.short_quiz_question_toolbar)

        self.short_quiz_question_list = QListWidget(self.short_quiz_left_panel)
        self.short_quiz_question_list.setObjectName(u"short_quiz_question_list")

        self.verticalLayout_short_quiz_left.addWidget(self.short_quiz_question_list)

        self.horizontalSplitter_short_quiz_root.addWidget(self.short_quiz_left_panel)
        self.short_quiz_answer_panel = QWidget(self.horizontalSplitter_short_quiz_root)
        self.short_quiz_answer_panel.setObjectName(u"short_quiz_answer_panel")
        self.verticalLayout_short_quiz_answer_panel = QVBoxLayout(self.short_quiz_answer_panel)
        self.verticalLayout_short_quiz_answer_panel.setObjectName(u"verticalLayout_short_quiz_answer_panel")
        self.verticalLayout_short_quiz_answer_panel.setContentsMargins(8, 0, 0, 0)
        self.short_quiz_answer_header_label = QLabel(self.short_quiz_answer_panel)
        self.short_quiz_answer_header_label.setObjectName(u"short_quiz_answer_header_label")

        self.verticalLayout_short_quiz_answer_panel.addWidget(self.short_quiz_answer_header_label)

        self.short_quiz_answer_scroll = QScrollArea(self.short_quiz_answer_panel)
        self.short_quiz_answer_scroll.setObjectName(u"short_quiz_answer_scroll")
        self.short_quiz_answer_scroll.setWidgetResizable(True)
        self.short_quiz_answer_container = QWidget()
        self.short_quiz_answer_container.setObjectName(u"short_quiz_answer_container")
        self.short_quiz_answer_container.setGeometry(QRect(0, 0, 320, 400))
        self.verticalLayout_short_quiz_answer_cards = QVBoxLayout(self.short_quiz_answer_container)
        self.verticalLayout_short_quiz_answer_cards.setObjectName(u"verticalLayout_short_quiz_answer_cards")
        self.verticalLayout_short_quiz_answer_cards.setContentsMargins(0, 0, 0, 0)
        self.short_quiz_answer_scroll.setWidget(self.short_quiz_answer_container)

        self.verticalLayout_short_quiz_answer_panel.addWidget(self.short_quiz_answer_scroll)

        self.horizontalSplitter_short_quiz_root.addWidget(self.short_quiz_answer_panel)

        self.verticalLayout_short_quiz_root.addWidget(self.horizontalSplitter_short_quiz_root)

        self.TaskTabs.addTab(self.short_quiz, "")
        self.long_quiz = QWidget()
        self.long_quiz.setObjectName(u"long_quiz")
        self.verticalLayout_long_quiz_root = QVBoxLayout(self.long_quiz)
        self.verticalLayout_long_quiz_root.setObjectName(u"verticalLayout_long_quiz_root")
        self.horizontalSplitter_long_quiz_root = QSplitter(self.long_quiz)
        self.horizontalSplitter_long_quiz_root.setObjectName(u"horizontalSplitter_long_quiz_root")
        self.horizontalSplitter_long_quiz_root.setOrientation(Qt.Orientation.Horizontal)
        self.long_quiz_left_panel = QWidget(self.horizontalSplitter_long_quiz_root)
        self.long_quiz_left_panel.setObjectName(u"long_quiz_left_panel")
        self.verticalLayout_long_quiz_left = QVBoxLayout(self.long_quiz_left_panel)
        self.verticalLayout_long_quiz_left.setObjectName(u"verticalLayout_long_quiz_left")
        self.verticalLayout_long_quiz_left.setContentsMargins(0, 0, 8, 0)
        self.long_quiz_toolbar = QWidget(self.long_quiz_left_panel)
        self.long_quiz_toolbar.setObjectName(u"long_quiz_toolbar")
        self.horizontalLayout_long_quiz_toolbar = QHBoxLayout(self.long_quiz_toolbar)
        self.horizontalLayout_long_quiz_toolbar.setObjectName(u"horizontalLayout_long_quiz_toolbar")
        self.horizontalLayout_long_quiz_toolbar.setContentsMargins(0, 0, 0, 0)
        self.long_quiz_title_label = QLabel(self.long_quiz_toolbar)
        self.long_quiz_title_label.setObjectName(u"long_quiz_title_label")

        self.horizontalLayout_long_quiz_toolbar.addWidget(self.long_quiz_title_label)

        self.horizontalSpacer_long_quiz_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_long_quiz_toolbar.addItem(self.horizontalSpacer_long_quiz_toolbar)

        self.long_quiz_status_label = QLabel(self.long_quiz_toolbar)
        self.long_quiz_status_label.setObjectName(u"long_quiz_status_label")

        self.horizontalLayout_long_quiz_toolbar.addWidget(self.long_quiz_status_label)

        self.long_quiz_add_chapter_button = QPushButton(self.long_quiz_toolbar)
        self.long_quiz_add_chapter_button.setObjectName(u"long_quiz_add_chapter_button")

        self.horizontalLayout_long_quiz_toolbar.addWidget(self.long_quiz_add_chapter_button)

        self.long_quiz_import_button = QPushButton(self.long_quiz_toolbar)
        self.long_quiz_import_button.setObjectName(u"long_quiz_import_button")

        self.horizontalLayout_long_quiz_toolbar.addWidget(self.long_quiz_import_button)

        self.long_quiz_export_button = QPushButton(self.long_quiz_toolbar)
        self.long_quiz_export_button.setObjectName(u"long_quiz_export_button")

        self.horizontalLayout_long_quiz_toolbar.addWidget(self.long_quiz_export_button)


        self.verticalLayout_long_quiz_left.addWidget(self.long_quiz_toolbar)

        self.long_quiz_chapter_header_label = QLabel(self.long_quiz_left_panel)
        self.long_quiz_chapter_header_label.setObjectName(u"long_quiz_chapter_header_label")

        self.verticalLayout_long_quiz_left.addWidget(self.long_quiz_chapter_header_label)

        self.long_quiz_chapter_list = QListWidget(self.long_quiz_left_panel)
        self.long_quiz_chapter_list.setObjectName(u"long_quiz_chapter_list")

        self.verticalLayout_long_quiz_left.addWidget(self.long_quiz_chapter_list)

        self.long_quiz_question_toolbar = QWidget(self.long_quiz_left_panel)
        self.long_quiz_question_toolbar.setObjectName(u"long_quiz_question_toolbar")
        self.horizontalLayout_long_quiz_question_toolbar = QHBoxLayout(self.long_quiz_question_toolbar)
        self.horizontalLayout_long_quiz_question_toolbar.setObjectName(u"horizontalLayout_long_quiz_question_toolbar")
        self.horizontalLayout_long_quiz_question_toolbar.setContentsMargins(0, 0, 0, 0)
        self.long_quiz_question_header_label = QLabel(self.long_quiz_question_toolbar)
        self.long_quiz_question_header_label.setObjectName(u"long_quiz_question_header_label")

        self.horizontalLayout_long_quiz_question_toolbar.addWidget(self.long_quiz_question_header_label)

        self.horizontalSpacer_long_quiz_question_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_long_quiz_question_toolbar.addItem(self.horizontalSpacer_long_quiz_question_toolbar)

        self.long_quiz_question_status_label = QLabel(self.long_quiz_question_toolbar)
        self.long_quiz_question_status_label.setObjectName(u"long_quiz_question_status_label")

        self.horizontalLayout_long_quiz_question_toolbar.addWidget(self.long_quiz_question_status_label)

        self.long_quiz_add_question_button = QPushButton(self.long_quiz_question_toolbar)
        self.long_quiz_add_question_button.setObjectName(u"long_quiz_add_question_button")

        self.horizontalLayout_long_quiz_question_toolbar.addWidget(self.long_quiz_add_question_button)

        self.long_quiz_edit_question_button = QPushButton(self.long_quiz_question_toolbar)
        self.long_quiz_edit_question_button.setObjectName(u"long_quiz_edit_question_button")

        self.horizontalLayout_long_quiz_question_toolbar.addWidget(self.long_quiz_edit_question_button)

        self.long_quiz_delete_question_button = QPushButton(self.long_quiz_question_toolbar)
        self.long_quiz_delete_question_button.setObjectName(u"long_quiz_delete_question_button")

        self.horizontalLayout_long_quiz_question_toolbar.addWidget(self.long_quiz_delete_question_button)


        self.verticalLayout_long_quiz_left.addWidget(self.long_quiz_question_toolbar)

        self.long_quiz_question_list = QListWidget(self.long_quiz_left_panel)
        self.long_quiz_question_list.setObjectName(u"long_quiz_question_list")

        self.verticalLayout_long_quiz_left.addWidget(self.long_quiz_question_list)

        self.horizontalSplitter_long_quiz_root.addWidget(self.long_quiz_left_panel)
        self.long_quiz_answer_panel = QWidget(self.horizontalSplitter_long_quiz_root)
        self.long_quiz_answer_panel.setObjectName(u"long_quiz_answer_panel")
        self.verticalLayout_long_quiz_answer_panel = QVBoxLayout(self.long_quiz_answer_panel)
        self.verticalLayout_long_quiz_answer_panel.setObjectName(u"verticalLayout_long_quiz_answer_panel")
        self.verticalLayout_long_quiz_answer_panel.setContentsMargins(8, 0, 0, 0)
        self.long_quiz_answer_header_label = QLabel(self.long_quiz_answer_panel)
        self.long_quiz_answer_header_label.setObjectName(u"long_quiz_answer_header_label")

        self.verticalLayout_long_quiz_answer_panel.addWidget(self.long_quiz_answer_header_label)

        self.long_quiz_review_toolbar = QWidget(self.long_quiz_answer_panel)
        self.long_quiz_review_toolbar.setObjectName(u"long_quiz_review_toolbar")
        self.horizontalLayout_long_quiz_review_toolbar = QHBoxLayout(self.long_quiz_review_toolbar)
        self.horizontalLayout_long_quiz_review_toolbar.setObjectName(u"horizontalLayout_long_quiz_review_toolbar")
        self.horizontalLayout_long_quiz_review_toolbar.setContentsMargins(0, 0, 0, 0)
        self.long_quiz_score_label = QLabel(self.long_quiz_review_toolbar)
        self.long_quiz_score_label.setObjectName(u"long_quiz_score_label")

        self.horizontalLayout_long_quiz_review_toolbar.addWidget(self.long_quiz_score_label)

        self.horizontalSpacer_long_quiz_review_toolbar = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_long_quiz_review_toolbar.addItem(self.horizontalSpacer_long_quiz_review_toolbar)

        self.long_quiz_submit_button = QPushButton(self.long_quiz_review_toolbar)
        self.long_quiz_submit_button.setObjectName(u"long_quiz_submit_button")

        self.horizontalLayout_long_quiz_review_toolbar.addWidget(self.long_quiz_submit_button)

        self.verticalLayout_long_quiz_answer_panel.addWidget(self.long_quiz_review_toolbar)

        self.long_quiz_answer_scroll = QScrollArea(self.long_quiz_answer_panel)
        self.long_quiz_answer_scroll.setObjectName(u"long_quiz_answer_scroll")
        self.long_quiz_answer_scroll.setWidgetResizable(True)
        self.long_quiz_answer_container = QWidget()
        self.long_quiz_answer_container.setObjectName(u"long_quiz_answer_container")
        self.long_quiz_answer_container.setGeometry(QRect(0, 0, 320, 400))
        self.verticalLayout_long_quiz_answer_cards = QVBoxLayout(self.long_quiz_answer_container)
        self.verticalLayout_long_quiz_answer_cards.setObjectName(u"verticalLayout_long_quiz_answer_cards")
        self.verticalLayout_long_quiz_answer_cards.setContentsMargins(0, 0, 0, 0)
        self.long_quiz_answer_scroll.setWidget(self.long_quiz_answer_container)

        self.verticalLayout_long_quiz_answer_panel.addWidget(self.long_quiz_answer_scroll)

        self.horizontalSplitter_long_quiz_root.addWidget(self.long_quiz_answer_panel)

        self.verticalLayout_long_quiz_root.addWidget(self.horizontalSplitter_long_quiz_root)

        self.TaskTabs.addTab(self.long_quiz, "")

        self.center_splitter.addWidget(self.TaskTabs)
        self.center_splitter.setStretchFactor(0, 1)
        self.center_splitter.setStretchFactor(1, 2)

        self.gridLayout.addWidget(self.center_splitter, 2, 0, 3, 1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 918, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        self.menuTools = QMenu(self.menubar)
        self.menuTools.setObjectName(u"menuTools")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.Subject = QDockWidget(MainWindow)
        self.Subject.setObjectName(u"Subject")
        self.Subject.setFloating(True)
        self.Subjects = QWidget()
        self.Subjects.setObjectName(u"Subjects")
        self.gridLayout_2 = QGridLayout(self.Subjects)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.subject_list = QWidget(self.Subjects)
        self.subject_list.setObjectName(u"subject_list")

        self.gridLayout_2.addWidget(self.subject_list, 0, 0, 1, 1)

        self.Subject.setWidget(self.Subjects)
        MainWindow.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.Subject)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionNew)
        self.menuFile.addAction(self.actionImport)
        self.menuView.addAction(self.actionPreference)

        self.retranslateUi(MainWindow)

        self.time_organizer.setCurrentIndex(2)
        self.TaskTabs.setCurrentIndex(1)
        self.outline_stack.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"PrepCore", None))
        self.actionPreference.setText(QCoreApplication.translate("MainWindow", u"Preference", None))
        self.actionNew.setText(QCoreApplication.translate("MainWindow", u"New", None))
        self.actionImport.setText(QCoreApplication.translate("MainWindow", u"Import", None))
        self.time_organizer.setTabText(self.time_organizer.indexOf(self.gant_chart), QCoreApplication.translate("MainWindow", u"Gantt Chart", None))
        self.time_organizer.setTabText(self.time_organizer.indexOf(self.calendar), QCoreApplication.translate("MainWindow", u"Calendar", None))
        self.time_organizer.setTabText(self.time_organizer.indexOf(self.todo_list_2), QCoreApplication.translate("MainWindow", u"TodoList", None))
        self.outline_mode_label.setText(QCoreApplication.translate("MainWindow", u"Editor", None))
        self.outline_toggle_button.setText(QCoreApplication.translate("MainWindow", u"Switch to Reader", None))
        self.outline_editor.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Write your outline markup here using Markdown.", None))
        self.TaskTabs.setTabText(self.TaskTabs.indexOf(self.todo_list), QCoreApplication.translate("MainWindow", u"Outline", None))
        self.short_quiz_title_label.setText(QCoreApplication.translate("MainWindow", u"Short Quiz", None))
        self.short_quiz_status_label.setText(QCoreApplication.translate("MainWindow", u"0 chapters loaded", None))
        self.short_quiz_add_chapter_button.setText(QCoreApplication.translate("MainWindow", u"Add Chapter", None))
        self.short_quiz_import_button.setText(QCoreApplication.translate("MainWindow", u"Import", None))
        self.short_quiz_export_button.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        self.short_quiz_chapter_header_label.setText(QCoreApplication.translate("MainWindow", u"Chapters", None))
        self.short_quiz_question_header_label.setText(QCoreApplication.translate("MainWindow", u"Questions", None))
        self.short_quiz_question_status_label.setText(QCoreApplication.translate("MainWindow", u"0 questions", None))
        self.short_quiz_add_question_button.setText(QCoreApplication.translate("MainWindow", u"Add Question", None))
        self.short_quiz_edit_question_button.setText(QCoreApplication.translate("MainWindow", u"Edit", None))
        self.short_quiz_delete_question_button.setText(QCoreApplication.translate("MainWindow", u"Delete", None))
        self.short_quiz_answer_header_label.setText(QCoreApplication.translate("MainWindow", u"Answer Board", None))
        self.TaskTabs.setTabText(self.TaskTabs.indexOf(self.short_quiz), QCoreApplication.translate("MainWindow", u"ShortQuiz", None))
        self.long_quiz_title_label.setText(QCoreApplication.translate("MainWindow", u"Long Quiz", None))
        self.long_quiz_status_label.setText(QCoreApplication.translate("MainWindow", u"0 chapters loaded", None))
        self.long_quiz_add_chapter_button.setText(QCoreApplication.translate("MainWindow", u"Add Chapter", None))
        self.long_quiz_import_button.setText(QCoreApplication.translate("MainWindow", u"Import", None))
        self.long_quiz_export_button.setText(QCoreApplication.translate("MainWindow", u"Export", None))
        self.long_quiz_chapter_header_label.setText(QCoreApplication.translate("MainWindow", u"Chapters", None))
        self.long_quiz_question_header_label.setText(QCoreApplication.translate("MainWindow", u"Questions", None))
        self.long_quiz_question_status_label.setText(QCoreApplication.translate("MainWindow", u"0 questions", None))
        self.long_quiz_add_question_button.setText(QCoreApplication.translate("MainWindow", u"Add Question", None))
        self.long_quiz_edit_question_button.setText(QCoreApplication.translate("MainWindow", u"Edit", None))
        self.long_quiz_delete_question_button.setText(QCoreApplication.translate("MainWindow", u"Delete", None))
        self.long_quiz_answer_header_label.setText(QCoreApplication.translate("MainWindow", u"Answer Board", None))
        self.long_quiz_score_label.setText("")
        self.long_quiz_submit_button.setText(QCoreApplication.translate("MainWindow", u"Submit", None))
        self.TaskTabs.setTabText(self.TaskTabs.indexOf(self.long_quiz), QCoreApplication.translate("MainWindow", u"LongQuiz", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        self.menuTools.setTitle(QCoreApplication.translate("MainWindow", u"Tools", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
        self.Subject.setWindowTitle(QCoreApplication.translate("MainWindow", u"Subject List", None))
    # retranslateUi


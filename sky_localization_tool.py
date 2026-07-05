#!/usr/bin/env python3
import os
import sys
import re
import shutil
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import (QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter,
                          QTextCharFormat, QTextDocument, QKeySequence, QShortcut)
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPlainTextEdit, QWidget, 
                             QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
                             QFileDialog, QMessageBox, QLineEdit, QCheckBox)

# =====================================================================
# ⚙️ НАСТРОЙКА ПУТИ (Программа будет сразу открываться в этой папке)
# =====================================================================
DEFAULT_STRINGS_PATH = r"D:/Sky_arhiv_versii/Sky Children of the Light/data/assets/initial/Data"

# Стилизация под VS Code (Dark Theme)
DARK_STYLE = """
    QMainWindow, QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas', 'Segoe UI', monospace; }
    QPushButton { background-color: #0e639c; color: white; border: none; padding: 8px 15px; font-weight: bold; border-radius: 3px; font-size: 10pt; }
    QPushButton:hover { background-color: #1177bb; }
    QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3c3c3c; font-size: 11pt; }
    QLabel { font-size: 10pt; color: #858585; }
    QLineEdit { background-color: #3c3c3c; color: #d4d4d4; border: 1px solid #5a5a5a; padding: 5px; border-radius: 3px; font-size: 10pt; }
    QLineEdit:focus { border: 1px solid #0e639c; }
    QCheckBox { font-size: 9pt; color: #d4d4d4; }
"""

# =====================================================================
# 📑 МОДУЛЬ НУМЕРАЦИИ СТРОК (КАК В VS CODE)
# =====================================================================
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor
    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num /= 10
            digits += 1
        space = 15 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#2d2d2d"))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#858585"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1

# =====================================================================
# 🎨 УМНАЯ ПОДСВЕТКА СИНТАКСИСА ИГРОВЫХ ТЕГОВ
# =====================================================================
class StringsHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.rules = []
        
        # Ключи локализации (до знака равно)
        key_format = QTextCharFormat()
        key_format.setForeground(QColor("#9cdcfe"))
        self.rules.append((r'^\s*"[^"]*"', key_format))
        
        # Значения строк (внутри кавычек после знака равно)
        val_format = QTextCharFormat()
        val_format.setForeground(QColor("#ce9178"))
        self.rules.append((r'=\s*"[^"]*"', val_format))
        
        # Игровые теги (<2>, <b>, </2> и т.д.)
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor("#569cd6"))
        self.rules.append((r'<[^>]+>', tag_format))
        
        # Переменные подстановки ( {{1}}, {{2}} )
        var_format = QTextCharFormat()
        var_format.setForeground(QColor("#4ec9b0"))
        self.rules.append((r'\{\{[^\}]+\}\}', var_format))
        
        # Спецсимволы переноса строки (\n)
        slash_format = QTextCharFormat()
        slash_format.setForeground(QColor("#d7ba7d"))
        self.rules.append((r'\\n', slash_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)

# =====================================================================
# 🔎 ПАНЕЛЬ ПОИСКА (Ctrl+F, как в VS Code)
# =====================================================================
class FindBar(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.hide()

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Найти...")
        self.input.textChanged.connect(self.on_text_changed)
        self.input.returnPressed.connect(self.find_next)

        self.case_checkbox = QCheckBox("Учитывать регистр")

        self.count_label = QLabel("")
        self.count_label.setFixedWidth(90)

        self.btn_prev = QPushButton("▲")
        self.btn_prev.setFixedWidth(32)
        self.btn_prev.clicked.connect(self.find_prev)

        self.btn_next = QPushButton("▼")
        self.btn_next.setFixedWidth(32)
        self.btn_next.clicked.connect(self.find_next)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedWidth(32)
        self.btn_close.clicked.connect(self.hide_bar)

        layout.addWidget(self.input)
        layout.addWidget(self.count_label)
        layout.addWidget(self.btn_prev)
        layout.addWidget(self.btn_next)
        layout.addWidget(self.case_checkbox)
        layout.addWidget(self.btn_close)
        layout.addStretch()
        self.setLayout(layout)

        # Esc закрывает панель поиска
        close_shortcut = QShortcut(QKeySequence("Escape"), self.input)
        close_shortcut.activated.connect(self.hide_bar)

        # Shift+Enter - искать в обратную сторону
        prev_shortcut = QShortcut(QKeySequence("Shift+Return"), self.input)
        prev_shortcut.activated.connect(self.find_prev)

    def show_bar(self):
        self.show()
        self.input.setFocus()
        self.input.selectAll()
        if self.input.text():
            self.on_text_changed(self.input.text())

    def hide_bar(self):
        self.hide()
        self.editor.setFocus()

    def _flags(self, backward=False):
        flags = QTextDocument.FindFlag(0)
        if self.case_checkbox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags

    def on_text_changed(self, text):
        self._update_count(text)
        if not text:
            return
        # начинаем поиск сначала документа при каждом новом вводе
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        self._do_find(text, backward=False)

    def _update_count(self, text):
        if not text:
            self.count_label.setText("")
            return
        plain = self.editor.toPlainText()
        haystack = plain if self.case_checkbox.isChecked() else plain.lower()
        needle = text if self.case_checkbox.isChecked() else text.lower()
        count = haystack.count(needle) if needle else 0
        self.count_label.setText(f"{count} совпад.")

    def _do_find(self, text, backward):
        found = self.editor.find(text, self._flags(backward))
        if not found:
            # не нашли дальше по документу - оборачиваемся в начало/конец
            cursor = self.editor.textCursor()
            cursor.movePosition(
                cursor.MoveOperation.End if backward else cursor.MoveOperation.Start
            )
            self.editor.setTextCursor(cursor)
            self.editor.find(text, self._flags(backward))

    def find_next(self):
        text = self.input.text()
        if text:
            self._do_find(text, backward=False)

    def find_prev(self):
        text = self.input.text()
        if text:
            self._do_find(text, backward=True)


# =====================================================================
# 🏛 ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ
# =====================================================================
class SkyLocalizationTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sky: Children of the Light — Localization Tool 📝")
        self.setGeometry(100, 100, 950, 750)
        self.setStyleSheet(DARK_STYLE)
        self.current_file_path = ""

        # Главный контейнер
        main_widget = QWidget()
        layout = QVBoxLayout()

        # Верхняя панель с кнопками
        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("📂 Открыть Localizable.strings")
        self.btn_open.clicked.connect(self.open_file)
        self.btn_save = QPushButton("💾 Сохранить и применить в игре")
        self.btn_save.clicked.connect(self.save_file)
        
        top_bar.addWidget(self.btn_open)
        top_bar.addWidget(self.btn_save)
        top_bar.addStretch() # Сдвигает кнопки влево
        layout.addLayout(top_bar)

        # Статус-бар под кнопками
        self.lbl_status = QLabel("Файл не выбран. Нажмите кнопку 'Открыть' для начала редактирования.")
        layout.addWidget(self.lbl_status)

        # Продвинутый текстовый редактор
        self.editor = CodeEditor()
        self.highlighter = StringsHighlighter(self.editor.document())
        layout.addWidget(self.editor)

        # Панель поиска (скрыта по умолчанию, вызывается через Ctrl+F)
        self.find_bar = FindBar(self.editor)
        layout.addWidget(self.find_bar)

        find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        find_shortcut.activated.connect(self.find_bar.show_bar)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть файл локализации", DEFAULT_STRINGS_PATH, "Файлы строк (*.strings *.txt)"
        )
        if path:
            self.current_file_path = path
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.editor.setPlainText(f.read())
                self.lbl_status.setText(f"🟢 Активный файл: {path}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка чтения", f"Не удалось прочитать файл:\n{str(e)}")

    def save_file(self):
        if not self.current_file_path:
            QMessageBox.warning(self, "Внимание", "Сначала откройте файл через кнопку 'Открыть'!")
            return
            
        try:
            # 1. АВТО-БЭКАП: Создаем резервную копию перед записью
            backup_path = self.current_file_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(self.current_file_path, backup_path)

            # 2. ЗАПИСЬ: Сохраняем измененный текст прямо в файл игры
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
                
            QMessageBox.information(
                self, "Успех!", 
                "Файл локализации успешно обновлен прямо в папке игры!\n\nОригинал сохранен рядом с расширением .strings.bak"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось перезаписать файл:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SkyLocalizationTool()
    window.show()
    sys.exit(app.exec())

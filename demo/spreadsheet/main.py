import sys
import re
from functools import partial
import traceback
from pathlib import Path
import json
import datetime  # noqa
from itertools import product
from code import InteractiveConsole
from queue import Queue
import warnings
import html
from io import StringIO
import csv
from textwrap import dedent
import copy

from PyQt5.QtWidgets import (
    QStatusBar,
    QMainWindow,
    QToolBar,
    QApplication,
    QAction,
    QTableWidget,
    QTableWidgetItem,
    QItemDelegate,
    QStyle,
    QMessageBox,
    QFileDialog,
    QDockWidget,
    QPlainTextEdit,
    QToolTip,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)
from PyQt5.QtGui import QIcon, QFont, QFontMetrics, QTextCursor
from PyQt5.QtCore import (
    pyqtSignal,
    Qt,
    QSize,
    QEvent,
    QObject,
    pyqtSlot,
    QThread,
    QByteArray,
)
import PIL.Image
from PIL.ImageQt import ImageQt
import dateutil

try:
    import matplotlib
    import matplotlib.artist
    import matplotlib.pyplot as mpl

    warnings.filterwarnings(
        "ignore", category=matplotlib.cbook.deprecation.MatplotlibDeprecationWarning
    )
    HAS_MATPLOTLIB = True
except:  # noqa
    HAS_MATPLOTLIB = False

from calcengine import CalcEngine
from syntax import PythonHighlighter
from json_helper import JSONEncoder, JSONDecoder, InvalidCellDuringCopyException

if hasattr(Qt, "AA_EnableHighDpiScaling"):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

if hasattr(Qt, "AA_UseHighDpiPixmaps"):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


CALC_ENGINE = CalcEngine()
FUNC_PREFIX = ""
INIT_ROWS, INIT_COLS = 100, 20


CODE_FONT = QFont()
CODE_FONT.setFamily("Courier")
CODE_FONT.setStyleHint(QFont.Monospace)
CODE_FONT.setFixedPitch(True)
CODE_FONT.setPointSize(10)


def new_name_space():
    ns = dict()
    ns["CE"] = CALC_ENGINE
    ns["datetime"] = datetime
    return ns


NAME_SPACE = new_name_space()


class CellData:
    __slots__ = ("r1", "c1", "_formula", "_value", "_format", "_func")

    def __init__(self, r1, c1, formula=None, value=None, format=None):
        self.r1 = r1
        self.c1 = c1
        self._formula = formula
        self._value = value
        self._format = format
        self._func = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        # convert matplotlib artist into png images
        if HAS_MATPLOTLIB and isinstance(val, matplotlib.artist.Artist):
            canvas = val.figure.canvas
            canvas.draw()
            self._value = PIL.Image.frombytes(
                "RGB", canvas.get_width_height(), canvas.tostring_rgb(),
            )
            mpl.close(val.figure)
        else:
            self._value = val

    @property
    def formula(self):
        return self._formula

    @formula.setter
    def formula(self, val):
        self._formula = val
        self._func = None

    @property
    def format(self):
        return self._format

    @format.setter
    def format(self, val):
        self._format = val

    def formatted(self):
        try:
            return format(self.value, self.format or "")
        except:  # noqa
            return str(self.value)

    FORMULA_REGEX = r"(R(\[?(?:-?\d+|)\]?)C(\[?(?:-?\d+|)\]?)(?![A-Z])(?:\:R(\[?(?:-?\d+|)\]?)C(\[?(?:-?\d+|)\]?))?)(?![\d:])"

    @property
    def func(self):
        """Converts cell formula to node function"""
        if not self._func:
            fn_name = f"{FUNC_PREFIX}R{self.r1}C{self.c1}"

            # remove "=" at start as not needed
            # but used to old excel habits
            formula = self.formula
            if formula.startswith("="):
                formula = formula[1:]

            # don't do any substitutions to string literals!
            if not is_string_literal(formula):

                # replace date literals yyyy-mm-dd with dates(...)
                formula = re.sub(
                    r"([1-9]\d{3})-0*([1-9]\d?)-0*([1-9]\d?)",
                    r"datetime.date(\1, \2, \3)",
                    formula,
                    flags=re.IGNORECASE,
                )

                # convert RaCb to _bk_RaCb() and and RaCb:RxCy strings
                # to [[_bk_RaCb(), ..], .., [.., _bk_RxRy()]]
                # optionally support R[da]C[db] relative refs

                def _to_abs(s, origin):
                    if not s:
                        return origin
                    elif s.isdigit():
                        return int(s)
                    elif s.startswith("[") and s.endswith("]"):
                        return origin + int(s[1:-1])
                    else:
                        raise RuntimeError(f"could not parse {s}")

                def _to_ce_func(mo):
                    expr, r1, c1, r2, c2 = mo.groups()
                    r1, c1 = _to_abs(r1, self.r1), _to_abs(c1, self.c1)
                    r2, c2 = _to_abs(r2, self.r1), _to_abs(c2, self.c1)
                    if ":" in expr:
                        text = "[%s]" % ",".join(
                            [
                                "[%s]"
                                % ",".join(
                                    [
                                        f"{FUNC_PREFIX}R{r}C{c}()"
                                        for c in range(c1, c2 + 1)
                                    ]
                                )
                                for r in range(r1, r2 + 1)
                            ]
                        )
                    else:
                        text = f"{FUNC_PREFIX}R{r1}C{c1}()"
                    return text

                formula = re.sub(
                    CellData.FORMULA_REGEX, _to_ce_func, formula, flags=re.IGNORECASE,
                )

            fn_def = f"def {fn_name}(): return {formula}\n"

            # creates the function
            # TODO: rather than pollute namespace
            # with many functions perhaps store them
            # in a dictionary referenced by row, col.
            NAME_SPACE.pop(fn_name, None)
            exec(fn_def, NAME_SPACE)
            fn = NAME_SPACE[fn_name]
            fn = CALC_ENGINE.watch(path="GUI..")(fn)
            NAME_SPACE[fn_name] = fn
            self._func = fn

        return self._func


def show_exception(exc, parent=None):
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Warning)
    msg.setText(str(exc))
    msg.setWindowTitle("Error")
    msg.setDetailedText(
        "".join(traceback.TracebackException.from_exception(exc).format())
    )
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()


class DisplayDelegate(QItemDelegate):
    def paint(self, painter, option, index):
        row = index.row()
        col = index.column()

        if (row, col) in self.parent().data:
            cell_data = self.parent().data[(row, col)]
            try:
                if isinstance(cell_data.value, PIL.Image.Image):
                    painter.drawImage(option.rect, ImageQt(cell_data.value))
                else:
                    painter.drawText(option.rect, Qt.AlignLeft, cell_data.formatted())
                return
            except Exception as exc:  # noqa
                pass

        super().paint(painter, option, index)

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.ToolTip:
            row = index.row()
            col = index.column()

            if (row, col) in self.parent().data:
                cell_data = self.parent().data[(row, col)]
                tooltip = (
                    f"{cell_data.formula}\n{type(cell_data.value)}\n{cell_data.value}"
                )
                QToolTip.showText(event.globalPos(), tooltip, view)
        return True


def is_string_literal(expr):
    # TODO: check for escaped quotes
    for q in ["'", '"']:
        if expr.startswith(q) and expr.endswith(q) and q not in expr[1:-1]:
            return True
    return False


def get_literal(formula):
    """Determine if literal number, date or string.
    Return casted value if it is otherwise None."""
    try:
        return int(formula)
    except:  # noqa
        try:
            return float(formula)
        except ValueError:
            try:
                return datetime.date(*map(int, formula.split("-")))
            except:  # noqa
                if is_string_literal(formula):
                    return formula
    return None


class GridEditor(QTableWidget):
    cellEditingStarted = pyqtSignal(int, int)

    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.refresh_header_labels()

        # stores the cell data sparsely
        self.data: dict[tuple[int, int], CellData] = {}

        # events
        self.itemChanged.connect(self.item_changed)
        self.itemSelectionChanged.connect(self.item_selection_changed)
        self.setItemDelegate(DisplayDelegate(self))

    def sizeHintForRow(self, row):
        heights = [22]
        for key, cell_data in self.data.items():
            if key[0] == row:
                if isinstance(cell_data.value, PIL.Image.Image):
                    heights.append(cell_data.value.height)
                else:
                    heights.append(self.fontMetrics().height())
        return max(heights)

    def sizeHintForColumn(self, col):
        widths = [50]
        for key, cell_data in self.data.items():
            if key[1] == col:
                if isinstance(cell_data.value, PIL.Image.Image):
                    widths.append(cell_data.value.width)
                else:
                    longest_line = max(cell_data.formatted().splitlines(), key=len)
                    widths.append(self.fontMetrics().width(longest_line))
        return max(widths)

    def move_to_relative_cell(self, dr, dc):
        next_index = self.model().index(
            self.currentIndex().row() + dr, self.currentIndex().column() + dc
        )
        self.setCurrentIndex(next_index)

    def get_block_info(self):
        # get block information, check if contiguous
        coors = [(i.row(), i.column()) for i in self.selectedIndexes()]
        rows, cols = zip(*coors)
        r_min, c_min, r_max, c_max = min(rows), min(cols), max(rows), max(cols)
        is_cont = set(product(range(r_min, r_max + 1), range(c_min, c_max + 1))) == set(
            coors
        )
        return is_cont, r_min, c_min, r_max, c_max

    def auto_fill(self, direction):
        is_cont, r_min, c_min, r_max, c_max = self.get_block_info()

        # choose parallel/perpendicular directions
        if direction == "down":
            par_min, par_max, per_min, per_max = r_min, r_max, c_min, c_max
            C_ = lambda x, y: (x, y)  # noqa
        elif direction == "right":
            par_min, par_max, per_min, per_max = c_min, c_max, r_min, r_max
            C_ = lambda x, y: (y, x)  # noqa
        else:
            return

        if is_cont and par_max > par_min:
            for y in range(per_min, per_max + 1):
                item_1 = self.item(*C_(par_min, y))
                item_2 = self.item(*C_(par_min + 1, y))
                lit_1 = get_literal(item_1.text()) if item_1 else None
                lit_2 = get_literal(item_2.text()) if item_2 else None
                if (
                    par_max > par_min + 1
                    and lit_1
                    and lit_2
                    and type(lit_1) == type(lit_2)
                    and isinstance(lit_1, (int, float, datetime.date))
                ):
                    if isinstance(lit_1, (datetime.date,)):
                        diff = dateutil.relativedelta.relativedelta(lit_2, lit_1)
                    else:
                        diff = lit_2 - lit_1
                    prev = lit_2
                    for x in range(par_min + 2, par_max + 1):
                        new = prev + diff
                        self.set_cell_data(
                            *C_(x, y), formula=str(new), value=None, fmt=None
                        )
                        self.setItem(*C_(x, y), QTableWidgetItem(str(new)))
                        prev = new
                elif item_1:
                    form_1 = item_1.text()
                    for x in range(par_min + 1, par_max + 1):
                        self.set_cell_data(
                            *C_(x, y), formula=form_1, value=None, fmt=None
                        )
                        self.setItem(*C_(x, y), QTableWidgetItem(form_1))
            self.calculate()

    # emulate some Excel style key bindings
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.modifiers() & Qt.ControlModifier:
            # pressing control + d / r fills down / right (unlike excel will follow pattern)
            if event.key() == Qt.Key_D:
                self.auto_fill(direction="down")

            if event.key() == Qt.Key_R:
                self.auto_fill(direction="right")

            if event.key() == Qt.Key_C:
                self.copy_cell(attr="formula")

            if event.key() == Qt.Key_X:
                self.copy_cell(attr="formula", clear=True)

            if event.key() == Qt.Key_V:
                self.paste_cell()

            return True
        # pressing enter in cell (not while editing moves down one cell)
        if event.type() == QEvent.ShortcutOverride and event.key() == Qt.Key_Return:
            self.move_to_relative_cell(1, 0)
            return True
        return super().eventFilter(obj, event)

    def item_changed(self, item):
        self.set_cell_data(item.row(), item.column(), formula=str(item.text()))
        self.calculate()

    def refresh_header_labels(self):
        self.setHorizontalHeaderLabels(
            [f"{i}" for i in range(1, self.columnCount() + 1)]
        )

    def invalidate_cell(self):
        for index in self.selectedIndexes():
            row, col = index.row(), index.column()
            if (row, col) in self.data:
                cell_data = self.data[(row, col)]
                cell_data.func.invalidate()
        self.calculate()

    def clear_cell_at(self, row, col):
        if (row, col) in self.data:
            self.setItem(row, col, QTableWidgetItem(""))
            cell_data = self.data.pop((row, col))
            cell_data.func.invalidate()
            del NAME_SPACE[cell_data.func.__name__]

    def clear_cell(self):
        for index in self.selectedIndexes():
            self.clear_cell_at(index.row(), index.column())
        self.calculate()

    def format_cell(self):
        for index in self.selectedIndexes():
            row, col = index.row(), index.column()
            if (row, col) in self.data:
                self.data[(row, col)].format = (
                    self.parent().toolbar_controls["textfield_format"].text()
                )
                self.raise_data_changed(row, col)

    def copy_cell(self, attr, clear=False):
        is_cont, r_min, c_min, r_max, c_max = self.get_block_info()

        if is_cont:
            data = [[""] * (c_max - c_min + 1) for _ in range(r_max - r_min + 1)]
            for r in range(r_min, r_max + 1):
                for c in range(c_min, c_max + 1):
                    if (r, c) in self.data:
                        data[r - r_min][c - c_min] = getattr(self.data[(r, c)], attr)
                        if clear:
                            self.clear_cell_at(r, c)
            buffer = StringIO()
            csv.writer(buffer, dialect="excel-tab").writerows(data)
            QApplication.clipboard().setText(buffer.getvalue())
        else:
            self.parent().status_bar.showMessage(
                "Can only copy contiguous region!", 2000
            )

    def paste_cell(self):
        text = QApplication.clipboard().text()
        indexes = self.selectedIndexes()
        if len(indexes) == 1:
            r_min, c_min = indexes[0].row(), indexes[0].column()
            for r_delta, row_data in enumerate(
                csv.reader(text.splitlines(), dialect="excel-tab")
            ):
                for c_delta, formula in enumerate(row_data):
                    self.set_cell_data(
                        r_min + r_delta, c_min + c_delta, formula=formula
                    )
                    self.setItem(
                        r_min + r_delta, c_min + c_delta, QTableWidgetItem(formula)
                    )
            self.calculate()
        else:
            self.parent().status_bar.showMessage(
                "Can only paste if single top left cell selected!", 2000
            )

    def item_selection_changed(self):
        formats = {
            self.data[(ix.row(), ix.column())].format
            for ix in self.selectedIndexes()
            if (ix.row(), ix.column()) in self.data
        }

        line_edit = self.parent().toolbar_controls["textfield_format"]

        if len(formats) == 1:
            line_edit.setText(formats.pop())
        else:
            line_edit.setText("")

    def calculate(self):
        self.parent().status_bar.showMessage("Calculating..", 1000)
        # TODO: do a topological sort here?
        for (row, col), cell_data in self.data.items():
            try:
                cell_data.func()
            except Exception as e:
                self.parent().status_bar.showMessage(f"Error: {e}", 2000)
                # raise DC event to reflect error
                self.data[(row, col)].value = f"#ERR: {e}"
                self.raise_data_changed(row, col)

    def raise_data_changed(self, row, col):
        index = self.model().index(row, col)
        self.dataChanged(index, index, [Qt.EditRole])

    def set_cell_data(self, row, col, **kwds):
        """Also takes optional parameters formula, value, fmt"""
        if (row, col) in self.data:
            cell_data = self.data[(row, col)]
        else:
            self.data[(row, col)] = cell_data = CellData(row + 1, col + 1)
        try:
            # to avoid clobbering cell data attributes
            # if nothing needs to be changed we check
            # kw args exist one by one.

            if "formula" in kwds:
                cell_data.formula = kwds["formula"]

            if "value" in kwds:
                # to detect if we have deserialized an invalid cell
                # with in a deep structure (eg list of lists etc), we
                # call deepcopy. Invalid cell's __deepcopy__ will raise
                # an exception if called.
                try:
                    value = kwds["value"]
                    _ = copy.deepcopy(value)
                    cell_data.value = value
                    cell_data.func.set_value(value)
                except InvalidCellDuringCopyException:
                    cell_data.func.invalidate()
            else:
                # if we don't have a value, reset the node
                cell_data.func.invalidate()

            if "fmt" in kwds:
                cell_data.format = kwds["fmt"]

            def refresh_cell_callback(row, col, res, *args_, **kwds_):
                self.data[(row, col)].value = res
                self.raise_data_changed(row, col)

            cell_data.func.node_calculated.append(
                partial(refresh_cell_callback, row, col)
            )

            cell_data.func.node_value_set.append(
                partial(refresh_cell_callback, row, col)
            )

        except Exception as e:
            self.parent().status_bar.showMessage(f"Error: {e}", 2000)
            # raise DC event to reflect error
            self.data[(row, col)].value = f"#ERR: {e}"
            self.raise_data_changed(row, col)

    def resize_all(self):
        self.resizeColumnsToContents()
        self.resizeRowsToContents()

    def import_data(self, data):
        self.clear()

        # data in format:
        # "r1", "c1", "formula", "value", "format"
        # NOTE: we block signals to prevent itemChanged being triggered
        # and calculate() being called too early.
        self.blockSignals(True)
        for r1, c1, formula, value, fmt in data:
            self.set_cell_data(r1 - 1, c1 - 1, formula=formula, value=value, fmt=fmt)
            self.setItem(r1 - 1, c1 - 1, QTableWidgetItem(formula))
        self.blockSignals(False)

        # resize rows, cols if necessary
        max_row, max_col = [max(d) for d in zip(*self.data.keys())]
        if self.columnCount() <= max_col:
            self.setColumnCount(max_col + 1)
            self.refresh_header_labels()
        if self.rowCount() <= max_row:
            self.setRowCount(max_row + 1)

        self.calculate()

    def export_data(self):
        data = []
        for (row, col), cell_data in self.data.items():
            data.append(
                [row + 1, col + 1, cell_data.formula, cell_data.value, cell_data.format]
            )
        return data

    def clear(self):
        self.data = {}
        self.clearContents()
        self.resize_all()
        CALC_ENGINE.clear_cache()

    @property
    def state(self):
        h_state = self.horizontalHeader().saveState()
        v_state = self.verticalHeader().saveState()
        return {
            "h_state": h_state.toBase64().data().decode(),
            "v_state": v_state.toBase64().data().decode(),
        }

    @state.setter
    def state(self, val):
        self.horizontalHeader().restoreState(
            QByteArray.fromBase64(bytes(val["h_state"], encoding="utf8"))
        )
        self.verticalHeader().restoreState(
            QByteArray.fromBase64(bytes(val["v_state"], encoding="utf8"))
        )


class CodeEditor(QPlainTextEdit):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        self.highlighter = PythonHighlighter(self.document())
        self.setFont(CODE_FONT)
        metrics = QFontMetrics(CODE_FONT)
        self.setTabStopWidth(4 * metrics.width(" "))

    def keyPressEvent(self, event):
        # insert 4 spaces instead of tab
        if event.key() == Qt.Key_Tab:
            self.textCursor().insertText("    ")
        else:
            super().keyPressEvent(event)

    def clear(self):
        self.setPlainText("")

    def import_code(self, code):
        self.setPlainText(code)

    def export_code(self):
        return self.toPlainText()

    def execute_code(self):
        try:
            code = self.export_code()
            exec(code, NAME_SPACE)
        except Exception as exc:
            show_exception(exc, parent=self)


class QueueWriteStream:
    """Emulates file handle writing messages to queue"""

    def __init__(self, queue):
        self.queue = queue

    def write(self, msg):
        self.queue.put(msg)

    def flush(self):
        pass


class QueueBroadcaster(QObject):
    """Broadcasts queue items via event slot"""

    new_queue_item = pyqtSignal(str)

    def __init__(self, queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue

    @pyqtSlot()
    def loop(self):
        while True:
            self.new_queue_item.emit(self.queue.get())


class ConsolePanel(QWidget):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        vbox = QVBoxLayout()

        prompt_area = QHBoxLayout()
        prompt_area.addWidget(QLabel("> "))
        self.input = QLineEdit()
        prompt_area.addWidget(self.input)

        self.log = QPlainTextEdit()
        vbox.addWidget(self.log)
        vbox.addLayout(prompt_area)

        self.setLayout(vbox)

        self.log.setFont(CODE_FONT)
        self.input.setFont(CODE_FONT)

        self.console = InteractiveConsole(locals=NAME_SPACE)

        self.input.returnPressed.connect(self.send_console_command)

    def send_console_command(self):
        text = str(self.input.text())
        self.console.push(text)
        self.append_to_log("black", f">>> {text}\n")
        self.input.clear()

    def append_to_log(self, color, msg):
        self.log.moveCursor(QTextCursor.End)
        html_msg = html.escape(msg).replace("\n", "<br>")
        self.log.textCursor().insertHtml(f'<font color="{color}">{html_msg}</font>')
        self.log.moveCursor(QTextCursor.End)


class Window(QMainWindow):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)

        # TODO: save state in settings file on exit
        self.setMinimumSize(1000, 600)
        # self.resize(QDesktopWidget().availableGeometry(self).size() * 0.7)
        self.set_title()

        self.main_grid = GridEditor(INIT_ROWS, INIT_COLS, self)
        self.setCentralWidget(self.main_grid)

        self.text_editor = CodeEditor()
        self.text_editor_dock = QDockWidget("Code Editor", self)
        self.text_editor_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.text_editor_dock.setWidget(self.text_editor)
        self.addDockWidget(Qt.RightDockWidgetArea, self.text_editor_dock)

        self.console_panel = ConsolePanel()
        self.console_panel_dock = QDockWidget("Console", self)
        self.console_panel_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.console_panel_dock.setWidget(self.console_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.console_panel_dock)

        self.stdout_queue = Queue()
        sys.stdout = QueueWriteStream(self.stdout_queue)
        self.stdout_broadcaster = QueueBroadcaster(self.stdout_queue)
        self.stdout_broadcaster.new_queue_item.connect(
            partial(self.console_panel.append_to_log, "black")
        )
        self.stdout_queue_thread = QThread()
        self.stdout_broadcaster.moveToThread(self.stdout_queue_thread)
        self.stdout_queue_thread.started.connect(self.stdout_broadcaster.loop)
        self.stdout_queue_thread.start()

        self.stderr_queue = Queue()
        sys.stderr = QueueWriteStream(self.stderr_queue)
        self.stderr_broadcaster = QueueBroadcaster(self.stderr_queue)
        self.stderr_broadcaster.new_queue_item.connect(
            partial(self.console_panel.append_to_log, "red")
        )
        self.stderr_queue_thread = QThread()
        self.stderr_broadcaster.moveToThread(self.stderr_queue_thread)
        self.stderr_queue_thread.started.connect(self.stderr_broadcaster.loop)
        self.stderr_queue_thread.start()

        self.toolbar = QToolBar("Main toolbar")
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        self.toolbar_controls = dict()

        # standard icons from https://joekuan.wordpress.com/2015/09/23/list-of-qt-icons/
        # theme icons from https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
        for tb_config in [
            # fmt: off
            ["button", "open", "Open", "document-open", "Click to open.", self.open_file_dialog, False],
            ["button", "save", "Save As", "document-save-as", "Click to save.", self.save_file_dialog, False],
            ["button", "new", "New", "document-new", "Click to clear and start new sheet.", self.new_sheet, False],
            ["separator"],
            ["button", "calculate", "Calculate", "media-playback-start", "Click to calculate sheet.", self.calculate, False],
            ["button", "resize_all", "Resize", "zoom-fit-best", "Click to resize columns and rows to fit.", self.main_grid.resize_all, False],
            ["separator"],
            ["label", "Cell: "],
            ["button", "invalidate", "Invalidate", QStyle.SP_TrashIcon, "Click to invalidate selected cells.", self.main_grid.invalidate_cell, False],
            ["button", "copy_values", "Copy Values", "edit-copy", "Click to copy selected cell values.", partial(self.main_grid.copy_cell, "value"), False],
            ["button", "paste", "Paste", "edit-paste", "Click to paste.", self.main_grid.paste_cell, False],
            ["button", "clear", "Clear", "edit-clear", "Click to clear selected cells.", self.main_grid.clear_cell, False],
            ["textfield", "format", "Format Spec..", 100, self.main_grid.format_cell],
            ["separator"],
            ["button", "show_editor", "Editor", "accessories-text-editor", "Click to show editor.", self.text_editor_dock.show, False],
            ["button", "show_console", "Console", "utilities-terminal", "Click to show console.", self.console_panel_dock.show, False],
            ["separator"],
            ["button", "exit", "Exit", "application-exit", "Click to exit.", self.close, False],
            ["separator"],
            ["button", "help", "Help", "help-about", "Click for help and about.", self.show_help_dialog, False],
            # fmt: on
        ]:
            if tb_config[0] == "button":
                name, label, icon, status, func, checkable = tb_config[1:]
                if isinstance(icon, QStyle.StandardPixmap):
                    icon = QIcon(QApplication.style().standardIcon(icon))
                else:
                    icon = QIcon.fromTheme(icon)
                button = QAction(icon, label, self,)
                button.setStatusTip(status)
                button.triggered.connect(func)
                button.setCheckable(checkable)
                self.toolbar_controls[f"button_{name}"] = button
                self.toolbar.addAction(button)
            elif tb_config[0] == "separator":
                self.toolbar.addSeparator()
            elif tb_config[0] == "textfield":
                name, placeholder, max_width, func = tb_config[1:]
                line_edit = QLineEdit(self)
                line_edit.setPlaceholderText(placeholder)
                line_edit.setMaximumWidth(max_width)
                line_edit.returnPressed.connect(func)
                self.toolbar_controls[f"textfield_{name}"] = line_edit
                self.toolbar.addWidget(line_edit)
            elif tb_config[0] == "label":
                (label,) = tb_config[1:]
                self.toolbar.addWidget(QLabel(label))

        self.addToolBar(self.toolbar)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        # event filter needs to be in top level thread
        self.main_grid.installEventFilter(self.main_grid)

    def set_title(self, label=None):
        self.setWindowTitle("Simple Spreadsheet" + (f" - {label}" if label else ""))

    def calculate(self, s):
        self.main_grid.calculate()
        self.text_editor.execute_code()

    def new_sheet(self, s):
        self.clear_all()

    def clear_all(self):
        self.main_grid.clear()
        self.text_editor.clear()
        NAME_SPACE.clear()
        NAME_SPACE.update(new_name_space())
        NAME_SPACE["WINDOW"] = self
        NAME_SPACE["GRID"] = self.main_grid

    def show_help_dialog(self, s):
        detail = dedent(
            """\
            Keyboard shortcuts:

            CTRL + D: Fill down.
            CTRL + R: Fill right.
            CTRL + C: Copy cell formulas.
            CTRL + X: Cut cell formulas.
            CTRL + V: Paste cell formulas.

            For license information please see LICENSE text file included with this distribution.
        """
        )
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"Copyright © {datetime.date.today().year} Blair Azzopardi.")
        msg.setWindowTitle("About Simple Spreadsheet")
        msg.setDetailedText(detail)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def save_file_dialog(self, s):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save sheet data",
            "",
            "All Files (*);;Text Files (*.json)",
            options=options,
        )
        if file_name:
            self.save_file(file_name)

    def save_file(self, file):
        try:
            file = Path(file)
            file_data = {
                "data": self.main_grid.export_data(),
                "code": self.text_editor.export_code(),
                "grid_state": self.main_grid.state,
            }
            file.write_text(json.dumps(file_data, cls=JSONEncoder))
            self.set_title(file.name)
        except Exception as exc:
            show_exception(exc, self)

    def open_file_dialog(self, s):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load sheet data",
            "",
            "All Files (*);;Text Files (*.json)",
            options=options,
        )
        if file_name:
            self.open_file(file_name)

    def open_file(self, file):
        self.clear_all()
        file = Path(file)
        file_data = json.loads(file.read_text(), cls=JSONDecoder)
        # load & exec code, useful to load json importers
        self.text_editor.import_code(file_data["code"])
        self.text_editor.execute_code()
        # load grid data - do not calc
        self.main_grid.import_data(file_data["data"])
        self.set_title(file.name)
        # load grid state
        if "grid_state" in file_data:
            self.main_grid.state = file_data["grid_state"]


def main(args):
    # file = Path(__file__).parent / "samples/pandas.json"

    app = QApplication(args)
    w = Window()
    # w.open_file(file)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main(sys.argv)

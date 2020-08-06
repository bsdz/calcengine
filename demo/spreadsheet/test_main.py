import unittest
import re
import datetime
from itertools import count
from functools import partial
from random import gauss

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QAction
from PyQt5.QtCore import Qt, QPoint

from main import CellData
from main import Window


def _to_array(mo):
    print(mo.groups())
    return "GOT"


class MainTestCase(unittest.TestCase):
    def test_r1c1_regex(self):

        for formula, results in [
            ["r[-]c1", []],  # no match
            ["r3c4:r[-2][1]", []],  # no match
            ["r[2c1", [("r[2c1", "[2", "1", "", "")]],  # needs to tested manually
            ["rc1", [("rc1", "", "1", "", "")]],
            ["r[1]c1", [("r[1]c1", "[1]", "1", "", "")]],
            ["r[1]c[-1]", [("r[1]c[-1]", "[1]", "[-1]", "", "")]],
            ["r[-1]c1", [("r[-1]c1", "[-1]", "1", "", "")]],
            ["r1c1", [("r1c1", "1", "1", "", "")]],
            ["r1c1:r3c3", [("r1c1:r3c3", "1", "1", "3", "3")]],
            [
                "r1c1:r3c3 + r1c1:r3c3",
                [("r1c1:r3c3", "1", "1", "3", "3"), ("r1c1:r3c3", "1", "1", "3", "3")],
            ],
            ["exercise", []],  # no match
        ]:
            groups = re.findall(CellData.FORMULA_REGEX, formula, flags=re.IGNORECASE)
            self.assertEqual(groups, results)


class SpreadsheetAppTestCase(unittest.TestCase):
    def setUp(self):
        app = QApplication.instance()
        self.app = app or QApplication([])
        self.window = Window()

        # some useful shortcuts
        self.grid = self.window.main_grid
        self.gridvp = self.grid.viewport()
        self.tb = {
            k: self.window.toolbar.widgetForAction(obj)
            if isinstance(obj, QAction)
            else obj
            for k, obj in self.window.toolbar_controls.items()
        }

        self.window.show()
        # bring to foreground
        self.window.setWindowState(
            (self.window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive
        )
        QTest.qWaitForWindowExposed(self.window)

    def tearDown(self):
        # self.app.exec_()
        pass

    def cell_pos(self, row, col):
        """center x,y position of row, col"""
        grid = self.grid
        return QPoint(
            grid.columnViewportPosition(col) + grid.columnWidth(col) // 2,
            grid.rowViewportPosition(row) + grid.rowHeight(row) // 2,
        )

    def test_filldown(self):
        gridvp = self.grid.viewport()

        # date diff filldown
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(0, 0))
        QTest.keyClicks(gridvp.focusWidget(), "2020-1-1\r")
        QTest.keyClicks(gridvp.focusWidget(), "2020-2-1\r")
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(0, 0))
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.ShiftModifier, self.cell_pos(5, 0))
        QTest.keyClick(gridvp, "d", Qt.ControlModifier)
        output = [self.grid.data[(r, 0)].value for r in range(0, 6)]
        expected = [
            datetime.date(2020, 1, 1),
            datetime.date(2020, 2, 1),
            datetime.date(2020, 3, 1),
            datetime.date(2020, 4, 1),
            datetime.date(2020, 5, 1),
            datetime.date(2020, 6, 1),
        ]
        self.assertListEqual(output, expected)

        # formula fill down
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(0, 1))
        QTest.keyClicks(gridvp.focusWidget(), "5\r")
        QTest.keyClicks(gridvp.focusWidget(), "2*r[-1]c+3\r")
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(1, 1))
        QTest.mouseClick(gridvp, Qt.LeftButton, Qt.ShiftModifier, self.cell_pos(5, 1))
        QTest.keyClick(gridvp, "d", Qt.ControlModifier)
        output = [self.grid.data[(r, 1)].value for r in range(0, 6)]
        expected = [5, 13, 29, 61, 125, 253]
        self.assertListEqual(output, expected)

    def cell_typer(self, delay, row, col, text):
        """Enters text into cell with delay."""
        QTest.mouseClick(
            self.gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(row, col)
        )
        for ch in text:
            QTest.keyClicks(self.gridvp.focusWidget(), ch, Qt.NoModifier, -1)
            QTest.qWait(int(gauss(delay, 3)))

    def widget_typer(self, delay, widget, text):
        """Enters text into widget with delay."""
        for ch in text:
            QTest.keyClicks(widget, ch, Qt.NoModifier, -1)
            QTest.qWait(int(gauss(delay, 3)))

    def hover_click(self, delay, widget):
        QTest.mouseMove(widget)
        QTest.qWait(int(gauss(delay, 3)))
        QTest.mouseClick(widget, Qt.LeftButton)
        QTest.qWait(int(gauss(delay, 3)))

    def grid_select_range(self, rs, cs, rf, cf):
        QTest.mouseClick(
            self.gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(rs, cs)
        )
        QTest.mouseClick(
            self.gridvp, Qt.LeftButton, Qt.ShiftModifier, self.cell_pos(rf, cf)
        )

    @unittest.skip("For demo generation only")
    def test_demo(self):
        QTest.qWait(5000)

        delay = 50

        cell_typer = partial(self.cell_typer, delay)
        widget_typer = partial(self.widget_typer, delay)
        hover_click = partial(self.hover_click, 1000)

        QTest.keyClicks(
            self.window.text_editor,
            ("from random import uniform, gauss\r" "import pandas as pd\r"),
            Qt.NoModifier,
            delay,
        )

        hover_click(self.tb["button_calculate"])

        rs = 2
        rc = count(rs)
        cell_typer(next(rc), 0, '"Date"\r')
        cell_typer(next(rc), 0, "2020-1-1\r")
        cell_typer(next(rc), 0, "2020-2-1\r")

        rc = count(rs)
        cell_typer(next(rc), 1, '"Uniform"\r')
        cell_typer(next(rc), 1, "uniform(0,1)\r")

        rc = count(rs)
        cell_typer(next(rc), 2, '"Gauss"\r')
        cell_typer(next(rc), 2, "gauss(0,1)\r")

        # fill down
        self.grid_select_range(rs + 1, 0, rs + 9, 2)
        QTest.keyClick(self.gridvp, "d", Qt.ControlModifier, delay)

        # format
        self.grid_select_range(rs + 1, 1, rs + 9, 2)
        widget_typer(self.tb["textfield_format"], ".4f\r")

        # add pandas objects
        cell_typer(
            0,
            4,
            f'pd.DataFrame(r{rs+2}c1:r{rs+10}c3, columns=r{rs+1}c1:r{rs+1}c3[0]).set_index("Date")\r',
        )
        cell_typer(1, 4, f"r[-1]c.plot()\r")
        hover_click(self.tb["button_resize_all"])

        # invalidate
        self.grid_select_range(rs + 1, 1, rs + 9, 2)
        for _ in range(3):
            hover_click(self.tb["button_invalidate"])

        # type something into console
        widget_typer(self.window.console_panel.input, "dir()\r")

        # add some code
        QTest.keyClicks(
            self.window.text_editor,
            (
                "\r\r"
                "def tick():\r"
                "\tfor r in range(3, 12):\r"
                "\t\tfor c in range(1, 3):\r"
                "\t\t\tGRID.data[(r, c)].func.invalidate()\r"
                "\tGRID.calculate()\r"
                "\r\r"
            ),
            Qt.NoModifier,
            delay,
        )
        hover_click(self.tb["button_calculate"])

        # test in console
        widget_typer(self.window.console_panel.input, "tick()\r")
        widget_typer(self.window.console_panel.input, "tick()\r")

        # add timer
        # add some code
        QTest.keyClicks(
            self.window.text_editor,
            (
                "# start a timer\r"
                "from PyQt5.QtCore import QTimer\r"
                "timer = QTimer()\r"
                "timer.timeout.connect(tick)\r"
                "timer.start(1000)\r"
            ),
            Qt.NoModifier,
            delay,
        )
        hover_click(self.tb["button_calculate"])


if __name__ == "__main__":
    unittest.main()

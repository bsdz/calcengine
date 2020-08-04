import unittest
import re
import datetime
from itertools import chain

from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
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
        self.grid = self.window.main_grid
        self.gridvp = self.grid.viewport()
        self.window.show()
        # bring to foreground
        self.window.setWindowState(
            (self.window.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive
        )
        QTest.qWaitForWindowExposed(self.window)

    def tearDown(self):
        self.app.exec_()
        pass

    def cell_pos(self, row, col):
        """center x,y position of row, col"""
        grid = self.grid
        return QPoint(
            grid.columnViewportPosition(col) + grid.columnWidth(col) // 2,
            grid.rowViewportPosition(row) + grid.rowHeight(row) // 2,
        )

    def cell_typer(self, row, col, text, delay=50):
        """Enters text into cell with delay."""
        QTest.mouseClick(
            self.gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(row, col)
        )
        for ch in text:
            QTest.keyClicks(self.gridvp.focusWidget(), ch, Qt.NoModifier, -1)
            QTest.qWait(delay)

    @unittest.skip("")
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

    def test_demo(self):
        QTest.keyClicks(
            self.window.text_editor,
            "from random import uniform, gauss\r",
            Qt.NoModifier,
            50,
        )

        button_calc = self.window.toolbar.widgetForAction(
            self.window.toolbar_controls["button_calculate"]
        )
        button_invalid = self.window.toolbar.widgetForAction(
            self.window.toolbar_controls["button_invalidate"]
        )

        QTest.mouseMove(button_calc)
        QTest.mouseClick(button_calc, Qt.LeftButton)

        self.cell_typer(0, 0, '"Date"\r')
        self.cell_typer(1, 0, "2020-1-1\r")
        self.cell_typer(2, 0, "2020-2-1\r")

        self.cell_typer(0, 1, '"Uniform"\r')
        self.cell_typer(1, 1, "uniform(0,1)\r")

        self.cell_typer(0, 2, '"Gauss"\r')
        self.cell_typer(1, 2, "gauss(0,1)\r")

        # fill down
        QTest.mouseClick(self.gridvp, Qt.LeftButton, Qt.NoModifier, self.cell_pos(1, 0))
        QTest.mouseClick(self.gridvp, Qt.LeftButton, Qt.ShiftModifier, self.cell_pos(10, 2))
        QTest.keyClick(self.gridvp, "d", Qt.ControlModifier)

        # invalidate
        for _ in range(3):
            QTest.mouseMove(button_invalid)
            QTest.qWait(1000)
            QTest.mouseClick(button_invalid, Qt.LeftButton)



if __name__ == "__main__":
    unittest.main()

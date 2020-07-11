import unittest
import re

from main import CellData


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


if __name__ == "__main__":
    unittest.main()

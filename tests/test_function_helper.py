import unittest

from calcengine.function_helper import find_calls


def x(*args, **kwds):
    pass


def y(*args, **kwds):
    pass


def foo1(a, b):
    x(2, 3, 4)
    y(9, 8)


def foo2(a, b):
    x(2, 3, y=4)
    y(9, 8)


x.helper = None
y.helper = None


class Foo:
    def p(self):
        pass

    p.helper = None

    def q(self):
        pass

    q.helper = None

    def foo3(self, a, b):
        self.p(1, 5)
        self.q(2, 3, r=10)


class FunctionHelperTestCase(unittest.TestCase):
    def test_find_calls(self):
        for func, expected in [
            [foo1, [["x", (2, 3, 4), {}], ["y", (9, 8), {}]]],
            [foo2, [["x", (2, 3), {"y": 4}], ["y", (9, 8), {}]]],
            [Foo().foo3, [['p', (1, 5), {}], ['q', (2, 3), {'r': 10}]]],
        ]:
            with self.subTest(func.__name__):
                this = getattr(func, "__self__", None)
                found = find_calls(func, this)
                found_with_names = [[f[0].__name__, f[1], f[2]] for f in found]
                self.assertListEqual(found_with_names, expected)


if __name__ == "__main__":
    unittest.main()

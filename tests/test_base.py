import unittest
import logging

from calcengine import CalcEngine

# since module path can vary based on whether
# tests are run as module or as single file
# we hard code a prefix here.
PATH = "test."

ce = CalcEngine()


@ce.watch(path=PATH)
def a():
    return 100


@ce.watch(path=PATH)
def b():
    return a()


@ce.watch(path=PATH)
def c(x, y):
    return 2 * a() + x * y


@ce.watch(path=PATH)
def d(x, y=0):
    return 3 * b() + x - y


@ce.watch(path=PATH)
def e():
    _x = d(5, y=-3)
    return c(2, 3) - 5 + _x


@ce.watch(path=PATH)
def f():
    return d(0) + e()


g = lambda: d(0) + e()  # noqa
g = ce.watch(alias="g", path=PATH)(g)


class Foo:
    @ce.watch(path=PATH)
    def a(self):
        return 10

    @ce.watch(path=PATH)
    def b(self, x):
        return self.a() + x

    @ce.watch(path=PATH)
    def c(self):
        return self.a() + self.b(5)


def map_short_to_long_key(text):
    pos = text.rfind(":") + 2
    lhs, rhs = text[:pos], text[pos:]
    for sk, lk in ce.id_map.items():
        lhs = lhs.replace(sk, str(lk))
    if rhs:
        rhs = ", ".join(sorted([str(ce.id_map[_]) for _ in rhs.split(", ")]))
    return lhs + rhs


class CalcEngineBaseTestCase(unittest.TestCase):
    def setUp(self):
        ce.clear_cache()

    def test_simple_cascaded_function_calls(self):

        # 1st run calls everything
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            x1 = f()
        output = [map_short_to_long_key(msg) for msg in cm.output]
        expected = [
            f"DEBUG:calcengine.base:{PATH}.f called requiring: ['{PATH}.d', 0], {PATH}.e",
            f"DEBUG:calcengine.base:['{PATH}.d', 0] called requiring: {PATH}.b",
            f"DEBUG:calcengine.base:{PATH}.b called requiring: {PATH}.a",
            f"DEBUG:calcengine.base:{PATH}.a called requiring: ",
            f"DEBUG:calcengine.base:{PATH}.e called requiring: ['{PATH}.c', 2, 3], ['{PATH}.d', 5, '___KWDS___', 'y', -3]",
            f"DEBUG:calcengine.base:['{PATH}.d', 5, '___KWDS___', 'y', -3] called requiring: {PATH}.b",
            f"DEBUG:calcengine.base:['{PATH}.c', 2, 3] called requiring: {PATH}.a",
        ]
        self.assertListEqual(output, expected)

        # 2nd run doesn't call anything
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            # use dummmy log https://bugs.python.org/issue39385
            logging.getLogger("calcengine.base").debug("DUMMY")
            x2 = f()
        expected = ["DEBUG:calcengine.base:DUMMY"]
        self.assertListEqual(cm.output, expected)
        self.assertEqual(x1, x2)

        # invalidate node recalls invalidated path
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            c.invalidate(2, 3)
            x3 = f()
        output = [map_short_to_long_key(msg) for msg in cm.output]
        expected = [
            f"DEBUG:calcengine.base:{PATH}.f called requiring: ['{PATH}.d', 0], {PATH}.e",
            f"DEBUG:calcengine.base:{PATH}.e called requiring: ['{PATH}.c', 2, 3], ['{PATH}.d', 5, '___KWDS___', 'y', -3]",
            f"DEBUG:calcengine.base:['{PATH}.c', 2, 3] called requiring: {PATH}.a",
        ]
        self.assertListEqual(output, expected)
        self.assertEqual(x1, x3)

    def test_class_instances(self):

        foo1 = Foo()
        foo2 = Foo()

        ids_to_names = {
            hex(id(foo1)): "INS_foo1",
            hex(id(foo2)): "INS_foo2",
        }

        def map_id_to_name(msg):
            for id_, name in ids_to_names.items():
                msg = msg.replace(id_, name)
            return msg

        # 1st run calls everything
        # check two instances do not interfere
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            res1 = foo1.c()
            res2 = foo2.c()
        output = [map_short_to_long_key(msg) for msg in cm.output]
        output = [map_id_to_name(msg) for msg in output]
        expected = [
            f"DEBUG:calcengine.base:['{PATH}.Foo.c', 'INS_foo1'] called requiring: ['{PATH}.Foo.a', 'INS_foo1'], ['{PATH}.Foo.b', 'INS_foo1', 5]",
            f"DEBUG:calcengine.base:['{PATH}.Foo.a', 'INS_foo1'] called requiring: ",
            f"DEBUG:calcengine.base:['{PATH}.Foo.b', 'INS_foo1', 5] called requiring: ['{PATH}.Foo.a', 'INS_foo1']",
            f"DEBUG:calcengine.base:['{PATH}.Foo.c', 'INS_foo2'] called requiring: ['{PATH}.Foo.a', 'INS_foo2'], ['{PATH}.Foo.b', 'INS_foo2', 5]",
            f"DEBUG:calcengine.base:['{PATH}.Foo.a', 'INS_foo2'] called requiring: ",
            f"DEBUG:calcengine.base:['{PATH}.Foo.b', 'INS_foo2', 5] called requiring: ['{PATH}.Foo.a', 'INS_foo2']",
        ]
        self.assertListEqual(output, expected)
        self.assertEqual(res1, res2)

        # 2nd run doesn't call anything
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            # use dummmy log https://bugs.python.org/issue39385
            logging.getLogger("calcengine.base").debug("DUMMY")
            res3 = foo1.c()
        expected = ["DEBUG:calcengine.base:DUMMY"]
        self.assertListEqual(cm.output, expected)
        self.assertEqual(res1, res3)

        # invalidate node recalls invalidated path
        with self.assertLogs("calcengine.base", "DEBUG") as cm:
            Foo.b.invalidate(foo1, 5)
            res4 = foo1.c()
        output = [map_short_to_long_key(msg) for msg in cm.output]
        output = [map_id_to_name(msg) for msg in output]
        expected = [
            "DEBUG:calcengine.base:['test..Foo.c', 'INS_foo1'] called requiring: ['test..Foo.a', 'INS_foo1'], ['test..Foo.b', 'INS_foo1', 5]",
            "DEBUG:calcengine.base:['test..Foo.b', 'INS_foo1', 5] called requiring: ['test..Foo.a', 'INS_foo1']",
        ]
        self.assertListEqual(output, expected)
        self.assertEqual(res1, res4)

    def test_set_value_and_invalidate(self):
        # simple smoke test for now
        res1 = f()  # d(0) + c(2, 3) -5 + d(5, y=-3)
        self.assertEqual(res1, 809)
        c.set_value_and_invalidate(5, 2, 3)
        res2 = f()  # d(0) + 5 -5 + d(5, y=-3)
        self.assertEqual(res2, 608)

    @unittest.skip("TODO")
    def test_lambda(self):
        g()


if __name__ == "__main__":
    unittest.main()

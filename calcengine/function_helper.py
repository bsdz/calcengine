import sys
import struct
from functools import _make_key  # type: ignore
from dis import get_instructions
from typing import Optional, Hashable, Callable, Dict, Any, Tuple

from .utility import deep_getattr, deep_hasattr


def hash_unsigned_hex(key: Hashable):
    """For converting make_id_pair into simple string. We use
    native integer for packing/unpacking, the same is used
    by python hash() function.
    """
    return hex(struct.unpack("N", struct.pack("n", hash(key)))[0])


def find_calls(func, this=None):
    """Searches code object for names within function block that
    have been helper attribute (on graph); then process disassembled
    code to discover arguments to these functions. This should be
    enough data to form a unique node.

    Optional parameter this is reference to self. Normally func.__self__.

    TODO: this routine is a shallow implementation. it should unroll
    loops, comprehensions, etc; perhaps consider conditional branches.
    Potentially use a decompiler such as python-decompile3.
    """
    objs = func.__globals__
    ins = get_instructions(func.__code__)
    found = []
    while True:
        try:
            oc = next(ins)
            if (
                oc.opname in ("LOAD_GLOBAL", "LOAD_ATTR")
                and oc.argval in objs
                and hasattr(objs[oc.argval], "helper")
            ):
                fn, args_ = objs[oc.argval], []
                while True:
                    oc = next(ins)
                    if oc.opname == "LOAD_CONST":
                        args_.append(oc.argval)

                    if oc.opname == "CALL_FUNCTION":
                        found.append((fn, tuple(args_), {}))
                        break

                    elif oc.opname == "CALL_FUNCTION_KW":
                        kw_names = args_.pop()
                        kwds_ = {n: args_.pop() for n in kw_names}
                        found.append((fn, tuple(args_), kwds_))
                        break

            if oc.opname in ["LOAD_METHOD", "LOAD_ATTR"] and deep_hasattr(
                this, [oc.argval, "helper"]
            ):
                # NOTE: we fetch the methods unbound function
                fn, args_ = deep_getattr(this, [oc.argval, "__func__"]), []
                while True:
                    oc = next(ins)
                    if oc.opname == "LOAD_CONST":
                        args_.append(oc.argval)

                    if oc.opname == "CALL_METHOD":
                        found.append((fn, tuple(args_), {}))
                        break

                    elif oc.opname == "CALL_FUNCTION_KW":
                        kw_names = args_.pop()
                        kwds_ = {n: args_.pop() for n in kw_names}
                        found.append((fn, tuple(args_), kwds_))
                        break

        except StopIteration:
            break

    return found


class FunctionHelper:
    """Encapsulate useful methods around functions"""

    def __init__(
        self,
        func: Callable,
        typed_key: bool = True,
        alias: Optional[str] = None,
        path: Optional[str] = None,
    ):
        self.func = func
        self.typed = typed_key

        # overrides for fully qualified names.
        # can be used to name lambdas.
        self.alias = alias
        self.path = path

    def fqn(self):
        """Fully qualified name of function. The module and base names
        are overridable using members alias and path. We use filename
        as more reliable than just __module__.
        """
        if self.path:
            module_path = self.path
        else:
            fp = self.func.__code__.co_filename
            matching = max([p for p in sys.path if p in fp], key=len)
            module_path = (
                fp.replace(matching + "/", "").replace(".py", "").replace("/", ".")
            )
        func_name = self.alias or self.func.__qualname__
        return ".".join([module_path, func_name])

    def make_node_id_pair(self, args: Tuple[Any, ...], kwds: Dict[Any, Any]):
        """Wraps functools private _make_key method. Inserts additional
        fully qualified function name (aka graph path) as 1st argument.
        Return a short and long variant of id. The short version can be
        considered as a unique node id.

        Since a method call cannot easily be detected until it is called
        from a class instance we simply check if the first argument is
        `self` and convert that argument to unique string id.

        TODO: add class parameter to allow override `self` word check,
        eg is_method=True|False or type=Enum(guess,function,instancemeth,..)

        TODO: replace fqn based on module path and function name with one
        also including context, ie context / module / name.
        """
        vn = self.func.__code__.co_varnames
        if vn and vn[0] == "self":
            args = (hex(id(args[0])),) + args[1:]

        # choose a more presentable keyword mark for _make_key
        long_id = _make_key(
            (self.fqn(),) + args, kwds, self.typed, kwd_mark=("___KWDS___",)
        )
        short_id = hash_unsigned_hex(long_id)
        return short_id, long_id

    def get_required_node_ids(self, this):
        found = find_calls(self.func, this)
        this_pos_arg = (this,) if this else tuple()
        return {
            f.helper.make_node_id_pair(this_pos_arg + args_, kwds_)[0] for f, args_, kwds_ in found
        }

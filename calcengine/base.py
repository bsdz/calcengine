from functools import wraps, partial
from collections import defaultdict
from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from .function_helper import FunctionHelper
from .event import Event
from .utility import deep_getattr

logger = logging.getLogger(__name__)


@dataclass
class NodeData:
    """Store child nodes and cached values.
    """

    requires: set = field(default_factory=set)
    value = None


class NodeCalculatedEvent(Event):
    """Called after node function completes.
    """

    pass


class NodeValueSetEvent(Event):
    """Called after node value has been set.
    """

    pass


class CalcEngine:
    """Simple lazy calculation engine.

    The calc engine cache can be viewed as
    a directed graph with each unique function
    call along with it's arguments considered
    a graph node.

    A unique node id is generated for each node
    using the function module, name and arguments.
    """

    def __init__(self):
        self.cache = defaultdict(NodeData)

        # stores mapping from long functool type ids to
        # shorter hex variant.
        self.id_map = {}

    def clear_cache(self):
        """Clears all cached node data.
        """
        self.cache.clear()
        self.id_map.clear()

    def required_by(self, id_):
        """Finds all nodes required by this node.
        """
        all_ids = set()
        if id_ in self.cache:
            ids = set([id_])
            while ids:
                new_ids = set()
                for node_id, node_data in self.cache.items():
                    if ids & node_data.requires:
                        new_ids.add(node_id)
                ids = new_ids
                all_ids.update(new_ids)
        return all_ids

    def invalidate(self, fh: FunctionHelper, *args: Any, **kwds: Any):
        """Invalidate a node.

        Removes all data for this node and for all
        nodes that require it.
        """
        sid, _ = fh.make_node_id_pair(args, kwds)
        # find all nodes required by current node
        all_ids = self.required_by(sid)
        # also clear this node from cache
        all_ids.add(sid)
        for id_ in all_ids:
            self.cache.pop(id_, None)

    def set_value(
        self,
        fh: FunctionHelper,
        node_value_set_event: NodeValueSetEvent,
        new_val: Any,
        *args: Any,
        **kwds: Any
    ):
        """Set value for a node.

        Does not automatically invalidate nodes required by this node.
        """
        sid, _ = fh.make_node_id_pair(args, kwds)  # type: ignore
        self.cache[sid].value = new_val
        node_value_set_event(new_val)

    def set_value_and_invalidate(
        self,
        fh: FunctionHelper,
        node_value_set_event: NodeValueSetEvent,
        new_val: Any,
        *args: Any,
        **kwds: Any
    ):
        """Set value for a node.

        Invalidate nodes required by this node.
        """
        sid, _ = fh.make_node_id_pair(args, kwds)  # type: ignore
        self.cache[sid].value = new_val
        # find all nodes required by current node
        all_ids = self.required_by(sid)
        for id_ in all_ids:
            self.cache.pop(id_, None)
        # TODO: perhaps have different event here?
        node_value_set_event(new_val)

    def watch(
        self,
        typed: bool = False,
        alias: Optional[str] = None,
        path: Optional[str] = None,
    ):
        """Decorator to indicate function is on graph.

        Args:
            typed (bool, optional): Whether to record argument types when
                when generating keys. Defaults to False.
            alias (Optional[str], optional): Alternative name for function
                in cache. Defaults to None to use existing name.
            path (Optional[str], optional): Alternative module path for
                function in cache. Defaults to None to use existing path.
        """

        def _watch(f):

            fh = FunctionHelper(f, typed_key=typed, alias=alias, path=path)

            # stores callbacks that can be subscribed to
            node_calculated_event = NodeCalculatedEvent()
            node_value_set_event = NodeValueSetEvent()

            @wraps(f)
            def wrapper(*args: Any, **kwds: Any):
                nonlocal fh
                sid, lid = fh.make_node_id_pair(args, kwds)
                self.id_map[sid] = lid

                if sid in self.cache:
                    return self.cache[sid].value

                # determine if method call (by checking if method call exists
                # in 1st arg that is potentially an instance, then to see if
                # that methods unbound function is a wrapper around the same
                # function - appears to work!).
                this = None
                if args:
                    method_func_wrapped = deep_getattr(
                        args[0], [f.__name__, "__func__", "__wrapped__"], default=None
                    )
                    if method_func_wrapped == f:
                        this = args[0]

                self.cache[sid].requires = fh.get_required_node_ids(this)

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "%s called requiring: %s",
                        sid,
                        ", ".join(self.cache[sid].requires),
                    )
                result = f(*args, **kwds)
                self.cache[sid].value = result
                node_calculated_event(result)
                return result

            # core utility and used to detect
            # if node on graph
            wrapper.helper = fh

            # events
            wrapper.node_calculated = node_calculated_event
            wrapper.node_value_set = node_value_set_event

            # graph functions
            wrapper.invalidate = partial(self.invalidate, fh)
            wrapper.set_value = partial(self.set_value, fh, node_value_set_event)
            wrapper.set_value_and_invalidate = partial(
                self.set_value_and_invalidate, fh, node_value_set_event
            )

            return wrapper

        return _watch

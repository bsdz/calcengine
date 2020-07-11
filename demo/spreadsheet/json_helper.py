import json
from base64 import b64encode, b64decode
from io import BytesIO
import datetime
import decimal


def full_class_name(obj):
    if isinstance(obj, type):
        return obj.__module__ + "." + obj.__name__
    else:
        return full_class_name(obj.__class__)


SIMPLE_TYPE_ATTRIBUTES = {
    # fmt: off
    datetime.datetime: ('year', 'month', 'day', 'hour', 'minute', 'second', 'microsecond'),
    datetime.date: ('year', 'month', 'day'),
    datetime.time: ('hour', 'minute', 'second', 'microsecond'),
    datetime.timedelta: ('days', 'seconds', 'microseconds'),
    # fmt: on
}

SIMPLE_NAMES = {full_class_name(t): t for t in SIMPLE_TYPE_ATTRIBUTES}


class InvalidCellDuringCopyException(Exception):
    pass


class InvalidCell:
    """Leverage python's deepcopy to detect cells
    requiring invalidation within deep structures.
    """
    def __deepcopy__(self, memo):
        raise InvalidCellDuringCopyException()


INVALID_CELL_FCN = full_class_name(InvalidCell)


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        # use string type to avoid unneccesary imports for
        # modules that might not be installed.
        fcn = full_class_name(obj)
        if fcn == "pandas.core.frame.DataFrame":
            return {
                "_type": fcn,
                "value": obj.to_json(),
            }
        elif fcn == "pandas.core.series.Series":
            return {
                "_type": fcn,
                "value": obj.to_json(),
            }
        elif fcn == "numpy.ndarray":
            return {
                "_type": fcn,
                "value": obj.tolist(),
            }
        elif fcn == "PIL.Image.Image":
            buffer = BytesIO()
            obj.save(buffer, format="PNG")
            return {
                "_type": fcn,
                "value": b64encode(buffer.getvalue()).decode("ascii"),
            }
        elif isinstance(obj, decimal.Decimal):
            return {
                "_type": fcn,
                "value": str(obj),
            }

        elif type(obj) in SIMPLE_TYPE_ATTRIBUTES:
            return {
                "_type": fcn,
                "value": [getattr(obj, a) for a in SIMPLE_TYPE_ATTRIBUTES[type(obj)]],
            }

        # if we can't serialize then return None
        # and rely on re-calculating cell later.
        try:
            return super().default(obj)
        except:  # noqa
            return {
                "_type": INVALID_CELL_FCN,
                "value": "",
            }


class JSONDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook, *args, **kwargs)

    def object_hook(self, obj):
        if "_type" not in obj:
            return obj

        if obj["_type"] == "pandas.core.frame.DataFrame":
            import pandas as pd

            return pd.read_json(obj["value"])
        elif obj["_type"] == "pandas.core.series.Series":
            import pandas as pd

            return pd.read_json(obj["value"], typ="series")
        elif obj["_type"] == "numpy.ndarray":
            import numpy as np

            return np.asarray(obj["value"])
        elif obj["_type"] == "PIL.Image.Image":
            import PIL.Image

            return PIL.Image.open(BytesIO(b64decode(obj["value"].encode())))
        elif obj["_type"] == "decimal.Decimal":
            return decimal.Decimal(obj["value"])

        elif obj["_type"] in SIMPLE_NAMES:
            return SIMPLE_NAMES[obj["_type"]](*obj["value"])

        elif obj["_type"] == INVALID_CELL_FCN:
            return InvalidCell()

        return obj

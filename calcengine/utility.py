def deep_getattr(obj, attrs, **kwds):
    try:
        for attr in attrs:
            obj = getattr(obj, attr)
        return obj
    except AttributeError:
        if "default" in kwds:
            return kwds["default"]
        else:
            raise


def deep_hasattr(obj, attrs):
    try:
        deep_getattr(obj, attrs)
        return True
    except AttributeError:
        return False

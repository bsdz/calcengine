# calcengine
A simple lazy Python Calculation Engine.


## Installation

The module is still in development. You can install it by cloning this repository and using the [poetry install](https://python-poetry.org/docs/cli/#install) command.

```bash
git clone git@github.com:bsdz/calcengine.git
cd calcengine
python3 -mvenv --prompt calceng .venv
. ./.venv/bin/activate
poetry install
```

Alternatively, you can add to your existing poetry project:

```bash
poetry add git+https://github.com/bsdz/calcengine.git
```

Or install via pip:

```bash
pip install git+https://github.com/bsdz/calcengine.git#master
```

## Core Dependencies

The core module for the calculation engine only uses core python standard library.

The demo spreadsheet application uses pyqt5, pandas, matplotlib and pillow.

## Usage

First instantiate a CalcEngine and use `watch` decorator
to register functions as nodes. Note that a function along
with any arguments and keyword arguments make a unique node.

```python
from calcengine import CalcEngine

ce = CalcEngine()

@ce.watch()
def a():
    print("..in a")
    return 100

@ce.watch()
def b():
    print("..in b")
    return a() 

@ce.watch()
def c(x, y):
    print(f"..in c with x={x} and y={y}")
    return 2 * a() + x * y

@ce.watch()
def d(x, y=0):
    print(f"..in d with x={x} and y={y}")
    return 3 * b() + x - y

@ce.watch()
def e():
    print("..in e")
    _x = d(5, y=-3)
    return c(2, 3) - 5 + _x

@ce.watch()
def f():
    print("..in f")
    return d(0) + e()
```

Calling a function will cache all values and path
during first run.

```python
>>> f()
..in f
..in d with x=0 and y=0
..in b
..in a
..in e
..in d with x=5 and y=-3
..in c with x=2 and y=3
809
```

And obviously a 2nd invocation will retrieve the final
value from cache.

```python
>>> f()
809
```

Invalidating a node by calling function helper method.

```python
>>> e.invalidate()
>>> f()
..in f
..in e
809
```

Invalidating a node without arguments if previous call did 
have arguments won't have any effect.

```python
>>> d.invalidate()
>>> f()
809
```

Whereas with arguments specified exactly as prior call will. Note
the sensitivity of argument specification.

```python
>>> d.invalidate(5, y=-3)
>>> f()
..in f
..in e
..in d with x=5 and y=-3
809
```

It is also possible to add a trigger that will be called on completion
of a function. This might be used to produce some form of data binding
in applications.

```python
def my_trigger(res):
    print(f"got {res}")

>>> c.node_calculated.append(my_trigger)
>>> c.invalidate(2, 3)
>>> f()
call f
call e
call c with x=2 and y=3
got 206
809
```

## Demo application

Included is a simple spreadsheet demo. Read more [here](./demo/spreadsheet/README.md)

![Demo animation](./demo/spreadsheet/demo.gif)

## To do

* Support watching global variables.
* Support multiprocessing.
* Support asyncio?.

## similar packages

Some similar packages spotted. None of them tested.

* [pyungo](https://github.com/cedricleroy/pyungo)
* [dask](https://docs.dask.org/en/latest/delayed.html)
* [schedula](https://pypi.org/project/schedula/)
* [graphkit](https://pythonhosted.org/graphkit/index.html)
* [mdf](https://github.com/man-group/mdf)

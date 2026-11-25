import json
import numpy as np
import pandas as pd
import xarray as xr
from xarray.core.variable import as_compatible_data


class PublicScalarObject:
    values = 5


class PublicVectorAttribute:
    values = np.array([3, 7])


class PublicPropertyObject:
    @property
    def values(self):
        raise AssertionError("Arbitrary objects must not have their values property evaluated")


def assignment(value, route):
    if route == "variable":
        result = xr.Variable(("sample",), np.array([None], dtype=object))
        result[0] = value
    else:
        result = xr.DataArray(np.array([None], dtype=object), dims=("sample",))
        if route == "direct":
            result[0] = value
        else:
            result.loc[{"sample": 0}] = value
    return result.values[0] is value


rows = []


def check(name, operation):
    try:
        passed = bool(operation())
        rows.append({"name": name, "passed": passed})
    except Exception as error:
        rows.append({"name": name, "passed": False, "error_type": type(error).__name__, "error": str(error)})


for object_type in (PublicScalarObject, PublicVectorAttribute, PublicPropertyObject):
    value = object_type()
    for route, operation in (
            ("compatible", lambda value=value: as_compatible_data(value)),
            ("variable_constructor", lambda value=value: xr.Variable((), value).values),
            ("dataarray_constructor", lambda value=value: xr.DataArray(value).values)):
        def preserved(operation=operation, value=value):
            result = operation()
            return result.shape == () and result.dtype == object and result.item() is value
        check(object_type.__name__ + ":" + route, preserved)
    for route in ("variable", "direct", "loc"):
        check(object_type.__name__ + ":assignment:" + route,
            lambda value=value, route=route: assignment(value, route))

known = (
    ("numpy", np.array([2, 4]), np.array([2, 4])),
    ("variable", xr.Variable(("sample",), [2, 4]), np.array([2, 4])),
    ("dataarray", xr.DataArray([2, 4], dims=("sample",)), np.array([2, 4])),
    ("series", pd.Series([2, 4]), np.array([2, 4])),
    ("dataframe", pd.DataFrame({"a": [2, 4]}), np.array([[2], [4]])),
    ("index", pd.Index([2, 4]), np.array([2, 4])),
    ("list", [2, 4], np.array([2, 4])),
    ("scalar", 2, np.array(2)),
)
for name, value, expected in known:
    check("known_container:" + name, lambda value=value, expected=expected:
        np.array_equal(np.asarray(as_compatible_data(value)), expected))

passed = all(row["passed"] for row in rows)
print(json.dumps({"passed": passed, "cases": rows, "total": len(rows),
    "scope": "Public task-derived arbitrary objects, constructor and assignment paths, and existing named container conversions. No hidden grader fixtures or expected patch."}))
raise SystemExit(0 if passed else 1)

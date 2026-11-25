import os

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import json
import warnings

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer


rows = []
source = np.array([[1.0, 2.0], [np.nan, 4.0], [5.0, np.nan], [7.0, 8.0]])


def check(name, operation):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            details = operation()
            row = {"name": name, "passed": True, **details}
        except Exception as error:
            row = {"name": name, "passed": False, "error_type": type(error).__name__, "error": str(error)}
    row["warnings"] = sorted({item.category.__name__ for item in caught})
    rows.append(row)


def expected_observed(actual, original, missing):
    assert actual.shape == original.shape, (actual.shape, original.shape)
    np.testing.assert_allclose(actual[~missing], original[~missing], rtol=0, atol=0)


def default_mean():
    imputer = IterativeImputer(max_iter=2, random_state=0)
    actual = imputer.fit_transform(source.copy())
    expected_observed(actual, source, np.isnan(source))
    assert np.isfinite(actual).all(), actual.tolist()
    return {"shape": list(actual.shape), "n_iter": int(imputer.n_iter_)}


def constant_initial(value):
    imputer = IterativeImputer(initial_strategy="constant", fill_value=value, max_iter=0, random_state=0)
    copied = clone(imputer)
    parameter = copied.get_params()["fill_value"]
    if value is None:
        assert parameter is None
        expected = 0.0
    else:
        assert parameter == value
        expected = value
    actual = copied.fit_transform(source.copy())
    missing = np.isnan(source)
    expected_observed(actual, source, missing)
    np.testing.assert_allclose(actual[missing], expected, rtol=0, atol=0)
    return {"shape": list(actual.shape), "n_iter": int(copied.n_iter_)}


def nan_initial():
    imputer = IterativeImputer(initial_strategy="constant", fill_value=np.nan, max_iter=0)
    copied = clone(imputer)
    assert np.isnan(copied.get_params()["fill_value"])
    actual = copied.fit_transform(source.copy())
    missing = np.isnan(source)
    expected_observed(actual, source, missing)
    np.testing.assert_array_equal(np.isnan(actual), missing)
    return {"shape": list(actual.shape), "n_iter": int(copied.n_iter_)}


def tree_imputer(missing, keep):
    return IterativeImputer(estimator=HistGradientBoostingRegressor(max_iter=5, random_state=0),
        missing_values=missing, initial_strategy="constant", fill_value=np.nan,
        keep_empty_features=keep, max_iter=1, random_state=0)


def assert_tree_predictions(actual, mask):
    # 三个目标观察值小于默认min_samples_leaf20，平方损失单叶预测是目标均值。
    np.testing.assert_allclose(actual[mask], np.nanmean(source, axis=0), rtol=1e-10, atol=1e-10)


def assert_transform_predictions(actual, training):
    np.testing.assert_allclose(actual[:, 0], training[:, 0].mean(), rtol=1e-10, atol=1e-10)


def tree_fit(missing, keep):
    data = source.copy()
    mask = np.isnan(data)
    if not np.isnan(missing):
        data[mask] = missing
    imputer = tree_imputer(missing, keep)
    actual = imputer.fit_transform(data)
    expected_observed(actual, data, mask)
    assert imputer.n_iter_ == 1, int(imputer.n_iter_)
    assert np.isfinite(actual).all(), actual.tolist()
    assert_tree_predictions(actual, mask)
    return {"shape": list(actual.shape), "n_iter": int(imputer.n_iter_),
        "imputed_values": actual[mask].tolist()}


def fitted_feature_range(keep):
    training = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    following = np.array([[-1.0, 3.0], [-1.0, 5.0], [-1.0, 7.0], [-1.0, 9.0]])
    imputer = tree_imputer(-1.0, keep)
    imputer.fit(training)
    actual = imputer.transform(following)
    expected_observed(actual, following, following == -1)
    assert np.isfinite(actual).all(), actual.tolist()
    assert_transform_predictions(actual, training)
    return {"shape": list(actual.shape), "n_iter": int(imputer.n_iter_),
        "transformed_missing_column": actual[:, 0].tolist()}


def other_strategy():
    imputer = IterativeImputer(initial_strategy="mean", fill_value=-99.0, max_iter=0)
    actual = imputer.fit_transform(source.copy())
    missing = np.isnan(source)
    expected_observed(actual, source, missing)
    np.testing.assert_allclose(actual[missing], np.array([13 / 3, 14 / 3]), rtol=1e-12)
    return {"shape": list(actual.shape), "n_iter": int(imputer.n_iter_)}


check("existing_mean_strategy", default_mean)
for value in (None, 10.0, -3.0):
    check("constant_initial:" + str(value), lambda value=value: constant_initial(value))
check("nan_initial_without_iteration", nan_initial)
for missing in (np.nan, -1.0):
    for keep in (False, True):
        check("tree_nan_fit:" + str(missing) + ":keep=" + str(keep),
            lambda missing=missing, keep=keep: tree_fit(missing, keep))
for keep in (False, True):
    check("fitted_feature_range:keep=" + str(keep), lambda keep=keep: fitted_feature_range(keep))
check("fill_value_ignored_for_mean", other_strategy)

passed = all(row["passed"] for row in rows)
print(json.dumps({"passed": passed, "total": len(rows), "cases": rows,
    "scope": "Public task-derived fill_value, NaN-tolerant tree iteration and fitted transform feature range. Each training feature has observations;no hidden grader inputs, gold patch or model candidate reference."}))
raise SystemExit(0 if passed else 1)

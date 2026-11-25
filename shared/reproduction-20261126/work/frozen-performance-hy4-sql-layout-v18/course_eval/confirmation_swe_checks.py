import importlib
import json
import sys


def django_setup():
    import django
    from django.conf import settings
    settings.configure(SECRET_KEY="public-reproducer-only", INSTALLED_APPS=[
        "django.contrib.contenttypes", "django.contrib.auth", "django.contrib.admin"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}],
        ROOT_URLCONF=__name__, USE_I18N=False)
    django.setup()


def check(task):
    if task.startswith("django__"):
        django_setup()
        from django import forms
        from django.db import models
        if task == "django__django-11999":
            class FooBar(models.Model):
                foo_bar = models.CharField(max_length=20, choices=[("1", "foo"), ("2", "bar")])

                class Meta:
                    app_label = "course"

                def get_foo_bar_display(self):
                    return "something"

            values = [FooBar(foo_bar=value).get_foo_bar_display() for value in ("1", "2")]
            return values == ["something", "something"], {"display": values}, "overridden display method retained"
        if task == "django__django-12193":
            from django.contrib.postgres.forms import SplitArrayField
            field = SplitArrayField(forms.BooleanField(required=False), size=4)
            expected = [True, False, True, False]
            widgets = field.widget.get_context("flags", expected, {})["widget"]["subwidgets"]
            actual = [bool(widget["attrs"].get("checked", False)) for widget in widgets]
            direct = []
            for value in (True, False):
                for supplied in (None, {"id": "public-checkbox", "data-origin": "caller"}):
                    attrs = None if supplied is None else dict(supplied)
                    before = None if attrs is None else dict(attrs)
                    context = forms.CheckboxInput().get_context("flag", value, attrs)
                    direct.append({"value": value, "attrs_kind": "none" if attrs is None else "dictionary",
                        "caller_attrs_unchanged": attrs == before,
                        "checked": bool(context["widget"]["attrs"].get("checked", False))})
            preserved = all(row["caller_attrs_unchanged"] for row in direct)
            direct_correct = all(row["checked"] == row["value"] for row in direct)
            return actual == expected and preserved and direct_correct, {
                "checked": actual, "direct_checkbox_cases": direct,
            }, {"checked": expected, "caller_attrs_unchanged": True, "direct_checked_matches_boolean": True}
        if task == "django__django-14855":
            from django.contrib import admin
            from django.contrib.admin.helpers import AdminReadonlyField
            from django.urls import path

            class Author(models.Model):
                name = models.CharField(max_length=30)

                class Meta:
                    app_label = "course"

            class Book(models.Model):
                author = models.ForeignKey(Author, on_delete=models.CASCADE)

                class Meta:
                    app_label = "course"

            default = admin.AdminSite(name="admin")
            custom = admin.AdminSite(name="custom-admin")
            default.register(Author)
            custom.register(Author)
            globals()["urlpatterns"] = [path("admin/", default.urls), path("custom-admin/", custom.urls)]
            form = forms.modelform_factory(Book, fields=("author",))()
            readonly = AdminReadonlyField(form, "author", is_first=False, model_admin=admin.ModelAdmin(Book, custom))
            value = str(readonly.get_admin_url(Book._meta.get_field("author").remote_field, Author(pk=1)))
            from html.parser import HTMLParser

            class Links(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.links = []

                def handle_starttag(self, tag, attrs):
                    if tag == "a":
                        self.links.append(dict(attrs).get("href"))

            parsed = Links()
            parsed.feed(value)
            return parsed.links == ["/custom-admin/course/author/1/change/"], {"links": parsed.links}, "custom AdminSite URL"
    if task.startswith("scikit-learn__"):
        import numpy as np
        if task == "scikit-learn__scikit-learn-11310":
            from sklearn.model_selection import GridSearchCV
            from sklearn.tree import DecisionTreeClassifier
            from sklearn.datasets import load_iris
            x, y = load_iris(return_X_y=True)
            search = GridSearchCV(DecisionTreeClassifier(random_state=0), {"max_depth": [1, 2]}, cv=3).fit(x, y)
            value = getattr(search, "refit_time_", None)
            return isinstance(value, float) and value >= 0, {"refit_time_": value}, "nonnegative measured refit duration"
        if task == "scikit-learn__scikit-learn-13124":
            from sklearn.model_selection import StratifiedKFold
            x = np.arange(20)
            y = np.concatenate([np.ones(10), np.zeros(10)])
            folds = [sorted(tuple(sorted(test)) for _, test in StratifiedKFold(
                n_splits=10, shuffle=True, random_state=seed).split(x, y)) for seed in (1, 2)]
            balanced = all(len(test) == 2 and sum(y[list(test)]) == 1 for group in folds for test in group)
            return folds[0] != folds[1] and balanced, {"folds": folds}, "different stratified sample partitions across seeds"
        if task == "scikit-learn__scikit-learn-25232":
            from sklearn.experimental import enable_iterative_imputer
            from sklearn.impute import IterativeImputer
            output = IterativeImputer(initial_strategy="constant", fill_value=7, max_iter=0).fit_transform(
                np.array([[1., np.nan], [np.nan, 2.], [3., 4.]]))
            expected = np.array([[1., 7.], [7., 2.], [3., 4.]])
            return bool(np.array_equal(output, expected)), {"initial_output": output.tolist()}, expected.tolist()
    if task.startswith("pydata__"):
        import numpy as np
        import xarray as xr
        if task == "pydata__xarray-4687":
            data = xr.DataArray(np.array([0, 1]), attrs={"foo": "bar"})
            result = xr.where(data == 0, data, -1, keep_attrs=True)
            cond = xr.DataArray([True, False], dims="sample", attrs={"source": "predicate"})
            x = xr.DataArray([4, 8], dims="sample", attrs={"source": "selected"})
            y = xr.DataArray([12, 16], dims="sample", attrs={"source": "alternative"})
            before = [dict(value.attrs) for value in (cond, x, y)]
            choices = []
            for global_keep in (False, True):
                with xr.set_options(keep_attrs=global_keep):
                    for explicit in (None, False, True):
                        chosen = xr.where(cond, x, y, keep_attrs=explicit)
                        expected_attrs = x.attrs if (global_keep if explicit is None else explicit) else {}
                        choices.append({"global_keep_attrs": global_keep, "explicit_keep_attrs": explicit,
                            "attrs": dict(chosen.attrs), "expected_attrs": dict(expected_attrs),
                            "passed": chosen.attrs == expected_attrs and bool(np.array_equal(chosen.values, [4, 16]))})
            with xr.set_options(keep_attrs=True):
                method = x.where(cond, other=y)
                function = xr.where(cond, x, y, keep_attrs=True)
            public_cond_only = xr.where(cond, 5, 0)
            public_y = xr.where(data == 0, -1, data)
            unchanged = before == [value.attrs for value in (cond, x, y)]
            equal_values = bool(np.array_equal(method.values, function.values))
            consistent = equal_values and method.attrs == function.attrs and unchanged
            public_forms = bool(np.array_equal(public_cond_only.values, [5, 0])
                                and np.array_equal(public_y.values, [-1, 1]))
            return result.attrs == data.attrs and consistent and public_forms and all(row["passed"] for row in choices), {
                "attrs": result.attrs, "method_attrs": method.attrs, "function_attrs": function.attrs,
                "values_equal": equal_values, "input_attrs_unchanged": unchanged,
                "attribute_choices": choices, "public_cond_only_and_y_values": public_forms,
            }, {"attrs": data.attrs, "attribute_choice": "explicit Boolean overrides global option; None follows it",
                "equivalent_public_methods": "same values and attributes; inputs preserved",
                "scalar_attribute_precedence": "not asserted"}
        if task == "pydata__xarray-6599":
            values = np.array(["2021-04-01T05:25:19", "2021-04-01T05:25:29", "2021-04-01T05:25:39",
                               "2021-04-01T05:25:49", "2021-04-01T05:25:59", "2021-04-01T05:26:09"],
                              dtype="datetime64[ns]")
            coordinate = xr.DataArray(values, name="azimuth_time", coords={"azimuth_time": values - values[0]})
            coefficients = np.array([[2.33333335e-43, 1.62499999e-43, 2.79166678e-43],
                [-1.15316667e-30, 1.49518518e-31, 9.08833333e-31],
                [-2.50272583e-18, -1.23851062e-18, -2.99098229e-18],
                [5.83965193e-06, -1.53321770e-07, -4.84640242e-06],
                [4.44739216e06, 1.45053974e06, 5.29960857e06]])
            coeffs = xr.DataArray(coefficients, dims=("degree", "axis"),
                                 coords={"degree": [4, 3, 2, 1, 0], "axis": [0, 1, 2]})
            original_call = xr.polyval(coordinate, coeffs).transpose("azimuth_time", "axis").values
            original_call_expected = np.stack([np.polyval(coefficients[:, index], values.astype("int64"))
                                               for index in range(3)], axis=1)
            actual = xr.polyval(coordinate["azimuth_time"], coeffs).transpose("azimuth_time", "axis").values
            elapsed_ns = (values - values[0]).astype("timedelta64[ns]").astype("int64")
            expected = np.stack([np.polyval(coefficients[:, index], elapsed_ns) for index in range(3)], axis=1)
            linear = xr.DataArray([3., 2.], dims="degree", coords={"degree": [1, 0]})
            durations = np.array([2, 5, 9], dtype="timedelta64[s]")
            duration_actual = xr.polyval(xr.DataArray(durations, dims="sample"), linear).values
            duration_expected = 3 * durations.astype("timedelta64[ns]").astype("int64") + 2
            dates = np.array(["2001-01-01", "2001-01-03"], dtype="datetime64[ns]")
            date_actual = xr.polyval(xr.DataArray(dates, dims="sample"), linear).values
            date_expected = 3 * dates.astype("int64") + 2
            matches = {"explicit_timedelta_coordinate": bool(np.allclose(actual, expected, rtol=1e-12, atol=1e-6)),
                "original_call_uses_data_values": bool(np.allclose(original_call, original_call_expected, rtol=1e-12, atol=1e-6)),
                "nonzero_duration": bool(np.allclose(duration_actual, duration_expected, rtol=1e-12, atol=1e-6)),
                "datetime_epoch_preserved": bool(np.allclose(date_actual, date_expected, rtol=1e-12, atol=1e-6))}
            return all(matches.values()), {"matches": matches, "explicit_timedelta_coordinate": actual.tolist(),
                "original_call": original_call.tolist(), "original_call_expected": original_call_expected.tolist(),
                "duration_actual": duration_actual.tolist(), "duration_expected": duration_expected.tolist(),
                "date_actual": date_actual.tolist(), "date_expected": date_expected.tolist()}, {
                "explicit_timedelta_coordinate": expected.tolist(),
                "numeric_contract": "Evaluate the supplied data values, not their index; retain nonzero durations and datetime epoch in nanoseconds",
                "compatibility_source": "Xarray v2022.06.0 breaking changes: polyval now uses coord directly instead of its index coordinate"}
        if task == "pydata__xarray-7393":
            original = xr.Dataset(coords={"a": np.array([0], dtype="i4")})
            result = original.stack(b=("a",))["a"].values.dtype
            return result == original["a"].values.dtype, {"dtype": str(result)}, "int32"
    if task.startswith("pytest-dev__"):
        import pytest
        from pathlib import Path
        directory = Path(".course-public-check")
        directory.mkdir(exist_ok=True)
        if task == "pytest-dev__pytest-7490":
            text = "import pytest\ndef test_public_xfail(request):\n    request.node.add_marker(pytest.mark.xfail(reason='public issue'))\n    assert 0\n"
        elif task == "pytest-dev__pytest-5631":
            text = ("import numpy as np\nfrom unittest.mock import patch\n"
                    "@patch('os.getcwd', new=np.array([-5.5,3.0]))\n"
                    "def test_public_patch():\n    assert True\n")
        else:
            raise ValueError(task)
        path = directory / "test_public_issue.py"
        path.write_text(text)
        reports = []

        class Reports:
            def pytest_runtest_logreport(self, report):
                if report.when == "call" or report.failed:
                    reports.append({"outcome": report.outcome, "xfail": hasattr(report, "wasxfail")})

        code = int(pytest.main([str(path), "-q", "--confcutdir=" + str(directory)], plugins=[Reports()]))
        expected_xfail = task.endswith("7490")
        okay = code == 0 and len(reports) == 1 and (
            reports[0]["xfail"] if expected_xfail else reports[0]["outcome"] == "passed")
        return okay, {"pytest_exit": code, "reports": reports}, "public reproducer completes with expected outcome"
    raise ValueError("No task-visible reproducer for " + task)


def main():
    task = sys.argv[1]
    try:
        passed, actual, required = check(task)
    except (AssertionError, TypeError, ValueError, AttributeError) as exc:
        passed, actual, required = False, {"error": type(exc).__name__, "detail": str(exc)}, "public issue behavior"
    result = {"passed": passed, "conditions": [{"id": "public-issue", "passed": passed,
                                                "actual": actual, "required": required}]}
    print(json.dumps(result, ensure_ascii=False, default=str))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

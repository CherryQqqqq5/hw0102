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
            return actual == expected, {"checked": actual}, {"checked": expected}
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
            import inspect
            data = xr.DataArray(np.array([0, 1]), attrs={"foo": "bar"})
            kwargs = {"keep_attrs": True} if "keep_attrs" in inspect.signature(xr.where).parameters else {}
            result = xr.where(data == 0, data, -1, **kwargs)
            return result.attrs == data.attrs, {"attrs": result.attrs}, data.attrs
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

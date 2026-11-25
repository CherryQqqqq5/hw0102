import json
import sys

sys.path.insert(0, "/testbed")

import django
from django.conf import settings

settings.configure(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=[], SECRET_KEY="public-json-type-regression", USE_TZ=False,
)
django.setup()

from django.db import DatabaseError, InterfaceError, connection, models


class PublicJSONValue(models.Model):
    payload = models.JSONField()

    class Meta:
        app_label = "course_public_json_types"


values = [True, False, 7, -4, 2.5, "", "Campus", "O'Reilly-course", "null", "true", "[0]",
          [], [7, {"nested": False}], {}, {"nested": [1, None, False]}]
absent = "public-value-not-present-in-this-case"
results = []
with connection.schema_editor() as editor:
    editor.create_model(PublicJSONValue)

for index, value in enumerate(values):
    PublicJSONValue.objects.all().delete()
    PublicJSONValue.objects.create(id=1, payload={"sample": value})
    for label, rhs, expected in (("single", [value], [1]),
                                 ("mixed", [absent, value], [1]), ("negative", [absent], [])):
        record = {"case": index, "python_type": type(value).__name__, "value": value, "rhs_kind": label}
        try:
            actual = list(PublicJSONValue.objects.filter(payload__sample__in=rhs).values_list("id", flat=True))
            record.update(actual_ids=actual, expected_ids=expected, passed=actual == expected)
        except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
            record.update(passed=False, error_type=type(error).__name__, error=str(error))
        results.append(record)

for label, rhs in (("empty_rhs", []), ("expression_rhs", models.Subquery(
        PublicJSONValue.objects.values("payload__sample")))):
    try:
        actual = list(PublicJSONValue.objects.filter(payload__sample__in=rhs).values_list("id", flat=True))
        expected = [] if label == "empty_rhs" else [1]
        results.append({"case": label, "actual_ids": actual, "expected_ids": expected, "passed": actual == expected})
    except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
        results.append({"case": label, "passed": False, "error_type": type(error).__name__, "error": str(error)})

original_limit = connection.ops.max_in_list_size
try:
    connection.ops.max_in_list_size = lambda: 3
    rhs = [absent + "-a", absent + "-b", values[-1], absent + "-c", absent + "-d"]
    try:
        actual = list(PublicJSONValue.objects.filter(payload__sample__in=rhs).values_list("id", flat=True))
        results.append({"case": "controlled_split_path", "configured_test_limit": 3,
                        "actual_ids": actual, "expected_ids": [1], "passed": actual == [1]})
    except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
        results.append({"case": "controlled_split_path", "configured_test_limit": 3,
                        "passed": False, "error_type": type(error).__name__, "error": str(error)})
finally:
    connection.ops.max_in_list_size = original_limit

oracle = []
original_vendor = connection.vendor
marker = "O'Reilly-course-bound-value"
try:
    connection.vendor = "oracle"
    for value in (marker, [marker, False], {"nested": marker}):
        record = {"value": value, "validation_tier": "real_ORM_Oracle_SQL_branch_on_SQLite_wrapper"}
        try:
            query = PublicJSONValue.objects.filter(payload__sample__in=[value]).query
            sql, parameters = query.get_compiler(using="default").as_sql()
            bound = any(marker in str(parameter) for parameter in parameters)
            outside_sql = marker not in sql and marker.replace("'", "''") not in sql
            scalar_parameters = all(not isinstance(parameter, (dict, list)) for parameter in parameters)
            record.update(sql=sql, parameters=list(parameters), value_bound=bound,
                          value_absent_from_sql=outside_sql, scalar_parameters=scalar_parameters,
                          passed=bound and outside_sql and scalar_parameters)
        except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
            record.update(passed=False, error_type=type(error).__name__, error=str(error))
        oracle.append(record)
finally:
    connection.vendor = original_vendor

passed = all(record["passed"] for record in results + oracle)
print(json.dumps({"passed": passed, "django_version": django.get_version(),
    "sqlite_database_cases": results, "oracle_parameter_separation_cases": oracle,
    "sqlite_cases_total": len(results), "oracle_branch_cases_total": len(oracle),
    "live_oracle_queries": 0, "new_model_calls": 0,
    "coverage_limit": "Non-null JSON IN round trips, empty/expression RHS, and an actual SQLite query with a controlled IN-list limit3 to exercise splitting. Direct IN(None) and cross-type inequality are not asserted. Oracle validation is compilation and parameter separation only, not driver/server execution."},
    ensure_ascii=False))
raise SystemExit(0 if passed else 1)

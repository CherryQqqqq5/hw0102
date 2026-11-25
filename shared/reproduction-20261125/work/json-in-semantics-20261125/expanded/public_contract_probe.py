import json
import re
import sys

sys.path.insert(0, "/testbed")

import django
from django.conf import settings

settings.configure(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=[], SECRET_KEY="public-json-type-regression", USE_TZ=False,
)
django.setup()

from django.db import DatabaseError, InterfaceError, connection, connections, models


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

expressions = []
for value, row_id, cases in (
        (7, 7, [("value", [models.Value(7)]), ("mixed_value", [absent, models.Value(7)]),
                ("column", [models.F("id")]), ("mixed_column", [models.F("id"), absent])]),
        ("Campus", 9, [("value", [models.Value("Campus")]),
                        ("mixed_value", [absent, models.Value("Campus")])])):
    PublicJSONValue.objects.all().delete()
    PublicJSONValue.objects.create(id=row_id, payload={"sample": value})
    for label, rhs in cases:
        item = {"case": label, "value": value, "tier": "actual_SQLite_expression_list_query"}
        try:
            actual = list(PublicJSONValue.objects.filter(payload__sample__in=rhs).values_list("id", flat=True))
            item.update(passed=actual == [row_id], actual_ids=actual, expected_ids=[row_id])
        except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
            item.update(passed=False, error_type=type(error).__name__, error=str(error))
        expressions.append(item)

raw = connection.connection


def oracle_json_value(document, path):
    kind, value = raw.execute("SELECT json_type(?, ?), json_extract(?, ?)",
                              (document, path, document, path)).fetchone()
    return None if kind in (None, "null", "object", "array") else value


def oracle_json_query(document, path):
    kind, value = raw.execute("SELECT json_type(?, ?), json_extract(?, ?)",
                              (document, path, document, path)).fetchone()
    return value if kind in ("object", "array") else None


def mysql_json_unquote(value):
    return json.loads(value) if isinstance(value, str) and value.startswith('"') else value


raw.create_function("COURSE_JSON_VALUE", 2, oracle_json_value)
raw.create_function("COURSE_JSON_QUERY", 2, oracle_json_query)
raw.create_function("JSON_UNQUOTE", 1, mysql_json_unquote)
backend_strings = []
wrapper = connections["default"]
original_mariadb = wrapper.__dict__.get("mysql_is_mariadb")
had_mariadb = "mysql_is_mariadb" in wrapper.__dict__
try:
    wrapper.mysql_is_mariadb = False
    for vendor in ("mysql", "oracle"):
        for value in ("Campus", "O'Reilly-course-bound", "null", "true", ""):
            item = {"vendor": vendor, "value": value,
                    "tier": "compiled_singleton_RHS_string_decoding_on_SQLite_JSON1_adapter",
                    "controlled_mysql_is_mariadb": False}
            try:
                connection.vendor = vendor
                query = PublicJSONValue.objects.filter(payload__sample__in=[value]).query
                compiler = query.get_compiler(using="default")
                rhs_sql, rhs_parameters = query.where.children[0].process_rhs(compiler, connection)
                connection.vendor = original_vendor
                adapted = re.sub(r"\bJSON_VALUE\s*\(", "COURSE_JSON_VALUE(", rhs_sql, flags=re.I)
                adapted = re.sub(r"\bJSON_QUERY\s*\(", "COURSE_JSON_QUERY(", adapted, flags=re.I)
                adapted = re.sub(r"JSON_OBJECT\(\s*('(?:''|[^'])*')\s+VALUE\s+(%s)\s+FORMAT\s+JSON\s*\)",
                                 r"JSON_OBJECT(\1, JSON(\2))", adapted, flags=re.I)
                adapted = re.sub(r"CAST\(\s*(%s)\s+AS\s+JSON\s*\)",
                                 r"JSON_EXTRACT(\1, '$')", adapted, flags=re.I)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT " + adapted, rhs_parameters)
                    actual, = cursor.fetchone()
                item.update(passed=actual == value, rhs_sql=rhs_sql, rhs_parameters=list(rhs_parameters),
                            adapted_sql=adapted, actual_value=actual, expected_value=value)
            except (DatabaseError, InterfaceError, TypeError, ValueError, AttributeError) as error:
                item.update(passed=False, error_type=type(error).__name__, error=str(error))
            finally:
                connection.vendor = original_vendor
            backend_strings.append(item)
finally:
    connection.vendor = original_vendor
    if had_mariadb:
        wrapper.mysql_is_mariadb = original_mariadb
    else:
        wrapper.__dict__.pop("mysql_is_mariadb", None)

passed = all(record["passed"] for record in results + oracle + expressions + backend_strings)
print(json.dumps({"passed": passed, "django_version": django.get_version(),
    "sqlite_database_cases": results, "oracle_parameter_separation_cases": oracle,
    "sqlite_cases_total": len(results), "oracle_branch_cases_total": len(oracle),
    "sqlite_expression_cases": expressions, "sqlite_expression_cases_total": len(expressions),
    "backend_rhs_string_cases": backend_strings, "backend_rhs_string_cases_total": len(backend_strings),
    "live_oracle_queries": 0, "new_model_calls": 0,
    "coverage_limit": "48 original SQLite ORM cases plus6 expression-list queries. Direct IN(None) and cross-type inequality are not asserted. Oracle parameter isolation has3 compiler cases. Ten compiled singleton string RHS fragments are evaluated using explicit SQLite JSON1 adapters, not a MySQL/Oracle server, JSON comparison semantics or full backend integration. Only the documented JSON_VALUE/QUERY, JSON_OBJECT, JSON_EXTRACT, JSON_UNQUOTE and direct JSON-cast forms are adapted; unrecognized vendor syntax is a diagnostic limitation, not proof that a target-server query fails."},
    ensure_ascii=False))
raise SystemExit(0 if passed else 1)

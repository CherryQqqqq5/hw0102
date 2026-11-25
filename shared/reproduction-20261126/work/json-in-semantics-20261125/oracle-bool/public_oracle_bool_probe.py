import ast
import hashlib
import json
from pathlib import Path
import re


SOURCE_SHA256 = "ec6dd37a702485aa5fb9a7ef54588fd6616167a23dd5d94e4a4808444a331462"


def public_namespace():
    supplied = globals().get("BASE_SOURCE")
    if supplied is None:
        source = Path("/base-public-contract-probe.py").read_bytes()
    elif isinstance(supplied, str):
        source = supplied.encode()
    else:
        raise ValueError("BASE_SOURCE must be the unchanged public source string")
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError("The previously qualified public probe source changed")
    module = ast.parse(source)
    if not (isinstance(module.body[-2], ast.Expr)
            and isinstance(module.body[-2].value, ast.Call)
            and isinstance(module.body[-2].value.func, ast.Name)
            and module.body[-2].value.func.id == "print"
            and isinstance(module.body[-1], ast.Raise)):
        raise ValueError("The qualified public probe no longer has the expected output tail")
    module.body = module.body[:-2]
    namespace = {"__name__": "__main__"}
    exec(compile(module, "<qualified-public-contract-probe>", "exec"), namespace)
    return namespace


def main():
    namespace = public_namespace()
    connection, raw = namespace["connection"], namespace["raw"]
    fallback = namespace["oracle_json_value"]

    def oracle19_json_value(document, path):
        kind, = raw.execute("SELECT json_type(?, ?)", (document, path)).fetchone()
        # Oracle19默认JSON_VALUE将JSON布尔值返回为VARCHAR2字符串。
        return kind if kind in ("true", "false") else fallback(document, path)

    raw.create_function("COURSE_JSON_VALUE", 2, oracle19_json_value)
    cases, original_vendor = [], connection.vendor
    try:
        connection.vendor = "oracle"
        for value, expected in ((True, "true"), (False, "false")):
            row = {"value": value, "expected_string": expected,
                "tier": "compiled_Oracle_singleton_bool_RHS_on_limited_SQLite_JSON1_adapter"}
            try:
                query = namespace["PublicJSONValue"].objects.filter(payload__sample__in=[value]).query
                compiler = query.get_compiler(using="default")
                sql, parameters = query.where.children[0].process_rhs(compiler, connection)
                connection.vendor = original_vendor
                adapted = re.sub(r"\bJSON_VALUE\s*\(", "COURSE_JSON_VALUE(", sql, flags=re.I)
                adapted = re.sub(r"\bJSON_QUERY\s*\(", "COURSE_JSON_QUERY(", adapted, flags=re.I)
                adapted = re.sub(r"JSON_OBJECT\(\s*('(?:''|[^'])*')\s+VALUE\s+(%s)\s+FORMAT\s+JSON\s*\)",
                    r"JSON_OBJECT(\1, JSON(\2))", adapted, flags=re.I)
                placeholder_match = sql.count("%s") == len(parameters)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT " + adapted, parameters)
                    actual, = cursor.fetchone()
                row.update(rhs_sql=sql, parameters=list(parameters), adapted_sql=adapted,
                    parameters_separate=bool(parameters) and placeholder_match,
                    placeholder_count_match=placeholder_match, actual_value=actual,
                    passed=placeholder_match and isinstance(actual, str) and actual == expected)
            except (namespace["DatabaseError"], namespace["InterfaceError"], TypeError, ValueError, AttributeError) as error:
                row.update(passed=False, error_type=type(error).__name__, error=str(error))
            finally:
                connection.vendor = "oracle"
            cases.append(row)
    finally:
        connection.vendor = original_vendor
    groups = {"sqlite_database_cases": namespace["results"],
        "sqlite_expression_cases": namespace["expressions"],
        "oracle_parameter_separation_cases": namespace["oracle"],
        "backend_rhs_string_cases": namespace["backend_strings"]}
    passed = all(row["passed"] for group in [*groups.values(), cases] for row in group)
    print(json.dumps({"passed": passed, **groups, "oracle_bool_rhs_string_cases": cases,
        "qualified_public_source_sha256": SOURCE_SHA256,
        "base_cases_total": 67, "oracle_bool_cases_total": 2,
        "new_model_calls": 0, "original_grader_calls": 0, "live_mysql_or_oracle_queries": 0,
        "coverage_limit": "The unchanged48+6+3+10 public cases, including strict dangerous-string parameter isolation, execute first. Two additional compiled Oracle RHS fragments must match placeholder counts and return strings true/false for True/False; static SQL and parameterized forms are both admitted. Only the documented JSON_VALUE/QUERY and JSON_OBJECT forms are adapted with SQLite JSON1; this is not an Oracle19 driver/server query, complete SQL comparison, or general SQL-template equivalence test.",
        "oracle_boolean_source": "https://docs.oracle.com/en/database/oracle/oracle-database/19/adjsn/function-JSON_VALUE.html"}, ensure_ascii=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()

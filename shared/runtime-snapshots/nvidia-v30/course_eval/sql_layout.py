import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import sqlparse
from sqlparse import lexer, tokens


@dataclass(frozen=True)
class NormalizedQuery:
    sql: str
    source_sha256: str
    normalized_sha256: str
    source_characters: int
    normalized_characters: int
    semantic_tokens: int


def semantic_signature(sql):
    signature = []
    for kind, value in lexer.tokenize(sql):
        if kind in tokens.Whitespace or kind in tokens.Comment:
            continue
        if kind in tokens.Keyword:
            value = " ".join(value.split())
        signature.append((str(kind), value))
    if signature and signature[-1] == (str(tokens.Punctuation), ";"):
        signature.pop()
    return signature


def normalize_query(sql):
    parsed = sqlparse.parse(sql)
    if len(parsed) != 1 or parsed[0].get_type() != "SELECT":
        raise ValueError("Delivery normalization requires exactly one SELECT query")
    normalized = sqlparse.format(sql, strip_comments=True, strip_whitespace=True).strip()
    if not normalized.endswith(";"):
        normalized += ";"
    after = sqlparse.parse(normalized)
    if len(after) != 1 or after[0].get_type() != "SELECT":
        raise ValueError("The formatter changed the number or type of SQL statements")
    signature = semantic_signature(sql)
    if signature != semantic_signature(normalized):
        raise ValueError("The formatter changed a literal, identifier, operator or token order")
    return NormalizedQuery(normalized + "\n", hashlib.sha256(sql.encode()).hexdigest(),
        hashlib.sha256((normalized + "\n").encode()).hexdigest(), len(sql.strip()), len(normalized), len(signature))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError("Keep the original scored candidate unchanged; write the derived delivery separately")
    result = normalize_query(args.input.read_text())
    args.output.write_text(result.sql)
    record = asdict(result)
    record.pop("sql")
    record.update(sqlparse_version=sqlparse.__version__, new_model_calls=0,
        scope="Generic comment removal and repeated-whitespace collapse with a preserved non-layout token sequence; no hidden grader threshold or expected answer is supplied")
    args.output.with_suffix(".normalization.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()

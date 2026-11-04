def answer(question):
    if not question.startswith("What is") or not question.endswith("?"):
        raise ValueError("unknown operation")

    expr = question[len("What is "):-1].strip()
    if not expr:
        raise ValueError("syntax error")

    tokens = expr.split()

    ops = {
        "plus": lambda a, b: a + b,
        "minus": lambda a, b: a - b,
        "multiplied": lambda a, b: a * b,
        "divided": lambda a, b: a // b,
    }

    items = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        try:
            val = int(tok)
            items.append(("num", val))
            i += 1
            continue
        except ValueError:
            pass

        if tok in ("plus", "minus"):
            items.append(("op", ops[tok]))
            i += 1
        elif tok in ("multiplied", "divided"):
            if i + 1 < n and tokens[i + 1] == "by":
                items.append(("op", ops[tok]))
                i += 2
            else:
                raise ValueError("unknown operation")
        else:
            raise ValueError("unknown operation")

    if not items or items[0][0] != "num":
        raise ValueError("syntax error")

    result = items[0][1]
    i = 1
    while i < len(items):
        if i + 1 >= len(items):
            raise ValueError("syntax error")
        op_item = items[i]
        num_item = items[i + 1]
        if op_item[0] != "op" or num_item[0] != "num":
            raise ValueError("syntax error")
        result = op_item[1](result, num_item[1])
        i += 2

    return result

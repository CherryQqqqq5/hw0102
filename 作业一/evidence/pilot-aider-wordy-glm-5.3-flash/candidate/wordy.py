def answer(question):
    if not isinstance(question, str) or not question.endswith("?"):
        raise ValueError("unknown operation")

    question = question[:-1]
    words = question.split()

    if len(words) < 2 or words[0] != "What" or words[1] != "is":
        raise ValueError("unknown operation")

    tokens = words[2:]

    ops = {
        "plus": lambda a, b: a + b,
        "minus": lambda a, b: a - b,
        "multiplied by": lambda a, b: a * b,
        "divided by": lambda a, b: a / b,
    }

    def is_number(token):
        try:
            int(token)
            return True
        except ValueError:
            return False

    if not tokens:
        raise ValueError("syntax error")
    if not is_number(tokens[0]):
        raise ValueError("syntax error")

    result = int(tokens[0])
    i = 1
    while i < len(tokens):
        matched = None
        for op, func in ops.items():
            parts = op.split()
            if tokens[i:i + len(parts)] == parts:
                matched = (op, func, len(parts))
                break
        if matched is None:
            if is_number(tokens[i]):
                raise ValueError("syntax error")
            raise ValueError("unknown operation")
        op, func, oplen = matched
        i += oplen
        if i >= len(tokens) or not is_number(tokens[i]):
            raise ValueError("syntax error")
        operand = int(tokens[i])
        i += 1
        result = func(result, operand)

    if isinstance(result, float):
        if result.is_integer():
            return int(result)
        return result
    return result

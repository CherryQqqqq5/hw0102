import re


def answer(question):
    prefix = "What is"
    if not question.startswith(prefix):
        raise ValueError("unknown operation")

    text = question[len(prefix):].strip()
    if text.endswith("?"):
        text = text[:-1].strip()
    if not text:
        raise ValueError("syntax error")

    # Normalize verbal operations into single-character operators.
    text = re.sub(r"\bmultiplied\s+by\b", "*", text)
    text = re.sub(r"\bdivided\s+by\b", "/", text)
    text = re.sub(r"\bplus\b", "+", text)
    text = re.sub(r"\bminus\b", "-", text)

    tokens = text.split()
    if not tokens:
        raise ValueError("syntax error")

    operators = {"+", "-", "*", "/"}

    # Any token that is neither an integer nor a supported operator is an
    # unknown operation.
    for token in tokens:
        if token in operators:
            continue
        try:
            int(token)
        except ValueError:
            raise ValueError("unknown operation")

    # Valid expressions must alternate: number, operator, number, ...
    if len(tokens) % 2 == 0:
        raise ValueError("syntax error")

    for index, token in enumerate(tokens):
        if index % 2 == 0:
            try:
                int(token)
            except ValueError:
                raise ValueError("syntax error")
        elif token not in operators:
            raise ValueError("syntax error")

    result = int(tokens[0])
    for index in range(1, len(tokens), 2):
        operator = tokens[index]
        operand = int(tokens[index + 1])
        if operator == "+":
            result += operand
        elif operator == "-":
            result -= operand
        elif operator == "*":
            result *= operand
        else:
            result //= operand

    return result

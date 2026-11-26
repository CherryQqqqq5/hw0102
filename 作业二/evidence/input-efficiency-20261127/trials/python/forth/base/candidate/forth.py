"""A small evaluator for a subset of the Forth programming language."""

import re


class StackUnderflowError(Exception):
    """Raised when an operation needs more values than the stack contains."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


_INTEGER_RE = re.compile(r"-?[0-9]+")
_UNDERFLOW_MESSAGE = "Insufficient number of items in stack"


def _require(stack, count):
    """Ensure that at least ``count`` values are available on ``stack``."""
    if len(stack) < count:
        raise StackUnderflowError(_UNDERFLOW_MESSAGE)


def _add(stack):
    _require(stack, 2)
    right = stack.pop()
    left = stack.pop()
    stack.append(left + right)


def _subtract(stack):
    _require(stack, 2)
    right = stack.pop()
    left = stack.pop()
    stack.append(left - right)


def _multiply(stack):
    _require(stack, 2)
    right = stack.pop()
    left = stack.pop()
    stack.append(left * right)


def _divide(stack):
    _require(stack, 2)
    right = stack[-1]
    if right == 0:
        raise ZeroDivisionError("divide by zero")

    left = stack[-2]
    del stack[-2:]
    quotient = abs(left) // abs(right)
    if (left < 0) != (right < 0):
        quotient = -quotient
    stack.append(quotient)


def _dup(stack):
    _require(stack, 1)
    stack.append(stack[-1])


def _drop(stack):
    _require(stack, 1)
    stack.pop()


def _swap(stack):
    _require(stack, 2)
    stack[-1], stack[-2] = stack[-2], stack[-1]


def _over(stack):
    _require(stack, 2)
    stack.append(stack[-2])


_BUILT_INS = {
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "dup": _dup,
    "drop": _drop,
    "swap": _swap,
    "over": _over,
}


class _UserWord:
    """A defined word and the word table available when it was defined."""

    __slots__ = ("body", "environment")

    def __init__(self, body, environment):
        self.body = body
        self.environment = environment


class _Interpreter:
    def __init__(self):
        self.stack = []
        self.words = dict(_BUILT_INS)

    def run(self, tokens):
        index = 0
        while index < len(tokens):
            token = tokens[index].lower()
            if token == ":":
                index = self._define(tokens, index)
            elif token == ";":
                raise ValueError("illegal operation")
            else:
                self._execute(tokens[index], self.words)
                index += 1
        return self.stack

    def _define(self, tokens, index):
        index += 1
        if index >= len(tokens):
            raise ValueError("illegal operation")

        name = tokens[index].lower()
        if (
            _INTEGER_RE.fullmatch(name)
            or name == ":"
            or name == ";"
        ):
            raise ValueError("illegal operation")
        index += 1

        body = []
        while index < len(tokens) and tokens[index].lower() != ";":
            body.append(tokens[index])
            index += 1
        if index >= len(tokens):
            raise ValueError("illegal operation")

        # A definition sees exactly the words that existed before it was made.
        # This lets a redefined word refer to its previous definition.
        environment = dict(self.words)
        self.words[name] = _UserWord(body, environment)
        return index + 1

    def _execute(self, token, words):
        normalized = token.lower()
        if _INTEGER_RE.fullmatch(normalized):
            self.stack.append(int(normalized))
            return

        word = words.get(normalized)
        if word is None:
            raise ValueError("undefined operation")

        if isinstance(word, _UserWord):
            for body_token in word.body:
                self._execute(body_token, word.environment)
        else:
            word(self.stack)


def evaluate(input_data):
    """Evaluate Forth source lines and return the resulting stack."""
    if isinstance(input_data, str):
        lines = [input_data]
    else:
        lines = input_data

    tokens = []
    for line in lines:
        tokens.extend(str(line).split())

    return _Interpreter().run(tokens)

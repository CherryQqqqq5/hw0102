"""A small evaluator for a deliberately limited subset of Forth."""

import re


_NUMBER_RE = re.compile(r"[+-]?[0-9]+")
_UNDERFLOW_MESSAGE = "Insufficient number of items in stack"
_ILLEGAL_OPERATION = "illegal operation"
_UNDEFINED_OPERATION = "undefined operation"
_DIVIDE_BY_ZERO = "divide by zero"


class StackUnderflowError(Exception):
    """Raised when the stack does not contain enough values for an operation."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class _UserWord:
    """A defined word and the word table it saw when it was defined."""

    __slots__ = ("body", "words")

    def __init__(self, body, words):
        self.body = tuple(body)
        self.words = words


def _is_number(token):
    return _NUMBER_RE.fullmatch(token) is not None


def _require(stack, count):
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
    divisor = stack.pop()
    dividend = stack.pop()
    if divisor == 0:
        raise ZeroDivisionError(_DIVIDE_BY_ZERO)
    quotient = abs(dividend) // abs(divisor)
    if (dividend < 0) != (divisor < 0):
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


_BUILTINS = {
    "+": _add,
    "-": _subtract,
    "*": _multiply,
    "/": _divide,
    "dup": _dup,
    "drop": _drop,
    "swap": _swap,
    "over": _over,
}


def _execute(tokens, words, stack):
    for token in tokens:
        if _is_number(token):
            stack.append(int(token))
            continue

        word = token.lower()
        action = words.get(word)
        if action is None:
            raise ValueError(_UNDEFINED_OPERATION)

        if isinstance(action, _UserWord):
            _execute(action.body, action.words, stack)
        else:
            action(stack)


def evaluate(input_data):
    """Evaluate Forth source lines and return the final stack."""
    stack = []
    words = dict(_BUILTINS)

    defining = False
    name = None
    body = []
    definition_words = None

    for line in input_data:
        for token in line.split():
            if defining:
                if name is None:
                    if token in (":", ";") or _is_number(token):
                        raise ValueError(_ILLEGAL_OPERATION)
                    name = token.lower()
                elif token == ";":
                    words[name] = _UserWord(body, definition_words)
                    defining = False
                    name = None
                    body = []
                    definition_words = None
                else:
                    body.append(token)
                continue

            if token == ":":
                defining = True
                name = None
                body = []
                definition_words = dict(words)
            elif token == ";":
                raise ValueError(_ILLEGAL_OPERATION)
            else:
                _execute((token,), words, stack)

    if defining:
        raise ValueError(_ILLEGAL_OPERATION)

    return stack

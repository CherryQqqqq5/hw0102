"""A small evaluator for a subset of the Forth programming language.

Only signed integers, the four basic integer arithmetic operations and the
four basic stack operations are supported, plus user defined words.
"""

import re


class StackUnderflowError(Exception):
    """Raised when an operation needs more values than the stack holds."""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


_NUMBER = re.compile(r"-?[0-9]+\Z")

# Words provided by the evaluator itself.  A user definition with the same
# name takes precedence over one of these.
_BUILTINS = frozenset({"+", "-", "*", "/", "dup", "drop", "swap", "over"})

_UNDERFLOW_MESSAGE = "Insufficient number of items in stack"


def _is_number(token):
    """Return True when *token* is an integer literal."""
    return _NUMBER.fullmatch(token) is not None


def _require(stack, count):
    """Make sure the stack holds at least *count* values."""
    if len(stack) < count:
        raise StackUnderflowError(_UNDERFLOW_MESSAGE)


def _apply_builtin(word, stack):
    """Execute a built-in word against *stack*."""
    if word in {"+", "-", "*", "/"}:
        _require(stack, 2)
        right = stack.pop()
        left = stack.pop()
        if word == "+":
            stack.append(left + right)
        elif word == "-":
            stack.append(left - right)
        elif word == "*":
            stack.append(left * right)
        else:  # division
            if right == 0:
                raise ZeroDivisionError("divide by zero")
            quotient = abs(left) // abs(right)
            stack.append(-quotient if (left < 0) != (right < 0) else quotient)
        return

    if word == "dup":
        _require(stack, 1)
        stack.append(stack[-1])
    elif word == "drop":
        _require(stack, 1)
        stack.pop()
    elif word == "swap":
        _require(stack, 2)
        stack[-2], stack[-1] = stack[-1], stack[-2]
    elif word == "over":
        _require(stack, 2)
        stack.append(stack[-2])


def _expand(token, definitions):
    """Resolve *token* using the definitions that exist at this moment.

    A definition stores a snapshot of the words it was built from, so later
    redefinitions do not change an already defined word.
    """
    if _is_number(token):
        return [int(token)]
    word = token.lower()
    if word in definitions:
        return list(definitions[word])
    return [word]


def _execute(token, stack, definitions):
    """Execute one (already expanded) token."""
    if isinstance(token, int):
        stack.append(token)
    elif token in definitions:
        for inner in definitions[token]:
            _execute(inner, stack, definitions)
    elif token in _BUILTINS:
        _apply_builtin(token, stack)
    else:
        raise ValueError("undefined operation")


def evaluate(input_data):
    """Evaluate the lines of Forth code in *input_data*.

    Returns the stack (bottom to top) after all lines have been processed.
    Definitions and stack contents carry over from one line to the next.
    """
    if isinstance(input_data, str):
        input_data = [input_data]

    stack = []
    definitions = {}
    state = "normal"       # one of: normal, name, definition
    current_name = None
    current_body = []

    for line in input_data:
        for raw_token in line.split():
            token = raw_token.lower()

            if state == "name":
                # Numbers cannot be used as names for new words.
                if _is_number(token):
                    raise ValueError("illegal operation")
                current_name = token
                state = "definition"
                continue

            if state == "definition":
                if token == ";":
                    definitions[current_name] = current_body
                    current_body = []
                    current_name = None
                    state = "normal"
                else:
                    current_body.extend(_expand(token, definitions))
                continue

            # Normal mode.
            if token == ":":
                state = "name"
            elif token == ";":
                raise ValueError("illegal operation")
            else:
                for expanded in _expand(token, definitions):
                    _execute(expanded, stack, definitions)

    return stack

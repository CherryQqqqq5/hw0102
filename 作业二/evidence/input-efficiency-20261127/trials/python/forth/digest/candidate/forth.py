"""A small evaluator for a deliberately restricted subset of Forth."""

import re


_UNDERFLOW_MESSAGE = "Insufficient number of items in stack"
_NUMBER_PATTERN = re.compile(r"[+-]?[0-9]+\Z")
_BUILTINS = frozenset({"+", "-", "*", "/", "dup", "drop", "swap", "over"})


class StackUnderflowError(Exception):
    """Raised when an operation requires more values than the stack holds."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _is_number(token):
    """Return whether a token should be interpreted as an integer literal."""
    return _NUMBER_PATTERN.fullmatch(token) is not None


class _Evaluator:
    def __init__(self):
        self.stack = []
        # Each definition is stored as primitive instructions: integers are
        # literals and strings are built-in operation names.  Expanding words
        # here makes a definition keep the meanings that were active when it
        # was created, which matters when words are later redefined.
        self.definitions = {}

    def run(self, input_data):
        tokens = []
        for line in input_data:
            tokens.extend(line.split())

        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token == ":":
                index = self._define_word(tokens, index)
            elif token == ";":
                raise ValueError("illegal operation")
            else:
                self._execute_token(token)
                index += 1

        return self.stack

    def _define_word(self, tokens, start):
        if start + 1 >= len(tokens):
            raise ValueError("illegal operation")

        name = tokens[start + 1]
        if _is_number(name) or name in {":", ";"}:
            raise ValueError("illegal operation")

        end = start + 2
        while end < len(tokens) and tokens[end] != ";":
            if tokens[end] == ":":
                raise ValueError("illegal operation")
            end += 1

        if end == len(tokens):
            raise ValueError("illegal operation")

        self.definitions[name.lower()] = self._resolve_body(tokens[start + 2:end])
        return end + 1

    def _resolve_body(self, tokens):
        """Expand a definition body using the currently known word meanings."""
        instructions = []
        for token in tokens:
            if _is_number(token):
                instructions.append(int(token))
                continue

            word = token.lower()
            if word in self.definitions:
                instructions.extend(self.definitions[word])
            elif word in _BUILTINS:
                instructions.append(word)
            else:
                raise ValueError("undefined operation")
        return tuple(instructions)

    def _execute_token(self, token):
        if _is_number(token):
            self.stack.append(int(token))
            return

        word = token.lower()
        if word in self.definitions:
            for instruction in self.definitions[word]:
                self._execute_instruction(instruction)
        elif word in _BUILTINS:
            self._apply(word)
        else:
            raise ValueError("undefined operation")

    def _execute_instruction(self, instruction):
        if isinstance(instruction, int):
            self.stack.append(instruction)
        else:
            self._apply(instruction)

    def _require(self, count):
        if len(self.stack) < count:
            raise StackUnderflowError(_UNDERFLOW_MESSAGE)

    def _binary(self, operation):
        self._require(2)
        right = self.stack.pop()
        left = self.stack.pop()
        self.stack.append(operation(left, right))

    def _apply(self, word):
        if word == "+":
            self._binary(lambda left, right: left + right)
        elif word == "-":
            self._binary(lambda left, right: left - right)
        elif word == "*":
            self._binary(lambda left, right: left * right)
        elif word == "/":
            self._divide()
        elif word == "dup":
            self._require(1)
            self.stack.append(self.stack[-1])
        elif word == "drop":
            self._require(1)
            self.stack.pop()
        elif word == "swap":
            self._require(2)
            self.stack[-2], self.stack[-1] = self.stack[-1], self.stack[-2]
        elif word == "over":
            self._require(2)
            self.stack.append(self.stack[-2])

    def _divide(self):
        self._require(2)
        divisor = self.stack.pop()
        dividend = self.stack.pop()
        if divisor == 0:
            raise ZeroDivisionError("divide by zero")

        quotient = abs(dividend) // abs(divisor)
        if (dividend < 0) != (divisor < 0):
            quotient = -quotient
        self.stack.append(quotient)


def evaluate(input_data):
    """Evaluate the Forth source lines and return the resulting stack."""
    return _Evaluator().run(input_data)

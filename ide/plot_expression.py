"""Bounded parser and numeric evaluator for plot expressions."""
from dataclasses import dataclass
import math
import operator
import re

PARAMETERS = ('a', 'b', 'c')
MAX_EXPRESSION = 512
TOKEN = re.compile(r'\s+|[0-9]+(?:\.[0-9]*)?|[a-zA-Z_][a-zA-Z_0-9]*|.')
BINARY = {'+': (10, operator.add), '-': (10, operator.sub),
          '*': (20, operator.mul), '/': (20, operator.truediv), '^': (30, math.pow)}
FUNCTIONS = {'sin': (math.sin, 1), 'cos': (math.cos, 1), 'pow': (math.pow, 2)}


class ExpressionError(ValueError):
    def __init__(self, message, position):
        self.position = position
        super().__init__(f'{message} (column {position + 1})')


@dataclass(frozen=True)
class Expression:
    operations: tuple
    parameters: tuple

    def value(self, x, parameters):
        values = []
        try:
            for operation, argument in self.operations:
                if operation is None:
                    values.append(x if argument == 'x' else
                                  parameters.get(argument, 1.) if isinstance(argument, str) else argument)
                elif argument == 1:
                    values[-1] = operation(values[-1])
                else:
                    right = values.pop()
                    values[-1] = operation(values[-1], right)
                if not math.isfinite(values[-1]):
                    return None
        except (ArithmeticError, ValueError):
            return None
        return values[0]


def parse(source):
    if len(source) > MAX_EXPRESSION:
        raise ExpressionError('Expression too long', MAX_EXPRESSION)
    tokens = [(m[0], m.start()) for m in TOKEN.finditer(source) if not m[0].isspace()]
    tokens.append(('', len(source)))
    index = 0
    operations = []
    used = set()

    def expect(expected):
        nonlocal index
        token, pos = tokens[index]
        if token != expected:
            raise ExpressionError(f'Expected {expected!r}', pos)
        index += 1

    def read(minimum, depth):
        nonlocal index
        token, pos = tokens[index]
        if depth > 32:
            raise ExpressionError('Expression nested too deeply', pos)
        index += 1
        if token in ('+', '-'):
            read(30, depth + 1)
            if token == '-':
                operations.append((operator.neg, 1))
        elif token == '(':
            read(0, depth + 1)
            expect(')')
        elif token and '0' <= token[0] <= '9':
            operations.append((None, float(token)))
        elif token == 'x' or token in PARAMETERS:
            used.add(token)
            operations.append((None, token))
        elif token in FUNCTIONS:
            operation, arity = FUNCTIONS[token]
            expect('(')
            read(0, depth + 1)
            if arity == 2:
                expect(',')
                read(0, depth + 1)
            expect(')')
            operations.append((operation, arity))
        else:
            raise ExpressionError(f'Unexpected token {token!r}' if token else 'Expected expression', pos)
        while tokens[index][0] in BINARY:
            symbol = tokens[index][0]
            precedence, operation = BINARY[symbol]
            if precedence < minimum:
                break
            index += 1
            read(precedence + (symbol != '^'), depth + 1)
            operations.append((operation, 2))

    read(0, 0)
    if tokens[index][0]:
        token, pos = tokens[index]
        raise ExpressionError(f'Unexpected token {token!r}', pos)
    return Expression(tuple(operations), tuple(p for p in PARAMETERS if p in used))


def sample(expression, parameters, view, width, height, cancelled=lambda: False):
    """Return polyline segments with a bounded midpoint refinement budget."""
    count = max(256, min(2048, width))
    budget = 4 * count
    yspan = view.ymax - view.ymin
    xspan = view.xmax - view.xmin

    def inspect(left, right, depth):
        nonlocal budget
        x0, y0 = left
        x1, y1 = right
        if y0 is None or y1 is None:
            return [None, right]
        midpoint = x0 + (x1 - x0) / 2
        if budget <= 0 or midpoint in (x0, x1):
            return [None, right] if abs(y1 / 2 - y0 / 2) / yspan > 1 else [right]
        budget -= 1
        middle = expression.value(midpoint, parameters)
        if middle is None:
            return [None, right]
        deviation = abs(middle - (y0 / 2 + y1 / 2)) / yspan * height
        if deviation <= 2:
            return [right]
        if depth == 0:
            return [None, right] if deviation > 12 else [(midpoint, middle), right]
        return inspect(left, (midpoint, middle), depth - 1) + inspect((midpoint, middle), right, depth - 1)

    segments = [[]]
    left = (view.xmin, expression.value(view.xmin, parameters))
    if left[1] is not None:
        segments[-1].append(left)
    for i in range(1, count):
        if i % 32 == 1 and cancelled():
            return []
        x = view.xmax if i == count - 1 else view.xmin + i / (count - 1) * xspan
        right = (x, expression.value(x, parameters))
        for point in inspect(left, right, 4):
            if point is None or point[1] is None:
                if segments[-1]:
                    segments.append([])
            else:
                segments[-1].append(point)
        left = right
    return [segment for segment in segments if segment]

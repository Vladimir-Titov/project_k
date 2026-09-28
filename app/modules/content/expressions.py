import ast
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Protocol


class InvalidExpressionError(ValueError):
    pass


@dataclass(slots=True)
class RandomSource:
    seed: int
    counter: int = 0
    draws: list[int] = field(default_factory=list, init=False)
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)
        for _ in range(self.counter):
            self._random.randint(0, 2**31 - 1)

    def randint(self, start: int, end: int) -> int:
        if start > end:
            raise InvalidExpressionError('random_int start must not exceed end')
        # One fixed-width draw keeps the persisted counter independent from
        # CPython's range implementation.
        raw = self._random.randint(0, 2**31 - 1)
        self.counter += 1
        result = start + raw % (end - start + 1)
        self.draws.append(result)
        return result


class ExpressionEvaluator(Protocol):
    def __call__(
        self,
        expression: str,
        *,
        source: Mapping[str, Decimal],
        target: Mapping[str, Decimal],
        random_source: RandomSource,
    ) -> Decimal: ...


_BINARY_OPERATORS: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: lambda left, right: left + right,
    ast.Sub: lambda left, right: left - right,
    ast.Mult: lambda left, right: left * right,
    ast.Div: lambda left, right: left / right,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[Decimal], Decimal]] = {
    ast.UAdd: lambda value: value,
    ast.USub: lambda value: -value,
}
_FUNCTIONS = frozenset({'min', 'max', 'clamp', 'round_half_up', 'random_int'})
CLAMP_ARGUMENT_COUNT = 3
RANDOM_ARGUMENT_COUNT = 2


class ExpressionV1:
    def __init__(
        self,
        expression: str,
        *,
        available_stat_codes: set[str] | None = None,
        allow_random: bool = True,
    ) -> None:
        try:
            self.tree = ast.parse(expression, mode='eval')
        except SyntaxError as error:
            raise InvalidExpressionError('Expression has invalid syntax') from error
        self.available_stat_codes = available_stat_codes
        self.allow_random = allow_random
        self._validate(self.tree)

    def _validate(self, node: ast.AST) -> None:  # noqa: C901, PLR0912
        if isinstance(node, ast.Expression):
            self._validate(node.body)
            return
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise InvalidExpressionError('Only numeric constants are allowed')
            return
        if isinstance(node, ast.BinOp):
            if type(node.op) not in _BINARY_OPERATORS:
                raise InvalidExpressionError(f'Unsupported operator: {type(node.op).__name__}')
            self._validate(node.left)
            self._validate(node.right)
            return
        if isinstance(node, ast.UnaryOp):
            if type(node.op) not in _UNARY_OPERATORS:
                raise InvalidExpressionError(f'Unsupported operator: {type(node.op).__name__}')
            self._validate(node.operand)
            return
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name) or node.value.id not in {'source', 'target'}:
                raise InvalidExpressionError('Only source.<stat> and target.<stat> references are allowed')
            if node.attr.startswith('_'):
                raise InvalidExpressionError('Private attributes are forbidden')
            if self.available_stat_codes is not None and node.attr not in self.available_stat_codes:
                raise InvalidExpressionError(f'Unknown stat code: {node.attr}')
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCTIONS:
                raise InvalidExpressionError('Unsupported function')
            if node.func.id == 'random_int' and not self.allow_random:
                raise InvalidExpressionError('random_int is not allowed in persistent modifiers')
            if node.keywords:
                raise InvalidExpressionError('Keyword arguments are forbidden')
            for argument in node.args:
                self._validate(argument)
            return
        raise InvalidExpressionError(f'Unsupported expression: {type(node).__name__}')

    def evaluate(
        self,
        *,
        source: Mapping[str, Decimal],
        target: Mapping[str, Decimal],
        random_source: RandomSource,
    ) -> Decimal:
        try:
            return self._evaluate_node(
                self.tree.body,
                source=source,
                target=target,
                random_source=random_source,
            )
        except (ArithmeticError, InvalidOperation, KeyError) as error:
            raise InvalidExpressionError('Expression could not be evaluated') from error

    def _evaluate_node(
        self,
        node: ast.AST,
        *,
        source: Mapping[str, Decimal],
        target: Mapping[str, Decimal],
        random_source: RandomSource,
    ) -> Decimal:
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value))
        if isinstance(node, ast.BinOp):
            left = self._evaluate_node(node.left, source=source, target=target, random_source=random_source)
            right = self._evaluate_node(node.right, source=source, target=target, random_source=random_source)
            return _BINARY_OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            value = self._evaluate_node(node.operand, source=source, target=target, random_source=random_source)
            return _UNARY_OPERATORS[type(node.op)](value)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            values = source if node.value.id == 'source' else target
            return values[node.attr]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            arguments = [
                self._evaluate_node(item, source=source, target=target, random_source=random_source)
                for item in node.args
            ]
            return self._call(node.func.id, arguments, random_source)
        raise InvalidExpressionError(f'Unsupported expression: {type(node).__name__}')

    @staticmethod
    def _call(name: str, arguments: list[Decimal], random_source: RandomSource) -> Decimal:
        if name in {'min', 'max'}:
            if not arguments:
                raise InvalidExpressionError(f'{name} requires at least one argument')
            return (min if name == 'min' else max)(arguments)
        if name == 'clamp':
            if len(arguments) != CLAMP_ARGUMENT_COUNT:
                raise InvalidExpressionError('clamp requires three arguments')
            value, minimum, maximum = arguments
            return min(max(value, minimum), maximum)
        if name == 'round_half_up':
            if len(arguments) != 1:
                raise InvalidExpressionError('round_half_up requires one argument')
            return arguments[0].quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if name == 'random_int':
            if len(arguments) != RANDOM_ARGUMENT_COUNT or any(
                value != value.to_integral_value() for value in arguments
            ):
                raise InvalidExpressionError('random_int requires two integer arguments')
            return Decimal(random_source.randint(int(arguments[0]), int(arguments[1])))
        raise InvalidExpressionError(f'Unsupported function: {name}')


def evaluate_expression_v1(
    expression: str,
    *,
    source: Mapping[str, Decimal],
    target: Mapping[str, Decimal],
    random_source: RandomSource,
) -> Decimal:
    return ExpressionV1(expression).evaluate(source=source, target=target, random_source=random_source)


EVALUATORS: dict[str, ExpressionEvaluator] = {'expression_v1': evaluate_expression_v1}


def validate_expression(
    evaluator_type: str,
    expression: str,
    *,
    available_stat_codes: set[str] | None = None,
    allow_random: bool = True,
) -> None:
    if evaluator_type != 'expression_v1':
        raise InvalidExpressionError(f'Unknown evaluator type: {evaluator_type}')
    ExpressionV1(
        expression,
        available_stat_codes=available_stat_codes,
        allow_random=allow_random,
    )


def evaluate_expression(
    evaluator_type: str,
    expression: str,
    *,
    source: Mapping[str, Decimal],
    target: Mapping[str, Decimal],
    random_source: RandomSource,
) -> Decimal:
    try:
        evaluator = EVALUATORS[evaluator_type]
    except KeyError:
        raise InvalidExpressionError(f'Unknown evaluator type: {evaluator_type}') from None
    return evaluator(expression, source=source, target=target, random_source=random_source)

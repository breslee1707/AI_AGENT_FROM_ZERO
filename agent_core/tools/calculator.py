"""A restricted arithmetic calculator for model-generated expressions."""

from __future__ import annotations

import ast
import operator

from .base import ToolSpec


_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    """Evaluate only numeric constants and explicitly allowed operators."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](
            _eval_node(node.left), _eval_node(node.right)
        )
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Biểu thức chứa thành phần không được phép.")


def calculator(expression: str) -> str:
    """Calculate a basic arithmetic expression without using ``eval``."""
    tree = ast.parse(expression, mode="eval")
    value = _eval_node(tree.body)
    return f"{expression} = {value}"


CALCULATOR_TOOL = ToolSpec(
    name="calculator",
    description=(
        "Tính một biểu thức số học chính xác (cộng trừ nhân chia, luỹ thừa, "
        "phần dư). Dùng khi cần tính toán thay vì để model tự nhẩm (dễ sai)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Biểu thức số học, ví dụ: '12000000 + 1200000'.",
            }
        },
        "required": ["expression"],
    },
    func=calculator,
)

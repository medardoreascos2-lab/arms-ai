"""Registry of local, side-effect-free MEDAR tools and stubs."""

import ast
import operator
from types import MappingProxyType
from typing import Any, Mapping

from backend.medar.request import CognitiveDomain, RiskClass
from backend.medar.tool_contract import (
    CognitiveTool,
    SideEffectLevel,
    ToolCall,
    ToolContract,
    ToolResult,
    ToolResultStatus,
)


class SafeCalculator:
    contract = ToolContract(
        "calculator",
        "Safe arithmetic calculator",
        CognitiveDomain.GENERAL,
        RiskClass.LOW,
        {"expression": "string"},
        {"value": "number"},
        False,
        False,
        SideEffectLevel.NONE,
    )

    _OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def execute(self, call: ToolCall) -> ToolResult:
        expression = call.arguments.get("expression")
        if not isinstance(expression, str) or len(expression) > 200:
            return ToolResult(call.call_id, self.contract.tool_id, ToolResultStatus.FAILED, {}, "INVALID_INPUT")
        try:
            value = self._evaluate(ast.parse(expression, mode="eval").body)
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            return ToolResult(call.call_id, self.contract.tool_id, ToolResultStatus.FAILED, {}, "INVALID_EXPRESSION")
        return ToolResult(call.call_id, self.contract.tool_id, ToolResultStatus.SUCCESS, {"value": value})

    def _evaluate(self, node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._OPERATORS:
            return self._OPERATORS[type(node.op)](self._evaluate(node.left), self._evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._OPERATORS:
            return self._OPERATORS[type(node.op)](self._evaluate(node.operand))
        raise ValueError("unsupported arithmetic expression")


class LocalStubTool:
    def __init__(self, contract: ToolContract):
        self.contract = contract

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            call.call_id,
            self.contract.tool_id,
            ToolResultStatus.SUCCESS,
            {"stub": True, "received_keys": tuple(sorted(call.arguments))},
        )


class ToolRegistry:
    def __init__(self, tools: tuple[CognitiveTool, ...]):
        entries: dict[str, CognitiveTool] = {}
        for tool in tools:
            if tool.contract.tool_id in entries:
                raise ValueError("duplicate tool id")
            entries[tool.contract.tool_id] = tool
        self._entries: Mapping[str, CognitiveTool] = MappingProxyType(entries)

    def get(self, tool_id: str) -> CognitiveTool:
        try:
            return self._entries[tool_id]
        except KeyError as exc:
            raise KeyError(f"unregistered tool: {tool_id}") from exc

    @property
    def tools(self) -> tuple[CognitiveTool, ...]:
        return tuple(self._entries.values())


def _stub(tool_id: str, domain: CognitiveDomain, input_schema: Mapping[str, str]) -> LocalStubTool:
    return LocalStubTool(
        ToolContract(
            tool_id,
            tool_id.replace("_", " ").title(),
            domain,
            RiskClass.MODERATE,
            input_schema,
            {"stub": "boolean", "received_keys": "array"},
            False,
            False,
            SideEffectLevel.NONE,
        )
    )


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        (
            SafeCalculator(),
            _stub("web_search_stub", CognitiveDomain.WEB_RESEARCH, {"query": "string"}),
            _stub("document_reader_stub", CognitiveDomain.DOCUMENT, {"document_id": "string"}),
            _stub("code_analysis_stub", CognitiveDomain.CODING, {"scope": "array"}),
            _stub("financial_analysis_stub", CognitiveDomain.FINANCIAL, {"instrument": "string"}),
            _stub("memory_lookup_stub", CognitiveDomain.GENERAL, {"query": "string"}),
        )
    )

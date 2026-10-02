"""Source scanner for the reviewed, current Python clock-call inventory."""

import ast
from collections import Counter
from pathlib import Path


EXACT_CLOCK_CALLS = frozenset({
    "datetime.now", "datetime.utcnow", "time.time", "time.monotonic",
    "time.perf_counter", "clock",
})


def scan_direct_clock_calls(root: Path = Path("backend")) -> list[dict]:
    calls = []
    for path in sorted(root.rglob("*.py")):
        if "tests" in path.parts:
            continue
        owner = []
        ordinal = Counter()

        class Visitor(ast.NodeVisitor):
            def visit_ClassDef(self, node):
                owner.append(node.name)
                self.generic_visit(node)
                owner.pop()

            def visit_FunctionDef(self, node):
                owner.append(node.name)
                self.generic_visit(node)
                owner.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                callee = ast.unparse(node.func)
                if callee in EXACT_CLOCK_CALLS or callee.endswith((".clock", "._clock")):
                    scope = ".".join(owner) if owner else "<module>"
                    key = (scope, callee)
                    ordinal[key] += 1
                    calls.append({
                        "path": path.as_posix(),
                        "owner": scope,
                        "callee": callee,
                        "ordinal": ordinal[key],
                        "line": node.lineno,
                    })
                self.generic_visit(node)

        Visitor().visit(ast.parse(path.read_text(encoding="utf-8-sig")))
    return calls

#!/usr/bin/env python3
"""Find likely new user-visible literals without banning data or technical text."""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path


# Product/provider names and machine-readable input examples are data, not copy.
EXEMPT_LITERALS = {
    "Shazam", "Primuse", "YouTube", "YouTube Music", "YT Music", "OAuth",
    "client_id (YouTube Data API)", "client_secret", "Cookie: …\nX-Goog-AuthUser: 0\nAuthorization: …",
    "English", "Русский", "Inbox", "music-lib", "YT", "♥ YT", "t",
}
USER_FACING_ATTRIBUTES = "title|placeholder|aria-label|alt"
ATTRIBUTE_LITERAL = re.compile(rf"\b({USER_FACING_ATTRIBUTES})\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|\{{\s*[\"']([^\"']+)[\"']\s*\}})")
JSX_TEXT = re.compile(r"<[^>]+>\s*([^<>{}\n][^<>{}\n]*?)\s*</")
DOTTED_KEY = re.compile(r"^[a-z][\w]*(?:\.[\w]+)+$")


def _is_copy(value: str) -> bool:
    value = value.strip().replace("\\n", "\n")
    return bool(value and value not in EXEMPT_LITERALS and re.search(r"[A-Za-zА-Яа-я]", value))


def _line_number(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def frontend_candidates(directory: Path) -> list[str]:
    """Return literal UI candidates in JSX text/attrs and user notification calls."""
    errors: list[str] = []
    for path in sorted(directory.rglob("*.tsx")):
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(directory).as_posix()
        for match in ATTRIBUTE_LITERAL.finditer(source):
            value = next(value for value in match.groups()[1:] if value is not None)
            if _is_copy(value):
                errors.append(f"{relative}:{_line_number(source, match.start())}: {match.group(1)} literal {value!r}")
        for match in JSX_TEXT.finditer(source):
            value = match.group(1).strip()
            if _is_copy(value):
                errors.append(f"{relative}:{_line_number(source, match.start(1))}: JSX text {value!r}")
    errors.extend(_notification_candidates(directory))
    return errors


def _notification_candidates(directory: Path) -> list[str]:
    """Use TypeScript's AST and lexical bindings; never match call-shaped text."""
    files = sorted(directory.rglob("*.ts")) + sorted(directory.rglob("*.tsx"))
    if not files:
        return []
    script = Path(__file__).with_name("check_copy_frontend.mjs")
    frontend_root = Path(__file__).resolve().parents[1] / "frontend"
    result = subprocess.run(
        ["node", str(script), str(frontend_root), str(directory), *(str(path) for path in files)],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        f"{item['relative']}:{item['line']}: notification literal {item['value']!r}"
        for item in json.loads(result.stdout)
        if _is_copy(item["value"])
    ]


def _message_imports(statements: list[ast.stmt]) -> dict[str, bool]:
    supported_modules = {"messages", "src.messages", "web.messages", "src.web.messages"}
    imports: dict[str, bool] = {}
    for node in statements:
        if not isinstance(node, ast.ImportFrom):
            continue
        supported = node.module in supported_modules or (node.level and node.module == "messages")
        for name in node.names:
            bound_name = name.asname or name.name
            imports[bound_name] = bool(supported and name.name == "message")
    return imports


def _scope_bindings(statements: list[ast.stmt]) -> set[str]:
    bindings: set[str] = set()
    for node in statements:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in node.names:
                bindings.add(name.asname or name.name.split(".")[0])
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings.add(target.id)
    return bindings


class _MessageCallVisitor(ast.NodeVisitor):
    def __init__(self, names: dict[str, bool], relative: str):
        self.scopes = [names]
        self.relative = relative
        self.errors: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and self.scopes[-1].get(node.func.id, False) and node.args:
            code = node.args[0]
            if isinstance(code, ast.Constant) and isinstance(code.value, str) and not DOTTED_KEY.fullmatch(code.value):
                self.errors.append(f"{self.relative}:{node.lineno}: message code must be a dotted literal key")
        self.generic_visit(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        scope = self.scopes[-1].copy()
        for name in _scope_bindings(node.body):
            scope[name] = False
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            scope[arg.arg] = False
        if node.args.vararg:
            scope[node.args.vararg.arg] = False
        if node.args.kwarg:
            scope[node.args.kwarg.arg] = False
        scope.update(_message_imports(node.body))
        self.scopes.append(scope)
        for child in node.body:
            self.visit(child)
        self.scopes.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function


def backend_candidates(directory: Path) -> list[str]:
    """Check only calls bound to the application message-descriptor constructor."""
    errors: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(directory).as_posix()
        names = _message_imports(tree.body)
        visitor = _MessageCallVisitor(names, relative)
        visitor.visit(tree)
        errors.extend(visitor.errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=Path("frontend/src"))
    parser.add_argument("--backend", type=Path, default=Path("src"))
    args = parser.parse_args(argv)
    errors = frontend_candidates(args.frontend) + backend_candidates(args.backend)
    if errors:
        print("Hardcoded-copy candidates found (review or replace with a message key):", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("Hardcoded-copy guardrail passed: no scoped candidates found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Catalog contract: every route job descriptor is renderable in both locales."""

import ast
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / "src/web/routes.py").read_text()
EN = json.loads((ROOT / "frontend/src/locales/en.json").read_text())
RU = json.loads((ROOT / "frontend/src/locales/ru.json").read_text())


def _leaves(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, value


def _lookup(catalog, code):
    value = catalog
    for part in code.split("."):
        value = value[part]
    return value


def _icu_args(text):
    return set(re.findall(r"\{([A-Za-z][\w]*)(?:\s*,|\})", text))


def _invalid_message_fallback_calls(directory):
    """Return calls to src.messages.message without a usable literal fallback."""
    invalid_calls = []
    for path in directory.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        message_names = _imported_message_names(tree)
        for scope, shadowed_names in _scopes(tree):
            for call in _direct_calls(scope):
                if not isinstance(call.func, ast.Name) or call.func.id not in message_names - shadowed_names:
                    continue
                fallback = next((keyword.value for keyword in call.keywords if keyword.arg == "fallback"), None)
                if fallback is None:
                    invalid_calls.append((call.lineno, "missing fallback"))
                elif isinstance(fallback, ast.Constant) and isinstance(fallback.value, str) and not fallback.value.strip():
                    invalid_calls.append((call.lineno, "blank fallback"))
    return invalid_calls


def _imported_message_names(tree):
    """Return module-level names imported from the supported messages modules."""
    return {
        imported.asname or imported.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module in {"messages", "src.messages"}
        for imported in node.names
        if imported.name == "message"
    }


def _local_bindings(scope):
    """Return names that make an imported helper ambiguous in this lexical scope."""
    bindings = set()

    class BindingVisitor(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                bindings.add(node.id)

        def visit_FunctionDef(self, node):
            bindings.add(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            bindings.add(node.name)

    for node in scope.body if isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)) else ():
        BindingVisitor().visit(node)
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for argument in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs):
            bindings.add(argument.arg)
        if scope.args.vararg:
            bindings.add(scope.args.vararg.arg)
        if scope.args.kwarg:
            bindings.add(scope.args.kwarg.arg)
    return bindings


def _direct_calls(scope):
    """Return calls in a scope without descending into nested lexical scopes."""
    calls = []

    class CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            calls.append(node)
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            return None

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node):
            return None

        def visit_Lambda(self, node):
            return None

    for node in scope.body:
        CallVisitor().visit(node)
    return calls


def _scopes(tree):
    """Yield the module and function scopes; imports are trusted only at module level."""
    scopes = []

    def collect(scope, inherited_bindings):
        bindings = inherited_bindings | _local_bindings(scope)
        scopes.append((scope, bindings))

        class NestedScopeVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                collect(node, bindings)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_ClassDef(self, node):
                self.generic_visit(node)

        for node in scope.body:
            NestedScopeVisitor().visit(node)

    collect(tree, set())
    return scopes


def test_job_catalogs_cover_route_producer_codes_and_match_icu_args():
    """Route-owned jobs.* codes cannot ship without EN/RU leaf messages."""
    codes = set(re.findall(r'"(jobs\.[\w.]+)"', ROUTES))
    en_leaves = dict(_leaves(EN))
    ru_leaves = dict(_leaves(RU))

    assert codes <= en_leaves.keys()
    assert codes <= ru_leaves.keys()
    for code in codes:
        assert _icu_args(en_leaves[code]) == _icu_args(ru_leaves[code]), code


def test_backend_descriptor_producers_always_supply_a_readable_fallback():
    """All direct descriptor producers must retain English text for non-UI clients."""
    assert _invalid_message_fallback_calls(ROOT / "src") == []


@pytest.mark.parametrize("module", ["health", "lint", "quality"])
def test_fallback_checker_recognizes_diagnostic_message_aliases(module):
    """Diagnostic producers retain their relative messages import aliases."""
    tree = ast.parse((ROOT / "src" / f"{module}.py").read_text())

    assert "diagnostic_message" in _imported_message_names(tree)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "def message(code, fallback=''):\n"
            "    return fallback\n"
            "\n"
            "message('jobs.example', fallback='  ')\n",
            [],
        ),
        (
            "from src.messages import message\n"
            "message('jobs.example', fallback='  ')\n",
            [(2, "blank fallback")],
        ),
        (
            "from src.messages import message as localized_message\n"
            "localized_message('jobs.example', fallback='  ')\n",
            [(2, "blank fallback")],
        ),
        (
            "from src.messages import message as localized_message\n"
            "localized_message('jobs.example', fallback='Ready')\n",
            [],
        ),
        (
            "from messages import message\n"
            "message('jobs.example', fallback='  ')\n",
            [(2, "blank fallback")],
        ),
        (
            "from other_module import message\n"
            "message('jobs.example', fallback='  ')\n",
            [],
        ),
        (
            "from src.messages import message\n"
            "\n"
            "def render(message):\n"
            "    return message('jobs.example', fallback='  ')\n",
            [],
        ),
        (
            "from src.messages import message\n"
            "\n"
            "def render():\n"
            "    def message(code, fallback=''):\n"
            "        return fallback\n"
            "    return message('jobs.example', fallback='  ')\n",
            [],
        ),
        (
            "from src.messages import message\n"
            "\n"
            "def render():\n"
            "    def message(code, fallback=''):\n"
            "        return fallback\n"
            "    def nested():\n"
            "        return message('jobs.example', fallback='  ')\n"
            "    return nested()\n",
            [],
        ),
        (
            "from .messages import message as diagnostic_message\n"
            "\n"
            "def diagnostic():\n"
            "    return diagnostic_message('jobs.example', fallback='  ')\n",
            [(4, "blank fallback")],
        ),
    ],
)
def test_fallback_checker_recognizes_only_unshadowed_messages_imports(tmp_path, source, expected):
    """Only calls bound to supported messages imports require a readable fallback."""
    producer = tmp_path / "producer.py"
    producer.write_text(source)

    assert _invalid_message_fallback_calls(tmp_path) == expected

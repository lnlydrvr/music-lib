"""Focused fixtures for scoped hardcoded-copy guardrails."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_copy", ROOT / "scripts" / "check_copy.py")
assert SPEC and SPEC.loader
check_copy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_copy)


def test_frontend_checker_flags_visible_literal_but_exempts_provider_data(tmp_path):
    source = tmp_path / "Screen.tsx"
    source.write_text('export function Screen() { return <><button title="Save">Save</button><span>YouTube Music</span></>; }')

    errors = check_copy.frontend_candidates(tmp_path)

    assert ["Screen.tsx:1: title literal 'Save'", "Screen.tsx:1: JSX text 'Save'"] == errors


def test_frontend_checker_inspects_only_bound_notification_calls(tmp_path):
    source = tmp_path / "Screen.tsx"
    source.write_text(
        'import { toast as notify } from "../lib/toast";\n'
        'notify("Saved");\n'
        'function globalNotices() {\n'
        '  confirm("Delete this track?");\n'
        '  alert("This should be flagged");\n'
        '  prompt("Name the playlist");\n'
        '}\n'
        'function unrelated(toast: (value: string) => void, confirm: (value: string) => boolean) {\n'
        '  toast("local toast");\n'
        '  confirm("local confirm");\n'
        '}\n'
        'function shadows() {\n'
        '  function alert(value: string) {}\n'
        '  alert("local alert");\n'
        '  const prompt = (value: string) => value;\n'
        '  prompt("local prompt");\n'
        '}\n'
        '// toast("comment only")\n'
        'const text = "confirm(\\\"string only\\\")";\n',
    )

    assert check_copy.frontend_candidates(tmp_path) == [
        "Screen.tsx:2: notification literal 'Saved'",
        "Screen.tsx:4: notification literal 'Delete this track?'",
        "Screen.tsx:5: notification literal 'This should be flagged'",
        "Screen.tsx:6: notification literal 'Name the playlist'",
    ]


def test_frontend_checker_resolves_destructured_and_catch_bindings(tmp_path):
    """A destructured or catch-bound notifier must not be mistaken for a browser global."""
    source = tmp_path / "Screen.tsx"
    source.write_text(
        "function parameterShadow({ alert, toast: notify }: { alert: (value: string) => void; toast: (value: string) => void }) {\n"
        "  alert('parameter alert');\n"
        "  notify('parameter toast');\n"
        "}\n"
        "function localShadow() {\n"
        "  const { confirm } = { confirm: (value: string) => true };\n"
        "  confirm('local confirm');\n"
        "}\n"
        "function catchShadow() {\n"
        "  try { throw { prompt: (value: string) => value }; } catch ({ prompt }) {\n"
        "    prompt('catch prompt');\n"
        "  }\n"
        "}\n"
        "alert('browser alert');\n",
    )

    assert check_copy.frontend_candidates(tmp_path) == [
        "Screen.tsx:14: notification literal 'browser alert'",
    ]


def test_frontend_checker_inspects_unshadowed_window_and_globalthis_dialogs(tmp_path):
    """Property dialogs count only when their browser-object binding is unshadowed."""
    source = tmp_path / "Screen.tsx"
    source.write_text(
        "window.alert('window alert');\n"
        "globalThis.confirm('global confirm');\n"
        "globalThis.prompt('global prompt');\n"
        "function shadows(window: { alert: (value: string) => void }, globalThis: { confirm: (value: string) => boolean }) {\n"
        "  window.alert('local window alert');\n"
        "  globalThis.confirm('local global confirm');\n"
        "}\n"
        "function localShadow() {\n"
        "  const globalThis = { prompt: (value: string) => value };\n"
        "  globalThis.prompt('local global prompt');\n"
        "}\n"
        "const object = { alert: (value: string) => value };\n"
        "object.alert('object alert');\n",
    )

    assert check_copy.frontend_candidates(tmp_path) == [
        "Screen.tsx:1: notification literal 'window alert'",
        "Screen.tsx:2: notification literal 'global confirm'",
        "Screen.tsx:3: notification literal 'global prompt'",
    ]


def test_frontend_checker_resolves_loop_destructuring_bindings(tmp_path):
    """Loop binding patterns shadow browser dialogs throughout the loop body."""
    source = tmp_path / "Screen.tsx"
    source.write_text(
        "for (let { alert } = { alert: (value: string) => value }; false; ) {\n"
        "  alert('object loop alert');\n"
        "}\n"
        "for (const [confirm] of [[(value: string) => true]]) {\n"
        "  confirm('array loop confirm');\n"
        "}\n"
        "for (const { alert } in { item: true }) {\n"
        "  alert('object in-loop alert');\n"
        "}\n"
        "alert('unshadowed loop global');\n",
    )

    assert check_copy.frontend_candidates(tmp_path) == [
        "Screen.tsx:10: notification literal 'unshadowed loop global'",
    ]


def test_frontend_checker_resolves_var_at_function_and_module_scope(tmp_path):
    """Unlike let/const, var declarations shadow through their function/module scope."""
    source = tmp_path / "Screen.tsx"
    source.write_text(
        "function functionScope() {\n"
        "  alert('function var before declaration');\n"
        "  if (true) {\n"
        "    var alert = (value: string) => value;\n"
        "    let confirm = (value: string) => true;\n"
        "    const prompt = (value: string) => value;\n"
        "    confirm('block let confirm');\n"
        "    prompt('block const prompt');\n"
        "  }\n"
        "  alert('function var after declaration');\n"
        "  confirm('function let outside block');\n"
        "  prompt('function const outside block');\n"
        "}\n"
        "if (true) { var alert = (value: string) => value; }\n"
        "alert('module var outside block');\n"
        "prompt('unshadowed module global');\n",
    )

    assert check_copy.frontend_candidates(tmp_path) == [
        "Screen.tsx:11: notification literal 'function let outside block'",
        "Screen.tsx:12: notification literal 'function const outside block'",
        "Screen.tsx:16: notification literal 'unshadowed module global'",
    ]


def test_backend_checker_only_inspects_imported_message_constructor_calls(tmp_path):
    producer = tmp_path / "producer.py"
    producer.write_text(
        "from src.messages import message\n"
        "from other import message as unrelated\n"
        "message('api.errors.ok', fallback='OK')\n"
        "message('Readable text', fallback='Readable text')\n"
        "unrelated('Readable text')\n"
    )

    assert check_copy.backend_candidates(tmp_path) == ["producer.py:4: message code must be a dotted literal key"]


def test_backend_checker_respects_import_aliases_and_lexical_shadowing(tmp_path):
    producer = tmp_path / "producer.py"
    producer.write_text(
        "from src.messages import message as descriptor\n"
        "descriptor('api.errors.ok', fallback='OK')\n"
        "descriptor('Readable text', fallback='Readable text')\n"
        "def parameter_shadow(descriptor):\n"
        "    descriptor('Readable text')\n"
        "def local_shadow():\n"
        "    def descriptor(value): pass\n"
        "    descriptor('Readable text')\n"
        "def nested_import():\n"
        "    from other import message as descriptor\n"
        "    descriptor('Readable text')\n"
    )

    assert check_copy.backend_candidates(tmp_path) == ["producer.py:3: message code must be a dotted literal key"]

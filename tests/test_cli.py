"""CLI 行为测试。"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import loam.__main__ as cli


class _DummyService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def build_context(self, query: str, learn: bool = False):
        self.calls.append((query, bool(learn)))
        return {"text": "ctx", "context": {"query": query, "learn": learn}}

    def close(self) -> None:
        return


def _run_context(argv: list[str]):
    svc = _DummyService()
    orig = cli._service_from_args
    cli._service_from_args = lambda args, auto_start_grower: svc
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            rc = cli.main(argv)
    finally:
        cli._service_from_args = orig
    return rc, out.getvalue(), svc


def test_context_default_no_learn():
    rc, _, svc = _run_context(["context", "明天开会", "--text-only"])
    assert rc == 0
    assert svc.calls == [("明天开会", False)]


def test_context_learn_opt_in():
    rc, _, svc = _run_context(["context", "明天开会", "--learn", "--text-only"])
    assert rc == 0
    assert svc.calls == [("明天开会", True)]


def test_context_no_learn_overrides_learn():
    rc, _, svc = _run_context(["context", "明天开会", "--learn", "--no-learn", "--text-only"])
    assert rc == 0
    assert svc.calls == [("明天开会", False)]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    raise SystemExit(1 if failed else 0)

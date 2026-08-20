"""loam 命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import __version__
from .mind.llm import load_brain, write_secrets_template
from .server import LoamService, ServiceConfig, build_server


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.cmd == "init-secrets":
        path = write_secrets_template(args.secrets_home)
        print(path)
        return 0

    if args.cmd == "stats":
        svc = _service_from_args(args, auto_start_grower=False)
        try:
            _dump(svc.stats())
        finally:
            svc.close()
        return 0

    if args.cmd == "digest-once":
        svc = _service_from_args(args, auto_start_grower=False)
        try:
            _dump(svc.digest_once(limit=args.limit))
        finally:
            svc.close()
        return 0

    if args.cmd == "context":
        svc = _service_from_args(args, auto_start_grower=False)
        try:
            # 默认不学习；显式 --learn 才会让 recall 改写网络。
            learn = bool(getattr(args, "learn", False))
            if bool(getattr(args, "no_learn", False)):
                learn = False
            out = svc.build_context(args.query, learn=learn)
            if args.text_only:
                print(out["text"])
            else:
                _dump(out)
        finally:
            svc.close()
        return 0

    # 默认 run
    no_grower = bool(getattr(args, "no_grower", False))
    host_arg = str(getattr(args, "host", "127.0.0.1"))
    port_arg = int(getattr(args, "port", 8765))

    svc = _service_from_args(args, auto_start_grower=not no_grower)
    httpd = build_server(svc, host=host_arg, port=port_arg)
    host, port = httpd.server_address
    print(f"loam/{__version__} serving on http://{host}:{port} character={svc.character}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        svc.close()
    return 0


def _service_from_args(args: argparse.Namespace, auto_start_grower: bool) -> LoamService:
    cfg = ServiceConfig(
        character=str(getattr(args, "character", "default")),
        home=str(getattr(args, "home", "~/.loam/characters")),
        default_session=str(getattr(args, "session", "default")),
        batch_turns=int(getattr(args, "batch_turns", 20)),
        grow_interval=float(getattr(args, "grow_interval", 60.0)),
        idle_seconds=float(getattr(args, "idle_seconds", 900.0)),
        audit_every=int(getattr(args, "audit_every", 50)),
        auto_start_grower=auto_start_grower,
        api_key=str(getattr(args, "api_key", os.environ.get("LOAM_API_KEY", ""))),
    )
    brain = load_brain(home=str(getattr(args, "secrets_home", "~/.loam")))
    return LoamService(cfg, brain=brain)


def _dump(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m loam", description="loam local service")
    p.add_argument("--character", default="default", help="角色 id")
    p.add_argument("--home", default="~/.loam/characters", help="角色数据目录")
    p.add_argument("--session", default="default", help="默认会话名")
    p.add_argument("--secrets-home", default="~/.loam", help="secrets.json 所在目录")

    sub = p.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="启动 HTTP 服务（默认）")
    _common_run_flags(run)

    init_secrets = sub.add_parser("init-secrets", help="生成 secrets.json 模板")
    init_secrets.add_argument("--secrets-home", default="~/.loam")

    stats = sub.add_parser("stats", help="打印当前状态")
    _common_service_flags(stats)

    d1 = sub.add_parser("digest-once", help="手动消化一批")
    _common_service_flags(d1)
    d1.add_argument("--limit", type=int, default=None)

    ctx = sub.add_parser("context", help="构造一次上下文")
    _common_service_flags(ctx)
    ctx.add_argument("query")
    ctx.add_argument("--learn", action="store_true", help="回忆时学习（默认关闭）")
    # 兼容旧参数：默认本来就不学习，传了也只是显式声明。
    ctx.add_argument("--no-learn", action="store_true", help="显式关闭学习（默认即关闭）")
    ctx.add_argument("--text-only", action="store_true", help="只输出拼好的上下文文本")

    return p


def _common_service_flags(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--character", default="default")
    sp.add_argument("--home", default="~/.loam/characters")
    sp.add_argument("--session", default="default")
    sp.add_argument("--secrets-home", default="~/.loam")
    sp.add_argument("--api-key", default=os.environ.get("LOAM_API_KEY", ""))
    sp.add_argument("--batch-turns", type=int, default=20)
    sp.add_argument("--grow-interval", type=float, default=60.0)
    sp.add_argument("--idle-seconds", type=float, default=900.0)
    sp.add_argument("--audit-every", type=int, default=50)


def _common_run_flags(sp: argparse.ArgumentParser) -> None:
    _common_service_flags(sp)
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--no-grower", action="store_true")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
"""Command line: python -m yaqiz serve | seed | voices"""
from __future__ import annotations

import argparse
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Arabic output on Windows consoles
    ap = argparse.ArgumentParser(prog="python -m yaqiz", description="Yaqiz construction-site safety service")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("serve", help="run the API, camera workers and dashboard")
    sp.add_argument("--host")
    sp.add_argument("--port", type=int)
    sp.add_argument("--no-workers", action="store_true", help="API only, cameras off")
    sd = sub.add_parser("seed", help="create the demo site (plan, zones, demo cameras)")
    sd.add_argument("--reset", action="store_true", help="wipe zones, cameras, events and settings first")
    sv = sub.add_parser("voices", help="generate the multilingual voice clips (needs internet once)")
    sv.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from .config import get_settings

    settings = get_settings()

    if args.cmd == "serve":
        import uvicorn

        from .api.app import create_app
        from .seed import seed
        from .store import Store

        update = {k: v for k, v in (("host", args.host), ("port", args.port)) if v}
        if args.no_workers:
            update["start_workers"] = False
        settings = settings.model_copy(update=update)
        store = Store(settings.db_path)
        if not store.list_cameras() and not store.list_zones():
            logging.getLogger("yaqiz").info("empty site: creating the demo site")
            seed(store, settings)
        uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="info")
        return 0

    if args.cmd == "seed":
        from .seed import seed
        from .store import Store

        print(json.dumps(seed(Store(settings.db_path), settings, reset=args.reset), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "voices":
        from .voice import generate

        results = generate(settings.voices_dir, overwrite=args.overwrite)
        for name, ok, info in results:
            print(f"{'OK ' if ok else 'ERR'} {name}: {info}")
        return 0 if all(ok for _, ok, _ in results) else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

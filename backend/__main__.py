from __future__ import annotations

import argparse
import asyncio

from backend.ws_server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="BertFlow WebSocket Backend")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on file changes")
    args = parser.parse_args()

    if args.reload:
        try:
            import watchfiles
        except ImportError:
            print("--reload requires watchfiles: pip install watchfiles")
            return


        watchfiles.run_process(
            __file__.rsplit("/", 1)[0],
            target=run_server,
            args=(args.host, args.port),
        )
        return

    asyncio.run(run_server(args.host, args.port))


if __name__ == "__main__":
    main()

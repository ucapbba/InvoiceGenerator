"""Run the app with Waitress: python -m invoicegen

Listens on 127.0.0.1 only, so it's reachable from this machine (and a
Cloudflare Tunnel running on it) but not directly from the network.
"""

import os

from waitress import serve

from . import create_app


def main():
    host = os.environ.get("INVOICEGEN_HOST", "127.0.0.1")
    port = int(os.environ.get("INVOICEGEN_PORT", "8000"))
    print(f"Invoice Generator on http://{host}:{port}", flush=True)
    serve(create_app(), host=host, port=port, threads=4)


if __name__ == "__main__":
    main()

from __future__ import annotations

"""
- a parser is a piece of software that takes input written in some format,
interprets its structure, and turns it into something a program can work with.

- imagine you'd want to work with the CLI and you need to control operations through
commands in their terminal, like:
python -m tessel.cli serve --host 0.0.0.0 --port 9000

- The parser is the component that interprets those arguments and organizes them 
into a structured Python object.
"""

import argparse
import sys

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='tessel',
                                description='Multi-tenant telemetry backend for soil sensors')
    sub = p.add_subparsers(dest='command', required=True)
    serve = sub.add_parser('serve', help='run the HTTP API')
    serve.add_argument("--host", default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    serve.set_defaults(handler="tessel.api")
    return p

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

    # serve
    serve = sub.add_parser('serve', help='run the HTTP API')
    serve.add_argument("--host", default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    serve.set_defaults(handler="tessel.api")

    # worker
    worker = sub.add_parser('worker', help='claim jobs: alert rules, webhook deliveries, exports')
    worker.add_argument('--concurrency', type=int, default=4)
    worker.set_defaults(handler='tessel.worker')

    # simulate (sim)
    sim = sub.add_parser('simulate', help='replay real Open-Meteo history as a fleet of probes')
    sim.add_argument('sites_csv')
    sim.add_argument('--devices-per-site', type=int, default=5)
    sim.add_argument('--lose-responses', type=float, default=0.05)
    sim.set_defaults(handler='tessel.simulate')

    # migrate
    migrate = sub.add_parser('migrate', help='apply SQL migrations')
    migrate.set_defaults(handler='tessel.admin')

    # load
    load = sub.add_parser('loadtest', help='measure throughput and p99 latency')
    load.add_argument('--requests', type=int, default=10_000)
    load.add_argument('--concurrency', type=int, default=50)
    load.set_defaults(handler='tessel.load')

    return p

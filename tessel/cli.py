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
    """
    - p -> the object that will read the command line
    """
    sub = p.add_subparsers(dest='command', required=True)

    """
    - sub -> the factory used to create one parser per subcommand
    - dest='command' -> stores the chosen subcommand's name in 'args.command'
    - required=True -> running just 'tessel' will be an error
    """

    """
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args(["--port", "9000"])
    print(args.port)  # 9000, already an int
    """

    """
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("hello")
    a.set_defaults(handler="say hi")
    b = sub.add_parser("bye")
    b.set_defaults(handler="say goodbye")
    print(p.parse_args(["hello"]))  # Namespace(command='hello', handler='say hi')
    print(p.parse_args(["bye"]))    # Namespace(command='bye', handler='say goodbye')
    """

    # serve - run the HTTP API (could be anything; 'serve', 'run', 'api', etc.)
    serve = sub.add_parser('serve', help='run the HTTP API')
    serve.add_argument("--host", default='127.0.0.1')
    serve.add_argument('--port', type=int, default=8000)
    serve.set_defaults(handler="tessel.api")

    # worker - the background process that will run jobs from the queue
    worker = sub.add_parser('worker', help='claim jobs: alert rules, webhook deliveries, exports')
    worker.add_argument('--concurrency', type=int, default=4)
    worker.set_defaults(handler='tessel.worker')

    # simulate (sim) - the fake fleet of soil probes
    sim = sub.add_parser('simulate', help='replay real Open-Meteo history as a fleet of probes')
    sim.add_argument('sites_csv')
    sim.add_argument('--devices-per-site', type=int, default=5)
    sim.add_argument('--lose-responses', type=float, default=0.05)
    sim.set_defaults(handler='tessel.simulate')

    # migrate - only records its handler
    migrate = sub.add_parser('migrate', help='apply SQL migrations')
    migrate.set_defaults(handler='tessel.admin')

    # load - measures throughput and latency
    load = sub.add_parser('loadtest', help='measure throughput and p99 latency')
    load.add_argument('--requests', type=int, default=10_000)
    load.add_argument('--concurrency', type=int, default=50)
    load.set_defaults(handler='tessel.load')

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"would run {args.handler} with {vars(args)}")
    return 0



if __name__ == "__main__":
    sys.exit(main())
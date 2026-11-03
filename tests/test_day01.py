from tessel.cli import build_parser


def test_every_process_is_a_subcommand():
    p = build_parser()
    assert p.parse_args(["serve"]).handler == "tessel.api"
    assert p.parse_args(["serve", "--port", "9001"]).port == 9001
    assert p.parse_args(["worker"]).concurrency == 4
    sim = p.parse_args(["simulate", "data/sites.csv", "--lose-responses", "0.2"])
    assert sim.handler == "tessel.simulate" and sim.lose_responses == 0.2 and sim.devices_per_site == 5

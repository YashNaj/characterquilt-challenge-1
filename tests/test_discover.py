from cq.client import Result
from cq.discover import summarize, CANDIDATES


def test_summarize_shows_keys_and_minutes():
    r = Result(200, {"Content-Type": "application/json; charset=utf-8"},
               '{"briefs": [], "run_minutes_remaining": 118.2}', 0.1, 1)
    line = summarize("/s1/briefs", r)
    assert line.startswith("200 application/json")
    assert "keys[briefs,run_minutes_remaining]" in line and "118.2m" in line


def test_summarize_survives_transport_error():
    r = Result(0, {}, "", 0.1, 1, error="ConnectionError('x')")
    assert "ERR" in summarize("/s1", r)


def test_candidate_list_is_modest():
    assert 10 < len(CANDIDATES) < 50

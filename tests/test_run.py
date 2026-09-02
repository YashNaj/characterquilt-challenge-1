from cq.client import Result
from cq.run import classify_refusal, extract_reason


def res(status, text, error=None):
    return Result(status, {}, text, 0.1, 1, error=error)


def test_transport_failures_are_transient():
    assert classify_refusal(res(503, "")) == "transient"
    assert classify_refusal(res(429, "")) == "transient"
    assert classify_refusal(res(0, "", error="ConnectionError")) == "transient"


def test_wording_drives_classification():
    assert classify_refusal(res(409, '{"error":"budget window not open yet, try again later"}')) == "transient"
    assert classify_refusal(res(422, '{"error":"region prohibited by policy"}')) == "blocked"
    assert classify_refusal(res(400, '{"error":"???"}')) == "unknown"


def test_extract_reason_prefers_structured_fields():
    assert extract_reason(res(422, '{"error":"too spicy","code":"X"}')) == "too spicy"
    assert extract_reason(res(422, "plain text body")) == "plain text body"
    assert extract_reason(res(0, "", error="boom")) == "boom"

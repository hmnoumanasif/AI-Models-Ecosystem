from unittest.mock import Mock, patch

import pytest
import requests

from src.datasets import BY_ID
from src.extraction import api_client
from src.extraction.api_client import ExtractionError, MissingKeyError, fetch_dataset, fetch_json

IMAGE = BY_ID["image_t2i"]          # needs a key
CATALOG = BY_ID["llm_catalog"]      # key is optional
BENCHMARKS = BY_ID["llm_benchmarks"]  # needs a key and has pages


def fake_response(status=200, payload=None, bad_json=False):
    response = Mock(status_code=status)
    if bad_json:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = payload if payload is not None else {"data": [{"id": "a/b", "name": "M"}]}
    return response


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("src.extraction.api_client.time.sleep") as sleep:
        yield sleep


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", "secret-test-key")


def test_success_sends_timeout_and_key_header(key):
    with patch("src.extraction.api_client.requests.get", return_value=fake_response()) as get:
        assert fetch_dataset(IMAGE)["data"][0]["id"] == "a/b"
    get.assert_called_once()
    assert get.call_args.kwargs["timeout"] > 0
    assert get.call_args.kwargs["headers"]["x-api-key"] == "secret-test-key"


def test_missing_required_key_stops_before_any_request():
    with patch("src.extraction.api_client.requests.get") as get:
        with pytest.raises(MissingKeyError, match="ARTIFICIAL_ANALYSIS_API_KEY"):
            fetch_dataset(IMAGE)
    get.assert_not_called()


def test_blank_key_counts_as_missing(monkeypatch):
    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", "   ")
    with pytest.raises(MissingKeyError):
        fetch_dataset(IMAGE)


def test_optional_key_is_sent_only_when_configured(monkeypatch):
    with patch("src.extraction.api_client.requests.get", return_value=fake_response()) as get:
        fetch_dataset(CATALOG)
    assert "Authorization" not in get.call_args.kwargs["headers"]
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
    with patch("src.extraction.api_client.requests.get", return_value=fake_response()) as get:
        fetch_dataset(CATALOG)
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer or-key"


def test_retries_temporary_error_then_succeeds(no_sleep):
    responses = [fake_response(503), fake_response(429), fake_response()]
    with patch("src.extraction.api_client.requests.get", side_effect=responses) as get:
        assert fetch_json("http://x", {})["data"]
    assert get.call_count == 3
    assert [c.args[0] for c in no_sleep.call_args_list] == [1, 2]   # exponential backoff


def test_network_errors_give_up_after_max_attempts():
    with patch("src.extraction.api_client.requests.get", side_effect=requests.ConnectionError("down")) as get:
        with pytest.raises(ExtractionError, match="after 3 attempts"):
            fetch_json("http://x", {})
    assert get.call_count == 3


def test_timeout_is_retried():
    with patch("src.extraction.api_client.requests.get", side_effect=[requests.Timeout(), fake_response()]) as get:
        fetch_json("http://x", {})
    assert get.call_count == 2


def test_permanent_error_is_not_retried():
    with patch("src.extraction.api_client.requests.get", return_value=fake_response(404)) as get:
        with pytest.raises(ExtractionError, match="404"):
            fetch_json("http://x", {})
    assert get.call_count == 1


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_is_a_clear_permanent_error(status):
    with patch("src.extraction.api_client.requests.get", return_value=fake_response(status)) as get:
        with pytest.raises(ExtractionError, match="key was rejected"):
            fetch_json("http://x", {})
    assert get.call_count == 1


def test_malformed_json():
    with patch("src.extraction.api_client.requests.get", return_value=fake_response(bad_json=True)):
        with pytest.raises(ExtractionError, match="JSON"):
            fetch_json("http://x", {})


@pytest.mark.parametrize("payload", [[], {"data": "nope"}, {"items": []}, "text"])
def test_unexpected_structure(key, payload):
    with patch("src.extraction.api_client.requests.get", return_value=fake_response(payload=payload)):
        with pytest.raises(ExtractionError, match="Unexpected"):
            fetch_dataset(IMAGE)


def test_paged_api_is_read_page_by_page(key):
    pages = [fake_response(payload={"data": [{"id": "1"}], "pagination": {"has_more": True}}),
             fake_response(payload={"data": [{"id": "2"}], "pagination": {"has_more": False}})]
    with patch("src.extraction.api_client.requests.get", side_effect=pages) as get:
        payload = fetch_dataset(BENCHMARKS)
    assert [r["id"] for r in payload["data"]] == ["1", "2"]
    assert [c.kwargs["params"]["page"] for c in get.call_args_list] == [1, 2]


def test_paging_stops_at_the_safety_limit(key):
    endless = fake_response(payload={"data": [{"id": "x"}], "pagination": {"has_more": True}})
    with patch("src.extraction.api_client.MAX_PAGES", 3), \
         patch("src.extraction.api_client.requests.get", return_value=endless) as get:
        assert len(fetch_dataset(BENCHMARKS)["data"]) == 3
    assert get.call_count == 3


def test_the_api_key_never_appears_in_error_messages(key):
    with patch("src.extraction.api_client.requests.get", return_value=fake_response(401)):
        with pytest.raises(ExtractionError) as error:
            fetch_dataset(IMAGE)
    assert "secret-test-key" not in str(error.value)


# ---- saved snapshots
@pytest.fixture
def folders(tmp_path, monkeypatch):
    raw, sample = tmp_path / "raw", tmp_path / "sample"
    raw.mkdir(), sample.mkdir()
    monkeypatch.setattr(api_client, "RAW_DIR", raw)
    monkeypatch.setattr(api_client, "SAMPLE_DIR", sample)
    return raw, sample


def test_saved_snapshot_prefers_real_data_then_sample(folders):
    raw, sample = folders
    (sample / "image_t2i.json").write_text('{"data": []}')
    assert api_client.load_saved_snapshot(IMAGE)[1]["source"] == "synthetic_sample"
    (raw / "image_t2i").mkdir()
    (raw / "image_t2i" / "20260101T000000Z.json").write_text('{"data": []}')
    (raw / "image_t2i" / "20260202T101010Z.json").write_text('{"data": []}')
    info = api_client.load_saved_snapshot(IMAGE)[1]
    assert info["source"] == "saved_snapshot" and info["source_detail"] == "20260202T101010Z.json"
    assert info["data_time"] == "2026-02-02 10:10:10"


def test_snapshots_of_different_datasets_do_not_mix(folders):
    raw, sample = folders
    (raw / "video_t2v").mkdir()
    (raw / "video_t2v" / "20260101T000000Z.json").write_text('{"data": []}')
    (sample / "image_t2i.json").write_text('{"data": []}')
    assert api_client.load_saved_snapshot(IMAGE)[1]["source"] == "synthetic_sample"


def test_no_snapshot_available(folders):
    with pytest.raises(ExtractionError, match="No saved snapshot"):
        api_client.load_saved_snapshot(IMAGE)


def test_corrupt_snapshot_file(folders):
    raw, _ = folders
    (raw / "image_t2i").mkdir()
    (raw / "image_t2i" / "20260101T000000Z.json").write_text("{broken")
    with pytest.raises(ExtractionError, match="Cannot read"):
        api_client.load_saved_snapshot(IMAGE)


def rate_limited(seconds):
    response = fake_response(429)
    response.headers = {"Retry-After": str(seconds)}
    return response


def test_daily_limit_stops_at_once_with_a_helpful_message(no_sleep):
    """AA's free tier allows 100 requests per day. Retrying would only waste them."""
    with patch("src.extraction.api_client.requests.get", return_value=rate_limited(7200)) as get:
        with pytest.raises(ExtractionError, match="120 minutes"):
            fetch_json("http://x", {})
    assert get.call_count == 1
    no_sleep.assert_not_called()


def test_short_retry_after_is_respected(no_sleep):
    with patch("src.extraction.api_client.requests.get", side_effect=[rate_limited(5), fake_response()]) as get:
        assert fetch_json("http://x", {})["data"]
    assert get.call_count == 2
    assert [c.args[0] for c in no_sleep.call_args_list] == [5.0]

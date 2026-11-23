import pytest

from src.validation.schemas import (
    ArenaRecord,
    LLMBenchmarkRecord,
    SpeechToSpeechRecord,
    SpeechToTextRecord,
    validate_records,
)
from tests.conftest import make_arena, make_record


def test_valid_record():
    valid, rejected = validate_records([make_record()])
    assert len(valid) == 1 and rejected == []


def test_text_price_becomes_float():
    valid, _ = validate_records([make_record()])
    assert valid[0]["pricing"]["prompt"] == 0.000001


def test_missing_id_is_rejected_with_reason():
    valid, rejected = validate_records([{"name": "Model"}])
    assert valid == [] and "id" in rejected[0]["reason"]


def test_negative_or_zero_context_rejected():
    for bad in (-2, 0):
        valid, rejected = validate_records([make_record(context_length=bad)])
        assert valid == [] and len(rejected) == 1


def test_bad_prices_rejected():
    for bad in ("not-a-price", "nan", "inf", [1]):
        valid, rejected = validate_records([make_record(pricing={"prompt": bad})])
        assert valid == [] and len(rejected) == 1, bad


def test_one_bad_record_does_not_stop_the_others():
    records = [make_record("a/1", "One"), {"id": "", "name": "Bad"}, "not a dict", make_record("a/2", "Two")]
    valid, rejected = validate_records(records)
    assert len(valid) == 2 and len(rejected) == 2


def test_null_optional_fields_are_fine():
    valid, rejected = validate_records([{"id": "a/b", "name": "X", "pricing": None,
                                         "architecture": None, "context_length": None}])
    assert len(valid) == 1 and rejected == []


def test_wrong_types_rejected():
    valid, rejected = validate_records([make_record(architecture={"input_modalities": "text"})])
    assert valid == [] and len(rejected) == 1


def test_empty_input():
    assert validate_records([]) == ([], [])


# ---- Artificial Analysis schemas
def test_arena_record_valid():
    valid, rejected = validate_records([make_arena()], ArenaRecord)
    assert len(valid) == 1 and valid[0]["elo"] == 1200 and rejected == []


@pytest.mark.parametrize("bad", ["n/a", "nan", "inf", None, [1]])
def test_arena_elo_must_be_a_real_number(bad):
    valid, rejected = validate_records([make_arena(elo=bad)], ArenaRecord)
    assert valid == [] and len(rejected) == 1


def test_arena_confidence_interval_rules():
    assert validate_records([make_arena(ci=None)], ArenaRecord)[1] == []        # may be missing
    assert len(validate_records([make_arena(ci=-5)], ArenaRecord)[1]) == 1      # but not negative


def test_arena_creator_may_be_missing():
    record = {"id": "x", "name": "X", "elo": 1000}
    assert validate_records([record], ArenaRecord)[1] == []


def test_benchmark_record_accepts_missing_blocks_and_rejects_wrong_types():
    assert validate_records([{"id": "a", "name": "A"}], LLMBenchmarkRecord)[1] == []
    assert len(validate_records([{"id": "a", "name": "A", "evaluations": "oops"}], LLMBenchmarkRecord)[1]) == 1


def test_speech_schemas():
    assert validate_records([{"id": "a", "name": "A", "bba_score": 0.5, "fdb_score": None}],
                            SpeechToSpeechRecord)[1] == []
    assert len(validate_records([{"id": "a", "name": "A", "bba_score": "high"}], SpeechToSpeechRecord)[1]) == 1
    assert len(validate_records([{"id": "a", "name": "A", "aa_wer_index": "nan"}], SpeechToTextRecord)[1]) == 1

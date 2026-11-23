import pandas as pd

from src.transformation.transform import (
    get_provider,
    number,
    pricing_status,
    transform_arena,
    transform_llm_benchmarks,
    transform_records,
    transform_speech_to_speech,
    transform_speech_to_text,
)
from src.validation.schemas import validate_records
from tests.conftest import make_arena, make_record


def run(records):
    valid, _ = validate_records(records)
    return transform_records(valid)


def test_price_conversion_provider_and_multimodal():
    df = run([make_record("openai/m", architecture={"input_modalities": ["text", "image"],
                                                    "output_modalities": ["text"]})])
    assert df.loc[0, "provider"] == "openai"
    assert df.loc[0, "input_price_per_million"] == 1.0
    assert df.loc[0, "output_price_per_million"] == 2.0
    assert df.loc[0, "is_multimodal"] and df.loc[0, "accepts_image"]


def test_pricing_status_values():
    assert pricing_status(None, None) == "missing"
    assert pricing_status(0.0, 0.0) == "free"
    assert pricing_status(0.0, 1.0) == "paid"
    assert pricing_status(1.0, None) == "partial"


def test_missing_price_is_not_free(df):
    status = df.set_index("model_id")["pricing_status"]
    assert status["meta/e"] == "missing"
    assert status["google/c"] == "free"
    assert status["openai/a"] == "paid"


def test_negative_price_becomes_missing_and_is_flagged(df):
    row = df.set_index("model_id").loc["google/d"]
    assert pd.isna(row["input_price_per_million"]) and row["price_was_negative"]


def test_provider_without_slash():
    assert get_provider("justaname") == "unknown"
    assert get_provider("OpenAI/x") == "openai"


def test_duplicates_removed():
    df = run([make_record("a/x", "First"), make_record("a/x", "Second")])
    assert len(df) == 1 and df.loc[0, "model_name"] == "First"


def test_empty_and_single_record():
    assert run([]).empty
    assert len(run([make_record()])) == 1


def test_missing_architecture_and_context():
    df = run([{"id": "a/b", "name": "X"}])
    assert pd.isna(df.loc[0, "context_length"]) and not df.loc[0, "is_multimodal"]
    assert df.loc[0, "pricing_status"] == "missing"


def test_extremely_large_values():
    df = run([make_record(context_length=10**12, pricing={"prompt": "1000", "completion": "2000"})])
    assert df.loc[0, "context_length"] == 10**12
    assert df.loc[0, "input_price_per_million"] == 1_000_000_000


def test_result_is_sorted_and_deterministic():
    records = [make_record("b/2", "B"), make_record("a/1", "A")]
    assert run(records)["model_id"].tolist() == ["a/1", "b/2"] == run(records[::-1])["model_id"].tolist()


# ---- Artificial Analysis transforms
def test_number_helper():
    assert number("3.5") == 3.5 and number(2) == 2.0
    assert number(None) is None and number(True) is None and number("abc") is None
    assert number(float("nan")) is None and number(float("inf")) is None


def test_arena_sorted_ranked_and_interval():
    df = transform_arena([make_arena("a", "A", elo=1100, ci=10), make_arena("b", "B", elo=1200, ci=20),
                          make_arena("c", "C", elo=1200, ci=5)])
    assert df["model_id"].iloc[0] in {"b", "c"}
    assert df["rank"].tolist() == [1, 1, 3]                 # ties share a rank
    row = df.set_index("model_id").loc["b"]
    assert row["ci_low"] == 1180 and row["ci_high"] == 1220


def test_arena_duplicates_missing_creator_and_empty():
    df = transform_arena([make_arena("a"), make_arena("a", name="Again"), {"id": "z", "name": "Z", "elo": 900}])
    assert len(df) == 2 and df.set_index("model_id").loc["z", "creator"] == "unknown"
    assert transform_arena([]).empty and list(transform_arena([]).columns)[-1] == "rank"


def test_arena_without_confidence_interval():
    df = transform_arena([make_arena(ci=None)])
    assert pd.isna(df.loc[0, "ci_low"])


def test_llm_benchmarks_extracts_nested_fields_and_prefers_performance_v3():
    record = {"id": "x", "name": "X", "model_creator": {"name": "Lab"}, "release_date": "2026-08-18",
              "evaluations": {"artificial_analysis_intelligence_index": 31.7},
              "artificial_analysis_intelligence_index_cost": {"cost_per_task": {"total_cost": 5.0}},
              "pricing": {"price_1m_input_tokens": 1.4, "price_1m_output_tokens": 4.4},
              "performance": {"median_output_tokens_per_second": 80.0},
              "performance_v3": {"mean_output_tokens_per_second": 62.0, "mean_time_to_first_token_seconds": 3.4}}
    row = transform_llm_benchmarks([record]).iloc[0]
    assert row["intelligence_index"] == 31.7 and row["cost_per_task_usd"] == 5.0
    assert row["output_tokens_per_second"] == 62.0 and row["pricing_status"] == "paid"
    assert row["release_date"].year == 2026


def test_llm_benchmarks_falls_back_to_old_performance_and_handles_missing_blocks():
    old = {"id": "x", "name": "X", "performance": {"median_output_tokens_per_second": 80.0}}
    assert transform_llm_benchmarks([old]).loc[0, "output_tokens_per_second"] == 80.0
    row = transform_llm_benchmarks([{"id": "y", "name": "Y"}]).iloc[0]
    assert pd.isna(row["intelligence_index"]) and row["pricing_status"] == "missing"


def test_benchmarks_sorted_best_first_with_missing_last():
    records = [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "evaluations": {
        "artificial_analysis_intelligence_index": 10}}, {"id": "c", "name": "C", "evaluations": {
        "artificial_analysis_intelligence_index": 50}}]
    assert transform_llm_benchmarks(records)["model_id"].tolist() == ["c", "b", "a"]


def test_speech_transforms_sort_direction():
    stt = transform_speech_to_text([{"id": "a", "name": "A", "aa_wer_index": 0.09},
                                    {"id": "b", "name": "B", "aa_wer_index": 0.03}])
    assert stt["model_id"].tolist() == ["b", "a"]                     # lower error rate first
    s2s = transform_speech_to_speech([{"id": "a", "name": "A", "bba_score": 0.4},
                                      {"id": "b", "name": "B", "bba_score": 0.9, "fdb_score": None}])
    assert s2s["model_id"].tolist() == ["b", "a"] and pd.isna(s2s.loc[0, "fdb_score"])

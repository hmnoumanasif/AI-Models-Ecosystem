import pytest

from src import pipeline
from src.datasets import BY_ID
from src.extraction.api_client import load_saved_snapshot
from src.transformation.transform import transform_records
from src.validation.schemas import validate_records


def build_df(records):
    """Validate then transform OpenRouter records, exactly like the pipeline does."""
    valid, _ = validate_records(records)
    return transform_records(valid)


def make_record(model_id="openai/model-a", name="Model A", **extra):
    record = {"id": model_id, "name": name, "context_length": 128000,
              "pricing": {"prompt": "0.000001", "completion": "0.000002"},
              "architecture": {"modality": "text->text", "input_modalities": ["text"],
                               "output_modalities": ["text"]}}
    record.update(extra)
    return record


def make_arena(model_id="m1", name="Model 1", creator="Lab A", elo=1200, ci=10):
    """One record shaped like the Artificial Analysis arena API."""
    return {"id": model_id, "name": name, "slug": model_id, "model_creator": {"id": "c", "name": creator},
            "elo": elo, "ci_95": ci}


def load_df(dataset_id):
    """The cleaned table of one dataset, built from the saved/sample file (no network)."""
    dataset = BY_ID[dataset_id]
    payload, _ = load_saved_snapshot(dataset)
    valid, _ = validate_records(payload["data"], dataset.schema)
    return dataset.transform(valid)


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Every test gets its own empty database and its own output folders,
    and never sees a real API key from a .env file."""
    monkeypatch.setenv("AI_MODELS_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.delenv("ARTIFICIAL_ANALYSIS_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(pipeline, "RAW_DIR", tmp_path / "out_raw")
    monkeypatch.setattr(pipeline, "PROCESSED_DIR", tmp_path / "out_processed")


@pytest.fixture
def df():
    """A small OpenRouter table with every pricing status and several providers."""
    records = [
        make_record("openai/a", "A"),
        make_record("openai/b", "B", context_length=1000000,
                    pricing={"prompt": "0.00001", "completion": "0.00003"},
                    architecture={"input_modalities": ["text", "image"], "output_modalities": ["text"]}),
        make_record("google/c", "C", pricing={"prompt": "0", "completion": "0"}),
        make_record("google/d", "D", pricing={"prompt": "-1", "completion": "-1"}, context_length=None),
        make_record("meta/e", "E", pricing=None),
        make_record("meta/f", "F", pricing={"prompt": "0.0000005", "completion": "0.0000015"},
                    context_length=32000),
        make_record("meta/g", "G", pricing={"prompt": "0.000002", "completion": "0.000004"},
                    context_length=8000),
    ]
    return build_df(records)

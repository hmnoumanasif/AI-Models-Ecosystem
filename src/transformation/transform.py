"""TRANSFORM step: turn validated records into one clean pandas table."""
import math

import pandas as pd

# Prices come as USD per token. We show USD per 1 million tokens.
TOKENS_PER_UNIT = 1_000_000

COLUMNS = [
    "model_id", "model_name", "provider", "description", "created_at",
    "context_length", "input_price_per_million", "output_price_per_million",
    "pricing_status", "price_was_negative", "modality", "input_modalities",
    "output_modalities", "is_multimodal", "accepts_image", "accepts_audio",
    "accepts_video", "accepts_file",
]


def get_provider(model_id):
    """'openai/gpt-x' -> 'openai'. IDs without '/' become 'unknown'."""
    if "/" in model_id:
        return model_id.split("/", 1)[0].strip().lower() or "unknown"
    return "unknown"


def per_million(price):
    """Convert USD/token to USD/1M tokens. Negative prices are not real prices
    (the API uses -1 for 'variable price'), so they become missing (None)."""
    if price is None or price < 0:
        return None
    return round(price * TOKENS_PER_UNIT, 6)


def pricing_status(input_price, output_price):
    """free / paid / partial (only one price known) / missing.
    Missing is NOT the same as free."""
    if input_price is None and output_price is None:
        return "missing"
    if input_price is None or output_price is None:
        return "partial"
    if input_price == 0 and output_price == 0:
        return "free"
    return "paid"


def transform_records(records):
    """Return a DataFrame with one row per unique model, sorted by model_id."""
    rows = []
    for record in records:
        pricing = record.get("pricing") or {}
        architecture = record.get("architecture") or {}
        inputs = architecture.get("input_modalities") or []
        outputs = architecture.get("output_modalities") or []

        raw_in, raw_out = pricing.get("prompt"), pricing.get("completion")
        price_in, price_out = per_million(raw_in), per_million(raw_out)
        negative = (raw_in is not None and raw_in < 0) or (raw_out is not None and raw_out < 0)

        all_modalities = set(inputs) | set(outputs)
        rows.append({
            "model_id": record["id"],
            "model_name": record["name"],
            "provider": get_provider(record["id"]),
            "description": record.get("description"),
            "created_at": record.get("created"),
            "context_length": record.get("context_length"),
            "input_price_per_million": price_in,
            "output_price_per_million": price_out,
            "pricing_status": pricing_status(price_in, price_out),
            "price_was_negative": negative,
            "modality": architecture.get("modality"),
            "input_modalities": ", ".join(inputs) if inputs else None,
            "output_modalities": ", ".join(outputs) if outputs else None,
            # multimodal = handles anything besides plain text
            "is_multimodal": any(m != "text" for m in all_modalities),
            "accepts_image": "image" in inputs,
            "accepts_audio": "audio" in inputs,
            "accepts_video": "video" in inputs,
            "accepts_file": "file" in inputs,
        })

    df = pd.DataFrame(rows, columns=COLUMNS)
    df["created_at"] = pd.to_datetime(df["created_at"], unit="s", utc=True, errors="coerce")
    df["context_length"] = pd.to_numeric(df["context_length"], errors="coerce")
    for column in ["input_price_per_million", "output_price_per_million"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.drop_duplicates(subset="model_id", keep="first")
    return df.sort_values("model_id").reset_index(drop=True)


# ------------------------------------------------- Artificial Analysis data
def number(value):
    """Return a float, or None if the value is missing or not a real number."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(result) or math.isinf(result) else result


def creator_name(record):
    """The creator (company) of a model, e.g. 'OpenAI'."""
    creator = record.get("model_creator") or {}
    return creator.get("name") or "unknown"


def dig(data, *path):
    """Safely read data["a"]["b"]... and return None if any step is missing."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


ARENA_COLUMNS = ["model_id", "model_name", "slug", "creator", "elo", "ci_95", "ci_low", "ci_high", "rank"]


def transform_arena(records):
    """Arena leaderboards (image, video, text-to-speech): sorted by Elo, best first.
    ci_low / ci_high is the 95% confidence interval around the Elo score."""
    rows = []
    for record in records:
        elo, ci = number(record.get("elo")), number(record.get("ci_95"))
        rows.append({
            "model_id": record["id"], "model_name": record["name"], "slug": record.get("slug"),
            "creator": creator_name(record), "elo": elo, "ci_95": ci,
            "ci_low": elo - ci if elo is not None and ci is not None else None,
            "ci_high": elo + ci if elo is not None and ci is not None else None,
        })
    df = pd.DataFrame(rows, columns=ARENA_COLUMNS[:-1])
    df = df.drop_duplicates(subset="model_id", keep="first")
    df = df.sort_values("elo", ascending=False).reset_index(drop=True)
    df["rank"] = df["elo"].rank(ascending=False, method="min").astype(int)
    return df[ARENA_COLUMNS]


LLM_BENCHMARK_COLUMNS = [
    "model_id", "model_name", "slug", "creator", "release_date", "intelligence_index", "coding_index",
    "agentic_index", "cost_per_task_usd", "input_price_per_million", "output_price_per_million",
    "pricing_status", "output_tokens_per_second", "time_to_first_token_seconds",
]


def transform_llm_benchmarks(records):
    """Language models with benchmark scores. Speed comes from 'performance_v3'
    (the older 'performance' block is being switched off by the API)."""
    rows = []
    for record in records:
        price_in = number(dig(record, "pricing", "price_1m_input_tokens"))
        price_out = number(dig(record, "pricing", "price_1m_output_tokens"))
        speed = number(dig(record, "performance_v3", "mean_output_tokens_per_second"))
        if speed is None:
            speed = number(dig(record, "performance", "median_output_tokens_per_second"))
        ttft = number(dig(record, "performance_v3", "mean_time_to_first_token_seconds"))
        if ttft is None:
            ttft = number(dig(record, "performance", "median_time_to_first_token_seconds"))
        rows.append({
            "model_id": record["id"], "model_name": record["name"], "slug": record.get("slug"),
            "creator": creator_name(record), "release_date": record.get("release_date"),
            "intelligence_index": number(dig(record, "evaluations", "artificial_analysis_intelligence_index")),
            "coding_index": number(dig(record, "evaluations", "artificial_analysis_coding_index")),
            "agentic_index": number(dig(record, "evaluations", "artificial_analysis_agentic_index")),
            "cost_per_task_usd": number(dig(record, "artificial_analysis_intelligence_index_cost",
                                            "cost_per_task", "total_cost")),
            "input_price_per_million": price_in, "output_price_per_million": price_out,
            "pricing_status": pricing_status(price_in, price_out),
            "output_tokens_per_second": speed, "time_to_first_token_seconds": ttft,
        })
    df = pd.DataFrame(rows, columns=LLM_BENCHMARK_COLUMNS)
    df["release_date"] = pd.to_datetime(df["release_date"], utc=True, errors="coerce")
    df = df.drop_duplicates(subset="model_id", keep="first")
    return df.sort_values("intelligence_index", ascending=False, na_position="last").reset_index(drop=True)


def transform_speech_to_speech(records):
    rows = [{"model_id": r["id"], "model_name": r["name"], "slug": r.get("slug"), "creator": creator_name(r),
             "bba_score": number(r.get("bba_score")), "fdb_score": number(r.get("fdb_score")),
             "tau_voice_score": number(r.get("tau_voice_score"))} for r in records]
    columns = ["model_id", "model_name", "slug", "creator", "bba_score", "fdb_score", "tau_voice_score"]
    df = pd.DataFrame(rows, columns=columns).drop_duplicates(subset="model_id", keep="first")
    return df.sort_values("bba_score", ascending=False, na_position="last").reset_index(drop=True)


def transform_speech_to_text(records):
    """Word error rate: LOWER is better, so the best model is first."""
    rows = [{"model_id": r["id"], "model_name": r["name"], "creator": creator_name(r),
             "aa_wer_index": number(r.get("aa_wer_index"))} for r in records]
    df = pd.DataFrame(rows, columns=["model_id", "model_name", "creator", "aa_wer_index"])
    df = df.drop_duplicates(subset="model_id", keep="first")
    return df.sort_values("aa_wer_index", ascending=True, na_position="last").reset_index(drop=True)

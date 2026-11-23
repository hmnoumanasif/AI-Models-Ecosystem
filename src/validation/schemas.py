"""VALIDATE step: Pydantic models describe what a good record looks like.
There is one model per kind of API response."""
import math

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


def finite_or_none(value):
    """Numbers must be real: text like "abc", nan and inf are rejected."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("must be a number or null")
    if math.isnan(number) or math.isinf(number):
        raise ValueError("must be a finite number")
    return number


# ---------------------------------------------------------------- OpenRouter
class PricingSchema(BaseModel):
    """Prices are given by the API as text, e.g. "0.000001" (USD per token)."""
    prompt: float | None = None       # input price
    completion: float | None = None   # output price

    @field_validator("prompt", "completion", mode="before")
    @classmethod
    def check_price(cls, value):
        return finite_or_none(value)


class ArchitectureSchema(BaseModel):
    modality: str | None = None
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)


class ModelRecord(BaseModel):
    """One OpenRouter model. Only id and name are required; the rest may be missing."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    created: int | None = None
    context_length: int | None = Field(default=None, gt=0)
    pricing: PricingSchema | None = None
    architecture: ArchitectureSchema | None = None


# ------------------------------------------------------- Artificial Analysis
class Creator(BaseModel):
    name: str | None = None


class ArenaRecord(BaseModel):
    """One model of an arena leaderboard (image, video, text-to-speech). Elo is required."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str | None = None
    model_creator: Creator | None = None
    elo: float
    ci_95: float | None = Field(default=None, ge=0)    # 95% confidence interval

    @field_validator("elo", "ci_95", mode="before")
    @classmethod
    def check_numbers(cls, value):
        return finite_or_none(value)


class LLMBenchmarkRecord(BaseModel):
    """One language model with its benchmark results (free tier)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str | None = None
    release_date: str | None = None
    model_creator: Creator | None = None
    evaluations: dict | None = None
    artificial_analysis_intelligence_index_cost: dict | None = None
    pricing: dict | None = None
    performance: dict | None = None
    performance_v3: dict | None = None


class SpeechToSpeechRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str | None = None
    model_creator: Creator | None = None
    bba_score: float | None = None
    fdb_score: float | None = None
    tau_voice_score: float | None = None

    @field_validator("bba_score", "fdb_score", "tau_voice_score", mode="before")
    @classmethod
    def check_numbers(cls, value):
        return finite_or_none(value)


class SpeechToTextRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    model_creator: Creator | None = None
    aa_wer_index: float | None = None

    @field_validator("aa_wer_index", mode="before")
    @classmethod
    def check_numbers(cls, value):
        return finite_or_none(value)


# ----------------------------------------------------------------- the check
def explain_errors(error):
    """Turn Pydantic's error list into one readable sentence."""
    parts = []
    for item in error.errors():
        field = ".".join(str(p) for p in item["loc"]) or "record"
        parts.append(f"{field}: {item['msg']}")
    return "; ".join(parts)


def validate_records(records, schema=ModelRecord):
    """Check every record separately with the given Pydantic model.

    One bad record is rejected (with a reason) but never stops the others.
    Returns (valid_records, rejected) where rejected is a list of dicts.
    """
    valid, rejected = [], []
    for index, record in enumerate(records):
        try:
            valid.append(schema.model_validate(record).model_dump())
        except ValidationError as error:
            model_id = record.get("id") if isinstance(record, dict) else None
            rejected.append({"index": index, "model_id": model_id, "reason": explain_errors(error)})
    return valid, rejected

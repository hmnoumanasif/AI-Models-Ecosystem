"""The list of all datasets the project can load.

HOW TO ADD A NEW DATASET (this is what makes the project scalable):
  1. Write a Pydantic model in validation/schemas.py (or reuse one).
  2. Write a transform function in transformation/transform.py (or reuse one).
  3. Add one Dataset(...) entry to the DATASETS list below.
  4. Put a small synthetic file in data/sample/<id>.json.
The pipeline, the database and the dashboard pick it up automatically.
"""
from dataclasses import dataclass, field

from src.transformation import transform
from src.validation import schemas

CATEGORIES = ["Language Models", "Image", "Video", "Speech"]

AA_URL = "https://artificialanalysis.ai/api/v2"
AA_ATTRIBUTION = "Data: Artificial Analysis (https://artificialanalysis.ai)"


@dataclass
class Dataset:
    id: str                     # short name, also used for the table and file names
    category: str               # one of CATEGORIES
    title: str                  # shown in the app
    url: str                    # API address
    schema: type                # Pydantic model that validates each record
    transform: callable         # list of valid records -> pandas DataFrame
    key_env: str | None = None  # name of the environment variable that holds the API key
    key_required: bool = False  # True: live download is impossible without a key
    key_header: str = "x-api-key"
    key_prefix: str = ""        # e.g. "Bearer " for the Authorization header
    paged: bool = False         # True: the API returns several pages
    attribution: str = ""       # text we must show for this data
    # --- used by the generic leaderboard pages ---
    metric: str | None = None   # main column to rank by
    metric_label: str = ""
    higher_is_better: bool = True
    ci_column: str | None = None            # confidence interval column (+/-), if any
    color: str = "#4C8DF6"      # small colour square next to chart titles
    bool_columns: list = field(default_factory=list)   # restored as True/False when read from the database
    date_columns: list = field(default_factory=list)   # restored as dates when read from the database


def arena(id, category, title, endpoint, label, color):
    """All arena leaderboards have the same shape, so one helper builds them."""
    return Dataset(
        id=id, category=category, title=title, url=f"{AA_URL}/media/{endpoint}/models/free",
        schema=schemas.ArenaRecord, transform=transform.transform_arena,
        key_env="ARTIFICIAL_ANALYSIS_API_KEY", key_required=True, attribution=AA_ATTRIBUTION,
        metric="elo", metric_label=label, ci_column="ci_95", color=color)


DATASETS = [
    # ---------------- Language Models
    Dataset(
        id="llm_catalog", category="Language Models", title="Model catalog (OpenRouter)",
        url="https://openrouter.ai/api/v1/models", schema=schemas.ModelRecord,
        transform=transform.transform_records, key_env="OPENROUTER_API_KEY", key_required=False,
        key_header="Authorization", key_prefix="Bearer ",
        bool_columns=["price_was_negative", "is_multimodal", "accepts_image", "accepts_audio",
                      "accepts_video", "accepts_file"],
        date_columns=["created_at"]),
    Dataset(
        id="llm_benchmarks", category="Language Models", title="Benchmarks (Artificial Analysis)",
        url=f"{AA_URL}/language/models/free", schema=schemas.LLMBenchmarkRecord,
        transform=transform.transform_llm_benchmarks, key_env="ARTIFICIAL_ANALYSIS_API_KEY",
        key_required=True, paged=True, attribution=AA_ATTRIBUTION,
        metric="intelligence_index", metric_label="Artificial Analysis Intelligence Index",
        color="#8B5CF6", date_columns=["release_date"]),
    # ---------------- Image
    arena("image_t2i", "Image", "Text to Image", "text-to-image", "Image Arena Elo", "#8B5CF6"),
    arena("image_edit", "Image", "Image Editing", "image-editing", "Image Editing Arena Elo", "#F97316"),
    # ---------------- Video
    arena("video_t2v", "Video", "Text to Video (silent)", "text-to-video", "Video Arena Elo", "#8B5CF6"),
    arena("video_i2v", "Video", "Image to Video (silent)", "image-to-video", "Video Arena Elo", "#F97316"),
    arena("video_t2v_audio", "Video", "Text to Video (with audio)", "text-to-video-audio",
          "Video Arena Elo", "#10B981"),
    arena("video_i2v_audio", "Video", "Image to Video (with audio)", "image-to-video-audio",
          "Video Arena Elo", "#EAB308"),
    # ---------------- Speech
    arena("speech_tts", "Speech", "Text to Speech", "text-to-speech", "Speech Arena Elo", "#8B5CF6"),
    Dataset(
        id="speech_s2s", category="Speech", title="Speech to Speech", url=f"{AA_URL}/media/speech-to-speech/models/free",
        schema=schemas.SpeechToSpeechRecord, transform=transform.transform_speech_to_speech,
        key_env="ARTIFICIAL_ANALYSIS_API_KEY", key_required=True, attribution=AA_ATTRIBUTION,
        metric="bba_score", metric_label="Big Bench Audio score (BBA)", color="#F97316"),
    Dataset(
        id="speech_stt", category="Speech", title="Speech to Text", url=f"{AA_URL}/media/speech-to-text/models/free",
        schema=schemas.SpeechToTextRecord, transform=transform.transform_speech_to_text,
        key_env="ARTIFICIAL_ANALYSIS_API_KEY", key_required=True, attribution=AA_ATTRIBUTION,
        metric="aa_wer_index", metric_label="AA Word Error Rate index", higher_is_better=False, color="#10B981"),
]

BY_ID = {d.id: d for d in DATASETS}


def datasets_in(category):
    """All datasets of one category, in the order of the list above."""
    return [d for d in DATASETS if d.category == category]

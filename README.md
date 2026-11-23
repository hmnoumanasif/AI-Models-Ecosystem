# AI Model Ecosystem Intelligence
**An ETL and Exploratory Data Analysis pipeline** (Project 1: ETL + EDA Pipeline)

## 1. Project description

**What it does.** It extracts data about AI models from public APIs, validates it (Pydantic), cleans it (pandas),
loads it into SQLite (and CSV files) and shows a structured exploratory analysis in a Streamlit app.
The app has **four categories**: Language Models, Image, Video and Speech.

**Datasets (why we chose them).** Real, public, frequently changing and messy enough to need real validation.

| Category | Dataset | API | Key needed for live data |
|---|---|---|---|
| Language Models | Model catalog: context window, token prices, modalities | OpenRouter `/api/v1/models` | No (optional) |
| Language Models | Benchmarks: Intelligence Index, cost, speed | Artificial Analysis `/language/models/free` | Yes |
| Image | Text to Image, Image Editing (arena Elo) | Artificial Analysis `/media/.../models/free` | Yes |
| Video | Text/Image to Video, silent and with audio (arena Elo) | Artificial Analysis | Yes |
| Speech | Text to Speech (Elo), Speech to Speech, Speech to Text (error rate) | Artificial Analysis | Yes |

**Where the data is loaded.** SQLite (`data/ai_intelligence.db`, one table per dataset plus a run history table) and
cleaned CSV files in `data/processed/`. Raw JSON of every live download is kept in `data/raw/<dataset>/`.

**EDA we perform.**
- Language Models: provider distribution, context windows and outliers, pricing (free vs. missing vs. paid),
  modalities, benchmark scores vs. cost/speed/price, data quality, search/filter/compare/download.
- Image / Video / Speech: ranking with 95% confidence intervals, models statistically tied with the leader,
  creators (companies), score distribution, data quality, search/filter/compare/download.

## 2. How the pipeline works

```text
 API (live)  or  saved snapshot  or  synthetic sample      <- the source is always shown in the app
      |  1. EXTRACT    src/extraction/api_client.py     requests, API key, timeout, retries, pages
      v
      |  2. VALIDATE   src/validation/schemas.py        Pydantic: bad records rejected with a reason
      v
      |  3. TRANSFORM  src/transformation/transform.py  pandas: one clean table per dataset
      v
      |  4. LOAD       src/loading/database.py          SQLite (one transaction) + CSV
      v
 EDA (src/analysis/) -> charts -> Streamlit pages (src/dashboard.py, app.py)
```

`src/datasets.py` is the **list of all datasets**. Every dataset is one entry (URL, schema, transform, key name,
which column is the score). The pipeline, the database and the app read this list, so nothing else is hard-coded.

Cleaning rules (also written as comments in the code):
- Prices are converted to **USD per 1 million tokens**. `-1` (the API's "variable price") becomes **missing**.
- **Missing is not free.** Pricing status: `free` (both prices exactly 0), `paid`, `partial`, `missing`.
- Duplicate model ids are removed (first one kept). One bad record never stops the others.

## 3. Folder structure

```text
app.py                      Streamlit app (categories, sidebar, loader, error handling)
src/
  config.py                 paths, retry settings, API keys from .env
  datasets.py               THE LIST of datasets and categories (add a dataset here)
  pipeline.py               Extract -> Validate -> Transform -> Load, for one or all datasets
  extraction/api_client.py  download, API key header, retries, pages, saved snapshots
  validation/schemas.py     Pydantic models
  transformation/transform.py
  loading/database.py       SQLite code (the only file that knows about the database)
  analysis/eda.py           Language Model catalog analysis
  analysis/leaderboard.py   Generic analysis for any ranking (Image, Video, Speech, Benchmarks)
  analysis/charts.py        Matplotlib charts (no longer used by the app; kept as it was)
  dashboard.py              one function per page
  ui/                       the interface: styles.py (light/dark CSS), palette.py (colours and fonts),
                            plots.py (interactive Plotly charts), tables.py (sortable tables), components.py
tests/                      automated tests (no internet needed)
data/raw/llm_catalog/       real OpenRouter download (2026-10-30), used when offline
data/sample/                tiny SYNTHETIC files (made-up models), last-resort fallback
.streamlit/config.toml      Streamlit base settings (the app draws its own light and dark look)
```

## 4. Install and run (Windows PowerShell)

Use Python **3.10 to 3.13** from python.org (the `py` launcher). The MSYS2/MinGW Python has no pip.

```powershell
cd ai-model-ecosystem-intelligence
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```
If activating is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
Linux/macOS: `source .venv/bin/activate`.

**Without internet or keys** the app still works: it builds the database from the saved OpenRouter file and the
synthetic samples. Synthetic data is shown with a **red banner** and is never called live data.

### API keys (.env)
1. Copy `.env.example` to a new file named `.env`.
2. Put your key after `ARTIFICIAL_ANALYSIS_API_KEY=` (free key from artificialanalysis.ai).
3. Restart the app and press **Fetch live data**. The key is only sent in the `x-api-key` header and is never
   logged or shown. `.env` is ignored by Git.

### Pipeline from the terminal
```powershell
python -m src.pipeline --offline            # all datasets, saved data only
python -m src.pipeline                      # try live APIs, fall back to saved data
python -m src.pipeline image_t2i video_t2v  # only these datasets
```

### Tests
```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## 5. Fault tolerance (what happens when something fails)

| Failure | Behaviour |
|---|---|
| No internet / timeout / HTTP 429, 5xx | 3 attempts, waiting 1 s then 2 s (exponential backoff) |
| Daily request limit reached (HTTP 429 with a long Retry-After) | Stops at once (no wasted requests) and says when to try again |
| Missing or wrong API key (401/403) | Clear message, no retries, saved data is shown |
| Broken JSON / unexpected structure | Clear message, saved data is shown |
| One bad record | Only that record is rejected, with a reason (Data quality page) |
| One dataset fails | The other datasets and categories keep working |
| Database cannot be written | Old data is kept (rollback); app shows the data with a warning |
| Database folder is read-only | The temp folder is used instead |
| A chart or page crashes | Only that chart shows a warning |

## 6. Scalability: add a dataset or a whole new category

1. Add one `Dataset(...)` entry to `src/datasets.py` (URL, Pydantic schema, transform, key name, score column).
2. Put a small synthetic file in `data/sample/<id>.json`.
3. For a **new category** also add its name to `CATEGORIES`.

The pipeline, database tables, run history, ranking pages, creators, distribution, quality and explore pages are
created automatically. `tests/test_datasets.py` and `tests/test_app.py` prove this with a made-up "Music" category.

## 7. Streamlit Community Cloud
1. Upload the **contents of this folder** to a GitHub repository (`app.py` at the top level, no `.env`).
2. https://share.streamlit.io > Create app > choose the repository, main file `app.py`, Python 3.12.
3. In **Advanced settings > Secrets** add: `ARTIFICIAL_ANALYSIS_API_KEY = "your-key"`
   (Streamlit exposes top-level secrets as environment variables, so the same code reads it).

The cloud file system is temporary, so the database may be reset on restart; after a restart the app shows the empty first-visit page again until someone presses **Fetch live data**.

## 8. Data sources, attribution and honest limitations
- Image, Video, Speech and Benchmark data: **Artificial Analysis** (https://artificialanalysis.ai). Attribution is
  shown in the app. Their terms allow internal use and no redistribution, so **real Artificial Analysis data is
  never committed to the repository**; the files in `data/sample/` are synthetic.
- The free API tier allows 100 requests per 24 hours. Pressing **Fetch live data** for one category uses a few.
- The free benchmark tier has no context window or modality columns; those come from the OpenRouter catalog.
- Image/Video/Speech free data contains Elo, confidence interval and creator only (no prices).
- Catalog share and creator share are shares of the listed models, not market share. Correlation is not causation.
- Live API calls were tested with mocked responses; the real keys must be tested on your own computer.
- Switch between the Bright and Dark look with the switch at the top right of the page. The choice is kept in the
  address (`?theme=dark`), so a reload or a shared link keeps it.
- The app shows no results on the very first visit. Press **Fetch live data** (per category): the pipeline runs and
  the result is saved in the database (`data/ai_intelligence.db`). When the app is opened again, it shows the saved
  results straight from the database. To see the empty first visit again, stop the app and delete that file.
- Charts are interactive (hover for details, drag to zoom, double-click to reset, click a legend entry to hide it,
  camera icon to save a PNG). Tables sort when you click a column header.
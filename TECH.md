# Tech Stack

Systematic Review Processor — the technologies behind the tool that codes
research PDFs with Claude for the Laboratory for Social Connectedness & Health.

## Backend (Python 3.8+)

| Component | Tech | Role |
|-----------|------|------|
| Web framework | **FastAPI** | REST API + serves the local web UI |
| ASGI server | **Uvicorn** | Runs the app at `http://127.0.0.1:8000` |
| Validation | **Pydantic** | Request / response schemas |
| LLM client | **Anthropic SDK** (`anthropic`) | Calls Claude to code each paper |
| PDF parsing | **pypdf** | Extracts text from research PDFs |
| Prompt loading | **python-docx** | Reads the `.docx` coding instructions |
| Data export | **pandas** + stdlib `csv` | Builds the results CSV and the change log |
| Progress / CLI | **tqdm** | Progress bars for command-line runs |
| Config | **python-dotenv** | Loads `ANTHROPIC_API_KEY` from `.env` |
| Concurrency | **threading** (stdlib) | Background job runner + cancel support |

## Frontend — local web UI (`web/`)

- **Vanilla HTML / CSS / JavaScript** (no framework, no build step)
- **Server-Sent Events (SSE)** for live progress updates
- Drag-and-drop uploads, progress ring, per-paper status cards

## Static demo site (`docs/` → GitHub Pages)

- Standalone **HTML / CSS / JS** simulation (no backend, no API key required)
- Deployed via **GitHub Actions** (`.github/workflows/pages.yml`)
- Live at https://isjustabhi.github.io/systematic-review-processor/

## LLM service

- **Anthropic Claude API**, default model `claude-sonnet-5-5`
  (`claude-sonnet-4-6` remains selectable)
- **Method: full-context prompting** — the entire paper text is sent in one
  call with the coding protocol; the model returns structured JSON.
- **Optional two-step prompt:** a framework PDF is digested once, then that
  briefing is prepended to the coding protocol (still one call per paper; no RAG).
- **Response parsing** reads only `type=text` content blocks. Newer Claude
  models may lead with a thinking block that has no `.text` attribute.
- Sequential, rate-limited calls (default ~4–5s gap) to stay under rate limits
- ~17K input tokens/paper (prompt + paper text), a few K tokens out

## Tooling & infrastructure

- **Git / GitHub** — version control + hosting
- **setuptools** (`pyproject.toml`) — packaging
- Dev extras: **pytest**, **black**, **flake8**

## Architecture pattern

- Core library (`sr_processor/`) is **UI-agnostic** — shared by both the CLI
  (`run_review.py`) and the FastAPI web app (`api/`).
- Sequential processing with **resume-on-restart**: already-coded papers are
  skipped automatically.
- Up to **400 papers** per run.

### Outputs (in `output/`)

| File | Purpose |
|------|---------|
| `{Paper}.json` | Coded fields for one paper |
| `{Paper}_ERROR.json` | Failed run — contains the error |
| `systematic_review_results.csv` | All papers combined for Excel |
| `change_log.csv` | Papers that failed, hit a parse error, or need human review |
| `processor.log` | Full run log |
| `batch_summary.json` | Counts: success / failed / parse errors / skipped |

## Run it

```bash
pip install -r requirements.txt        # includes FastAPI + Uvicorn for the web UI
# add ANTHROPIC_API_KEY=sk-ant-... to .env

python3 run_server.py                  # web UI at http://127.0.0.1:8000
# or
python3 run_review.py                  # command-line batch run
```

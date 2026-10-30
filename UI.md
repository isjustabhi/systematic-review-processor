# Web UI

## Start

```bash
cd /Users/abhi/Downloads/systematic-review-processor
pip install -r requirements.txt
python3 run_server.py
```

Open **http://127.0.0.1:8000**

## Features

- Drag-and-drop up to **400 PDFs**
- Upload coding prompt (`.docx`)
- Optional framework PDF — Claude reads it once, then applies the coding prompt
- Choose **Claude Sonnet 5.5** (default) or **Sonnet 4.6**
- Live progress ring and per-paper status cards
- **Start / Stop** processing (1 worker by default — stable for rate limits)
- **Download CSV** or **ZIP** (all JSON + log)
- **Clear outputs** without removing PDFs
- Resume: already-coded papers are skipped automatically

## Requirements

- `ANTHROPIC_API_KEY` in `.env`
- Default prompt: `Claude_Code_Prompting_v4.docx` in project root (or upload via UI)

# Systematic Review Processor

**[Laboratory for Social Connectedness & Health](https://www.relationshipshealth.com/)** · Department of Psychology · University of Arizona  
PI: [David Sbarra, Ph.D.](mailto:sbarra@arizona.edu)  
Data Scientist: [Abhiram Varma Nandimandalam](mailto:abhiramn@arizona.edu)

**Interactive guide (GitHub Pages):** https://isjustabhi.github.io/systematic-review-processor/

Code research PDFs for the lab’s social connectedness & health systematic review using Claude and `Claude_Code_Prompting_v4.docx`.

- **Up to 400 papers** per run (RAG Pilot Papers folder)
- **Sequential processing** (stable for API rate limits)
- Web UI or command line → JSON + CSV + **change log** (papers that couldn't be coded)

## Setup

```bash
pip install -r requirements.txt
# Create .env with: ANTHROPIC_API_KEY=sk-ant-your-key
```

Place your coding prompt as `Claude_Code_Prompting_v4.docx` in this folder.  
PDFs go in **`RAG Pilot Papers/`** (up to 400 PDFs per run).

## Command line (recommended for pilot)

```bash
python3 run_review.py
```

Results: `output/*.json`, `output/systematic_review_results.csv`

## Web UI (for lab / non-technical users)

```bash
python3 run_server.py
```

Open **http://127.0.0.1:8000**

1. **Step 1** — Paste Anthropic API key (or use `.env`)
2. **Step 2** — Upload coding prompt `.docx`
3. **Step 3** — Drag & drop PDF papers (up to 400)
4. Click **Start coding papers** → **Download CSV** (and the **change log** for any papers that couldn't be coded)

## License

MIT

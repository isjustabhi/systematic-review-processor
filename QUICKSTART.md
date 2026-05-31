# Quick Start Guide

Get started in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- Anthropic API key (get it from https://console.anthropic.com/api/keys)
- Folder of PDF files to process
- Your coding prompt as a Word document (.docx)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Your API Key

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="sk-ant-v7-YOUR_KEY_HERE"
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-v7-YOUR_KEY_HERE"
```

**Windows (Command Prompt):**
```cmd
set ANTHROPIC_API_KEY=sk-ant-v7-YOUR_KEY_HERE
```

## Run the Processor

### Test on a few papers first
To do a small trial run, put just a handful of PDFs in the folder (the tool
processes whatever is in `--pdf-folder`, up to 400). Already-coded papers are
skipped automatically, so you can add more later and rerun.

```bash
python systematic_review_processor.py \
  --pdf-folder /path/to/your/pdfs \
  --output-folder /path/to/output \
  --prompt-file /path/to/your/prompt.docx
```

### Process All PDFs
```bash
python systematic_review_processor.py \
  --pdf-folder /path/to/your/pdfs \
  --output-folder /path/to/output \
  --prompt-file /path/to/your/prompt.docx
```

### Process with Custom Workers
```bash
python systematic_review_processor.py \
  --pdf-folder /path/to/your/pdfs \
  --output-folder /path/to/output \
  --prompt-file /path/to/your/prompt.docx \
  --workers 2
```

## Example Paths

**Mac:**
```bash
python systematic_review_processor.py \
  --pdf-folder ~/Documents/Papers \
  --output-folder ~/Documents/Output \
  --prompt-file ~/Documents/prompt.docx
```

**Windows:**
```bash
python systematic_review_processor.py \
  --pdf-folder "C:\Users\YourName\Documents\Papers" \
  --output-folder "C:\Users\YourName\Documents\Output" \
  --prompt-file "C:\Users\YourName\Documents\prompt.docx"
```

**Linux:**
```bash
python systematic_review_processor.py \
  --pdf-folder ~/papers \
  --output-folder ~/output \
  --prompt-file ~/prompt.docx
```

## Check Results

After processing completes:

```bash
# List output files
ls /path/to/output

# View CSV results
# Open with Excel or your favorite spreadsheet app
open /path/to/output/systematic_review_results.csv
```

You'll find:
- **`*.json`** — One file per PDF with structured coding
- **`systematic_review_results.csv`** — All papers combined in one spreadsheet
- **`processor.log`** — Detailed processing log

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "API key not found" | Make sure you set the environment variable in the same terminal window |
| "PDF folder not found" | Check the path exists and contains `.pdf` files |
| "Prompt file not found" | Verify the path to your `.docx` prompt file |
| "Rate limit exceeded" | Run with `--workers 2` to slow down API calls |

## Next Steps

1. **Read the full README** — `README.md` for advanced options
2. **Check the logs** — `processor.log` contains detailed diagnostics
3. **Review outputs** — Open the CSV to see results
4. **Iterate** — Refine your prompt based on results

## Performance

Processing is deliberately paced (~4–5s gap between API calls) to stay under
Anthropic rate limits, so wall-clock time is dominated by the per-paper delay:

- **20 papers:** a few minutes
- **100 papers:** ~1 hour
- **300+ papers:** several hours

It's fine to leave a large run going and check back — interrupted runs resume
where they left off (already-coded papers are skipped).

## Cost

Roughly **$0.06–$0.10 per paper** (about 17K input tokens for the prompt +
paper text, plus a few thousand output tokens), at Claude Sonnet pricing.

- For 100 papers: ~$6–$10
- For 300 papers: ~$20–$30

Check your Anthropic account dashboard for actual usage.

---

Need help? Check the README.md for comprehensive documentation.

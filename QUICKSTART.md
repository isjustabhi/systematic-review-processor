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

### Test Mode (First 10 PDFs)
```bash
python systematic_review_processor.py \
  --pdf-folder /path/to/your/pdfs \
  --output-folder /path/to/output \
  --prompt-file /path/to/your/prompt.docx \
  --test
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

- **20 PDFs:** ~25 seconds
- **100 PDFs:** ~2 minutes
- **300 PDFs:** ~6 minutes

Actual time depends on PDF size and your internet speed.

## Cost

Approximately $0.003 per PDF processed.

For 100 PDFs: ~$0.30
For 300 PDFs: ~$0.90

Check your Anthropic account dashboard for actual usage.

---

Need help? Check the README.md for comprehensive documentation.

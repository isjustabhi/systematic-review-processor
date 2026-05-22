# ============================================================
# Systematic Review PDF Processor — Pilot 2
# ============================================================
# Reads PDFs, sends text to Anthropic API for structured coding,
# and saves each response as a JSON file named after the PDF.
#
# SETUP (one-time, run in RStudio console):
#   install.packages(c("httr2", "pdftools", "jsonlite", "officer"))
#
# USAGE:
#   Open this file in RStudio and click Source (or press Ctrl+Shift+S).
#   API key is loaded automatically from .Renviron.
# ============================================================

library(httr2)
library(pdftools)
library(jsonlite)
library(officer)

# ── Configuration ──────────────────────────────────────────────────────────────

PDF_FOLDER    <- "C:/Users/sbarra/Box/Social Connectedness & Health Coding/Dave Sbarra/Dave Claude Code Work/Dave Claude Papers/Pilot2"
OUTPUT_FOLDER <- "C:/Users/sbarra/Box/Social Connectedness & Health Coding/Dave Sbarra/Dave Claude Code Work/Dave Claude Papers/Pilot2/json_output"
PROMPT_FILE   <- "C:/Users/sbarra/Box/Social Connectedness & Health Coding/Dave Sbarra/Dave Claude Code Work/Dave Claude Papers/Pilot2/Prompt/Claude_Code_Prompting_v3.docx"

MODEL         <- "claude-sonnet-4-20250514"
MAX_TOKENS    <- 4096L
DELAY_SECONDS <- 5
TEST_MODE     <- TRUE    # TRUE = first 10 PDFs only; FALSE = all PDFs
TEST_LIMIT    <- 10L

# ── Load System Prompt from Word file ──────────────────────────────────────────

load_prompt <- function(path) {
  if (!file.exists(path)) stop("Prompt file not found: ", path)
  raw       <- docx_summary(read_docx(path))
  text_rows <- raw$text[raw$content_type == "paragraph"]
  text_rows <- text_rows[!is.na(text_rows)]
  prompt    <- paste(text_rows, collapse = "\n")
  if (nchar(trimws(prompt)) == 0) stop("Prompt file appears empty after extraction.")
  cat(sprintf("Prompt loaded: %d characters from %s\n", nchar(prompt), basename(path)))
  return(prompt)
}

# ── Process one PDF ────────────────────────────────────────────────────────────

process_pdf <- function(api_key, pdf_path, output_folder, system_prompt) {

  pdf_name    <- tools::file_path_sans_ext(basename(pdf_path))
  output_path <- file.path(output_folder, paste0(pdf_name, ".json"))

  if (file.exists(output_path)) {
    cat("  Skipping (already done):", basename(pdf_path), "\n")
    return(invisible(NULL))
  }

  # Extract text from PDF
  pages <- tryCatch(pdf_text(pdf_path), error = function(e) NULL)
  if (is.null(pages) || length(pages) == 0) {
    stop("pdftools could not extract text from this file.")
  }
  full_text <- paste(pages, collapse = "\n\n")

  user_message <- paste0(
    "Please code the following paper according to the systematic review coding instructions. ",
    "Return only the JSON object - no other text.\n\n",
    full_text
  )

  # Build and send API request
  resp <- request("https://api.anthropic.com/v1/messages") |>
    req_headers(
      "x-api-key"         = api_key,
      "anthropic-version" = "2023-06-01",
      "content-type"      = "application/json"
    ) |>
    req_body_json(list(
      model      = MODEL,
      max_tokens = MAX_TOKENS,
      system     = system_prompt,
      messages   = list(
        list(role = "user", content = user_message)
      )
    )) |>
    req_error(is_error = \(r) FALSE) |>
    req_perform()

  # Check for API-level errors
  if (resp_status(resp) != 200L) {
    err_body <- tryCatch(resp_body_json(resp), error = function(e) list())
    stop(sprintf("API error %d: %s", resp_status(resp),
                 err_body$error$message %||% "unknown error"))
  }

  resp_body <- resp_body_json(resp)
  raw_text  <- trimws(resp_body$content[[1]]$text)

  # Strip markdown code fences if present
  if (startsWith(raw_text, "```")) {
    raw_text <- gsub("^```[a-zA-Z]*\\n?", "", raw_text)
    raw_text <- gsub("\\n?```$",          "", raw_text)
    raw_text <- trimws(raw_text)
  }

  # Parse JSON response
  result <- tryCatch(
    fromJSON(raw_text, simplifyVector = FALSE),
    error = function(e) {
      warning("Could not parse JSON - saving raw response. Parse error: ", conditionMessage(e))
      list(parse_error = TRUE, raw_response = raw_text, eligible = NULL)
    }
  )

  # Attach metadata
  result[["_source_file"]] <- basename(pdf_path)
  result[["_model"]]       <- MODEL
  result[["_prompt_file"]] <- basename(PROMPT_FILE)

  # Save immediately
  write(
    toJSON(result, pretty = TRUE, auto_unbox = TRUE, null = "null"),
    file = output_path
  )

  cat("  Saved:", basename(output_path), "\n")
  return(invisible(result))
}

# Null-coalescing helper
`%||%` <- function(a, b) if (!is.null(a)) a else b

# ── Main ───────────────────────────────────────────────────────────────────────

main <- function() {

  # API key
  api_key <- Sys.getenv("ANTHROPIC_API_KEY")
  if (nchar(api_key) == 0) {
    api_key <- readline("Enter your Anthropic API key: ")
  }
  if (nchar(trimws(api_key)) == 0) stop("No API key provided.")

  # Load prompt from Word file
  cat("Loading prompt from Word file...\n")
  system_prompt <- load_prompt(PROMPT_FILE)

  # Create output folder
  dir.create(OUTPUT_FOLDER, showWarnings = FALSE, recursive = TRUE)
  cat("Output folder:", OUTPUT_FOLDER, "\n\n")

  # Find PDFs
  all_pdfs <- sort(list.files(PDF_FOLDER, pattern = "\\.pdf$",
                              full.names = TRUE, ignore.case = TRUE))
  if (length(all_pdfs) == 0) stop("No PDF files found in: ", PDF_FOLDER)

  pdfs <- if (TEST_MODE) head(all_pdfs, TEST_LIMIT) else all_pdfs
  cat(sprintf("Found %d PDF(s). Processing %d.\n\n", length(all_pdfs), length(pdfs)))

  # Process each PDF
  n_success <- 0L
  n_error   <- 0L

  for (i in seq_along(pdfs)) {
    pdf_path <- pdfs[[i]]
    cat(sprintf("[%d/%d] %s\n", i, length(pdfs), basename(pdf_path)))

    result <- tryCatch({
      process_pdf(api_key, pdf_path, OUTPUT_FOLDER, system_prompt)
    }, error = function(e) {
      cat("  ERROR:", conditionMessage(e), "\n")
      err_path <- file.path(OUTPUT_FOLDER,
                            paste0(tools::file_path_sans_ext(basename(pdf_path)), "_ERROR.json"))
      write(toJSON(list(error = conditionMessage(e), source_file = basename(pdf_path)),
                   pretty = TRUE, auto_unbox = TRUE),
            file = err_path)
      NULL
    })

    if (is.null(result)) {
      n_error <- n_error + 1L
    } else {
      n_success <- n_success + 1L
      eligible  <- result[["eligible"]]
      conf      <- result[["confidence"]]
      if (!is.null(eligible)) cat(sprintf("  Eligible: %s  |  Confidence: %s\n", eligible, conf))
    }

    # Delay between calls (skip after last)
    if (i < length(pdfs)) {
      cat(sprintf("  Waiting %ds...\n", DELAY_SECONDS))
      Sys.sleep(DELAY_SECONDS)
    }
  }

  cat(sprintf("\n%s\nDone. Processed: %d | Errors: %d\nJSON files in: %s\n",
              strrep("=", 50), n_success, n_error, OUTPUT_FOLDER))
}

main()

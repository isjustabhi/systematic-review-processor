library(jsonlite)
library(dplyr)

JSON_FOLDER <- "C:/Users/sbarra/Box/Social Connectedness & Health Coding/Dave Sbarra/Dave Claude Code Work/Dave Claude Papers/Pilot2/json_output"
OUTPUT_FILE <- "C:/Users/sbarra/Box/Social Connectedness & Health Coding/Dave Sbarra/Dave Claude Code Work/Dave Claude Papers/Pilot2/systematic_review_results_Pilot2.csv"

json_files <- list.files(JSON_FOLDER, pattern = "\\.json$", full.names = TRUE, ignore.case = TRUE)
if (length(json_files) == 0) stop("No JSON files found in: ", JSON_FOLDER)
cat(sprintf("Found %d JSON files.\n", length(json_files)))

read_json_file <- function(path) {
  tryCatch({
    data <- fromJSON(path, simplifyVector = TRUE, flatten = TRUE)
    data <- lapply(data, function(x) if (length(x) > 1) paste(x, collapse = "; ") else if (length(x) == 0) NA else x)
    data <- lapply(data, as.character)
    as.data.frame(data, stringsAsFactors = FALSE)
  }, error = function(e) {
    cat("  Skipping (parse error):", basename(path), "\n")
    NULL
  })
}

all_results <- lapply(json_files, read_json_file)
all_results <- Filter(Negate(is.null), all_results)
combined <- bind_rows(all_results)
combined <- combined[order(combined$eligible, combined$authors, na.last = TRUE), ]
write.csv(combined, OUTPUT_FILE, row.names = FALSE, na = "")
cat(sprintf("Done. %d rows written to: %s\n", nrow(combined), OUTPUT_FILE))

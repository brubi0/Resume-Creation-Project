#!/bin/bash
# Generate DOCX files from markdown outputs using the resume template.
# Usage: ./generate.sh <Name> [DRAFT|FINAL]
#   e.g., ./generate.sh Cindy_Rubio FINAL
#
# Looks for markdown files in candidates/[name]/output/ first,
# falls back to output/ for quick-start usage.

set -e

NAME="${1:?Usage: ./generate.sh <Name> [DRAFT|FINAL]}"
SUFFIX="${2:-FINAL}"
TEMPLATE="templates/resume_template.docx"

# Convert Name to lowercase directory name (e.g., Cindy_Rubio -> cindy_rubio)
CANDIDATE_DIR="candidates/$(echo "$NAME" | tr '[:upper:]' '[:lower:]')/output"

# Determine output directory: prefer candidates/, fall back to output/
if [ -d "$CANDIDATE_DIR" ]; then
  OUTDIR="$CANDIDATE_DIR"
else
  OUTDIR="output"
fi

if [ ! -f "$TEMPLATE" ]; then
  echo "Error: Template not found at $TEMPLATE"
  exit 1
fi

echo "Using output directory: $OUTDIR"

for TYPE in Resume Interview_Prep; do
  MD="$OUTDIR/${NAME}_${TYPE}_${SUFFIX}.md"
  if [ -f "$MD" ]; then
    DOCX="$OUTDIR/${NAME}_${TYPE}_${SUFFIX}.docx"
    echo "Generating $DOCX..."
    pandoc "$MD" -o "$DOCX" --reference-doc="$TEMPLATE"
  fi
done

# Resume without suffix (e.g., Name_Resume.md)
MD_PLAIN="$OUTDIR/${NAME}_Resume.md"
if [ -f "$MD_PLAIN" ]; then
  DOCX_PLAIN="$OUTDIR/${NAME}_Resume.docx"
  echo "Generating $DOCX_PLAIN..."
  pandoc "$MD_PLAIN" -o "$DOCX_PLAIN" --reference-doc="$TEMPLATE"
fi

echo "Done."

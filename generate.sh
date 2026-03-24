#!/bin/bash
# Generate DOCX files from markdown outputs using the resume template.
# Usage: ./generate.sh <Name> [DRAFT|FINAL]
#   e.g., ./generate.sh Cindy_Rubio FINAL

set -e

NAME="${1:?Usage: ./generate.sh <Name> [DRAFT|FINAL]}"
SUFFIX="${2:-FINAL}"
TEMPLATE="templates/resume_template.docx"

if [ ! -f "$TEMPLATE" ]; then
  echo "Error: Template not found at $TEMPLATE"
  exit 1
fi

for TYPE in Resume Interview_Prep; do
  MD="output/${NAME}_${TYPE}_${SUFFIX}.md"
  if [ -f "$MD" ]; then
    DOCX="output/${NAME}_${TYPE}_${SUFFIX}.docx"
    echo "Generating $DOCX..."
    pandoc "$MD" -o "$DOCX" --reference-doc="$TEMPLATE"
  fi
done

# Resume without suffix (e.g., Name_Resume.md)
MD_PLAIN="output/${NAME}_Resume.md"
if [ -f "$MD_PLAIN" ]; then
  DOCX_PLAIN="output/${NAME}_Resume.docx"
  echo "Generating $DOCX_PLAIN..."
  pandoc "$MD_PLAIN" -o "$DOCX_PLAIN" --reference-doc="$TEMPLATE"
fi

echo "Done."

#!/usr/bin/env bash

set -euo pipefail

# Usage:
# ./run_tcd.sh green_fields.jpg
# ./run_tcd.sh green_fields.jpg --gsd 0.05

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <input_image> [--gsd VALUE]" >&2
    exit 1
fi

INPUT="$1"
shift

GSD="0.1"

# Parse optional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gsd)
            if [[ $# -lt 2 ]]; then
                echo "Error: --gsd requires a value." >&2
                exit 1
            fi
            GSD="$2"
            shift 2
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            echo "Usage: $0 <input_image> [--gsd VALUE]" >&2
            exit 1
            ;;
    esac
done

if [[ ! -f "$INPUT" ]]; then
    echo "Error: Input file '$INPUT' does not exist." >&2
    exit 1
fi

# Ensure the output directories exist
mkdir -p samples predictions

# Find the highest numbered prediction directory
LAST=0

for DIR in predictions/*; do
    [[ -d "$DIR" ]] || continue

    NAME="${DIR##*/}"

    if [[ "$NAME" =~ ^[0-9]+$ ]] && (( 10#$NAME > LAST )); then
        LAST=$((10#$NAME))
    fi
done

NEXT=$((LAST + 1))
OUTPUT="predictions/$(printf '%03d' "$NEXT")"

# Preserve the input filename, replacing its extension with .tif
BASENAME="$(basename "${INPUT%.*}")"
TIFF="samples/${BASENAME}.tif"

echo "Input:  $INPUT"
echo "GSD:    $GSD"
echo "Output: $OUTPUT"

# Convert the input image to TIFF
uv run tiff_converter.py "$INPUT" "$TIFF"

# Run tree crown detection
uv run tree_count.py "$TIFF" --gsd "$GSD" --out "$OUTPUT"

echo "Finished. Results saved to: $OUTPUT"
# Project Setup and Execution Guide

This guide provides instructions for setting up and running the **Restor Tree Crown Delineation (TCD)** pipeline and the **FastAPI Tree Counting Web Dashboard**.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
  - [Option A: Setup with `uv` (Recommended)](#option-a-setup-with-uv-recommended)
  - [Option B: Setup with standard `pip` and `venv`](#option-b-setup-with-standard-pip-and-venv)
- [Starting the FastAPI Development Server](#starting-the-fastapi-development-server)
  - [Using `uv`](#using-uv)
  - [Using `pip` / standard virtualenv](#using-pip--standard-virtualenv)
  - [Accessing the Dashboard & API Documentation](#accessing-the-dashboard--api-documentation)
  - [Environment Variables](#environment-variables)
- [Scripts Reference](#scripts-reference)
  - [1. `tiff_converter.py` (TIFF Georeferencing Converter)](#1-tiff_converterpy-tiff-georeferencing-converter)
  - [2. `tree_count.py` (Standalone Tree Detection Engine)](#2-tree_countpy-standalone-tree-detection-engine)
  - [3. `main.py` (FastAPI Web Application)](#3-mainpy-fastapi-web-application)
  - [4. `run.sh` (Automated End-to-End Pipeline)](#4-runsh-automated-end-to-end-pipeline)
  - [5. `predictions/collect_overlays.sh` (Batch Overlay Collector)](#5-predictionscollect_overlayssh-batch-overlay-collector)
- [File Format Reference Summary](#file-format-reference-summary)
- [Troubleshooting & Tips](#troubleshooting--tips)

---

## Overview

The repository consists of two primary operational components:

1. **Core Tree Crown Delineation Engine (`tree_count.py` / `tcd_pipeline`)**:
   - **Stage 1 (Semantic Segmentation)**: Leverages pre-trained SegFormer vision models (e.g. `restor/tcd-segformer-mit-b5`) to infer a dense canopy probability map over overlapping 1024×1024 pixel tiles blended with a 2D Hann window.
   - **Stage 2 (Instance Watershed)**: Applies distance-transform watershed segmentation to delineate individual tree crowns from contiguous canopy areas, filtering by minimum diameter and area.
   - **Stage 3 (Export)**: Produces instance overlays (`overlay.png`), pixel coordinates and crown areas (`trees.csv`), instance mask arrays (`labels.npy`), and run metrics (`summary.json`).
2. **FastAPI Web Service & Dashboard (`main.py` + `static/`)**:
   - An interactive web application allowing users to upload aerial imagery, set the Ground Sampling Distance (GSD), and inspect tree counts alongside visual overlay masks directly in their browser.

---

## Prerequisites

- **Python**: Version **3.10** or newer (Python **3.12** is recommended and tested).
- **System Packages (Linux / Ubuntu / Debian)**:
  ```bash
  sudo apt-get update
  sudo apt-get install -y build-essential git gdal-bin libgdal-dev
  ```
- **Hardware**:
  - **CUDA-enabled NVIDIA GPU** (strongly recommended for accelerated model inference).
  - **CPU-only**: Fully supported, but inference on high-resolution imagery will take longer.
- **Model Checkpoints**: Downloaded automatically from the Hugging Face Hub on first inference run (cached under `~/.cache/huggingface/hub/`).

---

## Environment Setup

### Option A: Setup with `uv` (Recommended)

[`uv`](https://docs.astral.sh/uv/) is an extremely fast Python package manager and resolver. This repository includes configuration in `pyproject.toml` and a locked dependency manifest in `uv.lock`.

1. **Install `uv`** (if not already installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   _Or via pip:_ `pip install uv`

2. **Clone the repository and enter the directory**:

   ```bash
   cd /path/to/tcd
   ```

3. **Install dependencies and create virtual environment**:

   ```bash
   # Sync all core dependencies based on uv.lock
   uv sync

   # (Optional) Include test and documentation dependencies
   uv sync --all-extras
   ```

   _Note: `uv` automatically creates and populates a `.venv` directory in the repository._

4. **Activate the virtual environment (optional)**:
   ```bash
   source .venv/bin/activate
   ```
   _(Alternatively, run any command directly with `uv run <command>`, which automatically executes inside the managed environment)._

---

### Option B: Setup with standard `pip` and `venv`

If you prefer using standard Python tools:

1. **Create and activate a virtual environment**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Upgrade packaging build tools**:

   ```bash
   pip install --upgrade pip setuptools wheel
   ```

3. **Install PyTorch with appropriate compute support**:
   - **For Linux with CUDA 12.8**:
     ```bash
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
     ```
   - **For Linux with CUDA 12.4**:
     ```bash
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
     ```
   - **For CPU only**:
     ```bash
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
     ```

4. **Install repository requirements and package in editable mode**:

   ```bash
   # Install dependencies
   pip install -r requirements.txt

   # Install the package in editable mode
   pip install -e .
   ```

   _(Optional) To install testing and documentation tools:_

   ```bash
   pip install -e ".[test,docs]"
   ```

> [!NOTE]
> `detectron2` requires C++ compilation against PyTorch. Installing `torch` and `wheel` before installing `requirements.txt` ensures that `detectron2` compiles cleanly.

---

## Starting the FastAPI Development Server

The web API and user interface are defined in [main.py](file:///home/iann34/src/tcd/main.py). It serves the frontend dashboard from [static/index.html](file:///home/iann34/src/tcd/static/index.html) and exposes the `/count-trees` processing endpoint.

### Using `uv`

Run the server with live reloading enabled:

```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Using `pip` / standard virtualenv

Ensure the virtual environment is activated, then run:

```bash
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

_(Optional: If `fastapi[standard]` is installed, you can also run `uv run fastapi dev main.py` or `fastapi dev main.py`)_

### Accessing the Dashboard & API Documentation

Once Uvicorn displays `Application startup complete`:

- **Web Dashboard**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000) or [http://localhost:8000](http://localhost:8000) in your browser.
- **Interactive Swagger Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/test](http://127.0.0.1:8000/test)

### Environment Variables

You can customize the model loaded during startup using the `TCD_MODEL` environment variable:

```bash
TCD_MODEL="restor/tcd-segformer-mit-b5" uv run uvicorn main:app --reload
```

Other model variants available in the Restor model zoo include `restor/tcd-segformer-mit-b3` and `restor/tcd-segformer-mit-b0`.

---

## Scripts Reference

### 1. `tiff_converter.py` (TIFF Georeferencing Converter)

#### What it does:

[tiff_converter.py](file:///home/iann34/src/tcd/tiff_converter.py) converts standard RGB image files into an uncompressed or Deflate-compressed **GeoTIFF** (`GTiff`) file with artificial georeferencing metadata.
Geospatial tools and raster pipelines (such as `rasterio`) require spatial coordinate reference systems (`CRS`) and affine transforms (`transform`). When using non-georeferenced images (such as standard drone photos or online aerial photos), `tiff_converter.py` wraps the RGB channels into `EPSG:3857` (Web Mercator) coordinates derived from the user-specified Ground Sampling Distance (GSD).

#### How to use:

```bash
# Using uv:
uv run tiff_converter.py <input_image> <output_tiff> [--gsd VALUE]

# Using python:
python tiff_converter.py <input_image> <output_tiff> [--gsd VALUE]
```

#### Example:

```bash
uv run tiff_converter.py src_imgs/green_fields.jpg samples/green_fields.tif --gsd 0.10
```

#### Arguments:

- `input`: Path to source image file (required).
- `output`: Path where the converted GeoTIFF will be saved (required; parent directories are created automatically).
- `--gsd`: Assumed Ground Sampling Distance in metres per pixel (optional float, default `0.10`, must be `> 0`).

#### File Formats:

- **Input Formats**: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`, or unreferenced `.tif`/`.tiff` (any standard raster image format decodable by Pillow).
- **Output Format**: Georeferenced GeoTIFF (`.tif` / `.tiff`):
  - Driver: `GTiff`
  - Compression: `deflate`
  - Data Type: `uint8`, 3 channels (RGB)
  - Coordinate System: `EPSG:3857`
  - Affine Transform: Calculated from image height and assumed GSD.

---

### 2. `tree_count.py` (Standalone Tree Detection Engine)

#### What it does:

[tree_count.py](file:///home/iann34/src/tcd/tree_count.py) executes the full deep learning inference and instance segmentation pipeline directly from the command line:

1. **Resampling**: If the input image's GSD differs from the model's target resolution (0.10 m/pixel), the image is rescaled automatically.
2. **Tiled Inference**: Slices large imagery into 1024×1024 pixel tiles with 128 pixel overlaps, feeds them into the Hugging Face SegFormer model, and stitches them with a 2D Hann window weighting.
3. **Instance Segmentation**: Applies watershed segmentation on the smoothed distance transform map to split canopy into individual tree crowns.
4. **Artifact Generation**: Saves CSV records of crown centroids, raw instance label arrays, visual overlay images, and summary metrics.

#### How to use:

```bash
# Using uv:
uv run tree_count.py <image_path> [--gsd VALUE] [--model MODEL_NAME] [--threshold FLOAT] [--min-crown-diameter METRES] [--min-area M2] [--out OUTPUT_DIR]

# Using python:
python tree_count.py <image_path> --gsd 0.10 --out results/
```

#### Example:

```bash
uv run tree_count.py samples/green_fields.tif --gsd 0.10 --threshold 0.5 --out results/green_fields
```

#### Arguments:

- `image`: Path to the aerial image to analyze (required).
- `--gsd`: Ground Sampling Distance in metres per pixel of the input image (default: assumes `0.10` if omitted).
- `--model`: Hugging Face model repository (default: `restor/tcd-segformer-mit-b5`).
- `--threshold`: Probability threshold for canopy presence (default: `0.5`).
- `--min-crown-diameter`: Minimum tree crown diameter in metres for watershed peak merging (default: `1.5`).
- `--min-area`: Minimum tree crown area in square metres; smaller detections are discarded (default: `2.0`).
- `--out`: Destination directory where result files will be stored (default: `results`).

#### File Formats:

- **Input Formats**: `.tif`, `.tiff`, `.jpg`, `.jpeg`, `.png`.
- **Output Formats (saved into `--out` directory)**:
  - `overlay.png`: RGB PNG image with detected crown perimeters highlighted in yellow, crown centroids marked as blue circles, and total tree count text in the top-left corner.
  - `trees.csv`: CSV spreadsheet containing `id`, `x_px` (centroid X in original image pixels), `y_px` (centroid Y in original image pixels), and `crown_area_m2`.
  - `labels.npy`: NumPy binary array representing 2D pixel-level integer instance labels (`0` = background, `1..N` = individual crowns).
  - `summary.json`: JSON metadata file recording `image`, `tree_count`, `canopy_fraction`, `gsd_input_m`, `gsd_model_m`, and `size_px`.

---

### 3. `main.py` (FastAPI Web Application)

#### What it does:

[main.py](file:///home/iann34/src/tcd/main.py) provides the web backend that wraps the detection capabilities of `tree_count.py` and format conversion of `tiff_converter.py` for web clients and REST integrations:

- Serves the static web dashboard from `static/index.html` at `GET /`.
- Provides a health check endpoint at `GET /test`.
- Implements `POST /count-trees`:
  - Enforces a 50 MB upload size limit and validates file extensions.
  - Automatically invokes `tiff_converter.convert_image` if a JPEG image (`.jpg`, `.jpeg`) is uploaded.
  - Invokes `tree_count.count_trees` in a background threadpool (`run_in_threadpool`) so asynchronous request handling is not blocked by heavy matrix calculations.
  - Returns a JSON response with the total tree count, a Base64-encoded PNG of `overlay.png`, and calculation metadata.

#### How to use:

1. **Start the server**:
   ```bash
   uv run uvicorn main:app --reload --port 8000
   ```
2. **Access via the Web UI**: Navigate to `http://localhost:8000`, drag-and-drop an aerial image, enter the GSD, and click **Count Trees**.
3. **Access via `curl` / HTTP POST**:
   ```bash
   curl -X POST "http://127.0.0.1:8000/count-trees" \
     -F "file=@src_imgs/green_fields.jpg" \
     -F "gsd=0.10"
   ```

#### File Formats:

- **Accepted Upload Formats**: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` (up to 50 MB).
- **Endpoint Response Format**:
  ```json
  {
    "tree_count": 142,
    "image": "<base64_encoded_png_overlay>",
    "image_mime_type": "image/png",
    "summary": {
      "image": "converted.tif",
      "tree_count": 142,
      "canopy_fraction": 0.421,
      "gsd_input_m": 0.1,
      "gsd_model_m": 0.1,
      "size_px": [1024, 1024]
    }
  }
  ```

---

### 4. `run.sh` (Automated End-to-End Pipeline)

#### What it does:

[run.sh](file:///home/iann34/src/tcd/run.sh) is a convenience bash script designed for batch or CLI execution:

1. Validates that the input file exists and parses the `--gsd` flag (defaulting to `0.1` m/px).
2. Creates the directories `samples/` and `predictions/` if they do not already exist.
3. Finds the highest existing numeric run directory under `predictions/` (e.g. `predictions/039`) and assigns the next sequential directory (e.g. `predictions/040`).
4. Invokes `tiff_converter.py` to convert the input image to a georeferenced GeoTIFF in `samples/<basename>.tif`.
5. Executes the tree detection pipeline to compute crowns and save outputs into the assigned predictions directory.

#### How to use:

Make sure the script has execute permissions:

```bash
chmod +x run.sh
```

Run with default GSD (0.10 m/pixel):

```bash
./run.sh src_imgs/green_fields.jpg
```

Run with custom GSD (e.g. 0.05 m/pixel for 5 cm/pixel imagery):

```bash
./run.sh src_imgs/green_fields.jpg --gsd 0.05
```

#### Important note regarding `run.sh`:

Line 74 of `run.sh` calls:

```bash
uv run main.py "$TIFF" --gsd "$GSD" --out "$OUTPUT"
```

Because `main.py` is configured as the FastAPI web server entrypoint, executing `main.py` with CLI flags does not run the detection script. The CLI inference logic is implemented in [tree_count.py](file:///home/iann34/src/tcd/tree_count.py).

If you wish to run the full CLI pipeline through `run.sh`, ensure line 74 invokes `tree_count.py`:

```bash
uv run tree_count.py "$TIFF" --gsd "$GSD" --out "$OUTPUT"
```

_(Or without `uv`: `python tree_count.py "$TIFF" --gsd "$GSD" --out "$OUTPUT"`)_

#### File Formats:

- **Input Formats**: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`.
- **Output Formats & Locations**:
  - `samples/<basename>.tif`: Intermediate georeferenced GeoTIFF.
  - `predictions/<run_id>/`:
    - `overlay.png`: Visual PNG with yellow crown boundaries and blue centroid markers.
    - `trees.csv`: CSV spreadsheet of tree coordinates and areas.
    - `labels.npy`: NumPy array of labeled pixel crowns.
    - `summary.json`: JSON summary of detection statistics.

---

### 5. `predictions/collect_overlays.sh` (Batch Overlay Collector)

#### What it does:

[predictions/collect_overlays.sh](file:///home/iann34/src/tcd/predictions/collect_overlays.sh) scans all subdirectories inside `predictions/`, locates each generated `overlay.png`, and consolidates them into `predictions/images/<run_id>-overlay.png` without overwriting existing files.

#### How to use:

```bash
cd predictions
bash collect_overlays.sh
```

---

## File Format Reference Summary

| Script / Component      | Role                        | Supported Input Formats                                              | Generated Output Formats                                                   |
| :---------------------- | :-------------------------- | :------------------------------------------------------------------- | :------------------------------------------------------------------------- |
| **`tiff_converter.py`** | Georeferencing converter    | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`, `.tif`, `.tiff`            | GeoTIFF (`.tif`, 3-channel RGB, EPSG:3857, Deflate)                        |
| **`tree_count.py`**     | Direct CLI inference engine | GeoTIFF (`.tif`, `.tiff`), `.jpg`, `.jpeg`, `.png`                   | Directory with `overlay.png`, `trees.csv`, `labels.npy`, `summary.json`    |
| **`main.py`**           | FastAPI server & web API    | Multipart upload: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` (≤ 50 MB) | JSON containing `tree_count`, Base64 PNG image overlay, and metadata       |
| **`run.sh`**            | Automated workflow script   | `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`                             | GeoTIFF in `samples/*.tif`, plus full artifact set in `predictions/<XXX>/` |

---

## Troubleshooting & Tips

### 1. Ground Sampling Distance (GSD) Accuracy

The SegFormer model was trained at **0.10 m/pixel (10 cm/pixel)**.

- If your aerial or drone imagery is at 5 cm/pixel, specify `--gsd 0.05`. The pipeline will automatically downsample the input to match the model's receptive field.
- If your imagery is at 20 cm/pixel, specify `--gsd 0.20`. The pipeline will upsample the image accordingly.
- Providing an inaccurate GSD will result in incorrect crown area calculations and either over- or under-segmentation.

### 2. CUDA Out of Memory (OOM)

Because the pipeline tiles imagery in 1024×1024 windows, memory usage is bounded. However, if running on a GPU with limited VRAM:

- Set batch size to `1` in `predict_canopy_prob` inside `tree_count.py`.
- Or force CPU mode by setting `CUDA_VISIBLE_DEVICES=""`.

### 3. Detectron2 Compilation

If installing via `pip` and encountering errors compiling `detectron2`:

- Make sure `torch` is installed first: `python -c "import torch; print(torch.__version__)"`.
- Ensure a C++ compiler (`gcc` / `g++`) is installed: `sudo apt-get install build-essential`.
- When using `uv`, `detectron2` is configured with `no-build-isolation-package = ["detectron2"]` in `pyproject.toml` so that it accesses PyTorch in the active environment during build.

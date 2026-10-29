
import argparse
from pathlib import Path

import numpy as np
from PIL import Image
import rasterio
from rasterio.transform import from_origin


def convert_image(input_path, output_path, assumed_gsd=0.1):
    # Read the source image regardless of whether it is JPG or TIFF.
    with Image.open(input_path) as img:
        img = img.convert("RGB")
        data = np.array(img)
        width, height = img.size

    # Convert RGB layout (height, width, bands) to Rasterio layout.
    data = np.moveaxis(data, -1, 0)

    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 3,
        "dtype": "uint8",
        "crs": "EPSG:3857",
        "transform": from_origin(
            0, height * assumed_gsd, assumed_gsd, assumed_gsd
        ),
        "compress": "deflate",
    }

    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(data)

    print(f"Created: {output_path}")
    print(f"Dimensions: {width} x {height}")
    print(f"Assumed GSD: {assumed_gsd} m/pixel")
    print("Coordinates are artificial, not the real location.")


def main():
    parser = argparse.ArgumentParser(
        description="Convert an image to TIFF with artificial georeferencing."
    )
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output TIFF path")
    parser.add_argument("--gsd", type=float, default=0.1)

    args = parser.parse_args()

    if args.gsd <= 0:
        parser.error("--gsd must be greater than zero")

    if not Path(args.input).is_file():
        parser.error(f"Input file does not exist: {args.input}")

    if Path(args.input).resolve() == Path(args.output).resolve():
        parser.error("Input and output paths must be different")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        convert_image(args.input, str(output), args.gsd)
    except Exception as exc:
        parser.error(f"Conversion failed: {exc}")


if __name__ == "__main__":
    main()

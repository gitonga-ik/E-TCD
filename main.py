import os
import base64
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from tree_count import make_tcd_predictor, count_trees
from tiff_converter import convert_image

MODEL_NAME = os.getenv("TCD_MODEL", "restor/tcd-segformer-mit-b5")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once when the API starts.
    app.state.predict_fn = make_tcd_predictor(MODEL_NAME)
    yield
    # Add model cleanup here if needed.


app = FastAPI(
    title="Tree Counting API",
    description="Counts individual tree crowns in aerial imagery.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def home():
    return FileResponse("static/index.html")


@app.get("/test")
async def root():
    return {"message": "Tree Counting API is running"}


@app.post("/count-trees")
async def count_trees_endpoint(
    file: UploadFile = File(...),
    gsd: float = 0.10,
):
    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Use JPG, JPEG, PNG, or TIFF.",
        )

    if not (0 < gsd <= 100):
        raise HTTPException(
            status_code=400,
            detail="gsd must be greater than 0 and at most 100 metres per pixel.",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="tcd_") as temp_dir:
            work_dir = Path(temp_dir)
            input_path = work_dir / f"input{extension}"

            # Save the uploaded image, enforcing the upload limit.
            size = 0

            with input_path.open("wb") as temp_file:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)

                    if size > MAX_FILE_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail="Image exceeds the 50 MB upload limit.",
                        )

                    temp_file.write(chunk)

            if size == 0:
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded image is empty.",
                )

            processing_path = input_path

            # Convert JPEG uploads using your existing converter.
            if extension in {".jpg", ".jpeg"}:
                processing_path = work_dir / "converted.tif"

                await run_in_threadpool(
                    convert_image,
                    str(input_path),
                    str(processing_path),
                    gsd,
                )

            # Store generated results temporarily.
            output_dir = work_dir / "results"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Run inference outside the async event loop.
            tree_count, result = await run_in_threadpool(
                count_trees,
                str(processing_path),
                app.state.predict_fn,
                gsd,
                0.5,  # Canopy probability threshold
                1.5,  # Minimum crown diameter in metres
                2.0,  # Minimum crown area in square metres
                str(output_dir),
            )

            # The supplied count_trees implementation saves overlay.png.
            overlay_path = output_dir / "overlay.png"

            if not overlay_path.is_file():
                raise RuntimeError("Tree-counting overlay was not generated.")

            image_base64 = base64.b64encode(
                overlay_path.read_bytes()
            ).decode("utf-8")

            return {
                "tree_count": int(tree_count),
                "image": image_base64,
                "image_mime_type": "image/png",
                "summary": result,
            }

    except HTTPException:
        raise

    except Exception as exc:
        # Log the exception for debugging without exposing it to clients.
        print(f"Tree counting failed: {exc}")

        raise HTTPException(
            status_code=500,
            detail="Tree counting failed. Check the server logs.",
        ) from exc

    finally:
        await file.close()
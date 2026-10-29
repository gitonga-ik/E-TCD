"""
Count trees in an aerial image (jpg/png/tif, any size).

Stage 1  TCD semantic model (restor/tcd-segformer-*) -> tree-canopy probability map,
         run with overlapping 1024px tiles and blended.
Stage 2  Instance splitting (distance-transform watershed) turns canopy into
         individual crowns; crowns below a minimum area are discarded.
Stage 3  Returns the count + saves overlay, label map and centroid CSV.

The TCD SegFormer models are semantic only (tree / no tree); the instance step is
done here. Models were trained at 10 cm/px, so pass --gsd (metres per pixel of YOUR
image) and the image is resampled to 0.10 m/px first.

Usage:
  python count_trees_tcd.py image.jpg --gsd 0.05 --out results/
  python count_trees_tcd.py image.jpg --mask-only-test  # (skip model; see __main__)
"""

import argparse, json, csv, os, warnings

warnings.filterwarnings("ignore", category=FutureWarning)
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure, morphology, segmentation, feature

Image.MAX_IMAGE_PIXELS = None
TARGET_GSD = 0.10  # m/px the TCD models were trained at
TILE, OVERLAP = 1024, 128


def load_rgb(path):
    img = np.array(Image.open(path).convert("RGB"))
    return img


def hann2d(n):
    w = np.hanning(n + 2)[1:-1].astype(np.float32)
    return np.outer(w, w)


def predict_canopy_prob(img_rgb, predict_fn, tile=TILE, overlap=OVERLAP, batch=4):
    """predict_fn(list_of_HxWx3_uint8) -> list_of_HxW float prob. Returns HxW prob."""
    H, W, _ = img_rgb.shape
    stride = tile - overlap

    def starts(L):
        if L <= tile:
            return [0]
        s = list(range(0, L - tile, stride)) + [L - tile]
        return sorted(set(s))

    ys, xs = starts(H), starts(W)
    acc = np.zeros((H, W), np.float32)
    wsum = np.zeros((H, W), np.float32)
    coords = [(y, x) for y in ys for x in xs]
    for i in range(0, len(coords), batch):
        chunk = coords[i : i + batch]
        tiles = [img_rgb[y : y + tile, x : x + tile] for y, x in chunk]
        probs = predict_fn(tiles)
        for (y, x), t, p in zip(chunk, tiles, probs):
            h, w = t.shape[:2]
            win = hann2d(max(h, w))[:h, :w] + 1e-3
            acc[y : y + h, x : x + w] += p[:h, :w] * win
            wsum[y : y + h, x : x + w] += win
    return acc / np.maximum(wsum, 1e-6)


def make_tcd_predictor(model_name="restor/tcd-segformer-mit-b5", device=None):
    import torch
    from transformers import AutoImageProcessor, SegformerForSemanticSegmentation

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    proc = AutoImageProcessor.from_pretrained(model_name)
    model = (
        SegformerForSemanticSegmentation.from_pretrained(model_name).to(device).eval()
    )
    # find the "tree" class id from the model config; fall back to 1
    tree_id = 1
    for k, v in model.config.id2label.items():
        if any(s in str(v).lower() for s in ("tree", "canopy")):
            tree_id = int(k)

    @torch.no_grad()
    def predict(tiles):
        inp = proc(images=tiles, return_tensors="pt").to(device)
        logits = model(**inp).logits  # (B, C, h/4, w/4)
        out = []
        for i, t in enumerate(tiles):
            l = torch.nn.functional.interpolate(
                logits[i : i + 1],
                size=t.shape[:2],
                mode="bilinear",
                align_corners=False,
            )
            out.append(l.softmax(1)[0, tree_id].float().cpu().numpy())
        return out

    return predict


def split_instances(
    canopy, gsd, min_crown_diameter_m=1.5, min_area_m2=2.0, smooth_m=0.4
):
    """
    canopy: bool HxW at resolution `gsd` (m/px). Returns int label image, n.
    Peaks of the smoothed distance transform seed a watershed; peaks closer than
    ~min_crown_diameter_m/2 are merged, so smaller values -> more, smaller trees.
    """
    canopy = morphology.remove_small_holes(canopy, int(1.0 / gsd**2))
    canopy = morphology.remove_small_objects(canopy, max(int(min_area_m2 / gsd**2), 1))
    dist = ndi.distance_transform_edt(canopy)
    sigma = max(smooth_m / gsd, 1.0)
    dist_s = ndi.gaussian_filter(dist, sigma)
    min_dist = max(int(min_crown_diameter_m / 2 / gsd), 2)
    peaks = feature.peak_local_max(
        dist_s,
        min_distance=min_dist,
        threshold_abs=0.5 * min_crown_diameter_m / 2 / gsd,
        labels=measure.label(canopy),
        exclude_border=False,
    )
    markers = np.zeros(canopy.shape, np.int32)
    for i, (r, c) in enumerate(peaks, 1):
        markers[r, c] = i
    labels = segmentation.watershed(-dist_s, markers, mask=canopy)
    # drop crowns that are too small
    min_px = max(int(min_area_m2 / gsd**2), 1)
    out = np.zeros_like(labels)
    n = 0
    for r in measure.regionprops(labels):
        if r.area >= min_px:
            n += 1
            out[labels == r.label] = n
    return out, n


def count_trees(
    image_path,
    predict_fn,
    gsd=None,
    threshold=0.5,
    min_crown_diameter_m=1.5,
    min_area_m2=2.0,
    out_dir=None,
):
    img = load_rgb(image_path)
    H0, W0 = img.shape[:2]
    if gsd is None:
        print("WARNING: --gsd not given, assuming image is already 0.10 m/px.")
        gsd = TARGET_GSD
    scale = gsd / TARGET_GSD  # >1 upsample, <1 downsample
    if abs(scale - 1) > 1e-3:
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        img_r = cv2.resize(img, None, fx=scale, fy=scale, interpolation=interp)
    else:
        img_r = img

    prob = predict_canopy_prob(img_r, predict_fn)
    canopy = prob >= threshold
    labels, n = split_instances(canopy, TARGET_GSD, min_crown_diameter_m, min_area_m2)

    result = dict(
        image=os.path.basename(image_path),
        tree_count=int(n),
        canopy_fraction=float(canopy.mean()),
        gsd_input_m=gsd,
        gsd_model_m=TARGET_GSD,
        size_px=[W0, H0],
    )
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        # centroids mapped back to ORIGINAL pixel coordinates
        rows = []
        for r in measure.regionprops(labels):
            cy, cx = r.centroid
            rows.append((r.label, cx / scale, cy / scale, r.area * TARGET_GSD**2))
        with open(os.path.join(out_dir, "trees.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "x_px", "y_px", "crown_area_m2"])
            w.writerows(rows)
        np.save(os.path.join(out_dir, "labels.npy"), labels)
        bnd = segmentation.find_boundaries(labels, mode="outer")
        ov = img_r.copy()
        ov[bnd] = (255, 255, 0)
        for _, x, y, _a in rows:
            cv2.circle(ov, (int(x * scale), int(y * scale)), 4, (255, 0, 0), -1)
        cv2.putText(
            ov,
            f"trees: {n}",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (255, 255, 255),
            4,
        )
        Image.fromarray(ov).save(os.path.join(out_dir, "overlay.png"))
        json.dump(result, open(os.path.join(out_dir, "summary.json"), "w"), indent=2)
    return n, result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--gsd", type=float, help="metres per pixel of the input image")
    ap.add_argument("--model", default="restor/tcd-segformer-mit-b5")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--min-crown-diameter", type=float, default=1.5, help="metres")
    ap.add_argument("--min-area", type=float, default=2.0, help="m^2")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    n, res = count_trees(
        a.image,
        make_tcd_predictor(a.model),
        a.gsd,
        a.threshold,
        a.min_crown_diameter,
        a.min_area,
        a.out,
    )
    print(f"Trees counted: {n}\n{json.dumps(res, indent=2)}")

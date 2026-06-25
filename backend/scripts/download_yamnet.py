"""Download YamNet assets for the audio-event classifier.

The class map (AudioSet labels) has a stable public URL and is fetched
automatically. The ONNX model is pulled from CLIPFORGE_YAMNET_URL if set;
otherwise this prints instructions. The pipeline degrades gracefully (events=[])
until both files exist, so this script is optional but recommended.

Usage:
    python -m backend.scripts.download_yamnet
    # or with a custom ONNX source:
    CLIPFORGE_YAMNET_URL=https://.../yamnet.onnx python -m backend.scripts.download_yamnet
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
import urllib.request

from backend.gpu_config import YAMNET_ONNX_PATH, YAMNET_CLASSMAP_PATH

CLASSMAP_URL = (
    "https://raw.githubusercontent.com/tensorflow/models/master/"
    "research/audioset/yamnet/yamnet_class_map.csv"
)


def _download(url: str, dest: str) -> None:
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    print(f"↓ {url}\n  → {dest}")
    urllib.request.urlretrieve(url, dest)
    print(f"  ✓ {os.path.getsize(dest):,} bytes")


def main() -> int:
    # 1) Class map (stable, always downloadable)
    if os.path.exists(YAMNET_CLASSMAP_PATH):
        print(f"= class map already present: {YAMNET_CLASSMAP_PATH}")
    else:
        _download(CLASSMAP_URL, YAMNET_CLASSMAP_PATH)

    # 2) ONNX model
    if os.path.exists(YAMNET_ONNX_PATH):
        print(f"= model already present: {YAMNET_ONNX_PATH}")
        return 0

    url = os.getenv("CLIPFORGE_YAMNET_URL")
    if url:
        _download(url, YAMNET_ONNX_PATH)
        return 0

    print(
        "\n⚠ YamNet ONNX model not found and CLIPFORGE_YAMNET_URL not set.\n"
        f"  Place a YamNet ONNX file at: {YAMNET_ONNX_PATH}\n"
        "  Options:\n"
        "   • set CLIPFORGE_YAMNET_URL to a direct ONNX download link and re-run, or\n"
        "   • convert the TF-Hub model: pip install tensorflow tensorflow_hub tf2onnx,\n"
        "     then export yamnet to ONNX (mono 16kHz float32 input → [frames,521] output).\n"
        "  Until then audio-event detection stays disabled (pipeline still works).\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

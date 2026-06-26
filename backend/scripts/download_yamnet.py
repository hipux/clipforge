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
    print("downloading " + url + " -> " + dest)
    urllib.request.urlretrieve(url, dest)
    print("  OK " + format(os.path.getsize(dest), ",") + " bytes")


def _build_from_tfhub(dest: str) -> bool:
    """Convert the official TF-Hub YamNet to ONNX (one-time, needs TF + tf2onnx).

    TensorFlow is used ONLY here for the conversion; runtime stays onnxruntime.
    Returns True on success. The exported graph takes a 1-D float32 waveform
    (mono 16 kHz) and returns scores [frames, 521] - exactly what the classifier
    expects.
    """
    try:
        import tensorflow as tf  # noqa
        import tensorflow_hub as hub
        import tf2onnx
    except ImportError:
        print("  installing conversion deps (tensorflow, tensorflow_hub, tf2onnx)...")
        import subprocess, sys as _sys
        rc = subprocess.call([_sys.executable, "-m", "pip", "install", "--quiet",
                              "tensorflow", "tensorflow_hub", "tf2onnx"])
        if rc != 0:
            print("  ERROR could not install conversion dependencies")
            return False
        import tensorflow as tf  # noqa
        import tensorflow_hub as hub
        import tf2onnx

    print("  loading YamNet from TF-Hub (one-time)...")
    yamnet = hub.load("https://tfhub.dev/google/yamnet/1")

    class _Wrap(tf.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        @tf.function(input_signature=[tf.TensorSpec([None], tf.float32, name="waveform")])
        def __call__(self, waveform):
            scores, _embeddings, _spectrogram = self.m(waveform)
            return scores

    wrapped = _Wrap(yamnet)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)

    # Freeze: fold the model's variables (weights) into constants. Without this,
    # tf2onnx exports them as extra REQUIRED graph inputs (15210:0, ...) and the
    # ONNX would demand 27 weight tensors alongside the waveform - unusable.
    from tensorflow.python.framework.convert_to_constants import (
        convert_variables_to_constants_v2,
    )
    print("  freezing variables into constants...")
    concrete = wrapped.__call__.get_concrete_function(
        tf.TensorSpec([None], tf.float32, name="waveform")
    )
    frozen = convert_variables_to_constants_v2(concrete)
    graph_def = frozen.graph.as_graph_def()

    print("  converting frozen graph to ONNX (opset 13)...")
    import tf2onnx
    tf2onnx.convert.from_graph_def(
        graph_def,
        input_names=[t.name for t in frozen.inputs],
        output_names=[t.name for t in frozen.outputs],
        opset=13,
        output_path=dest,
    )
    ok = os.path.exists(dest) and os.path.getsize(dest) > 0
    if ok:
        print("  OK " + format(os.path.getsize(dest), ",") + " bytes")
    return ok


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

    # No direct URL: there is no reliable public pre-built ONNX, so convert the
    # official TF-Hub model once. Disable with CLIPFORGE_YAMNET_NO_BUILD=1.
    if os.getenv("CLIPFORGE_YAMNET_NO_BUILD") != "1":
        print("\nNo CLIPFORGE_YAMNET_URL set - building ONNX from TF-Hub (one-time)...")
        try:
            if _build_from_tfhub(YAMNET_ONNX_PATH):
                return 0
        except Exception as e:
            print("  ERROR auto-build failed: " + str(e))

    print(
        "\n[!] YamNet ONNX model not found and CLIPFORGE_YAMNET_URL not set.\n"
        f"  Place a YamNet ONNX file at: {YAMNET_ONNX_PATH}\n"
        "  Options:\n"
        "   - set CLIPFORGE_YAMNET_URL to a direct ONNX download link and re-run, or\n"
        "   - convert the TF-Hub model: pip install tensorflow tensorflow_hub tf2onnx,\n"
        "     then export yamnet to ONNX (mono 16kHz float32 input -> [frames,521] output).\n"
        "  Until then audio-event detection stays disabled (pipeline still works).\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
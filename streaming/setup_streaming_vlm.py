"""
Setup script for StreamingVLM integration.

The streaming-vlm-qwen3-rocm package is installed via `pip install -e` and
importable directly. This script is kept for path verification and CI checks.

Usage:
    source .venv/bin/activate
    python streaming/setup_streaming_vlm.py
"""
import os
import sys

STREAMING_VLM_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'streaming-vlm-qwen3-rocm')

def setup_streaming_vlm_path():
    """Add streaming-vlm-qwen3-rocm to Python path if not already installed."""
    if os.path.isdir(STREAMING_VLM_PATH):
        if STREAMING_VLM_PATH not in sys.path:
            sys.path.insert(0, STREAMING_VLM_PATH)
        return True
    return False

def check_streaming_vlm_available():
    """Check if streaming_vlm module can be imported."""
    try:
        from streaming_vlm.inference.qwen3.patch_model import convert_qwen3_to_streaming
        from streaming_vlm.inference.streaming_args import StreamingArgs
        return True
    except ImportError as e:
        print(f"StreamingVLM not available: {e}")
        return False

if __name__ == "__main__":
    # Package should be importable directly if installed with pip install -e
    if check_streaming_vlm_available():
        print("StreamingVLM (qwen3-rocm) imports successful!")
    elif setup_streaming_vlm_path():
        print(f"Added {STREAMING_VLM_PATH} to PYTHONPATH")
        if check_streaming_vlm_available():
            print("StreamingVLM imports successful!")
        else:
            print("WARNING: Path added but imports still fail. Install the package:")
            print(f"  pip install -e {STREAMING_VLM_PATH}")
    else:
        print(f"ERROR: streaming-vlm-qwen3-rocm not found at {STREAMING_VLM_PATH}")
        print("Run: git clone https://huggingface.co/s23deepak/streaming-vlm-qwen3-rocm")
        print("     pip install -e streaming-vlm-qwen3-rocm/")

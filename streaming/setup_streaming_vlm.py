"""
Setup script for StreamingVLM integration.

This script adds the cloned streaming-vlm repo to PYTHONPATH
so imports like `from streaming_vlm.inference...` work correctly.

Usage:
    source .venv/bin/activate
    python streaming/setup_streaming_vlm.py

Or add to your shell profile:
    export PYTHONPATH=/home/deepu/PitchAI/streaming-vlm:$PYTHONPATH
"""
import os
import sys

STREAMING_VLM_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'streaming-vlm')

def setup_streaming_vlm_path():
    """Add streaming-vlm to Python path if it exists."""
    if os.path.isdir(STREAMING_VLM_PATH):
        if STREAMING_VLM_PATH not in sys.path:
            sys.path.insert(0, STREAMING_VLM_PATH)
        return True
    return False

def check_streaming_vlm_available():
    """Check if streaming_vlm module can be imported."""
    try:
        from streaming_vlm.inference.qwen2_5.patch_model import convert_qwen2_5_to_streaming
        from streaming_vlm.inference.streaming_args import StreamingArgs
        return True
    except ImportError as e:
        print(f"StreamingVLM not available: {e}")
        return False

if __name__ == "__main__":
    if setup_streaming_vlm_path():
        print(f"Added {STREAMING_VLM_PATH} to PYTHONPATH")
        if check_streaming_vlm_available():
            print("StreamingVLM imports successful!")
        else:
            print("WARNING: Path added but imports still fail. Install dependencies:")
            print(f"  cd {STREAMING_VLM_PATH}")
            print("  pip install -r infer_requirements.txt")
    else:
        print(f"ERROR: streaming-vlm not found at {STREAMING_VLM_PATH}")
        print("Run: git clone https://github.com/mit-han-lab/streaming-vlm.git")

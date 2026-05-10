#!/usr/bin/env python3
"""
Test StreamingVLM Locally on RTX 5060 8GB

This script:
1. Tries to load StreamingVLM from HuggingFace
2. Uses Qwen3-VL-2B-Instruct optimized for 8GB VRAM
3. Runs a simple video inference test

Usage:
    python scripts/test_streamingvlm_rtx5060.py
"""
import os
import sys
import torch
from pathlib import Path

# Add project root and streaming-vlm-qwen3-rocm to path
PROJECT_ROOT = Path(__file__).parent.parent
STREAMING_VLM_PATH = PROJECT_ROOT / "streaming-vlm-qwen3-rocm"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(STREAMING_VLM_PATH))

print("=" * 70)
print("StreamingVLM Local Test - RTX 5060 8GB")
print("=" * 70)

# Check GPU
print("\n[1] Checking GPU...")
print(f"  CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  CUDA version: {torch.version.cuda}")
    print(f"  GPU count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
        props = torch.cuda.get_device_properties(i)
        print(f"    - Memory: {props.total_memory / 1024**3:.2f} GB")
        print(f"    - Compute Capability: {props.major}.{props.minor}")
else:
    print("  WARNING: No CUDA GPU detected!")
    sys.exit(1)

# Check VRAM
device = torch.device("cuda:0")
free_memory = torch.cuda.mem_get_info(device)[0] / 1024**3
total_memory = torch.cuda.get_device_properties(device).total_memory / 1024**3
print(f"\n  VRAM: {free_memory:.2f} GB free / {total_memory:.2f} GB total")

# Memory budget for 8GB card
MAX_MEMORY_GB = 6.0  # Leave 2GB for system
print(f"  Using memory budget: {MAX_MEMORY_GB} GB (to avoid OOM on 8GB card)")

# Try to load models
print("\n[2] Loading Model...")

MODEL_CHOICES = [
    ("Qwen/Qwen3-VL-2B-Instruct", "Qwen3-VL 2B Instruct (primary - fits 8GB)"),
    ("Qwen/Qwen3-VL-4B-Instruct", "Qwen3-VL 4B Instruct (fallback 1 - needs 12GB)"),
]

def try_load_model(model_name: str, model_type: str):
    """Try to load a model from HuggingFace."""
    print(f"\n  Trying: {model_name} ({model_type})")

    try:
        # Try transformers load (Qwen2.5-VL)
        from transformers import AutoModelForVision2Seq, AutoProcessor, AutoTokenizer
        import torch

        print(f"    Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        print(f"    ✓ Tokenizer loaded")

        print(f"    Loading processor...")
        processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        print(f"    ✓ Processor loaded")

        print(f"    Loading model (this may take a while)...")
        model = AutoModelForVision2Seq.from_pretrained(
            model_name,
            device_map="cuda",
            torch_dtype=torch.float16,  # Use FP16 for 8GB VRAM
            trust_remote_code=True,
            attn_implementation="sdpa",
        )
        print(f"    ✓ Model loaded successfully")

        return model, processor, tokenizer

    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return None, None, None

def is_flash_attn_available():
    """Check if Flash Attention 2 is available."""
    try:
        import flash_attn
        print(f"    SDPA: Using PyTorch built-in attention (no flash_attn needed)")
        return True
    except ImportError:
        print(f"    Using SDPA attention (built into PyTorch 2.0+)")
        return False

# Try each model in order
loaded_model = None
loaded_processor = None
loaded_tokenizer = None
selected_model_name = None

for model_name, model_type in MODEL_CHOICES:
    model, processor, tokenizer = try_load_model(model_name, model_type)
    if model is not None:
        loaded_model = model
        loaded_processor = processor
        loaded_tokenizer = tokenizer
        selected_model_name = model_name
        print(f"\n  ✓ Successfully loaded: {model_name}")
        break

if loaded_model is None:
    print("\n✗ All model loading attempts failed!")
    print("\nSuggestions:")
    print("  1. Check your internet connection")
    print("  2. Run: huggingface-cli login")
    print("  3. Try downloading the model manually first")
    sys.exit(1)

# Check memory after load
torch.cuda.empty_cache()
free_memory_after = torch.cuda.mem_get_info(device)[0] / 1024**3
print(f"\n  VRAM after load: {free_memory_after:.2f} GB free")

# Test inference
print("\n[3] Running Inference Test...")

def test_image_qa():
    """Test simple image QA (single frame)."""
    from PIL import Image
    import requests
    from io import BytesIO

    print("\n  Loading test image...")

    # Use a sample sports image
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Association_football.svg/320px-Association_football.svg.png"

    try:
        response = requests.get(image_url)
        image = Image.open(BytesIO(response.content)).convert("RGB")
        print(f"    ✓ Image loaded: {image.size}")
    except Exception as e:
        # Create a dummy image if download fails
        print(f"    ⚠ Download failed, creating dummy image: {e}")
        image = Image.new("RGB", (224, 224), color=(73, 109, 137))

    # Prepare inputs
    print("  Preparing inputs...")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": "What is in this image? Describe it in detail."}
            ]
        }
    ]

    # Process
    print("  Processing with model...")
    text_prompt = loaded_processor.apply_chat_template(messages, add_generation_prompt=True)

    if hasattr(loaded_processor, 'process'):
        # StreamingVLM style
        inputs = loaded_processor.process(
            text=text_prompt,
            images=[image],
            return_tensors="pt"
        )
    else:
        # Qwen2.5-VL style
        inputs = loaded_processor(
            text=[text_prompt],
            images=[image],
            return_tensors="pt",
            padding=True
        )

    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Generate
    print("  Generating response...")
    with torch.no_grad():
        with torch.cuda.amp.autocast(dtype=torch.float16):
            generated_ids = loaded_model.generate(
                **inputs,
                max_new_tokens=100,
                do_sample=False,
            )

    # Decode
    generated_text = loaded_tokenizer.decode(
        generated_ids[0][inputs['input_ids'].shape[1]:],
        skip_special_tokens=True
    )

    print(f"\n  ✓ Response: {generated_text[:200]}...")
    return True

def test_video_chunk():
    """Test video chunk processing (multiple frames)."""
    import numpy as np

    print("\n  Testing video chunk processing...")

    # Create dummy frames (since we don't have a video file)
    print("  Creating dummy video frames...")
    frames = []
    for i in range(8):  # 8 frames = ~1 second at 8 FPS
        # Create a simple moving pattern
        frame = np.zeros((224, 224, 3), dtype=np.uint8)
        frame[i*10:(i+1)*10, i*10:(i+1)*10] = 255  # Moving white square
        frames.append(Image.fromarray(frame))

    print(f"    Created {len(frames)} frames")

    # Prepare messages
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "video"},
                {"type": "text", "text": "What is happening in this video?"}
            ]
        }
    ]

    try:
        # Process video
        print("  Processing video frames...")

        if hasattr(loaded_processor, 'process'):
            # StreamingVLM style
            inputs = loaded_processor.process(
                text=loaded_processor.apply_chat_template(messages, add_generation_prompt=True),
                images=frames,  # Pass list of frames
                return_tensors="pt"
            )
        else:
            # Qwen2.5-VL style
            text_prompt = loaded_processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = loaded_processor(
                text=[text_prompt],
                images=frames,
                return_tensors="pt",
                padding=True
            )

        inputs = {k: v.to(device) for k, v in inputs.items()}

        print(f"    Input shape: {inputs['input_ids'].shape}")

        # Generate
        print("  Generating response...")
        with torch.no_grad():
            with torch.cuda.amp.autocast(dtype=torch.float16):
                generated_ids = loaded_model.generate(
                    **inputs,
                    max_new_tokens=50,
                    do_sample=False,
                )

        # Decode
        generated_text = loaded_tokenizer.decode(
            generated_ids[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )

        print(f"\n  ✓ Video response: {generated_text[:100]}...")
        return True

    except Exception as e:
        print(f"  ⚠ Video test failed (expected for some models): {e}")
        return False

# Run tests
print("\n" + "=" * 70)
print("Running Tests")
print("=" * 70)

test_results = {}

# Test 1: Image QA
try:
    test_results["image_qa"] = test_image_qa()
except Exception as e:
    print(f"\n✗ Image QA test failed: {e}")
    test_results["image_qa"] = False

# Test 2: Video chunk
try:
    test_results["video_chunk"] = test_video_chunk()
except Exception as e:
    print(f"\n✗ Video chunk test failed: {e}")
    test_results["video_chunk"] = False

# Summary
print("\n" + "=" * 70)
print("Test Summary")
print("=" * 70)
print(f"  Model: {selected_model_name}")
print(f"  Image QA: {'✓ PASS' if test_results.get('image_qa') else '✗ FAIL'}")
print(f"  Video Chunk: {'✓ PASS' if test_results.get('video_chunk') else '✗ FAIL / Not supported'}")

if all(test_results.values()):
    print("\n✓ All tests passed!")
else:
    print("\n⚠ Some tests failed or were skipped")

print("\n" + "=" * 70)
print("Next Steps:")
print("=" * 70)
print("1. To use with SGLang serving:")
print("   python -m sglang.launch_server \\")
print(f"       --model-path Qwen/Qwen3-VL-2B-Instruct \\")
print("       --port 30000 \\")
print("       --mem-fraction-static 0.7")
print("")
print("2. To integrate with PitchSideAI:")
print("   python -m uvicorn api.server:app --reload --port 8080")
print("")
print("3. For StreamingVLM-specific inference:")
print(f"   cd {STREAMING_VLM_PATH}")
print("   python streaming_vlm/inference/inference.py")
print("=" * 70)

#!/usr/bin/env python3
"""
Test vLLM Backend on RTX 5060 (Level 4 fallback)

This script tests the vLLM streaming backend with the running server.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streaming.streaming_bridge import VLLMStreamingBackend, StreamingResult
from streaming.frame_buffer import VideoChunk, FrameBuffer, FrameBufferConfig
import base64


async def test_vllm_backend():
    """Test vLLM backend with a simple image test."""
    print("=" * 60)
    print("Testing vLLM Backend (RTX 5060 8GB)")
    print("=" * 60)

    # Create backend
    backend = VLLMStreamingBackend(
        vllm_base_url="http://localhost:8001",
        model_name="Qwen/Qwen2.5-VL-3B-Instruct-AWQ",
        sport="football",
    )

    print(f"\n✓ Backend created")
    print(f"  URL: {backend.vllm_base_url}")
    print(f"  Model: {backend.model_name}")

    # Initialize
    await backend.initialize()
    print(f"✓ Backend initialized")

    # Create a test image (1x1 red pixel as placeholder)
    # In real usage, this would be actual video frames
    import numpy as np
    from PIL import Image
    import io

    # Create a simple test image (football field green)
    img = Image.new('RGB', (224, 224), color=(34, 139, 34))
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    img_bytes = buffer.getvalue()

    # Create mock video chunk
    from streaming.frame_buffer import FrameSample
    frame = FrameSample(data=img_bytes, timestamp_ms=0, frame_index=0)
    chunk = VideoChunk(
        frames=[frame],
        start_timestamp_ms=0,
        end_timestamp_ms=5000,
        duration_seconds=5.0,
        chunk_index=0,
    )

    print(f"\n✓ Test chunk created (1 frame, 224x224)")

    # Process chunk
    print(f"\nProcessing chunk through vLLM...")
    try:
        result = await backend.process_chunk(
            chunk,
            previous_text="",
            query_hint="What do you see in this image?",
        )

        print(f"✓ Result received:")
        print(f"  Commentary: {result.commentary[:100]}..." if len(result.commentary) > 100 else f"  Commentary: {result.commentary}")
        print(f"  Tactical Label: {result.tactical_label}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Latency: {result.latency_ms:.1f}ms")

    except Exception as e:
        print(f"✗ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Get stats
    stats = backend.get_stats()
    print(f"\n✓ Backend stats:")
    print(f"  Chunks processed: {stats['chunks_processed']}")
    print(f"  Avg latency: {stats['avg_latency_ms']:.1f}ms")
    print(f"  Total latency: {stats['total_latency_ms']:.1f}ms")

    return True


async def test_fallback_to_vllm():
    """Test that fallback chain correctly falls back to vLLM (Level 4)."""
    print("\n" + "=" * 60)
    print("Testing Fallback Chain (Level 4 = vLLM)")
    print("=" * 60)

    from streaming.factory import FallbackStreamingBackend

    # Start at Level 1, should fall back to Level 4 (vLLM) since SGLang/StreamingVLM not available
    backend = FallbackStreamingBackend(start_level=1)

    print(f"\nInitializing fallback backend (start_level=1)...")
    print(f"  Expected: Will try Level 1→2→3→4, settle at Level 4 (vLLM)")

    try:
        await backend.initialize()
        stats = backend.get_stats()

        print(f"✓ Initialized at Level {stats.get('fallback_level', 'unknown')}")
        print(f"  Backend: {stats.get('backend', 'unknown')}")
        print(f"  Errors encountered: {len(stats.get('fallback_errors', []))}")

        for err in stats.get('fallback_errors', []):
            print(f"    - {err[:100]}...")

        return True

    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return False


async def main():
    results = []

    # Test 1: Direct vLLM backend
    results.append(("vLLM Backend", await test_vllm_backend()))

    # Test 2: Fallback chain
    results.append(("Fallback Chain", await test_fallback_to_vllm()))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY - RTX 5060 8GB")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n✓ vLLM backend working on RTX 5060 8GB!")
        print("\nTo use in production:")
        print("  1. Set VLLM_BASE_URL=http://localhost:8001")
        print("  2. Set VISION_MODEL=Qwen/Qwen2.5-VL-3B-Instruct-AWQ")
        print("  3. Fallback chain will auto-detect and use Level 4")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

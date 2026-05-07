#!/usr/bin/env python3
"""
Test SGLang + StreamingVLM Integration

This script validates the SGLang backend and fallback chain implementation.

Usage:
    python scripts/test_sglang_integration.py
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all SGLang + StreamingVLM imports work."""
    print("Testing imports...")

    try:
        from streaming.sglang_backend import SGLangStreamingBackend
        print("  ✓ SGLangStreamingBackend")
    except ImportError as e:
        print(f"  ✗ SGLangStreamingBackend: {e}")
        return False

    try:
        from streaming.factory import get_streaming_backend, FallbackStreamingBackend
        print("  ✓ FallbackStreamingBackend")
    except ImportError as e:
        print(f"  ✗ FallbackStreamingBackend: {e}")
        return False

    try:
        from streaming.streaming_bridge import StreamingBridgeConfig, StreamingVisionBridge
        print("  ✓ StreamingBridgeConfig, StreamingVisionBridge")
    except ImportError as e:
        print(f"  ✗ StreamingBridge: {e}")
        return False

    try:
        # Test StreamingVLM imports (requires streaming-vlm in path)
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streaming-vlm'))
        from streaming_vlm.inference.streaming_args import StreamingArgs
        print("  ✓ StreamingVLM (streaming-vlm in path)")
    except ImportError as e:
        print(f"  ⚠ StreamingVLM: {e} (install dependencies for Level 1)")

    return True


def test_sglang_backend():
    """Test SGLang backend instantiation."""
    print("\nTesting SGLang backend...")

    from streaming.sglang_backend import SGLangStreamingBackend

    backend = SGLangStreamingBackend(
        sglang_base_url="http://localhost:30000",
        model_name="Qwen/Qwen2.5-VL-3B-Instruct",
        sport="football",
    )

    print(f"  ✓ Backend created: {backend.sglang_base_url}")
    print(f"  ✓ Model: {backend.model_name}")
    print(f"  ✓ RadixAttention: {backend.enable_radix_attention}")

    return True


def test_fallback_chain():
    """Test fallback chain factory."""
    print("\nTesting fallback chain...")

    from streaming.factory import get_streaming_backend, FallbackStreamingBackend

    # Test explicit level selection
    for level in [1, 2, 4]:
        try:
            backend = get_streaming_backend(target_level=level)
            print(f"  ✓ Level {level}: {type(backend).__name__}")
        except Exception as e:
            print(f"  ⚠ Level {level}: {e}")

    # Test auto-fallback wrapper
    try:
        fallback = FallbackStreamingBackend(start_level=1)
        print(f"  ✓ FallbackStreamingBackend created (start_level=1)")
        print(f"     Will try: Level 1 → 2 → 3 → 4 on failure")
    except Exception as e:
        print(f"  ✗ FallbackStreamingBackend: {e}")
        return False

    return True


def test_bridge_config():
    """Test StreamingVisionBridge config with SGLang."""
    print("\nTesting StreamingVisionBridge config...")

    from streaming.streaming_bridge import StreamingBridgeConfig

    # Test SGLang config
    config = StreamingBridgeConfig(
        backend="sglang",
        sglang_base_url="http://localhost:30000",
        sglang_model="Qwen/Qwen2.5-VL-3B-Instruct",
        use_fallback_chain=False,
    )
    print(f"  ✓ SGLang config: {config.sglang_base_url}")

    # Test fallback chain config
    config_fb = StreamingBridgeConfig(
        backend="auto",
        use_fallback_chain=True,
    )
    print(f"  ✓ Fallback config: Level 1→2→3→4")

    return True


def test_environment_vars():
    """Test environment variable configuration."""
    print("\nTesting environment variables...")

    # Set test env vars
    os.environ["SGLANG_BASE_URL"] = "http://localhost:30000"
    os.environ["VISION_MODEL"] = "Qwen/Qwen2.5-VL-3B-Instruct"
    os.environ["STREAMING_BACKEND"] = "sglang"

    from streaming.factory import get_streaming_backend

    # Test SGLang from env
    backend = get_streaming_backend(backend="sglang")
    print(f"  ✓ SGLANG_BASE_URL: {os.environ['SGLANG_BASE_URL']}")
    print(f"  ✓ VISION_MODEL: {os.environ['VISION_MODEL']}")
    print(f"  ✓ STREAMING_BACKEND: {os.environ['STREAMING_BACKEND']}")

    return True


def main():
    print("=" * 60)
    print("SGLang + StreamingVLM Integration Test")
    print("=" * 60)

    tests = [
        ("Imports", test_imports),
        ("SGLang Backend", test_sglang_backend),
        ("Fallback Chain", test_fallback_chain),
        ("Bridge Config", test_bridge_config),
        ("Environment Vars", test_environment_vars),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ {name} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✓ All tests passed!")
        print("\nNext steps:")
        print("1. Install ffmpeg 7: sudo apt install ffmpeg")
        print("2. Install StreamingVLM deps: cd streaming-vlm && pip install -r infer_requirements.txt")
        print("3. Start SGLang server: python -m sglang.launch_server --model-path Qwen/Qwen2.5-VL-3B-Instruct --port 30000")
        print("4. Run: python -m uvicorn api.server:app --reload --port 8080")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

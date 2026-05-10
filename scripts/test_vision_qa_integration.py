#!/usr/bin/env python3
"""
Full Integration Test: StreamingVisionBridge → QAAgent Pipeline

This test verifies the end-to-end flow:
1. Server receives video frames via WebSocket /ws/video/streaming
2. StreamingVisionBridge processes frames → produces tactical analysis
3. Vision context is stored in ConnectionManager
4. Fan asks a question via WebSocket
5. QAAgent retrieves vision context and uses it in the answer

Usage:
    source .venv/bin/activate
    python scripts/test_vision_qa_integration.py
"""
import asyncio
import base64
import json
import sys
import websockets
from pathlib import Path

# Try to import cv2 for frame extraction
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("Warning: cv2 not available, will use raw video bytes")


async def extract_frames_from_video(video_path: str, max_frames: int = 5):
    """Extract frames from video file as base64 JPEGs."""
    if not HAS_CV2:
        print(f"  Cannot extract frames without cv2, will use raw video bytes")
        return None

    frames = []
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"  Error: Cannot open video {video_path}")
        return None

    frame_count = 0
    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        frames.append(frame_b64)
        frame_count += 1

    cap.release()
    print(f"  Extracted {len(frames)} frames from video")
    return frames


async def run_integration_test(
    server_url: str = "ws://localhost:8765/ws/video/streaming",
    video_path: str = None
):
    """
    Run full integration test with WebSocket connection.

    Test flow:
    1. Connect to WebSocket /ws/video/streaming
    2. Send init message
    3. Send frame messages
    4. Wait for vision analysis
    5. Send tactical question
    6. Verify answer includes vision context
    """
    print("=" * 70)
    print("FULL INTEGRATION TEST: Vision-Powered Q&A")
    print("=" * 70)

    # Load video frames if available
    video_frames = None
    if video_path and Path(video_path).exists():
        print(f"\n1. Loading video: {video_path}")
        video_frames = await extract_frames_from_video(video_path, max_frames=5)

    print(f"\n2. Connecting to WebSocket: {server_url}")

    try:
        async with websockets.connect(
            server_url,
            ping_timeout=10,
            additional_headers={"Origin": "http://localhost:5173"}
        ) as ws:
            print("  ✓ Connected")

            # Step 1: Send init message
            print("\n3. Sending init message...")
            init_msg = {
                "type": "init",
                "home_team": "Real Madrid",
                "away_team": "Barcelona",
                "sport": "soccer",
                "config": {
                    "backend": "vllm",
                    "chunk_interval_seconds": 3,  # Faster for testing
                    "max_chunk_frames": 4,  # Minimum allowed
                    "target_fps": 4.0,
                }
            }
            await ws.send(json.dumps(init_msg))

            # Wait for ready message
            response = await asyncio.wait_for(ws.recv(), timeout=30)
            init_result = json.loads(response)
            print(f"  Server response: {init_result.get('type')}")
            if init_result.get('type') == 'ready':
                print(f"  {init_result.get('message', '')}")
            else:
                print(f"  Unexpected response: {init_result}")

            # Step 2: Send frame messages
            if video_frames:
                print(f"\n4. Sending {len(video_frames)} video frames...")
                for i, frame_b64 in enumerate(video_frames):
                    frame_msg = {
                        "type": "frame",
                        "frame_b64": frame_b64,
                        "timestamp_ms": i * 1000,
                        "keyframe": i == 0,
                    }
                    await ws.send(json.dumps(frame_msg))
                    print(f"  Sent frame {i+1}/{len(video_frames)}")

                    # Wait for commentary/vision analysis response
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=20)
                        result = json.loads(response)
                        msg_type = result.get("type", "unknown")

                        if msg_type == "commentary":
                            tactical_label = result.get("tactical_label", "N/A")
                            confidence = result.get("confidence", 0)
                            commentary = result.get("text", "")[:150]
                            print(f"  ✓ Commentary: label=\"{tactical_label}\", confidence={confidence:.2f}")
                            print(f"    Text: {commentary}...")
                        elif msg_type == "status":
                            print(f"  Status: {result.get('message', '')}")
                        else:
                            print(f"  Response type: {msg_type}")
                    except asyncio.TimeoutError:
                        print(f"  Timeout waiting for response on frame {i+1}")

                # Wait for processing
                print("\n5. Waiting for vision processing to complete...")
                await asyncio.sleep(3)

                # Check for any pending messages
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=2)
                    result = json.loads(response)
                    print(f"  Additional message: {result.get('type')} - {result.get('message', '')[:100]}")
                except asyncio.TimeoutError:
                    pass
            else:
                print("\n4. Skipping frame send (no video frames available)")

            # Step 3: Send tactical question
            print("\n6. Sending tactical question...")
            question = "What formation are they playing?"
            query_msg = {
                "type": "query",
                "text": question,
            }
            await ws.send(json.dumps(query_msg))
            print(f"  Question: {question}")

            # Step 4: Receive answer
            print("\n7. Waiting for answer...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=30)
                result = json.loads(response)

                print(f"\n{'=' * 70}")
                print("RESULTS")
                print("=" * 70)
                print(f"Answer type: {result.get('type')}")
                print(f"Source: {result.get('source', 'N/A')}")
                vision_ctx = result.get('vision_context')
                print(f"Vision context: {vision_ctx}")

                if result.get('type') == 'answer':
                    print(f"\nAnswer:\n{result.get('text', 'No answer text')}")
                elif result.get('type') == 'commentary':
                    print(f"\nCommentary:\n{result.get('text', 'No commentary')}")
                print("=" * 70)

                # Verify vision context was used
                if vision_ctx:
                    print("\n✓ SUCCESS: Vision context was included in the response!")
                    print(f"  Tactical label: {vision_ctx.get('tactical_label', 'N/A')}")
                    print(f"  Confidence: {vision_ctx.get('confidence', 0):.2f}")
                    return True
                else:
                    print("\n⚠ No vision context in response")
                    print("  This could mean:")
                    print("  - Vision processing didn't produce high-confidence results")
                    print("  - Vision backend is at fallback level 4 (no vision)")
                    return False

            except asyncio.TimeoutError:
                print("\n✗ ERROR: Timeout waiting for answer")
                return False

    except websockets.exceptions.ConnectionClosed as e:
        print(f"\n✗ ERROR: WebSocket connection closed: {e}")
        return False
    except ConnectionRefusedError:
        print(f"\n✗ ERROR: Connection refused. Is the server running?")
        print("  Start server with: python -m uvicorn api.server:app --reload --port 8765")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Test vision-powered Q&A integration")
    parser.add_argument(
        "--server",
        type=str,
        default="ws://localhost:8765/ws/video/streaming",
        help="WebSocket server URL"
    )
    parser.add_argument(
        "--video",
        type=str,
        default="test_images/short_test_video.mp4",
        help="Path to test video file"
    )

    args = parser.parse_args()

    success = await run_integration_test(args.server, args.video)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

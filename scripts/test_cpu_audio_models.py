#!/usr/bin/env python3
"""
CPU audio model smoke tests for PitchAI.

This script checks whether local CPU-side ASR/TTS options are usable without
touching the live StreamingVLM GPU path.

Examples:
  python3 scripts/test_cpu_audio_models.py
  python3 scripts/test_cpu_audio_models.py --audio /tmp/question.wav
  python3 scripts/test_cpu_audio_models.py --asr-model tiny --tts-output /tmp/tts.wav
  python3 scripts/test_cpu_audio_models.py --skip-asr --tts-engine pyttsx3
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


DEFAULT_TTS_TEXT = (
    "Roma have risen from their ruins. PitchAI is ready for live commentary."
)


@dataclass
class CheckResult:
    name: str
    status: str
    latency_ms: Optional[float] = None
    detail: str = ""
    output_path: Optional[str] = None


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _write_silence_wav(path: Path, seconds: float = 2.0, sample_rate: int = 16000) -> None:
    frame_count = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frame_count)


def _existing_audio_or_silence(audio_path: Optional[str]) -> tuple[Path, Optional[tempfile.TemporaryDirectory[str]]]:
    if audio_path:
        path = Path(audio_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Audio file does not exist: {path}")
        return path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="pitchai-audio-")
    path = Path(temp_dir.name) / "silence.wav"
    _write_silence_wav(path)
    return path, temp_dir


def test_faster_whisper(audio_path: Path, model_name: str, language: str) -> CheckResult:
    start = _now_ms()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return CheckResult(
            name="asr:faster-whisper",
            status="skipped",
            detail=(
                "faster-whisper is not installed. Install with: "
                "pip install faster-whisper"
            ),
        )

    try:
        load_start = _now_ms()
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        load_ms = _now_ms() - load_start

        transcribe_start = _now_ms()
        segments, info = model.transcribe(
            str(audio_path),
            language=language,
            beam_size=1,
            vad_filter=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        transcribe_ms = _now_ms() - transcribe_start
        total_ms = _now_ms() - start
        detected_language = getattr(info, "language", None) or language

        return CheckResult(
            name="asr:faster-whisper",
            status="ok",
            latency_ms=round(total_ms, 1),
            detail=(
                f"model={model_name}, language={detected_language}, "
                f"load_ms={load_ms:.1f}, transcribe_ms={transcribe_ms:.1f}, "
                f"text={text!r}"
            ),
        )
    except Exception as exc:
        return CheckResult(
            name="asr:faster-whisper",
            status="failed",
            latency_ms=round(_now_ms() - start, 1),
            detail=str(exc),
        )


def test_piper_tts(text: str, voice_path: Optional[str], output_path: Path) -> CheckResult:
    start = _now_ms()
    piper = shutil.which("piper")
    if not piper:
        return CheckResult(
            name="tts:piper",
            status="skipped",
            detail="piper executable not found on PATH.",
        )
    if not voice_path:
        return CheckResult(
            name="tts:piper",
            status="skipped",
            detail="provide --piper-voice /path/to/voice.onnx to test Piper.",
        )

    voice = Path(voice_path).expanduser().resolve()
    if not voice.exists():
        return CheckResult(
            name="tts:piper",
            status="failed",
            detail=f"Piper voice file does not exist: {voice}",
        )

    try:
        proc = subprocess.run(
            [piper, "--model", str(voice), "--output_file", str(output_path)],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            return CheckResult(
                name="tts:piper",
                status="failed",
                latency_ms=round(_now_ms() - start, 1),
                detail=(proc.stderr or proc.stdout or "piper failed").strip()[:500],
            )
        return CheckResult(
            name="tts:piper",
            status="ok",
            latency_ms=round(_now_ms() - start, 1),
            detail=f"text_chars={len(text)}, bytes={output_path.stat().st_size}",
            output_path=str(output_path),
        )
    except Exception as exc:
        return CheckResult(
            name="tts:piper",
            status="failed",
            latency_ms=round(_now_ms() - start, 1),
            detail=str(exc),
        )


def test_pyttsx3_tts(text: str, output_path: Path) -> CheckResult:
    start = _now_ms()
    try:
        import pyttsx3
    except ImportError:
        return CheckResult(
            name="tts:pyttsx3",
            status="skipped",
            detail="pyttsx3 is not installed. Install with: pip install pyttsx3",
        )

    try:
        engine = pyttsx3.init()
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        if not output_path.exists() or output_path.stat().st_size == 0:
            return CheckResult(
                name="tts:pyttsx3",
                status="failed",
                latency_ms=round(_now_ms() - start, 1),
                detail="pyttsx3 completed but did not create an audio file.",
            )
        return CheckResult(
            name="tts:pyttsx3",
            status="ok",
            latency_ms=round(_now_ms() - start, 1),
            detail=f"text_chars={len(text)}, bytes={output_path.stat().st_size}",
            output_path=str(output_path),
        )
    except Exception as exc:
        return CheckResult(
            name="tts:pyttsx3",
            status="failed",
            latency_ms=round(_now_ms() - start, 1),
            detail=str(exc),
        )


def browser_tts_hint() -> CheckResult:
    return CheckResult(
        name="tts:browser-speech-synthesis",
        status="manual",
        detail=(
            "Use the existing frontend/browser SpeechSynthesis path for the "
            "lowest-friction demo TTS test."
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test CPU ASR/TTS options for the PitchAI demo."
    )
    parser.add_argument("--audio", help="Path to a WAV/MP3/WebM question clip for ASR.")
    parser.add_argument("--asr-model", default="tiny", help="faster-whisper model size/name.")
    parser.add_argument("--language", default="en", help="ASR language hint.")
    parser.add_argument("--skip-asr", action="store_true", help="Skip faster-whisper ASR.")
    parser.add_argument(
        "--tts-engine",
        choices=("browser", "piper", "pyttsx3", "all"),
        default="all",
        help="Which CPU/local TTS path to check.",
    )
    parser.add_argument("--tts-text", default=DEFAULT_TTS_TEXT, help="Text to synthesize.")
    parser.add_argument("--tts-output", default="/tmp/pitchai_cpu_tts.wav")
    parser.add_argument("--piper-voice", help="Path to a Piper .onnx voice model.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def print_human(results: list[CheckResult]) -> None:
    print("PitchAI CPU Audio Smoke Test")
    print("=" * 31)
    for result in results:
        latency = f" ({result.latency_ms:.1f} ms)" if result.latency_ms is not None else ""
        print(f"{result.name}: {result.status}{latency}")
        if result.detail:
            print(f"  {result.detail}")
        if result.output_path:
            print(f"  output: {result.output_path}")


def main() -> int:
    args = parse_args()
    results: list[CheckResult] = []

    temp_dir: Optional[tempfile.TemporaryDirectory[str]] = None
    try:
        if not args.skip_asr:
            audio_path, temp_dir = _existing_audio_or_silence(args.audio)
            results.append(test_faster_whisper(audio_path, args.asr_model, args.language))

        tts_output = Path(args.tts_output).expanduser().resolve()
        tts_output.parent.mkdir(parents=True, exist_ok=True)

        if args.tts_engine in {"browser", "all"}:
            results.append(browser_tts_hint())
        if args.tts_engine in {"piper", "all"}:
            piper_output = tts_output.with_name(f"{tts_output.stem}.piper{tts_output.suffix}")
            results.append(test_piper_tts(args.tts_text, args.piper_voice, piper_output))
        if args.tts_engine in {"pyttsx3", "all"}:
            pyttsx3_output = tts_output.with_name(f"{tts_output.stem}.pyttsx3{tts_output.suffix}")
            results.append(test_pyttsx3_tts(args.tts_text, pyttsx3_output))

        if args.json:
            print(json.dumps([asdict(result) for result in results], indent=2))
        else:
            print_human(results)

        return 1 if any(result.status == "failed" for result in results) else 0
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Unit tests for latency benchmarking components.
"""

import unittest
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.benchmark_latency import LatencyBenchmarker, BenchmarkResult


class TestLatencyBenchmarker(unittest.IsolatedAsyncioTestCase):
    """Test cases for LatencyBenchmarker."""

    async def test_nfr1_result_structure(self):
        """Test that NFR-1 results have correct structure."""
        benchmarker = LatencyBenchmarker(runs=5)
        result = await benchmarker.measure_nfr1_audio_qa()

        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.nfr, "NFR-1")
        self.assertEqual(result.target, 3500)
        self.assertEqual(result.unit, "ms")
        self.assertEqual(len(result.measurements), 5)
        self.assertGreaterEqual(result.p50, 0)
        self.assertGreaterEqual(result.p95, 0)
        self.assertGreaterEqual(result.p99, 0)

    async def test_nfr1_passes_with_simulated_latency(self):
        """Test that simulated latency passes NFR-1 target."""
        benchmarker = LatencyBenchmarker(runs=10)
        result = await benchmarker.measure_nfr1_audio_qa()

        # Simulated latency should be well under 3.5s target
        self.assertTrue(result.passed)
        self.assertLess(result.p95, 3500)

    async def test_nfr2_result_structure(self):
        """Test that NFR-2 results have correct structure."""
        benchmarker = LatencyBenchmarker(runs=5)
        result = await benchmarker.measure_nfr2_language_switch()

        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.nfr, "NFR-2")
        self.assertEqual(result.target, 3000)
        self.assertEqual(result.target_silence, 500)
        self.assertGreater(len(result.measurements), 0)
        self.assertGreater(len(result.silence_measurements), 0)

    async def test_nfr2_silence_within_target(self):
        """Test that simulated silence is within 500ms target."""
        benchmarker = LatencyBenchmarker(runs=10)
        result = await benchmarker.measure_nfr2_language_switch()

        self.assertTrue(result.passed)
        if result.p95_silence is not None:
            self.assertLess(result.p95_silence, 500)

    async def test_nfr3_passes_with_simulated_cold_start(self):
        """Test that simulated cold start passes NFR-3 target."""
        benchmarker = LatencyBenchmarker(runs=5)
        result = await benchmarker.measure_nfr3_cold_start()

        # Simulated cold start should be well under 20s target
        self.assertTrue(result.passed)
        self.assertLess(result.p95, 20000)

    async def test_nfr4_passes_with_simulated_ttft(self):
        """Test that simulated TTFT passes NFR-4 target."""
        benchmarker = LatencyBenchmarker(runs=10)
        result = await benchmarker.measure_nfr4_commentary_ttft()

        # Simulated TTFT should be well under 500ms target
        self.assertTrue(result.passed)
        self.assertLess(result.p95, 500)

    async def test_nfr5_passes_with_simulated_fps(self):
        """Test that simulated FPS passes NFR-5 target."""
        benchmarker = LatencyBenchmarker(runs=5)
        result = await benchmarker.measure_nfr5_vision_fps()

        # Simulated FPS should be above 5 FPS target
        self.assertTrue(result.passed)
        self.assertGreaterEqual(result.p95, 5.0)

    async def test_run_all_returns_five_results(self):
        """Test that run_all returns exactly 5 results."""
        benchmarker = LatencyBenchmarker(runs=3)
        results = await benchmarker.run_all()

        self.assertEqual(len(results), 5)
        self.assertEqual([r.nfr for r in results], [
            "NFR-1", "NFR-2", "NFR-3", "NFR-4", "NFR-5"
        ])


if __name__ == '__main__':
    unittest.main()

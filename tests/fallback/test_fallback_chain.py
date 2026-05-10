#!/usr/bin/env python3
"""
Unit tests for fallback chain validation components.
"""

import unittest
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.test_fallback_chain import FallbackChainTester, FallbackTestResult


class TestFallbackChainTester(unittest.IsolatedAsyncioTestCase):
    """Test cases for FallbackChainTester."""

    async def test_level_1_capabilities(self):
        """Test Level 1 (full capability) expectations."""
        tester = FallbackChainTester()
        expected = tester.EXPECTED_CAPABILITIES[1]

        self.assertEqual(expected['temporal_continuity'], True)
        self.assertEqual(expected['streaming_optimizations'], True)
        self.assertEqual(expected['temporal_scrub'], True)
        self.assertEqual(expected['name'], 'SGLang + StreamingVLM (Full Capability)')

    async def test_level_2_capabilities(self):
        """Test Level 2 (loses StreamingVLM optimizations) expectations."""
        tester = FallbackChainTester()
        expected = tester.EXPECTED_CAPABILITIES[2]

        self.assertEqual(expected['temporal_continuity'], True)
        self.assertEqual(expected['streaming_optimizations'], False)
        self.assertEqual(expected['temporal_scrub'], True)

    async def test_level_3_capabilities(self):
        """Test Level 3 (loses temporal scrub) expectations."""
        tester = FallbackChainTester()
        expected = tester.EXPECTED_CAPABILITIES[3]

        self.assertEqual(expected['temporal_continuity'], False)
        self.assertEqual(expected['streaming_optimizations'], False)
        self.assertEqual(expected['temporal_scrub'], False)

    async def test_level_4_capabilities(self):
        """Test Level 4 (no temporal continuity) expectations."""
        tester = FallbackChainTester()
        expected = tester.EXPECTED_CAPABILITIES[4]

        self.assertEqual(expected['temporal_continuity'], False)
        self.assertEqual(expected['streaming_optimizations'], False)
        self.assertEqual(expected['temporal_scrub'], False)

    async def test_invalid_level_returns_error(self):
        """Test that invalid level returns error result."""
        tester = FallbackChainTester()
        result = await tester.test_fallback_level(99)

        self.assertFalse(result.passed)
        self.assertEqual(result.level, 99)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("Invalid fallback level", result.errors[0])

    async def test_valid_level_returns_result(self):
        """Test that valid level returns proper result."""
        tester = FallbackChainTester()
        result = await tester.test_fallback_level(1)

        self.assertIsInstance(result, FallbackTestResult)
        self.assertEqual(result.level, 1)
        self.assertIsNotNone(result.timestamp)

    async def test_activation_time_under_30_seconds(self):
        """Test that simulated activation time is under 30 seconds."""
        tester = FallbackChainTester()
        activation_times = await tester.test_fallback_activation_time()

        for level, time_ms in activation_times.items():
            self.assertLess(time_ms, 30000, f"Level {level} activation exceeded 30s")

    async def test_ux_message_is_calm(self):
        """Test that UX messages are calm (no alarm words)."""
        tester = FallbackChainTester()
        ux_results = await tester.test_ux_graceful_degradation()

        for test_name, passed in ux_results.items():
            self.assertTrue(passed, f"{test_name} failed - UX message not calm")

    async def test_run_all_tests_returns_four_results(self):
        """Test that run_all_tests returns exactly 4 results."""
        tester = FallbackChainTester()
        results = await tester.run_all_tests()

        self.assertEqual(len(results), 4)
        self.assertEqual([r.level for r in results], [1, 2, 3, 4])


class TestFallbackChainCapabilities(unittest.IsolatedAsyncioTestCase):
    """Test capability matrix for fallback levels."""

    async def test_capability_degradation_pattern(self):
        """Test that capabilities degrade correctly across levels."""
        tester = FallbackChainTester()

        # Level 1: All capabilities
        self.assertTrue(tester.EXPECTED_CAPABILITIES[1]['temporal_continuity'])
        self.assertTrue(tester.EXPECTED_CAPABILITIES[1]['streaming_optimizations'])
        self.assertTrue(tester.EXPECTED_CAPABILITIES[1]['temporal_scrub'])

        # Level 2: Loses streaming optimizations only
        self.assertTrue(tester.EXPECTED_CAPABILITIES[2]['temporal_continuity'])
        self.assertFalse(tester.EXPECTED_CAPABILITIES[2]['streaming_optimizations'])
        self.assertTrue(tester.EXPECTED_CAPABILITIES[2]['temporal_scrub'])

        # Level 3 & 4: All capabilities lost
        for level in [3, 4]:
            self.assertFalse(tester.EXPECTED_CAPABILITIES[level]['temporal_continuity'])
            self.assertFalse(tester.EXPECTED_CAPABILITIES[level]['streaming_optimizations'])
            self.assertFalse(tester.EXPECTED_CAPABILITIES[level]['temporal_scrub'])


if __name__ == '__main__':
    unittest.main()

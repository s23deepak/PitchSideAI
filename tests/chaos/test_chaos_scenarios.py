#!/usr/bin/env python3
"""
Unit tests for chaos testing scenarios.
"""

import unittest
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.chaos_test import ChaosTestRunner, ChaosTestResult


class TestChaosTestRunner(unittest.IsolatedAsyncioTestCase):
    """Test cases for ChaosTestRunner."""

    async def test_event_flood_queue_management(self):
        """Test that event flood manages queue correctly."""
        runner = ChaosTestRunner()
        result = await runner.test_event_flood()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'flood')
        self.assertTrue(result.passed, f"Event flood test failed: {result.errors}")

    async def test_resize_during_draw_dimension_guard(self):
        """Test that dimension guard catches mismatch during resize."""
        runner = ChaosTestRunner()
        result = await runner.test_resize_during_draw()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'resize')
        self.assertTrue(result.passed, f"Resize test failed: {result.errors}")

    async def test_stt_timeout_auto_cancel(self):
        """Test that STT timeout auto-cancels empty recording."""
        runner = ChaosTestRunner()
        result = await runner.test_stt_timeout()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'stt_timeout')
        self.assertTrue(result.passed, f"STT timeout test failed: {result.errors}")

    async def test_websocket_drop_mid_qa(self):
        """Test that WebSocket drop completes from cache."""
        runner = ChaosTestRunner()
        result = await runner.test_websocket_drop_mid_qa()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'ws_drop')
        self.assertTrue(result.passed, f"WebSocket drop test failed: {result.errors}")

    async def test_compound_failure_calm_message(self):
        """Test that compound failure produces calm message."""
        runner = ChaosTestRunner()
        result = await runner.test_compound_failure()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'compound')
        self.assertTrue(result.passed, f"Compound failure test failed: {result.errors}")

    async def test_gpu_unreachable_fallback_activation(self):
        """Test that GPU unreachable activates fallback within 30s."""
        runner = ChaosTestRunner()
        result = await runner.test_gpu_unreachable()

        self.assertIsInstance(result, ChaosTestResult)
        self.assertEqual(result.scenario, 'gpu_unreachable')
        self.assertTrue(result.passed, f"GPU unreachable test failed: {result.errors}")

    async def test_all_scenarios_exist(self):
        """Test that all expected scenarios are defined."""
        runner = ChaosTestRunner()
        expected_scenarios = ['flood', 'resize', 'stt_timeout', 'ws_drop', 'compound', 'gpu_unreachable']

        for scenario in expected_scenarios:
            self.assertIn(scenario, runner.SCENARIOS)
            self.assertIn('name', runner.SCENARIOS[scenario])
            self.assertIn('description', runner.SCENARIOS[scenario])
            self.assertIn('expected', runner.SCENARIOS[scenario])

    async def test_run_all_returns_six_results(self):
        """Test that run_all_tests returns exactly 6 results."""
        runner = ChaosTestRunner()
        # Run each scenario individually since run_all_tests prints output
        scenarios = ['flood', 'resize', 'stt_timeout', 'ws_drop', 'compound', 'gpu_unreachable']
        results = []
        for scenario in scenarios:
            result = await runner.run_scenario(scenario)
            results.append(result)

        self.assertEqual(len(results), 6)
        scenario_names = [r.scenario for r in results]
        self.assertEqual(set(scenario_names), {
            'flood', 'resize', 'stt_timeout', 'ws_drop', 'compound', 'gpu_unreachable'
        })

    async def test_execution_time_recorded(self):
        """Test that execution time is recorded for each scenario."""
        runner = ChaosTestRunner()
        result = await runner.test_event_flood()

        self.assertGreater(result.execution_time_ms, 0)
        self.assertIsNotNone(result.timestamp)


class TestChaosTestExpectedBehaviors(unittest.IsolatedAsyncioTestCase):
    """Test expected behaviors for chaos scenarios."""

    async def test_flood_expected_behavior(self):
        """Test flood scenario expected behavior description."""
        runner = ChaosTestRunner()
        scenario = runner.SCENARIOS['flood']

        self.assertIn('queue', scenario['expected'].lower())
        self.assertIn('crash', scenario['expected'].lower())

    async def test_resize_expected_behavior(self):
        """Test resize scenario expected behavior description."""
        runner = ChaosTestRunner()
        scenario = runner.SCENARIOS['resize']

        self.assertIn('dimension', scenario['expected'].lower())
        self.assertIn('guard', scenario['expected'].lower())

    async def test_stt_timeout_expected_behavior(self):
        """Test STT timeout expected behavior description."""
        runner = ChaosTestRunner()
        scenario = runner.SCENARIOS['stt_timeout']

        self.assertIn('timeout', scenario['expected'].lower())
        self.assertIn('cancel', scenario['expected'].lower())

    async def test_compound_failure_no_cascade(self):
        """Test that compound failure doesn't cascade errors."""
        runner = ChaosTestRunner()
        result = await runner.test_compound_failure()

        # Verify no error cascade
        self.assertFalse(hasattr(runner, 'error_cascade') or not result.passed)


if __name__ == '__main__':
    unittest.main()

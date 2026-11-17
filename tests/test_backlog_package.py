from __future__ import annotations

import unittest
from pathlib import Path

import sentinel
from sentinel.backlog import gates, hooks, refinement, rollup, status


class BacklogPackageTests(unittest.TestCase):
    def test_backlog_lifecycle_lives_in_the_package(self):
        self.assertTrue(callable(gates.evaluate_story_gates))
        self.assertTrue(callable(hooks.mark_stale_stories_for_spec_units))
        self.assertTrue(callable(refinement.apply_backlog_refinement))
        self.assertTrue(callable(rollup.backlog_status))
        self.assertTrue(callable(status.update_story_status))

    def test_flat_compatibility_shims_are_gone(self):
        # IMP-338: nothing imported the flat modules any more.
        package_dir = Path(sentinel.__file__).resolve().parent
        for name in ("backlog_gates", "backlog_hooks", "backlog_refinement", "backlog_rollup", "backlog_status"):
            self.assertFalse((package_dir / f"{name}.py").exists(), name)


if __name__ == "__main__":
    unittest.main()

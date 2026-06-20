from __future__ import annotations

import unittest

from sentinel.backlog import gates, hooks, refinement, rollup, status
from sentinel import backlog_gates, backlog_hooks, backlog_refinement, backlog_rollup, backlog_status


class BacklogPackageTests(unittest.TestCase):
    def test_flat_backlog_modules_remain_compatibility_shims(self):
        self.assertIs(backlog_gates.evaluate_story_gates, gates.evaluate_story_gates)
        self.assertIs(backlog_hooks.mark_stale_stories_for_spec_units, hooks.mark_stale_stories_for_spec_units)
        self.assertIs(backlog_refinement.apply_backlog_refinement, refinement.apply_backlog_refinement)
        self.assertIs(backlog_rollup.backlog_status, rollup.backlog_status)
        self.assertIs(backlog_status.update_story_status, status.update_story_status)


if __name__ == "__main__":
    unittest.main()

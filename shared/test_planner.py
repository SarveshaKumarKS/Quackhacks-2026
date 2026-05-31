#!/usr/bin/env python3
import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import planner


class TestPlanner(unittest.TestCase):

    def test_compound_then(self):
        self.assertTrue(planner.looks_compound("summarize reddit then draft an email to sam"))

    def test_compound_multiple_ands(self):
        self.assertTrue(planner.looks_compound(
            "summarize the subreddit and draft an email and update the doc and open notes"))

    def test_compound_enumeration(self):
        self.assertTrue(planner.looks_compound("do these: 1. scrape 2. summarize"))

    def test_simple_not_compound(self):
        self.assertFalse(planner.looks_compound("send an email to sam"))
        self.assertFalse(planner.looks_compound("summarize the machine learning subreddit"))

    def test_plan_prompt_contains_goal(self):
        self.assertIn("scrape and email", planner.build_plan_prompt("scrape and email"))

    def test_normalize_strings(self):
        self.assertEqual(planner.normalize_steps(["a", " b ", ""]), ["a", "b"])

    def test_normalize_dicts(self):
        steps = [{"task": "scrape reddit"}, {"step": "draft email"}, {"nope": "x"}]
        self.assertEqual(planner.normalize_steps(steps), ["scrape reddit", "draft email"])

    def test_normalize_caps_length(self):
        self.assertEqual(len(planner.normalize_steps([str(i) for i in range(20)])), planner.MAX_STEPS)


if __name__ == "__main__":
    unittest.main()

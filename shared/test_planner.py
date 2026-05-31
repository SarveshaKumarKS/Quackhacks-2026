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

    def test_next_noun_not_compound(self):
        # "next meeting"/"next email" must NOT trigger the planner (bare " next " bug).
        self.assertFalse(planner.looks_compound("when is my next meeting"))
        self.assertFalse(planner.looks_compound("read my next email"))
        # genuine sequencing with 'next' still counts
        self.assertTrue(planner.looks_compound("summarize reddit, next draft an email"))

    def test_plan_prompt_contains_goal(self):
        self.assertIn("scrape and email", planner.build_plan_prompt("scrape and email"))

    def test_normalize_strings(self):
        self.assertEqual(planner.normalize_steps(["a", " b ", ""]), ["a", "b"])

    def test_normalize_dicts(self):
        steps = [{"task": "scrape reddit"}, {"step": "draft email"}, {"nope": "x"}]
        self.assertEqual(planner.normalize_steps(steps), ["scrape reddit", "draft email"])

    def test_normalize_caps_length(self):
        self.assertEqual(len(planner.normalize_steps([str(i) for i in range(20)])), planner.MAX_STEPS)

    def test_context_only_step_detection(self):
        context = "[Result of step 1]: useful ML findings"
        self.assertTrue(planner.should_use_context_only("Summarize the top 3 useful items identified.", context))
        self.assertTrue(planner.should_use_context_only("Append the generated summary to the doc.", context))
        self.assertFalse(planner.should_use_context_only("Search reddit for ML posts.", context))
        self.assertFalse(planner.should_use_context_only("Summarize the top 3 useful items identified.", ""))

    def test_context_transform_prompt_uses_prior_results(self):
        prompt = planner.build_context_transform_prompt("Summarize the generated summary", "prior facts")
        self.assertIn("prior facts", prompt)
        self.assertIn("Do not browse", prompt)


if __name__ == "__main__":
    unittest.main()

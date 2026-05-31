#!/usr/bin/env python3
import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import web_intent


class TestWebIntent(unittest.TestCase):

    def test_extract_explicit_url(self):
        self.assertEqual(
            web_intent.extract_first_url("scrape https://example.com/page please"),
            "https://example.com/page",
        )

    def test_extract_bare_domain(self):
        self.assertEqual(web_intent.extract_first_url("summarize news.ycombinator.com"),
                         "https://news.ycombinator.com")

    def test_extract_none(self):
        self.assertIsNone(web_intent.extract_first_url("what is the latest on AI chips"))

    def test_build_target_url(self):
        self.assertEqual(web_intent.build_target("read https://x.com"), "https://x.com")

    def test_build_target_search(self):
        t = web_intent.build_target("latest AI chip news")
        self.assertTrue(t.startswith(web_intent.DUCKDUCKGO_HTML))
        self.assertIn("latest", t)

    def test_answer_prompt_contains_goal_and_truncates(self):
        long_text = "x" * 20000
        p = web_intent.build_web_answer_prompt("summarize this", long_text, max_chars=100)
        self.assertIn("summarize this", p)
        # body snippet capped at max_chars
        self.assertLessEqual(p.count("x"), 100)


if __name__ == "__main__":
    unittest.main()

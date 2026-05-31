#!/usr/bin/env python3
import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import mcp_intent


class TestMcpIntent(unittest.TestCase):

    def test_affirmative_basic(self):
        for t in ("yes", "Yes please", "yep", "send it", "go ahead", "ok send the email", "lgtm"):
            self.assertTrue(mcp_intent.is_affirmative(t), t)

    def test_negative_basic(self):
        for t in ("no", "cancel", "stop", "never mind", "abort that"):
            self.assertTrue(mcp_intent.is_negative(t), t)

    def test_dont_send_is_not_affirmative(self):
        # Critical safety case: 'don't send' contains 'send' but must NOT approve.
        self.assertFalse(mcp_intent.is_affirmative("don't send"))
        self.assertFalse(mcp_intent.is_affirmative("do not send it"))
        self.assertTrue(mcp_intent.is_negative("don't send"))

    def test_revision_is_neither(self):
        t = "change the subject to Q3 results and make it shorter"
        self.assertFalse(mcp_intent.is_affirmative(t))
        self.assertFalse(mcp_intent.is_negative(t))

    def test_empty_is_neither(self):
        self.assertFalse(mcp_intent.is_affirmative(""))
        self.assertFalse(mcp_intent.is_negative(""))

    def test_standalone_confirmation_detection(self):
        for t in ("yes", "ok", "send it", "no", "cancel", "do not send"):
            self.assertTrue(mcp_intent.is_standalone_confirmation(t), t)
        self.assertFalse(mcp_intent.is_standalone_confirmation("yes, draft an email to Sam"))
        self.assertFalse(mcp_intent.is_standalone_confirmation("open calculator"))

    def test_email_prompt_contains_goal_and_revision(self):
        p = mcp_intent.build_email_draft_prompt("email Sam about lunch", "sam@x.com", "make it formal")
        self.assertIn("email Sam about lunch", p)
        self.assertIn("sam@x.com", p)
        self.assertIn("make it formal", p)

    def test_email_prompt_includes_memory_context(self):
        p = mcp_intent.build_email_draft_prompt(
            "email Sam", memory_context="Relevant memory: Sam prefers short notes")
        self.assertIn("Sam prefers short notes", p)

    def test_doc_prompt_contains_goal(self):
        self.assertIn("quarterly recap", mcp_intent.build_doc_content_prompt("quarterly recap"))

    def test_format_calendar_empty(self):
        self.assertEqual(mcp_intent.format_calendar_events([]), "No upcoming events found.")

    def test_format_calendar_events(self):
        out = mcp_intent.format_calendar_events([{"start": "2026-06-01T10:00", "title": "Demo"}])
        self.assertIn("Demo", out)
        self.assertIn("2026-06-01T10:00", out)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import sys
import os
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routing import classify_goal, is_reddit_scrape_shortcut, parse_app_launch
from contract import CommandModel


class TestRouting(unittest.TestCase):

    def test_email_routes_to_mcp_gmail(self):
        d = classify_goal("Send an email to the client about the demo")
        self.assertEqual(d.route, "mcp")
        self.assertEqual(d.mcp_capability, "gmail")
        self.assertTrue(d.is_background_safe)
        self.assertFalse(d.needs_foreground)

    def test_calendar_routes_to_mcp_calendar(self):
        d = classify_goal("What meetings are on my calendar tomorrow?")
        self.assertEqual(d.route, "mcp")
        self.assertEqual(d.mcp_capability, "calendar")

    def test_doc_routes_to_mcp_docs(self):
        d = classify_goal("Append the summary to the research doc")
        self.assertEqual(d.route, "mcp")
        self.assertEqual(d.mcp_capability, "docs")

    def test_sheet_routes_to_mcp_sheets(self):
        d = classify_goal("Log this run as a row in the activity log spreadsheet")
        self.assertEqual(d.route, "mcp")
        self.assertEqual(d.mcp_capability, "sheets")

    def test_activity_sheet_routes_to_mcp_sheets(self):
        for goal in (
            "Log the completion of these tasks in the activity sheet.",
            "Add this to the activity tracker.",
            "Log this run in the tracking sheet.",
        ):
            d = classify_goal(goal)
            self.assertEqual(d.route, "mcp", goal)
            self.assertEqual(d.mcp_capability, "sheets", goal)

    def test_web_search_routes_to_browser(self):
        d = classify_goal("Search Google for the latest on Apple stock")
        self.assertEqual(d.route, "browser")
        self.assertIsNone(d.mcp_capability)
        self.assertTrue(d.is_background_safe)

    def test_scrape_routes_to_browser(self):
        d = classify_goal("Scrape r/MachineLearning and give me insights")
        self.assertEqual(d.route, "browser")

    def test_native_app_routes_to_desktop(self):
        d = classify_goal("Open Spotlight and launch Notes")
        self.assertEqual(d.route, "desktop")
        self.assertTrue(d.needs_foreground)
        self.assertFalse(d.is_background_safe)

    def test_mcp_wins_over_browser(self):
        # "search" (browser) + "email" (mcp) -> mcp must win.
        d = classify_goal("Search my email for the invoice")
        self.assertEqual(d.route, "mcp")
        self.assertEqual(d.mcp_capability, "gmail")

    def test_reddit_shortcut_detection(self):
        self.assertTrue(is_reddit_scrape_shortcut("summarize the machine learning subreddit"))
        self.assertTrue(is_reddit_scrape_shortcut("scrape reddit r/MachineLearning"))
        self.assertFalse(is_reddit_scrape_shortcut("open finder"))

    def test_empty_goal_defaults_to_desktop(self):
        d = classify_goal("")
        self.assertEqual(d.route, "desktop")

    def test_mcp_verbs_valid_in_contract(self):
        for action in ("send_email", "append_doc", "append_sheet", "read_calendar"):
            cmd = CommandModel(path="mcp", action=action, args={})
            self.assertEqual(cmd.path, "mcp")
            self.assertEqual(cmd.action, action)

    def test_parse_app_launch_basic(self):
        self.assertEqual(parse_app_launch("open the Calculator app"), "Calculator")
        self.assertEqual(parse_app_launch("launch Safari"), "Safari")
        self.assertEqual(parse_app_launch("open Notes"), "Notes")
        self.assertEqual(parse_app_launch("start System Settings"), "System Settings")

    def test_parse_app_launch_rejects_non_apps(self):
        # Web / MCP 'open' phrasings must NOT be treated as native app launches.
        for g in ("open reddit", "open my email", "open the google doc",
                  "open https://x.com", "what is the latest news"):
            self.assertIsNone(parse_app_launch(g), g)

    def test_observation_accepts_background_lock(self):
        # Regression: the failsafe returns screen_state='background_lock'. If the
        # contract rejects it, the agent-server 500s exactly when B is backgrounded.
        from contract import ObservationModel
        obs = ObservationModel(screen_state="background_lock",
                               result={"success": False, "error_message": "blocked"})
        self.assertEqual(obs.screen_state, "background_lock")


if __name__ == "__main__":
    unittest.main()

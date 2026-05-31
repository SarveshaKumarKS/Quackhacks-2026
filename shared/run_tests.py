#!/usr/bin/env python3
import sys
import os
import unittest

# Ensure we can import from the contract file in the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pydantic import ValidationError
from contract import CommandModel, ObservationModel, MailNotificationModel

class TestMessageContract(unittest.TestCase):
    
    def test_command_model_valid(self):
        """Verify that a correct command parses properly."""
        data = {
            "type": "action",
            "path": "computer_use",
            "action": "click",
            "args": {"x": 500, "y": 600}
        }
        command = CommandModel(**data)
        self.assertEqual(command.type, "action")
        self.assertEqual(command.path, "computer_use")
        self.assertEqual(command.action, "click")
        self.assertEqual(command.args["x"], 500)

    def test_command_model_invalid_path(self):
        """Verify that an invalid path triggers validation error."""
        data = {
            "type": "action",
            "path": "invalid_path_name",  # Invalid path
            "action": "click"
        }
        with self.assertRaises(ValidationError):
            CommandModel(**data)

    def test_command_model_invalid_action(self):
        """Verify that an invalid action triggers validation error."""
        data = {
            "type": "action",
            "path": "browser_use",
            "action": "sing_a_song"  # Invalid action
        }
        with self.assertRaises(ValidationError):
            CommandModel(**data)

    def test_observation_model_valid(self):
        """Verify that a correct observation parses correctly."""
        data = {
            "type": "observation",
            "screenshot_url": "http://localhost:8421/frame.jpg",
            "screen_state": "ok",
            "result": {"success": True}
        }
        obs = ObservationModel(**data)
        self.assertEqual(obs.type, "observation")
        self.assertEqual(obs.screen_state, "ok")
        self.assertTrue(obs.result["success"])

    def test_observation_model_invalid_state(self):
        """Verify that an invalid screen state triggers validation error."""
        data = {
            "type": "observation",
            "screen_state": "broken"  # Invalid state
        }
        with self.assertRaises(ValidationError):
            ObservationModel(**data)

    def test_mail_notification_model_valid(self):
        """Verify mail notification validation succeeds."""
        data = {
            "type": "mail_notification",
            "unread_count": 3,
            "latest_sender": "test@example.com",
            "latest_subject": "Hello Doppelganger",
            "timestamp": "2026-05-30T14:15:00Z"
        }
        mail = MailNotificationModel(**data)
        self.assertEqual(mail.type, "mail_notification")
        self.assertEqual(mail.unread_count, 3)
        self.assertEqual(mail.latest_sender, "test@example.com")

if __name__ == "__main__":
    unittest.main()

import pytest
from pydantic import ValidationError
from contract import CommandModel, ObservationModel, MailNotificationModel

def test_command_model_valid():
    """Verify that a correct command serializes and parses properly."""
    data = {
        "type": "action",
        "path": "computer_use",
        "action": "click",
        "args": {"x": 500, "y": 600}
    }
    command = CommandModel(**data)
    assert command.type == "action"
    assert command.path == "computer_use"
    assert command.action == "click"
    assert command.args["x"] == 500

def test_command_model_invalid_path():
    """Verify that an invalid path triggers validation error."""
    data = {
        "type": "action",
        "path": "invalid_path_name",  # Invalid path
        "action": "click"
    }
    with pytest.raises(ValidationError):
        CommandModel(**data)

def test_command_model_invalid_action():
    """Verify that an invalid action triggers validation error."""
    data = {
        "type": "action",
        "path": "browser_use",
        "action": "sing_a_song"  # Invalid action
    }
    with pytest.raises(ValidationError):
        CommandModel(**data)

def test_observation_model_valid():
    """Verify that a correct observation parses correctly."""
    data = {
        "type": "observation",
        "screenshot_url": "http://localhost:8421/frame.jpg",
        "screen_state": "ok",
        "result": {"success": True}
    }
    obs = ObservationModel(**data)
    assert obs.type == "observation"
    assert obs.screen_state == "ok"
    assert obs.result["success"] is True

def test_observation_model_invalid_state():
    """Verify that an invalid screen state triggers validation error."""
    data = {
        "type": "observation",
        "screen_state": "broken"  # Invalid state
    }
    with pytest.raises(ValidationError):
        ObservationModel(**data)

def test_mail_notification_model_valid():
    """Verify mail notification validation succeeds."""
    data = {
        "type": "mail_notification",
        "unread_count": 3,
        "latest_sender": "test@example.com",
        "latest_subject": "Hello Doppelganger",
        "timestamp": "2026-05-30T14:15:00Z"
    }
    mail = MailNotificationModel(**data)
    assert mail.type == "mail_notification"
    assert mail.unread_count == 3
    assert mail.latest_sender == "test@example.com"

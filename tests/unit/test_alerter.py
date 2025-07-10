import logging
from datetime import datetime

from alerter import LogAlerter  # Assuming alerter.py is in the root or PYTHONPATH includes it


def test_log_alerter_send_alert_logging(caplog):
    """Test that LogAlerter.send_alert logs messages correctly via logging."""
    alerter = LogAlerter()
    subject = "Test Subject for Logging"
    message = "This is a test alert message for logging."

    caplog.set_level(logging.INFO)  # Ensure caplog captures INFO level messages

    alerter.send_alert(subject, message)

    assert len(caplog.records) == 1  # Should be one log record
    record = caplog.records[0]

    assert record.levelname == "INFO"
    expected_log_message = f"ALERT - Subject: {subject}\n{message}\n---"
    assert record.message == expected_log_message


def test_log_alerter_send_alert_printing(capsys):
    """Test that LogAlerter.send_alert prints messages correctly to stdout."""
    alerter = LogAlerter()
    subject = "Test Subject for Printing"
    message = "This is a test alert message for printing."

    alerter.send_alert(subject, message)

    captured = capsys.readouterr()

    # Check stdout part
    timestamp_prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # We can only check the relatively static part of the string due to the timestamp
    expected_print_suffix = (
        f" CONSOLE ALERT: {subject}\n{message}\n\n"  # Two newlines: one in f-string, one from print
    )

    assert expected_print_suffix in captured.out
    assert captured.out.startswith(f"[{timestamp_prefix[:17]}")  # Check most of timestamp


def test_log_alerter_send_alert_with_recipients(caplog, capsys):
    """Test that LogAlerter.send_alert ignores recipients but otherwise works."""
    alerter = LogAlerter()
    subject = "Test Subject with Recipients"
    message = "This message has recipients specified, but they should be ignored."
    recipients = ["test1@example.com", "test2@example.com"]

    caplog.set_level(logging.INFO)
    alerter.send_alert(subject, message, recipients=recipients)

    # Check logging part (same as without recipients)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "INFO"
    expected_log_message = f"ALERT - Subject: {subject}\n{message}\n---"
    assert record.message == expected_log_message

    # Check stdout part (same as without recipients)
    captured = capsys.readouterr()
    timestamp_prefix = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    expected_print_suffix = f" CONSOLE ALERT: {subject}\n{message}\n\n"
    assert expected_print_suffix in captured.out
    assert captured.out.startswith(f"[{timestamp_prefix[:17]}")


# To run these tests:
# pytest tests/unit/test_alerter.py
# Ensure that the root of your project is in PYTHONPATH or run pytest from the root.
# For example: python -m pytest tests/unit/test_alerter.py
# (if alerter.py is in the root)

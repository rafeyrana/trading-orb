# Module for handling alerts

from abc import ABC, abstractmethod
import logging
from datetime import datetime
import config

# Basic logging setup (if not already configured elsewhere, e.g. main)
# logging.basicConfig(level=config.LOG_LEVEL.upper(), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Alerter(ABC):
    """
    Abstract base class for alerters.
    """
    @abstractmethod
    def send_alert(self, subject: str, message: str, recipients: list = None):
        """
        Sends an alert.

        Args:
            subject (str): The subject of the alert (e.g., stock symbol or alert type).
            message (str): The detailed alert message.
            recipients (list, optional): A list of recipients. Specific to implementation.
                                         Defaults to None.
        """
        pass

class LogAlerter(Alerter):
    """
    An alerter that logs messages to the console (or a log file if logging is configured).
    """
    def send_alert(self, subject: str, message: str, recipients: list = None):
        """
        Logs the alert message. Recipients are ignored for this alerter.

        Args:
            subject (str): The subject of the alert.
            message (str): The detailed alert message.
            recipients (list, optional): Ignored for LogAlerter.
        """
        full_message = f"ALERT - Subject: {subject}\n{message}\n---"
        # Using the root logger configured in main.py or strategy.py for now
        # If specific alerter logging is needed, configure logger here.
        logger.info(full_message)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CONSOLE ALERT: {subject}\n{message}\n")


if __name__ == '__main__':
    # Configure basic logging for testing this module directly
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    logger.info("Testing Alerter module...")

    log_alerter = LogAlerter()

    test_subject = "TEST_SYMBOL Breakout"
    test_message = (
        "This is a test alert message.\n"
        "Price: $100.00\n"
        "Condition: Crossed above ORB High."
    )

    logger.info("\nSending a test alert via LogAlerter:")
    log_alerter.send_alert(test_subject, test_message)

    logger.info("\nLogAlerter test complete. Check console output for the alert.")

import logging
from plyer import notification

logger = logging.getLogger(__name__)

def notify_user(title: str, message: str, app_name="Study Agent"):
    """Triggers a native desktop notification."""
    logger.info(f"Notification: {title} - {message}")
    try:
        notification.notify(
            title=title,
            message=message,
            app_name=app_name,
            timeout=5
        )
    except Exception as e:
        logger.error(f"Failed to show notification: {e}")

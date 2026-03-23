from firebase_admin import messaging
import logging

logger = logging.getLogger(__name__)


def send_push_notification(token: str, title: str, body: str, data: dict = None):
    """
    Send a push notification via Firebase Cloud Messaging.
    
    Args:
        token: FCM token of the recipient
        title: Notification title
        body: Notification body
        data: Optional additional data to send (max 10 pairs, values must be strings)
    
    Returns:
        Message ID if successful, None otherwise
    """
    if not token:
        logger.warning("send_push_notification: No token provided")
        return None

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=data or {},
            token=token,
        )

        message_id = messaging.send(message)
        logger.info(f"Push notification sent successfully. Message ID: {message_id}")
        return message_id

    except Exception as e:
        logger.error(f"Failed to send push notification to {token}: {str(e)}")
        return None

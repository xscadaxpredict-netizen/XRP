#website/fcm_utils.py
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from django.conf import settings

def get_access_token():
    try:
        credentials = service_account.Credentials.from_service_account_file(
            settings.FCM_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        credentials.refresh(Request())
        return credentials.token
    except FileNotFoundError:
        import logging
        logging.getLogger(__name__).warning("FCM Service Account file not found. Notifications will not be sent.")
        return None


FCM_SERVICE_ACCOUNT_FILE = "/Users/shashank/Downloads/sample2/sample/xplbs/xentrix-ed813-firebase-adminsdk-fbsvc-b42147e8c4.json"
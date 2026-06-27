# website/fcm.py
import requests
from .models import FCMToken
from .fcm_utils import get_access_token

def send_push_fcm(user, title, body):
    access_token = get_access_token()
    print("🔥 ACCESS TOKEN GENERATED")

    # Load project ID from service account file
    try:
        from django.conf import settings
        import json
        with open(settings.FCM_SERVICE_ACCOUNT_FILE) as f:
            service_account_data = json.load(f)
            project_id = service_account_data.get('project_id')
    except Exception as e:
        print(f"❌ Error reading service account file: {e}")
        return

    tokens = FCMToken.objects.filter(user=user).values_list("token", flat=True)

    print("🔥 TOKENS:", list(tokens))

    for token in tokens:
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "android": {"priority": "HIGH"}
            }
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, headers=headers, json=payload)

        print("🔥 STATUS:", response.status_code)
        print("🔥 RESPONSE:", response.text)

import requests
import json
from django.conf import settings
from .fcm_utils import get_access_token

def send_push_notification(user, title, body):
    from .models import FCMToken
    
    # Load project ID from service account file
    try:
        with open(settings.FCM_SERVICE_ACCOUNT_FILE) as f:
            service_account_data = json.load(f)
            project_id = service_account_data.get('project_id')
    except Exception as e:
        print(f"❌ Error reading service account file: {e}")
        return []

    access_token = get_access_token()
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    
    # Get all tokens for this user
    tokens = FCMToken.objects.filter(user=user).values_list('token', flat=True)
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    results = []
    for token in tokens:
        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body
                },
                "android": {
                    "priority": "high",
                    "notification": {
                        "channel_id": "high_importance_channel"
                    }
                }
            }
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        resp_json = response.json()
        print(f"🔥 FCM Push Status: {response.status_code}, Response: {resp_json}")
        
        # If token is invalid (app reinstalled or token revoked), delete it from DB
        if response.status_code == 404:
            error_code = resp_json.get('error', {}).get('details', [{}])[0].get('errorCode')
            if error_code == 'UNREGISTERED':
                print(f"🚫 Token UNREGISTERED. Deleting from DB: {token[:15]}...")
                FCMToken.objects.filter(token=token).delete()

        results.append(resp_json)
        
    return results

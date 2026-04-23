import requests
from datetime import date


class LinkedInPublisher:
    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str, person_urn: str, token_issued_at: str = ""):
        self.access_token = access_token
        self.person_urn = person_urn
        self.token_issued_at = token_issued_at
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def publish(self, text: str, image_url: str) -> str:
        image_urn = self._upload_image(image_url) if image_url else None
        body: dict = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE" if image_urn else "NONE",
                    **({"media": [{"status": "READY", "media": image_urn}]} if image_urn else {}),
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = requests.post(f"{self.BASE_URL}/ugcPosts", json=body,
                             headers=self._headers, timeout=30)
        if resp.status_code != 201:
            raise RuntimeError(f"LinkedIn API error {resp.status_code}: {resp.text}")
        post_id = resp.headers.get("X-RestLi-Id", "")
        return f"https://www.linkedin.com/feed/update/{post_id}/"

    def _upload_image(self, image_url: str) -> str | None:
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": self.person_urn,
                "serviceRelationships": [
                    {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                ],
            }
        }
        resp = requests.post(f"{self.BASE_URL}/assets?action=registerUpload",
                             json=register_payload, headers=self._headers, timeout=30)
        if resp.status_code != 200:
            return None
        data = resp.json()
        upload_url = data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = data["value"]["asset"]
        image_data = requests.get(image_url, timeout=30).content
        requests.put(upload_url, data=image_data,
                     headers={"Authorization": f"Bearer {self.access_token}"}, timeout=60)
        return asset_urn

    def is_token_expiring_soon(self, warn_at_day: int = 55) -> bool:
        if not self.token_issued_at:
            return False
        try:
            issued = date.fromisoformat(self.token_issued_at)
            return (date.today() - issued).days >= warn_at_day
        except ValueError:
            return False

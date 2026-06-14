"""
core/skills/gmail.py — Gmail & Google Calendar integration
Currently returns helpful setup instructions.

To enable real Gmail access:
  1. Go to https://console.cloud.google.com
  2. Enable Gmail API + Google Calendar API
  3. Create OAuth2 credentials → download credentials.json
  4. Place credentials.json in the project root directory
  5. Run: pip install google-auth-oauthlib google-api-python-client
  6. On first run, browser will open for OAuth consent

After setup, replace the stub functions below with real API calls.
"""

import os
from pathlib import Path

BASE = Path(__file__).parent.parent.parent.resolve()
CREDS_PATH  = BASE / "credentials.json"
TOKEN_PATH  = BASE / "token.json"
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def _get_google_service(service_name: str, version: str):
    """Authenticate and return a Google API service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API libraries not installed.\n"
            "Run: pip install google-auth-oauthlib google-api-python-client"
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_PATH.exists():
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDS_PATH}.\n"
                    "Download from Google Cloud Console → APIs & Services → Credentials."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_PATH), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())

    return build(service_name, version, credentials=creds)


def gmail_read_inbox(max_results: int = 10) -> dict:
    """
    Read the most recent emails from Gmail inbox.
    Returns list of {id, subject, from, date, snippet}.
    """
    if not CREDS_PATH.exists():
        return {
            "success": False,
            "setup_required": True,
            "message": (
                "Gmail not configured. To enable:\n"
                "1. Go to https://console.cloud.google.com\n"
                "2. Enable Gmail API\n"
                f"3. Download credentials.json → {BASE}/credentials.json\n"
                "4. pip install google-auth-oauthlib google-api-python-client"
            )
        }
    try:
        service  = _get_google_service("gmail", "v1")
        result   = service.users().messages().list(userId="me", maxResults=max_results, labelIds=["INBOX"]).execute()
        messages = result.get("messages", [])

        emails = []
        for msg in messages[:max_results]:
            detail  = service.users().messages().get(userId="me", id=msg["id"], format="metadata").execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            emails.append({
                "id":      msg["id"],
                "subject": headers.get("Subject", "(no subject)"),
                "from":    headers.get("From", ""),
                "date":    headers.get("Date", ""),
                "snippet": detail.get("snippet", "")[:200]
            })

        return {"success": True, "count": len(emails), "emails": emails}
    except Exception as e:
        return {"success": False, "error": str(e)}


def calendar_upcoming(days: int = 7) -> dict:
    """
    Get upcoming calendar events for the next N days.
    Returns list of {summary, start, end, location}.
    """
    if not CREDS_PATH.exists():
        return {
            "success": False,
            "setup_required": True,
            "message": "Google Calendar not configured. See gmail.py for setup instructions."
        }
    try:
        import datetime
        service   = _get_google_service("calendar", "v3")
        now       = datetime.datetime.utcnow().isoformat() + "Z"
        end_time  = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end_time,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        items  = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            end   = e["end"].get("dateTime",   e["end"].get("date"))
            items.append({
                "summary":  e.get("summary", "(no title)"),
                "start":    start,
                "end":      end,
                "location": e.get("location", ""),
                "link":     e.get("htmlLink", "")
            })

        return {"success": True, "days": days, "count": len(items), "events": items}
    except Exception as e:
        return {"success": False, "error": str(e)}

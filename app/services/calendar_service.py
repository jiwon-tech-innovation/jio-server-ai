from datetime import datetime, time, timedelta
import os
import pytz
from typing import List, Dict

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    print("Google Client Library not found. Using Mock.")

class CalendarService:
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __init__(self):
        # Path to service account file (e.g., k8s secret mount)
        self.creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
        self.use_mock = not os.path.exists(self.creds_path)

    def get_todays_plan(self) -> List[Dict]:
        """
        Fetches events for the current day.
        Returns: [{"summary": "Study", "start": "10:00", "end": "12:00"}]
        """
        if self.use_mock:
            return self._get_mock_plan()
            
        try:
            creds = service_account.Credentials.from_service_account_file(
                self.creds_path, scopes=self.SCOPES)
            service = build('calendar', 'v3', credentials=creds)

            now = datetime.utcnow()
            # Start of day (UTC approx, strictly should be User Timezone)
            # Assuming KST (UTC+9) for simple logic or using settings
            # Let's assume server runs in UTC but user is KST.
            kst = pytz.timezone('Asia/Seoul')
            now_kst = datetime.now(kst)
            start_of_day = now_kst.replace(hour=0, minute=0, second=0).isoformat()
            end_of_day = now_kst.replace(hour=23, minute=59, second=59).isoformat()

            events_result = service.events().list(
                calendarId='primary', 
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])

            plan = []
            for event in events:
                # 2026-01-05T10:00:00+09:00
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                summary = event.get('summary', 'No Title')
                plan.append({
                    "summary": summary,
                    "start": start[:16].replace("T", " "), # Simple string format
                    "end": end[:16].replace("T", " ")
                })
            return plan

        except Exception as e:
            print(f"[CalendarService] Error: {e}")
            return []

    def _get_mock_plan(self):
        # Mock data for testing logic
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            {"summary": "Update Logic (Algorithm)", "start": f"{today} 14:00", "end": f"{today} 16:00"},
            {"summary": "Team Meeting", "start": f"{today} 17:00", "end": f"{today} 18:00"}
        ]

calendar_service = CalendarService()

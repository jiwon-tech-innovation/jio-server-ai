import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permissions
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Path setup - keeping tokens in the same directory for now
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")

class CalendarService:
    def __init__(self):
        self._service = None

    def get_service(self):
        """Authentication and Service Object Creation"""
        if self._service is not None:
            return self._service
        
        creds = None
        # Load token if exists
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        
        # If no valid token, let it fail or log (Server shouldn't pop up UI)
        # For a server, we usually expect a valid token or a service account.
        # However, to match the client logic closely for now:
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    return None
            else:
                # Cannot run local server on a headless server usually, 
                # but for dev environment it might be okay or we expect token.json to be pre-filled.
                print("No valid token found. Cannot authenticate.")
                return None
            
            # Save refreshed token
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

        self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def get_todays_plan(self) -> list[dict]:
        """
        Fetches events for the current day (00:00 to 23:59).
        Returns a list of dicts: {'summary': ..., 'start': ..., 'end': ...}
        """
        service = self.get_service()
        if not service:
            return []

        now = datetime.datetime.now()
        start_of_day = datetime.datetime(now.year, now.month, now.day, 0, 0, 0).isoformat() + 'Z'
        end_of_day = datetime.datetime(now.year, now.month, now.day, 23, 59, 59).isoformat() + 'Z'

        try:
            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            plans = []
            for event in events:
                summary = event.get('summary', '(No Title)')
                start = event.get('start')
                end = event.get('end')
                
                # Format time nicely (e.g., 14:00)
                start_str = start.get('dateTime', start.get('date'))
                end_str = end.get('dateTime', end.get('date'))
                
                # If it's dateTime, slice to HH:MM
                if 'T' in start_str:
                    start_display = start_str.split('T')[1][:5]
                else:
                    start_display = "All Day"
                    
                if 'T' in end_str:
                    end_display = end_str.split('T')[1][:5]
                else:
                    end_display = "All Day"

                plans.append({
                    "summary": summary,
                    "start": start_display,
                    "end": end_display
                })
            
            return plans

        except Exception as e:
            print(f"Calendar Fetch Error: {e}")
            return []

calendar_service = CalendarService()

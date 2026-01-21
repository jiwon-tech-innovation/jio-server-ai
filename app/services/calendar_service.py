"""
Calendar Service - Fetches calendar events from jiaa-auth
"""
import os
import datetime
import httpx

class CalendarService:
    def __init__(self):
        # jiaa-auth API URL (K8s internal or ALB)
        self.base_url = os.environ.get("AUTH_API_URL", "http://jiaa-auth:8080")

    def get_todays_plan(self, token: str = None) -> list[dict]:
        """
        Fetches events for the current day from jiaa-auth.
        Returns a list of dicts: {'summary': ..., 'start': ..., 'end': ...}
        """
        url = f"{self.base_url}/api/calendar/events"
        
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        
        try:
            # Using sync httpx for simplicity (can be made async if needed)
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    events = data if isinstance(data, list) else data.get("items", [])
                    
                    now = datetime.datetime.now()
                    today_str = now.strftime("%Y-%m-%d")
                    
                    plans = []
                    for event in events:
                        summary = event.get('summary', '(No Title)')
                        start = event.get('start', {})
                        end = event.get('end', {})
                        
                        # Get datetime or date string
                        start_str = start.get('dateTime', start.get('date', ''))
                        end_str = end.get('dateTime', end.get('date', ''))
                        
                        # Filter for today's events
                        if today_str not in start_str:
                            continue
                        
                        # Format time nicely
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
                else:
                    print(f"[CalendarService] API Error: {response.status_code}")
                    return []
        except Exception as e:
            print(f"[CalendarService] Request Error: {e}")
            return []

calendar_service = CalendarService()



import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


#para configurar hpla
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly"
]

TIMEZONE = ZoneInfo("America/Bogota")
CALENDAR_ID = "primary"


# 2. Authentication
def connect_calendar():
    credentials = None

    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file(
            "token.json", SCOPES
        )

    if not credentials or not credentials.valid:
        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            credentials = flow.run_local_server(port=0)

        with open("token.json", "w", encoding="utf-8") as file:
            file.write(credentials.to_json())

    return build(
        "calendar",
        "v3",
        credentials=credentials,
    )


# 3. Read events
def get_events(service, days=7):
    now = datetime.now(TIMEZONE)
    end = now + timedelta(days=days)

    response = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        maxResults=250,
    ).execute()

    return response.get("items", [])


# 4. Format and print events
def print_events(events):
    print("\nMY GOOGLE CALENDAR")
    print("=" * 50)

    if not events:
        print("No upcoming events.")
        return

    for event in events:
        title = event.get("summary", "Untitled event")

        start = event.get("start", {})

        if "dateTime" in start:
            dt = datetime.fromisoformat(
                start["dateTime"].replace("Z", "+00:00")
            )
            dt = dt.astimezone(TIMEZONE)

            date_text = dt.strftime("%d/%m/%Y")
            time_text = dt.strftime("%H:%M")

        else: 
            # All-day event
            date_text = dt.strftime("%d/%m/%Y")
            time_text = "All day"

        print(f"{date_text} | {time_text} | {title}")


# 5. Run the backend
def main():
    service = connect_calendar()
    events = get_events(service, days=7)
    print_events(events)


if __name__ == "__main__":
    main()

if_ name_== "main

"""
calendar_client.py
Thin wrapper around the Google Calendar API for ePARS.
No business logic here — just create/update/delete/list events.
Burnout/reassignment decisions live in tools.py / the agent, not here.
"""

import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'sa_key.json'
CALENDAR_ID = 'aarna.manjunath04@gmail.com'  # from Google Calendar > Settings > Integrate calendar

_creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
_service = build('calendar', 'v3', credentials=_creds)


def create_event(summary: str, start_time: str, end_time: str,
                  description: str = "", attendee_emails: list[str] | None = None,
                  timezone: str = "Asia/Kolkata") -> dict:
    """
    Create a calendar event.
    start_time / end_time must be ISO 8601, e.g. '2026-07-15T10:00:00'
    Returns the created event dict (includes 'id' — store this as google_event_id).
    """
    event_body = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time, 'timeZone': timezone},
        'end': {'dateTime': end_time, 'timeZone': timezone},
    }
    if attendee_emails:
        event_body['attendees'] = [{'email': e} for e in attendee_emails]

    try:
        event = _service.events().insert(
            calendarId=CALENDAR_ID, body=event_body
        ).execute()
        return {'success': True, 'event_id': event['id'], 'html_link': event.get('htmlLink')}
    except HttpError as e:
        return {'success': False, 'error': str(e)}


def update_event(event_id: str, start_time: str | None = None,
                  end_time: str | None = None, summary: str | None = None,
                  timezone: str = "Asia/Kolkata") -> dict:
    """
    Reschedule or update an existing event. Only pass the fields you want changed.
    """
    try:
        event = _service.events().get(calendarId=CALENDAR_ID, eventId=event_id).execute()

        if start_time:
            event['start'] = {'dateTime': start_time, 'timeZone': timezone}
        if end_time:
            event['end'] = {'dateTime': end_time, 'timeZone': timezone}
        if summary:
            event['summary'] = summary

        updated = _service.events().update(
            calendarId=CALENDAR_ID, eventId=event_id, body=event
        ).execute()
        return {'success': True, 'event_id': updated['id']}
    except HttpError as e:
        return {'success': False, 'error': str(e)}


def delete_event(event_id: str) -> dict:
    try:
        _service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
        return {'success': True}
    except HttpError as e:
        return {'success': False, 'error': str(e)}


def list_events(time_min: str | None = None, time_max: str | None = None,
                 max_results: int = 20) -> dict:
    """
    List events in a time window. Defaults to now -> +7 days if not given.
    Used to check an employee's existing load before scheduling something new.
    """
    if not time_min:
        time_min = datetime.datetime.utcnow().isoformat() + 'Z'
    if not time_max:
        time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'

    try:
        result = _service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = result.get('items', [])
        return {
            'success': True,
            'events': [
                {
                    'id': e['id'],
                    'summary': e.get('summary', ''),
                    'start': e['start'].get('dateTime', e['start'].get('date')),
                    'end': e['end'].get('dateTime', e['end'].get('date')),
                }
                for e in events
            ]
        }
    except HttpError as e:
        return {'success': False, 'error': str(e)}


if __name__ == '__main__':
    # quick manual test — run: python calendar_client.py
    print("Listing next events...")
    result = list_events()
    print(result)
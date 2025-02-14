import os
import json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from pytz import timezone

# Load environment variables
load_dotenv()

# Slack configuration
SLACK_TOKEN = os.getenv('SLACK_TOKEN')
CHANNEL_ID = 'C08B0CAFD3J'
slack_client = WebClient(token=SLACK_TOKEN)

# Google Calendar configuration
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_google_calendar_service():
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        return build('calendar', 'v3', credentials=creds)
    raise Exception("Google credentials not found in environment variables")

def post_to_slack(message):
    try:
        response = slack_client.chat_postMessage(
            channel=CHANNEL_ID,
            text=message
        )
    except SlackApiError as e:
        print(f"Error posting to Slack: {e.response['error']}")

def check_team_leave():
    service = get_google_calendar_service()
    team_calendars = os.getenv('TEAM_CALENDAR_IDS').split(',')
    
    today = datetime.now(timezone('UTC')).date()
    today_start = datetime.combine(today, datetime.min.time()).isoformat() + 'Z'
    today_end = datetime.combine(today, datetime.max.time()).isoformat() + 'Z'
    
    on_leave = []
    
    for calendar_id in team_calendars:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=today_start,
            timeMax=today_end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events.get('items', []):
            if 'Annual Leave' in event.get('summary', ''):
                on_leave.append(event['summary'].split(' - ')[0])
    
    if on_leave:
        message = f"🏖️ *Team Leave Update*\nTeam members on leave today: {', '.join(on_leave)}"
    else:
        message = "🏢 *Team Leave Update*\nNo team members on leave today."
    
    post_to_slack(message)

def check_upcoming_leave():
    service = get_google_calendar_service()
    team_calendars = os.getenv('TEAM_CALENDAR_IDS').split(',')
    
    today = datetime.now(timezone('UTC')).date()
    start = datetime.combine(today, datetime.min.time()).isoformat() + 'Z'
    end = datetime.combine(today + timedelta(days=10), datetime.max.time()).isoformat() + 'Z'
    
    upcoming_leave = []
    
    for calendar_id in team_calendars:
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events.get('items', []):
            if 'Annual Leave' in event.get('summary', ''):
                start_date = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date'))).date()
                name = event['summary'].split(' - ')[0]
                upcoming_leave.append((start_date, name))
    
    if upcoming_leave:
        upcoming_leave.sort()
        message = "📅 *Upcoming Team Leave (Next 10 Days)*\n"
        for date, name in upcoming_leave:
            message += f"• {date.strftime('%d %B')}: {name}\n"
    else:
        message = "📅 *Upcoming Team Leave*\nNo upcoming team leave in the next 10 days."
    
    post_to_slack(message)

def check_daily_meetings():
    service = get_google_calendar_service()
    calendar_id = os.getenv('MY_CALENDAR_ID')
    
    today = datetime.now(timezone('UTC')).date()
    tomorrow = today + timedelta(days=1)
    
    def get_meetings_message(date, is_today=True):
        start = datetime.combine(date, datetime.min.time()).isoformat() + 'Z'
        end = datetime.combine(date, datetime.max.time()).isoformat() + 'Z'
        
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        meetings = []
        for event in events.get('items', []):
            start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            meetings.append(f"• {start_time.strftime('%H:%M')} - {event.get('summary', 'No title')}")
        
        day_str = "Today" if is_today else "Tomorrow"
        if meetings:
            return f"📊 *Meetings for {day_str}*\n" + "\n".join(meetings)
        return f"📅 *Meetings for {day_str}*\nNo meetings scheduled."
    
    return get_meetings_message(today), get_meetings_message(tomorrow, False)

def morning_meetings():
    today_meetings, _ = check_daily_meetings()
    post_to_slack(today_meetings)

def evening_meetings():
    _, tomorrow_meetings = check_daily_meetings()
    post_to_slack(tomorrow_meetings)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    
    # Daily leave check at 9:00 AM
    scheduler.add_job(check_team_leave, 'cron', hour=9, minute=0)
    
    # Weekly upcoming leave check on Mondays at 2:00 PM
    scheduler.add_job(check_upcoming_leave, 'cron', day_of_week='mon', hour=14, minute=0)
    
    # Daily meeting checks
    scheduler.add_job(morning_meetings, 'cron', hour=8, minute=50)
    scheduler.add_job(evening_meetings, 'cron', hour=16, minute=55)
    
    print("Starting scheduler...")
    scheduler.start()

import os
import json
import logging
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from pytz import timezone

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Verify environment variables
slack_token = os.getenv('SLACK_TOKEN')
google_creds = os.getenv('GOOGLE_CREDENTIALS')
my_calendar = os.getenv('MY_CALENDAR_ID')
team_calendars = os.getenv('TEAM_CALENDAR_IDS')

logger.info(f"SLACK_TOKEN present: {bool(slack_token)}")
logger.info(f"GOOGLE_CREDENTIALS present: {bool(google_creds)}")
logger.info(f"MY_CALENDAR_ID present: {bool(my_calendar)}")
logger.info(f"TEAM_CALENDAR_IDS present: {bool(team_calendars)}")

# Slack configuration
CHANNEL_ID = 'C08B0CAFD3J'
slack_client = WebClient(token=slack_token)
logger.info("Slack client initialized")

# Verify channel access
try:
    channel_info = slack_client.conversations_info(channel=CHANNEL_ID)
    logger.info(f"Successfully verified access to channel: {channel_info['channel']['name']}")
except SlackApiError as e:
    logger.error(f"Error accessing channel: {str(e)}")
    raise

# Google Calendar configuration
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Keywords that indicate leave
LEAVE_KEYWORDS = [
    'annual leave',
    'vacation',
    'holiday',
    'out of office',
    'ooo',
    'pto',
    'time off',
    'toil',
    'rdo',
    'al',
    ' al ',  # Space before and after to avoid matching words like "personal"
    'al-',
    'al:'
]

def get_google_calendar_service():
    logger.info("Attempting to get Google Calendar service")
    creds_json = os.getenv('GOOGLE_CREDENTIALS')
    if creds_json:
        try:
            creds_dict = json.loads(creds_json)
            creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
            service = build('calendar', 'v3', credentials=creds)
            logger.info("Google Calendar service created successfully")
            return service
        except Exception as e:
            logger.error(f"Error creating Google Calendar service: {str(e)}")
            raise
    raise Exception("Google credentials not found in environment variables")

def post_to_slack(message):
    logger.info(f"Attempting to post message to Slack: {message[:50]}...")
    try:
        response = slack_client.chat_postMessage(
            channel=CHANNEL_ID,
            text=message
        )
        logger.info("Message posted to Slack successfully")
    except SlackApiError as e:
        logger.error(f"Error posting to Slack: {e.response['error']}")
        raise

def is_leave_event(event_summary):
    if not event_summary:
        return False
    event_summary_lower = event_summary.lower()
    return any(keyword in event_summary_lower for keyword in LEAVE_KEYWORDS)

def check_team_leave():
    logger.info("Checking team leave")
    service = get_google_calendar_service()
    team_calendars = os.getenv('TEAM_CALENDAR_IDS').split(',')
    
    today = datetime.now(timezone('UTC')).date()
    today_start = datetime.combine(today, datetime.min.time()).isoformat() + 'Z'
    today_end = datetime.combine(today, datetime.max.time()).isoformat() + 'Z'
    
    on_leave = []
    
    for calendar_id in team_calendars:
        logger.info(f"Checking calendar: {calendar_id}")
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=today_start,
            timeMax=today_end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events.get('items', []):
            if is_leave_event(event.get('summary', '')):
                name = event['summary'].split(' - ')[0] if ' - ' in event['summary'] else calendar_id.split('@')[0]
                leave_type = next((keyword for keyword in LEAVE_KEYWORDS if keyword in event.get('summary', '').lower()), 'Leave')
                on_leave.append((name, leave_type.upper()))
    
    if on_leave:
        message = "🏖️ *Team Leave Update*\n"
        for name, leave_type in on_leave:
            message += f"• {name} ({leave_type})\n"
    else:
        message = "🏢 *Team Leave Update*\nNo team members on leave today."
    
    post_to_slack(message)

def check_daily_meetings():
    logger.info("Checking daily meetings")
    service = get_google_calendar_service()
    calendar_id = os.getenv('MY_CALENDAR_ID')
    
    today = datetime.now(timezone('UTC')).date()
    tomorrow = today + timedelta(days=1)
    
    def get_meetings_message(date, is_today=True):
        start = datetime.combine(date, datetime.min.time()).isoformat() + 'Z'
        end = datetime.combine(date, datetime.max.time()).isoformat() + 'Z'
        
        # Get regular calendar events
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        # Get personal calendar events if configured
        personal_calendar_id = os.getenv('PERSONAL_CALENDAR_ID')
        if personal_calendar_id:
            personal_events = service.events().list(
                calendarId=personal_calendar_id,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            events['items'].extend(personal_events.get('items', []))
            events['items'].sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
        
        meetings = []
        for event in events.get('items', []):
            start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            calendar_name = "📆 Personal" if event.get('organizer', {}).get('email') == personal_calendar_id else "💼 Work"
            meetings.append(f"• {start_time.strftime('%H:%M')} [{calendar_name}] - {event.get('summary', 'No title')}")
        
        day_str = "Today" if is_today else "Tomorrow"
        if meetings:
            return f"📊 *Meetings for {day_str}*\n" + "\n".join(meetings)
        return f"📅 *Meetings for {day_str}*\nNo meetings scheduled."
    
    return get_meetings_message(today), get_meetings_message(tomorrow, False)

def check_upcoming_leave():
    logger.info("Checking upcoming leave")
    service = get_google_calendar_service()
    team_calendars = os.getenv('TEAM_CALENDAR_IDS').split(',')
    
    today = datetime.now(timezone('UTC')).date()
    start = datetime.combine(today, datetime.min.time()).isoformat() + 'Z'
    end = datetime.combine(today + timedelta(days=10), datetime.max.time()).isoformat() + 'Z'
    
    upcoming_leave = []
    
    for calendar_id in team_calendars:
        logger.info(f"Checking calendar: {calendar_id}")
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=start,
            timeMax=end,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        for event in events.get('items', []):
            if is_leave_event(event.get('summary', '')):
                start_date = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date'))).date()
                name = event['summary'].split(' - ')[0] if ' - ' in event['summary'] else calendar_id.split('@')[0]
                leave_type = next((keyword for keyword in LEAVE_KEYWORDS if keyword in event.get('summary', '').lower()), 'Leave')
                upcoming_leave.append((start_date, name, leave_type.upper()))
    
    if upcoming_leave:
        upcoming_leave.sort()
        message = "📅 *Upcoming Team Leave (Next 10 Days)*\n"
        for date, name, leave_type in upcoming_leave:
            message += f"• {date.strftime('%d %B')}: {name} ({leave_type})\n"
    else:
        message = "📅 *Upcoming Team Leave*\nNo upcoming team leave in the next 10 days."
    
    post_to_slack(message)

def morning_meetings():
    today_meetings, _ = check_daily_meetings()
    post_to_slack(today_meetings)

def evening_meetings():
    _, tomorrow_meetings = check_daily_meetings()
    post_to_slack(tomorrow_meetings)

if __name__ == "__main__":
    logger.info("Starting application")
    try:
        # Test Slack connection
        logger.info("Testing Slack connection")
        post_to_slack("🧪 Test message: Bot is now connected!")
        
        # Test Google Calendar connection
        logger.info("Testing Google Calendar connection")
        service = get_google_calendar_service()
        today_meetings, tomorrow_meetings = check_daily_meetings()
        post_to_slack("📅 Test calendar fetch successful!\n" + today_meetings)
        
        # Test team leave check
        logger.info("Testing team leave check")
        check_team_leave()
        
        logger.info("All tests completed successfully")
    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        try:
            post_to_slack(f"⚠️ Test Error: {str(e)}")
        except:
            logger.error("Could not send error message to Slack")
            raise
    
    # Set up regular schedule
    scheduler = BlockingScheduler()
    scheduler.add_job(check_team_leave, 'cron', hour=9, minute=0)
    scheduler.add_job(check_upcoming_leave, 'cron', day_of_week='mon', hour=14, minute=0)
    scheduler.add_job(morning_meetings, 'cron', hour=8, minute=50)
    scheduler.add_job(evening_meetings, 'cron', hour=16, minute=55)
    
    logger.info("Starting scheduler")
    scheduler.start()

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

[Previous functions remain the same...]

if __name__ == "__main__":
    # Send test messages
    try:
        # Test Slack connection
        post_to_slack("🧪 Test message: Bot is now connected!")
        
        # Test Google Calendar connection
        service = get_google_calendar_service()
        today_meetings, tomorrow_meetings = check_daily_meetings()
        post_to_slack("📅 Test calendar fetch successful!\n" + today_meetings)
        
        # Test team leave check
        check_team_leave()
        
        print("Test messages sent successfully!")
    except Exception as e:
        print(f"Error during test: {str(e)}")
        post_to_slack(f"⚠️ Test Error: {str(e)}")
    
    # Set up regular schedule
    scheduler = BlockingScheduler()
    scheduler.add_job(check_team_leave, 'cron', hour=9, minute=0)
    scheduler.add_job(check_upcoming_leave, 'cron', day_of_week='mon', hour=14, minute=0)
    scheduler.add_job(morning_meetings, 'cron', hour=8, minute=50)
    scheduler.add_job(evening_meetings, 'cron', hour=16, minute=55)
    
    print("Starting scheduler...")
    scheduler.start()

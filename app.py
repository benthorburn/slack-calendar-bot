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

[Rest of the code remains the same...]

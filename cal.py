import httplib2
import re
import urllib
import json
import urllib2
import dateparser
from datetime import (datetime, timedelta)

from apiclient.discovery import build
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from oauth2client.tools import argparser
from apiclient import errors

import secrets

NOW = datetime.now()

def get_calendar_events(calendar_id, max_cutoff):
  flags = argparser.parse_args(args=[])

  # Try to retrieve Gmail credentials from storage or generate them
  HTTP = httplib2.Http()
  STORAGE = Storage('calendar.storage')
  credentials = STORAGE.get()
  if credentials is None or credentials.invalid:
    credentials = run_flow(flow_from_clientsecrets(
        secrets.CLIENT_SECRET_FILE,
        scope='https://www.googleapis.com/auth/calendar.readonly'), STORAGE, flags, http=HTTP)
  CALENDAR_SERVICE = build('calendar', 'v3', http=credentials.authorize(HTTP))

  MIN_CUTOFF = datetime.now() - timedelta(days=1)

  now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
  eventsResult = CALENDAR_SERVICE.events().list(
      calendarId=calendar_id,
      timeMin=MIN_CUTOFF.isoformat() + 'Z',
      timeMax=max_cutoff.isoformat() + 'Z',
      maxResults=1000, singleEvents=True,
      orderBy='startTime').execute()
  return eventsResult.get('items', [])

def evaluate_calendar_pattern_helper(calendar_data, name_pat, date):
  for event in calendar_data:
    if re.match(name_pat, event['summary']):
      start = dateparser.parse(event['start'].get('dateTime', event['start'].get('date')))
      end = dateparser.parse(event['end'].get('dateTime', event['end'].get('date')))
      #print 'RE MATCH!! start: %s end: %s date: %s' % (start, end, date)
      if not start or not end:
        print 'Strange calendar event is missing start/end: %s' % event
        continue
      if start < date and date < end:
        return event
  return None

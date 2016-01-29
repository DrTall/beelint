#!/usr/bin/python
# -*- coding: utf-8 -*-

import collections
import dateparser
import json
import requests
import urllib
import urllib2
from datetime import (date, datetime, timedelta)

from google.protobuf import text_format

import cal
import config_pb2 # protoc -I=. --python_out=. config.proto
import secrets

def epoch_time(d):
  """Seriously this is the best way to do this???"""
  return int((d - datetime(1970, 1, 1)).total_seconds())

def get_config(path):
  with open(path) as f:
    result = config_pb2.BeelintConfig()
    text_format.Merge(f.read(), result)
    return result

def post_datum(username, goalname, value, comment):
  beeminder_url = (
      'https://www.beeminder.com/api/v1/users/' +
      '%(username)s/goals/%(goalname)s/datapoints.json' %
      {'username': username, 'goalname':goalname})
  payload = {'auth_token':secrets.BEEMINDER_AUTH_TOKEN, 'value': value, 'comment': comment}
  r = requests.post(beeminder_url, data=payload)

  print r.status_code
  print r.content

def evaluate_date_pattern(pat, data, goalname, permit_all_after_first_forbidden_block):
  losedate = datetime.fromtimestamp(data[goalname]['losedate'])
  if pat.start_date and dateparser.parse(pat.start_date) > losedate:
    print 'Skipping future permitted_eep_entry for %s: %s' % (goalname, permitted_eep_entry)
  elif pat.end_date and dateparser.parse(pat.end_date) < losedate:
    print 'Skipping expired permitted_eep_entry for %s: %s' % (goalname, permitted_eep_entry)
  elif losedate.weekday() in pat.specific_weekday:
    print 'Valid eep! day for %s: %s in %s' % (goalname, losedate.weekday(), pat.specific_weekday)
  elif not permit_all_after_first_forbidden_block:
    violation = 'Illegal eep! day for %s: %s not in %s.' % (
        goalname, losedate.weekday(), pat.specific_weekday)
    return True
  else:
    # Have to go looking for the first forbidden block between now and the eep!.
    # See permit_all_after_first_forbidden_block in config.proto.
    now = NOW
    if pat.start_date and dateparser.parse(pat.start_date) > now:
      now = dateparser.parse(pat.start_date)
    found_forbidden_block = False
    # Explicitly iterating is uglier than being clever but easier to reason about.
    while now < losedate:
      if now.weekday() not in pat.specific_weekday:
        found_forbidden_block = True
      if found_forbidden_block and now.weekday() in pat.specific_weekday:
        print 'Valid eep! day for %s: %s not in %s but %s ends the first forbidden block' % (
            goalname, losedate.weekday(), pat.specific_weekday, now)
        break
      # This is probably not legitimate in regards to timezones and/or non-midnight deadlines.
      now += timedelta(days=1)
    else:
      violation = 'Illegal eep! day for %s: %s not in %s with no suitable forbidden block beforehand.' % (
          goalname, losedate.weekday(), pat.specific_weekday)
      return True
  return False

NOW = datetime.now()
DIFF_SINCE = NOW - timedelta(weeks=4)
DIFF_SINCE_EPOCH = epoch_time(DIFF_SINCE)

goals = []
beeminder_url = 'https://www.beeminder.com/api/v1/users/me.json'
beeminder_url += ('?diff_since=%s&' % DIFF_SINCE_EPOCH) + urllib.urlencode(
    {'auth_token':secrets.BEEMINDER_AUTH_TOKEN})
user_data = json.loads(urllib2.urlopen(beeminder_url).read())
goals.extend(user_data['goals'])
del user_data

data = {g['slug']:g for g in goals}
del goals

violations = set()
config = get_config('config')
calendar_data = None
for permitted_eep_entry in config.permitted_eep_entry:
  if permitted_eep_entry.start_date and dateparser.parse(permitted_eep_entry.start_date) > NOW:
    print 'Skipping future permitted_eep_entry: %s' % (permitted_eep_entry)
    continue

  for goalname in permitted_eep_entry.goalname or sorted(data, key=lambda d: data[d]['losedate']):
    if goalname == config.lint_goalname:
      print 'Skipping lint on the lint_goalname because that can lead to unrecoverable eep!s.'
      continue
    if permitted_eep_entry.HasField('date_pattern'):
      if evaluate_date_pattern(
          permitted_eep_entry.date_pattern,
          data,
          goalname,
          permitted_eep_entry.permit_all_after_first_forbidden_block):
        violations.add(goalname)
    if permitted_eep_entry.HasField('calendar_pattern'):
      if calendar_data is None:
        calendar_data = cal.get_calendar_events(
            config.calendar_id,
            max(datetime.fromtimestamp(g['losedate']) for g in data.values()))
      if cal.evaluate_calendar_pattern(
          calendar_data,
          permitted_eep_entry.calendar_pattern,
          data,
          goalname,
          permitted_eep_entry.permit_all_after_first_forbidden_block):
        violations.add(goalname)

if not violations:
  print 'No violations on any goals.'
else:
  print 'Violations: %s' % ','.join(violations)

if not config.lint_goalname:
  print 'It was all for nothing. No lint_goalname provided.'
elif config.lint_goalname not in data:
  print 'It was all for nothing. The provided lint_goalname (%s) does not exist.' % config.lint_goalname
else:
  value = len(violations)
  comment = ','.join(sorted(violations))
  print 'Might post data to Beeminder: %s (%s)' % (value, comment)
  last_data = data[config.lint_goalname]['datapoints'][-1:]
  if not last_data or int(last_data[0]['value']) != value or last_data[0]['comment'] != comment:
    print 'Proceeding with update, since %s != %s' % (last_data, value)
    post_datum(config.username, config.lint_goalname, value, comment)
  else:
    print 'No change since last run, skipping update.'

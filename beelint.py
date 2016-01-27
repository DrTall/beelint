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

violations = collections.defaultdict(list)
config = get_config('config')
for permitted_eep_entry in config.permitted_eep_entry:
  if not permitted_eep_entry.date_pattern:
    print 'Skipping permitted_eep_entry without date_pattern: %s' % permitted_eep_entry
    continue
  if permitted_eep_entry.start_date and dateparser.parse(permitted_eep_entry.start_date) > NOW:
    print 'Skipping future permitted_eep_entry: %s' % (permitted_eep_entry)
    continue

  pat = permitted_eep_entry.date_pattern
  for goalname in permitted_eep_entry.goalname or sorted(data, key=lambda d: data[d]['losedate']):
    if goalname == config.lint_goalname:
      print 'Skipping lint on the lint_goalname because that can lead to unrecoverable eep!s.'
      continue
    losedate = datetime.fromtimestamp(data[goalname]['losedate'])
    if pat.start_date and dateparser.parse(pat.start_date) > losedate:
      print 'Skipping future permitted_eep_entry for %s: %s' % (goalname, permitted_eep_entry)
      continue
    if pat.end_date and dateparser.parse(pat.end_date) < losedate:
      print 'Skipping expired permitted_eep_entry for %s: %s' % (goalname, permitted_eep_entry)
      continue

    if losedate.weekday() in pat.specific_weekday:
      print 'Valid eep! day for %s: %s in %s' % (goalname, losedate.weekday(), pat.specific_weekday)
      continue
    if not permitted_eep_entry.permit_all_after_first_forbidden_block:
      violation = 'Illegal eep! day for %s: %s not in %s.' % (
          goalname, losedate.weekday(), pat.specific_weekday)
      print violation
      violations[goalname].append(violation)
      continue

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
      print violation
      violations[goalname].append(violation)

if not violations:
  print 'No violations on any goals.'
else:
  for goalname, vlist in violations.items():
    if not vlist:
      continue
    print 'Violations(%s) for %s: %s' % (len(vlist), goalname, vlist)

if not config.lint_goalname:
  print 'It was all for nothing. No lint_goalname provided.'
elif config.lint_goalname not in data:
  print 'It was all for nothing. The provided lint_goalname (%s) does not exist.' % config.lint_goalname
else:
  value = sum([len(v) for v in violations.values()])
  comment = ','.join(violations.keys())
  print 'Might post data to Beeminder: %s (%s)' % (value, comment)
  last_data = data[config.lint_goalname]['datapoints'][-1:]
  if not last_data or int(last_data[0]['value']) != value:
    print 'Proceeding with update, since %s != %s' % (last_data, value)
    post_datum(config.username, config.lint_goalname, value, comment)
  else:
    print 'No change since last run, skipping update.'

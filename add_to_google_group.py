# auto rclone
# Add service accounts to groups for your organization
#
# Author Telegram https://t.me/CodyDoby
# Inbox  codyd@qq.com

from __future__ import print_function

import os
import pickle

import argparse
import glob
import googleapiclient.discovery
import json
import progress.bar
import time
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

stt = time.time()

parse = argparse.ArgumentParser(
    description='A tool to add service accounts to groups for your organization from a folder containing credential '
                'files.')
parse.add_argument('--path', '-p', default='accounts',
                   help='Specify an alternative path to the service accounts folder.')
parse.add_argument('--credentials', '-c', default='credentials/credentials.json',
                   help='Specify the relative path for the controller file.')
parsereq = parse.add_argument_group('required arguments')
# service-account@googlegroups.com
parsereq.add_argument('--groupaddr', '-g', help='The address of groups for your organization.', required=True)

args = parse.parse_args()
acc_dir = args.path
gaddr = args.groupaddr
credentials = glob.glob(args.credentials)

creds = None
if os.path.exists('credentials/token.pickle'):
    with open('credentials/token.pickle', 'rb') as token:
        creds = pickle.load(token)
# If there are no (valid) credentials available, let the user log in.
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(credentials[0], scopes=[
            'https://www.googleapis.com/auth/admin.directory.group',
            'https://www.googleapis.com/auth/admin.directory.group.member'
        ])
        # creds = flow.run_local_server(port=0)
        creds = flow.run_console()
    # Save the credentials for the next run
    with open('credentials/token.pickle', 'wb') as token:
        pickle.dump(creds, token)

group = googleapiclient.discovery.build("admin", "directory_v1", credentials=creds)

print(group.members())

batch = group.new_batch_http_request()

sa = glob.glob('%s/*.json' % acc_dir)

# sa = sa[0:5]

pbar = progress.bar.Bar("Readying accounts", max=len(sa))
for i in sa:
    ce = json.loads(open(i, 'r').read())['client_email']

    body = {"email": ce, "role": "MEMBER"}
    batch.add(group.members().insert(groupKey=gaddr, body=body))
    # group.members().insert(groupKey=gaddr, body=body).execute()

    pbar.next()
pbar.finish()
print('Adding...')
batch.execute()

print('Complete.')
hours, rem = divmod((time.time() - stt), 3600)
minutes, sec = divmod(rem, 60)
print("Elapsed Time:\n{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), sec))

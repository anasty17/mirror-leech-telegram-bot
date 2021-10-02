from __future__ import print_function
from google.oauth2.service_account import Credentials
import googleapiclient.discovery, json, progress.bar, glob, sys, argparse, time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, pickle

stt = time.time()

parse = argparse.ArgumentParser(
    description='A tool to add service accounts to a shared drive from a folder containing credential files.')
parse.add_argument('--path', '-p', default='accounts',
                   help='Specify an alternative path to the service accounts folder.')
parse.add_argument('--credentials', '-c', default='./credentials.json',
                   help='Specify the relative path for the credentials file.')
parse.add_argument('--yes', '-y', default=False, action='store_true', help='Skips the sanity prompt.')
parsereq = parse.add_argument_group('required arguments')
parsereq.add_argument('--drive-id', '-d', help='The ID of the Shared Drive.', required=True)

args = parse.parse_args()
acc_dir = args.path
did = args.drive_id
credentials = glob.glob(args.credentials)

try:
    open(credentials[0], 'r')
    print('>> Found credentials.')
except IndexError:
    print('>> No credentials found.')
    sys.exit(0)

if not args.yes:
    # input('Make sure the following client id is added to the shared drive as Manager:\n' + json.loads((open(
    # credentials[0],'r').read()))['installed']['client_id'])
    input('>> Make sure the **Google account** that has generated credentials.json\n   is added into your Team Drive '
          '(shared drive) as Manager\n>> (Press any key to continue)')

creds = None
if os.path.exists('token_sa.pickle'):
    with open('token_sa.pickle', 'rb') as token:
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
    with open('token_sa.pickle', 'wb') as token:
        pickle.dump(creds, token)

drive = googleapiclient.discovery.build("drive", "v3", credentials=creds)
batch = drive.new_batch_http_request()

aa = glob.glob('%s/*.json' % acc_dir)
pbar = progress.bar.Bar("Readying accounts", max=len(aa))
for i in aa:
    ce = json.loads(open(i, 'r').read())['client_email']
    batch.add(drive.permissions().create(fileId=did, supportsAllDrives=True, body={
        "role": "organizer",
        "type": "user",
        "emailAddress": ce
    }))
    pbar.next()
pbar.finish()
print('Adding...')
batch.execute()

print('Complete.')
hours, rem = divmod((time.time() - stt), 3600)
minutes, sec = divmod(rem, 60)
print("Elapsed Time:\n{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), sec))

import os
import sys
import pickle

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient import discovery

OAUTH_SCOPE = ['https://www.googleapis.com/auth/cloud-platform']


# noinspection DuplicatedCode
def authorize():
    # Get credentials
    credentials = None
    if os.path.exists('token-iam.pickle'):
        with open('token-iam.pickle', 'rb') as f:
            credentials = pickle.load(f)
    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', OAUTH_SCOPE)
            credentials = flow.run_console(port=0)

        # Save the credentials for the next run
        with open('token-iam.pickle', 'wb') as token:
            pickle.dump(credentials, token)
    return discovery.build('iam', 'v1', credentials=credentials)


def get_service_accounts(project_id):
    """Returns a list of service accounts in project with id == project_id"""
    accounts = service.projects().serviceAccounts().list(
        name=f'projects/{project_id}').execute()
    return accounts['accounts']


def download_keys(project_id):
    accounts = get_service_accounts(project_id)
    print(f'{len(accounts)} service accounts found! Dumping now')
    i = 0
    for acc in accounts:
        if not os.path.exists('accounts/'):
            os.mkdir('accounts/')
        if os.path.isfile('accounts/'):
            os.remove('accounts')
            os.mkdir('accounts/')
        print("Dumping " + acc['email'])
        key = service.projects().serviceAccounts().keys().create(
            name='projects/-/serviceAccounts/' + acc['email'], body={}
        ).execute()
        with open(f'accounts/{i}.json', 'w') as f:
            f.write(str(key))
        i += 1


service = authorize()

if __name__ == '__main__':
    download_keys(sys.argv[1])

import errno
import os
import pickle
import sys
from argparse import ArgumentParser
from base64 import b64decode
from glob import glob
from json import loads
from random import choices
from time import sleep

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/cloud-platform', 'https://www.googleapis.com/auth/iam']
project_create_ops = []
current_key_dump = []
sleep_time = 30


# Create count SAs in project
def _create_accounts(service, project, count):
    batch = service.new_batch_http_request(callback=_def_batch_resp)
    for _ in range(count):
        aid = _generate_id('mfc-')
        batch.add(service.projects().serviceAccounts().create(name=f'projects/{project}', body={'accountId': aid, 'serviceAccount': {'displayName': aid}}))
    batch.execute()


# Create accounts needed to fill project
def _create_remaining_accounts(iam, project):
    print(f'Creating accounts in {project}')
    sa_count = len(_list_sas(iam, project))
    while sa_count != 100:
        _create_accounts(iam, project, 100 - sa_count)
        sa_count = len(_list_sas(iam, project))


# Generate a random id
def _generate_id(prefix='saf-'):
    chars = '-abcdefghijklmnopqrstuvwxyz1234567890'
    return prefix + ''.join(choices(chars, k=25)) + choices(chars[1:])


# List projects using service
def _get_projects(service):
    return [i['projectId'] for i in service.projects().list().execute()['projects']]


# Default batch callback handler
def _def_batch_resp(id, resp, exception):
    if exception is not None:
        if str(exception).startswith('<HttpError 429'):
            sleep(sleep_time / 100)
        else:
            print(str(exception))


# Project Creation Batch Handler
def _pc_resp(id, resp, exception):
    global project_create_ops
    if exception is not None:
        print(str(exception))
    else:
        for i in resp.values():
            project_create_ops.append(i)


# Project Creation
def _create_projects(cloud, count):
    global project_create_ops
    batch = cloud.new_batch_http_request(callback=_pc_resp)
    new_projs = []
    for _ in range(count):
        new_proj = _generate_id()
        new_projs.append(new_proj)
        batch.add(cloud.projects().create(body={'project_id': new_proj}))
    batch.execute()

    for i in project_create_ops:
        while True:
            resp = cloud.operations().get(name=i).execute()
            if 'done' in resp and resp['done']:
                break
            sleep(3)
    return new_projs


# Enable services ste for projects in projects
def _enable_services(service, projects, ste):
    batch = service.new_batch_http_request(callback=_def_batch_resp)
    for i in projects:
        for j in ste:
            batch.add(service.services().enable(name=f'projects/{i}/services/{j}'))
    batch.execute()


# List SAs in project
def _list_sas(iam, project):
    resp = iam.projects().serviceAccounts().list(name=f'projects/{project}', pageSize=100).execute()
    return resp.get('accounts', [])


# Create Keys Batch Handler
def _batch_keys_resp(id, resp, exception):
    global current_key_dump
    if exception is not None:
        print(str(exception))
    else:
        for i in resp['keys']:
            current_key_dump.append(b64decode(i['privateKeyData']).decode())


# Create keys for SAs in project
def _create_keys(iam, project):
    global current_key_dump
    current_key_dump = []
    sas = _list_sas(iam, project)
    batch = iam.new_batch_http_request(callback=_batch_keys_resp)
    for i in sas:
        batch.add(iam.projects().serviceAccounts().keys().create(name=f'{i["name"]}', body={}))
    batch.execute()


# Download Key Handler
def _download_key_resp(id, resp, exception):
    if exception is not None:
        print(str(exception))
    else:
        with open(f'{id}.json', 'wb') as f:
            f.write(b64decode(resp['privateKeyData']))


# Download keys for SAs in project
def _download_keys(iam, project):
    batch = iam.new_batch_http_request(callback=_download_key_resp)
    for i in _list_sas(iam, project):
        batch.add(iam.projects().serviceAccounts().keys().get(name=f'{i["name"]}/keys/{i["email"]}.json'))
    batch.execute()


def main(args):
    # Load or create credentials
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Build Google service clients
    cloud = build('cloudresourcemanager', 'v1', credentials=creds)
    iam = build('iam', 'v1', credentials=creds)

    # Create projects
    new_projects = _create_projects(cloud, args.count)
    print(f'Created {args.count} new projects:', new_projects)

    # Enable services
    _enable_services(cloud, new_projects, args.services)

    # Create and download keys
    for project in new_projects:
        _create_keys(iam, project)
        _download_keys(iam, project)

    # Create remaining service accounts
    for project in new_projects:
        _create_remaining_accounts(iam, project)

    print('Finished creating service accounts.')


if __name__ == '__main__':
    parser = ArgumentParser(description='Script to create service accounts in Google Cloud projects')
    parser.add_argument('-c', '--count', type=int, default=1, help='Number of projects to create')
    parser.add_argument('-s', '--services', nargs='+', default=['iam.googleapis.com'], help='Services to enable in the projects')
    args = parser.parse_args()
    main(args)

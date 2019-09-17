from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient.errors import ResumableUploadError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client import file, client, tools
from mimetypes import guess_type
import httplib2
import os
from config import Config
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)


G_DRIVE_TOKEN_FILE = "auth_token.txt"
# Copy your credentials from the APIs Console
CLIENT_ID = Config.G_DRIVE_CLIENT_ID
CLIENT_SECRET = Config.G_DRIVE_CLIENT_SECRET
# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
# Redirect URI for installed apps, can be left as is
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
parent_id = Config.GDRIVE_FOLDER_ID
G_DRIVE_DIR_MIME_TYPE = "application/vnd.google-apps.folder"


if CLIENT_ID is None or CLIENT_SECRET is None or parent_id is None:
	logging.error("Please Setup Config Properly.")






def upload(fileName):
	try:
		with open(G_DRIVE_TOKEN_FILE) as f:
			pass
	except IOError:
		storage = create_token_file(G_DRIVE_TOKEN_FILE)
		http = authorize(G_DRIVE_TOKEN_FILE, storage)
	print("Uploading File: "+fileName)	
	if os.path.isfile(fileName):
		http = authorize(G_DRIVE_TOKEN_FILE, None)
		file_name, mime_type = file_ops(fileName)	
		try:
			g_drive_link = upload_file(http, file_name,file_name, mime_type,parent_id)
			logging.info("Uploaded To G-Drive: "+fileName)
			link = g_drive_link
		except Exception as e:
			logging.error(str(e))
			pass
	else:
		http = authorize(G_DRIVE_TOKEN_FILE, None)
		file_name, mime_type = file_ops(fileName)
		try:
			dir_id = create_directory(http, os.path.basename(os.path.abspath(fileName)), parent_id)		
			DoTeskWithDir(http,fileName, dir_id)
			logging.info("Uploaded To G-Drive: "+fileName)
			dir_link = "https://drive.google.com/folderview?id={}".format(dir_id)
			link = dir_link
		except Exception as e:
			logging.error(str(e))	
			pass
	return link 		
	# with open('data','w') as f:
	# 	f.write(link)





def create_directory(http, directory_name, parent_id):
	drive_service = build("drive", "v2", http=http, cache_discovery=False)
	permissions = {
        "role": "reader",
        "type": "anyone",
        "value": None,
        "withLink": True
	}
	file_metadata = {
        "title": directory_name,
        "mimeType": G_DRIVE_DIR_MIME_TYPE
	}
	if parent_id is not None:
		file_metadata["parents"] = [{"id": parent_id}]
	file = drive_service.files().insert(body=file_metadata).execute()
	file_id = file.get("id")
	drive_service.permissions().insert(fileId=file_id, body=permissions).execute()
	logging.info("Created Gdrive Folder:\nName: {}\nID: {} ".format(file.get("title"), file_id))
	return file_id


def DoTeskWithDir(http, input_directory, parent_id):
	list_dirs = os.listdir(input_directory)
	if len(list_dirs) == 0:
		return parent_id
	r_p_id = None
	for a_c_f_name in list_dirs:
		current_file_name = os.path.join(input_directory, a_c_f_name)
		if os.path.isdir(current_file_name):
			current_dir_id = create_directory(http, a_c_f_name, parent_id)
			r_p_id = DoTeskWithDir(http, current_file_name,current_dir_id)
		else:
			file_name, mime_type = file_ops(current_file_name)
            # current_file_name will have the full path
			g_drive_link = upload_file(http, current_file_name, file_name, mime_type, parent_id)
			r_p_id = parent_id
    # TODO: there is a #bug here :(
	return r_p_id

def file_ops(file_path):
	mime_type = guess_type(file_path)[0]
	mime_type = mime_type if mime_type else "text/plain"
	file_name = file_path.split("/")[-1]
	return file_name, mime_type


def create_token_file(token_file):
# Run through the OAuth flow and retrieve credentials
	flow = OAuth2WebServerFlow(
		CLIENT_ID,
		CLIENT_SECRET,
		OAUTH_SCOPE,
		redirect_uri=REDIRECT_URI
		)
	authorize_url = flow.step1_get_authorize_url()
	print('Go to the following link in your browser: ' + authorize_url)
	code = input('Enter verification code: ').strip()
	credentials = flow.step2_exchange(code)
	storage = Storage(token_file)
	storage.put(credentials)
	return storage

def authorize(token_file, storage):
    # Get credentials
	if storage is None:
		storage = Storage(token_file)
	credentials = storage.get()
	# Create an httplib2.Http object and authorize it with our credentials
	http = httplib2.Http()
	credentials.refresh(http)
	http = credentials.authorize(http)
	return http




def upload_file(http, file_path,file_name, mime_type, parent_id):
# Create Google Drive service instance
	drive_service = build('drive', 'v2', http=http, cache_discovery=False)
# File body description
	media_body = MediaFileUpload(file_path,
                                 mimetype=mime_type,
                                 resumable=True)
	body = {
        'title': file_name,
        'description': 'backup',
        'mimeType': mime_type,
	}
	if parent_id is not None:
		body["parents"] = [{"id": parent_id}]
# Permissions body description: anyone who has link can upload
# Other permissions can be found at https://developers.google.com/drive/v2/reference/permissions
	permissions = {
        'role': 'reader',
        'type': 'anyone',
        'value': None,
        'withLink': True
    }
# Insert a file
	file = drive_service.files().insert(body=body, media_body=media_body).execute()
# Insert new permissions
	drive_service.permissions().insert(fileId=file['id'], body=permissions).execute()
# Define file instance and get url for download
	file = drive_service.files().get(fileId=file['id']).execute()
	download_url = file.get('webContentLink')
	return download_url	




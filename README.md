# What is this repo about?
This is a telegram bot writen in python for mirroring files on the internet to our beloved Google Drive.

# Inspiration 
This project is heavily inspired from @out386 's telegram bot which is written in JS.

# Features supported:
- Mirroring direct download links to google drive
- Download progress
- Upload progress
- Download/upload speeds and ETAs
- Docker support

# Upcoming features (TODOs):
- Mega link mirror support
- More code clean up

# How to deploy?
Deploying is pretty much straight forward and is divided into several steps as follows:
## Installing requirements

- Clone this repo:
```
git clone https://github.com/lzzy12/python-aria-mirror-bot mirror-bot/
cd mirror-bot
```

- Install requirements
For Debian based distros
```
sudo apt install python3
sudo snap install docker 
```
- For Arch and it's derivatives:
```
sudo pacman -S docker python
```

## Setting up config file
```
cp bot/config_sample.ini bot/config.ini
```
- Remove the first line saying:
```
_____REMOVE_THIS_LINE_____=True
```
Fill up rest of the fields. Meaning of each fields are discussed below:
- BOT_TOKEN : The telegram bot token that you get from @BotFather
- GDRIVE_FOLDER_ID : This is the folder ID of the Google Drive Folder to which you want to upload all the mirrors.
- DOWNLOAD_DIR : The path to the local folder where the downloads should be downloaded to
- DOWNLOAD_STATUS_UPDATE_INTERVAL : A short interval of time in seconds after which the Mirror progress message is updated. (I recommend to keep it 5 seconds at least)  
- OWNER_ID : The Telegram user ID (not username) of the owner of the bot
- AUTO_DELETE_MESSAGE_DURATION : Interval of time (in seconds), after which the bot deletes it's message (and command message) which is expected to be viewed instantly. Note: Set to -1 to never automatically delete messages

Note: You can limit maximum concurrent downloads by changing the value of MAX_CONCURRENT_DOWNLOADS in aria.sh. By default, it's set to 2
 
## Getting Google OAuth API credential file

- Visit the Google Cloud Console
- Go to the OAuth Consent tab, fill it, and save.
- Go to the Credentials tab and click Create Credentials -> OAuth Client ID
- Choose Other and Create.
- Use the download button to download your credentials.
- Move that file to the root of mirror-bot, and rename it to credentials.json
- Finally, run the script to generate token file (token.pickle) for Google Drive:
```
python3 generate_drive_token.py
```
## Deploying

- Start docker daemon (skip if already running):
```
sudo dockerd
```
- Build Docker image:
```
sudo docker build . -t mirror-bot
```
- Run the image:
```
sudo docker run mirror-bot
```

## Deploying on Heroku
- Run the script to generate token file(token.pickle) for Google Drive:
```
python3 generate_drive_token.py
```
- Change Bot Download Dir to /bot/downloads in config.ini file.
- Install [Heroku cli](https://devcenter.heroku.com/articles/heroku-cli)
- Login into your heroku account with command:
```
heroku login
```
- Create a new heroku app:
```
heroku create appname	
```
- Select This App in your Heroku-cli: 
```
heroku git:remote -a appname
```
- Change Dyno Stack to a Docker Container:
```
heroku stack:set container
```
- Add Private Credentials and Config Stuff:
```
git add -f credentials.json token.pickle ./bot/config.ini
```
- Commit new changes:
```
git commit -m "Added Creds."
```
- Push Code to Heroku:
```
git push heroku master --force
```
- Restart Worker by these commands:
```
heroku ps:scale worker=0
```
```
heroku ps:scale worker=1	 	
```
Heroku-Note: Doing authorizations ( /authorize command ) through telegram wont be permanent as heroku uses ephemeral filesystem. They will be reset on each dyno boot. As a workaround you can:
- Make a file authorized_chats.txt and write the user names and chat_id of you want to authorize, each separated by new line
- Then force add authorized_chats.txt to git and push it to heroku
```
git add authorized_chats.txt -f
git commit -asm "Added hardcoded authorized_chats.txt"
git push heroku heroku:master
```
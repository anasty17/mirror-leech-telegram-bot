# What is this repo about?
This is a telegram bot writen in python for mirroring files on the internet to our beloved Google Drive.

# Inspiration 
This project is heavily inspired from @out386 's telegram bot which is written in JS.

# Features supported:
- Mirroring direct download links to google drive
- Download progress
- Upload progress
- Download/upload speeds and ETAs

# Upcoming features (TODOs):
- Mega link mirror support
- Docker support
- More code clean up

# How to deploy?
Deploying is pretty much straight forward and is divided into several steps as follows:
## Installing requirements

- Clone this repo:
```
git clone https://github.com/lzzy12/python-aria-mirror-bot mirror-bot/
```

- Installing requirements
```
cd mirror-bot
pip3 install -r requirements.txt 
```

- Install aria2
For Debian based distros
```
sudo apt install aria2c
```
- For Arch and it's derivatives:
```
sudo pacman -S aria2
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
## Getting Google OAuth API credential file

- Visit the Google Cloud Console
- Go to the OAuth Consent tab, fill it, and save.
- Go to the Credentials tab and click Create Credentials -> OAuth Client ID
- Choose Other and Create.
- Use the download button to download your credentials.
- Move that file to the root of mirror-bot, and rename it to credentials.json

## Deploy
- Start aria client by `./aria.sh` on linux or running `aria.bat` on Windows (Any issue on Windows is not supported and will be closed immediately)
- Start the bot by
```
python3 -m bot
```

Note: You can limit maximum concurrent downloads by changing the value of MAX_CONCURRENT_DOWNLOADS in aria.sh. By default, it's set to 2
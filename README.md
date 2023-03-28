This is a Telegram Bot written in Python for mirroring files on the Internet to your Google Drive or Telegram. Based on [python-aria-mirror-bot](https://github.com/lzzy12/python-aria-mirror-bot)

# Features:

## By [anasty17](https://github.com/anasty17)
In each single file there is a major change from base code, it's almost totaly different. Here some of features and fixes that I remember.
### qBittorrent
- Qbittorrent support
- Select files from Torrent before and while downloading
- Seed torrents to specific ratio and time
- Edit Global Options while bot running from bot settings
### Aria2c
- Select files from Torrent before and while downloading
- Seed torrents to specific ratio and time
- Netrc support
- Direct link authentication for specific link while using the bot (it will work even if only username or password)
- Improve aria.sh
- Fix all download listener functions and status
- Edit Global Options while bot running from bot settings
### Leech
- Leech support
- Splitting
- Thumbnail for each user
- Set upload as document or as media for each user
- 4GB file upload with premium account
- Upload all files to specific superGroup/channel.
- Leech Split size and equal split size settings for each user
- Ability to leech splitted file parts in media group. Setting for each user
### Google
- Stop duplicates for all tasks except yt-dlp tasks
- Download from Google Drive
- Counting Google Drive files/folders
- Search in multiple Drive folder/TeamDrive
- Recursive Search (only with `root` or TeamDrive ID, folder ids will be listed with non-recursive method). Based on [Sreeraj](https://github.com/SVR666) searchX-bot.
- Use Token.pickle if file not found with Service Account, for all Gdrive functions
- Random Service Account for each task
### Status
- Clone Status
- Extract Status
- Archive Status
- Seed Status
- Status Pages for unlimited tasks
- Ability to cancel upload/clone/archive/extract/split
- Cancel all buttons for choosing specific tasks status to cancel
- Fix flooding issues
- Fix overall upload and download speed
### Yt-dlp
- Switch from youtube-dl to yt-dlp and fix all conflicts
- Yt-dlp quality buttons
- Ability to use specific yt-dlp option for each task
- Custom default video quality for each user
- Fix download progress
### Database
- Mongo Database support
- Store bot settings
- Store user settings including thumbnails and rclone config in database
- Store private files
- Store RSS data
- Store incompleted task messages
### Torrents Search
- Torrent search support
- Search on torrents with Torrent Search API
- Search on torrents with variable plugins using qBittorrent search engine
### Archives
- Zip instead of tar
- Using 7-zip tool to extract all supported types
- Extract rar, zip and 7z within folder or splits with or without password
- Zip file/folder with or without password
### RSS
- Rss feed. Based on this repository [rss-chan](https://github.com/hyPnOtICDo0g/rss-chan)
- Filters added
- Edit any feed while running: pause, resume, edit command and edit filters
- Rss for each user with tag
- Sudo settings to control users feeds
- All functions have been improved using buttons from one command.
### Rclone
- Download and Upload using rclone
- Ability to choose config, remote and path from list with buttons
- Ability to set rclone flags
- Rclone.conf for each user
- Rclone serve for combine remote to use it as index from all remotes
### Overall
- Docker image support for linux `amd64, arm64/v8, arm/v7`
- Switch from sync to async
- SWitch from python-telegram-bot to pyrogram
- Edit variables and overwrite the private files while bot running
- Update bot at startup and with restart command using `UPSTREAM_REPO`
- Improve Telegraph. Based on [Sreeraj](https://github.com/SVR666) loaderX-bot
- Mirror/Leech/Watch/Clone/Count/Del by reply
- Mirror/Leech/Clone multi links/files with one command
- Custom name for all links except torrents. For files you should add extension except yt-dlp links
- Extensions Filter for the files to be uploaded/cloned
- View Link button. Extra button to open index link in broswer instead of direct download for file
- Queueing System
- Ability to zip/unzip multi links in same directory. Mostly helpful in unziping tg file parts
- Almost all repository functions have been improved and many other details can't mention all of them
- Many bugs have been fixed

## From Base and other Repositories
- Mirror direct download links, Torrent, Mega.nz and Telegram files to Google Drive
- Copy files from someone's Drive to your Drive
- Download/Upload progress, Speeds and ETAs
- Mirror all youtube-dl supported links
- Docker support
- Uploading to Team Drive
- Index Link support
- Service Account support
- Delete files from Drive
- Multiple Trackers support
- Shell and Executor
- Add sudo users
- Extract password protected files
- Extract these filetypes
  > ZIP, RAR, TAR, 7z, ISO, WIM, CAB, GZIP, BZIP2, APM, ARJ, CHM, CPIO, CramFS, DEB, DMG, FAT, HFS, LZH, LZMA, LZMA2, MBR, MSI, MSLZ, NSIS, NTFS, RPM, SquashFS, UDF, VHD, XAR, Z, TAR.XZ
- Direct links Supported:
  > mediafire, letsupload.io, hxfile.co, antfiles, fembed.com, fembed.net, femax20.com, layarkacaxxi.icu, fcdn.stream, sbplay.org, naniplay.com, naniplay.nanime.in, naniplay.nanime.biz, sbembed.com, streamtape.com, streamsb.net, feurl.com, upload.ee, pixeldrain.com, racaty.net, 1fichier.com, 1drv.ms (Only works for file not folder or business account), uptobox.com and solidfiles.com, linkbox.to, shrdsk.me (sharedisk.io), akmfiles.com, wetransfer.com, mdisk.me (with ytdl), terabox.com (you need to add cookies txt with name) [terabox.txt](https://github.com/ytdl-org/youtube-dl#how-do-i-pass-cookies-to-youtube-dl) and almost every anonfiles based sites

# How to deploy?

## Prerequisites

- Tutorial Video from A to Z:
  - Thanks to [Wiszky](https://github.com/vishnoe115)
 <p><a href="https://youtu.be/IUmq1paCiHI"> <img src="https://img.shields.io/badge/See%20Video-black?style=for-the-badge&logo=YouTube" width="160""/></a></p>

### 1. Installing requirements

- Clone this repo:
```
git clone https://github.com/anasty17/mirror-leech-telegram-bot mirrorbot/ && cd mirrorbot
```
- For Debian based distros
```
sudo apt install python3 python3-pip
```
Install Docker by following the [official Docker docs](https://docs.docker.com/engine/install/debian/)

- For Arch and it's derivatives:
```
sudo pacman -S docker python
```
- Install dependencies for running setup scripts:
```
pip3 install -r requirements-cli.txt
```

------

### 2. Setting up config file

```
cp config_sample.env config.env
```
- Remove the first line saying:
```
_____REMOVE_THIS_LINE_____=True
```
Fill up rest of the fields. Meaning of each field is discussed below. **NOTE**: All values must be filled between quotes, even if it's `Int`, `Bool` or `List`.

**1. Required Fields**

- `BOT_TOKEN`: The Telegram Bot Token that you got from [@BotFather](https://t.me/BotFather). `Str`
- `OWNER_ID`: The Telegram User ID (not username) of the Owner of the bot. `Int`
- `TELEGRAM_API`: This is to authenticate your Telegram account for downloading Telegram files. You can get this from https://my.telegram.org. `Int`
- `TELEGRAM_HASH`: This is to authenticate your Telegram account for downloading Telegram files. You can get this from https://my.telegram.org. `Str`

**2. Optional Fields**

- `GDRIVE_ID`: This is the Folder/TeamDrive ID of the Google Drive OR `root` to which you want to upload all the mirrors using google-api-python-client. `Str`
- `RCLONE_PATH`: Default rclone path to which you want to upload all the mirrors using rclone. `Str`
- `DEFAULT_UPLOAD`: Whether `rc` to upload to `RCLONE_PATH` or `gd` to upload to `GDRIVE_ID`. Default is `gd`. Read More [HERE](https://github.com/anasty17/mirror-leech-telegram-bot/tree/master#upload).`Str`
- `RCLONE_FLAGS`: key:value|key|key|key:value . Check here all [RcloneFlags](https://rclone.org/flags/). `Str`
- `IS_TEAM_DRIVE`: Set `True` if uploading to TeamDrive using google-api-python-client. Default is `False`. `Bool`
- `DOWNLOAD_DIR`: The path to the local folder where the downloads should be downloaded to. `Str`
- `STATUS_UPDATE_INTERVAL`: Time in seconds after which the progress/status message will be updated. Recommended `10` seconds at least. `Int`
- `AUTO_DELETE_MESSAGE_DURATION`: Interval of time (in seconds), after which the bot deletes it's message and command message which is expected to be viewed instantly. **NOTE**: Set to `-1` to disable auto message deletion. `Int`
- `DATABASE_URL`: Your Mongo Database URL (Connection string). Follow this [Generate Database](https://github.com/anasty17/mirror-leech-telegram-bot/tree/master#generate-database) to generate database. Data will be saved in Database: auth and sudo users, users settings including thumbnails for each user, rss data and incomplete tasks. **NOTE**: You can always edit all settings that saved in database from the official site -> (Browse collections). `Str`
- `AUTHORIZED_CHATS`: Fill user_id and chat_id of groups/users you want to authorize. Separate them by space. `Int`
- `SUDO_USERS`: Fill user_id of users whom you want to give sudo permission. Separate them by space. `Int`
- `USE_SERVICE_ACCOUNTS`: Whether to use Service Accounts or not, with google-api-python-client. For this to work see [Using Service Accounts](https://github.com/anasty17/mirror-leech-telegram-bot#generate-service-accounts-what-is-service-account) section below. Default is `False`. `Bool`
- `INDEX_URL`: Refer to https://gitlab.com/ParveenBhadooOfficial/Google-Drive-Index. `Str`
- `RCLONE_SERVE_URL`: Valid URL where the bot is deployed to use rclone serve. Format of URL should be `http://myip`, where `myip` is the IP/Domain(public) of your bot or if you have chosen port other than `80` so write it in this format `http://myip:port` (`http` and not `https`). `Str`
- `RCLONE_SERVE_PORT`: Which is the **RCLONE_SERVE_URL** Port. Default is `8080`. `Int`
- `STATUS_LIMIT`: Limit the no. of tasks shown in status message with buttons. Default is `10`. **NOTE**: Recommended limit is `4` tasks. `Int`
- `STOP_DUPLICATE`: Bot will check file/folder name in Drive incase uploading to `GDRIVE_ID`. If it's present in Drive then downloading or cloning will be stopped. (**NOTE**: Item will be checked using name and not hash, so this feature is not perfect yet). Default is `False`. `Bool`
- `CMD_SUFFIX`: commands index number. This number will added at the end all commands. `Str`|`Int`
- `TORRENT_TIMEOUT`: Timeout of dead torrents downloading with qBittorrent and Aria2c in seconds. `Int`
- `EXTENSION_FILTER`: File extensions that won't upload/clone. Separate them by space. `Str`
- `INCOMPLETE_TASK_NOTIFIER`: Get incomplete task messages after restart. Require database and superGroup. Default is `False`. `Bool`
- `UPTOBOX_TOKEN`: Uptobox token to mirror uptobox links. Get it from [Uptobox Premium Account](https://uptobox.com/my_account). `str`
- `YT_DLP_QUALITY`: Default yt-dlp quality. Check all possible formats [HERE](https://github.com/yt-dlp/yt-dlp#filtering-formats). `str`

### Update
- `UPSTREAM_REPO`: Your github repository link, if your repo is private add `https://username:{githubtoken}@github.com/{username}/{reponame}` format. Get token from [Github settings](https://github.com/settings/tokens). So you can update your bot from filled repository on each restart. `Str`.
  - **NOTE**: Any change in docker or requirements you need to deploy/build again with updated repo to take effect. DON'T delete .gitignore file. For more information read [THIS](https://github.com/anasty17/mirror-leech-telegram-bot/tree/master#upstream-repo-recommended).
- `UPSTREAM_BRANCH`: Upstream branch for update. Default is `master`. `Str`

### Leech
- `LEECH_SPLIT_SIZE`: Size of split in bytes. Default is `2GB`. Default is `4GB` if your account is premium. `Int`
- `AS_DOCUMENT`: Default type of Telegram file upload. Default is `False` mean as media. `Bool`
- `EQUAL_SPLITS`: Split files larger than **LEECH_SPLIT_SIZE** into equal parts size (Not working with zip cmd). Default is `False`. `Bool`
- `MEDIA_GROUP`: View Uploaded splitted file parts in media group. Default is `False`. `Bool`.
- `LEECH_FILENAME_PREFIX`: Add custom word to leeched file name. `Str`
- `DUMP_CHAT`: Chat ID. Upload files to specific chat. `str`. **NOTE**: Only available for superGroup/channel. Add `-100` before channel/superGroup id. In short don't add bot id or your id!
- `USER_SESSION_STRING`: To download/upload from your telegram account. If you own premium account. To generate session string use this command `python3 generate_string_session.py` after mounting repo folder for sure. `Str`. **NOTE**: You can't use bot with private message. Use it with superGroup.

### qBittorrent/Aria2c
- `BASE_URL`: Valid BASE URL where the bot is deployed to use qbittorrent web selection. Format of URL should be `http://myip`, where `myip` is the IP/Domain(public) of your bot or if you have chosen port other than `80` so write it in this format `http://myip:port` (`http` and not `https`). `Str`
- `BASE_URL_PORT`: Which is the **BASE_URL** Port. Default is `80`. `Int`
- `WEB_PINCODE`: If empty or `False` means no more pincode required while torrent files web selection. `Bool`
  - **Qbittorrent NOTE**: If your facing ram exceeded issue then set limit for `MaxConnecs`, decrease `AsyncIOThreadsCount` in qbittorrent config and set limit of `DiskWriteCacheSize` to `32`.

### RSS
- `RSS_DELAY`: Time in seconds for rss refresh interval. Recommended `900` second at least. Default is `900` in sec. `Int`
- `RSS_CHAT_ID`: Chat ID where rss links will be sent. If you want message to be sent to the channel then add channel id. Add `-100` before channel id. `Int`
  - **RSS NOTE**: `RSS_CHAT_ID` is required, otherwise monitor will not work. You must use `USER_STRING_SESSION` --OR-- bot should be added in both channel and group(linked to channel) so messages sent by the bot to channel will be forwarded to group without using `USER_STRING_SESSION`. If `DATABASE_URL` not added you will miss the feeds while bot offline.

### MEGA
- `MEGA_API_KEY`: Mega.nz API key to mirror mega.nz links. Get it from [Mega SDK Page](https://mega.nz/sdk). `Int`
- `MEGA_EMAIL_ID`: E-Mail ID used to sign up on mega.nz for using premium account. `Str`
- `MEGA_PASSWORD`: Password for mega.nz account. `Str`

### Queue System
- `QUEUE_ALL`: Number of parallel tasks of downloads from (mega, telegram, yt-dlp, gdrive) + all uploads. For example if 20 task added and `QUEUE_ALL` is `8`, then the summation of uploading and downloading tasks are 8 and the rest in queue. `Int`. **NOTE**: if you want to fill `QUEUE_DOWNLOAD` or `QUEUE_UPLOAD`, then `QUEUE_ALL` value must be greater than or equal to the greatest one and less than or equal to summation of `QUEUE_UPLOAD` and `QUEUE_DOWNLOAD`.
- `QUEUE_DOWNLOAD`: Number of parallel downloading tasks from mega, telegram, yt-dlp and gdrive. `Int`
- `QUEUE_UPLOAD`: Number of all parallel uploading tasks. `Int`

### Buttons
- `VIEW_LINK`: View Link button to open file Index Link in browser instead of direct download link, you can figure out if it's compatible with your Index code or not, open any video from you Index and check if its URL ends with `?a=view`. Compatible with [BhadooIndex](https://gitlab.com/ParveenBhadooOfficial/Google-Drive-Index) Code. Default is `False`. `Bool`

### Torrent Search
- `SEARCH_API_LINK`: Search api app link. Get your api from deploying this [repository](https://github.com/Ryuk-me/Torrent-Api-py). `Str`
  - Supported Sites:
  >1337x, Piratebay, Nyaasi, Torlock, Torrent Galaxy, Zooqle, Kickass, Bitsearch, MagnetDL, Libgen, YTS, Limetorrent, TorrentFunk, Glodls, TorrentProject and YourBittorrent
- `SEARCH_LIMIT`: Search limit for search api, limit for each site and not overall result limit. Default is zero (Default api limit for each site). `Int`
- `SEARCH_PLUGINS`: List of qBittorrent search plugins (github raw links). I have added some plugins, you can remove/add plugins as you want. Main Source: [qBittorrent Search Plugins (Official/Unofficial)](https://github.com/qbittorrent/search-plugins/wiki/Unofficial-search-plugins). `List`

------

### 3. Getting Google OAuth API credential file and token.pickle

**NOTES**
- Old authentication changed, now we can't use bot or replit to generate token.pickle. You need OS with a local browser. For example `Termux`.
- Windows users should install python3 and pip. You can find how to install and use them from google or from this [telegraph](https://telegra.ph/Create-Telegram-Mirror-Leech-Bot-by-Deploying-App-with-Heroku-Branch-using-Github-Workflow-12-06) from [Wiszky](https://github.com/vishnoe115) tutorial.
- You can ONLY open the generated link from `generate_drive_token.py` in local browser.

1. Visit the [Google Cloud Console](https://console.developers.google.com/apis/credentials)
2. Go to the OAuth Consent tab, fill it, and save.
3. Go to the Credentials tab and click Create Credentials -> OAuth Client ID
4. Choose Desktop and Create.
5. Publish your OAuth consent screen App to prevent **token.pickle** from expire
6. Use the download button to download your credentials.
7. Move that file to the root of mirrorbot, and rename it to **credentials.json**
8. Visit [Google API page](https://console.developers.google.com/apis/library)
9. Search for Google Drive Api and enable it
10. Finally, run the script to generate **token.pickle** file for Google Drive:
```
pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 generate_drive_token.py
```
------

### 4. Build And Run the Docker Image

Make sure you still mount the app folder and installed the docker from official documentation.
- There are two methods to build and run the docker:
  1. Using official docker commands.
  2. Using docker-compose. (Recommended)

------

#### Build And Run The Docker Image Using Official Docker Commands

- Start Docker daemon (SKIP if already running, mostly you don't need to do this):
```
sudo dockerd
```
- Build Docker image:
```
sudo docker build . -t mltb
```
- Run the image:
```
sudo docker run -p 80:80 -p 8080:8080 mltb
```
- To stop the running image:
```
sudo docker ps
```
```
sudo docker stop id
```

----

#### Build And Run The Docker Image Using docker-compose

**NOTE**: If you want to use ports other than 80 and 8080 for torrent file selection and rclone serve respectively, change it in [docker-compose.yml](https://github.com/anasty17/mirror-leech-telegram-bot/blob/master/docker-compose.yml) also.

```
sudo apt install docker-compose
```
- Build and run Docker image or to view current running image:
```
sudo docker-compose up
```
- After editing files with nano for example (nano start.sh):
```
sudo docker-compose up --build
```
- To stop the running image:
```
sudo docker-compose stop
```
- To run the image:
```
sudo docker-compose start
```
- To get latest log from already running image (after mounting the folder):
```
sudo docker-compose up
```
- Tutorial video from Tortoolkit repo for docker-compose and checking ports
<p><a href="https://youtu.be/c8_TU1sPK08"> <img src="https://img.shields.io/badge/See%20Video-black?style=for-the-badge&logo=YouTube" width="160""/></a></p>

------

#### Docker Notes

**IMPORTANT NOTES**:
1. Set `BASE_URL_PORT` and `RCLONE_SERVE_PORT` variables to any port you want to use. Default is `80` and `8080` respectively.
2. You should stop the running image before deleting the container and you should delete the container before the image.
3. To delete the container (this will not affect on the image):
```
sudo docker container prune
```
4. To delete the images:
```
sudo docker image prune -a
```
5. Check the number of processing units of your machine with `nproc` cmd and times it by 4, then edit `AsyncIOThreadsCount` in qBittorrent.conf.

------

# Extras

## Bot commands to be set in [@BotFather](https://t.me/BotFather)

```
mirror - or /m Mirror
zipmirror - or /zm Mirror and upload as zip
unzipmirror - or /uzm Mirror and extract files
qbmirror - or /qm Mirror torrent using qBittorrent
qbzipmirror - or /qzm Mirror torrent using qb and upload as zip
qbunzipmirror - or /quzm Mirror torrent using qb and extract files
leech - or /l Leech
zipleech - or /zl Leech and upload as zip
unzipleech - or /uzl Leech and extract files
qbleech - or /ql Leech torrent using qBittorrent
qbzipleech - or /qzl Leech torrent using qb and upload as zip
qbunzipleech - or /quzl Leech torrent using qb and extract
clone - Copy file/folder to Drive
count - Count file/folder from Drive
ytdl - or /y Mirror yt-dlp supported link
ytdlzip - or /yz Mirror yt-dlp supported link as zip
ytdlleech - or /yl Leech through yt-dlp supported link
ytdlzipleech - or /yzl Leech yt-dlp support link as zip
usetting - User settings
bsetting - Bot settings
status - Get Mirror Status message
btsel - Select files from torrent
rss - Rss menu
list - Search files in Drive
search - Search for torrents with API
cancel - Cancel a task
cancelall - Cancel all tasks
del - Delete file/folder from Drive
log - Get the Bot Log
shell - Run commands in Shell
restart - Restart the Bot
stats - Bot Usage Stats
ping - Ping the Bot
help - All cmds with description
```
------

## UPSTREAM REPO (Recommended)

- `UPSTREAM_REPO` variable can be used for edit/add any file in repository.
- You can add private/public repository link to grab/overwrite all files from it.
- You can skip adding the privates files like token.pickle or accounts folder before deploying, simply fill `UPSTREAM_REPO` private one in case you want to grab all files including private files.
- If you added private files while deploying and you have added private `UPSTREAM_REPO` and your private files in this private repository, so your private files will be overwritten from this repository. Also if you are using database for private files, then all files from database will override the private files that added before deploying or from private `UPSTREAM_REPO`.
- If you filled `UPSTREAM_REPO` with the official repository link, then be carefull incase any change in requirements.txt your bot will not start after restart. In this case you need to deploy again with updated code to install the new requirements or simply by changing the `UPSTREAM_REPO` to you fork link with that old updates.
- In case you you filled `UPSTREAM_REPO` with your fork link be carefull also if you fetched the commits from the official repository.
- The changes in your `UPSTREAM_REPO` will take affect only after restart.

------

## Bittorrent Seed

- Add `d:ratio:time` perfix along with leech or mirror cmd.
- Using `d` perfix alone will lead to use global options for aria2c or qbittorrent.

### Qbittorrent
- Global options: `GlobalMaxRatio` and `GlobalMaxSeedingMinutes` in qbittorrent.conf, `-1` means no limit, but you can cancel manually.
  - **NOTE**: Don't change `MaxRatioAction`.

### Aria2c
- Global options: `--seed-ratio` (0 means no limit) and `--seed-time` (0 means no seed) in aria.sh.

------

## Using Service Accounts for uploading to avoid user rate limit

>For Service Account to work, you must set `USE_SERVICE_ACCOUNTS` = "True" in config file or environment variables.
>**NOTE**: Using Service Accounts is only recommended while uploading to a Team Drive.

### 1. Generate Service Accounts. [What is Service Account?](https://cloud.google.com/iam/docs/service-accounts)
Let us create only the Service Accounts that we need.

**Warning**: Abuse of this feature is not the aim of this project and we do **NOT** recommend that you make a lot of projects, just one project and 100 SAs allow you plenty of use, its also possible that over abuse might get your projects banned by Google.

>**NOTE**: If you have created SAs in past from this script, you can also just re download the keys by running:
```
python3 gen_sa_accounts.py --download-keys $PROJECTID
```
>**NOTE:** 1 Service Account can upload/copy around 750 GB a day, 1 project can make 100 Service Accounts so you can upload 75 TB a day.

>**NOTE:** All people can copy `2TB/DAY` from each file creator (uploader account), so if you got error `userRateLimitExceeded` that doesn't mean your limit exceeded but file creator limit have been exceeded which is `2TB/DAY`.

#### Two methods to create service accounts
Choose one of these methods

##### 1. Create Service Accounts in existed Project (Recommended Method)
- List your projects ids
```
python3 gen_sa_accounts.py --list-projects
```
- Enable services automatically by this command
```
python3 gen_sa_accounts.py --enable-services $PROJECTID
```
- Create Sevice Accounts to current project
```
python3 gen_sa_accounts.py --create-sas $PROJECTID
```
- Download Sevice Accounts as accounts folder
```
python3 gen_sa_accounts.py --download-keys $PROJECTID
```

##### 2. Create Service Accounts in New Project
```
python3 gen_sa_accounts.py --quick-setup 1 --new-only
```
A folder named accounts will be created which will contain keys for the Service Accounts.

### 2. Add Service Accounts

#### Two methods to add service accounts
Choose one of these methods

##### 1. Add Them To Google Group then to Team Drive (Recommended)
- Mount accounts folder
```
cd accounts
```
- Grab emails form all accounts to emails.txt file that would be created in accounts folder
- `For Windows using PowerShell`
```
$emails = Get-ChildItem .\**.json |Get-Content -Raw |ConvertFrom-Json |Select -ExpandProperty client_email >>emails.txt
```
- `For Linux`
```
grep -oPh '"client_email": "\K[^"]+' *.json > emails.txt
```
- Unmount acounts folder
```
cd ..
```
Then add emails from emails.txt to Google Group, after that add this Google Group to your Shared Drive and promote it to manager and delete email.txt file from accounts folder

##### 2. Add Them To Team Drive Directly
- Run:
```
python3 add_to_team_drive.py -d SharedTeamDriveSrcID
```

------

## Upload

- `RCLONE_PATH` is like `GDRIVE_ID` a default path for mirror. In additional to those variables `DEFAULT_UPLOAD` to choose the default tool whether it's rclone or google-api-python-client.
- If `DEFAULT_UPLOAD` = 'rc' then you must fill `RCLONE_PATH` with path as default one or with `rcl` to select destination path on each new task.
- If `DEFAULT_UPLOAD` = 'gd' then you must fill `GDRIVE_ID` with folder/TD id.
- If rclone.conf uploaded from usetting or added in `rclone/{user_id}.conf` then `RCLONE_PATH` must start with `mrcc:`.
- Whenever you want to write path manually to use user rclone.conf that added from usetting then you must add the `mrcc:` at the beginning.

------

## Generate Database

1. Go to `https://mongodb.com/` and sign-up.
2. Create Shared Cluster.
3. Press on `Database` under `Deployment` Header, your created cluster will be there.
5. Press on connect, choose `Allow Acces From Anywhere` and press on `Add IP Address` without editing the ip, then create user.
6. After creating user press on `Choose a connection`, then press on `Connect your application`. Choose `Driver` **python** and `version` **3.6 or later**.
7. Copy your `connection string` and replace `<password>` with the password of your user, then press close.

------

## Multi Drive List
To use list from multi TD/folder. Run driveid.py in your terminal and follow it. It will generate **list_drives.txt** file or u can simply create `list_drives.txt` file in working directory and fill it, check below format:
```
DriveName folderID/tdID or `root` IndexLink(if available)
DriveName folderID/tdID or `root` IndexLink(if available)
```

Example:
```
TD1 root https://example.dev
TD2 0AO1JDB1t3i5jUk9PVA https://example.dev
```
-----

## Yt-dlp and Aria2c Authentication Using .netrc File
For using your premium accounts in yt-dlp or for protected Index Links, create .netrc file according to following format:

**Note**: Create .netrc and not netrc, this file will be hidden, so view hidden files to edit it after creation.

Format:
```
machine host login username password my_password
```
Example:
```
machine instagram login anas.tayyar password mypassword
```
**Instagram Note**: You must login even if you want to download public posts and after first try you must confirm that this was you logged in from different ip(you can confirm from phone app).

**Youtube Note**: For `youtube` authentication use [cookies.txt](https://github.com/ytdl-org/youtube-dl#how-do-i-pass-cookies-to-youtube-dl) file.

Using Aria2c you can also use built in feature from bot with or without username. Here example for index link without username.
```
machine example.workers.dev password index_password
```
Where host is the name of extractor (eg. instagram, Twitch). Multiple accounts of different hosts can be added each separated by a new line.

-----

## Donations

<p> If you feel like showing your appreciation for this project, then how about buying me a coffee.</p>

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/anasty17)

USDT Address:
```
TEzjjfkxLKQqndpsdpkA7jgiX7QQCL5p4f
```
Network:
```
TRC20
```
BTC Address:
```
17dkvxjqdc3yiaTs6dpjUB1TjV3tD7ScWe
```
ETH Address:
```
0xf798a8a1c72d593e16d8f3bb619ebd1a093c7309
```

-----

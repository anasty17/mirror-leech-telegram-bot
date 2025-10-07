This Telegram Bot, based on [python-aria-mirror-bot](https://github.com/lzzy12/python-aria-mirror-bot), has undergone
substantial modifications and is designed for efficiently mirroring or leeching files from the Internet to various
destinations, including Google Drive, Telegram, or any rclone-supported cloud. It is built using asynchronous
programming in Python.

- **TELEGRAM CHANNEL:** https://t.me/mltb_official_channel
- **TELEGRAM GROUP:** https://t.me/mltb_official_support

<details>
  <summary><h1>Features</h1></summary>

<details>
  <summary><h5>QBittorrent</h5></summary>

- External access to webui, so you can remove files or edit settings. Then you can sync settings in database with sync button in bsetting
- Select files from a Torrent before and during download using mltb file selector (Requires Base URL) (task option)
- Seed torrents to a specific ratio and time (task option)
- Edit Global Options while the bot is running from bot settings (global option)

</details>

<details>
  <summary><h5>Aria2c</h5></summary>

- Select files from a Torrent before and during download (Requires Base URL) (task option)
- Seed torrents to a specific ratio and time (task option)
- Netrc support (global option)
- Direct link authentication for a specific link while using the bot (it will work even if only the username or password
  is provided) (task option)
- Edit Global Options while the bot is running from bot settings (global option)

</details>

<details>
  <summary><h5>Sabnzbd</h5></summary>

- External access to web interface, so you can remove files or edit settings. Then you can sync settings in database with sync button in bsetting
- Remove files from job before and during download using mltb file selector (Requires Base URL) (task option)
- Edit Global Options while the bot is running from bot settings (global option)
- Servers menu to edit/add/remove usenet servers

</details>

<details>
  <summary><h5>TG Upload/Download</h5></summary>

- Split size (global, user, and task option)
- Thumbnail (user and task option)
- Leech filename prefix (user option)
- Set upload as a document or as media (global, user and task option)
- Upload all files to a specific chat (superGroup/channel/private/topic) (global, user, and task option)
- Equal split size settings (global and user option)
- Ability to leech split file parts in a media group (global and user option)
- Download restricted messages (document or link) by tg private/public/super links (task option)
- Choose transfer by bot or user session incase you have a premium plan (global, user option and task option)
- Mix upload between user and bot session with respect to file size (global, user option and task option)
- Upload with custom layout multiple thumbnail (global, user option and task option)
- Topics support

</details>

<details>
  <summary><h5>Google Drive</h5></summary>

- Download/Upload/Clone/Delete/Count from/to Google Drive
- Count Google Drive files/folders
- Search in multiple Drive folder/TeamDrive
- Use Token.pickle if the file is not found with a Service Account, for all Gdrive functions
- Random Service Account for each task
- Recursive Search (only with `root` or TeamDrive ID, folder ids will be listed with a non-recursive method). Based
  on [Sreeraj](https://github.com/SVR666) searchX-bot. (task option)
- Stop Duplicates (global and user option)
- Custom upload destination (global, user, and task option)
- Ability to choose token.pickle or service acccount and upload destinations from list with or without buttons (global, user and task option)
- Index link support only
  for [Bhadoo](https://gitlab.com/GoogleDriveIndex/Google-Drive-Index/-/blob/master/src/worker.js)

</details>

<details>
  <summary><h5>Rclone</h5></summary>

- Transfer (download/upload/clone-server-side) without or with random service accounts (global and user option)
- Ability to choose config, remote and path from list with or without buttons (global, user and task option)
- Ability to set flags for each task or globally from config (global, user and task option)
- Ability to select specific files or folders to download/copy using buttons (task option)
- Rclone.conf (global and user option)
- Rclone serve for combine remote to use it as index from all remotes (global option)
- Upload destination (global, user and task option)

</details>

<details>
  <summary><h5>Status</h5></summary>

- Download/Upload/Extract/Archive/Seed/Clone Status
- Status Pages for an unlimited number of tasks, view a specific number of tasks in a message (global option)
- Interval message update (global option)
- Next/Previous buttons to get different pages (global and user option)
- Status buttons to get specific tasks for the chosen status regarding transfer type if the number of tasks is more than
  30 (global and user option)
- Steps buttons for how much next/previous buttons should step backward/forward (global and user option)
- Status for each user (no auto refresh)

</details>

<details>
  <summary><h5>Yt-dlp</h5></summary>

- Yt-dlp quality buttons (task option)
- Ability to use a specific yt-dlp option (global, user, and task option)
- Netrc support (global option)
- Cookies support (global option)
- Embed the original thumbnail and add it for leech
- All supported audio formats

</details>

<details>
  <summary><h5>JDownloader</h5></summary>

- Synchronize Settings (global option)
- Waiting to select (enable/disable files or change variants) before download start
- DLC file support
- All settings can be edited from the remote access to your JDownloader with Web Interface, Android App, iPhone App or
  Browser Extensions

</details>

<details>
  <summary><h5>Mongo Database</h5></summary>

- Store bot settings
- Store user settings including thumbnails and all private files
- Store RSS data
- Store incompleted task messages
- Store JDownloader settings
- Store config.py file on first build and incase any change occured to it, then next build it will define variables
  from config.py instead of database

</details>

<details>
  <summary><h5>Torrents Search</h5></summary>

- Search on torrents with Torrent Search API
- Search on torrents with variable plugins using qBittorrent search engine

</details>

<details>
  <summary><h5>Archives</h5></summary>

- Extract splits with or without password
- Zip file/folder with or without password and splits incase of leech
- Using 7z package to extract with or without password all supported types

</details>

<details>
  <summary><h5>RSS</h5></summary>

- Based on this repository [rss-chan](https://github.com/hyPnOtICDo0g/rss-chan)
- Rss feed (user option)
- Title Filters (feed option)
- Edit any feed while running: pause, resume, edit command and edit filters (feed option)
- Sudo settings to control users feeds
- All functions have been improved using buttons from one command.

</details>

<details>
  <summary><h5>Overall</h5></summary>

- Docker image support for linux `amd64, arm64/v8, arm/v7`
- Edit variables and overwrite the private files while bot running (bot, user settings)
- Update bot at startup and with restart command using `UPSTREAM_REPO`
- Telegraph. Based on [Sreeraj](https://github.com/SVR666) loaderX-bot
- Mirror/Leech/Watch/Clone/Count/Del by reply
- Mirror/Leech/Clone multi links/files with one command
- Custom name for all links except torrents. For files you should add extension except yt-dlp links (global and user
  option)
- Exclude files with specific extensions from being uploaded/cloned (global and user option)
- View Link button. Extra button to open index link in browser instead of direct download for file
- Queueing System for all tasks (global option)
- Ability to zip/unzip multi links in same directory. Mostly helpful in unzipping tg file parts (task option)
- Bulk download from telegram txt file or text message contains links separated by new line (task option)
- Join splitted files that have splitted before by split(linux pkg) (task option)
- Sample video Generator (task option)
- Screenshots Generator (task option)
- Ability to cancel upload/clone/archive/extract/split/queue (task option)
- Cancel all buttons for choosing specific tasks status to cancel (global option)
- Convert videos and audios to specific format with filter (task option)
- Force start to upload or download or both from queue using cmds or args once you add the download (task option)
- Shell and Executor
- Add sudo users
- Ability to save upload paths
- Name Substitution to rename the files before upload
- User can select whether he want to use his rclone.conf/token.pickle without adding mpt: or mrcc: before path/gd-id
- FFmpeg commands to execute it after download (task option)
- Supported Direct links Generators:

> mediafire (file/folders), hxfile.co (need cookies txt with name) [hxfile.txt], streamtape.com, streamsb.net, streamhub.ink,
> streamvid.net, doodstream.com,
> feurl.com, upload.ee, pixeldrain.com, racaty.net, 1fichier.com, 1drv.ms (Only works for file not folder or business
> account), filelions.com, streamwish.com, send.cm (file/folders), solidfiles.com, linkbox.to (file/folders),
> shrdsk.me (
> sharedisk.io), akmfiles.com, wetransfer.com, pcloud.link, gofile.io (file/folders), easyupload.io, mdisk.me (with
> ytdl),
> tmpsend.com, qiwi.gg, berkasdrive.com, mp4upload.com, terabox.com (videos only file/folders).

</details>
</details>

<details>
  <summary><h1>How to deploy?</h1></summary>

<details>
  <summary><h2>Prerequisites</h2></summary>

<details>
  <summary><h5>1. Installing requirements</h5></summary>

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

</details>

<details>
  <summary><h5>2. Setting up config file</h5></summary>

```
cp config_sample.py config.py
```

Fill up rest of the fields. Meaning of each field is discussed below.

**1. Required Fields**

- `BOT_TOKEN` (`Str`):  The Telegram Bot Token that you got from [@BotFather](https://t.me/BotFather).

- `OWNER_ID` (`Int`):  The Telegram User ID (not username) of the Owner of the bot.

- `TELEGRAM_API` (`Int`): This is to authenticate your Telegram account for downloading Telegram files. You can get this
  from <https://my.telegram.org>.

- `TELEGRAM_HASH` (`Str`):  This is to authenticate your Telegram account for downloading Telegram files. You can get this
  from <https://my.telegram.org>.

**2. Optional Fields**
- `DATABASE_URL` (`Str`): Your Mongo Database URL (Connection string). Follow this [Create Database](https://github.com/anasty17/test?tab=readme-ov-file#create-database) to create database. Data will be saved in Database: bot settings, users settings, rss data and incomplete tasks. **NOTE**: You can always edit all settings that saved in database from the official site -> (Browse collections). 

- `CMD_SUFFIX` (`Str`|`Int`): Commands index number. This number will added at the end all commands.

- `AUTHORIZED_CHATS` (`Str`): Fill user_id and chat_id of groups/users you want to authorize. To auth only specific topic(s) write it in this format `chat_id|thread_id` Ex:-100XXXXXXXXXXX or -100XXXXXXXXXXX|10 or -100XXXXXXXXXXX|10|12. Separate them by spaces.

- `SUDO_USERS` (`Str`):  Fill user_id of users whom you want to give sudo permission. Separate them by spaces.

- `UPLOAD_PATHS` (`Dict`): Send Dict of keys that have path values. Example: {"path 1": "remote:rclonefolder", "path 2": "gdrive1 id", "path 3": "tg chat id", "path 4": "mrcc:remote:", "path 5": "b: @username"}. 

- `DEFAULT_UPLOAD` (`Str`): Whether `rc` to upload to `RCLONE_PATH` or `gd` to upload to `GDRIVE_ID`. Default is `rc`. Read More [HERE](https://github.com/anasty17/mirror-leech-telegram-bot/tree/master#upload).

- `STATUS_UPDATE_INTERVAL` (`Int`): Time in seconds after which the progress/status message will be updated. Recommended `10` seconds at least.

- `STATUS_LIMIT` (`Int`): Limit the no. of tasks shown in status message with buttons. Default is `4`. **NOTE**: Recommended limit is `4` tasks.

- `EXCLUDED_EXTENSIONS` (`Str`): File extensions that won't upload/clone. Separate them by spaces.

- `INCOMPLETE_TASK_NOTIFIER` (`Bool`): Get incomplete task messages after restart. Require database and superGroup. Default
is `False`.

- `FILELION_API` (`Str`): Filelion api key to mirror Filelion links. Get it
from [Filelion](https://vidhide.com/?op=my_account).

- `STREAMWISH_API` (`Str`): Streamwish api key to mirror Streamwish links. Get it
from [Streamwish](https://streamwish.com/?op=my_account).

- `YT_DLP_OPTIONS` (`Dict`): Dict of yt-dlp options. Check all possible
options [HERE](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184) or use this [script](https://t.me/mltb_official_channel/177) to convert cli arguments to api options. Format: {key: value, key: value, key: value}.
  - Example: {"format": "bv*+mergeall[vcodec=none]", "nocheckcertificate": True, "playliststart": 10, "fragment_retries": float("inf"), "matchtitle": "S13", "writesubtitles": True, "live_from_start": True, "postprocessor_args": {"ffmpeg": ["-threads", "4"]}, "wait_for_video": (5, 100), "download_ranges": [{"start_time": 0, "end_time": 10}]}

- `USE_SERVICE_ACCOUNTS` (`Bool`): Whether to use Service Accounts or not, with google-api-python-client. For this to work
see [Using Service Accounts](https://github.com/anasty17/mirror-leech-telegram-bot#generate-service-accounts-what-is-service-account) section below. Default is `False`.

- `FFMPEG_CMDS` (`Dict`): Dict of list values of ffmpeg commands. You can set multiple ffmpeg commands for all files before upload. Don't write ffmpeg at beginning, start directly with the arguments. `Dict`
  - Examples: {"subtitle": ["-i mltb.mkv -c copy -c:s srt mltb.mkv", "-i mltb.video -c copy -c:s srt mltb"], "convert": ["-i mltb.m4a -c:a libmp3lame -q:a 2 mltb.mp3", "-i mltb.audio -c:a libmp3lame -q:a 2 mltb.mp3"], extract: ["-i mltb -map 0:a -c copy mltb.mka -map 0:s -c copy mltb.srt"], "metadata": ["-i mltb.mkv -map 0 -map -0:v:1 -map -0:s -map 0:s:0 -map -0:v:m:attachment -c copy -metadata:s:v:0 title={title} -metadata:s:a:0 title={title} -metadata:s:a:1 title={title2} -metadata:s:a:2 title={title2} -c:s srt -metadata:s:s:0 title={title3} mltb -y -del"], "watermark": ["-i mltb -i tg://openmessage?user_id=5272663208&message_id=322801 -filter_complex 'overlay=W-w-10:H-h-10' -c:a copy mltb"]}
  **Notes**:
  - Don't add ffmpeg at the beginning!
  - Add `-del` to the list which you want from the bot to delete the original files after command run complete!
  - To execute one of those lists in bot for example, you must use -ff subtitle (list key) or -ff convert (list key)
  **Example**:
  - Here I will explain how to use mltb.* which is reference to files you want to work on.
  1. First cmd: the input is mltb.mkv so this cmd will work only on mkv videos and the output is mltb.mkv also so all outputs is mkv. `-del` will delete the original media after complete run of the cmd.
  2. Second cmd: the input is mltb.video so this cmd will work on all videos and the output is only mltb so the extenstion is same as input files.
  3. Third cmd: the input in mltb.m4a so this cmd will work only on m4a audios and the output is mltb.mp3 so the output extension is mp3.
  4. Fourth cmd: the input is mltb.audio so this cmd will work on all audios and the output is mltb.mp3 so the output extension is mp3.
  5. FFmpeg Variables in last cmd which is metadata ({title}, {title2}, etc...), you can edit them in usetting
  6. Telegram link for small size inputs like photo to set watermark.

- `NAME_SUBSTITUTE` (`Str`): Add word/letter/character/sentense/pattern to remove or replace with other words with sensitive case or without. 
  **Notes**:
    - Before any character you must add `\BACKSLASH`, those are the characters: `\^$.|?*+()[]{}-`
    * Example: script/code/s | mirror/leech | tea/ /s | clone | cpu/ | \[mltb\]/mltb | \\text\\/text/s
    - script will get replaced by code with sensitive case
    - mirror will get replaced by leech
    - tea will get replaced by space with sensitive case
    - clone will get removed
    - cpu will get replaced by space
    - [mltb] will get replaced by mltb
    - \text\ will get replaced by text with sensitive case

**3. GDrive Tools**

- `GDRIVE_ID` (`Str`): This is the Folder/TeamDrive ID of the Google Drive OR `root` to which you want to upload all the mirrors using google-api-python-client.

- `IS_TEAM_DRIVE` (`Bool`): Set `True` if uploading to TeamDrive using google-api-python-client. Default is `False`.

- `INDEX_URL` (`Str`): Refer to <https://gitlab.com/ParveenBhadooOfficial/Google-Drive-Index>. Example: https://xxx.xx.workers.dev/0: (If you have multiple ID config -- replace 0: with the desired id index) or https://xxx.xx.workers.dev without index if you only have one ID in config which is the basic config.

- `STOP_DUPLICATE` (`Bool`): Bot will check file/folder name in Drive incase uploading to `GDRIVE_ID`. If it's present in Drive then downloading or cloning will be stopped. (**NOTE**: Item will be checked using name and not hash, so this feature is not perfect). Default is `False`.

**4. Rclone**

- `RCLONE_PATH` (`Str`): Default rclone path to which you want to upload all the files/folders using rclone.

- `RCLONE_FLAGS` (`Str`): --key:value|--key|--key|--key:value . Check here all [RcloneFlags](https://rclone.org/flags/).

- `RCLONE_SERVE_URL` (`Str`): Valid URL where the bot is deployed to use rclone serve. Format of URL should be `http://myip`, where `myip` is the IP/Domain(public) of your bot or if you have chosen port other than `80` so write it in this format `http://myip:port` (`http` and not `https`).

- `RCLONE_SERVE_PORT` (`Int`): Which is the **RCLONE_SERVE_URL** Port. Default is `8080`.

- `RCLONE_SERVE_USER` (`Str`): Username for rclone serve authentication.

- `RCLONE_SERVE_PASS` (`Str`): Password for rclone serve authentication.

**5. Update**

- `UPSTREAM_REPO` (`Str`): Your github repository link, if your repo is private add `https://username:{githubtoken}@github.com/{username}/{reponame}` format. Get token from [Github settings](https://github.com/settings/tokens). So you can update your bot from filled repository on each restart.
  - **NOTE**: Any change in docker or requirements you need to deploy/build again with updated repo to take effect. DON'T delete .gitignore file. For more information read [THIS](https://github.com/anasty17/mirror-leech-telegram-bot/tree/master#upstream-repo-recommended).

- `UPSTREAM_BRANCH` (`Str`): Upstream branch for update. Default is `master`.

**6. Leech**

- `LEECH_SPLIT_SIZE` (`Int`): Size of split in bytes. Default is `2GB`. Default is `4GB` if your account is premium.
- `AS_DOCUMENT` (`Bool`): Default type of Telegram file upload. Default is `False` mean as media.

- `EQUAL_SPLITS` (`Bool`): Split files larger than **LEECH_SPLIT_SIZE** into equal parts size (Not working with zip cmd). Default is `False`.

- `MEDIA_GROUP` (`Bool`): View Uploaded splitted file parts in media group. Default is `False`.

- `USER_TRANSMISSION` (`Bool`): Upload/Download by user session. Only in superChat. Default is `False`.

- `HYBRID_LEECH` (`Bool`): Upload by user and bot session with respect to file size. Only in superChat. Default is `False`.

- `LEECH_FILENAME_PREFIX` (`Str`): Add custom word to leeched file name.

- `LEECH_DUMP_CHAT` (`Int`|`Str`): ID or USERNAME or PM(private message) to where files would be uploaded. Add `-100` before channel/superGroup id. To use only specific topic write it in this format `chat_id|thread_id`. Ex:-100XXXXXXXXXXX or -100XXXXXXXXXXX|10 or pm or @xxxxxxx or @xxxxxxx|10.

- `THUMBNAIL_LAYOUT` (`Str`): Thumbnail layout (widthxheight, 2x2, 3x3, 2x4, 4x4, ...) of how many photo arranged for the thumbnail.

**7. qBittorrent/Aria2c/Sabnzbd**

- `TORRENT_TIMEOUT` (`Int`): Timeout of dead torrents downloading with qBittorrent and Aria2c in seconds.

- `BASE_URL` (`Str`): Valid BASE URL where the bot is deployed to use torrent/nzb web files selection. Format of URL should be `http://myip`, where `myip` is the IP/Domain(public) of your bot or if you have chosen port other than `80` so write it in this format `http://myip:port` (`http` and not `https`).

- `BASE_URL_PORT` (`Int`): Which is the **BASE_URL** Port. Default is `80`.

- `WEB_PINCODE` (`Bool`): Whether to ask for pincode before selecting files from torrent in web or not. Default is `False`.
    - **Qbittorrent NOTE**: If your facing ram issues then set limit for `MaxConnections`, decrease `AsyncIOThreadsCount`, set limit of `DiskWriteCacheSize` to `32` and decrease `MemoryWorkingSetLimit` from qbittorrent.conf or bsetting command.
    - Open port 8090 in your vps to access webui from any device. username: mltb, password: mltbmltb

**8. JDownloader**

- `JD_EMAIL` (`Str`): jdownloader email sign up on [JDownloader](https://my.jdownloader.org/).

- `JD_PASS` (`Str`): jdownloader password.
  - **JDownloader Config**: You can use your config from local machine in bot by *zipping* cfg folder (cfg.zip) and add it in repo folder.

**9. Sabnzbd**

- `USENET_SERVERS` (`List`): list of dictionaries, you can add as much as you want and there is a button for servers in sabnzbd settings to edit current servers and add new servers.

  ***[{'name': 'main', 'host': '', 'port': 563, 'timeout': 60, 'username': '', 'password': '', 'connections': 8, 'ssl': 1, 'ssl_verify': 2, 'ssl_ciphers': '', 'enable': 1, 'required': 0, 'optional': 0, 'retention': 0, 'send_group': 0, 'priority': 0}]***

  - [READ THIS FOR MORE INFORMATION](https://sabnzbd.org/wiki/configuration/4.2/servers)

  - Open port 8070 in your vps to access full web interface from any device. Use it like http://ip:8070/sabnzbd/. username: mltb, password: mltbmltb

**10. RSS**

- `RSS_DELAY` (`Int`): Time in seconds for rss refresh interval. Recommended `600` second at least. Default is `600` in sec.

- `RSS_SIZE_LIMIT` (`INT`): Item size limit in bytes. Default is `0`.

- `RSS_CHAT` (`Int`|`Str`): Chat `ID or USERNAME or ID|TOPIC_ID or USERNAME|TOPIC_ID` where rss links will be sent. If you want message to be sent to the channel then add channel id. Add `-100` before channel id.
    - **RSS NOTES**: `RSS_CHAT` is required, otherwise monitor will not work. You must use `USER_STRING_SESSION` --OR-- *CHANNEL*. If using channel then bot should be added in both channel and group(linked to channel) and `RSS_CHAT` is the channel id, so messages sent by the bot to channel will be forwarded to group. Otherwise with `USER_STRING_SESSION` add group id for `RSS_CHAT`. If `DATABASE_URL` not added you will miss the feeds while bot offline.

**11. Queue System**

- `QUEUE_ALL` (`Int`): Number of parallel tasks of downloads and uploads. For example if 20 task added and `QUEUE_ALL` is `8`, then the summation of uploading and downloading tasks are 8 and the rest in queue. **NOTE**: if you want to fill `QUEUE_DOWNLOAD` or `QUEUE_UPLOAD`, then `QUEUE_ALL` value must be greater than or equal to the greatest one and less than or equal to summation of `QUEUE_UPLOAD` and `QUEUE_DOWNLOAD`.

- `QUEUE_DOWNLOAD` (`Int`): Number of all parallel downloading tasks.

- `QUEUE_UPLOAD` (`Int`): Number of all parallel uploading tasks.

**12. Torrent Search**

- `SEARCH_API_LINK` (`Str`): Search api app link. Get your api from deploying this [repository](https://github.com/Ryuk-me/Torrent-Api-py).
    - Supported Sites:
  > 1337x, Piratebay, Nyaasi, Torlock, Torrent Galaxy, Zooqle, Kickass, Bitsearch, MagnetDL, Libgen, YTS, Limetorrent,
  TorrentFunk, Glodls, TorrentProject and YourBittorrent

- `SEARCH_LIMIT` (`Int`): Search limit for search api, limit for each site and not overall result limit. Default is zero (Default api limit for each site).

- `SEARCH_PLUGINS` (`List`): List of qBittorrent search plugins (github raw links). I have added some plugins, you can remove/add plugins as you want. Main Source: [qBittorrent Search Plugins (Official/Unofficial)](https://github.com/qbittorrent/search-plugins).

**13. NZB Search**

- `HYDRA_IP` (`Str`): IP address of [nzbhydra2](https://github.com/theotherp/nzbhydra2).

- `HYDRA_API_KEY` (`Str`): API key from [nzbhydra2](https://github.com/theotherp/nzbhydra2).

------

</details>
</details>

<details>
  <summary><h2>Build And Run</h2></summary>

Make sure you still mount the repo folder and installed the docker from official documentation.

- There are two methods to build and run the docker:
    1. Using official docker commands.
    2. Using docker compose plugin. (Recommended)

------

<details>
  <summary><h3>Using Official Docker Commands</h3></summary>

- Build Docker image:

```
sudo docker build . -t mltb
```

- Run the image:

```
sudo docker run --network host mltb
```

- To stop the running image:

```
sudo docker ps
```

```
sudo docker stop id
```

----

</details>

<details>
  <summary><h3>Using Docker Compose Plugin</h3></summary>

- Install docker compose plugin

```
sudo apt install docker-compose-plugin
```

- Build and run Docker image:

```
sudo docker compose up
```

- After editing files with nano, for example (nano start.sh) or git pull you must use --build to edit container files:

```
sudo docker compose up --build
```

- To stop the running container:

```
sudo docker compose stop
```

- To run the container:

```
sudo docker compose start
```

- To get log from already running container (after mounting the folder):

```
sudo docker compose logs --follow
```

------

</details>

**IMPORTANT NOTES**:
1. Flush your machine iptables to use your opened ports with docker from the host network. 

```
# Flush All Rules (Reset iptables)
sudo iptables -F
sudo iptables -X
sudo iptables -t nat -F
sudo iptables -t nat -X
sudo iptables -t mangle -F
sudo iptables -t mangle -X

sudo ip6tables -F
sudo ip6tables -X
sudo ip6tables -t nat -F
sudo ip6tables -t nat -X
sudo ip6tables -t mangle -F
sudo ip6tables -t mangle -X

# Set Default Policies
sudo iptables -P INPUT ACCEPT
sudo iptables -P FORWARD ACCEPT
sudo iptables -P OUTPUT ACCEPT

sudo ip6tables -P INPUT ACCEPT
sudo ip6tables -P FORWARD ACCEPT
sudo ip6tables -P OUTPUT ACCEPT

# save
sudo iptables-save | sudo tee /etc/iptables/rules.v4
sudo ip6tables-save | sudo tee /etc/iptables/rules.v6
```

2. Set `BASE_URL_PORT` and `RCLONE_SERVE_PORT` variables to any port you want to use. Default is `80` and `8080`
   respectively.

3. Check the number of processing units of your machine with `nproc` cmd and times it by 4, then
   edit `AsyncIOThreadsCount` in qBittorrent.conf or while bot working from bsetting->qbittorrent settings.

------

</details>
</details>

<details>
  <summary><h1>Extras</h1></summary>

<details>
  <summary><h5>Bot commands to be set in <a href="https://t.me/BotFather">@BotFather</a></h5></summary>

```
mirror - or /m Mirror
qbmirror - or /qm Mirror torrent using qBittorrent
jdmirror - or /jm Mirror using jdownloader
nzbmirror - or /nm Mirror using sabnzbd
ytdl - or /y Mirror yt-dlp supported links
leech - or /l Upload to telegram
qbleech - or /ql Leech torrent using qBittorrent
jdleech - or /jl Leech using jdownloader
nzbleech - or /nl Leech using sabnzbd
ytdlleech - or /yl Leech yt-dlp supported links
clone - Copy file/folder to Drive
count - Count file/folder from GDrive
usetting - or /us User settings
bsetting - or /bs Bot settings
status - Get Mirror Status message
sel - Select files from torrent
rss - Rss menu
list - Search files in Drive
search - Search for torrents with API
cancel - or /c Cancel a task
cancelall - Cancel all tasks
forcestart - or /fs to start task from queue
del - Delete file/folder from GDrive
log - Get the Bot Log
auth - Authorize user or chat
unauth - Unauthorize uer or chat
shell - Run commands in Shell
aexec - Execute async function
exec - Execute sync function
restart - Restart the Bot
restartses - Restart Telegram Session(s)
stats - Bot Usage Stats
ping - Ping the Bot
help - All cmds with description
```

------

</details>

<details>
  <summary><h5>Getting Google OAuth API credential file and token.pickle</h5></summary>

**NOTES**

- Old authentication changed, now we can't use bot or replit to generate token.pickle. You need OS with a local browser.
  For example `Termux`.
- Windows users should install python3 and pip. You can find how to install and use them from google or from
  this [telegraph](https://telegra.ph/Create-Telegram-Mirror-Leech-Bot-by-Deploying-App-with-Heroku-Branch-using-Github-Workflow-12-06)
  from [Wiszky](https://github.com/vishnoe115) tutorial.
- You can ONLY open the generated link from `generate_drive_token.py` in a local browser.

1. Visit the [Google Cloud Console](https://console.developers.google.com/apis/credentials)
2. Go to the OAuth Consent tab, fill it, and save.
3. Go to the Credentials tab and click Create Credentials -> OAuth Client ID
4. Choose Desktop and Create.
5. Publish your OAuth consent screen App to prevent **token.pickle** from expiring.
6. Use the download button to download your credentials.
7. Move that file to the root of mirrorbot, and rename it to **credentials.json**
8. Visit [Google API page](https://console.developers.google.com/apis/library)
9. Search for Google Drive API and enable it
10. Finally, run the script to generate **token.pickle** file for Google Drive:

```
pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib
python3 generate_drive_token.py
```

------

</details>

<details>
  <summary><h5>Generating rclone.conf</h5></summary>

1. Install rclone from [Official Site](https://rclone.org/install/)
2. Create new remote(s) using `rclone config` command.
3. Copy rclone.conf from your system’s config directory into the repo root. For example:

------

</details>

<details>
  <summary><h5>Upload</h5></summary>

- `RCLONE_PATH` is like `GDRIVE_ID` a default path for mirror. In additional to those variables `DEFAULT_UPLOAD` to
  choose the default tool whether it's rclone or google-api-python-client.
- If `DEFAULT_UPLOAD` = 'rc' then you must fill `RCLONE_PATH` with path as default one or with `rcl` to select
  destination path on each new task.
- If `DEFAULT_UPLOAD` = 'gd' then you must fill `GDRIVE_ID` with folder/TD id.
- rclone.conf can be added before deploy like token.pickle to repo folder root or use bsetting to upload it as private
  file.
- If rclone.conf uploaded from usetting or added in `rclone/{user_id}.conf` then `RCLONE_PATH` must start with `mrcc:`.
- Whenever you want to write path manually to use user rclone.conf that added from usetting then you must add
  the `mrcc:` at the beginning.
- So in short, up: has 4 possible values which are: `gd` (Upload to GDRIVE_ID), `rc` (Upload to RCLONE_PATH), `rcl` (Select Rclone Path) and `rclone_path` (remote:path (owner rclone.conf) or `mrcc`:remote:path (user rclone.conf))

------

</details>

<details>
  <summary><h5>UPSTREAM REPO (Recommended)</h5></summary>

- `UPSTREAM_REPO` variable can be used for edit/add any file in repository.
- You can add private/public repository link to grab/overwrite all files from it.
- You can skip adding the private files like token.pickle or accounts folder before deploying, simply
  fill `UPSTREAM_REPO` private one incase you want to grab all files including private files.
- If you added private files while deploying and you have added private `UPSTREAM_REPO` and your private files in this
  private repository, so your private files will be overwritten from this repository. Also if you are using database for
  private files, then all files from database will override the private files that added before deploying or from
  private `UPSTREAM_REPO`.
- If you filled `UPSTREAM_REPO` with the official repository link, then be careful in case any change in
  requirements.txt your bot will not start after restart. In this case you need to deploy again with updated code to
  install the new requirements or simply by changing the `UPSTREAM_REPO` to you fork link with that old updates.
- In case you you filled `UPSTREAM_REPO` with your fork link be careful also if you fetched the commits from the
  official repository.
- The changes in your `UPSTREAM_REPO` will take affect only after restart.

------

</details>

<details>
  <summary><h5>Bittorrent Seed</h5></summary>

- Using `-d` argument alone will lead to use global options for aria2c or qbittorrent.

<details>
  <summary><h3>QBittorrent</h3></summary>

- Global options: `GlobalMaxRatio` and `GlobalMaxSeedingMinutes` in qbittorrent.conf, `-1` means no limit, but you can
  cancel manually.
    - **NOTE**: Don't change `MaxRatioAction`.

</details>

<details>
  <summary><h3>Aria2c</h3></summary>

- Global options: `--seed-ratio` (0 means no limit) and `--seed-time` (0 means no seed) in aria.sh.

------

</details>
</details>

<details>
  <summary><h5>Using Service Accounts for uploading to avoid user rate limit</h5></summary>

> For Service Account to work, you must set `USE_SERVICE_ACCOUNTS` = "True" in config file or environment variables.
> **NOTE**: Using Service Accounts is only recommended while uploading to a Team Drive.

<details>
  <summary><h3>1. Generate Service Accounts. <a href="https://cloud.google.com/iam/docs/service-accounts">What is Service Account?</a></h3></summary>
Let us create only the Service Accounts that we need.

**Warning**: Abuse of this feature is not the aim of this project and we do **NOT** recommend that you make a lot of
projects, just one project and 100 SAs allow you plenty of use, its also possible that over abuse might get your
projects banned by Google.

> **NOTE**: If you have created SAs in past from this script, you can also just re download the keys by running:

```
python3 gen_sa_accounts.py --download-keys $PROJECTID
```

> **NOTE:** 1 Service Account can upload/copy around 750 GB a day, 1 project can make 100 Service Accounts so you can
> upload 75 TB a day.

> **NOTE:** All people can copy `2TB/DAY` from each file creator (uploader account), so if you got
> error `userRateLimitExceeded` that doesn't mean your limit exceeded but file creator limit have been exceeded which
> is `2TB/DAY`.

#### Two methods to create service accounts

Choose one of these methods

<details>
  <summary><h5>1. Create Service Accounts in existed Project (Recommended Method)</h5></summary>

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

</details>

<details>
  <summary><h5>2. Create Service Accounts in New Project</h5></summary>

```
python3 gen_sa_accounts.py --quick-setup 1 --new-only
```

A folder named accounts will be created which will contain keys for the Service Accounts.

</details>
</details>

<details>
  <summary><h3>2. Add Service Accounts</h3></summary>

#### Two methods to add service accounts

Choose one of these methods

<details>
  <summary><h5>1. Add Them To Google Group then to Team Drive (Recommended)</h5></summary>

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

- Unmount accounts folder

```
cd ..
```

Then add emails from emails.txt to Google Group, after that add this Google Group to your Shared Drive and promote it to
manager and delete email.txt file from accounts folder

</details>

<details>
  <summary><h5>2. Add Them To Team Drive Directly</h5></summary>

- Run:

```
python3 add_to_team_drive.py -d SharedTeamDriveSrcID
```

------

</details>
</details>
</details>

<details>
  <summary><h5>Create Database</h5></summary>

1. Go to `https://mongodb.com/` and sign-up.
2. Create Shared Cluster.
3. Press on `Database` under `Deployment` Header, your created cluster will be there.
5. Press on connect, choose `Allow Access From Anywhere` and press on `Add IP Address` without editing the ip, then
   create user.
6. After creating user press on `Choose a connection`, then press on `Connect your application`. Choose `Driver` *
   *python** and `version` **3.12 or later**.
7. Copy your `connection string` and replace `<password>` with the password of your user, then press close.

------

</details>

<details>
  <summary><h5>Multi Drive List</h5></summary>

To use list from multi TD/folder. Run driveid.py in your terminal and follow it. It will generate **list_drives.txt**
file or u can simply create `list_drives.txt` file in working directory and fill it, check below format:

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

</details>

<details>
  <summary><h5>Yt-dlp and Aria2c Authentication Using .netrc File</h5></summary>

For using your premium accounts in yt-dlp or for protected Index Links, create .netrc file according to following
format:

**Note**: Create .netrc and not netrc, this file will be hidden, so view hidden files to edit it after creation.

Format:

```
machine host login username password my_password
```

Using Aria2c you can also use built in feature from bot with or without username. Here example for index link without
username.

```
machine example.workers.dev password index_password
```
Where host is the name of extractor (eg. instagram, Twitch). Multiple accounts of different hosts can be added each
separated by a new line.

**Yt-dlp**: 
Authentication using [cookies.txt](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies) file. CREATE IT IN INCOGNITO TAB.


-----

</details>
</details>


# All Thanks To Our Contributors

<a href="https://github.com/anasty17/mirror-leech-telegram-bot/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=anasty17/mirror-leech-telegram-bot" />
</a>

# Donations

<p> If you feel like showing your appreciation for this project, then how about buying me a coffee.</p>

[!["Buy Me A Coffee"](https://storage.ko-fi.com/cdn/kofi2.png)](https://ko-fi.com/anasty17)

Binance ID:

```
52187862
```

USDT Address:

```
TEzjjfkxLKQqndpsdpkA7jgiX7QQCL5p4f
```

Network:

```
TRC20
```
TRX Address:

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

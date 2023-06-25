#!/usr/bin/env python3

YT_HELP_MESSAGE = """
<b>Send link along with command line</b>:
<code>/cmd</code> link -s -n new name -opt x:y|x1:y1

<b>By replying to link</b>:
<code>/cmd</code> -n  new name -z password -opt x:y|x1:y1

<b>New Name</b>: -n
<code>/cmd</code> link -n new name
Note: Don't add file extension

<b>Quality Buttons</b>: -s
Incase default quality added from yt-dlp options using format option and you need to select quality for specific link or links with multi links feature.
<code>/cmd</code> link -s

<b>Zip</b>: -z password
<code>/cmd</code> link -z (zip)
<code>/cmd</code> link -z password (zip password protected)

<b>Options</b>: -opt
<code>/cmd</code> link -opt playliststart:^10|fragment_retries:^inf|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{"ffmpeg": ["-threads", "4"]}|wait_for_video:(5, 100)
Note: Add `^` before integer or float, some values must be numeric and some string.
Like playlist_items:10 works with string, so no need to add `^` before the number but playlistend works only with integer so you must add `^` before the number like example above.
You can add tuple and dict also. Use double quotes inside dict.

<b>Multi links only by replying to first link</b>: -i
<code>/cmd</code> -i 10(number of links)

<b>Multi links within same upload directory only by replying to first link</b>: -m
<code>/cmd</code> -i 10(number of links) -m folder name

<b>Upload</b>: -up
<code>/cmd</code> link -up <code>rcl</code> (To select rclone config, remote & path or Tg id/username)
You can directly add the upload path: -up remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link -up <code>mrcc:</code>main:dump
DEFAULT_UPLOAD doesn't effect on leech cmds.
<code>/yl</code> link -up chat_id or username

<b>Rclone Flags</b>: -rcf
<code>/cmd</code> link -up path|rcl -rcf --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>Bulk Download</b>: -b
Bulk can be used by text message and by replying to text file contains links seperated by new line.
You can use it only by reply to message(text/file).
All options should be along with link!
Example:
link1 -n new name -up remote1:path1 -rcf |key:value|key:value
link2 -z -n new name -up remote2:path2
link3 -e -n new name -opt ytdlpoptions
Note: You can't add -m arg for some links only, do it for all links or use multi without bulk!
link pswd: pass(zip/unzip) opt: ytdlpoptions up: remote2:path2
Reply to this example by this cmd <code>/cmd</code> b(bulk)
You can set start and end of the links from the bulk with -b start:end or only end by -b :end or only start by -b start. The default start is from zero(first link) to inf.


Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official_channel/177'>script</a> to convert cli arguments to api options.
"""

MIRROR_HELP_MESSAGE = """
<code>/cmd</code> link -n new name

<b>By replying to link/file</b>:
<code>/cmd</code> -n new name -z -e -up upload destination

<b>New Name</b>: -n
<code>/cmd</code> link -n new name
Note: Doesn't work with torrents.

<b>Direct link authorization</b>: -au -ap
<code>/cmd</code> link -au username -ap password

<b>Extract/Zip</b>: -e -z
<code>/cmd</code> link -e password (extract password protected)
<code>/cmd</code> link -z password (zip password protected)
<code>/cmd</code> link -z password -e (extract and zip password protected)
<code>/cmd</code> link -e password -z password (extract password protected and zip password protected)
Note: When both extract and zip added with cmd it will extract first and then zip, so always extract first

<b>Bittorrent selection</b>: -s
<code>/cmd</code> link -s or by replying to file/link

<b>Bittorrent seed</b>: -d
<code>/cmd</code> link -d ratio:seed_time or by replying to file/link
To specify ratio and seed time add -d ratio:time. Ex: -d 0.7:10 (ratio and time) or -d 0.7 (only ratio) or -d :10 (only time) where time in minutes.

<b>Multi links only by replying to first link/file</b>: -i
<code>/cmd</code> -i 10(number of links/files)

<b>Multi links within same upload directory only by replying to first link/file</b>: -m
<code>/cmd</code> -i 10(number of links/files) -m folder name (multi message)
<code>/cmd</code> -b -m folder name (bulk-message/file)

<b>Upload</b>: -up
<code>/cmd</code> link -up <code>rcl</code> (To select rclone config, remote & path or Tg id/username)
You can directly add the upload path: -up remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link -up <code>mrcc:</code>main:dump
DEFAULT_UPLOAD doesn't effect on leech cmds.
<code>/leech</code> link -up chat_id or username

<b>Rclone Flags</b>: -rcf
<code>/cmd</code> link|path|rcl -up path|rcl -rcf --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>Bulk Download</b>: -b
Bulk can be used by text message and by replying to text file contains links seperated by new line.
You can use it only by reply to message(text/file).
All options should be along with link!
Example:
link1 -n new name -up remote1:path1 -rcf |key:value|key:value
link2 -z -n new name -up remote2:path2
link3 -e -n new name -up remote2:path2
Note: You can't add -m arg for some links only, do it for all links or use multi without bulk!
Reply to this example by this cmd <code>/cmd</code> -b(bulk)
You can set start and end of the links from the bulk like seed, with -b start:end or only end by -b :end or only start by -b start. The default start is from zero(first link) to inf.

<b>Join Splitted Files</b>: -j
This option will only work before extract and zip, so mostly it will be used with -m argument (samedir)
By Reply:
<code>/cmd</code> -i 3 -j -m folder name
<code>/cmd</code> -b -j -m folder name
if u have link have splitted files:
<code>/cmd</code> link -j

<b>Rclone Download</b>:
Treat rclone paths exactly like links
<code>/cmd</code> main:dump/ubuntu.iso or <code>rcl</code>(To select config, remote and path)
Users can add their own rclone from user settings
If you want to add path manually from your config add <code>mrcc:</code> before the path without space
<code>/cmd</code> <code>mrcc:</code>main:dump/ubuntu.iso

<b>TG Links</b>:
Treat links like any direct link
Some links need user access so sure you must add USER_SESSION_STRING for it.
Three types of links:
Public: <code>https://t.me/channel_name/message_id</code>
Private: <code>tg://openmessage?user_id=xxxxxx&message_id=xxxxx</code>
Super: <code>https://t.me/c/channel_id/message_id</code>

<b>NOTES:</b>
1. Commands that start with <b>qb</b> are ONLY for torrents.
"""

RSS_HELP_MESSAGE = """
Use this format to add feed url:
Title1 link (required)
Title2 link -c cmd -inf xx -exf xx
Title3 link -c cmd -d ratio:time -z password

-c command + any arg
-inf For included words filter.
-exf For excluded words filter.

Example: Title https://www.rss-url.com inf: 1080 or 720 or 144p|mkv or mp4|hevc exf: flv or web|xxx opt: up: mrcc:remote:path/subdir rcf: --buffer-size:8M|key|key:value
This filter will parse links that it's titles contains `(1080 or 720 or 144p) and (mkv or mp4) and hevc` and doesn't conyain (flv or web) and xxx` words. You can add whatever you want.

Another example: inf:  1080  or 720p|.web. or .webrip.|hvec or x264. This will parse titles that contains ( 1080  or 720p) and (.web. or .webrip.) and (hvec or x264). I have added space before and after 1080 to avoid wrong matching. If this `10805695` number in title it will match 1080 if added 1080 without spaces after it.

Filter Notes:
1. | means and.
2. Add `or` between similar keys, you can add it between qualities or between extensions, so don't add filter like this f: 1080|mp4 or 720|web because this will parse 1080 and (mp4 or 720) and web ... not (1080 and mp4) or (720 and web)."
3. You can add `or` and `|` as much as you want."
4. Take look on title if it has static special character after or before the qualities or extensions or whatever and use them in filter to avoid wrong match.
Timeout: 60 sec.
"""

CLONE_HELP_MESSAGE = """
Send Gdrive|Gdot|Filepress|Filebee|Appdrive|Gdflix link or rclone path along with command or by replying to the link/rc_path by command.

<b>Multi links only by replying to first gdlink or rclone_path:</b>
<code>/cmd</code> -i 10(number of links/pathies)

<b>Gdrive:</b>
<code>/cmd</code> gdrivelink

<b>Rclone:</b>
<code>/cmd</code> (rcl or rclone_path) -up (rcl or rclone_path) -rcf flagkey:flagvalue|flagkey|flagkey:flagvalue

Note: If -up not specified then rclone destination will be the RCLONE_PATH from config.env
"""

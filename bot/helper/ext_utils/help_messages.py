YT_HELP_MESSAGE = """
<b>Send link along with command line</b>:<br>
/cmd link<br>
<br>
<b>By replying to link</b>:<br>
/cmd -n new name -z password -opt x:y|x1:y1<br>
<br>
<b>New Name</b>: -n<br>
/cmd link -n new name<br>
Note: Don't add file extension<br>
<br>
<b>Quality Buttons</b>: -s<br>
Incase default quality added from yt-dlp options using format option and you need to select quality for specific link or links with multi links feature.<br>
/cmd link -s<br>
<br>
<b>Zip</b>: -z password<br>
/cmd link -z (zip)<br>
/cmd link -z password (zip password protected)<br>
<br>
<b>Options</b>: -opt<br>
/cmd link -opt playliststart:^10|fragment_retries:^inf|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{"ffmpeg": ["-threads", "4"]}|wait_for_video:(5, 100)<br>
Note: Add `^` before integer or float, some values must be numeric and some string.<br>
Like playlist_items:10 works with string, so no need to add `^` before the number but playlistend works only with integer so you must add `^` before the number like example above.<br>
You can add tuple and dict also. Use double quotes inside dict.<br>
<br>
<b>Multi links only by replying to first link</b>: -i<br>
/cmd -i 10(number of links)<br>
<br>
<b>Multi links within same upload directory only by replying to first link</b>: -m<br>
/cmd -i 10(number of links/files) -m folder name (multi message)<br>
/cmd -b -m folder name (bulk-message/file)<br>
<br>
<b>Thumbnail for current task</b>: -t<br>
/cmd link -t tg-message-link(doc or photo)<br>
<br>
<b>Split size for current task</b>: -t<br>
/cmd link -sp (500mb or 2gb or 4000000000)<br>
Note: Only mb and gb are supported or write in bytes without unit!<br>
<br>
<b>Upload</b>: -up<br>
/cmd link -up rcl/gdl (To select rclone config/token.pickle, remote & path/ gdrive id or Tg id/username)<br>
You can directly add the upload path: -up remote:dir/subdir or -up (Gdrive_id) or -up id/username<br>
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.<br>
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.<br>
If you want to add path or gdrive manually from your config/token (uploaded from usetting) add mrcc: for rclone and mtp: before the path/gdrive_id without space.<br>
/cmd link -up mrcc:main:dump or -up mtp:gdrive_id or -up b:id/username(leech by bot) or -up u:id/username(leech by user)<br>
Incase you want to specify whether using token or service accounts you can add tp:link or tp:gdrive_id or sa:link or sa:gdrive_id. This for links and upload destination.<br>
DEFAULT_UPLOAD doesn't effect on leech cmds.<br>
<br>
<b>Rclone Flags</b>: -rcf<br>
/cmd link -up path|rcl -rcf --buffer-size:8M|--drive-starred-only|key|key:value<br>
This will override all other flags except --exclude<br>
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.<br>
<br>
<b>Bulk Download</b>: -b<br>
Bulk can be used by text message and by replying to text file contains links seperated by new line.<br>
You can use it only by reply to message(text/file).<br>
Example:<br>
link1 -n new name -up remote1:path1 -rcf |key:value|key:value<br>
link2 -z -n new name -up remote2:path2<br>
link3 -e -n new name -up remote2:path2<br>
Reply to this example by this cmd /cmd -b(bulk) -m folder name<br>
You can set start and end of the links from the bulk like seed, with -b start:end or only end by -b :end or only start by -b start. The default start is from zero(first link) to inf.<br>
<br>
<b>Sample Video</b>: -sv<br>
Create sample video for one video or folder of vidoes.<br>
/cmd -sv (it will take the default values which 60sec sample duration and part duration is 4sec).<br>
You can control those values. Example: /cmd -sv 70:5(sample-duration:part-duration) or /cmd -sv :5 or /cmd -sv 70.<br>
<br>
<b>ScreenShots</b>: -ss<br>
Create up to 10 screenshots for one video or folder of vidoes.<br>
/cmd -ss (it will take the default values which is 10 photos).<br>
You can control this value. Example: /cmd -ss 6.<br>
<br>
Check here all supported <a href='https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md'>SITES</a><br>
Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official_channel/177'>script</a> to convert cli arguments to api options.<br>
"""

MIRROR_HELP_MESSAGE = """
<b>Send link along with command line</b>:<br>
/cmd link<br>
<br>
<b>By replying to link/file</b>:<br>
/cmd -n new name -z -e -up upload destination<br>
<br>
<b>New Name</b>: -n<br>
/cmd link -n new name<br>
Note: Doesn't work with torrents.<br>
<br>
<b>Direct link authorization</b>: -au -ap<br>
/cmd link -au username -ap password<br>
<br>
<b>Direct link custom headers</b>: -h<br>
/cmd link -h key: value key1: value1<br>
<br>
<b>Extract/Zip</b>: -e or -z<br>
/cmd link -e password (extract password protected)<br>
/cmd link -z password (zip password protected)<br>
/cmd link -z password -e (extract and zip password protected)<br>
/cmd link -e password -z password (extract password protected and zip password protected)<br>
Note: When both extract and zip added with cmd it will extract first and then zip, so always extract first<br>
<br>
<b>Bittorrent selection</b>: -s<br>
/cmd link -s or by replying to file/link<br>
<br>
<b>Bittorrent seed</b>: -d<br>
/cmd link -d ratio:seed_time or by replying to file/link<br>
To specify ratio and seed time add -d ratio:time.<br>
Example: -d 0.7:10 (ratio and time) or -d 0.7 (only ratio) or -d :10 (only time) where time in minutes.<br>
<br>
<b>Multi links only by replying to first link/file</b>: -i<br>
/cmd -i 10(number of links/files)<br>
<br>
<b>Multi links within same upload directory only by replying to first link/file</b>: -m<br>
/cmd -i 10(number of links/files) -m folder name (multi message)<br>
/cmd -b -m folder name (bulk-message/file)<br>
<br>
<b>Thumbnail for current task</b>: -t<br>
/cmd link -t tg-message-link(doc or photo)<br>
<br>
<b>Split size for current task</b>: -t<br>
/cmd link -sp (500mb or 2gb or 4000000000)<br>
Note: Only mb and gb are supported or write in bytes without unit!<br>
<br>
<b>Upload</b>: -up<br>
/cmd link -up rcl/gdl (To select rclone config/token.pickle, remote & path/ gdrive id or Tg id/username)<br>
You can directly add the upload path: -up remote:dir/subdir or -up (Gdrive_id) or -up id/username<br>
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.<br>
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.<br>
If you want to add path or gdrive manually from your config/token (uploaded from usetting) add mrcc: for rclone and mtp: before the path/gdrive_id without space.<br>
/cmd link -up mrcc:main:dump or -up mtp:gdrive_id or -up b:id/username(leech by bot) or -up u:id/username(leech by user)<br>
Incase you want to specify whether using token or service accounts you can add tp:link or tp:gdrive_id or sa:link or sa:gdrive_id. This for links and upload destination.<br>
DEFAULT_UPLOAD doesn't effect on leech cmds.<br>
<br>
<b>Rclone Flags</b>: -rcf<br>
/cmd link|path|rcl -up path|rcl -rcf --buffer-size:8M|--drive-starred-only|key|key:value<br>
This will override all other flags except --exclude<br>
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.<br>
<br>
<b>Bulk Download</b>: -b<br>
Bulk can be used by text message and by replying to text file contains links seperated by new line.<br>
You can use it only by reply to message(text/file).<br>
Example:<br>
link1 -n new name -up remote1:path1 -rcf |key:value|key:value<br>
link2 -z -n new name -up remote2:path2<br>
link3 -e -n new name -up remote2:path2<br>
Reply to this example by this cmd /cmd -b(bulk) -m folder name<br>
You can set start and end of the links from the bulk like seed, with -b start:end or only end by -b :end or only start by -b start. The default start is from zero(first link) to inf.<br>
<br>
<b>Join Splitted Files</b>: -j<br>
This option will only work before extract and zip, so mostly it will be used with -m argument (samedir)<br>
By Reply:<br>
/cmd -i 3 -j -m folder name<br>
/cmd -b -j -m folder name<br>
if u have link(folder) have splitted files:<br>
/cmd link -j<br>
<br>
<b>Rclone Download</b>:<br>
Treat rclone paths exactly like links<br>
/cmd main:dump/ubuntu.iso or rcl(To select config, remote and path)<br>
Users can add their own rclone from user settings<br>
If you want to add path manually from your config add mrcc: before the path without space<br>
/cmd mrcc:main:dump/ubuntu.iso<br>
<br>
<b>TG Links</b>:<br>
Treat links like any direct link<br>
Some links need user access so sure you must add USER_SESSION_STRING for it.<br>
Three types of links:<br>
Public: https://t.me/channel_name/message_id<br>
Private: tg://openmessage?user_id=xxxxxx&message_id=xxxxx<br>
Super: https://t.me/c/channel_id/message_id<br>
Range: https://t.me/channel_name/first_message_id-last_message_id<br>
Range Example: tg://openmessage?user_id=xxxxxx&message_id=555-560 or https://t.me/channel_name/100-150<br>
Note: Range link will work only by replying cmd to it<br>
<br>
<b>Sample Video</b>: -sv<br>
Create sample video for one video or folder of vidoes.<br>
/cmd -sv (it will take the default values which 60sec sample duration and part duration is 4sec).<br>
You can control those values. Example: /cmd -sv 70:5(sample-duration:part-duration) or /cmd -sv :5 or /cmd -sv 70.<br>
<br>
<b>ScreenShots</b>: -ss<br>
Create up to 10 screenshots for one video or folder of vidoes.<br>
/cmd -ss (it will take the default values which is 10 photos).<br>
You can control this value. Example: /cmd -ss 6.<br>
<br>
<b>NOTES:</b><br>
1. Commands that start with <b>qb</b> are ONLY for torrents.
"""

RSS_HELP_MESSAGE = """
Use this format to add feed url:
Title1 link (required)
Title2 link -c cmd -inf xx -exf xx
Title3 link -c cmd -d ratio:time -z password

-c command -up mrcc:remote:path/subdir -rcf --buffer-size:8M|key|key:value
-inf For included words filter.
-exf For excluded words filter.

Example: Title https://www.rss-url.com inf: 1080 or 720 or 144p|mkv or mp4|hevc exf: flv or web|xxx
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
Send Gdrive|Gdot|Filepress|Filebee|Appdrive|Gdflix link or rclone path along with command or by replying to the link/rc_path by command.<br>
<br>
<b>Multi links only by replying to first gdlink or rclone_path:</b> -i<br>
/cmd -i 10(number of links/paths)<br>
<br>
<b>Bulk Clone</b>: -b<br>
Bulk can be used by text message and by replying to text file contains links seperated by new line.<br>
You can use it only by reply to message(text/file).<br>
Example:<br>
link1 -up remote1:path1 -rcf |key:value|key:value<br>
link2 -up remote2:path2<br>
link3 -up remote2:path2<br>
Reply to this example by this cmd /cmd -b(bulk)<br>
You can set start and end of the links from the bulk like seed, with -b start:end or only end by -b :end or only start by -b start. The default start is from zero(first link) to inf.<br>
<br>
<b>Clone Destination</b>: -up<br>
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.<br>
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.<br>
If you want to add path or gdrive manually from your config/token (uploaded from usetting) add mrcc: for rclone and mtp: before the path/gdrive_id without space.<br>
Incase you want to specify whether using token or service accounts you can add tp:link or tp:gdrive_id or sa:link or sa:gdrive_id. This for links and upload destination.<br>
<br>
<b>Gdrive:</b><br>
/cmd gdrivelink/gdl/gdrive_id -up gdl/gdrive_id/gd<br>
<br>
<b>Rclone:</b><br>
/cmd rcl/rclone_path -up rcl/rclone_path/rc -rcf flagkey:flagvalue|flagkey|flagkey:flagvalue<br>
"""

PASSWORD_ERROR_MESSAGE = """
<b>This link requires a password!</b>
- Insert <b>::</b> after the link and write the password after the sign.

<b>Example:</b> link::my password
"""

#!/usr/bin/env python3

YT_HELP_MESSAGE = """
<b>SEND LINK ALONG WITH COMMAND LINE</b>
<code>/cmd</code> s link n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>BY REPLYING TO LINK</b>
<code>/cmd</code> n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>MULTI LINKS ONLY BY REPLYING TO FIRST LINK</b>
<code>/cmd</code> 10 (number of links)
Number should be always before n:, pswd: and opt:

<b>MULTI LINKS WITHIN SAME UPLOAD DIRECTORY ONLY BY REPLYING TO FIRST LINK</b>
<code>/cmd</code> 10 (number of links) m:folder_name
Number and m:folder_name should be always before n:, pswd: and opt:

<b>QUALITY BUTTONS</b>
Incase default quality added but you need to select quality for specific link or links with multi links feature.
<code>/cmd</code> s link
This option should be always before n:, pswd: and opt:

<b>"opt: " Note:</b>
Add "^" before integer or float, some values must be numeric and some string.
Like playlist_items:10 works with string, so no need to add "^" before the number but playlistend works only with integer so you must add "^" before the number like example above.
You can add tuple and dict also. Use double quotes inside dict.

<b>"opt: " Example:</b>
opt: playliststart:^10|fragment_retries:^inf|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{"ffmpeg": ["-threads", "4"]}|wait_for_video:(5, 100)

<b>UPLOAD</b>
<code>/cmd</code> link up: <code>rcl</code> (to select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is "rc" then you can pass up: "gd" to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is "gd" then you can pass up: "rc" to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space.
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>RCLONE FLAGS</b>
<code>/cmd</code> link up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>FLAGS</a>.

<b>NOTES</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>s, m: and multi</b>) should be added randomly before link and before any other option.
3. Options (<b>n:, pswd: and opt</b>) should be added randomly after the link if link along with the cmd or after cmd if by reply.
4. You can always add video quality from yt-dlp api options.
5. Don't add file extension while rename using "n: ".

Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>LINK</a>.
"""


MIRROR_HELP_MESSAGE = """
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)

<b>BY REPLYING TO LINK/FILE</b>
<code>/cmd</code> n: newname pswd: xx(zip/unzip)

<b>DIRECT LINK AUTHORIZATION</b>
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)
<b>username</b>
<b>password</b>

<b>BITTORRENT SELECTION</b>
<code>/cmd</code> <b>s</b> link or by replying to file/link
This option should be always before n: or pswd:

<b>BITTORRENT SEED</b>
<code>/cmd</code> <b>d</b> link or by replying to file/link
To specify ratio and seed time add d:ratio:time. Ex: d:0.7:10 (ratio and time) or d:0.7 (only ratio) or d::10 (only time) where time in minutes.
Those options should be always before n: or pswd:

<b>MULTI LINKS ONLY BY REPLYING TO FIRST LINK/FILE</b>
<code>/cmd</code> 10 (number of links/files)
Number should be always before n: or pswd:

<b>MULTI LINKS WITHIN SAME UPLOAD DIRECTORY ONLY BY REPLYING TO FIRST LINK/FILE</b>
<code>/cmd</code> 10 (number of links/files) m:folder_name (folder_name without space). Should be always before n: or pswd:

<b>RCLONE DOWNLOAD</b>
Treat rclone paths exactly like links.
<code>/cmd</code> main:dump/ubuntu.iso or <code>rcl</code> (to select config, remote and path)
Users can add their own rclone from user settings. If you want to add path manually from your config add <code>mrcc:</code> before the path without space.
<code>/cmd</code> <code>mrcc:</code>main:/dump/ubuntu.iso

<b>TELEGRAM LINK</b>
Treat links like any direct link. Some links need user access so sure you must add USER_SESSION_STRING for it.
<b>Type of Link</b>
Public: <code>https://t.me/channel_name/message_id</code>
Private: <code>tg://openmessage?user_id=xxxxxx&message_id=xxxxx</code>
Super: <code>https://t.me/c/channel_id/message_id</code>

<b>UPLOAD</b>
<code>/cmd</code> link up: <code>rcl</code> (to select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is "rc" then you can pass up: "gd" to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is "gd" then you can pass up: "rc" to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space.
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>RCLONE FLAGS</b>
<code>/cmd</code> link|path|rcl up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>FLAGS</a>.

<b>NOTES</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>n: and pswd</b>) should be added randomly after the link if link along with the cmd and after any other option.
3. Options (<b>d, s, m: and multi</b>) should be added randomly before the link and before any other option.
4. Commands that start with <b>qb</b> are ONLY for torrents.
5. (n:) option doesn't work with torrents.
"""


RSS_HELP_MESSAGE = """
<b>USE THIS FORMAT TO ADD FEED URL</b>
Title1 link (required)
Title2 link c: cmd inf: xx exf: xx opt: options like(up, rcf, pswd) (optional)
Title3 link c: cmd d:ratio:time opt: up: gd

c: command + any mirror option before link like seed option.
opt: any option after link like up, rcf and pswd(zip).
inf: For included words filter.
exf: For excluded words filter.

<b>Example:</b>
Title https://www.rss-url.com inf: 1080 or 720 or 144p|mkv or mp4|hevc exf: flv or web|xxx opt: up: mrcc:remote:path/subdir rcf: --buffer-size:8M|key|key:value
This filter will parse links that it's titles contains "(1080 or 720 or 144p) and (mkv or mp4) and hevc" and doesn't conyain (flv or web) and xxx" words. You can add whatever you want.

<b>Another Example:</b>
inf:  1080  or 720p|.web. or .webrip.|hvec or x264. This will parse titles that contains ( 1080  or 720p) and (.web. or .webrip.) and (hvec or x264). I have added space before and after 1080 to avoid wrong matching. If this "10805695" number in title it will match 1080 if added 1080 without spaces after it.

<b>FILTER NOTES</b>
1. | means and.
2. Add "or" between similar keys, you can add it between qualities or between extensions, so don't add filter like this f: 1080|mp4 or 720|web because this will parse 1080 and (mp4 or 720) and web ... not (1080 and mp4) or (720 and web).
3. You can add "or" and "|" as much as you want.
4. Take look on title if it has static special character after or before the qualities or extensions or whatever and use them in filter to avoid wrong match.
Timeout: 60 sec.
"""

CLONE_HELP_MESSAGE = """
<b>SEND GDRIVE, GDTOT, FILEBEE, APPDRIVE, GDFLIX LINK</b>
<b>Example</b> <code>/cmd</code> link

<b>MULTI LINKS ONLY BY REPLYING TO FIRST GDLINK</b>
<code>/cmd</code> 10 (number of links)

<b>RCLONE</b>
<code>/cmd</code> rcl or rclone_path up: rcl or rclone_path rcf: flagkey:flagvalue|flagkey|flagkey:flagvalue
<b>Notes</b> if up: not specified then rclone destination will be the RCLONE_PATH from config.env
"""
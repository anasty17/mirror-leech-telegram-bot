#!/usr/bin/env python3

YT_HELP_MESSAGE = """
<b>Send link along with command line:</b>
<code>/cmd</code> s link n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>By replying to link:</b>
<code>/cmd</code> n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>Quality Buttons:</b>
Incase default quality added but you need to select quality for specific link or links with multi links feature.
<code>/cmd</code> s link
This option should be always before n:, pswd: and opt:

<b>Options Example:</b> opt: playliststart:^10|fragment_retries:^inf|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{"ffmpeg": ["-threads", "4"]}|wait_for_video:(5, 100)

<b>Multi links only by replying to first link:</b>
<code>/cmd</code> 10(number of links)
Number should be always before n:, pswd: and opt:

<b>Multi links within same upload directory only by replying to first link:</b>
<code>/cmd</code> 10(number of links) m:folder_name
Number and m:folder_name should be always before n:, pswd: and opt:

<b>Options Note:</b> Add `^` before integer or float, some values must be numeric and some string.
Like playlist_items:10 works with string, so no need to add `^` before the number but playlistend works only with integer so you must add `^` before the number like example above.
You can add tuple and dict also. Use double quotes inside dict.

<b>Upload</b>:
<code>/cmd</code> link up: <code>rcl</code> (To select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>Rclone Flags</b>:
<code>/cmd</code> link up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>NOTES:</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>s, m: and multi</b>) should be added randomly before link and before any other option.
3. Options (<b>n:, pswd: and opt:</b>) should be added randomly after the link if link along with the cmd or after cmd if by reply.
4. You can always add video quality from yt-dlp api options.
5. Don't add file extension while rename using `n:`

Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official/177'>script</a> to convert cli arguments to api options.
"""

MIRROR_HELP_MESSAGE = """
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)

<b>By replying to link/file:</b>
<code>/cmd</code> n: newname pswd: xx(zip/unzip)

<b>Direct link authorization:</b>
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)
<b>username</b>
<b>password</b>

<b>Bittorrent selection:</b>
<code>/cmd</code> <b>s</b> link or by replying to file/link
This option should be always before n: or pswd:

<b>Bittorrent seed</b>:
<code>/cmd</code> <b>d</b> link or by replying to file/link
To specify ratio and seed time add d:ratio:time. Ex: d:0.7:10 (ratio and time) or d:0.7 (only ratio) or d::10 (only time) where time in minutes.
Those options should be always before n: or pswd:

<b>Multi links only by replying to first link/file:</b>
<code>/cmd</code> 10(number of links/files)
Number should be always before n: or pswd:

<b>Multi links within same upload directory only by replying to first link/file:</b>
<code>/cmd</code> 10(number of links/files) m:folder_name
Number and m:folder_name (folder_name without space) should be always before n: or pswd:

<b>Rclone Download</b>:
Treat rclone paths exactly like links
<code>/cmd</code> main:dump/ubuntu.iso or <code>rcl</code> (To select config, remote and path)
Users can add their own rclone from user settings
If you want to add path manually from your config add <code>mrcc:</code> before the path without space
<code>/cmd</code> <code>mrcc:</code>main:/dump/ubuntu.iso

<b>Upload</b>:
<code>/cmd</code> link up: <code>rcl</code> (To select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>Rclone Flags</b>:
<code>/cmd</code> link|path|rcl up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>NOTES:</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>n: and pswd:</b>) should be added randomly after the link if link along with the cmd and after any other option
3. Options (<b>d, s, m: and multi</b>) should be added randomly before the link and before any other option.
4. Commands that start with <b>qb</b> are ONLY for torrents.
5. (n:) option doesn't work with torrents.
"""


RSS_HELP_MESSAGE = """
Use this format to add feed url:
Title1 link (required)
Title2 link c: cmd inf: xx exf: xx opt: options like(up, rcf, pswd) (optional)
Title3 link c: cmd d:ratio:time opt: up: gd

c: command + any mirror option before link like seed option.
opt: any option after link like up, rcf and pswd(zip).
inf: For included words filter.
exf: For excluded words filter.

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

CLONE_HELP_MESSAGE = """Send Gdrive|Gdot|Filepress|Filebee|Appdrive|Gdflix link or rclone path along with command or by replying to the link/rc_path by command
<b>Multi links only by replying to first gdlink or rclone_path:</b>
<code>/cmd</code> 10(number of links/pathies)
<b>Gdrive:</b>
<code>/cmd</code> gdrivelink
<b>Rclone:</b>
<code>/cmd</code> rcl or rclone_path up: rcl or rclone_path rcf: flagkey:flagvalue|flagkey|flagkey:flagvalue
Notes:
if up: not specified then rclone destination will be the RCLONE_PATH from config.env
"""
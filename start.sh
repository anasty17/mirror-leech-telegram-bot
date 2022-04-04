wget -q https://github.com/dogbutcat/gclone/releases/download/v1.57.0-mod1.4.0/gclone-v1.57.0-mod1.4.0-linux-amd64.zip
unzip -q gclone-v1.57.0-mod1.4.0-linux-amd64.zip
export PATH=$PWD/gclone-v1.57.0-mod1.4.0-linux-amd64:$PATH

if [[ -n $RCLONE_CONFIG_URL ]]; then
	echo "Rclone config detected"
	mkdir -p /usr/src/app/.config/rclone
	wget $RCLONE_CONFIG_URL -O /usr/src/app/.config/rclone/rclone.conf
fi

sed -i "47s/.*/WebUI\\\Port=${PORT}/" /user/src/app/qBittorrent/config/qBittorrent.conf

python3 update.py && python3 -m bot

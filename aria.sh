if [ -z $TORRENT_TIMEOUT ]
then
   TORRENT_TIMEOUT=0
fi
tracker_list=$(curl -Ns https://raw.githubusercontent.com/XIU2/TrackersListCollection/master/all.txt https://ngosang.github.io/trackerslist/trackers_all_http.txt https://newtrackon.com/api/all https://raw.githubusercontent.com/hezhijie0327/Trackerslist/main/trackerslist_tracker.txt | awk '$0' | tr '\n\n' ',')
aria2c --allow-overwrite=true --auto-file-renaming=true --bt-enable-lpd=true --bt-detach-seed-only=true \
       --bt-remove-unselected-file=true --bt-stop-timeout=$TORRENT_TIMEOUT --bt-tracker="[$tracker_list]" \
       --check-certificate=false --check-integrity=true --continue=true --content-disposition-default-utf8=true \
       --daemon=true --disk-cache=40M --enable-rpc=true --follow-torrent=mem --force-save=true --http-accept-gzip=true \
       --max-connection-per-server=10 --max-concurrent-downloads=10 --max-file-not-found=0 --max-tries=20 \
       --min-split-size=10M --netrc-path=/usr/src/app/.netrc --optimize-concurrent-downloads=true \
       --peer-id-prefix=-qB4430- --peer-agent=qBittorrent/4.4.3 --quiet=true --reuse-uri=true \
       --rpc-max-request-size=1024M --seed-ratio=0 --split=10 --summary-interval=0 --user-agent=Wget/1.12

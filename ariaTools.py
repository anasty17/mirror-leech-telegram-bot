import aria2p
import os
from time import sleep
import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)



cmd = "aria2c --enable-rpc --rpc-listen-all=false --rpc-listen-port 6800  --max-connection-per-server=10 --rpc-max-request-size=1024M --seed-time=0.01 --min-split-size=10M --follow-torrent=mem --split=10 --daemon=true --allow-overwrite=true"
EDIT_SLEEP_TIME_OUT = 5
aria2_is_running = os.system(cmd)

aria2 = aria2p.API(
		aria2p.Client(
			host="http://localhost",
			port=6800,
			secret=""
		)
	)


allDls = {}

def check_metadata(gid):
	file = aria2.get_download(gid)
	if file.followed_by_ids[0] != None:
		new_gid = file.followed_by_ids[0]
		logging.info("Changing GID "+gid+" to "+new_gid)
		return new_gid	
	else:
		return False	


def add_download(link,message):
	if "magnet" in link:
		download = aria2.add_magnet(link)
		allDls[message[0]] = [download,message[1]]
		logging.info("Adding: "+link)
		return download
	else:
		download = aria2.add_uris([link])
		allDls[message[0]] = [download,message[1]]
		logging.info("Adding: "+link)
		return download


def remove_download(message):
	del allDls[message]
	aria2.remove_download(allDls[message].gid)
	return True	



def get_download_by_message(message):
	if allDls[message] == None:
		return None
	else:
		download = allDls[message]
		return download[0]



def progress_status(context,update,previous):
	download = get_download_by_message(update)
	file = aria2.get_download(download.gid)
	if not file.is_complete:
		if not file.error_message:
			msg = "<i>"+str(file.name) +"</i>:- " +str(file.progress_string())+" of "+str(file.total_length_string())+" at "+str(file.download_speed_string())+" ,ETA: "+str(file.eta_string())
			if previous != msg:
				print("editing message")
				try:
					context.bot.edit_message_text(text=msg,message_id=update.message_id,chat_id=update.chat.id,parse_mode='HTMl')
				except:
					pass
				previous = msg
			sleep(5)	
			progress_status(context,update,previous)	
		else:
			logging.error(file.error_message)
			return
	else:
		try:
			new_gid = check_metadata(file.gid)
		except:
			new_gid = None
			pass
		if new_gid:
			download = aria2.get_download(new_gid)
			allDls[update][0] = download
			progress_status(context,update,previous=None)
		else:	
			logging.info(file.name+" Completed.")
			msg = "<i>"+str(file.name) +"</i>:- Uploading."
			context.bot.edit_message_text(text=msg,message_id=update.message_id,chat_id=update.chat.id,parse_mode='HTMl')
			with open('data','w') as f:
				f.write(file.name)	

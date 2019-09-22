import aria2p
import os
from time import sleep
from bot import LOGGER,DOWNLOAD_DIR


EDIT_SLEEP_TIME_OUT = 5

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
		LOGGER.info("Changing GID "+gid+" to "+new_gid)
		return new_gid	
	else:
		return False	


def add_download(link,message):
	if "magnet" in link:
		download = aria2.add_magnet(link,{'dir':DOWNLOAD_DIR})
		allDls[message[0]] = [download,message[1]]
		LOGGER.info("Adding: "+link)
		return download
	else:
		download = aria2.add_uris([link],{'dir':DOWNLOAD_DIR})
		allDls[message[0]] = [download,message[1]]
		LOGGER.info("Adding: "+link)
		return download


def remove_download(message):
	del allDls[message]
	aria2.remove_download(allDls[message].gid)
	return True	


def get_file_name(download):
	file = aria2.get_download(download.gid)
	return file.name

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
			msg = "<i>" + file.name +"</i>:- " + file.progress_string()+" of " + file.total_length_string() + \
				" at " + file.download_speed_string() + " ,ETA: " + file.eta_string()
			if previous != msg:
				LOGGER.info("Editing message")
				try:
					context.bot.edit_message_text(text=msg,message_id=update.message_id,chat_id=update.chat.id,parse_mode='HTMl')
				except:
					pass
				previous = msg
			sleep(5)	
			return progress_status(context,update,previous)	
		else:
			LOGGER.error(file.error_message)
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
			return progress_status(context,update,previous=None)
		else:	
			LOGGER.info(file.name+" Completed.")
			msg = "<i>" + file.name +"</i>:- Uploading."
			context.bot.edit_message_text(text=msg,message_id=update.message_id,chat_id=update.chat.id,parse_mode='HTMl')

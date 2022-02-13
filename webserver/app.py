# Flask WebServer Implement By - @VarnaX-279

import os
import logging
import time
import nodes

from qbittorrentapi import Client, NotFound404Error
from flask import Flask, request, render_template, abort, redirect, url_for

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)


LOGGER = logging.getLogger(__name__)
app = Flask(__name__)
port=os.environ.get('PORT', '5000')
os.environ["FLASK_ENV"] = "mirror-leech-telegram-bot"

@app.route('/')
def home():
    return "<h1>See mirror-leech-telegram-bot <a href='https://www.github.com/anasty17/mirror-leech-telegram-bot'>@GitHub</a> By <a href='https://github.com/anasty17'>Anas</a></h1>"


def re_verfiy(paused, resumed, qbclient, torr):
    
    paused = paused.strip()
    resumed = resumed.strip()
    if paused:
        paused = paused.split("|")
    if resumed:
        resumed = resumed.split("|")
    k = 0
    while True:
        
        res = qbclient.torrents_files(torrent_hash=torr)
        verify = True
        
        for i in res:
            if str(i.id) in paused and i.priority != 0:
                verify = False
                break
            
            if str(i.id) in resumed and i.priority == 0:
                verify = False
                break
        
        if verify:
            break
        LOGGER.info("Reverification Failed: correcting stuff...")
        qbclient.auth_log_out()
        time.sleep(1)
        qbclient = Client(host="localhost", port="8090")
        try:
            qbclient.torrents_file_priority(torrent_hash=torr, file_ids=paused, priority=0)
        except:
            LOGGER.error("Errored in reverification paused")
        try:
            qbclient.torrents_file_priority(torrent_hash=torr, file_ids=resumed, priority=1)
        except:
            LOGGER.error("Errored in reverification resumed")
        k += 1
        if k > 5:
            qbclient.auth_log_out()
            return False
    qbclient.auth_log_out()
    LOGGER.info("Verified")
    return True


@app.route('/app/files/<string:hash_id>', methods=['GET','POST'])
def main(hash_id):
    torr = hash_id
    if request.method == 'GET':
        
        qbclient = Client(host="localhost", port="8090")
        try:
            res = qbclient.torrents_files(torrent_hash=torr)
        except NotFound404Error:
            abort(404)
        qbclient.auth_log_out()
        
        pincode  = request.args.get('pin_code')
        if not pincode:
            return render_template('code.html', form_url=f"/app/files/{torr}")
        
        passw = ""
        for n in str(torr):
            if n.isdigit():
                passw += str(n)
            if len(passw) == 4:
                break
        
        if pincode != passw:
            return '<h1>Wrong Pin Code</h1>'
        
        par = nodes.make_tree(res)
        cont = ["", 0]
        nodes.create_list(par, cont)
        content = cont[0]
        form_url = f"/app/files/{torr}?pin_code={pincode}"
        
        return render_template('main.html', content=content, form_url=form_url)
    
    elif request.method == 'POST':
        qbclient = Client(host="localhost", port="8090")
        data = dict(request.form)
        resume = ""
        pause = ""
        for i, value in data.items():
            if i.find("filenode") != -1:
                node_no = i.split("_")[-1]
                
                if value == "on":
                    resume += f"{node_no}|"
                else:
                    pause += f"{node_no}|"
        
        pause = pause.strip("|")
        resume = resume.strip("|")

        try:
            qbclient.torrents_file_priority(torrent_hash=torr, file_ids=pause, priority=0)
        except NotFound404Error:
            abort(404)
        except:
            LOGGER.error("Errored in paused")

        try:
            qbclient.torrents_file_priority(torrent_hash=torr, file_ids=resume, priority=1)
        except NotFound404Error:
            abort(404)
        except:
            LOGGER.error("Errored in resumed")
        
        time.sleep(2)
        if not re_verfiy(pause, resume, qbclient, torr):
            LOGGER.error("Verification Failed")

        redirect_url=f"{url_for('main', hash_id=torr)}?pin_code={request.args.get('pin_code')}"
        return redirect(redirect_url)

    else:
        return '<h1>Wrong Method</h1>'


@app.errorhandler(404)
def page_not_found(_):
    return f'404 Page not found', 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)
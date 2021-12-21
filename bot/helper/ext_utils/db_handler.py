import os
import psycopg2
from psycopg2 import Error

from bot import DB_URI, AUTHORIZED_CHATS, SUDO_USERS, AS_DOC_USERS, AS_MEDIA_USERS, rss_dict, LOGGER

class DbManger:
    def __init__(self):
        self.err = False
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(DB_URI)
            self.cur = self.conn.cursor()
        except psycopg2.DatabaseError as error:
            LOGGER.error(f"Error in DB connection: {error}")
            self.err = True

    def disconnect(self):
        self.cur.close()
        self.conn.close()

    def db_init(self):
        if self.err:
            return
        sql = """CREATE TABLE IF NOT EXISTS users (
                 uid bigint,
                 sudo boolean DEFAULT FALSE,
                 auth boolean DEFAULT FALSE,
                 media boolean DEFAULT FALSE,
                 doc boolean DEFAULT FALSE,
                 thumb bytea DEFAULT NULL
              )
              """
        self.cur.execute(sql)
        self.cur.execute("CREATE TABLE IF NOT EXISTS rss (name text, link text, last text, title text)")
        self.conn.commit()
        LOGGER.info("Database Initiated")
        self.db_load()

    def db_load(self):
        # User Data
        self.cur.execute("SELECT * from users")
        rows = self.cur.fetchall()  #returns a list ==> (uid, sudo, auth, media, doc, thumb)
        if rows:
            for row in rows:
                if row[1] and row[0] not in SUDO_USERS:
                    SUDO_USERS.add(row[0])
                elif row[2] and row[0] not in AUTHORIZED_CHATS:
                    AUTHORIZED_CHATS.add(row[0])
                if row[3]:
                    AS_MEDIA_USERS.add(row[0])
                elif row[4]:
                    AS_DOC_USERS.add(row[0])
                path = f"Thumbnails/{row[0]}.jpg"
                if row[5] is not None and not os.path.exists(path):
                    if not os.path.exists('Thumbnails'):
                        os.makedirs('Thumbnails')
                    with open(path, 'wb+') as f:
                        f.write(row[5])
                        f.close()
            LOGGER.info("Users data has been imported from Database")
        # Rss Data
        self.cur.execute("SELECT * FROM rss")
        rows = self.cur.fetchall()  #returns a list ==> (name, feed_link, last_link, last_title)
        if rows:
            for row in rows:
                rss_dict[row[0]] = [row[1], row[2], row[3]]
            LOGGER.info("Rss data has been imported from Database.")
        self.disconnect()

    def user_auth(self, chat_id: int):
        if self.err:
            return "Error in DB connection, check log for details"
        elif not self.user_check(chat_id):
            sql = 'INSERT INTO users (uid, auth) VALUES ({}, TRUE)'.format(chat_id)
        else:
            sql = 'UPDATE users SET auth = TRUE WHERE uid = {}'.format(chat_id)
        self.cur.execute(sql)
        self.conn.commit()
        self.disconnect()
        return 'Authorized successfully'

    def user_unauth(self, chat_id: int):
        if self.err:
            return "Error in DB connection, check log for details"
        elif self.user_check(chat_id):
            sql = 'UPDATE users SET auth = FALSE WHERE uid = {}'.format(chat_id)
            self.cur.execute(sql)
            self.conn.commit()
            self.disconnect()
            return 'Unauthorized successfully'

    def user_addsudo(self, user_id: int):
        if self.err:
            return "Error in DB connection, check log for details"
        elif not self.user_check(user_id):
            sql = 'INSERT INTO users (uid, sudo) VALUES ({}, TRUE)'.format(user_id)
        else:
            sql = 'UPDATE users SET sudo = TRUE WHERE uid = {}'.format(user_id)
        self.cur.execute(sql)
        self.conn.commit()
        self.disconnect()
        return 'Successfully Promoted as Sudo'

    def user_rmsudo(self, user_id: int):
        if self.err:
            return "Error in DB connection, check log for details"
        elif self.user_check(user_id):
             sql = 'UPDATE users SET sudo = FALSE WHERE uid = {}'.format(user_id)
             self.cur.execute(sql)
             self.conn.commit()
             self.disconnect()
             return 'Successfully removed from Sudo'

    def user_media(self, user_id: int):
        if self.err:
            return
        elif not self.user_check(user_id):
            sql = 'INSERT INTO users (uid, media) VALUES ({}, TRUE)'.format(user_id)
        else:
            sql = 'UPDATE users SET media = TRUE, doc = FALSE WHERE uid = {}'.format(user_id)
        self.cur.execute(sql)
        self.conn.commit()
        self.disconnect()

    def user_doc(self, user_id: int):
        if self.err:
            return
        elif not self.user_check(user_id):
            sql = 'INSERT INTO users (uid, doc) VALUES ({}, TRUE)'.format(user_id)
        else:
            sql = 'UPDATE users SET media = FALSE, doc = TRUE WHERE uid = {}'.format(user_id)
        self.cur.execute(sql)
        self.conn.commit()
        self.disconnect()

    def user_save_thumb(self, user_id: int, path):
        if self.err:
            return
        image = open(path, 'rb+')
        image_bin = image.read()
        if not self.user_check(user_id):
            sql = 'INSERT INTO users (thumb, uid) VALUES (%s, %s)'
        else:
            sql = 'UPDATE users SET thumb = %s WHERE uid = %s'
        self.cur.execute(sql, (image_bin, user_id))
        self.conn.commit()
        self.disconnect()

    def user_rm_thumb(self, user_id: int, path):
        if self.err:
            return
        elif self.user_check(user_id):
            sql = 'UPDATE users SET thumb = NULL WHERE uid = {}'.format(user_id)
        self.cur.execute(sql)
        self.conn.commit()
        self.disconnect()

    def user_check(self, uid: int):
        self.cur.execute("SELECT * FROM users WHERE uid = {}".format(uid))
        res = self.cur.fetchone()
        return res

    def rss_add(self, name, link, last, title):
        if self.err:
            return
        q = (name, link, last, title)
        self.cur.execute("INSERT INTO rss (name, link, last, title) VALUES (%s, %s, %s, %s)", q)
        self.conn.commit()
        self.disconnect()

    def rss_update(self, name, last, title):
        if self.err:
            return
        q = (last, title, name)
        self.cur.execute("UPDATE rss SET last = %s, title = %s WHERE name = %s", q)
        self.conn.commit()
        self.disconnect()

    def rss_delete(self, name: str):
        if self.err:
            return
        self.cur.execute("DELETE FROM rss WHERE name = %s", (name,))
        self.conn.commit()
        self.disconnect()

    def rss_delete_all(self):
        if self.err:
            return
        self.cur.execute("TRUNCATE TABLE rss")
        self.conn.commit()
        self.disconnect()

if DB_URI is not None:
    DbManger().db_init()


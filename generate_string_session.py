from pyrogram import Client

API_KEY = int(input("Enter API KEY: "))
API_HASH = input("Enter API HASH: ")
with Client(name='USS', api_id=API_KEY, api_hash=API_HASH, in_memory=True) as app:
    print(app.export_session_string())

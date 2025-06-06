from os import getcwd
from os.path import join
from shutil import make_archive
from asyncio import run, sleep, to_thread
from pytdbot import Client

api_id = input("Enter api_id: ")
api_hash = input("Enter api_hash: ")


async def main():
    client = Client(
        api_id=api_id,
        api_hash=api_hash,
        files_directory=join(getcwd(), "tdlib_user"),
        database_encryption_key="mltbmltb",
        td_verbosity=1,
        user_bot=True,
    )

    @client.on_updateAuthorizationState()
    async def handle_auth(client, _):
        match client.authorization_state:
            case "authorizationStateReady":
                print("LOGIN SUCCESSFUL")
                await sleep(2)

                me = await client.invoke({"@type": "getMe"})
                session_dir = join(getcwd(), "tdlib_user")
                zip_path = make_archive(session_dir, "zip", session_dir)

                await client.sendDocument(
                    chat_id=me.id,
                    document={
                        "@type": "inputFileLocal",
                        "path": zip_path
                    },
                    caption="Your session data",
                )
                print("Session zip file sent to saved messages.")
                await client.stop()

            case "authorizationStateWaitTdlibParameter":
                await client.set_td_parameters()

            case "authorizationStateWaitPhoneNumber":
                phone_number = await to_thread(input, "Enter phone_number: ")
                res = await client.setAuthenticationPhoneNumber(
                    phone_number=phone_number
                )
                if res["@type"] != "ok":
                    print(res["message"])

            case "authorizationStateWaitCode":
                code = await to_thread(input, "Enter code: ")
                res = await client.checkAuthenticationCode(code=code)
                if res["@type"] != "ok":
                    print(res["message"])

            case "authorizationStateWaitPassword":
                password = await to_thread(input, "Enter password: ")
                res = await client.checkAuthenticationPassword(password=password)
                if res["@type"] != "ok":
                    print(res["message"])

    await client.start()
    await client.idle()


run(main())

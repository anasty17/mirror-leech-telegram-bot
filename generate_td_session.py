from os import getcwd
from pytdbot import Client
from asyncio import run, to_thread

api_id = input("Enter api_id: ")
api_hash = input("Enter api_hash: ")


async def main():

    client = Client(
        api_id=api_id,
        api_hash=api_hash,
        files_directory=f"{getcwd()}/tdlib_user",
        use_file_database=False,
        td_verbosity=1,
        user_bot=True,
    )

    @client.on_updateAuthorizationState()
    async def handle_auth(_, update):
        match update.authorization_state:
            case "authorizationStateReady":
                print("LOGIN SUCCESSFUL")
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

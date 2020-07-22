from telegraph import Telegraph

telegraph = Telegraph()
telegraph.create_account(short_name=input("Enter a username for your Telegra.ph : "))

print(f"Your Telegra.ph token ==>  {telegraph.get_access_token()}")
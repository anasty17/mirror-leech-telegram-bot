class SubFunctions:

    def __init__(self):
        pass

    async def login(self, name: str, host: str, username: str, password: str):
        return await self.set_special_config(
            "servers",
            {
                "name": name,
                "displayname": host,
                "host": host,
                "connections": 8,
                "username": username,
                "password": password,
            },
        )

    async def create_category(self, name: str, dir: str):
        return await self.set_special_config("categories", {"name": name, "dir": dir})

    async def delete_category(self, name: str):
        return await self.delete_config("categories", name)

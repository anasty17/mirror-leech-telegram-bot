class SubFunctions:

    async def check_login(self):
        res = await self.get_config("servers")
        if res["config"]:
            self.LOGGED_IN = True
            return res["config"]
        else:
            return False

    async def add_server(self, server: dict):
        """server = {
            "name": "main",
            "displayname": "main",
            "host": "",
            "port": 5126,
            "timeout": 60,
            "username": "",
            "password": "",
            "connections": 8,
            "ssl": 1,
            "ssl_verify": 2,
            "ssl_ciphers": "",
            "enable": 1,
            "required": 0,
            "optional": 0,
            "retention": 0,
            "send_group": 0,
            "priority": 0,
        }"""
        return await self.set_special_config("servers", server)

    async def create_category(self, name: str, dir: str):
        return await self.set_special_config("categories", {"name": name, "dir": dir})

    async def delete_category(self, name: str):
        return await self.delete_config("categories", name)

import discord
import asyncio

class Role:

    title = None
    player = None

    async def initialize(player):
        return await Role.initialize_helper(player, "Unassigned", Role())

    async def initialize_helper(player, title, role_instance):
        self = role_instance
        self.player = player
        self.title = title
        await self.send_role_introduction_message()
        await self.send_team_introduction_message()
        return self

    async def send_role_introduction_message(self):
        await self.player.send_message(f"[ROLE INTRODUCTION: {self.title}]")

    async def send_team_introduction_message(self):
        pass

    async def handle_message(self, message):
        pass

    async def night_action(self):
        pass

    async def round_action(self):
        pass

    async def election_action(self):
        pass

class RoleCivilian(Role):

    async def initialize(player):
        return await Role.initialize_helper(player, "Civilian", RoleCivilian())
    
    async def send_team_introduction_message(self):
        await self.player.send_message("Civilian team")

class RoleVillain(Role):

    async def initialize(player):
        return await Role.initialize_helper(player, "Villain", RoleVillain())
    
    async def send_team_introduction_message(self):
        await self.player.send_message("Villain team")
        await self.player.send_message(f"The keyword is `{self.player.game.keyword}`.")

    async def night_action(self):
        await super.night_action()
        msg = "Here's your villainous team:"
        for ply in self.player.game.player_list:
            if isinstance(ply.role, RoleVillain):
                msg += "\n" + ply.user.name
        await self.player.send_message(msg)

class RoleSheriff(RoleCivilian):

    async def initialize(player):
        return await Role.initialize_helper(player, "Sheriff", RoleSheriff())
    
class RoleMastermind(RoleVillain):

    async def initialize(player):
        return await Role.initialize_helper(player, "Mastermind", RoleMastermind())

    async def night_action(self):
        await super.night_action()
        await self.player.send_message(f"Write 5 words (separated by spaces) that the WITNESS cannot use when describing the keyword, `{self.player.game.keyword}`.")
        
    
    
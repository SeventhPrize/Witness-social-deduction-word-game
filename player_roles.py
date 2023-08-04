"""
Classes for player roles: Sheriff, Civilians, Mastermind, Villains
"""

from nltk.stem.snowball import SnowballStemmer
import random
from time import time
import math
import re
import deprecated.gamestates as gs
from gpt_responder import GptWitness

# Number of seconds between WITNESS questions. Saves money on OpenAI API.
QUESTION_COOLDOWN = 15

class Role:
    '''
    Abstract parent class for each of the player roles.
    Has methods for role actions during each game state.
    '''

    title = None            # String title of this role
    player = None           # The Player object who holds this role
    power_activated = None  # Counts the number of times this role has activated their special power

    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        return await Role.initialize_helper(player, "Unassigned", Role())

    async def initialize_helper(player, title, role_instance):
        '''
        Intializes and returns the given Role object
        INPUT
            player; Player object who holds this role
            title; string title for this role
            role_instance; instance of the role to initialize
        RETURNS
            the initialized Role object
        '''
        self = role_instance
        self.player = player
        self.title = title
        self.power_activated = 0
        await self.send_team_introduction_message()
        await self.send_role_introduction_message()
        return self

    async def send_role_introduction_message(self):
        '''
        Sends the player an introduction message for their role.
        '''
        pass

    async def send_team_introduction_message(self):
        '''
        Sends the player an intrdouction message for their team (Villain or Civilian)
        '''
        pass

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        split_msg = message.split()
        if len(split_msg) >= 1 and split_msg[0] == "$power":
            if len(split_msg) >= 2:
                value = " ".join(split_msg[1:])
            else:
                value = None
            await self.power(value)
            return

    async def question_action(self):
        '''
        Role actions during Questioning
        '''
        pass

    async def guess_action(self):
        '''
        Role actions during Guess
        '''
        pass

    async def trial_action(self):
        '''
        Role actions during Trial
        '''
        pass

    async def power(self, value):
        return

class RoleCivilian(Role):
    '''
    Class for Civilian role. Parent class for Civilians with special powers, like the Sheriff.
    '''

    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        return await Role.initialize_helper(player, "Civilian", RoleCivilian())
    
    async def send_team_introduction_message(self):
        '''
        Sends the player an intrdouction message for the Civilian team
        '''
        await self.player.send_message("As a **Civilian**, your goal is to figure out the secret keyword or to identify a Villain.")

class RoleVillain(Role):
    '''
    Class for Villain role. Parent class for Villains with special powers, like the Mastermind.
    '''

    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        return await Role.initialize_helper(player, "Villain", RoleVillain())
    
    async def send_team_introduction_message(self):
        '''
        Sends the player an intrdouction message for the Villain team
        '''
        await self.player.send_message("As a **Villain**, your goal is to mislead the Civilians so that they cannot figure out the keyword. Stay hidden so that they do not suspect your villanous nature.")
        await self.player.send_message(f":key: The keyword is **{self.player.game.keyword}**.")

        # Report the villainous teammates
        msg = "Here's your villainous team:"
        for ply in self.player.game.player_list:
            if isinstance(ply.role, RoleVillain):
                msg += f"\n\t**{ply.user.name}**"
        await self.player.send_message(msg)

class RoleReporter(RoleCivilian):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Reporter", RoleReporter())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Reporter an introduction message.
        '''
        await self.player.send_message("**Reporter**, you find out whenver another player activates a special power.")

class RoleUndercoverInvestigator(RoleCivilian):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "UndercoverInvestigator", RoleUndercoverInvestigator())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the UndercoverInvestigator an introduction message.
        '''
        await self.player.send_message("**UndercoverInvestigator**, once per game, use command `$power` to alert the active Questioner that you are a Civilian.")

    async def power(self, value=None):
        await super.power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            active_questioner = self.player.game.get_questioner()
            await self.player.send_message(f"Alerted Questioner `{active_questioner.user.name}` that you are a Civilian.")
            await active_questioner.send_message(f"**ALERT**\tUndercoverInvestigator `{self.player.user.name}` secretly alerted you that they are a Civilian. No one else knows this.")
            return
        
class RoleDetective(RoleCivilian):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Detective", RoleDetective())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Detective an introduction message.
        '''
        word = random.choice(self.player.game.gpt_witness.banned_words)
        await self.player.send_message(f"**Detective**, you know one of the banned words: **{word}**.")
        
class RoleCensorer(RoleVillain):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Censorer", RoleCensorer())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Censorer an introduction message.
        '''
        await self.player.send_message("**Censorer**, once per game, use command `$power` to censor the next WITNESS's next response. Everyone will only observe a single word from the WITNESS's response. This may mean that some of the response is not observed by anybody.")

    async def power(self, value=None):
        await super.power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message("You censored the WITNESS's next response!")
            return

class RoleIntimidator(RoleVillain):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Intimidator", RoleIntimidator())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Intimidator an introduction message.
        '''
        await self.player.send_message("**Intimidator**, once per game, use command `$power <text>` to add additional text to the next question asked to the WITNESS. This text is secret; no one will know about this addendum.")

    async def power(self, value=""):
        await super.power(value)

        if self.power_activated == 0:
            if value > self.player.game.settings["questioncharlimit"]:
                await self.player.send_message(f"Your addendum text is too long! It is {len(value)} characters, and it capped at {self.player.game.settings['questioncharlimit']} characters. Enter again.")
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message(f"You added the following text to the WITNESS's next question: {value}")
            return

class RoleHacker(RoleVillain):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Hacker", RoleHacker())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Hacker an introduction message.
        '''
        await self.player.send_message("**Hacker**, once per game, use command `$power` to secretly force the WITNESS to ignore the next question they are asked. The WITNESS will instead answer the previous question again.")

    async def power(self, value=None):
        await super.power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message("You hacked the WITNESS's next question!")
            return

class RolePolitician(RoleCivilian):
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Politician", RolePolitician())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Politician an introduction message.
        '''
        await self.player.send_message("**Politician**, you are a Civilian. Once per game during Questioning, use command `$power` to become a Villain instead.")

    async def power(self, value=None):
        await super.power(value)

        if self.power_activated == 0:
            self.power_activated += 1
# TODO
            return

"""
Classes for player roles: Sheriff, Civilians, Mastermind, Villains
"""

import pandas as pd
import re
import random
import gamestates as gs

# Get the .csv file describing each role's abilities
ROLE_DF = pd.read_csv("Role Summary.csv",
                      index_col="Title")

def get_titles():
    '''
    RETURNS list of all unique role titles that can be assigned at the start of the game
    '''
    return [title.lower() for title in ROLE_DF.index.tolist()]

def get_role_desc():
    '''
    RETURNS string table of all the unique roles and their descriptions
    '''
    return "\n".join([f"**{title}**\t{ROLE_DF.loc[title, 'Intro']}"
                      for title in ROLE_DF.index])

async def role_builder(ply, title="civilian"):
    '''
    RETURNS an instance of the Role associated with the given title
    INPPUT
        ply; the player for which the Role should be instantiated
        title; the title of the role
    RETURNS
        instance of the Role
    '''
    match title.lower():
        case "civilian":
            return await RoleCivilian.initialize(ply)
        case "villain":
            return await RoleVillain.initialize(ply)
        case "reporter":
            return await RoleReporter.initialize(ply)
        case "undercover":
            return await RoleUndercover.initialize(ply)
        case "stenographer":
            return await RoleStenographer.initialize(ply)
        case "detective":
            return await RoleDetective.initialize(ply)
        case "forensic":
            return await RoleForensic.initialize(ply)
        case "censorer":
            return await RoleCensorer.initialize(ply)
        case "intimidator":
            return await RoleIntimidator.initialize(ply)
        case "hacker":
            return await RoleHacker.initialize(ply)
        case "politician":
            return await RolePolitician.initialize(ply)
        case _:
            raise Exception(f"Invalid title {title}.")

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
        # await self.send_team_introduction_message()
        await self.send_role_introduction_message()
        return self

    async def send_role_introduction_message(self):
        '''
        Sends the player an introduction message for their role.
        '''
        await self.player.send_message(f"**{self.title}**: {ROLE_DF.loc[self.title, 'Intro']}")

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
        # Check for power activation
        split_msg = message.content.split()
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
        await self.player.send_message(f"The WITNESSS is banned from using these words:\n"
                                       + "\n".join(self.player.game.gpt_witness.banned_words))

        # Report the villainous teammates
        msg = "Here's your villainous team:"
        for ply in self.player.game.player_list:
            if isinstance(ply.role, RoleVillain):
                msg += f"\n\t**{ply.user.name}**"
        await self.player.send_message(msg)

class RoleReporter(RoleCivilian):
    '''
    Reporter gets alerted whenever a power is activated.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Reporter", RoleReporter())
        return self
    
class RoleUndercover(RoleCivilian):
    '''
    Undercover can alert the questioner that they are a civilian.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Undercover", RoleUndercover())
        return self
    
    async def power(self, value=None):
        '''
        Alerts the current questioner that this player is a civilian
        '''
        await super().power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            active_questioner = self.player.game.get_questioner()
            await self.player.send_message(f"Alerted Questioner `{active_questioner.user.name}` that you are a Civilian.")
            await active_questioner.send_message(f"**ALERT**\tUndercover `{self.player.user.name}` secretly alerted you that they are a Civilian. No one else knows this.")
            return
        
class RoleStenographer(RoleCivilian):
    '''
    Stenographer can see the full text of one question.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Stenographer", RoleStenographer())
        return self
    
    async def power(self, value=None):
        '''
        Request to see the next question's full text
        '''
        await super().power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.send_message("You will see the entirety of the next question.")
            await self.player.game.activate_power(self.title, value)
            return
        
class RoleDetective(RoleCivilian):
    '''
    Detective sees one of the banned words
    '''
    
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
        Reveal a banned word.
        '''
        await super().send_role_introduction_message()
        word = random.choice(self.player.game.gpt_witness.banned_words)
        await self.player.send_message(f"**{word}**")

class RoleForensic(RoleCivilian):
    '''
    Forensic sees a banned word, but its vowels are missing and its letters are scrambled.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Forensic", RoleForensic())
        return self
    
    async def send_role_introduction_message(self):
        '''
        Sends the Forensic an introduction message.
        See a scrambled banned word
        '''
        await super().send_role_introduction_message()

        word = random.choice(self.player.game.gpt_witness.banned_words)
        pattern = r"[aeiou]"
        clue = re.sub(pattern, "", word.lower()).capitalize()
        clue = list(clue)
        random.shuffle(clue)
        clue = "".join(clue)
        await self.player.send_message(f"**{clue}**")

class RoleCensorer(RoleVillain):
    '''
    Censorer can supress the WITNESS response.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Censorer", RoleCensorer())
        return self
    
    async def power(self, value=None):
        '''
        Requests to supress WITNESS response
        '''
        
        await super().power(value)

        if self.power_activated == 0:
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message("You censored the WITNESS's next response!")
            return

class RoleIntimidator(RoleVillain):
    '''
    Intimidator can change the text of one WITNESS question
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Intimidator", RoleIntimidator())
        return self
    
    async def power(self, value=""):
        '''
        Request to change the next WITNESS question
        '''
        await super().power(value)

        if self.power_activated == 0:
            if len(value) > self.player.game.settings["questioncharlimit"]:
                await self.player.send_message(f"Your addendum text is too long! It is {len(value)} characters, and it capped at {self.player.game.settings['questioncharlimit']} characters. Enter again.")
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message(f"You added the following text to the WITNESS's next question: {value}")
            return

class RoleHacker(RoleVillain):
    '''
    Hacker can burn one of the WITNESS's questions, making them instead answer the previous question again
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Hacker", RoleHacker())
        return self
    
    async def power(self, value=None):
        '''
        Request to burn the next question
        '''
        
        await super().power(value)

        if self.power_activated == 0:
            if len(self.player.game.gpt_witness.witness_questions) == 0:
                await self.player.send_message("You cannot use your Hacker power until at least one question has been asked.")
                return
            self.power_activated += 1
            await self.player.game.activate_power(self.title, value)
            await self.player.send_message("You hacked the WITNESS's next question!")
            return

class RolePolitician(RoleCivilian):
    '''
    Politician can change to a Crook.
    '''
    
    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Politician", RolePolitician())
        return self
    
    async def power(self, value=None):
        '''
        Change to a Crook
        '''
        await super().power(value)

        if self.power_activated == 0:
            if isinstance(self.player.game.gamestate, gs.GameStateQuestion):
                self.power_activated += 1
                await self.player.game.send_global_message("The Politician has been corrupted! They are now a Crook on the Villain team.")
                self.player.role = await RoleCrook.initialize(self.player)
                return
            else:
                await self.player.send_message("You can only activate your Politician power during the Questioning phase.")
                return

class RoleCrook(RoleVillain):
    '''
    This role is not intended to be assigned. It is what the Politician turns into if they activate their power.
    '''

    async def initialize(player):
        self = RoleCrook()
        self.player = player
        self.title = "Crook"
        self.power_activated = 1
        await self.send_role_introduction_message()
        return self
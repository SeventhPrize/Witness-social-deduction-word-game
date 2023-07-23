from nltk.stem.snowball import SnowballStemmer
import discord
import asyncio
import random
from time import time
import math
import re
import gamestates as gs

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

    # async def act(self):
    #     print("HERE")
    #     gamestate = self.player.game.gamestate
    #     if isinstance(gamestate, gs.GameStateNight):
    #         await self.night_action()
    #         return
    #     if isinstance(gamestate, gs.GameStateDay):
    #         await self.daily_action()
    #         return
    #     if isinstance(gamestate, gs.GameStateGuess):
    #         await self.guess_action()
    #         return
    #     if isinstance(gamestate, gs.GameStateTrial):
    #         await self.trial_action()
    #         return

    async def night_action(self):
        pass
        # if not isinstance(self, RoleMastermind):
        #     await self.player.send_message(f"Hold tight while the Mastermind secretly bans words from the WITNESS vocabulary . . .")

    async def daily_action(self):
        pass
        # if not isinstance(self, RoleSheriff):
        #     await self.player.send_message(f"Hold tight while Sheriff `{self.player.game.sheriff_player.user.name}` asks the WITNESS a question about the keyword . . .")

    async def guess_action(self):
        pass

    async def trial_action(self):
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
        await super().night_action()
        msg = "Here's your villainous team:"
        for ply in self.player.game.player_list:
            if isinstance(ply.role, RoleVillain):
                msg += f"\n\t**{ply.user.name}**"
        await self.player.send_message(msg)

class RoleSheriff(RoleCivilian):

    prompt_char_limit = None

    async def initialize(player):
        self = await Role.initialize_helper(player, "Sheriff", RoleSheriff())
        self.prompt_char_limit = 100
        return self

    async def daily_action(self):
        await super().daily_action()
        await self.player.game.send_global_message(f"The Sheriff has {self.player.game.gamestate.time_limit} seconds to ask the WITNESS a series of open-ended questions to figure out the keyword. Everyone is encouraged to help--although the Villains might try to mislead. The WITNESS's response is vague and complicated: everyone sees a different portion of each of the WITNESS's clues.")
        await self.player.send_message("**Sheriff, ask the WITNESS a question about the keyword.**")

    async def guess_action(self):
        await super().guess_action()
        await self.player.game.send_global_message(f"The Sheriff has {self.player.game.gamestate.time_limit} seconds to guess the keyword. They only have one attempt. Everyone is encouraged to help brainstorm. The keyword is made of up {len(self.player.game.keyword.split())} word(s).")
        await self.player.send_message("Sheriff, make your guess.")

    async def handle_message(self, message):
        await super().handle_message(message)

        if isinstance(self.player.game.gamestate, gs.GameStateDay):

            if len(message.content) > self.prompt_char_limit:
                await self.player.send_message(f"Your question must be fewer than {self.prompt_char_limit} characters. Your question was {len(message.content)} characters.")
                return
            
            if message.content == "$readytoguess":
                await self.player.game.send_global_message("The Sheriff has elected to end questioning early!")
                await self.player.game.gamestate.proceed()
                return
            
            self.player.game.witness_questions.append(message.content)
            
            raw_response = self.player.game.gpt_witness.ask(message.content)
            self.player.game.witness_responses.append(raw_response)

            witness_response = raw_response.split()
            
            random.shuffle(witness_response)

            for ply in self.player.game.player_list:
                observed_words = witness_response[: self.player.game.n_words_per_player]
                witness_response = witness_response[self.player.game.n_words_per_player :]
                
                msg = f"Sheriff `{self.player.user.name}` asked the WITNESS:"
                msg += f"\n\t**{message.content}**"
                msg += "\n"
                msg += "You observed the following words."
                for word in observed_words:
                    msg += f"\n\t**{word}**"
                msg += "\n" + f"There are {math.floor(self.player.game.gamestate.time_limit - time() + self.player.game.gamestate.start)} of {self.player.game.gamestate.time_limit} seconds remaining."
                await ply.send_message(msg)

            return
        
        if isinstance(self.player.game.gamestate, gs.GameStateGuess):
            guess = message.content.strip()
            if len(guess.split()) != len(self.player.game.keyword.split()):
                await self.player.send_message(f"Your guess for the keyword contained {len(guess.split())} word(s), but the keyword is made of {len(self.player.game.keyword.split())} word(s) (separated by spaces).")
                return
            
            await self.player.game.send_global_message(f"The Sheriff guessed **{guess}**. The correct keyword is **{self.player.game.keyword}**.")

            stemmer = SnowballStemmer("english")
            guess_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                           for word in guess.split()]
            true_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                          for word in self.player.game.keyword.split()]
            if guess_stems == true_stems:
                await self.player.game.send_global_message("The Sheriff guessed **correctly**. The Civilians win!")
                await self.player.game.gamestate.proceed(go_to_trial=False)
            else:
                await self.player.game.send_global_message("The Sheriff was **wrong**. The Villains gain the upper hand!")
                await self.player.game.gamestate.proceed(go_to_trial=True)
            return


class RoleMastermind(RoleVillain):

    n_banned_words = None

    async def initialize(player):
        self = await Role.initialize_helper(player, "Mastermind", RoleMastermind())
        self.n_banned_words = 5
        return self

    async def night_action(self):
        await super().night_action()
        await self.player.game.send_global_message("The Mastermind is banning words from the WITNESS's vocabulary . . .")
        await self.player.send_message(f"**Mastermind, write {self.n_banned_words} words (separated by spaces) that the WITNESS cannot use when describing the keyword, `{self.player.game.keyword}`.**")
        
    async def handle_message(self, message):
        await super().handle_message(message)
        
        if isinstance(self.player.game.gamestate, gs.GameStateNight):
            split_msg = message.content.strip().split()
            if len(split_msg) != self.n_banned_words:
                await self.player.send_message(f"Write {self.n_banned_words} words (separated by spaces). You wrote {len(split_msg)} words.")
                return
            for word in split_msg:
                if len(word) > 20:
                    await self.player.send_message(f"Each submitted word must be 20 characters or less. `{word}` is {len(word)} characters. Submit your {self.n_banned_words} again.")
                    return
            self.player.game.gpt_witness.banned_words = self.player.game.keyword.split() + split_msg
            await self.player.send_message("Banned words successfully submitted! The WITNESS will not use of these words.")
            await self.player.game.gamestate.proceed()


    
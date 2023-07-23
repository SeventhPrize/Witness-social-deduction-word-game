"""
Classes for player roles: Sheriff, Civilians, Mastermind, Villains
"""

from nltk.stem.snowball import SnowballStemmer
import random
from time import time
import math
import re
import gamestates as gs
from gpt_responder import GptWitness

class Role:
    '''
    Abstract parent class for each of the player roles.
    Has methods for role actions during each game state.
    '''

    title = None    # String title of this role
    player = None   # The Player object who holds this role

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
        await self.send_team_introduction_message()
        await self.send_role_introduction_message()
        return self

    async def send_role_introduction_message(self):
        '''
        Sends the player an introduction message for their role.
        '''
        await self.player.send_message(f"[ROLE INTRODUCTION: {self.title}]")

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
        pass

    async def night_action(self):
        '''
        Role actions during Night
        '''
        pass

    async def daily_action(self):
        '''
        Role actions during Day
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

    def conclusion(self):
        '''
        RETURNS a string conclusion for this Role's actions this game
        '''
        return ""

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
        await self.player.send_message("Civilian team INTRODUCTION")

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
        await self.player.send_message("Villain team INTRODUCTION")
        await self.player.send_message(f"The keyword is **{self.player.game.keyword}**.")

        # Report the villainous teammates
        msg = "Here's your villainous team:"
        for ply in self.player.game.player_list:
            if isinstance(ply.role, RoleVillain):
                msg += f"\n\t**{ply.user.name}**"
        await self.player.send_message(msg)

class RoleSheriff(RoleCivilian):
    '''
    Class for Sheriff role
    '''

    prompt_char_limit = None    # Character limit on WITNESS question prompts
    witness_questions = None    # List of string questions asked to the WITNESS
    witness_responses = None    # List of string responses received from the WITNESS

    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Sheriff", RoleSheriff())
        self.prompt_char_limit = self.player.game.settings["questioncharlimit"]
        self.witness_questions = []
        self.witness_responses = []
        return self

    async def daily_action(self):
        '''
        Prompts the Sheriff to ask the WITNESS questions at Day
        '''
        await super().daily_action()
        await self.player.game.send_global_message(f"The Sheriff has {self.player.game.gamestate.time_limit} seconds to ask the WITNESS a series of open-ended questions to figure out the keyword. Everyone is encouraged to help--although the Villains might try to mislead. The WITNESS's response is vague and complicated: everyone sees a different portion of each of the WITNESS's clues.")
        await self.player.send_message("**Sheriff, ask the WITNESS a question about the keyword.**")

    async def guess_action(self):
        '''
        Prompts the Sheriff to guess the keyword at Guess
        '''
        await super().guess_action()
        await self.player.game.send_global_message(f"The Sheriff has {self.player.game.gamestate.time_limit} seconds to guess the keyword. They only have one attempt. Everyone is encouraged to help brainstorm. The keyword is made of up {len(self.player.game.keyword.split())} word(s).")
        await self.player.send_message("Sheriff, make your guess.")

    async def handle_message(self, message):
        '''
        Handles Sheriff player's messages.
        If during Day, handles messages as questions to the WITNESS
        If during Guess, handles messages as keyword guesses
        INPUT
            message; Discord message object to handle
        '''
        await super().handle_message(message)

        # If Day, handle message as questions to the WITNESS
        if isinstance(self.player.game.gamestate, gs.GameStateDay):

            # Check for proper question length
            if len(message.content) > self.prompt_char_limit:
                await self.player.send_message(f"Your question must be fewer than {self.prompt_char_limit} characters. Your question was {len(message.content)} characters.")
                return
            
            # $readytoguess ends Day early and immediately sends game state to Guess
            if message.content == "$readytoguess":
                await self.player.game.send_global_message("The Sheriff has elected to end questioning early!")
                await self.player.game.gamestate.proceed()
                return
            
            # Record question and answer
            self.witness_questions.append(message.content)
            raw_response = self.player.game.gpt_witness.ask(message.content)
            self.witness_responses.append(raw_response)

            # Shuffle response and distribute clues to players
            witness_response = raw_response.split()
            random.shuffle(witness_response)
            for ply in self.player.game.player_list:
                observed_words = witness_response[: self.player.game.settings["wordsperplayer"]]
                witness_response = witness_response[self.player.game.settings["wordsperplayer"] :]
                
                # Report clue
                msg = f"Sheriff `{self.player.user.name}` asked the WITNESS:"
                msg += f"\n\t**{message.content}**"
                msg += "\n"
                msg += "You observed the following words."
                for word in observed_words:
                    msg += f"\n\t**{word}**"
                msg += "\n" + f"There are {math.floor(self.player.game.gamestate.time_limit - time() + self.player.game.gamestate.start)} of {self.player.game.gamestate.time_limit} seconds remaining."
                await ply.send_message(msg)
            return
        
        # If Guess, handle message as keyword guess
        if isinstance(self.player.game.gamestate, gs.GameStateGuess):
            guess = message.content.strip()

            # Check if guess has same number of words as keyword
            if len(guess.split()) != len(self.player.game.keyword.split()):
                await self.player.send_message(f"Your guess for the keyword contained {len(guess.split())} word(s), but the keyword is made of {len(self.player.game.keyword.split())} word(s) (separated by spaces).")
                return
            
            # Check if guess and keyword have the same English roots (stems). If so, then correct.
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
        
    def conclusion(self):
        '''
        RETURNS string reporting the Sheriff's questions and answers from Day phase
        '''
        msg = super().conclusion()           
        msg += ("Here are the WITNESS prompts and responses:"
                + "".join([f"\n*{question}* \n{response}"
                           for question, response in zip(self.witness_questions, self.witness_responses)])) 
        return msg

class RoleMastermind(RoleVillain):
    '''
    Class for Mastermind role
    '''

    banned_words = None     # list of string words that are banned from WITNESS vocabulary
    n_banned_words = None   # number of words to be banned from WITNESS vocabulary

    async def initialize(player):
        '''
        RETURNS this intialized Role object
        INPUT
            player; Player object who holds this role
        '''
        self = await Role.initialize_helper(player, "Mastermind", RoleMastermind())
        self.n_banned_words = self.player.game.settings["numbannedwords"]
        return self

    async def night_action(self):
        '''
        Prompts the Mastermind to ban words from WITNESS vocabulary
        '''
        await super().night_action()
        await self.player.game.send_global_message("The Mastermind is banning words from the WITNESS's vocabulary . . .")
        await self.player.send_message(f"**Mastermind, write {self.n_banned_words} words (separated by spaces) that the WITNESS cannot use when describing the keyword, `{self.player.game.keyword}`.**")
        
    async def handle_message(self, message):
        '''
        If Night, handles message as a list of words to ban from WITNESS vocabulary
        '''
        await super().handle_message(message)
        
        if isinstance(self.player.game.gamestate, gs.GameStateNight):
            split_msg = message.content.strip().split()

            # Check if correct number of words are banned
            if len(split_msg) != self.n_banned_words:
                await self.player.send_message(f"Write {self.n_banned_words} words (separated by spaces). You wrote {len(split_msg)} words.")
                return
            
            # Check if each word is less than 16 characters
            for word in split_msg:
                if len(word) > 16:
                    await self.player.send_message(f"Each submitted word must be 20 or fewer characters. `{word}` is {len(word)} characters. Submit your {self.n_banned_words} again.")
                    return
                
            # Initialize GptWitness object
            n_words = self.player.game.settings["wordsperplayer"] * len(self.player.game.player_list)
            self.player.game.gpt_witness = GptWitness(self.player.game.keyword, n_words, split_msg)

            await self.player.send_message("Banned words successfully submitted! The WITNESS will not use of these words.")
            await self.player.game.gamestate.proceed()

    def conclusion(self):
        '''
        RETURNS string reporting the Mastermind's banned words from Night phase
        '''
        msg = super().conclusion()
        msg += ("The Mastermind banned the following words from the WITNESS's vocabulary: "
                + ", ".join(self.player.game.gpt_witness.banned_words))
        return msg

    
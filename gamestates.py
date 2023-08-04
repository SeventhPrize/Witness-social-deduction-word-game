"""
Game states/phases: Creation, Questioning, Guess, Trial
"""
import numpy as np
from nltk.stem.snowball import SnowballStemmer
from time import time
import math
import random
import re
import player_roles as pr
from gpt_responder import GptWitness

# Limit the maximum characters in WITNESS question and responses. Saves OpenAI API costs.
MAX_LIMITS = {"wordsperplayer" : 4,
              "questioncharlimit" : 100,
              "numbannedwords" : 20}
MIN_LIMITS = {"questioncooldown" : 15}

class GameState:
    '''
    Parent class for each game state.
    Has methods for proceeding between game states and handling game state-specific messages.
    '''    
    
    game = None                 # The Game object for this game state
    start = None                # The time() call at the start of this game state
    time_limit = None           # Integer number of seconds for this phase's time limit
    phase_end_message = None    # String message to send to all players when this phase's time limit is reached

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        return await GameState.initialize_helper(game, GameState())

    async def initialize_helper(game, gamestate_instance):
        '''
        Initializes and returns the input GameState object
        INPUT
            game; Game object
            gamestate_instance; instance of a GameState object to initialize
        RETURNS 
            the initialized GameState object
        '''
        self = gamestate_instance
        self.game = game
        self.start = time()
        self.time_limit = 3600
        self.phase_end_message = f"**This phase's time limit ({math.floor(self.time_limit)}sec) has been reached! If you had a task but did not submit an entry, your task will be ignored.**"
        return self

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        # If time limit is reached, then move to next GameState
        if time() - self.start > self.time_limit:
            await self.game.send_global_message(self.phase_end_message)
            await self.proceed()
            return "PROCEED"
        
        # Otherwise, have the sender's Player object handle the message
        for ply in self.game.player_list:
            if message.author.id == ply.user.id:
                await ply.handle_message(message)
                return
            
    async def conclude(self):
        '''
        RETURNS string message, intended to be sent to all players, that summarizes the events this game
        Starts a new game on this same channel
        '''
        # Get everyone's roles
        await self.game.send_global_message("Here is everyone's role for this game:\n"
                                            + "\n".join([f"{ply.user.name} \t {ply.role.title}"
                                                       for ply in self.game.player_list]))

        # Show WITNESS questions
        msg = ""
        if self.game.gpt_witness.witness_responses:
            for question, response in zip(self.game.gpt_witness.witness_questions, self.game.gpt_witness.witness_responses):
                msg += f"*{question}*\n{response}\n"
        await self.game.send_global_message(msg)

        # Report keyword
        await self.game.send_global_message(f"The keyword was **{self.game.keyword}**.")
        await self.game.send_global_message("The following words were banned: " + ", ".join(self.game.gpt_witness.banned_words))

        # Thank the players
        await self.game.send_global_message(":pray: Thanks for playing this trial version of **Witness: The Social Deduction Word Game**. Starting new game . . .")
        
        # Start new game
        self.game.gamestate = await GameStateCreation.initialize(self.game)
        await self.game.send_game_creation_message()
        return

    async def proceed(self):
        '''
        Changes the Game's game state to the next game state
        '''
        pass

class GameStateCreation(GameState):
    '''
    Game creation. The game host adjusts game settings before gameplay begins
    '''

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        return await GameState.initialize_helper(game, GameStateCreation())

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''

        # If game host sent the message, then either adjust settings or start game
        if message.author.id == self.game.player_list[0].user.id:
            split_msg = message.content.strip().split()
            
            # Adjust player roles
            if len(split_msg[0]) > 2 and split_msg[0][0] == "$" and split_msg[0][1:] == "role":
                split_msg[1] = split_msg[1].lower()
                split_msg[2] = split_msg[2].lower()
                if len(split_msg) != 3:
                    await self.game.player_list[0].send_message("Incorrect syntax for role modification. `$role <add/remove> <roletitle>` adds/removes a special role to the game.")
                    return
                if split_msg[1] != "add" and split_msg[1] != "remove":
                    await self.game.player_list[0].send_message("Incorrect syntax for role modificaiton. Second argument must be either `add` or `remove`.")
                    return
                if split_msg[2] not in pr.get_titles():
                    await self.game.player_list[0].send_message("Role title does not exist.")
                    return
                if split_msg[1] == "add":
                    self.game.settings["specialroles"].add(split_msg[2])
                    await self.game.send_global_message(f"Host added role `{split_msg[2]}`.")
                    return
                else:
                    self.game.settings["specialroles"].discard(split_msg[2])
                    await self.game.send_global_message(f"Host removed role `{split_msg[2]}`.")
                    return

            # Adjust game numeric settings
            if len(split_msg[0]) > 2 and split_msg[0][0] == "$" and split_msg[0][1:] in self.game.settings.keys():
                setting_name = split_msg[0][1:]

                # Confirm valid <settingname> <settingvalue> syntax
                if len(split_msg) == 2 and split_msg[1].isdigit():
                    found_int = int(split_msg[1])
                    if found_int <= 0:
                        await self.game.player_list[0].send_message("Invalid setting. Setting must be positive.")
                        return
                    
                    # Confirm the new setting value is within limits
                    if setting_name in MAX_LIMITS.keys() and found_int > MAX_LIMITS[setting_name]:
                        await self.game.player_list[0].send_message(f"Invalid setting value. `{setting_name}` has maximum limit of {MAX_LIMITS[setting_name]}.")
                        return
                    
                    if setting_name in MIN_LIMITS.keys() and found_int < MIN_LIMITS[setting_name]:
                        await self.game.player_list[0].send_message(f"Invalid setting value. `{setting_name}` has minimum limit of {MIN_LIMITS[setting_name]}.")
                        return

                    # Set new setting
                    self.game.settings[setting_name] = found_int
                    await self.game.send_global_message(f"Game host set {setting_name} to {found_int}.")
                else:
                    await self.game.player_list[0].send_message(f"Invalid setting. See `$showsettings` for help. Change settings by `$<settingname> <integer value>`.")
                return
            
            # Start game
            if split_msg[0] == "$start":

                # Check proper player count
                if len(self.game.player_list) < 2 or len(self.game.player_list) > 12:
                    await self.game.player_list[0].send_message("Cannot start game with fewer than 2 players or more than 12 players."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}.")
                    return
                                
                # Check proper role count
                if len(self.game.player_list) < len(self.game.settings["specialroles"]):
                    await self.game.player_list[0].send_message("Cannot start game with fewer players than the number of declared special roles."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}. The number of declared special roles is {len(self.game.settings['specialroles'])}."
                                                                + "\n" + "Use command `$showroles` to see the list of roles.")
                    return

                # Proceed to Questioning game state
                await self.proceed()
                return
            
        # Handle player leaving the game
        if message.content == "$leavegame":
            new_host = (message.author.id == self.game.player_list[0].user.id)
            for ply in self.game.player_list:
                if ply.user.id == message.author.id:
                    self.game.player_list.remove(ply)
                    await self.game.send_global_message(f"`{ply.user.name}` left the game. There are now {len(self.game.player_list)} players.")
                    await ply.channel.delete()
            if new_host:
                await self.game.send_game_creation_message()
            return
                
    async def proceed(self):
        '''
        Changes the Game's game state to Questioning
        Assigns a role to each player
        '''

        # Get keyword
        self.game.keyword = self.get_random_word()

        # Build GPT Responder
        self.game.gpt_witness = GptWitness(self.game,
                                           self.game.keyword,
                                           self.game.settings["numbannedwords"])

        # Randomized list of players for role assignment
        temp_player_list = self.game.player_list.copy()
        random.shuffle(temp_player_list)

        # Assign special roles
        for title in self.game.settings["specialroles"]:
            ply = temp_player_list.pop()
            ply.role = await pr.role_builder(ply, title)

        # Assign civilians
        while temp_player_list:
            ply = temp_player_list.pop()
            ply.role = await pr.role_builder(ply, "Civilian")
        
        # Send intro messages
        for ply in self.game.player_list:
            await ply.role.send_team_introduction_message()

        # Move to Questioning phase
        self.game.gamestate = await GameStateQuestion.initialize(self.game)
        return
    
    def get_random_word(self):
        '''
        RETURNS a random word from pictionary_words.txt
        '''
        with open("pictionary_words.txt") as f:
            words = f.readlines()
        keyword = random.choice(words).strip()
        print(f"'{keyword}'")
        return keyword

class GameStateQuestion(GameState):
    '''
    Questioning phase. Players take turns questioning the WITNESS about the keyword.
    '''

    previous_guess_time = None  # The time() seconds of the most recent guess

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        # Get object instance
        self = await GameState.initialize_helper(game, GameStateQuestion())
        self.time_limit = self.game.settings["questiondur"]
        self.phase_end_message = f"**The Questioning phase's time limit ({self.time_limit}sec) has been reached before anyone guessed the keyword. The current Questioner must attempt to guess the keyword!**"

        # Give player instructions
        await self.game.send_global_message(f":interrobang: Players will now take turns asking the WITNESS a question about the keyword. You have {self.time_limit}sec.")
        for ply in self.game.player_list:
            await ply.role.question_action()

        # Set initial questioner
        self.game.questioner = random.randrange(len(self.game.player_list))
        await self.send_questioner_instructions()
        self.previous_guess_time = time()

        return self
    
    async def proceed(self):
        '''
        Changes the Game's game state to Guess
        '''
        self.game.gamestate = await GameStateGuess.initialize(self.game)

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        # Check that the time limit has not passed
        flag = await super().handle_message(message)
        if flag and flag == "PROCEED":
            return

        # Check for questioner message
        if message.author.id == (self.game.get_questioner()).user.id:

            # If $readytoguess, end questioning early
            if message.content == "$readytoguess":
                await self.game.send_global_message("The Questioner has elected to end questioning early!")
                await self.game.gamestate.proceed()
                return

            # Ask the question
            split_msg = message.content.split()
            if len(split_msg) >= 2 and split_msg[0] == "$ask":
                
                # Check for question frequency cooldown
                if time() - self.previous_guess_time < MIN_LIMITS["questioncooldown"]:
                    await (self.game.get_questioner()).send_message(f"You're asking questions too quickly! Wait {MIN_LIMITS['questioncooldown']} seconds between questions.")
                    return
                
                # Check for proper question length
                if len(split_msg[1]) > self.game.settings["questioncharlimit"]:
                    await (self.game.get_questioner()).send_message(f"Your question must be fewer than {self.game.settings['questioncharlimit']} characters. Your question was {len(split_msg[1])} characters.")
                    return

                # Record question and answer
                question = " ".join(split_msg[1:])

                witness_response = await self.game.gpt_witness.ask(question)
                witness_words = witness_response.split()
                # self.game.gpt_witness.witness_responses.append((self.game.get_questioner()).user.name + ": " + witness_response)
                self.previous_guess_time = time()

                # Shuffle response
                random.shuffle(witness_words)
                if "Censorer" in self.game.powers.keys() and len(self.game.player_list) <= len(witness_words):
                    split_response = [[word] for word in witness_words[:len(self.game.player_list)]]
                    await self.game.send_global_message("The villainous **Censorer** has muddled the WITNESS response! Everyone only observes one word this round.")
                else:
                    split_response = np.array_split(np.array(witness_words), len(self.game.player_list))
                
                # Distribute response to players
                for ply in self.game.player_list:
                    observed_words = split_response.pop()
                    msg = f"`{(self.game.get_questioner()).user.name}` questioned the WITNESS."
                    msg += "\n"
                    msg += "You observed the following words."
                    for word in observed_words:
                        msg += f"\n\t**{word}**"
                    msg += "\n" + f"There are {math.floor(self.game.gamestate.time_limit - time() + self.game.gamestate.start)} of {self.game.gamestate.time_limit} seconds remaining."
                    await ply.send_message(msg)    
                
                # Rotate to new questioner and reset power activations
                self.game.questioner = (self.game.questioner + 1) % len(self.game.player_list)
                await self.send_questioner_instructions()   
                self.game.powers = {}     
                return
            
    async def send_questioner_instructions(self):
        '''
        Messages the current questioner with instructions about how to ask questions to the WITNESS
        '''
        await self.game.send_global_message(f"`{(self.game.get_questioner()).user.name}` is the Questioner!")
        await (self.game.get_questioner()).send_message(":mag: Use `$ask <question text>` to ask the WITNESS a question. If the group is ready to guess the keyword before time is up, use command `$readytoguess`.")
        return
                
            

class GameStateGuess(GameState):
    '''
    Guess phase. Questioner, with players' help, attempts to guess the keyword.
    '''

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        self = await GameState.initialize_helper(game, GameStateGuess())
        self.time_limit = self.game.settings["guessdur"]
        self.phase_end_message = f"**The Guess phase's time limit ({self.time_limit}sec) has been reached! The Questioner didn't submit a guess in time. Civilians' only recourse is to capture a Villain!**"
        await self.game.send_global_message(f":detective: Help **{(self.game.get_questioner()).user.name}** guess the keyword. The keyword is made of {len(self.game.keyword.split())} words. You have {self.time_limit}sec.")
        await (self.game.get_questioner()).send_message("Use command `$guess <your guess>` to make your guess.")
        for ply in self.game.player_list:
            await ply.role.guess_action()
        return self
    
    async def proceed(self, go_to_trial=True):
        '''
        Changes the Game's game state to Trial, or concludes the game and starts a new game at Creation
        INPUT
            go_to_trial; boolean whether to move game state to Trial; else concludes the game and starts new game at Creation
        '''
        if go_to_trial:
            self.game.gamestate = await GameStateTrial.initialize(self.game)
        else:
            await self.conclude()

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        # Check that the time limit has not passed
        flag = await super().handle_message(message)
        if flag and flag == "PROCEED":
            return

        # Check for a keyword guess
        split_msg = message.content.split()
        if split_msg[0] == "$guess" and message.author.id == (self.game.get_questioner()).user.id:
            
            guess = split_msg[1].lower()

            # Check if guess has same number of words as keyword
            if len(guess.split()) != len(self.game.keyword.split()):
                await (self.game.get_questioner()).send_message(f"Your guess for the keyword contained {len(guess.split())} word(s), but the keyword is made of {len(self.game.keyword.split())} word(s) (separated by spaces).")
                return
            
            # Check if guess and keyword have the same English roots (stems). If so, then correct.
            await self.game.send_global_message(f"Questioner {(self.game.get_questioner()).user.name} guessed **{guess}**. The correct keyword is **{self.game.keyword}**.")
            stemmer = SnowballStemmer("english")
            guess_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                            for word in guess.split()]
            true_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                            for word in self.game.keyword.split()]
            if guess_stems == true_stems:
                await self.game.send_global_message(":white_check_mark: The Questioner guessed **correctly**. The Civilians win!")
                await self.proceed(go_to_trial=False)
            else:
                await self.game.send_global_message(":no_entry_sign: The Questioner was **wrong**. The Villains gain the upper hand!")
                await self.proceed(go_to_trial=True)
            return

class GameStateTrial(GameState):
    '''
    Trial phase. Players vote for a player to convict.
    '''

    votes = None    # Dictionary mapping each player's name to the name of the player they vote for

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        self = await GameState.initialize_helper(game, GameStateTrial())
        self.time_limit = self.game.settings["trialdur"]
        self.votes = {}
        self.phase_end_message = f"**The Trial phase's time limit ({self.time_limit}sec) has been reached! If you didn't vote or failed to submit a Trial phase task, your submission will be ignored.**"
        suspects = [f"\n`{ply.user.name}`" for ply in self.game.player_list]
        await self.game.send_global_message(f":ballot_box: Everyone has {self.time_limit} seconds to vote for a player to convict. The Civilians win if the player with/tied for the most votes is a Villain. You can vote exactly once. You can change your vote as long as the time limit has not been reached and at least one player has not voted. Type (or copy/paste) the name of the player you want to vote for:" + "".join(suspects))
        for ply in self.game.player_list:
            await ply.role.trial_action()
        return self
    
    async def proceed(self):
        '''
        Counts votes and reports if a Villain was convicted
        Concludes the game and starts a new game at the GameStateCreation gamestate
        '''
        # Count the votes
        vote_dict = {} # dictionary maps each suspect's name to a list of player names that voted for that suspect
        for accuser in self.votes.keys():
            suspect = self.votes[accuser]
            if suspect is not None:
                if suspect not in vote_dict.keys():
                    vote_dict[suspect] = [accuser]
                else:
                    vote_dict[suspect].append(accuser)

        # Report final vote tally
        msg = "Here is the final vote tally:"
        for key in vote_dict.keys():
            msg += (f"\n`{key}` was suspected by "
                    + ", ".join([f"`{accusers}`"
                                 for accusers in vote_dict[key]]))
        await self.game.send_global_message(msg)
        
        # Report who was convicted
        max_votes = max([len(accusers) for accusers in vote_dict.values()])
        convicted = [suspect for suspect in vote_dict.keys()
                     if len(vote_dict[key]) == max_votes]
        await self.game.send_global_message(":link: The following players were convicted: "
                                            + ", ".join([f"`{suspect}`"
                                                         for suspect in convicted]))

        # Report if any Villains were convicted
        guilty = set(convicted).intersection([ply.user.name for ply in self.game.player_list
                                              if isinstance(ply.role, pr.RoleVillain)])
        if guilty:
            await self.game.send_global_message(":cop: **Congratulations, Civilians!** The following Villains were convicted: "
                                                + ", ".join([f"`{suspect}`" for suspect in guilty]))
        else:
            await self.game.send_global_message(":spy: **Congratulations, Villains!** You have escaped justice.")

        await self.conclude()
    
    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        # Check that the time limit has not passed
        flag = await super().handle_message(message)
        if flag and flag == "PROCEED":
            return

        # Check if the message author and suspect are both players in this game
        for accuser in self.game.player_list:
            if accuser.user.name == message.author.name:
                if message.content in [suspect.user.name for suspect in self.game.player_list]:
                    
                    # Record the vote
                    self.votes[accuser.user.name] = message.content
                    await accuser.send_message(f"You voted for `{message.content}`.")
                    if len(self.votes.keys()) == len(self.game.player_list):
                        await self.proceed()
                    return



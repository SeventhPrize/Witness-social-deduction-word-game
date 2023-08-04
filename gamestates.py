"""
Game states/phases: Creation, Night, Day, Guess, Trial
Random word generation from: https://github.com/first20hours/google-10000-english/blob/master/google-10000-english-usa-no-swears-long.txt
"""

from time import time
import math
import random
import deprecated.player_roles as pr
import numpy as np
from gpt_responder import GptWitness
from nltk.stem.snowball import SnowballStemmer

# Limit the maximum characters in WITNESS question and responses. Saves OpenAI API costs.
LIMITS = {"wordsperplayer" : 4,
          "questioncharlimit" : 100,
          "questioncooldown" : 15}

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
        self.phase_end_message = f"**This phase's time limit ({math.floor(self.time_limit)} sec) has been reached! If you had a task but did not submit an entry, your task will be ignored.**"
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
            return
        
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
        await self.game.send_global_message("Here is everyone's role for this game:"
                                            + "".join([f"{ply.user.name} \t {ply.role.title}"
                                                       for ply in self.game.player_list]))

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
                if len(split_msg) != 3:
                    await self.game.player_list[0].send_message("Incorrect syntax for role modification. `$role <roletitle> <add/remove>` adds/removes a special role to the game.")
                    return
                if split_msg[2] != "add" and split_msg[2] != "remove":
                    await self.game.player_list[0].send_message("Incorrect syntax for role modificaiton. Third argument must be either `add` or `remove`.")
                    return
                if split_msg[1] == "civilian" or split_msg[1] == "villain":
                    await self.game.player_list[0].send_message("Basic villains and civilians are not special roles and do not need to be specially added.")
                    return
                if split_msg[1] not in pr.get_special_role_titles():
                    await self.game.player_list[0].send_message("Special title does not exist.")
                    return
                if split_msg[2] == "add":
                    self.game.settings["specialroles"].append(split_msg[1])
                    await self.game.send_global_message(f"Host added role `{split_msg[1]}`.")
                    return
                else:
                    self.game.settings["specialroles"].remove(split_msg[1])
                    await self.game.send_global_message(f"Host removed role `{split_msg[1]}`.")
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
                    if setting_name in LIMITS.keys() and found_int > LIMITS[setting_name]:
                        await self.game.player_list[0].send_message(f"Invalid setting value. `{setting_name}` has maximum limit of {LIMITS[setting_name]}.")
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
                
                # Check proper villain count
                if self.game.settings["villaincount"] <= 0 or self.game.settings["villaincount"] >= len(self.game.player_list):
                    await self.game.player_list[0].send_message("Cannot start game until the number of villains has been set to a number larger than 0 and smaller than the player count."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}, and the number of villains is {self.game.settings['villaincount']}."
                                                                + "\n" + "Declare the number of villains using the format `$villaincount #`, where `#` is the desired number of villains.")
                    return
                
                # Proceed to Night game state
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
        Changes the Game's game state to Night
        Assigns a role to each player
        '''

        # Get keyword
        self.game.keyword = self.get_random_word()

        # Randomized list of players for role assignment
        temp_player_list = self.game.player_list.copy()
        random.shuffle(temp_player_list)
        self.game.role_dict = {}

        # Assign Sheriff
        ply_ind = 0
        self.game.role_dict["Sheriff"] = [temp_player_list[ply_ind]]
        temp_player_list[0].role = await pr.RoleSheriff.initialize(temp_player_list[0])

        # Assign Civilians
        ply_ind += 1
        self.game.role_dict["Civilian"] = []
        for _ in range(1, len(self.game.player_list) - self.game.settings["villaincount"]):
            self.game.role_dict["Civilian"].append(temp_player_list[ply_ind])
            temp_player_list[ply_ind].role = await pr.RoleCivilian.initialize(temp_player_list[ply_ind])
            ply_ind += 1
        
        # Assign Mastermind
        self.game.role_dict["Mastermind"] = [temp_player_list[ply_ind]]
        temp_player_list[ply_ind].role = await pr.RoleMastermind.initialize(temp_player_list[ply_ind])
        
        # Assign Villains
        ply_ind += 1
        for _ in range(1, self.game.settings["villaincount"]):
            self.game.role_dict["Villain"] = temp_player_list[ply_ind]
            temp_player_list[ply_ind].role = await pr.RoleVillain.initialize(temp_player_list[ply_ind])
            ply_ind += 1

        # Move to Questioning phase
        self.game.gamestate = await GameStateQuestion.initialize(self.game)
        return
    
    def get_random_word(self):
        with open("pictionary_words.txt") as f:
            words = f.readlines()
        return random.choice(words)

class GameStateQuestion(GameState):
    '''
    Questioning phase. Players take turns questioning the WITNESS about the keyword.
    '''

    previous_guess_time = None

    async def initialize(game):
        '''
        RETURNS this intialized GameState object
        INPUT
            game; Game object
        '''
        self = await GameState.initialize_helper(game, GameStateQuestion())
        self.time_limit = self.game.settings["questiondur"]
        self.phase_end_message = f"**The Questioning phase's time limit ({self.time_limit} sec) has been reached before anyone guessed the keyword. The current Questioner must attempt to guess the keyword!**"
        for ply in self.game.player_list:
            await ply.role.question_action()
        self.previous_guess_time = time()
        return self
    
    async def proceed(self):
        '''
        Changes the Game's game state to Guess
        '''
        self.game.gamestate = await GameStateGuess.initialize(self.game)

    async def handle_message(self, message):
        await super().handle_message(message)

        if message.author.id == self.game.get_questioner().user.id:

            # If $readytoguess, end questioning early
            if message.content == "$readytoguess":
                await self.game.send_global_message("The Questioner has elected to end questioning early!")
                await self.game.gamestate.proceed()
                return

            # Ask the question
            split_msg = message.split()
            if len(split_msg) == 2 and split_msg[0] == "$ask":
                
                # Check for question frequency cooldown
                if time() - self.previous_guess_time < LIMITS["questioncooldown"]:
                    await self.game.get_questioner().send_message(f"You're asking questions too quickly! Wait {LIMITS['questioncooldown']} seconds between questions.")
                    return
                
                # Check for proper question length
                if len(split_msg[1]) > self.game.settings["questioncharlimit"]:
                    await self.game.get_questioner().send_message(f"Your question must be fewer than {self.game.settings['questioncharlimit']} characters. Your question was {len(split_msg[1])} characters.")
                    return

                # Record question and answer
                # self.game.gpt_witness.witness_questions.append(split_msg[1])
                witness_response = self.game.gpt_witness.ask(split_msg[1])
                witness_words = witness_response.split()
                # self.game.gpt_witness.witness_responses.append(self.game.get_questioner().user.name + ": " + witness_response)
                self.previous_guess_time = time()

                # Shuffle response and distribute clues to players
                random.shuffle(witness_words)
                if "Censorer" in self.game.powers.keys():
                    if len(self.game.player_list) > len(witness_words):
                        split_response = witness_words[:len(self.game.player_list)]
                    await self.game.send_global_message("The villainous **Censorer** has muddled the WITNESS response! Everyone only observes one word this round.")
                    self.game.powers.remove("censorer")
                else:
                    split_response = np.array_split(np.array(witness_words), len(self.game.player_list))
                for ply in self.game.player_list:
                    observed_words = split_response.pop()
                    msg = f"`{self.game.get_questioner().user.name}` questioned the WITNESS."
                    msg += "\n"
                    msg += "You observed the following words."
                    for word in observed_words:
                        msg += f"\n\t**{word}**"
                    msg += "\n" + f"There are {math.floor(self.game.gamestate.time_limit - time() + self.game.gamestate.start)} of {self.game.gamestate.time_limit} seconds remaining."
                    await ply.send_message(msg)    
                self.game.questioner = (self.game.questioner + 1) % len(self.game.player_list)
                await self.send_questioner_instructions()   
                self.game.powers = {}     
                return
            
    async def send_questioner_instructions(self):
        await self.game.send_global_message(f"`{self.game.get_quetioner().user.name}` is the Questioner!")
        await self.game.get_questioner().send_message("Use `$ask <question text>` to ask the WITNESS a question.")
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
        self.phase_end_message = f"**The Guess phase's time limit ({self.time_limit} sec) has been reached! The Questioner didn't submit a guess in time. Civilians' only recourse is to capture a Villain!**"
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
        await super().handle_message(message)

        split_msg = message.split()
        if split_msg[0] == "$guess":
            
            guess = split_msg[1].lower()

            # Check if guess has same number of words as keyword
            if len(guess.split()) != len(self.game.keyword.split()):
                await self.game.get_questioner().send_message(f"Your guess for the keyword contained {len(guess.split())} word(s), but the keyword is made of {len(self.game.keyword.split())} word(s) (separated by spaces).")
                return
            
            # Check if guess and keyword have the same English roots (stems). If so, then correct.
            await self.game.send_global_message(f"Questioner {self.game.get_questioner().user.name} guessed **{guess}**. The correct keyword is **{self.game.keyword}**.")
            stemmer = SnowballStemmer("english")
            guess_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                            for word in guess.split()]
            true_stems = [stemmer.stem(re.sub(r'[^a-zA-Z]', '', word.lower()))
                            for word in self.game.keyword.split()]
            if guess_stems == true_stems:
                await self.game.send_global_message(":white_check_mark: The Sheriff guessed **correctly**. The Civilians win!")
                await self.game.gamestate.proceed(go_to_trial=False)
            else:
                await self.game.send_global_message(":no_entry_sign: The Sheriff was **wrong**. The Villains gain the upper hand!")
                await self.game.gamestate.proceed(go_to_trial=True)
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
        self.phase_end_message = f"**The Trial phase's time limit ({self.time_limit} sec) has been reached! If you didn't vote or failed to submit a Trial phase task, your submission will be ignored.**"
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
        Handles the player votes
        INPUT
            message; Discord Message object whose content the suspect player that is being voted for
        '''
        await super().handle_message(message)

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



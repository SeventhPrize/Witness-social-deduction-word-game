from time import time
import math
import random
import player_roles as pr

class GameState:
    
    game = None
    start = None
    time_limit = None
    phase_end_message = None

    async def initialize(game):
        return await GameState.initialize_helper(game, GameState())

    async def initialize_helper(game, gamestate_instance):
        self = gamestate_instance
        self.game = game
        self.start = time()
        self.time_limit = 3600
        self.phase_end_message = f"**This phase's time limit ({math.floor(self.time_limit)} sec) has been reached! If you had a task but did not submit an entry, your task will be ignored.**"
        return self

    async def handle_message(self, message):
        if time() - self.start > self.time_limit:
            self.game.send_global_message(self.phase_end_message)
            await self.proceed()
            return
        for ply in self.game.player_list:
            if message.author.id == ply.user.id:
                await ply.handle_message(message)
                return
            
    async def conclude(self):

        await self.game.send_global_message("Here is everyone's role for this game:"
                                            + "".join([f"\n`{ply.user.name}` \t {ply.role.title}"
                                                       for ply in self.game.player_list]))

        await self.game.send_global_message("Here are the WITNESS prompts and responses:"
                                            + "".join([f"\n*{self.game.witness_questions[ind]}* \n{self.game.witness_responses[ind]}"
                                                     for ind in range(len(self.game.witness_questions))]))

        await self.game.send_global_message("The Mastermind banned the following words from the WITNESS's vocabulary: "
                                            + ", ".join(self.game.gpt_witness.banned_words))

        await self.game.send_global_message("Thanks for playing this trial version of **Witness: The Social Deduction Word Game**. Starting new game . . .")
        self.game.gamestate = await GameStateCreation.initialize(self.game)
        await self.game.send_game_creation_message()
        return

    async def proceed(self):
        pass

class GameStateCreation(GameState):

    async def initialize(game):
        return await GameState.initialize_helper(game, GameStateCreation())

    async def handle_message(self, message):

        # if host sent the message
        if message.author.id == self.game.player_list[0].user.id:
            split_msg = message.content.strip().split()
            if split_msg[0] == "$villaincount":
                if len(split_msg) == 2 and split_msg[1].isdigit():
                    found_int = int(split_msg[1])
                    self.game.villain_count = found_int
                    await self.game.send_global_message(f"Game host set number of villains to {found_int}.")
                    return
                else:
                    await self.game.player_list[0].send_message("Invalid command. Declare the number of villains using the format `$villaincount #`, where `#` is the desired number of villains.")
                    return
            if split_msg[0] == "$start":
                if len(self.game.player_list) < 2 or len(self.game.player_list) > 12:
                    await self.game.player_list[0].send_message("Cannot start game with fewer than 2 players or more than 12 players."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}.")
                    return
                if self.game.villain_count <= 0 or self.game.villain_count >= len(self.game.player_list):
                    await self.game.player_list[0].send_message("Cannot start game until the number of villains has been set to a number larger than 0 and smaller than the player count."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}, and the number of villains is {self.game.villain_count}."
                                                                + "\n" + "Declare the number of villains using the format `$villaincount #`, where `#` is the desired number of villains.")
                    return
                await self.proceed()
                return
                
    async def proceed(self):

        temp_player_list = self.game.player_list.copy()
        random.shuffle(temp_player_list)

        ply_ind = 0
        
        temp_player_list[0].role = await pr.RoleSheriff.initialize(temp_player_list[0])
        self.game.sheriff_player = temp_player_list[0]
        ply_ind += 1
        for _ in range(1, len(self.game.player_list) - self.game.villain_count):
            temp_player_list[ply_ind].role = await pr.RoleCivilian.initialize(temp_player_list[ply_ind])
            ply_ind += 1
        
        temp_player_list[ply_ind].role = await pr.RoleMastermind.initialize(temp_player_list[ply_ind])
        ply_ind += 1
        for _ in range(1, self.game.villain_count):
            temp_player_list[ply_ind].role = await pr.RoleVillain.initialize(temp_player_list[ply_ind])
            ply_ind += 1

        self.game.gpt_witness.n_words = 2 * len(self.game.player_list)

        self.game.gamestate = await GameStateNight.initialize(self.game)
        return
        
class GameStateNight(GameState):
    
    async def initialize(game):
        self = await GameState.initialize_helper(game, GameStateNight())
        self.time_limit = 60
        self.phase_end_message = f"**The Night phase's time limit ({self.time_limit} sec) has been reached! If you had a Night task and did not submit an entry, then your task will be ignored.**"
        for ply in self.game.player_list:
            await ply.role.night_action()
        return self

    async def proceed(self):
        self.game.gamestate = await GameStateDay.initialize(self.game)

class GameStateDay(GameState):

    async def initialize(game):
        self = await GameState.initialize_helper(game, GameStateDay())
        self.time_limit = 300
        self.phase_end_message = f"**The Day phase's time limit ({self.time_limit} sec) has been reached! It's time to guess the keyword!**"
        for ply in self.game.player_list:
            await ply.role.daily_action()
        return self
    
    async def proceed(self):
        self.game.gamestate = await GameStateGuess.initialize(self.game)

class GameStateGuess(GameState):

    async def initialize(game):
        self = await GameState.initialize_helper(game, GameStateGuess())
        self.time_limit = 90
        self.phase_end_message = f"**The Guess phase's time limit ({self.time_limit} sec) has been reached! The Sheriff didn't submit a guess in time. Your only recourse now is to capture a Villain!**"
        for ply in self.game.player_list:
            await ply.role.guess_action()
        return self
    
    async def proceed(self, go_to_trial=True):
        if go_to_trial:
            self.game.gamestate = await GameStateTrial.initialize(self.game)
        else:
            await self.conclude()

class GameStateTrial(GameState):

    votes = None

    async def initialize(game):
        self = await GameState.initialize_helper(game, GameStateTrial())
        self.round_counter = 0
        self.time_limit = 90
        self.votes = {}
        self.phase_end_message = f"**The Trial phase's time limit ({self.time_limit} sec) has been reached! If you didn't vote or failed to submit a Trial phase task, your submission will be ignored.**"
        suspects = [f"\n`{ply.user.name}`" for ply in self.game.player_list]
        await self.game.send_global_message(f"Everyone has {self.time_limit} seconds to vote for a player to convict. The Civilians win if the player with/tied for the most votes is a Villain. You can vote exactly once. You can change your vote as long as the time limit has not been reached and at least one player has not voted. Type (or copy/paste) the name of the player you want to vote for:" + "".join(suspects))
        for ply in self.game.player_list:
            await ply.role.trial_action()
        return self
    
    async def proceed(self):

        vote_dict = {}
        for accuser in self.votes.keys():
            suspect = self.votes[accuser]
            if suspect is not None:
                if suspect not in vote_dict.keys():
                    vote_dict[suspect] = [accuser]
                else:
                    vote_dict[suspect].append(accuser)

        msg = "Here is the final vote tally:"
        for key in vote_dict.keys():
            msg += (f"\n`{key}` was suspected by "
                    + ", ".join([f"`{accusers}`"
                                 for accusers in vote_dict[key]]))
        await self.game.send_global_message(msg)
        
        max_votes = max([len(accusers) for accusers in vote_dict.values()])
        convicted = [suspect for suspect in vote_dict.keys() if len(vote_dict[key]) == max_votes]

        await self.game.send_global_message("The following players were convicted: "
                                            + ", ".join([f"`{suspect}`"
                                                         for suspect in convicted]))

        guilty = set(convicted).intersection([ply.user.name for ply in self.game.player_list
                                              if isinstance(ply.role, pr.RoleVillain)])
        if guilty:
            await self.game.send_global_message("Guilty! Congratulations, Civilians! The following Villains were convicted: "
                                                + ", ".join([f"`{suspect}`" for suspect in guilty]))
        else:
            await self.game.send_global_message("Congratulations, Villains! You have escaped justice.")

        await self.conclude()
    
    async def handle_message(self, message):
        await super().handle_message(message)
        for accuser in self.game.player_list:
            if accuser.user.name == message.author.name:
                if message.content in [suspect.user.name for suspect in self.game.player_list]:
                    self.votes[accuser.user.name] = message.content
                    await accuser.send_message(f"You voted for `{message.content}`.")
                    if len(self.votes.keys()) == len(self.game.player_list):
                        await self.proceed()
                    return



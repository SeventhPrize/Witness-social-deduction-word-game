from time import time
import random
import player_roles as pr

class GameState:
    
    game = None
    start = None

    async def initialize(game):
        return await GameState.initialize_helper(game, GameState())

    async def initialize_helper(game, gamestate_instance):
        self = gamestate_instance
        self.game = game
        self.start = time()
        return self

    async def handle_message(self, message):
        for ply in self.game.player_list:
            if message.author.id == ply.user.id:
                await ply.handle_message(message)
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

        for ply in self.game.player_list:
            await ply.role.night_action()

        return
        
class GameStateNight(GameState):
    
    async def initialize(game):
        return await GameState.initialize_helper(game, GameStateNight())
    
    async def proceed(self):
        self.game.gamestate = await GameStateDay.initialize(self.game)

        for ply in self.game.player_list:
            await ply.role.daily_action()

class GameStateDay(GameState):

    round_counter = None
    time_limit = None

    async def initialize(game):
        self = await GameState.initialize_helper(game, GameStateDay())
        self.round_counter = 0
        self.time_limit = 300
        return self
    
    async def proceed(self):
        self.game.gamestate = await GameStateGuess.initialize(self.game)

        for ply in self.game.player_list:
            await ply.role.guess_action()

class GameStateGuess(GameState):
    pass

class GameStateTrial(GameState):
    pass

    



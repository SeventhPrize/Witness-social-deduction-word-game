"""
Contains Game and Player classes for Witness gameplay.
"""

import discord
import random
import deprecated.gamestates as gs
import player_roles as pr

class Game:
    '''
    Encapsulates methods and attributes for a single Witness game.
    '''
    category = None         # The discord category that hosts this game
    registration_msg = None # The discord message that users react to to register for this game 
    keyword = None          # The keyword for this game
    player_list = None      # List of players  
    questioner = None       # Index of the player who is the current questioner
    role_dict = None        # Dictionary mapping a string title of each role to the list of players with that role
    gamestate = None        # The GameState object describing the phase of the game
    gpt_witness = None      # The GptWitness object that provides the WITNESS clues
    settings = None         # Dictionary mapping a string name for each game setting to its natural number value
    powers = {}

    async def initialize(trigger_msg):
        '''
        RETURNS this initialized Game object.
        '''
        self = Game()

        # Create game category
        self.category = await trigger_msg.guild.create_category("Witness-" + str(random.randint(1000, 9999)))
        
        # Create registration message
        self.registration_msg = await trigger_msg.channel.send(f"React to this message to play Witness: Social Deduction Word Game. After reacting, check category `{self.category}` for your private channel. Up to 12 players may join.")
        await self.registration_msg.add_reaction("\N{THUMBS UP SIGN}")
        
        # Initialize settings and parameters
        self.player_list = []
        self.default_settings()

        # Set the game host as the user who sent the "$play" message
        await self.add_player(trigger_msg.author)
        await self.send_game_creation_message()

        # Start the Creation gamestate
        self.gamestate = await gs.GameStateCreation.initialize(self)
        return self
    
    def default_settings(self):
        '''
        Sets this game's self.settings to the default settings
        '''
        self.settings = {}
        self.settings["specialroles"] = []          # Special player roles
        self.settings["villaincount"] = 1           # Number of villain players
        self.settings["numbannedwords"] = 3         # Number of words the Mastermind bans from WITNESS vocabulary
        self.settings["questiondur"] = 60           # Seconds duration of the Night phase
        self.settings["trialdur"] = 300             # Seconds duration of the Day phase
        self.settings["wordsperplayer"] = 2         # Target number of words that each player observes from each WITNESS response
        self.settings["questioncharlimit"] = 100    # Maximum character length of Sheriff's questions to the WITNESS

    async def print_settings(self, ply):
        '''
        Sends a discord message to the given player that summarizes the game's current settings
        INPUT
            ply; Player object for the player to send the game settings summary to 
        '''
        await ply.send_message("\n".join([(f"{param} \t {val}")
                                                  for param, val in self.settings.items()]))
        if ply.user.id == self.player_list[0].user.id:
            await ply.send_message("`$role <roletitle> <add/remove>` adds/removes a special role to the game."
                                    + "\n`$<settingname> <settingvalue>` changes a specific setting."
                                    + "\n`$resetdefaultsettings` resets to defaults.")

    async def add_player(self, user):
        '''
        Adds the given user as a player to this game
        INPUT
            user; Discord User object to add as a plyaer
        RETURNS
            the Player object for the given user
        '''
        player = await Player.initialize(user, self)
        self.player_list.append(player)
        await self.send_global_message(f"`{user.name}` joined the game! There are now {len(self.player_list)} players.")
        return player
    
    async def send_game_creation_message(self):
        '''
        Sends the game creation message to the game host.
        '''
        await self.player_list[0].send_message("**You are the game host. Use `$showsettings` to change settings. Use `$start` to start the game.**")
        return

    async def send_global_message(self, content):
        '''
        Sends the given message to all players.
        INPUT
            content; string message to send to all players
        '''
        for player in self.player_list:
            await player.send_message(content)
        return

    async def get_questioner(self):
        if self.questioner is None:
            return None
        else:
            return self.player_list[self.questioner]

    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object to handle
        '''
        # If $showsettings, sends message to author summarizing game settings
        if message.content == "$showsettings":
            for ply in self.player_list:
                if ply.user.id == message.author.id:
                    await self.print_settings(ply)
                    return
        
        # If $resetdefaultsettings, resets the default settings
        if message.content == "$resetdefaultsettings" and message.author.id == self.player_list[0].user.id:
            self.default_settings()
            await self.send_global_message("Game host reset settings to defaults.")
       
        # If $restartgame, restarts game
        if message.content == "$restartgame" and message.author.id == self.player_list[0].user.id:
            await self.gamestate.conclude()
        
        # Otherwise, let the GameState handle the message
        await self.gamestate.handle_message(message)

    async def activate_power(self, title, value):
        self.powers[title] = value
        for ply in self.player_list:
            if isinstance(ply.role, pr.Reporter):
                ply.send_message("**ALERT**\tSomeone activated their power!")

class Player:
    '''
    Encapsulates methods and attributes for game players
    '''
    user = None     # This player's Discord User object
    game = None     # The game object
    channel = None  # This player's dedicated Discord channel for this game
    role = None     # This player's role

    async def initialize(user, game):
        '''
        RETURNS this intialized Player object
        INPUT
            game; the Game object this Player is playing
        '''
        self = Player()
        self.user = user
        self.game = game
        self.role = None
        self.channel = await self.create_private_channel(user)
        await self.send_message("Welcome to **Witness: The Social Deducation Word Game**, powered by **GPT-3.5 Turbo** and written by @SeventhPrize!"
                                + "\n:supervillain: A heinous crime has upset the city. It's up to you to find the villains and restore the peace!"
                                + "\n:key: A secret keyword will be chosen by when the game begins. The Civilians want to figure out the keyword by the end of the game. The Villains, who know the keyword, want to keep the keyword a secret by misleading the Civilians."
                                + "\n:oncoming_police_car: The Sheriff will ask the WITNESS a series of open-ended questions to find clues about the keyword. The WITNESS's responses will scattered and shuffled among all the players, so everyone must collaborate to piece together the WITNESS's responses."
                                + "\n:mag: The devious Mastermind will attempt to trick the Civilians by banning words from the WITNESS's vocabulary, making the truth even harder to discern."
                                + "\n:ballot_box: But if the Villains may fall if they are too obvious with their tricks--at the end of the game, everyone will vote for a player they suspect to be a Villain. If a Villain receives the most votes, the Villains lose!"
                                + "\n:person_in_tuxedo: The Villains win if they stop the Sheriff from finding out the keyword AND no Villain is convicted."
                                + "\n\n:no_entry_sign: This channel is your dedicated communication method for this game. You may not direct-message other players, use admin privileges to view other players' channels, or otherwise use other players' information.")
        return self

    async def create_private_channel(self, user):
        '''
        Creates this player's dedicated private gameplay channel
        INPUT
            user; this player's the Discord User object
        '''
        # Channel should be private to the player
        overwrites = {
            self.game.category.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True),
            self.game.category.guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        # Make channel
        channel = await self.game.category.create_text_channel(user.name, overwrites=overwrites)
        return channel
    
    async def send_message(self, content):
        '''
        Sends given message to the player as a Discord message on their private channel
        INPUT
            content; string message to send to the player
        '''
        await self.channel.send(content) 
        return
    
    async def handle_message(self, message):
        '''
        Handles the input message
        INPUT
            message; Discord Message object
        '''
        return await self.role.handle_message(message)

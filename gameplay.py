"""
Contains Game and Player classes for Witness gameplay.
"""

import discord
import random
import gamestates as gs

class Game:
    '''
    Encapsulates methods and attributes for a single Witness game.
    '''
    category = None         # The discord category that hosts this game
    registration_msg = None # The discord message that users react to to register for this game 
    keyword = None          # The keyword for this game
    player_list = None      # List of players  
    role_dict = None        # Dictionary mapping a string title of each role to the list of players with that role
    gamestate = None        # The GameState object describing the phase of the game
    gpt_witness = None      # The GptWitness object that provides the WITNESS clues
    settings = None         # Dictionary mapping a string name for each game setting to its natural number value

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
        self.keyword = self.get_keyword()
        self.player_list = []
        self.default_settings()

        # Set the game host as the user who sent the "$play" message
        await self.add_player(trigger_msg.author)
        await self.send_game_creation_message()

        # Start the Creation gamestate
        self.gamestate = await gs.GameStateCreation.initialize(self)
        return self
    
    def get_keyword(self):
        '''
        RETURNS the keyword for this game 
        '''
        return "TEST"

    def default_settings(self):
        '''
        Sets this game's self.settings to the default settings
        '''
        self.settings = {}
        self.settings["villaincount"] = 1   # Number of villain players
        self.settings["numbannedwords"] = 5 # Number of words the Mastermind bans from WITNESS vocabulary
        self.settings["nightdur"] = 60      # Seconds duration of the Night phase
        self.settings["daydur"] = 300       # Seconds duration of the Day phase
        self.settings["guessdur"] = 90      # Seconds duration of the Guess phase
        self.settings["trialdur"] = 90      # Seconds duration of the Trial phase
        self.settings["wordsperplayer"] = 2 # Number of words that each player observes from each WITNESS response
        self.settings["questioncharlimit"] = 100 # Maximum character length of Sheriff's questions to the WITNESS

    async def print_settings(self, ply):
        '''
        Sends a discord message to the given player that summarizes the game's current settings
        INPUT
            ply; Player object for the player to send the game settings summary to 
        '''
        await ply.send_message("\n".join([(f"{param} \t {val}")
                                                  for param, val in self.settings.items()])
                                        + "\n`$resetdefaultsettings` will reset to defaults")

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
        return player
    
    async def send_game_creation_message(self):
        '''
        Sends the game creation message to the game host.
        '''
        await self.player_list[0].send_message("[CREATION MENU HERE]")
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
        if message.content == "$resetdefaultsettings":
            self.default_settings()
            await self.send_global_message("Game host reset settings to defaults.")
        
        # Otherwise, let the GameState handle the message
        await self.gamestate.handle_message(message)

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
        await self.send_message("[RULES HERE]")
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

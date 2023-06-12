import discord
import os
import asyncio
import random
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)

game_list = []

@client.event
async def on_ready():
    print('DISCORD BOT logged in as {0.user}.'.format(client))

@client.event
async def on_message(message):

    if message.author.id == client.user.id:
        return

    if message.content == "$hello":
        await message.channel.send("Hello!")
        return

    if message.content == "$play":
        category = await message.guild.create_category("Witness-" + str(random.randint(1000, 9999)))
        registration_msg = await message.channel.send(f"React to this message to play Witness: Social Deduction Word Game. After reacting, check category `{category}` for your private channel.")
        new_game = await Game.initialize(category, registration_msg, message.author)
        game_list.append(new_game)
        return
    
    if message.content == "$prune":
        for category in message.guild.categories:
            if category.name.startswith("Witness-"):
                for channel in category.channels:
                    await channel.delete()
                await category.delete()
        return

    for game in game_list:
        if message.channel.category.id == game.category.id:
            await game.handle_message(message)
            return

@client.event
async def on_reaction_add(reaction, user):
    for game in game_list:
        if reaction.message.id == game.registration_msg.id:
            if user not in [player.user for player in game.player_list]:
                await game.add_player(user)
                return
            
class Game:
    category = None
    registration_msg = None
    player_list = None
    villain_count = None
    gamestate = None

    async def initialize(category, registration_msg, creator):
        self = Game()
        self.category = category
        self.registration_msg = registration_msg
        self.player_list = []
        self.villain_count = 1
        await self.add_player(creator)
        await self.send_game_creation_message()
        self.gamestate = await GameStateCreation.initialize(self)
        return self

    async def add_player(self, user):
        player = await Player.initialize(user, self.category)
        self.player_list.append(player)
        return player
    
    async def send_game_creation_message(self):
        await self.player_list[0].send_message("[CREATION MENU HERE]")
        return

    async def send_global_message(self, content):
        for player in self.player_list:
            await player.send_message(content)
        return

    async def handle_message(self, message):
        await self.gamestate.handle_message(message)

class Player:
    user = None
    category = None
    channel = None
    role = None

    async def initialize(user, category):
        self = Player()
        self.user = user
        self.category = category
        self.role = None
        self.channel = await self.create_private_channel(user)
        await self.send_message("[RULES HERE]")
        return self

    async def create_private_channel(self, user):
        overwrites = {
            self.category.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True),
            self.category.guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        channel = await self.category.create_text_channel(user.name, overwrites=overwrites)
        return channel
    
    async def send_message(self, content):
        await self.channel.send(content) 
        return
    
class GameState:
    
    game = None

    async def initialize(game):
        self = GameState()
        self.game = game
        return self

    async def handle_message(self, message):
        pass

class GameStateCreation(GameState):

    async def initialize(game):
        self = GameStateCreation()
        self.game = game
        return self

    async def handle_message(self, message):
        split_message = message.content.strip().split()

        # if host sent the message
        if message.author.id == self.game.player_list[0].user.id:
            if split_message[0] == "$villaincount":
                if len(split_message) == 2 and split_message[1].isdigit():
                    found_int = int(split_message[1])
                    self.game.villain_count = found_int
                    await self.game.send_global_message(f"Game host set number of villains to {found_int}.")
                else:
                    await self.game.player_list[0].send_message("Declare the number of villains using the format `$villaincount #`, where `#` is the desired number of villains.")
                return
            if split_message[0] == "$start":
                if self.game.villain_count <= 0 or self.game.villain_count >= len(self.game.player_list):
                    await self.game.player_list[0].send_message("Cannot start game until the number of villains has been set to a number larger than 0 and smaller than the player count."
                                                                + "\n" + f"The current number of players is {len(self.game.player_list)}, and the number of villains is {self.game.villain_count}."
                                                                + "\n" + "Declare the number of villains using the format `$villaincount #`, where `#` is the desired number of villains.")
                else:
                    self.game.gamestate = await GameStateNight.initialize(self.game)       
        else:
            pass

class GameStateNight(GameState):
    
    async def intialize(game):
        self = GameStateNight()
        self.game = game
        return self
    
    async def handle_message(self, message):
        return await super().handle_message(message)

load_dotenv()  # take environment variables from .env.
client.run(os.getenv('DISCORD_TOKEN'))
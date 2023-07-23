import discord
import os
import random
import gamestates as gs
import gpt_responder as gptr
from time import time
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
        game_list.append(await Game.initialize(message))
        return
    
    if message.content == "$prune":
        category_counter = 0
        channel_counter = 0
        for category in message.guild.categories:
            if category.name.startswith("Witness-"):
                for channel in category.channels:
                    channel_counter += 1
                    await channel.delete()
                category_counter += 1
                await category.delete()
        # await message.channel.send(f"Pruned {category_counter} categories containing {channel_counter} channels.")
        return

    for game in game_list:
        if message.channel.category.id == game.category.id:
            await game.handle_message(message)
            return

@client.event
async def on_reaction_add(reaction, user):
    if user == client.user.id:
        return

    for game in game_list:
        if reaction.message.id == game.registration_msg.id:
            if user not in [player.user for player in game.player_list]:
                await game.add_player(user)
                return
            
class Game:
    category = None
    registration_msg = None
    keyword = None
    player_list = None
    n_words_per_player = None
    villain_count = None
    gamestate = None
    gpt_witness = None

    witness_questions = None
    witness_responses = None

    async def initialize(trigger_msg):
        self = Game()
        self.category = await trigger_msg.guild.create_category("Witness-" + str(random.randint(1000, 9999)))
        self.registration_msg = await trigger_msg.channel.send(f"React to this message to play Witness: Social Deduction Word Game. After reacting, check category `{self.category}` for your private channel.")
        await self.registration_msg.add_reaction("\N{THUMBS UP SIGN}")
        self.gpt_witness = gptr.GptWitness()
        self.keyword = "TEST"
        self.player_list = []
        self.n_words_per_player = 2
        self.villain_count = 1
        self.witness_questions = []
        self.witness_responses = []
        await self.add_player(trigger_msg.author)
        await self.send_game_creation_message()
        self.gamestate = await gs.GameStateCreation.initialize(self)
        return self

    async def add_player(self, user):
        player = await Player.initialize(user, self)
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

class GameSettings:
    pass

class Player:
    user = None
    game = None
    channel = None
    role = None

    async def initialize(user, game):
        self = Player()
        self.user = user
        self.game = game
        self.role = None
        self.channel = await self.create_private_channel(user)
        await self.send_message("[RULES HERE]")
        return self

    async def create_private_channel(self, user):
        overwrites = {
            self.game.category.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True),
            self.game.category.guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        channel = await self.game.category.create_text_channel(user.name, overwrites=overwrites)
        return channel
    
    async def send_message(self, content):
        await self.channel.send(content) 
        return
    
    async def handle_message(self, message):
        return await self.role.handle_message(message)
    
load_dotenv()  # take environment variables from .env.
client.run(os.getenv('DISCORD_TOKEN'))
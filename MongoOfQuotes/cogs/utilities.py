import discord
import json
import os
import discord.utils
import time
import logging
import sys
import arrow
import subprocess

from discord.ext import commands
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi


if not os.path.isfile(f"{os.getcwd()}/config.json"):
    sys.exit("'config.json' not found! Please add it and try again.")
else: 
    with open(f"{os.getcwd()}/config.json") as file: 
        config = json.load(file)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)



'''
class QuoteManager for commands.Cog (standard cog class)
'''
class Utilities(commands.Cog):
    def __init__(self, bot):
        self.bot = bot   


    ''' 
    standard discord events (commands) 
    '''
    @commands.is_owner()
    @commands.command(brief="Sends a message through the bot.")
    async def send(self, ctx, channel_id:int, *, message):
        # delte the message send by the user
        await ctx.message.delete()

        try:
            # setup discord variables
            channel = self.bot.get_channel(channel_id)

            # send message to channel
            await channel.send(message)
        except:
            # send error message in original channel
            await ctx.send("Please provide a valid channel id to send the message to.", delete_after=10)


    @commands.is_owner()
    @commands.command(brief="Duplicate a category with all its channels.")
    async def duplicate_category(self, ctx, category_id:int):
        guild = ctx.message.guild
        category = self.bot.get_channel(category_id)
 

        new_category = await guild.create_category(category.name)

        for channel in category.channels:
            await new_category.create_text_channel(channel.name)

    
    @commands.is_owner()
    @commands.command()
    async def sh(self, ctx, *, args):
        pass
        


# setup function to add cog to bot
async def setup(bot):
    await bot.add_cog(Utilities(bot))
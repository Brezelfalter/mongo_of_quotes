import discord
import json
import os
import discord.utils
import time
import logging
import sys
import arrow
import random
import datetime 
import asyncio

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
class QuoteOfTheDay for commands.Cog (standard cog class)
'''
class QuoteOfTheDay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot   


    ''' 
    standard discord events (commands) 
    '''
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.daily_quote_task())


    '''
    functions used for standard discord events
    '''
    # FUNCTIONS FOR "on_ready" (daily_task)
    async def daily_quote_task(self):
        # repeat this everytime the sleep timer is up
        while True:
            # get a random quote from db
            quote = await self.get_random_quote()

            # return if there was an error while getting quote
            if quote == True: return

            # create an embed to send 
            embed = await self.create_embed(quote)

            # setup discord variables
            channel = self.bot.get_channel(config["quote_of_the_day"]["channel_id"])
            msg_edit = [message async for message in channel.history(limit=1)]

            # try editing the message, except send a new one 
            try: await msg_edit[0].edit(embed=embed) 
            except: await channel.send(embed=embed)

            # logging 
            self.bot.logger.info(f"Daily quote has been created.")

            # get current date and until midnight
            date = datetime.datetime.today()
            await self.sleepUntil(date.year, date.month, date.day, 0, 0, 0)


    async def get_random_quote(self):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # get all names of collections
        collections = db.list_collection_names()

        # setup a list to save all quotes to
        quotes_list = []

        # iterate over all names of collections and add all values of quotes from each document to a list 
        for coll_name in collections:
            if coll_name in config["quote_of_the_day"]["blocked_collections"]: continue # block the collections from the config file

            # set collection and get all values of "quote" from each document
            coll = db[coll_name]
            values = coll.distinct("quote")

            # append all values in the values list to the main quotes list 
            for value in values: quotes_list.append(value)
        
        # shuffle the list so values from one collection are not next to each other
        random.shuffle(quotes_list)

        # choose a random quote
        if len(quotes_list) >= 1: random_quote = quotes_list[random.randint(0, (len(quotes_list)-1))]
        else: random_quote = True

        return random_quote
    

    async def create_embed(self, quote):
        # get timestamp in german time
        timestamp = arrow.now()
        timestamp_ger = timestamp.to("Europe/Berlin")
        timestamp_ger = timestamp_ger.format("DD.MM.YYYY HH:mm:ss")

        # create an embed
        embed = discord.Embed(
            title=f"Quote of the day ({timestamp_ger})",
            description=quote,
            color=discord.Color.greyple()
        )
        
        return embed


    async def sleepUntil(self, year, month, day, hour, minute, second):
        t = datetime.datetime.today()
        future = datetime.datetime(year, month, day, hour, minute, second)

        if t.timestamp() > future.timestamp():
            future += datetime.timedelta(days=1)

        await asyncio.sleep((future-t).total_seconds())



# setup function to add cog to bot
async def setup(bot):
    await bot.add_cog(QuoteOfTheDay(bot))
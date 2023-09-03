import discord
import json
import os
import discord.utils
import logging
import sys
import arrow

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
class QuoteStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot   


    '''
    standard discord events (commands) 
    '''
    @commands.Cog.listener()
    async def on_message(self, ctx):
        # only continue if message is not blocked by config file
        if ctx.channel.category_id not in config["quote_archiver"]["archive_categories"]: return
        else: await self.send_stats()

    
    '''
    functions used for standard discord events
    '''
    # FUNCTIONS USED IN "on_command"
    async def send_stats(self):
        # get the amount of quotes per channel and the total amount 
        quotes_per_channel, total_quotes = await self.get_amount_of_quotes()

        # create a dump to be sent to the channel 
        dump = await self.create_dump(quotes_per_channel, total_quotes)

        # get an earlier message in the channel
        channel = self.bot.get_channel(config["quote_stats"]["channel_id"])
        msg_edit = [message async for message in channel.history(limit=1)]

        # try to edit the message with new content, except send a new one
        try: await msg_edit[0].edit(content=dump) 
        except: await channel.send(dump)

        # logging 
        self.bot.logger.info(f"Quote stats have been updated.")


    async def get_amount_of_quotes(self):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # get all names of collections
        collections = db.list_collection_names()

        # setup a list to save all quotes to
        quotes_list = []
        quotes_per_channel = {}

        # iterate over all names of collections and add all values of quotes from each document to a list 
        for coll_name in collections:
            if coll_name in config["quote_stats"]["blocked_collections"]: continue # block the collections from the config file
            counter = 0

            # set collection and get all values of "quote" from each document
            coll = db[coll_name]
            values = coll.distinct("quote")

            # append all values in the values list to the main quotes list 
            for value in values: 
                quotes_list.append(value)
                counter += 1

            # set the quotes per channel in the dict
            quotes_per_channel[coll_name] = counter

        # sort channels from highest amount of quotes to lowest 
        quotes_per_channel = {k: v for k, v in sorted(quotes_per_channel.items(), key=lambda item: item[1], reverse=True)}

        return quotes_per_channel, len(quotes_list)
        

    async def create_dump(self, quotes_per_channel, total_quotes:int):
        # create the start of the dump 
        dump = f"{pad('Channel', 20)}{pad('Zitate (%)', 12)}Zitate\n"

        # iterate over all keys and their values in dict
        for k, v in quotes_per_channel.items():
            # calculate the percentage this channel has on the whole amount of quotes 
            percentage = (100 / total_quotes) * v

            # setup values to be formatted correctly in the dump
            key = pad(capitalize_channel_names(k), 20)
            percentage = pad(f"{str(percentage)[:4]}%", 12)
            value = v

            # add the newly created dump to the old one
            dump = f"{dump}{key}{percentage}{value}\n"

        # get timestamp in german time
        timestamp = arrow.now()
        timestamp_ger = timestamp.to("Europe/Berlin")
        timestamp_ger = timestamp_ger.format("DD.MM.YYYY HH:mm:ss")

        # add the end of the dump to the existing one
        dump = f"Zitatanteile (Stand: {timestamp_ger})\n```{dump}\n{pad('Total', 20)}{pad('100%', 12)}{total_quotes}```"
        
        return dump


    
'''
utilities
'''
def capitalize_channel_names(name):
    # split name at "-" and setup variable
    name = name.split("-")
    new_name = ""

    # iterate over elements of string and capitalize starting letters, then put it back together
    for i in name:
        i = i.capitalize()
        new_name = f"{new_name}{i}-"
    
    # remove the last "-"
    new_name = new_name[:-1]

    return new_name        


def pad(s, l=18):
    while len(s) < l:
        s += " "
    return s   



# setup function to add cog to bot
async def setup(bot):
    await bot.add_cog(QuoteStats(bot))
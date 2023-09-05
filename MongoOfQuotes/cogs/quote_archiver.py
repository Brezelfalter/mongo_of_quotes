import discord
import json
import os
import discord.utils
import time
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


class QuoteArchiver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.is_owner()
    @commands.command(brief="Archives a complete category with all its channels. \n\nUsage: `archive_category [category id]` \n\n'category id': the category id that should be archived.")
    async def archive_category(self, ctx, category_id:int):
        # check if category is on the list of archive categories
        # if yes, continue
        # if no, stop and give back an error
        if category_id not in config["quote_archiver"]["archive_categories"]: 
            await ctx.send("The category you are trying to archive is not on the list of categories to archive, please try again with a valid id.", delete_after=10)
            return
        
        # archive messages in channels in category
        await self.archive_messages_in_category(category_id)


    @commands.is_owner()
    @commands.command(brief="Archives a channel. \n\nUsage: `archive_channel [channel id]` \n\n'channel id': the channel id that should be archived.")
    async def archive_channel(self, ctx, channel_id:int):
        # setup discord variables 
        channel = self.bot.get_channel(channel_id)
        category_id = channel.category_id
        
        # check if category is on the list of archive categories
        # if yes, continue
        # if no, stop and give back an error
        if category_id not in config["quote_archiver"]["archive_categories"]: 
            await ctx.send("The channel you are trying to archive is not in a category which is on the list of categories to archive, please try again with a valid id.", delete_after=10)
            return
        
        # archive messages in channel
        await self.archive_messages_in_channel(channel_id)


    @commands.Cog.listener()
    async def on_message(self, msg):
        # check if message was send in one of the to be archived channels
        check = await self.check_archive(msg)
        if check == False: return

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        channel_name = msg.channel.name
        coll = db[channel_name]

        # create document for database
        insert_doc = {
            "quote": msg.content,
            "message_id": msg.id,
            "timestamp": msg.created_at
        }

        # push quote to database
        coll.insert_one(insert_doc)

        # logging 
        self.bot.logger.info(f"Archived quote by: {msg.author.name} (ID: {msg.author.id}) RAW: '{msg.content}'")

    
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        # setup discord variables
        msg_id = payload.message_id
        channel = self.bot.get_channel(payload.channel_id)
        msg = await channel.fetch_message(msg_id)

        # check if message is in a specified category
        check = await self.check_archive(msg)
        if not check: return

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        channel_name = channel.name
        coll = db[channel_name]

        # get datetime object from RawMessageUpdateEvent
        timestamp_obj = payload.data["timestamp"]
        timestamp_obj = arrow.get(timestamp_obj).datetime
        
        # define query to search for
        query = {
            "timestamp": timestamp_obj
        }

        # define the update for quote in database
        update_doc = {
            "$set": {
                "quote": payload.data["content"]
            }
        }

        # push update to database
        coll.update_one(query, update_doc)

        # logging 
        self.bot.logger.info(f"Edited already archived quote. RAW '{payload.data['content']}'")


    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        # setup discord variables
        channel = self.bot.get_channel(payload.channel_id)

        # check if channel id is in to be archived categories
        if channel.guild.id not in config["quote_archiver"]["archive_categories"]: return
 
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        channel_name = channel.name
        coll = db[channel_name]
        
        # define query to search for
        query = {
            "message_id": payload.message_id
        }

        # remove query from database
        coll.delete_one(query)
        
        # logging 
        self.bot.logger.info(f"Deleted quote. (ID: {payload.message_id})")


    async def check_archive(self, msg):
        # go through all categories from the config file, check if message channel is part of one of them
        # if yes, continue with the programm
        # if no, stop and ignore the message
        for category in config["quote_archiver"]["archive_categories"]:
            archive_category = self.bot.get_channel(category)
            check = False

            for channel in archive_category.channels:
                if str(msg.channel.name) == str(channel.name):
                    check = True
                    break

        return check
    

    async def archive_messages_in_category(self, category_id):
        category = self.bot.get_channel(category_id)

        for channel in category.text_channels:
            await self.archive_messages_in_channel(channel.id)


    async def archive_messages_in_channel(self, channel_id):
        # setup discord variables
        channel = self.bot.get_channel(channel_id)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        channel_name = channel.name
        coll = db[channel_name]

        # iterate over all messages in the channel and add them to db
        async for msg in channel.history(limit=None):
            # define query to search for
            query = {
                "message_id": msg.id
            }

            # search for query
            res = coll.find_one(query)

            # check for message_id in database
            # if not in db add the quote
            # if in db, skip quote
            if res == None:
                # create document for database
                insert_doc = {
                    "quote": msg.content,
                    "message_id": msg.id,
                    "timestamp": msg.created_at
                }

                # push quote to database 
                coll.insert_one(insert_doc)



async def setup(bot):
    await bot.add_cog(QuoteArchiver(bot))
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
logger.setLevel(logging.DEBUG)



'''
class QuoteManager for commands.Cog (standard cog class)
'''
class QuoteManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot   


    ''' 
    standard discord events (commands) 
    '''
    @commands.Cog.listener()
    async def on_message(self, msg):
        # setup discord variables 
        quote_channel = self.bot.get_channel(config["quote_manager"]["quote_channel_id"])
        quote_duplicate_channel = self.bot.get_channel(config["quote_manager"]["quote_duplicate_channel_id"])
        quote_review_channel = self.bot.get_channel(config["quote_manager"]["quote_review_channel_id"])

        # check if the original message send to the channel was send by the bot itself
        if str(msg.author) != str(self.bot.user):
            # check if message was send in the quote channel, if not do not continue
            if msg.channel.id != config["quote_manager"]["quote_channel_id"]:return

            # # duplicate quote to duplicate channel
            # duplicate_message = await self.duplicate_user_entry(quote_channel, quote_duplicate_channel, msg)

            # send review message to channel
            review_message = await self.send_review(quote_channel, quote_review_channel, msg)

            # add an entry to the database 
            await self.add_review_to_db(msg, review_message)

            # log the quote
            self.bot.logger.info(f"Recieved quote by: {msg.author.name} (ID: {msg.author.id}) RAW: '{msg.content}'")

            # logging 
            self.bot.logger.info(f"Added review message for quote in {msg.channel.name} (ID: {msg.channel.id}) by {msg.author.name} (ID: {msg.author.id})")


    @commands.has_role(config["quote_manager"]["quote_reviewer_role_id"])
    @commands.command(brief="Adds a quote to a given channel. This is used to sort a quote to a channel if it wasn't voted to be sorted automatically. \n\nUsage:`add [channel name] [formatted quote]` \n\nyou must reply to the message you want to add. \n\n'channel name': the channel the message should be sent to. \n\n'formatted quote': the quote that should be sent, leave empty if quote is already formatted correctly.")
    async def add(self, ctx, channel_name, *, formatted_quote=None):
        # check if message is reply and get the id of the message that was replied to
        review_message_id = await self.check_is_reply(ctx)
        if review_message_id == None: return
        
        # check if channel_name is valid
        is_channel = await self.check_is_channel(ctx, channel_name)
        if is_channel == None: return

        # check if review status is "voted"
        result = await self.check_review_status(config["quote_manager"]["quote_review_channel_id"], review_message_id)

        # if result == True return
        if result == True: return

        # check if result is present and is "voted"
        if result["status"] and result["status"] != "voted":
            await ctx.send(f"Please wait for enough votes ({config['quote_manager']['required_votes']}) before attempting to sort the quote.", delete_after=5)
            return

        # edit review message
        await self.edit_review_message(ctx.channel.id, review_message_id, "voted", "sorted", True)

        # edit db (add new formatted quote?)
        formatted_quote = await self.edit_database(review_message_id, ctx.message.author, formatted_quote)

        # get category from guild and id
        guild = ctx.guild
        category = discord.utils.get(guild.channels, id=config["quote_archiver"]["primary_category_id"])
        
        # find channel with fitting name in category
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel) and channel.name == channel_name:
                send_channel = channel

        # check if channel was found, if not return and message
        if not send_channel: 
            await ctx.send("Please use an existing channel name or check your spelling.")
            return
        
        # send message to the found channel
        await send_channel.send(formatted_quote)

        # delete message sent by user 
        await ctx.message.delete()


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # check if message is in review channel, return if not
        if payload.channel_id != config["quote_manager"]["quote_review_channel_id"]: return

        # check if message was sent by bot, return if not 
        channel = self.bot.get_channel(payload.channel_id) 
        message = await channel.fetch_message(payload.message_id)

        # if reaction came from bot, return
        if payload.user_id == self.bot.user.id: return

        # setup discord variables 
        review_channel = self.bot.get_channel(config["quote_manager"]["quote_review_channel_id"])

        # check if quote was already sorted 
        result = await self.check_review_status(payload.channel_id, payload.message_id)

        # if result == True return
        if result == True: return

        # check if result is present and is "sorted" or "voted"
        if result["status"] and (result["status"] == "sorted" or result["status"] == "voted"): 
            await review_channel.send("The message has already been sorted, please reply to an unsorted message instead.", delete_after=5)
            return

        # check if there are x reactions of the same type 
        emoji = await self.check_reactions(payload)
        if emoji == "": return

        # sort the quote 
        check = await self.sort_quote(emoji, payload, channel, result)
        if check == True: return


    @commands.has_role(config["quote_manager"]["quote_reviewer_role_id"])
    @commands.command(brief="Resends a review message. \n\nUsage: `resend` \n\n you must reply to the message you want to resend.")
    async def resend(self, ctx):
        # check if message is reply and get the id of the message that was replied to
        review_message_id = await self.check_is_reply(ctx)
        if review_message_id == None: return

        # resend the review with embed, button and emojis 
        new_review_message = await self.resend_review(ctx, config["quote_manager"]["quote_review_channel_id"], review_message_id)

        # set the review_message_id in db to the new review message
        await self.reregister_in_db(review_message_id, new_review_message)


    @commands.has_role(config["quote_manager"]["quote_reviewer_role_id"])
    @commands.command(brief="Edits a quote message that the bot has sent. \n\nUsage: `edit [new content]` \n\nyou must reply to the message you want to edit. \n\n'new content': the content the message should be edited to.")
    async def edit(self, ctx, *, new_content):
        # check if message is reply and get the id of the message that was replied to
        quote_message_id = await self.check_is_reply(ctx)
        if quote_message_id == None: return

        # setup discord variables 
        quote_message = await ctx.channel.fetch_message(quote_message_id) 

        # edit db 
        await self.edit_document_by_quote(quote_message.content, new_content)

        # edit quote_message
        await quote_message.edit(content=new_content)

        # delete message sent by user 
        await ctx.message.delete()


    @commands.has_role(config["quote_manager"]["quote_reviewer_role_id"])
    @commands.command(brief="Deletes a quote from the database and the channel it was sorted to. \n\nUsage: `delete`\n\n you must reply to the message you want to delete.")
    async def delete(self, ctx):
        # check if message is reply and get the id of the message that was replied to
        quote_message_id = await self.check_is_reply(ctx)
        if quote_message_id == None: return

        # setup discord variables 
        quote_message = await ctx.channel.fetch_message(quote_message_id) 

        # delete message from database
        await self.delete_document_by_quote(quote_message.content)

        # delete quote message
        await quote_message.delete()

        # delete message sent by user 
        await ctx.message.delete()


    @commands.is_owner()
    @commands.command(brief="Overrides the regular voting on a review message. \n\nUsage: `override_voting [emoji number]` \n\nyou must reply to the message you want to override. \n\n'emoji number': the number of the reaction you want to override the voting for.")
    async def override_voting(self, ctx, emoji_number=5):
        # check if message is reply and get the id of the message that was replied to
        review_message_id = await self.check_is_reply(ctx)
        if review_message_id == None: return

        # get quote from database 
        res = await self.get_quote_from_db(review_message_id)

        if res == True:
            await ctx.send("Please reply to a valid review message.")
            return

        # sorting for standard hidden channels
        if emoji_number == 1: await self.autosort_quote(config["quote_manager"]["sorting_channels"]["high_containment"], config["quote_manager"]["quote_review_channel_id"], review_message_id, res["quote"])
        if emoji_number == 2: await self.autosort_quote(config["quote_manager"]["sorting_channels"]["low_containment"], config["quote_manager"]["quote_review_channel_id"], review_message_id, res["quote"])
        if emoji_number == 3: await self.autosort_quote(config["quote_manager"]["sorting_channels"]["no_context"], config["quote_manager"]["quote_review_channel_id"], review_message_id, res["quote"])
        if emoji_number == 4: await self.autosort_quote(config["quote_manager"]["sorting_channels"]["not_funny"], config["quote_manager"]["quote_review_channel_id"], review_message_id, res["quote"])

        # editing status in db for user sorting
        if emoji_number == 5: await self.set_db_voted(config["quote_manager"]["quote_review_channel_id"], review_message_id, res["quote"])

        # set status in review message
        if emoji_number in [1, 2, 3, 4]: await self.edit_review_message(ctx.channel.id, review_message_id, "voting", "sorted", False)
        if emoji_number == 5: await self.edit_review_message(ctx.channel.id, review_message_id, "voting", "voted", False)

        # reply to user
        await ctx.send("Review message has been overriden.", delete_after=10)

        # delete user message 
        await ctx.message.delete()

        # logging 
        self.bot.logger.warning(f"Voting for ID {review_message_id} has been overriden by {ctx.author.name} (ID: {ctx.author.id})")


    '''
    functions used for standard discord events
    '''
    # FUNCTIONS USED IN COMMMAND "add"
    async def check_is_reply(self, ctx): # also used in: edit, delete, override_voting        
        try: 
            replied_message_id = ctx.message.reference.message_id
            return replied_message_id
        except: 
            await ctx.channel.send("Please reply to the message you are referring to.", delete_after=10)
            await ctx.message.delete()
            return


    async def check_is_channel(self, ctx, channel_name):
        category = self.bot.get_channel(config["quote_archiver"]["primary_category_id"])

        if not discord.utils.get(category.channels, name=channel_name): 
            await ctx.send("Please give a vaild channel name to send the message to. (Look out for '-' between words)")
            return
        else: 
            return True


    async def check_review_status(self, channel_id:int, message_id:int): # also used in: on_raw_reaction_add
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # set query for search in database 
        query = {
            "review_message_id": message_id
        }
        
        # if message id in db, get the document
        # if message author is the bot, return
        # if message id not in db, send message and return
        if coll.find_one(query) != None:
            res = coll.find_one(query)
            return res
        elif str(message.author) == str(self.bot.user):
            return True 
        else:
            await channel.send("Please reply to a valid review message.") 
            return True


    async def edit_review_message(self, channel_id:int, message_id:int, initial:str, new:str, edit_color):
        # setup discord variables    
        channel = self.bot.get_channel(channel_id)
        review_message = await channel.fetch_message(message_id)
        message_content = review_message.content

        # edit message content
        message_content = message_content.replace(initial, new)
        
        if edit_color == True:
            # edit embed color 
            review_embed = review_message.embeds[0]
            review_embed.color = discord.Color.green()

            # send edit
            await review_message.edit(content=message_content, embed=review_embed)
        else:
            # send edit
            await review_message.edit(content=message_content)


    async def edit_database(self, review_message_id:int, author, formatted_quote):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "review_message_id": review_message_id
        }

        # if no new version of the quote was passed, use the intial quote instead
        if formatted_quote == None:
            res = coll.find_one(query)
            formatted_quote = res["quote"]

        # define the update for quote in database
        update_doc = {
            "$set": {
                "formatted_quote": formatted_quote,
                "added_by_id": author.id,
                "added_by_name": author.name,
                "status": "sorted"
            }
        }

        # push update to database
        coll.update_one(query, update_doc)

        return formatted_quote


    # FUNCTIONS USED IN LISTENER "on_message"
    async def send_review(self, quote_channel, quote_review_channel, message):
        review_embed = discord.Embed(
            title=f"Quote by {message.author.name}",
            description=f"```{message.content}```",
            color=discord.Color.red()
        )
        review_embed.add_field(name="Voting options", value="1 - high-containment, \n2 - low-containment, \n3 - no-context, \n4 - not funny, \n5 - normal sorting")

        # send review message to channel
        review_message = await quote_review_channel.send("status: ** voting **\n", embed=review_embed,  view=ReviewMessageButtons(message.content))
        
        # add reactions to the review message
        await review_message.add_reaction("1️⃣")
        await review_message.add_reaction("2️⃣")
        await review_message.add_reaction("3️⃣")
        await review_message.add_reaction("4️⃣")
        await review_message.add_reaction("5️⃣")
        return review_message


    async def duplicate_user_entry(self, quote_channel, quote_duplicate_channel, message):
        # get message timestamp
        message_timestamp = arrow.get(message.created_at)
        message_timestamp = message_timestamp.timestamp()

        # information to put into the message 
        information = {
            "author_name": message.author.name,
            "author_id": message.author.id,
            "channel_name": message.channel.name,
            "channel_id": message.channel.id,
            "message_created_at": message_timestamp
        }

        # send the duplicate of the message into the specified channel
        duplicate_message = await quote_duplicate_channel.send(f"**Message duplicate**\n```{information}```content: ```{message.content}```")
        return duplicate_message


    async def add_review_to_db(self, message, review_message):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        insert_doc = {
            "quote": message.content,
            "formatted_quote": "",
            "submitted_by": message.author.name,
            "submitted_by_id": message.author.id,
            "message_id": message.id,
            "review_message_id": review_message.id,
            "timestamp": review_message.created_at,
            "status": "voting"
        }

        # push review to database
        coll.insert_one(insert_doc)


    # FUNCTIONS USED IN COMMAND "resend"
    async def resend_review(self, ctx, quote_review_channel_id:int, review_message_id:int):
        # setup discord variables
        quote_review_channel = self.bot.get_channel(quote_review_channel_id)
        review_message = await quote_review_channel.fetch_message(review_message_id)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # set query for search in database 
        query = {
            "review_message_id": review_message.id
        }

        # find document in db
        res = coll.find_one(query)
        
        if res["status"] == "voting": color = discord.Color.red()
        if res["status"] == "voted": color = discord.Color.gold()
        if res["status"] == "sorted": color = discord.Color.green()

        # create resend embed
        resend_embed = discord.Embed(
            title=f"Quote by {res['submitted_by']}",
            description=f"```{res['quote']}```",
            color=color
        )
        resend_embed.add_field(name="Voting options", value="1 - high-containment, \n2 - low-containment, \n3 - no-context, \n4 - not funny, \n5 - normal sorting")

        # send review message to channel and add view for button
        new_review_message = await ctx.send(review_message.content, embed=resend_embed, view=ReviewMessageButtons(res["quote"]))
        
        # add reactions to the review message
        await new_review_message.add_reaction("1️⃣")
        await new_review_message.add_reaction("2️⃣")
        await new_review_message.add_reaction("3️⃣")
        await new_review_message.add_reaction("4️⃣")
        await new_review_message.add_reaction("5️⃣")
        return new_review_message
    
    
    async def reregister_in_db(self, review_message_id:int, new_review_message):
        # setup discord variables
        review_channel = self.bot.get_channel(config["quote_manager"]["quote_review_channel_id"])
        review_message = await review_channel.fetch_message(review_message_id)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # set query for search in database 
        query = {
            "review_message_id": review_message.id
        }

        # define the update for quote in database
        update_doc = {
            "$set": {
                "review_message_id": new_review_message.id
            }
        }

        # find document in db
        res = coll.update_one(query, update_doc)


    # FUNCTIONS USED IN LISTENER "on_raw_reaction_add"
    async def check_reactions(self, payload):
        # setup discord variables
        review_channel = self.bot.get_channel(config["quote_manager"]["quote_review_channel_id"]) 
        review_message = await review_channel.fetch_message(payload.message_id)

        # setup return variable 
        reaction_emoji = ""

        # iterate over all reactions on the message
        for reaction in review_message.reactions:
            # if reaction emoji is the searched one and there are more or equally as many votes as is required in config file, return the emoji
            if reaction.emoji == str(payload.emoji) and reaction.count >= config["quote_manager"]["required_votes"]: reaction_emoji = reaction.emoji
            
            # elif reaction emoji is the searched one send reminder about votes 
            elif reaction.emoji == str(payload.emoji): await self.send_reminder_votes(reaction.emoji, reaction.count)

        return reaction_emoji


    async def sort_quote(self, emoji, payload, channel, result):
        # sorting for standard hidden channels
        if emoji == "1️⃣": await self.autosort_quote(config["quote_manager"]["sorting_channels"]["high_containment"], config["quote_manager"]["quote_review_channel_id"], payload.message_id, result["quote"])
        if emoji == "2️⃣": await self.autosort_quote(config["quote_manager"]["sorting_channels"]["low_containment"], config["quote_manager"]["quote_review_channel_id"], payload.message_id, result["quote"])
        if emoji == "3️⃣": await self.autosort_quote(config["quote_manager"]["sorting_channels"]["no_context"], config["quote_manager"]["quote_review_channel_id"], payload.message_id, result["quote"])
        if emoji == "4️⃣": await self.autosort_quote(config["quote_manager"]["sorting_channels"]["not_funny"], config["quote_manager"]["quote_review_channel_id"], payload.message_id, result["quote"])
        
        # sorting for quotes to teachers
        if emoji == "5️⃣": await self.set_db_voted(config["quote_manager"]["quote_review_channel_id"], payload.message_id, result["quote"])

        # if "5" send review message was sorted
        if emoji in ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]: 
            # remind_embed = discord.Embed(
            #     title="Review message reminder",
            #     description=f"Review message has reached enough votes and has been sorted automatically.",
            #     color=discord.Color.green()
            # )
            # remind_embed.set_footer(text=f"review_msg_id: {payload.message_id}")

            # # send reminder with given embed
            # await self.send_reminder(remind_embed)
            
            # logging 
            self.bot.logger.info(f"Reaction event in {channel.name} (ID: {channel.id}) [Quote was sorted.]")
        # if "5" send review message to be sorted
        elif emoji == "5️⃣": 
            # remind_embed = discord.Embed(
            #     title="Review message reminder",
            #     description=f"Review message has reached enough votes and can now be sorted.",
            #     color=discord.Color.red()
            # )
            # remind_embed.add_field(name="Quote:", value=f"```{result['quote']}```")
            # remind_embed.set_footer(text=f"review_msg_id: {payload.message_id}")

            # # send reminder with given embed
            # await self.send_reminder(remind_embed)

            # logging 
            self.bot.logger.info(f"Reaction event in {channel.name} (ID: {channel.id}) [Quote can now be sorted.]")
        else: return True


    async def autosort_quote(self, channel_id:int, review_channel_id:int, review_message_id:int, quote):
        # sort quote to channel
        channel = self.bot.get_channel(channel_id)
        await channel.send(quote)

        # setup discord review message variables 
        review_channel = self.bot.get_channel(review_channel_id)
        review_message = await review_channel.fetch_message(review_message_id)

        # setup discord quote message variables 
        quote_channel = self.bot.get_channel(config["quote_manager"]["quote_channel_id"])

        # edit review message
        review_message_content = review_message.content
        review_message_content = review_message_content.replace("voting", "sorted")

        # edit embed color 
        review_embed = review_message.embeds[0]
        review_embed.color = discord.Color.green()

        # send edit 
        await review_message.edit(content=review_message_content, embed=review_embed)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "review_message_id": review_message_id
        }

        # get result for query
        res = coll.find_one(query)

        # define the update for quote in database
        update_doc = {
            "$set": {
                "formatted_quote": quote,
                "status": "sorted"
            }
        }

        # push update to database
        coll.update_one(query, update_doc)

        # get the original message from the user entered quotes channel
        original_message = await quote_channel.fetch_message(res["message_id"])

        # delete the message
        await original_message.delete()


    async def set_db_voted(self, review_channel_id:int, review_message_id:int, quote):
        # setup discord review message variables 
        review_channel = self.bot.get_channel(review_channel_id)
        review_message = await review_channel.fetch_message(review_message_id)
        
        # setup discord quote message variables 
        quote_channel = self.bot.get_channel(config["quote_manager"]["quote_channel_id"])

        # edit review message
        review_message_content = review_message.content
        review_message_content = review_message_content.replace("voting", "voted")

        # edit embed color 
        review_embed = review_message.embeds[0]
        review_embed.color = discord.Color.gold()

        # send edit
        await review_message.edit(content=review_message_content, embed=review_embed)

        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "review_message_id": review_message_id
        }

        # get result for query
        res = coll.find_one(query)

        # define the update for quote in database
        update_doc = {
            "$set": {
                "status": "voted"
            }
        }

        # push update to database
        coll.update_one(query, update_doc)

        # get the original message from the user entered quotes channel
        original_message = await quote_channel.fetch_message(res["message_id"])

        # delete the message
        await original_message.delete()


    async def send_reminder(self, embed=None):
        reminder_channel = self.bot.get_channel(config["quote_manager"]["reminder_channel_id"])
        
        await reminder_channel.send(embed=embed, silent=True)


    async def send_reminder_votes(self, emoji, votes):
        reminder_channel = self.bot.get_channel(config["quote_manager"]["reminder_channel_id"])

        # remind_embed = discord.Embed(
        #     title="Review message reminder",
        #     description=f"Currently {votes}/{config['quote_manager']['required_votes']} votes for voting option {emoji}.",
        #     color=discord.Color.blue()
        # )

        # await reminder_channel.send(embed=remind_embed, silent=True)
        

    # FUNCTIONS USED IN COMMAND "edit"
    async def edit_document_by_quote(self, quote, new_quote):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "formatted_quote": quote
        }

        # define the update for quote in database
        update_doc = {
            "$set": {
                "quote": new_quote,
                "formatted_quote": new_quote,
                "status": "sorted"
            }
        }
        print("here", new_quote, quote)
        # push update to database
        coll.update_one(query, update_doc)


    # FUNCTIONS USED IN COMMAND "delete"
    async def delete_document_by_quote(self, quote):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "formatted_quote": quote
        }

       # push deltetion to database
        coll.delete_one(query)

    
    # FUNCTIONS USED IN COMMAND "override_voting"
    async def get_quote_from_db(self, message_id:int):
        # setup mongodb
        uri = config["mongodb_uri"]
        mongo_client = MongoClient(uri, server_api=ServerApi("1"))
        db = mongo_client["mongo_of_quotes_release"]

        # setup rquiered variables
        coll = db["quote_manager"]

        # define query to search for
        query = {
            "review_message_id": message_id
        }
        
        if coll.find_one(query) != None:
            res = coll.find_one(query)
            return res
        else:
            return True
       
       
    # use this to check if a quote was added to a channel in order to set its status to sorted in the db
    def contains_percent_splits(comparison, to_compare):
        # setup variables
        comparison = comparison.split(" ")
        count = 0

        # iterate over splits in comparison and check if the comparison contains them
        # if yes, count + 1
        # if no, continue with next split
        for split in comparison:
            if to_compare.__contains__(split):
                count += 1

        # calculate percentage of splits in comparison string
        contains_percent = count / int(len(comparison)) * 100
        return contains_percent



'''
additional classes for Buttons or similar
'''
# Button attached to the review message (sent in class QuoteManager in func send_review)
class ReviewMessageButtons(discord.ui.View):
    def __init__(self, raw_message, *, timeout=None):
        self.raw_message = raw_message
        super().__init__(timeout=timeout)

    @discord.ui.button(label="send quote (for mobile)", style=discord.ButtonStyle.blurple)
    async def send_quote_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        # send response on buttonpress
        await button.response.send_message(self.raw_message, silent=True, delete_after=20)
    


# setup function to add cog to bot
async def setup(bot):
    await bot.add_cog(QuoteManager(bot))
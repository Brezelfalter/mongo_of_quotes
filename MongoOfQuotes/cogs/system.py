import discord
import json
import os
import sys
import logging 
import urllib.request

from discord.ext import commands
from logging import exception


if not os.path.isfile(f"{os.getcwd()}/config.json"):
    sys.exit("'config.json' not found! Please add it and try again.")
else:
    with open(f"{os.getcwd()}/config.json") as file:
        config = json.load(file)


logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)


class System(commands.Cog):
    """
    the basic system functions
    currently consisting of:
    on_ready, help, ping, load, unload 
    """
    def __init__(self, client):
        self.client = client

    # presence is currently changed from main.py 
    # @commands.Cog.listener() 
    # async def on_ready(self):
    #     await self.client.change_presence(activity=discord.Game(name=f"with quotes (v{config['version']})"), status=discord.Status.online)
    #     logger.info("Changed presence")
    

    @commands.is_owner()
    @commands.dm_only()
    @commands.command(brief="A command to get the global IPv4 and IPv6 the bot is running on.")
    async def ip(self, ctx):
        # get IPv4 if possible
        try: ipv4 = urllib.request.urlopen('https://v4.ident.me').read().decode('utf8')
        except: ipv4 = "IPv4 could not be found."

        # get IPv6 if possible
        try: ipv6 = urllib.request.urlopen('https://v6.ident.me').read().decode('utf8')
        except: ipv6 = "IPv6 could not be found."

        # send message with information
        await ctx.send(f"IP Information:\nIPv4: {ipv4}\nIPv6: {ipv6}")


    @commands.is_owner()
    @commands.command(brief="Shuts down the bot. Restart through a command will not be possible.")
    async def shutdown(self, ctx):
        await ctx.send("Shutting down... sigh...")
        logger.info("Shutting down client...")
        exit(0)


    @commands.is_owner()
    @commands.command(brief="Sends genral or specific command help. Give the argument after the command")
    async def help(self, ctx, extension=None):
        """
        Gives help, while listing all the classes that contain commands as well as
        their commands in an Embed. 
        Also states the current Bot version and advice on more specific information 
        for each command.
        """
        # deletes the message that triggered the command to keep the chat clean
        await ctx.channel.purge(limit=1)

        # declares the base for the Embed
        help_Embed = discord.Embed(
            title="Bot help**                                               **",
            description="** **",
            colour=discord.Colour.blue()
        )
        # if extension was given, give command specifiic help
        if extension:
            # get command brief
            command_brief = self.client.get_command(extension).brief

            # if command brief is not existent
            if command_brief is None:
                # set command brief to a spare value  
                command_brief = "This command does not exist, please give a valid command."

            # add a field to the Embed, which contains the command brief
            help_Embed.add_field(
                name=f"Command info:",
                value=command_brief,
                inline=False
                )
        else:
            # if programm was not ended before, send standard help
            for item in self.client.cogs:
                commands_list = []
                edited_commands = ""

                # get all commands of one class and get their names
                commands = self.client.get_cog(f"{item}").get_commands()
                commands = [c.name for c in commands]

                # put all commands in a list that gets sorted alphabetically
                for command in commands:
                    if command not in config["system"]["command_help_blacklist"]:
                        commands_list.append(command)
                commands_list.sort()

                # puts all commands in a string and below each other
                for command in commands_list:
                    edited_commands = f"{edited_commands}\n{command}"
                
                # checks if there are commands and skips the editing of the embed if none exist
                if edited_commands == "":
                    continue
                
                # adds two fields to the Embed, one with the info and a second one to act as a placeholder
                help_Embed.add_field(
                    name=f"{item}:",
                    value=edited_commands,
                    inline=False
                )
                help_Embed.add_field(
                    name="** **",
                    value="** **",
                    inline=False
                )
            # adding a field with relation to individual extension information
            help_Embed.add_field(
                name = "** **",
                value = f"For more information on each command, \nuse `{config['prefix']}help <command name>` instead."
            )
        # sets the footer with the version info
        help_Embed.set_footer(
            text=f"Bot is running: v{config['version']}"
        )
        #sends the Embed and deletes it after 30s
        await ctx.send(embed=help_Embed, delete_after=30)
    

    @commands.is_owner()
    @commands.command(brief="Returns the current latency in ms.")
    async def ping(self, ctx):
        """ 
        returns the latency the client currently has in ms
        """
        # sends a message with the latency the client has in ms
        await ctx.send(embed=create_embed("[ping]", 'pong ({0}'.format(round(self.client.latency * 1000)) + "ms)", discord.Color.blue()))
        logger.info(f"ping: {round(self.client.latency * 1000)}ms")


    @commands.is_owner()
    @commands.command(brief="Returns information about the Heroku deploy version.")
    async def info(self, ctx):
        """
        Provides the owner with the current heroku deploy version.
        """
        try:
            heroku_version = str(os.environ.get("HEROKU_RELEASE_VERSION"))
            created_at = str(os.environ.get("HEROKU_RELEASE_CREATED_AT")).replace("T", " ").replace("Z", "")
            commit = str(os.environ.get("HEROKU_SLUG_COMMIT"))[:8]

            version_embed = discord.Embed(
                title="[Bot information]**                                               **",
                description="** **",
                colour=discord.Colour.blue()
            )
            version_embed.add_field(name="Heroku:", value=f"*{heroku_version}*", inline=False)
            version_embed.add_field(name="Started at:", value=f"*{created_at} [UTC]*", inline=False)
            version_embed.add_field(name="Commit:", value=f"*{commit}*", inline=False)

            await ctx.send(embed=version_embed)
            logger.info(f"Heroku Information\n{pad('')}  Heroku: {heroku_version}\n{pad('')}  Started at: {created_at}\n{pad('')}  Commit: {commit}")
        
        except exception as e:
            await ctx.send(f"Information not available. \n\n[error]\n{e}")
            logging.info(e)


    @commands.is_owner()
    @commands.command(brief="Loads an extension.")
    async def load(self, ctx, extension):
        """
        loads an extension that is not active currently
        """
        
        try:
            # loads the extension given by the user
            await self.client.load_extension(f"cogs.{extension}")

            # sends confirmation about the activation of the extension to the user
            await ctx.send(embed=create_embed("[loaded]", f"`<{extension}>` has been loaded", discord.Color.blue()))
            logger.info(f"Loaded {extension}.")

        except:
            await ctx.send(f"Unable to load the given extension. Did you spell it correctly? Is it already loaded?")
            logger.info(f"Could not load {extension}.")


    @commands.is_owner()
    @commands.command(brief="Unloads an extension.")
    async def unload(self, ctx, extension):
        """
        unloads an extension that is not active currently
        """
        try:
            if extension in config["system"]["command_blacklist"]:
                blacklist_embed = discord.Embed(
                    title = "[blacklisted]",
                    description = f"You are not permitted to disable `<{extension}>`",
                    color = discord.Color.red()
                )
                await ctx.send(embed=blacklist_embed, delete_after=10)
                return

            # unloads the extension given by the user
            await self.client.unload_extension(f"cogs.{extension}")

            # sends confirmation about the deactivation of the extension to the user
            await ctx.send(embed=create_embed("[unloaded]", f"`<{extension}>` has been unloaded", discord.Color.dark_blue()))
            logger.info(f"Unloaded {extension}.")

        except:
            await ctx.send(f"Unable to unload the given extension. Did you spell it correctly? Is it already unloaded?")
            logger.info(f"Could not unload {extension}.")


    @commands.is_owner()
    @commands.command(brief="Reloads an extension.")
    async def reload(self, ctx, extension):
        """
        reloads an extension that is currently active
        """
        try:
            if extension in config["system"]["config_blacklist"]:
                blacklist_embed = discord.Embed(
                    title = "[blacklisted]",
                    description = f"You are not permitted to disable `<{extension}>`",
                    color = discord.Color.red()
                )
                await ctx.send(embed=blacklist_embed, delete_after=10)
                return
        
            # reloads the extension given by the user
            await self.client.reload_extension(f"cogs.{extension}")

            await ctx.send(embed=create_embed("[reloaded]", f"`<{extension}>` has been reloaded", discord.Color.dark_blue()))
            logger.info(f"Reloaded {extension}.")

        except:
            await ctx.send(f"Unable to reload the given extension. Did you spell it correctly? Is it unloaded?")
            logger.info(f"Could not reload {extension}.")



def create_embed(title, description, color):
    # create basic discord Embed with given title, discription and color
    # color format: discord.Color.blue()
    embed = discord.Embed(title = title, description = description, color = color)
    # return the embed
    return embed

def pad(s, l=18):
    while len(s) < l:
        s += " "
    return s



async def setup(client):
    await client.add_cog(System(client))
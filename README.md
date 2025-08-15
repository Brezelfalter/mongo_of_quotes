# Mongo of Quotes
A discord bot designed to sort and save quotes using mongodb, containerized with docker.


&nbsp;
## Setup
1. Ensure docker and docker compose are installed on your system.

2. Clone the [repository](https://github.com/Brezelfalter/mongo_of_quotes).

3. Create a discord application on the discord developer portal and create a bot user, enable all additional intents and create an invite link to your server (currently only tested with administrator rights). 

4. Copy the token from the application you created and create a file called `.env` in `/MongoOfQuotes` with this content: `TOKEN=YOUR_TOKEN_HERE`.

5. Change the standard username and password in `docker-compose.yml`. 

6. Configure `config.json` with your channel IDs as described in [Configuration](#configuration).


&nbsp;
## Configuration
Some configuration is required to setup all the channels the bot will be using (since there is currently no setup that does so automatically).
For this, go into `config.json` and change all IDs that are set to `0`.

- `archive_categories` = List of category IDs that are saved to the database.
- `primary_category_id` = The category ID of the category that you currently want to sort the quotes to (this should also be in `archive_categories`)
- `quote_channel_id` = The channel you can send the raw quotes into.
- `quote_duplicate_channel_id` = Use this channel if you want the bot to duplicate the quotes into another channel (currently disabled, can stay 0).
- `quote_review_channel_id` = The channel used to vote on adding or not adding the quotes to the collection.
- `quote_reviewer_role_id` = The role ID of the role that permits a user to vote in the voting channel. 
- `reminder_channel_id`= A channel that can be set if you want a reminder when a new raw quote has been received (currently disabled, can stay 0).
- `sorting_channels` = The IDs defined within this are used to define 4 channels that are used to keep the quotes you do not want to add to the collection within other channels. The 4 different channel can be used to sort the quote based on severity of its contents.
- `quote_of_the_day` / `channel_id` = The channel that is used to send a new quote to everyday, which is picked randomly out of all quotes.
- `quote_stats` / `channel_id` = The channel a statspage is sent to.


### Database
Make sure to replace the standard credentials within `mongodb_uri` to the ones you set earlier, otherwise database connection **will fail**. 


### Additional setup
You can change these settings to customize how the bot behaves, but do not have to.
- `required_votes` = The amount of votes required (including the initial emoji reaction the bot will make) to vote for any given quote.
- `max_channels` = The maximum amount of channels displayed in the stats message. A too large number could lead to errors as the discord message length is limited.


&nbsp;
## Startup
To start the bot and database, navigate to the directory the project is in and run:
```
docker compose up -d --build
```
This will launch the bot and the database. 



&nbsp;
--- 
Currently on v1.1dev25-07-07. (as of 2025-07-07)
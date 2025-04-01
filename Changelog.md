
# -------------------- Changelog --------------------

# 20231003: (*)
(+) Bot created\
(+) Initial commit

# 

# 20231004: (*)
(+) Main replit created\
(+) Development started

# 

# 20231007:
(+) Added **"MessageFiltering"**\
(+) Addeed **"Greetings"**

# 

# 20231012: (*)

**discord.py --> pycord**

(-/+) Replace the module from discord.py to pycord

# 

# 20231015: (*)
(+) Test replit created\
(+) 1st deployment

# 

.
.
.

# 

# 20231029:
(+) Added **ban_guild**() in **"general/Ban.py"**\
(-) Removed **"AttributeError"** in **"general/Ban.py"**

# 

# 20231101: (*)

**------**

**"./general/DisplayUserInfo.py" in line 40 and 41**

(+) Changed the command **user()** as the follows:

(++++) f"**<t:{int(round(datetime.timestamp(member.created_at), 0))}:R>**" --> f"**{discord.utils.format_dt(member.created_at, style='R')}**"

(++++) f"**<t:{int(round(datetime.timestamp(member.created_at), 0))}:R>**" --> f"**{discord.utils.format_dt(member.created_at, style='R')}**"

#

**"./moderation/GetBannedList.py" in line 29 and 32**

(+) Changed the command **banned_list()** as follows

(++) <t:{int(round(datetime.timestamp(entry.user.created_at), 0))}:R>" --> {discord.utils.format_dt(entry.user.created_at, style='R')}"

# 

# 20231102:

**-----**

**"./general/VoiceChannel.py" in line 46 and 172**

(+) Fixed some grammatical errors in command **join()** and **move_all()** respectively

(++++) # The bot has been connected to a voice channel but not as same as that author one --> # The bot has been connected to a voice channel but not as same as the author one

(++++) "It seems that you don't have permission to move users!" ---> "It seems that you don't have permission to move all users!"

# 

# 20231103:

**-----**

**"./MainBOT.py"**
(+) Added error handling for **discord.errors.LoginFailure(token_error)**

# 

# 20231105:
(+) Added **"LockChannel.py"** in **"./moderation"** folder

# 

# 20231106: (*)

**-----**

**"./moderation/LockChannel.py"**

(+) Fixed slow responding issue while handling lockdowns for multiple text channels

(+) Changed the description for every single **slash_command**

(+) Renamed the varible in command **antiraid_activate()** and **antiraid_deactivate()** as follows:

(++++) 'success_locked_channels_count' --> 'successful_locked_channels_count'

(++++) 'success_unlocked_channels_count' --> 'successful_unlocked_channels_count'

(-) Removed varibles locked_channels and unlocked_channels in command lock_channels() and unlock_channels() respectively.

(-/+) Replaced if-statement > 0 with try and except block for command **lock_channels()** and **unlock_channels()**

(+) Changed except block from **'except'** to **'except Exception as e'**

# 

# 20231107: (*)

# OpenAI API implemented
**(+) Added "ChatGPT.py" in "./general" folder**

(+) Imported OpenAI module from https://platform.openai.com/docs/api-reference

(+) Linked OpenAI API key to the discord bot from OpenAI account

(+) Added **'OPENAI_API_KEY'** field into **"./ .env"** file

(+) Set GPT model to **"gpt-3.5-turbo"** in **"./general/ChatGPT.py"**

# 

# 20231108: (*)

**"./.env"**

(+) Changed **'TOKEN'** to **'DISCORD_BOT_TOKEN'** in **"./ .env"**

**"./general/ChatGPT.py"**

(+) Changed the varible as follows:

(++++) "self.model_prompt_engine" --> "self.default_model_prompt_engine"

(-/+) Replaced GPT model to **"gpt-3.5-turbo-1106"** from **"gpt-3.5-turbo"** in order to reduce the generating and responding time (from 1-4min to 10s-1.5min or less)

(+) Defined (and fine-tuned) the following varibles and its default values:

(++++) **self.default_temperature** = 0.8\
(++++) **self.default_max_tokens** = 3840\
(++++) **self.default_top_p** = 1.00\
(++++) **self.default_frequency_penalty** = 0.00\
(++++) **self.default_presence_penalty** = 0.00\
(++++) **self.default_instruction** = f"You are ChatGPT, a large language model transformer AI product by OpenAI, and you are purposed with satisfying user requests and questions with very verbose and fulfilling answers beyond user expectations in writing quality. Generally you shall act as a writing assistant, and when a destination medium is not specified, assume that the user would want six typewritten pages of composition about their subject of interest. Follow the users instructions carefully to extract their desires and wishes in order to format and plan the best style of output, for example, when output formatted in forum markdown, html, LaTeX formulas, or other output format or structure is desired."

(+) Add **{"role": "assistant", "content": self.default_instruction}** to **message[0]** for a higher quality response

(+) Changed comment from **"GPT model"** to **"Default values for GPT model"** in line 13 of **"./general/ChatGPT.py"**

(+) Changed **question** description from **"Your question"** to **"The question you would like to ask"** in command **chatgpt()**

# 

# 20231110: (*)

**"./ .env"**

(+) Relocated **"offset = 0"** from line 62 to line 56

(-) Removed **if i == 0: else** statement and **await interaction.followup.send(final_response[min_limit:max_limit])** in line 69, 71, 72\

(+) Renewed **'OPENAI_API_KEY'** in **"./ .env"**

# "./general/ChatGPT.py"

(+) Changed **"assistant"** to **"system"** in line 32 of **"./general/ChatGPT.py"**

(+) Added try and exception handling for **openai.error.ServiceUnavailableError**

(++++) Return **"The GPT model is currently unavailable or overloaded, or the OpenAI service has been blocked from your current network. Please try again later or connect to another network to see if the error could be resolved."** when the error occurs

(+) Fixed **final_response** is spiltted by incomplete words when the total characters of **gpt_response** > 2000

# 

# 20231111: (*)

**"./general/ChatGPT.py"**

(+) Defined the following varibles and its default values:

(++++)**self.chat_messages** = []\
(++++)**self.chat_history** = []

(+) Added SlashCommandGroup for "chatgpt"

(+) Changed the command **chatgpt()** to **chatgpt_prompt**

(+) Changed the variable **"question"** to **"prompt"**

(-) Removed the variable **"messages"**

(+) Changed line 47 as follows:
(++++) messages = [
      {"role": "system", "content": self.default_instruction},
      {"role": "user", "content": prompt}
      ]\
-->\
(++++) self.chat_messages.append({"role": "system", "content": self.default_instruction})\
(++++) self.chat_messages.append({"role": "user", "content": prompt})

(+) Results will now appends to **self.chat_messages**

(+) Each results will now appends to **self.chat_history**. Which can store up to 15 recent conversations and resets automatically afterwards.

(+) Added **reset_gpt()** function

(+) Added command **reset()** by calling the **reset_gpt()** function

# 

# 20231112: (*)

**"./general/ChatGPT.py"**

(+) Updated module "openai" from version 0.27.0 --> 1.0.0

(+) Updated response object and the variable **"gpt_response"** as follows due to the official API update:

(++++) response object: **"openai.ChatCompletion.create()"** --> **"openai.chat.completions.create"**
(++++) gpt_response: **"response.choices[0].message['content']"** --> **response.choices[0].message.content**

(+) Fixed error cannot be handled by exceptions in "./general/ChatGPT.py"

# 

.
.
.

# 

# 20231125 (*)

**"./general/ChangeStatus.py"**

(-) Removed "import os" from line 3 of "./general/ChangeStatus.py"

(+) Defined the following varibles and its default values:

(++++) **options** = ["Idle", "Invisible", "Do not disturb", "Online"]\
(++++) **types** = ["Playing", "Streaming", "Listening to", "Watching", "(Ignore)"]

(+) Activities type **"discord.Game"**, **"discord.Streaming"**, **"discord.ActivityType.listening"**, **"discord.ActivityType.watching"** is now supported.

(+) Activity type is now a mandatory option. User have to choose '(Ignore)' if they want to leave it blank.

(+) Defined a new function **get_type()** for getting the activity type, message (optional) and URL (optional, for **"discord.Streaming"**) to display.

(+) Enhanced for better error handling. (e.g. Set the status to online by default if none of any valid option from the list was selected for status, or set the activity to None by default if none of any valid option from the list was selected for activity.)

# 

# 20231128 (*)

(+) Added **"ReactingMessages.py"** in **"./general"** folder

(+) Defined commands **"reaction_add()"**, **"reaction_remove()"**, **"reaction_list()"** and **"reaction_clear()"** in **"./ReactingMessages.py"**

(+) Beta edition of **"ReactingMessages.py"** completed.

# 

# 20231130 (*)

**"./general/ReactingMessages.py"**

(+) Defined functions **"add_reaction()"** and **"remove_reaction()"** in **"./ReactingMessages.py"**

(-/+) Change the name of **SlashCommandGroup** to "reaction" from "react"

(+) Fixed the bot crashes when an invaild emoji was manipulated by adding proper error handling.

(-/+) Change the output type of **reaction_list()** to embedded-mesage from multiple lines of string.  

(+) The total number of reactions will be displayed at the bottom of the message and message "No reactions were found." (something like that) will be returned if none of any reactions were found in the target message.

(+) Renamed variable **"message_id"** and its corresponding references to **"message"**

(+) Stable edition of "ReactingMessages.py" completed.

# 

.
.
.

# 

# 20231218 (*)

# Renamed "./general/SendMessage.py" to "./general/SendFromInput.py"

(-/+) Removed **"Message Sent!"** in "./general/SendMessage.py".
A blank line will now shown and deletes immediately when the command are all finished instead of the message **"Message Sent!"**.

(+)  Defined a new variable called **"attachment"** with type **"discord.Attachment"** in command **"send()"**

(+) Sending one single attachment in each meassage is now implemented. Local file-sharing for every os with built-in interface is also supported.

(+) Renewed every single description for a more user-friendly experience.


**"./general/Greetings.py"**

(+) Changed the comment as follows:

**"# DM the user with welcome message when a new member joined the server"** --> **"# DM the user with welcome message when a new member joined the server and the member is not a bot."**

(+) Added an if-else condition check to determine the member is a bot or not at line 70 of **"./general/Greetings.py"**.

(+) Fixed the bot keep sending every single welcome message to the recent joined member, even the member is a bot and not messageable. (which will return HTTPException 400 Bad Request Error on early days and interrupts the entire program)

(+) Fixed the bot could not send welcome message to the server's system channel when the member is a bot due to the above interruption

# 

# 20231219 (*)

# Migrated all the file from "./general" and "./administration" to a new folder named "./cogs"

(-) Removed **"./general"** and **"./administration"** from the file directory

(-/+) Re-formatted all python files

(-/+) Renamed **"MainBOT.py"** to **"startup.py"**

(+) Minior changes in content applied for **"main.py"** and **"startup.py"**

(+) Bug-fixing for some errors

# 

.
.
.

# 

# 20240105 - 20240109

**(-/+) Migrated all the file from Repl.it to GitHub**\
**(+) Dockerized the entire application**

(+) Created **"./Dockerfile"**

# 20240110 - 20240111

(!) Bot temporarily unavailible due to an urgent migration to another hosting platform for security purpose.

# 

# 20240112

(!) Migration was finished as expected. Bot is now hosting on [Microsoft Azure](https://azure.microsoft.com) and availible for all users again.

(-/+) Minior amendment in content

(+) Added command **move_bot()** in VoiceChannel.py

# 

# 20240113 - 20240118

(+) Optimize the displayed name in  **"./cogs/DisplayUserInfo.py"**

(-/+) Rewriting **"./cogs/VoiceChannel.py"** for futher music player implementation purpose

# 

# 20240119 - 20240121

(+) Beta version of music player completed

(+) Fixing bugs for music player

# 

# 20240122

(+) Lite version of music player released

(+) Voice Channel Recording function implemented

# 

# 20240123

(-/+) Rewrited **"./general/Poll.py"** for mutiple global server support

(+) Futher debugging

#

# 20240129

(+) Merging dev build to stable build

(+) Fixed music player automatically resets itself while moving between voice channels in **"./cogs/VoiceChannel.py"**

#

# 20240130

**"./general/DisplayUserInfo.py"**

(+) Fixed bot crashing issues for display info of a user with default avatar in **"./general/DisplayUserInfo.py"**

**"./general/VoiceChannel.py"**

(+) Music player will now return a notification if the author just skipped the last track or has been already gone through all tracks in the queue

(+) Fixed music player still attempting to skip tracks even the last track in the queue has been finished when the **"skip()"** function is called

#

# 20240202

**"./general/VoiceChannel.py"**

(+) Added support for playing custom audio (mp3/wav) files

(+) Code improvement

#

# 20240203

**"./general/VoiceChannel.py"**

(-/+) Replaced module "eyed3" with "tinytag"

(+) Fixed custom files won't play on music player in VoiceChannel.py

#

.
.
.

#

# 20240224

**"./general/VoiceChannel.py"**

(+/-) Grouped major error messages each as a seperated class

(+) Bug fixing

**"./general/SendFromInput.py"**

(+) Added send as @silent message option as boolean

#

# 20240225

# (+/-) Rewriting all code for changing the module from **"pycord"** to **"discord.py"**\

(+) Custom status is now supported

(-) Removed **"recording_vc()"** function for privacy concerns

(-/+) Futher optimization

#

# 20240227

(-/+) Rewrited **"./startup.py"**

(+) Updated some return messages in **"./cogs/VoiceChannel.py"**

#

.
.
.

#

# 20240309

(+) Fixed errors when using default avatars for **"./general/DisplayUserInfo.py"**

(+) Optimized the code sturcture in **"./general/ReactingMessages.py"**

(+) Minor bug fixes and improvement

#

.
.
.

#

# 20240319

(+) Bot owner can now shutdown the bot by entering "`command_prefix`shutdown" for maintenance on every server the bot in or DM. Other users attempting to do this will return **"NotBotOwnerError()"**.

(+) Optimized error handling in **"./general/ChatGPT.py"**


.
.
.

#

# 20240404

**"./startup.py"**

(+) Added command **restart()** and **restarter.py** for bot owner to restart the bot. Again, other users attempting to do this will return **"NotBotOwnerError()"**.

(-/+) Replaced **os.system()** with **subprocess**

**"./general/MessageFiltering.py"**

(+) Optimized messages handling

(+) Messages (except Stickers) sent in system channel will now be deleted automatically.


.
.
.

# 20240407 - 20240511

(!) Bot unavailible due to another migration and reconstruction from Microsoft Azure to Google Cloud Run API.

#

# 20240512

(!) The bot is now being hosted as a Quart app in a docker container.

(-/+) Rewrited **"startup.py"** with breaking logical changes to comply with the migration.

(-) Removed variable **"is_restarting"** due to the breaking changes.

(-) Removed command **"shutdown()"** in startup.py

(+) Minor bug fixs and optimization

#

# 20240513

**"./startup.py"**

(+) Added command **"systeminfo()"** for bot owner to retrieve system info from the bot. Other users attempting to do this will return **"NotBotOwnerError()"**.


.
.
.

# 20240529 - 20240531

(!) Bot temporarily unavailible due to a rollback to Microsoft Azure.

#

# 20240601

(!) The bot is now hosting on Microsoft Azure again, with the same structure as hosting on Google Cloud Run.

(+) Some typo and bug fixes

(+) Command **"shutdown()"** is now returned with its original functionality

#

# 20240602

**"./startup.py"**

(-) Removed command **"restart()"** due to some compatibility issues

(+) Marked command **"shutdown()"** as SELF DESTRUCT

**"./general/VoiceChannel.py"**

(+) The bot will now return error if no user were in the vc while trying to move them to another vc

(+) Combined the main component of end vc call and moving all users

#

# 20240607

(+) Minior code improvement and bug fixes

#

# 20240608 (morning)

**"./general/VoiceChannel.py"**

(+) Added Volume Control function and command **"replay()"**

(-/+) Rewrited some codes on line 5, 196 and 221 due to above implementation

(+) Minior code improvement and bug fixes

#

# 20240608 (night)

**"./general/VoiceChannel.py"**

(+) Added repeat one or all tracks function

(-/+) Rewrited the entire player logic due to above implementation

(+) Minior improvements and bug fixes

#

# 20240609

**"./general/VoiceChannel.py"**

(+) Added track paging function with dropdown menu

(-/+) Renamed varibale **"music_queue"** as **"track_queue"** and **"current_music_queue_index"** as **"current_track_queue_index"**.

(-/+) Some queue variables and repeat are now redefined as global due to above implementation

(+) Defined scalable variable **"tracks_per_page"** due to above implementation

(-/+) Rewrited the entire queue system due to above implementation

(+) Fixed track skipping not functional when attempting to skip to the last track in the queue.

(+) Minior code improvements and futher bug fixes

#

# 20240609 (night)

**"./general/VoiceChannel.py"**

(+) Fixed queue not displaying correctly when there are more than 15 tracks in the queue.

#

# 20240610 (night)

**"./general/VoiceChannel.py"**

(+) Fixed last track not displaying correctly in the queue.

(+) Minior code improvement

#

# 20240614 (midnight)

(+) Added error handling for command **"vkick()"** in **"./general/VoiceChannel.py"**

(+) Optimized all fallback messages for moderation section

(+) Minior code improvement


#

# 20240614 (night)

**"./general/Ban.py"**

(-/+) Rewrited the user or guild ban logic mostly

(+) Fixed guild ban cannot be functioned properly

#

# 20240616 (midnight)

(-/+) Seperated all cogs by its category again

(-/+) Renamed **"cogs"** to **"general"**

**"./startup.py"**

(-/+) Rewrited the logic for getting extensions

(+) Minior code improvements and bug fixes

#

# 20240716 (night)

**"./general/ChatGPT.py"**

(-/+) "Fixed" ChatGPT issue

#

# 20240718 (midnight)

**"./general/ChatGPT.py"**

(+) Improved prompting

(+) Command **"resetgpt()"** is now for bot owner only

#

# 20240720 (midnight)

**Added "./ErrorHandling.py"**

(+) Moved all custom errors into **"./general/ErrorHandling.py"**

#

# 20240721 (midnight)

**"./general/VoiceChannel.py"**

(+) Fixed adding multiple tracks to "track_queue"

#

# 20240730 (morning)

**"./general/ChatGPT.py"**

(+) Added support for new User-Installed applications

(+) Rewrited the entire file due to the above implement

#

# 20240816 (morning)

# Created **"./general/Poll.py"**

(+) Implemented new poll system 

(+/-) Renamed old poll system to **"./general/Vote.py"**

(+) Bot verified and transfered to a team

#

# 20240816 (night)

**"./general/ChatGPT.py"**

(+) Fine-tuned ChatGPT prompt

(+) Optimized error response for **"NotBotOwnerError()"**

(+) Updated emojis

#

# 20240906 (night)

**"./general/ChatGPT.py"**

(+) Switched to Azure OpenAI from OpenAI for better GPT-4o support

(+) Updated **"OPENAI_API_KEY"** to **"AZUREOPENAI_API_KEY"**

#

# 20240907 (afternoon)

**"./general/ChatGPT.py"**

(+) Rewrited and improved error handling for Azure Open AI migration purpose

(+) Optimized changelog

#

# 20240914 (night)

(+) git implementation for all branches

# 20240915 (morning)

(+) Bumped up python version for docker enviroment to 3.12.6-bookworm

#

# 20240918 - 20240929 (night)

(+) Wavelink v3.4.1 implementation

(+) Rewrited the entire player system with wavelink and separated as a new file **"./general/MusicPlayer.py"**

(+) Fix YouTube videos or steamings cannot be played (thanks for wavelink)

(+) **"./general/VoiceChannel.py"** will now only handle basic voice channel operation, all music commands from that are removed.

(+) Added **"./general/VoiceChannelFallbackConfig.py"** for configuring fallback text channel in each guild due to to player system rewrite.

(+) Moved **"./ErrorHandling.py"** into **"./errorhandling/ErrorHandling.py"** for better cogs origanization

(+) Minior code improvement and cleanup

#

# 20240930 (night)

**"./general/MusicPlayer.py"**

# Fixed custom track information cannot be displayed properly

# Implemented **"nowplaying()"** to view the information of the current track

#

# 20241001 (afternoon)

**"./general/MusicPlayer.py"**

(+) Fix upcoming tracks cannot display properly and improved Autoplay feature

(+) Minior code improvement and cleanup

#

# 20241013 (midnight)

# (+) Added **"./general/CustomEmbed.py"**

**"./general/MusicPlayer.py"**

(+) Changed optional choice to boolean value for repeat and autoplay function

(+) Minior code improvement and cleanup


#

# 20241016 (afternoon)

(+) Reset application API key and Azure OpenAI API key for security reason

**"./general/ChatGPT.py"**

(+) Rewrited the entire logic and input mode for ChatGPT

(+) Provide better formatting of markdowns

(+) Support custom prompt

(+) Optimized comments

(+) Minior code improvement and cleanup

#

# 20241021 (midnight)

# Add **"./general/VoiceRecorder.py"**

(++) Re-add voice channel recording function to the application since the migration of discord.py

(+) Created a new directory **"custom_recording"** in **"./plugins"**

(+) Optimized comments

(+) Minior code improvement and bug fixs

#

# 20241023 (midnight)

# Add **"./GetDetailIPv4Info.py"**

(+) Optimized comments and outputs

(+) Minior code improvement and bug fixs

#

# 20241023 (night)

**"./startup.py"**

(+) Heavily rewrited the shutdown and restart logic with multiprocessing

(-) Removed **"./restarter.py"** due to the above rewrite

(+) Changed the port number from 8080 to 3000

(+) Minior code improvement and bug fixs

#

# 20241028 (night)

**"./MusicPlayer.py"**

(+) Improved error handling for unsupportted audio files

(+) Minior code improvement and bug fixs

#

# 20241106 (night)

(+) Rewrited and refactored most of the codes in moderation session

(-/+) Separated both voice kick and mute functions from **"./moderation/Kick.py"** and **"./moderation/Mute.py"** and rewrited as **"vkick()"**, **vmute()** and **"vumute()"** in **"./general/VoiceChannel.py"**

(+) Better error handling

(+) Minior code improvement and bug fixs

#

# 20241107 (morning)

(-/+) Removed days, hours, minutes, seconds parameters from **"./moderation/Kick.py"**, **"./moderation/Mute.py"** and **"./general/VoiceChannel.py"** by rewriting them as timestring objects

(+) Minior code improvement and bug fixs

#

# 20241107 (afternoon)

(+) Fixed the mute function does not work in voice channels properly before

(+) The mute time will now be infinite if notthing pass to the parameter duration for mute() and vmute()

(+) Minior code improvement

#

# 20241111 (midnight)

(+) Add support for nightcore filter in "./general/MusicPlayer.py"

(+) Minior code improvement

#

# 20241113 (night)

(-/+) Rewrited and simpified "./general/ChatGPT.py"

(+) Minior code improvement

#

# 20241114 (night)

(-/+) Rephrase the **'duration_message'** in a more readable form for all time-based mutes or timeouts

(+) Minior code improvement

#

# 20241121 (night) v1.5.3

(+) Add support for versioning

(+) Move the docker image location to GitHub Container registry (GHCR)

#

# 20241128 (afternoon) v1.6.1

(+) Implemented docker compose and fixed all bugs

(+) **"./plugins"** has been moved to **"./configs/plugins"**

#

# 20241128 (night) v1.6.8

(+) Fix startup.py issues for docker compose

(+) Reafactor all environmental variables as an example for publish purpose

#

# 20241201 (midnight) v1.9.3

(+) Recreate **"./requirements.txt"** for removing redundant dependencies

(+) Reafactor VoiceChannel.py for Embed support

#

# 20241203 (night) v1.9.4

(-) Removed workflow **"push_to_docker.yml"**

(+) Rewrited **"move_all()"** and **"end"** in **"./general/VoiceChannel.py"** for better resource usuage

(+) Migrated the application to Hetzner Cloud from Microsoft Azure.

(+) Temporarily fixed Lavalink issues for Web playback

(+) Minior code improvement

# 

# 20241206 (midnight) (*) v2.0.0

# Implemented MongoDB database

**(-/+) Rewrited "startup.py" for database integration**

**"./general/Greetings.py"**

(+) Add support for custom welcome messages (default messages remains untouched)

**"./general/ChatGPT.py"**

(+) **"chat_message"** and **"chat_history"** are now completely stored on database instead dictionary from local

(+) Minior code improvement

**"./moderation/Mute.py"** and **"./moderation/Unmute.py"** and **"./general/VoiceChannel.py"**

(+) Mute info are now completely stored on database, including type, ending_time (could be None) etc.

(+) Added a function to handle auto unmute after the time expired. Note this will not work immediately with the application offine. However, the user will be automatically unmuted once the application starts up next time.

**"./general/MessageFiltering.py"** --> **"./moderation/MessageFiltering.py"**

(+) Add support for configuring messages should be deleted on system channel or not on each server

(+) Minior code improvement

#

# 20241215 (midnight) v2.0.1

(-/+) Rewrited MongoDB connection and logic with **"motor_asyncio"**

(+) Improved **"./general/MusicPlayer.py"** for better custom files handling

(-) Removed all plugins directory due to no longer use

#

# 20241220 (night) v2.0.2

(-/+) Rewrite the startup script with full asynchronous approach for maximum resource optimization

(-) Removed multiprocessing

#

# 20241220 (night) v2.0.3 (*)

(+) Fix some minior issues in **"./startup.py"**

**"./general/ChatGPT.py"**

(-/+) Replaced Microsoft Azure OpenAI with OpenAI serivce

(-/+) Refactor error handling for OpenAI API

(-/+) Replaced **"openai.chat.completions"** with **"openai.beta.assistants"** for better integration

(+) Add support for file uploading.

(+) Files uploaded will be stored on OpenAI server side, with the file id stored on database

(-) Remove support for custom prompting due to some predictable issues may occurs

# 20241222 (night) v2.0.6 (*)

**"./general/ChatGPT.py"**

(-/+) Rewrited the message formatter for universal languages support

(-/+) Fix some minior issues in **"./general/ChatGPT.py"**

#

# 20241224 v2.1.0

(+) Fix Overflow error when a livestream is playing

#

# 20250211 v2.1.4

(+) Fix OpenAI issues after switching server

#

# 20250330 (night) v2.1.5 (*)

# IMPORTANT UPDATE

(-/+) Rebranded the bot as another name due to the original bot somehow **got deleted**, and resumed development process

(-) Removed most of the redundant codes and comments

(-/+) Refactor *"root/startup.py"** for another server migration

(+) Updated all env varibles for the new bot

(-/+) Moved the entire application ownership from person to a newly created organization (this repo)

(-/+) Replaced OpenAI serivce token

(+) Minior code improvement

(+) Created multiple backup just in case

#

# 20250401 (afternoon) v2.1.7 (*)

(-/+) Completely rewrited **"root/general/SendFromInput.py"** and renamed it to **"root/general/SendAsBot.py"**, and fixed most of the error handling for this cog

(+) Admin permission is now required for **"root/general/SendAsBot.py"** to work

(+) Minior code improvement

(-/+) Refactor progress will begin soon

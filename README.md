# Discord Music Bot

This is a Discord bot that allows users to search and play music from YouTube in their voice channels. The bot also manages a music queue, can skip to the next song, and displays the current queue.

Feel free to contact me for any doubt: theoalmeida00@gmail.com

## Features

- **Play Music:** Search for a song on YouTube and play it in a voice channel.
- **Queue Management:** Add songs to a queue and skip to the next song.
- **Display Queue:** Show the current list of songs in the queue.
- **Leave Channel:** Disconnect the bot from the voice channel.

## Getting Started

### Prerequisites

- Python 3.8+
- [discord.py](https://pypi.org/project/discord.py/)
- [yt-dlp](https://pypi.org/project/yt-dlp/)
- [yt-yt-search](https://pypi.org/project/youtube-search-python/)

### Discord requisities
- Create a discord application: https://discordjs.guide/preparations/setting-up-a-bot-application.html#creating-your-bot
- Create a server and add the bot: https://umatechnology.org/how-to-create-a-discord-bot-and-add-it-to-your-server/

### Local requisities
- Create a .env file containing:
    1- DISCORD_TOKEN -> your bot token (view the tutorial above)
    2- IMG_FOLDER_PATH -> your local folder containing your images for the bot reaction to messages

You can install the required packages using pip:

```bash
pip install discord.py yt-dlp yt-yt-search

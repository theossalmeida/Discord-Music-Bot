import asyncio
import ctypes.util
import logging
import os
import tempfile
from collections import deque

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("music-bot")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not configured")


def create_cookie_file():
    cookies = os.getenv("YOUTUBE_COOKIES")
    if not cookies:
        return None

    cookie_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    )
    cookie_file.write(cookies)
    cookie_file.close()
    os.chmod(cookie_file.name, 0o600)
    return cookie_file.name


COOKIE_FILE = create_cookie_file()

if not discord.opus.is_loaded():
    opus_library = ctypes.util.find_library("opus")
    if opus_library:
        discord.opus.load_opus(opus_library)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def youtube_options():
    options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
        "retries": 1,
        "extractor_retries": 1,
        # Fall back to the official remote EJS bundle if the packaged solver
        # cannot handle a newly introduced YouTube challenge yet.
        "remote_components": {"ejs:github"},
    }
    if COOKIE_FILE:
        options["cookiefile"] = COOKIE_FILE
    return options


def extract_song(query, *, search):
    target = f"ytsearch1:{query}" if search else query
    options = youtube_options()
    if search:
        # A search only needs a title and video URL. Extracting audio formats at
        # this point runs YouTube's expensive JS challenge twice and can hang.
        options["extract_flat"] = "in_playlist"

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(target, download=False)

    if search:
        entries = info.get("entries") if info else None
        if not entries:
            raise RuntimeError("No YouTube results found")
        info = entries[0]

    if not info:
        raise RuntimeError("YouTube did not return video information")

    webpage_url = info.get("webpage_url") or info.get("original_url")
    if search and not webpage_url:
        result_url = info.get("url")
        webpage_url = (
            result_url
            if result_url and result_url.startswith("http")
            else f"https://www.youtube.com/watch?v={result_url}"
        )
    if not webpage_url:
        webpage_url = query

    if not search and not info.get("url"):
        raise RuntimeError("YouTube did not return an audio stream")
    return {
        "title": info.get("title", "Título desconhecido"),
        "webpage_url": webpage_url,
        "source": info.get("url"),
    }


class MusicPlayer:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = deque()
        self.voice_client = None
        self.text_channel = None
        self.play_task = None

    async def enqueue(self, song, voice_channel, text_channel):
        self.queue.append((song, voice_channel))
        self.text_channel = text_channel
        if not self.voice_client or not self.voice_client.is_playing():
            self.start_next()

    def start_next(self):
        if self.play_task and not self.play_task.done():
            return
        self.play_task = asyncio.create_task(self._play_next())

    async def _play_next(self):
        if not self.queue:
            return

        song, voice_channel = self.queue.popleft()
        try:
            if not self.voice_client or not self.voice_client.is_connected():
                self.voice_client = await voice_channel.connect()
            elif self.voice_client.channel != voice_channel:
                await self.voice_client.move_to(voice_channel)

            # Stream URLs expire, so resolve the URL again immediately before playback.
            refreshed = await asyncio.wait_for(
                asyncio.to_thread(extract_song, song["webpage_url"], search=False),
                timeout=60,
            )
            audio = discord.FFmpegPCMAudio(
                refreshed["source"],
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn",
            )
            self.voice_client.play(audio, after=self._after_track)
            await self.text_channel.send(f'Reproduzindo: {song["title"]}')
        except Exception:
            logger.exception("Failed to play %s in guild %s", song["title"], self.guild_id)
            await self.text_channel.send(
                f'Não consegui reproduzir **{song["title"]}**. Pulando para a próxima.'
            )
            # Schedule after this task has completed so start_next does not see
            # the current task as still active.
            bot.loop.call_soon(self.start_next)

    def _after_track(self, error):
        if error:
            logger.error("FFmpeg playback error in guild %s: %s", self.guild_id, error)
        bot.loop.call_soon_threadsafe(self.start_next)

    async def disconnect(self):
        self.queue.clear()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        self.voice_client = None


players = {}


def get_player(guild):
    return players.setdefault(guild.id, MusicPlayer(guild.id))


@bot.event
async def on_ready():
    logger.info("Connected as %s", bot.user)


@bot.command(name="play", help="Busca e reproduz uma música do YouTube")
async def play(ctx, *, search):
    if not ctx.guild:
        await ctx.send("Este comando só funciona dentro de um servidor.")
        return
    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Você precisa estar em um canal de voz para usar este comando.")
        return

    try:
        logger.info("Searching YouTube for %r in guild %s", search, ctx.guild.id)
        async with ctx.typing():
            song = await asyncio.wait_for(
                asyncio.to_thread(extract_song, search, search=True), timeout=30
            )
        logger.info("YouTube search found %r", song["title"])
        await get_player(ctx.guild).enqueue(
            song, ctx.author.voice.channel, ctx.channel
        )
        await ctx.send(f'Adicionada à fila: {song["title"]}')
    except asyncio.TimeoutError:
        logger.error("YouTube search timed out for %r", search)
        await ctx.send("O YouTube demorou demais para responder. Tente novamente.")
    except Exception:
        logger.exception("YouTube search failed for %r", search)
        await ctx.send("Houve um problema ao buscar essa música no YouTube.")


@bot.command(name="next", aliases=["skip"], help="Pula a música atual")
async def skip_track(ctx):
    player = players.get(ctx.guild.id) if ctx.guild else None
    if player and player.voice_client and player.voice_client.is_playing():
        # stop() invokes the after callback, which starts exactly one next track.
        player.voice_client.stop()
        await ctx.send("Música pulada.")
    else:
        await ctx.send("Não há nenhuma música sendo reproduzida no momento.")


@bot.command(name="fila", aliases=["queue"], help="Mostra as músicas na fila")
async def show_queue(ctx):
    player = players.get(ctx.guild.id) if ctx.guild else None
    if not player or not player.queue:
        await ctx.send("A fila está vazia.")
        return
    titles = [song["title"] for song, _ in player.queue]
    await ctx.send("Fila de músicas:\n" + "\n".join(
        f"{index}. {title}" for index, title in enumerate(titles, start=1)
    ))


@bot.command(name="leave", help="Desconecta o bot do canal de voz")
async def leave(ctx):
    player = players.get(ctx.guild.id) if ctx.guild else None
    if not player or not player.voice_client or not player.voice_client.is_connected():
        await ctx.send("O bot não está conectado a nenhum canal de voz.")
        return
    await player.disconnect()
    await ctx.send("Tô indo embora...")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Use `!play nome da música`.")
        return
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error("Command error", exc_info=error)
    await ctx.send("Ocorreu um erro ao executar o comando.")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN, log_handler=None)

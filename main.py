import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os
from load_dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    print('Please make sure you have DISCORD_TOKEN on your .env file')
    print('Por favor, certifique-se que a variável DISCORD_TOKEN está corretamente salva no .env')
    raise Exception

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Class to manage music queue
class MusicQueue:
    def __init__(self):
        self.queue = []
        self.is_playing = False
        self.vc = None

    def add_to_queue(self, song, channel):
        self.queue.append((song, channel))

    def get_next_song(self):
        if self.queue:
            return self.queue.pop(0)
        return None

    def clear_queue(self):
        self.queue = []

    def get_queue_titles(self):
        return [song['title'] for song, _ in self.queue]

music_queue = MusicQueue()

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    # Send message in discord chat when bot is turned on
    for guild in bot.guilds:
        text_channel = guild.text_channels[0]
        # await text_channel.send(file=discord.File(os.path.join(images_folder, 'welcome.png')), content="Rei Macaco na área!")
        await text_channel.send(content="Rei Macaco na área!")

@bot.command(name='play', help='Busca e reproduz uma música do YouTube')
async def play(ctx, *, search):
    # Warning if user enter command without being on a voice channel
    if not ctx.author.voice:
        await ctx.send("Você precisa estar em um canal de voz para usar este comando.")
        return

    channel = ctx.author.voice.channel

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f'ytsearch1:{search}', download=False)
            info = info['entries'][0]
            for fmt in info['formats']:
                if fmt['ext'] == 'm4a':
                    song = {'source': fmt['url'], 'title': info['title']}
                    break
            else:
                song = {'source': info['formats'][0]['url'], 'title': info['title']}
            print(f'Playing URL: {song["source"]}')
            music_queue.add_to_queue(song, channel)

            await ctx.send(content=f'Adicionada à fila: {song["title"]}')

            if not music_queue.is_playing:
                await play_next(ctx)
        except Exception as e:
            print(f'Erro ao buscar/extrair música: {e}')
            await ctx.send(content="Houve um problema ao tentar buscar a música.")

async def play_next(ctx):
    next_song = music_queue.get_next_song()
    if next_song:
        music_queue.is_playing = True
        song, channel = next_song

        if music_queue.vc is None or not music_queue.vc.is_connected():
            music_queue.vc = await channel.connect()
        else:
            await music_queue.vc.move_to(channel)

        music_queue.vc.play(discord.FFmpegPCMAudio(
            song['source'],  
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", 
            options="-vn -bufsize 64k"
        ), after=lambda e: bot.loop.create_task(play_next(ctx)))
        await ctx.send(f'Reproduzindo: {song["title"]}')
    else:
        music_queue.is_playing = False

@bot.command(name='next', help='Pula a música atual e reproduz a próxima da fila')
async def next(ctx):
    if music_queue.vc and music_queue.vc.is_playing():
        music_queue.vc.stop()  # after callback will call play_next automatically
    else:
        await ctx.send("Não há nenhuma música sendo reproduzida no momento.")

@bot.command(name='fila', help='Mostra as músicas na fila')
async def fila(ctx):
    # Function to show all musics in queue
    queue_titles = music_queue.get_queue_titles()
    if queue_titles:
        queue_list = "\n".join([f"{i+1}. {title}" for i, title in enumerate(queue_titles)])
        await ctx.send(f"Fila de músicas:\n{queue_list}")
    else:
        await ctx.send("A fila está vazia.")

@bot.command(name='leave', help='Desconecta o bot do canal de voz')
async def leave(ctx):
    # Bot send a good bye message when disconnected
    if music_queue.vc:
        await music_queue.vc.disconnect()
        music_queue.clear_queue()
        music_queue.is_playing = False
        await ctx.send("To indo embora...")
    else:
        await ctx.send("O bot não está conectado a nenhum canal de voz.")

bot.run(DISCORD_TOKEN)

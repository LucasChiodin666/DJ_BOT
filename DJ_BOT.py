import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()  # Cargar variables de entorno desde .env
TOKEN = os.getenv('DISCORD_TOKEN')


# Configurar el registro
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, case_insensitive=True)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class MusicPlayer:
    def __init__(self, ctx):
        self.ctx = ctx
        self.voice_client = ctx.voice_client
        self.queue = []
        self.current_song = None
        self.is_playing = False

    async def play_next(self):
        if len(self.queue) > 0:
            self.current_song = self.queue.pop(0)
            self.is_playing = True
            try:
                self.voice_client.play(self.current_song, after=self.after_song)
                embed = discord.Embed(title="Sacudamos la maraca con :", description=f"**{self.current_song.title}**", color=discord.Color.blue())
                await self.ctx.send(embed=embed)
            except Exception as e:
                await self.ctx.send(f"An error occurred while playing the song: {str(e)}")
                self.is_playing = False
                await self.play_next()
        else:
            self.is_playing = False

    def after_song(self, error):
        if error:
            asyncio.run_coroutine_threadsafe(self.ctx.send(f"An error occurred: {str(error)}"), self.ctx.bot.loop)
        future = asyncio.run_coroutine_threadsafe(self.play_next(), self.ctx.bot.loop)
        try:
            future.result()
        except Exception as e:
            logging.error(f"Error in after_song: {e}")

    async def add_to_queue(self, url):
        try:
            data = await self.ctx.bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if 'url' in data:
                filename = data['url']
            elif 'formats' in data and len(data['formats']) > 0:
                filename = data['formats'][0]['url']
            else:
                await self.ctx.send("Error, no puedo extraer el audio del link.")
                return

            source = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
            song = discord.PCMVolumeTransformer(source)
            song.title = data.get('title')
            song.uploader = data.get('uploader')
            song.duration = data.get('duration')
            song.url = data.get('webpage_url')
            self.queue.append(song)

            if not self.is_playing:
                await self.play_next()
            else:
                embed = discord.Embed(title="Agregado a la lista de canciones", description=f"**{song.title}**", color=discord.Color.green())
                await self.ctx.send(embed=embed)
        except youtube_dl.utils.DownloadError as e:
            error_message = str(e)
            await self.ctx.send(f"Hubo un error mientras cargaba la cancion a la lista: {error_message}")
            logging.error(f"Error en agregar: {error_message}")
        except Exception as e:
            await self.ctx.send(f"An unexpected error occurred: {str(e)}")
            logging.error(f"Error en agregar a la lista: {e}")

    async def skip(self):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await self.ctx.send('**BAI BAI POOTA.**')
        else:
            await self.ctx.send('**No hay cancion en reproduccion.**')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='join', help='Joins a voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("{} para llamarme, primero conectate a un canal de voz".format(ctx.message.author.name))
        return
    else:
        channel = ctx.message.author.voice.channel

    await channel.connect()
    await ctx.send(f'Ya llegue estupidas, espero no causar conflicto con mi presencia de alto impacto. :zap:')

    if ctx.voice_client:
        ctx.voice_client.music_player = MusicPlayer(ctx)

@bot.command(name='leave', help='Leaves a voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send('Left the voice channel.')
    else:
        await ctx.send("The bot is not connected to a voice channel.")

@bot.command(name='play', aliases=['p'], help='Plays a song')  # Añadir alias 'p'
async def play(ctx, url):
    if not ctx.voice_client:
        await join(ctx)

    await ctx.voice_client.music_player.add_to_queue(url)

@bot.command(name='skip', aliases=['s'], help='Skips the current song')  # Añadir alias 's'
async def skip(ctx):
    if ctx.voice_client:
        await ctx.voice_client.music_player.skip()
    else:
        await ctx.send('**Not connected to a voice channel.**')

@bot.command(name='lista', help='Shows the current queue')
async def lista(ctx):
    if ctx.voice_client and ctx.voice_client.music_player.queue:
        queue_list = '\n'.join([f'{index + 1}. [{song.title}]({song.url})' for index, song in enumerate(ctx.voice_client.music_player.queue)])
        embed = discord.Embed(title="Lista de Canciones en cola:", description=queue_list, color=discord.Color.orange())
        await ctx.send(embed=embed)
    else:
        await ctx.send('**La lista de canciones esta vacia, sos tontite? **')

@bot.command(name='pausa', help='Pauses the current song')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('S T O P B I T C H.')
    else:
        await ctx.send('Ya estamos en pausa, sos tontite?.')

@bot.command(name='reanudar', help='Resumes the paused song')
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send('QUE NO PARE LA JODA.')
    else:
        await ctx.send('La cancion no está en pausa.')

@bot.command(name='limpiar', help='Stops the current song and clears the queue')
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        ctx.voice_client.music_player.queue = []
        await ctx.send('SE TERMINO EL BOLICHE LOCO.')
    else:
        await ctx.send('No hay nada para limpiar, el qlo limpiate.')

# Cambiar el token aquí a partir de la variable de entorno
bot.run(os.getenv('TOKEN'))


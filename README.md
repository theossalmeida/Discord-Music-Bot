# Discord Music Bot

Bot pessoal que busca músicas no YouTube, reproduz em canais de voz e mantém
uma fila separada para cada servidor.

## Comandos

- `!play <música>` — busca e adiciona uma música à fila
- `!next` / `!skip` — pula a música atual
- `!fila` / `!queue` — mostra a fila
- `!leave` — limpa a fila e desconecta o bot

## Desenvolvimento local

Requer Python 3.11+, FFmpeg e libopus.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crie um `.env` (ele não deve ser commitado):

```dotenv
DISCORD_TOKEN=seu_token
# Opcional: conteúdo completo de um arquivo Netscape cookies.txt
YOUTUBE_COOKIES=
```

Ative também o **Message Content Intent** na página do bot no Discord Developer
Portal. Depois execute `python main.py`.

## Fly.io

O bot é um processo worker e não precisa expor portas HTTP. Configure os secrets
e faça o deploy a partir da pasta do projeto:

```bash
fly secrets set DISCORD_TOKEN='seu_token'
fly deploy
```

Se o YouTube exigir autenticação, salve o conteúdo do arquivo de cookies como
secret sem colocá-lo na imagem:

```bash
fly secrets set YOUTUBE_COOKIES="$(cat youtube_cookies.txt)"
```

Use uma única Machine para evitar duas instâncias do mesmo bot:

```bash
fly scale count 1
```

A Machine usa 512 MB de memória. O processo combina Python, yt-dlp, Deno e
FFmpeg; 256 MB pode fazer o kernel encerrar o bot por falta de memória.

O arquivo local `youtube_cookies.txt` e o `.env` são ignorados pelo Git e pelo
Docker. Cookies do YouTube expiram e precisam ser renovados periodicamente.
O container instala Deno e `yt-dlp-ejs`, necessários para os desafios
JavaScript atuais do YouTube.

import os
import discord
from discord.ext import commands

# 環境変数からDiscordのトークンだけを読み込む
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Discord Botの基本設定
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # 接続に成功したらRenderのログにこれが表示される
    print(f"やったぜ！ {bot.user.name} としてDiscordに接続成功したよ！")

if __name__ == "__main__":
    if not TOKEN:
        print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
    else:
        bot.run(TOKEN)



import os
import discord
from discord import app_commands
from discord.ui import Select, View, Modal, TextInput

# ----------------- 設定 -----------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# ⚠️ ここをご自身の管理者チャンネルID（数字だけ）に書き換えてください！
ADMIN_CHANNEL_ID = 1521944800973029576
# ----------------------------------------

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

ITEMS = {
    "item1": {"name": "PAYPAY残高1-2万円", "price": 1900},
    "item2": {"name": "PAYPAY残高3-5万円", "price": 2400},
    "item3": {"name": "PAYPAY残高6-7万円", "price": 3200},
    "item4": {"name": "paypay1万円-2万円 本人確認済み", "price": 3000},
    "item5": {"name": "paypay3万円-5万円 本人確認済み", "price": 4000},
}

# --- 最終ステップ：PayPayリンクを入力する画面 ---
class PayPayModal(Modal):
    def __init__(self, item_name, count, total_price):
        super().__init__(title=f"{item_name} を購入")
        self.item_name = item_name
        self.count = count
        self.total_price = total_price

        self.link_input = TextInput(
            label="PayPay送金リンク（必須）",
            placeholder="https://pay.paypay.ne.jp/XXXXXX",
            required=True
        )
        self.pwd_input = TextInput(
            label="送金リンクのパスワード",
            placeholder="なしなら入力しない",
            required=False
        )
        self.add_item(self.link_input)
        self.add_item(self.pwd_input)

    async def on_submit(self, interaction: discord.Interaction):
        # 💡 まず「考え中...」のサインを出して3秒ルールを突破する
        await interaction.response.defer(ephemeral=True)

        admin_channel = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_channel:
            embed = discord.Embed(title="💰 【新規購入申請】 💰", color=discord.Color.green())
            embed.add_field(name="購入者", value=interaction.user.mention, inline=False)
            embed.add_field(name="商品名", value=self.item_name, inline=True)
            embed.add_field(name="個数", value=f"{self.count} 個", inline=True)
            embed.add_field(name="合計金額", value=f"{self.total_price} 円", inline=True)
            embed.add_field(name="PayPayリンク", value=self.link_input.value, inline=False)
            embed.add_field(name="パスワード", value=self.pwd_input.value or "なし", inline=False)
            await admin_channel.send(embed=embed)

            # 送信が完了したらユーザーに伝える
            await interaction.followup.send(
                f"【購入申請を受け付けました】\nスタッフが確認後、3分前後に商品をお渡ししますのでお待ちください！",
                ephemeral=True
            )
        else:
            await interaction.followup.send("エラー：管理者チャンネルが見つかりませんでした。", ephemeral=True)

# --- 第2ステップ：個数を選ぶメニュー ---
class CountSelect(Select):
    def __init__(self, item_key):
        self.item_key = item_key
        item = ITEMS[item_key]
        
        options = [
            discord.SelectOption(label=f"購入数: {i}個", value=str(i), description=f"合計金額: {item['price'] * i}円")
            for i in range(1, 11)  # 10個まで選べるようにしました
        ]
        super().__init__(placeholder="個数を選択してください", options=options)

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        item = ITEMS[self.item_key]
        total_price = item["price"] * count
        
        # モーダルを開くときは即座に反応する必要があるため、そのまま送る
        await interaction.response.send_modal(PayPayModal(item["name"], count, total_price))

# --- 第1ステップ：商品を選ぶメニュー ---
class ItemSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=data["name"], value=key, description=f"値段: {data['price']}円")
            for key, data in ITEMS.items()
        ]
        super().__init__(placeholder="ここから選択", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 💡 ここでも一度「考え中」の対応をしてから次のメニューを出す
        view = View()
        view.add_item(CountSelect(self.values[0]))
        await interaction.response.send_message("購入数を選んでください", view=view, ephemeral=True)

class StartView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ItemSelect())

@bot.tree.command(name="vending", description="自販機メニューを表示します")
async def vending(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏪 自動販売機",
        description="ボタンを押して購入！在庫がないものはチケットまで！",
        color=discord.Color.blue()
    )
    for key, data in ITEMS.items():
        embed.add_field(name=data["name"], value=f"値段: {data['price']}円", inline=False)
        
    await interaction.response.send_message(embed=embed, view=StartView())

# ダミーサーバー
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def run_dummy_server():
    class MyHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
    # 他のプロセスとぶつかりにくいポートに変更
    server = HTTPServer(("0.0.0.0", 10000), MyHandler)
    server.serve_forever()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()
    bot.run(TOKEN)

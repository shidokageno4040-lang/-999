import os
import discord
from discord import app_commands
from discord.ui import Select, View, Modal, TextInput
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# ----------------- 設定 -----------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 管理者用チャンネルID
ADMIN_CHANNEL_ID = 1521944800973029576

# 実績ログ用チャンネルID
LOG_CHANNEL_ID = 1520748892742746174
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
    "item1": {"name": "PAYPAY残高1-2万円", "price": 1500},
    "item2": {"name": "PAYPAY残高3-5万円", "price": 2000},
    "item3": {"name": "PAYPAY残高6-7万円", "price": 3000},
    "item4": {"name": "paypay1万円-2万円 本人確認済み", "price": 3000},
    "item5": {"name": "paypay3万円-5万円 本人確認済み", "price": 4000},
}

async def send_achievement_embed(buyer_name, item_info, comment):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="🟢 新着実績", color=discord.Color.from_rgb(47, 49, 54))
        embed.add_field(name="👤 購入者", value=buyer_name, inline=False)
        embed.add_field(name="📦 商品・内容", value=item_info, inline=False)
        embed.add_field(name="💬 コメント", value=comment or "なし", inline=False)
        await log_channel.send(embed=embed)
        return True
    return False

class UserReviewModal(Modal):
    def __init__(self, item_name, count):
        super().__init__(title="実績の投稿")
        self.item_name = item_name
        self.count = count
        
        self.comment_input = TextInput(
            label="コメント",
            placeholder="詐欺なしでこれは神！など",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.comment_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        item_info = f"{self.item_name} ×{self.count}"
        
        success = await send_achievement_embed(interaction.user.name, item_info, self.comment_input.value)
        if success:
            await interaction.followup.send("実績を投稿しました！ありがとうございます！✨", ephemeral=True)
        else:
            await interaction.followup.send("エラー：実績チャンネルが見つかりませんでした。", ephemeral=True)

# 購入者のDMに送信される実績投稿用のView（ボタンが無効化できるように改修）
class OpenReviewView(View):
    def __init__(self, item_name, count):
        super().__init__(timeout=None) # 管理者が手動で切るまでタイムアウトしない設定
        self.item_name = item_name
        self.count = count

    @discord.ui.button(label="🌟 実績を入力して投稿する", style=discord.ButtonStyle.primary, custom_id="open_review_btn")
    async def open_modal_btn(self, act_interaction: discord.Interaction, btn: discord.ui.Button):
        await act_interaction.response.send_modal(UserReviewModal(self.item_name, self.count))


class AdminApproveView(View):
    def __init__(self, buyer_id, item_name, count):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id
        self.item_name = item_name
        self.count = count
        self.dm_message = None  # 購入者に送ったDMのメッセージを保持

    @discord.ui.button(label="✅ 実績投稿を許可する", style=discord.ButtonStyle.success)
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        buyer = await bot.fetch_user(self.buyer_id)
        if buyer:
            review_view = OpenReviewView(self.item_name, self.count)
            try:
                # DMメッセージを保持しておく
                self.dm_message = await buyer.send(
                    f"【Sanctuary《聖域》よりお知らせ】\n先ほどご購入いただいた「{self.item_name}」の実績投稿が許可されました！\n以下のボタンからぜひ実績の投稿をお願いします！✨",
                    view=review_view
                )
                
                button.disabled = True
                button.label = "許可済み"
                await interaction.message.edit(view=self)
                
                await interaction.followup.send(f"{buyer.name} さんに実績投稿の案内DMを送信しました！", ephemeral=True)
            except Exception:
                await interaction.followup.send("購入者のDMが閉じられているため、通知を送れませんでした。サーバー内で手動で案内してください。", ephemeral=True)
        else:
            await interaction.followup.send("ユーザーが見つかりませんでした。", ephemeral=True)

    # ------------------ 追加：管理者が実績投稿を切る（締め切る）ボタン ------------------
    @discord.ui.button(label="🔒 実績投稿を切る（締め切り）", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # DMが送られている場合はDM側のボタンを無効化（無効表示）に変更する
        if self.dm_message:
            try:
                disabled_view = View()
                disabled_btn = discord.ui.Button(label="❌ 実績投稿の受付は終了しました", style=discord.ButtonStyle.secondary, disabled=True)
                disabled_view.add_item(disabled_btn)
                await self.dm_message.edit(content=f"【お知らせ】「{self.item_name}」の実績投稿の受け付けは終了（無効化）されました。", view=disabled_view)
            except Exception:
                pass # すでにDMが消されているなどの場合はスルー

        # 管理者チャンネル側のボタンも無効化・見た目を変更
        for item in self.children:
            item.disabled = True
        button.label = "締め切り済み"
        await interaction.message.edit(view=self)
        
        await interaction.followup.send("実績投稿の受付を切りました（購入者の投稿ボタンが無効化されました）。", ephemeral=True)


class PayPayModal(Modal):
    def __init__(self, item_name, count, total_price):
        super().__init__(title=f"{item_name} を購入")
        self.item_name = item_name
        self.count = count
        self.total_price = total_price

        self.link_input = TextInput(label="PayPay送金リンク（必須）", placeholder="https://pay.paypay.ne.jp/XXXXXX", required=True)
        self.pwd_input = TextInput(label="送金リンクのパスワード", placeholder="なしなら入力しない", required=False)
        self.add_item(self.link_input)
        self.add_item(self.pwd_input)

    async def on_submit(self, interaction: discord.Interaction):
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
            
            await admin_channel.send(
                embed=embed, 
                view=AdminApproveView(interaction.user.id, self.item_name, self.count)
            )

            await interaction.followup.send(
                f"【購入申請を受け付けました】\nスタッフが確認後、商品をお渡ししますのでお待ちください！",
                ephemeral=True
            )
        else:
            await interaction.followup.send("エラー：管理者チャンネルが見つかりませんでした。", ephemeral=True)

class CountSelect(Select):
    def __init__(self, item_key):
        self.item_key = item_key
        item = ITEMS[item_key]
        options = [discord.SelectOption(label=f"購入数: {i}個", value=str(i), description=f"合計金額: {item['price'] * i}円") for i in range(1, 6)]
        super().__init__(placeholder="個数を選択してください", options=options)

    async def callback(self, interaction: discord.Interaction):
        count = int(self.values[0])
        item = ITEMS[self.item_key]
        await interaction.response.send_modal(PayPayModal(item["name"], count, item["price"] * count))

class ItemSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=data["name"], value=key, description=f"値段: {data['price']}円") for key, data in ITEMS.items()]
        super().__init__(placeholder="ここから選択", options=options)

    async def callback(self, interaction: discord.Interaction):
        view = View()
        view.add_item(CountSelect(self.values[0]))
        await interaction.response.send_message("購入数を選んでください", view=view, ephemeral=True)

class StartView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ItemSelect())

@bot.tree.command(name="vending", description="自販機メニューを表示します")
async def vending(interaction: discord.Interaction):
    embed = discord.Embed(title="🏪 自動販売機", description="メニューを選択して購入してください。", color=discord.Color.blue())
    for key, data in ITEMS.items():
        embed.add_field(name=data["name"], value=f"値段: {data['price']}円", inline=False)
    await interaction.response.send_message(embed=embed, view=StartView())

@bot.tree.command(name="jissteki_proxy", description="【管理者専用】購入者の代わりに実績を代理投稿します")
@app_commands.describe(
    buyer="購入者の名前、またはメン

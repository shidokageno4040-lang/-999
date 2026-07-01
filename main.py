

def set_config(key: str, value: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
    )
    con.commit()
    con.close()

def get_all_products() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM products ORDER BY id")
    rows = cur.fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_product(product_id: int) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None

def add_product(name: str, price: int) -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO products (name, price) VALUES (?, ?)", (name, price))
    con.commit()
    product_id = cur.lastrowid
    con.close()
    return product_id

def update_product_field(product_id: int, field: str, value):
    allowed = {"name", "price", "stock", "paypay_link", "product_content"}
    if field not in allowed:
        raise ValueError(f"Invalid field: {field}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
    con.commit()
    con.close()

def decrement_product_stock(product_id: int) -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    if not row or row[0] <= 0:
        con.close()
        raise ValueError("在庫不足")
    new_stock = row[0] - 1
    cur.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    con.commit()
    con.close()
    return new_stock

def delete_product(product_id: int):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("DELETE FROM products WHERE id = ?", (product_id,))
    con.commit()
    con.close()

# ---------------------------------------------------------------------------
# Bot setup (「け.」の部分を正しい「commands」へ修正しました)
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class AdminApprovalView(discord.ui.View):
    def __init__(self, buyer: discord.User, product_id: int):
        super().__init__(timeout=None)
        self.buyer = buyer
        self.product_id = product_id

    @discord.ui.button(label="認証 (Approve)", style=discord.ButtonStyle.green)
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message(
                "このボタンは管理者のみ使用できます。", ephemeral=True
            )
            return

        product = get_product(self.product_id)
        if not product:
            await interaction.response.send_message(
                "商品が見つかりません。", ephemeral=True
            )
            return

        try:
            new_stock = decrement_product_stock(self.product_id)
        except ValueError:
            await interaction.response.send_message(
                "在庫が不足しているため承認できません。", ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        content = product["product_content"] or "（商品内容が設定されていません）"
        try:
            await self.buyer.send(
                f"✅ **お支払いが確認されました！**\n\n"
                f"ご購入ありがとうございます。\n"
                f"**商品名:** {product['name']}\n\n"
                f"以下の商品をお届けします。\n\n"
                f">>> {content}"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                f"承認しましたが、{self.buyer.mention} へのDM送信に失敗しました（DMが無効の可能性があります）。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"✅ {self.buyer.mention} の **{product['name']}** 購入を承認しました。残在庫: **{new_stock}**",
            ephemeral=True,
        )

    @discord.ui.button(label="却下 (Reject)", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message(
                "このボタンは管理者のみ使用できます。", ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        try:
            await self.buyer.send(
                "❌ **お支払いを確認できませんでした。**\n\n"
                "お支払いの確認ができなかったため、購入が承認されませんでした。\n"
                "ご不明な点がございましたら、管理者にお問い合わせください。"
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"❌ {self.buyer.mention} の購入を却下しました。", ephemeral=True
        )


class ReportPaymentView(discord.ui.View):
    def __init__(self, buyer: discord.User, product_id: int):
        super().__init__(timeout=300)
        self.buyer = buyer
        self.product_id = product_id

    @discord.ui.button(
        label="支払い完了を報告 (Report Payment)", style=discord.ButtonStyle.green
    )
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.NotFound:
            pass

        product = get_product(self.product_id)
        product_name = product["name"] if product else "不明な商品"

        admin = await bot.fetch_user(ADMIN_USER_ID)
        approval_view = AdminApprovalView(buyer=self.buyer, product_id=self.product_id)

        embed = discord.Embed(
            title="💳 支払い報告",
            description=(
                f"{self.buyer.mention} (`{self.buyer}` / ID: `{self.buyer.id}`) "
                f"が支払い完了を報告しました。"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="商品", value=product_name, inline=True)
        embed.add_field(
            name="承認 or 却下", value="下のボタンを押してください。", inline=False
        )

        try:
            await admin.send(embed=embed, view=approval_view)
        except discord.Forbidden:
            await interaction.response.send_message(
                "管理者へのDM送信に失敗しました。管理者のDMが無効になっている可能性があります。",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "✅ 支払い報告を送信しました。管理者の確認をお待ちください。",
            ephemeral=True,
        )


class ProductSelectForPurchase(discord.ui.Select):
    def __init__(self, products: list[dict] | None = None):
        if products is None:
            products = get_all_products()
        options = [
            discord.SelectOption(
                label=p["name"],
                description=f"値段: {p['price']:,}円　在庫: {p['stock']}個",
                value=str(p["id"]),
            )
            for p in products
            if p["stock"] > 0
        ] or [discord.SelectOption(label="在庫なし", value="none", default=True)]
        super().__init__(
            placeholder="購入する商品を選んでください",
            options=options,
            custom_id="shop_purchase_select",
            disabled=(not any(p["stock"] > 0 for p in products)),
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "現在在庫のある商品がありません。", ephemeral=True
            )
            return
        product_id = int(self.values[0])
        product = get_product(product_id)
        if not product or product["stock"] <= 0:
            await interaction.response.send_message(
                "この商品は現在在庫がありません。", ephemeral=True
            )
            return
        paypay = product["paypay_link"] or "（PayPayリンク未設定）"
        embed = discord.Embed(
            title=f"💳 {product['name']} を購入する",
            description=(
                f"**値段:** {product['price']:,}円\n\n"
                f"以下のリンクからお支払いください。\n\n"
                f"**[PayPayで支払う]({paypay})**\n\n"
                f"お支払い完了後、下のボタンを押して報告してください。"
            ),
            color=discord.Color.green(),
        )
        view = ReportPaymentView(buyer=interaction.user, product_id=product_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ProductSelectForStock(discord.ui.Select):
    def __init__(self, products: list[dict] | None = None):
        if products is None:
            products = get_all_products()
        options = [
            discord.SelectOption(
                label=p["name"],
                description=f"値段: {p['price']:,}円",
                value=str(p["id"]),
            )
            for p in products
        ] or [discord.SelectOption(label="商品なし", value="none")]
        super().__init__(
            placeholder="在庫を確認する商品を選んでください",
            options=options,
            custom_id="shop_stock_select",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message(
                "商品が登録されていません。", ephemeral=True
            )
            return
        product = get_product(int(self.values[0]))
        if not product:
            await interaction.response.send_message(
                "商品が見つかりません。", ephemeral=True
            )
            return
        status = "✅ 在庫あり" if product["stock"] > 0 else "❌ 在庫なし"
        await interaction.response.send_message(
            f"**{product['name']}**\n値段: {product['price']:,}円\n在庫数: **{product['stock']}** 個\n{status}",
            ephemeral=True,
        )


class ShopView(discord.ui.View):
    def __init__(self, products: list[dict] | None = None):
        super().__init__(timeout=None)
        self.add_item(ProductSelectForPurchase(products))
        self.add_item(ProductSelectForStock(products))

    @discord.ui.button(
        label="在庫確認",
        style=discord.ButtonStyle.blurple,
        custom_id="shop_stock_check",
    )
    async def check_all_stock(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        products = get_all_products()
        if not products:
            await interaction.response.send_message(
                "商品が登録されていません。", ephemeral=True
            )
            return
        lines = []
        for p in products:
            icon = "✅" if p["stock"] > 0 else "❌"
            lines.append(
                f"{icon} **{p['name']}** — {p['price']:,}円 (在庫: {p['stock']})"
            )
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def admin_only(ctx):
    return ctx.author.id == ADMIN_USER_ID

# --- 新機能: Gemini AI チャットコマンド ---
@bot.command(name="ai")
async def ai_chat(ctx, *, prompt: str):
    """!ai <質問内容> — Geminiに質問する"""
    if not GEMINI_API_KEY:
        await ctx.send("エラー: GeminiのAPIキーが設定されていません。")
        return

    async with ctx.typing():
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            # Discordの文字数制限(2000字)対策
            if len(response.text) > 2000:
                await ctx.send(response.text[:1990] + "...")
            else:
                await ctx.send(response.text)
        except Exception as e:
            await ctx.send(f"Geminiでの生成中にエラーが発生しました: {e}")

@bot.command(name="shop")
async def shop(ctx):
    products = get_all_products()
    embed = discord.Embed(
        title="🛒 自動販売機",
        description="ボタンを押して購入！在庫がないものはチケットまで！",
        color=discord.Color.blurple(),
    )
    if products:
        for p in products:
            stock_text = f"在庫: {p['stock']}個" if p["stock"] > 0 else "**売り切れ**"
            embed.add_field(
                name=p["name"],
                value=f"値段：{p['price']:,}円　|　{stock_text}",
                inline=False,
            )
    else:
        embed.description = "現在登録されている商品がありません。"

    await ctx.send(embed=embed, view=ShopView())


@bot.command(name="addproduct")
async def addproduct(ctx, price: int, *, name: str):
    """!addproduct <price> <name> — 新商品を追加"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product_id = add_product(name, price)
    await ctx.send(
        f"✅ 商品を追加しました。\n"
        f"**ID:** `{product_id}` | **名前:** {name} | **値段:** {price:,}円\n\n"
        f"次に在庫・PayPayリンク・商品内容を設定してください：\n"
        f"`!setstock {product_id} <在庫数>`\n"
        f"`!setpaypay {product_id} <URL>`\n"
        f"`!setproduct {product_id} <商品内容>`"
    )


@bot.command(name="removeproduct")
async def removeproduct(ctx, product_id: int):
    """!removeproduct <id> — 商品を削除"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品見つかりません。")
        return
    delete_product(product_id)
    await ctx.send(f"✅ **{product['name']}** (ID: {product_id}) を削除しました。")


@bot.command(name="setstock")
async def setstock(ctx, product_id: int, quantity: int):
    """!setstock <id> <quantity> — 在庫数を設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品が見つかりません。")
        return
    if quantity < 0:
        await ctx.send("在庫数は0以上を指定してください。")
        return
    update_product_field(product_id, "stock", quantity)
    await ctx.send(f"✅ **{product['name']}** の在庫を **{quantity}** に設定しました。")


@bot.command(name="setallstock")
async def setallstock(ctx, quantity: int):
    """!setallstock <quantity> — 全商品の在庫を一括設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    if quantity < 0:
        await ctx.send("在庫数は0以上を指定してください。")
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE products SET stock = ?", (quantity,))
    count = cur.rowcount
    con.commit()
    con.close()
    await ctx.send(f"✅ 全 **{count}** 商品の在庫を **{quantity}** に設定しました。")


@bot.command(name="setprice")
async def setprice(ctx, product_id: int, price: int):
    """!setprice <id> <price> — 値段を設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品が見つかりません。")
        return
    update_product_field(product_id, "price", price)
    await ctx.send(
        f"✅ **{product['name']}** の値段を **{price:,}円** に設定しました。"
    )


@bot.command(name="setallpaypay")
async def setallpaypay(ctx, link: str):
    """!setallpaypay <url> — 全商品のPayPayリンクを一括設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    if not link.startswith("http"):
        await ctx.send(
            "有効なURLを指定してください（http:// または https:// で始まるもの）。"
        )
        return
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE products SET paypay_link = ?", (link,))
    count = cur.rowcount
    con.commit()
    con.close()
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(
        f"✅ 全 **{count}** 商品のPayPayリンクを一括設定しました。（メッセージは削除されました）"
    )


@bot.command(name="setpaypay")
async def setpaypay(ctx, product_id: int, link: str):
    """!setpaypay <id> <url> — PayPayリンクを設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品が見つかりません。")
        return
    update_product_field(product_id, "paypay_link", link)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(
        f"✅ **{product['name']}** のPayPayリンクを設定しました。（メッセージは削除されました）"
    )


@bot.command(name="setproduct")
async def setproduct(ctx, product_id: int, *, content: str):
    """!setproduct <id> <content> — 承認後に送る商品内容を設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品が見つかりません。")
        return
    update_product_field(product_id, "product_content", content)
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await ctx.send(
        f"✅ **{product['name']}** の商品内容を設定しました。（メッセージは削除されました）"
    )


@bot.command(name="setname")
async def setname(ctx, product_id: int, *, name: str):
    """!setname <id> <name> — 商品名を変更"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    product = get_product(product_id)
    if not product:
        await ctx.send(f"ID `{product_id}` の商品が見つかりません。")
        return
    update_product_field(product_id, "name", name)
    await ctx.send(f"✅ 商品名を **{name}** に変更しました。")


@bot.command(name="products")
async def products(ctx):
    """!products — 全商品一覧（管理者用）"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    products_list = get_all_products()
    if not products_list:
        await ctx.send(
            "商品が登録されていません。`!addproduct <値段> <商品名>` で追加してください。"
        )
        return
    embed = discord.Embed(
        title="📦 商品一覧（管理者）", color=discord.Color.og_blurple()
    )
    for p in products_list:
        paypay_set = "✅ 設定済み" if p["paypay_link"] else "❌ 未設定"
        product_set = "✅ 設定済み" if p["product_content"] else "❌ 未設定"
        embed.add_field(
            name=f"[ID: {p['id']}] {p['name']}",
            value=(
                f"値段: {p['price']:,}円　|　在庫: {p['stock']}\n"
                f"PayPay: {paypay_set}　|　商品内容: {product_set}"
            ),
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="setshop")
async def setshop(ctx, channel_id: int, mode: str):
    """!setshop <channel_id> <edit|repost|remove> — ショップチャンネルを設定"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    mode = mode.lower()
    if mode not in ("edit", "repost", "remove"):
        await ctx.send(
            "モードは `edit`、`repost`、`remove` のいずれかを指定してください。\n"
            "`edit` = 既存メッセージを更新 | `repost` = 削除して新規投稿 | `remove` = チャンネル削除"
        )
        return
    if mode == "remove":
        set_config(f"shop_channel_mode_{channel_id}", "")
        if channel_id in EDIT_CHANNEL_IDS:
            EDIT_CHANNEL_IDS.remove(channel_id)
        if channel_id in REPOST_CHANNEL_IDS:
            REPOST_CHANNEL_IDS.remove(channel_id)
        await ctx.send(
            f"✅ チャンネル `{channel_id}` をショップリストから削除しました。"
        )
        return
    set_config(f"shop_channel_mode_{channel_id}", mode)
    if mode == "edit":
        if channel_id not in EDIT_CHANNEL_IDS:
            EDIT_CHANNEL_IDS.append(channel_id)
        if channel_id in REPOST_CHANNEL_IDS:
            REPOST_CHANNEL_IDS.remove(channel_id)
    else:
        if channel_id not in REPOST_CHANNEL_IDS:
            REPOST_CHANNEL_IDS.append(channel_id)
        if channel_id in EDIT_CHANNEL_IDS:
            EDIT_CHANNEL_IDS.remove(channel_id)
    mode_label = "既存メッセージを編集" if mode == "edit" else "削除して新規投稿"
    await ctx.send(
        f"✅ チャンネル `{channel_id}` を **{mode_label}** モードで追加しました。\n再起動時から有効になります。"
    )


@bot.command(name="listshops")
async def listshops(ctx):
    """!listshops — ショップチャンネル一覧"""
    if not admin_only(ctx):
        await ctx.send("このコマンドは管理者のみ使用できます。")
        return
    embed = discord.Embed(
        title="🏪 ショップチャンネル一覧", color=discord.Color.og_blurple()
    )
    if EDIT_CHANNEL_IDS:
        embed.add_field(
            name="✏️ 編集モード（既存メッセージを更新）",
            value="\n".join(f"`{cid}`" for cid in EDIT_CHANNEL_IDS),
            inline=False,
        )
    if REPOST_CHANNEL_IDS:
        embed.add_field(
            name="🔄 再投稿モード（削除して新規投稿）",
            value="\n".join(f"`{cid}`" for cid in REPOST_CHANNEL_IDS),
            inline=False,
        )
    if not EDIT_CHANNEL_IDS and not REPOST_CHANNEL_IDS:
        embed.description = "ショップチャンネルが設定されていません。"
    await ctx.send(embed=embed)


# チャンネル設定: edit=既存メッセージを更新, repost=削除して新規投稿
EDIT_CHANNEL_IDS = [
    1520737529870024754,  # paypay残高垢（既存メッセージを編集）
]
REPOST_CHANNEL_IDS = [
    1520737798607470602,  # paypayポイント垢（削除して新規投稿）
]


def build_shop_embed():
    products = get_all_products()
    embed = discord.Embed(
        title="🛒 自動販売機",
        description="ボタンを押して購入！在庫がないものはチケットまで！",
        color=discord.Color.blurple(),
    )
    if products:
        for p in products:
            stock_text = f"在庫: {p['stock']}個" if p["stock"] > 0 else "**売り切れ**"
            embed.add_field(
                name=p["name"],
                value=f"値段：{p['price']:,}円　|　{stock_text}",
                inline=False,
            )
    else:
        embed.description = "現在登録されている商品がありません。"
    return embed


async def get_channel_safe(channel_id):
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"Failed to fetch channel {channel_id}: {e}")
            return None
    return channel


async def edit_shop(channel):
    """既存のボットメッセージを編集して更新する"""
    embed = build_shop_embed()
    view = ShopView()
    stored_id = get_config(f"shop_message_id_{channel.id}")
    if stored_id:
        try:
            msg = await channel.fetch_message(int(stored_id))
            await msg.edit(embed=embed, view=view)
            print(f"Shop updated (edit) in channel {channel.id}")
            return
        except (discord.NotFound, discord.Forbidden):
            pass
    async for msg in channel.history(limit=50):
        if msg.author.id == bot.user.id and msg.embeds:
            await msg.edit(embed=embed, view=view)
            set_config(f"shop_message_id_{channel.id}", str(msg.id))
            print(f"Shop updated (edit found) in channel {channel.id}")
            return
    msg = await channel.send(embed=embed, view=view)
    set_config(f"shop_message_id_{channel.id}", str(msg.id))
    print(f"Shop posted (new) in channel {channel.id}")


async def repost_shop(channel):
    """古いメッセージを削除して新規投稿する"""
    embed = build_shop_embed()
    view = ShopView()
    old_msg_id = get_config(f"shop_message_id_{channel.id}")
    if old_msg_id:
        try:
            old_msg = await channel.fetch_message(int(old_msg_id))
            await old_msg.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
    msg = await channel.send(embed=embed, view=view)
    set_config(f"shop_message_id_{channel.id}", str(msg.id))
    print(f"Shop posted (repost) in channel {channel.id}")


@bot.event
async def on_ready():
    init_db()
    bot.add_view(ShopView())
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Admin user ID: {ADMIN_USER_ID}")
    for channel_id in EDIT_CHANNEL_IDS:
        channel = await get_channel_safe(channel_id)
        if channel:
            try:
                await edit_shop(channel)
            except Exception as e:
                print(f"Error editing shop in {channel_id}: {e}")
        else:
            print(f"Edit channel {channel_id} not accessible")
    for channel_id in REPOST_CHANNEL_IDS:
        channel = await get_channel_safe(channel_id)
        if channel:
            try:
                await repost_shop(channel)
            except Exception as e:
                print

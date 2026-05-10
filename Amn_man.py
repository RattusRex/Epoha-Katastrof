import discord
from discord.ext import commands
from discord import app_commands
import random
from discord.ui import Button, View
import sqlite3


intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="/", intents=discord.Intents.all())
API_KEY = "AIzaSyCgJl23rYGZxY-m8OQJAhtmeTm9MtOV_Ps"
GUILD_IDS = [1097141578834907238, 880539447966449765]

@client.event
async def on_ready():
    init_db()
    try:
        for guild_id in GUILD_IDS:
            guild = discord.Object(id=guild_id)
            await client.tree.sync(guild=guild)
            print(f"✅ Synced commands for guild {guild_id}")
    except Exception as e:
        print(f"⚠️ Guild sync failed: {e}")
    print(f"🤖 Logged in as {client.user}")
    await client.tree.sync()
    print("Online")

DB_FILE = "karma.db"

def init_db():
    """Create the database and table if they don't already exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS karma (
            user_id INTEGER PRIMARY KEY,
            karma REAL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
    #return result[0] if result else 0.0

def update_karma(user_id: int, delta: float) -> float:
    """Add (or subtract) Karma for a user and return the new total."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Check if the user already exists
    c.execute("SELECT karma FROM karma WHERE user_id = ?", (user_id,))
    result = c.fetchone()

    if result:
        new_karma = result[0] + delta
        c.execute("UPDATE karma SET karma = ? WHERE user_id = ?", (new_karma, user_id))
    else:
        new_karma = delta
        c.execute("INSERT INTO karma (user_id, karma) VALUES (?, ?)", (user_id, new_karma))

    conn.commit()
    conn.close()
    return new_karma

@client.tree.command(name="give_karma", description="Добавить игроку карму")
@app_commands.describe(
    member="The Discord user to receive Karma",
    amount="How much Karma to add (can be negative)"
)
@app_commands.checks.has_permissions(administrator=True)
async def give_karma(interaction: discord.Interaction, member: discord.Member, amount: float, reason: str):
    """Admin-only command to give Karma points to a user."""
    penalty_role, penalty_value = get_penalty(member)
    if amount > 0 and penalty_value < 0:
        given = int(amount)
        penalty_abs = abs(penalty_value)
        # Case A — given >= penalty → remove penalty + give leftover karma
        if given >= penalty_abs:
            leftover = given - penalty_abs
            await set_penalty_role(member, penalty_role, 0)

            new_total = update_karma(member.id, leftover)

            await interaction.response.send_message(
                f"🟢 Роль штрафника снята с {member.mention}!\n"
                f"ГМ выдал: {amount} кармы.\n"
                f"Добавлено кармы: **{leftover}**\n"
                f"Причина: {reason}\n"
                f"Текущее количество: **{round(new_total, 2)}**"
            )
            return
        # Case B — given < penalty → reduce penalty, no karma added
        new_penalty = -(penalty_abs - given)
        await set_penalty_role(member, penalty_role, new_penalty)

        await interaction.response.send_message(
            f"🟡 У {member.mention} уменьшён штраф: теперь **{new_penalty}**.\n"
            f"ГМ выдал: {amount} кармы.\n"
            f"Причина выдачи: {reason}.\n"
            f"Карма на счёт не добавлена. "
        )
        return
    # Update the player's Karma in the database
    new_total = update_karma(member.id, amount)

    # Create a clear, formatted public reply
    formatted_total = round(new_total, 2)
    formatted_amount = f"+{amount}" if amount > 0 else str(amount)

    await interaction.response.send_message(
        f"✅ Добавил {formatted_amount} Кармы игроку {member.mention}. Причина: **{reason}**\n"  
        f"Текущее количество: **{formatted_total}**"
    )
@give_karma.error
async def give_karma_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("❌ Не по масти тебе эти команды использовать.", ephemeral=False)
    else:
        await interaction.response.send_message("⚠️ Нихуя не понял, но что-то точно пошло по пизде.", ephemeral=False)
        raise error


PENALTY_ROLES = {
    "Штрафник (-1 карма)": -1,
    "Штрафник (-2 кармы)": -2,
    "Штрафник (-3 кармы)": -3,
}



def get_penalty(member: discord.Member):
    """Return (role_object, penalty_value) or (None, 0)."""
    for role in member.roles:
        if role.name in PENALTY_ROLES:
            return role, PENALTY_ROLES[role.name]
    return None, 0

async def set_penalty_role(member: discord.Member, old_role: discord.Role, new_penalty: int):
    """Replace penalty role with a new one or remove if new_penalty == 0."""
    guild = member.guild
    await member.remove_roles(old_role)

    if new_penalty == 0:
        return

    role_name = f"Штрафник ({new_penalty} карма)" if new_penalty == -1 else \
                f"Штрафник ({new_penalty} кармы)"

    new_role = discord.utils.get(guild.roles, name=role_name)
    if new_role:
        await member.add_roles(new_role)


RARITY_DATA = {
    "Обычный": {"dc": 5, "days_dice": 4, "base_price": 100},
    "Необычный": {"dc": 10, "days_dice": 8, "base_price": 500},
    "Редкий": {"dc": 15, "days_dice": 12, "base_price": 5000},
}
CONSUMABLE_BASE_PRICE = {
    "Обычный": 50,
    "Необычный": 250,
    "Редкий": 2500,
}
RARITY_PRICE_ROLL_ADJUSTMENT = {
    "Обычный": 10,
    "Необычный": 0,
    "Редкий": -10,
}
def get_base_price(rarity: str, consumable: str) -> int:
    """Return the base price for an item, accounting for consumables."""
    if consumable == "да" and rarity in CONSUMABLE_BASE_PRICE:
        return CONSUMABLE_BASE_PRICE[rarity]
    return RARITY_DATA[rarity]["base_price"]

def _adjusted_price_roll(rarity: str) -> int:
    """Roll d100 and apply the rarity-specific adjustment used by all shops."""
    return random.randint(1, 100) + RARITY_PRICE_ROLL_ADJUSTMENT.get(rarity, 0)

def roll_buy_price_multiplier(rarity: str):
    """Roll the buy-side price multiplier. Returns (price_roll, multiplier)."""
    price_roll = _adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 1.5 + (random.randint(0, 500) / 1000)
    elif price_roll <= 40:
        multiplier = 1.0 + (random.randint(0, 490) / 1000)
    elif price_roll <= 80:
        multiplier = 0.75 + (random.randint(0, 240) / 1000)
    elif price_roll <= 90:
        multiplier = 0.5 + (random.randint(0, 240) / 1000)
    else:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    return price_roll, multiplier

def roll_sell_price_multiplier(rarity: str):
    """Roll the sell-side price multiplier. Returns (price_roll, multiplier)."""
    price_roll = _adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    elif price_roll <= 42:
        multiplier = 0.5 + (random.randint(0, 250) / 1000)
    elif price_roll <= 82:
        multiplier = 0.75 + (random.randint(0, 150) / 1000)
    elif price_roll <= 92:
        multiplier = 0.9 + (random.randint(0, 350) / 1000)
    else:
        multiplier = 1.25 + (random.randint(0, 350) / 1000)
    return price_roll, multiplier

def calculate_final_price(rarity: str, consumable: str, mode: str):
    """Roll a final item price.

    mode: "buy" for searches, "sell" for sales.
    Returns (price_roll, multiplier, base_price, final_price).
    """
    if mode == "buy":
        price_roll, multiplier = roll_buy_price_multiplier(rarity)
    elif mode == "sell":
        price_roll, multiplier = roll_sell_price_multiplier(rarity)
    else:
        raise ValueError(f"Unknown price mode: {mode!r}")

    base_price = get_base_price(rarity, consumable)
    final_price = int(base_price * multiplier)
    return price_roll, multiplier, base_price, final_price
async def ask_item_name(interaction: discord.Interaction, rarity: str):
    """Отправляет поле для ввода названия предмета"""
    modal = ItemSearchModal(rarity)
    await interaction.response.send_modal(modal)

# === Определение модального окна ===
class ItemSearchModal(discord.ui.Modal):
    def __init__(self, rarity: str):
        super().__init__(title=f"Поиск {rarity.lower()} предмета")
        self.rarity = rarity

        self.item_name = discord.ui.TextInput(
            label="Введите название предмета:",
            placeholder="например: Меч +1, Наручи стрельбы из лука, Зелье исцеления",
            required=True,
            max_length=50
        )
        self.character_name = discord.ui.TextInput(
            label="Введите имя вашего персонажа:",
            placeholder="например: Мидей, Царис Лаонд, Моргана Виренс, Рюрик",
            required=True,
            max_length=50
        )
        self.consumable = discord.ui.TextInput(
            label="Является ли предмет расходником?:",
            placeholder="Вводить только МАЛЕНЬКИМИ буквами: да/нет",
            required=True,
            max_length=50
        )

        self.add_item(self.item_name)
        self.add_item(self.character_name)
        self.add_item(self.consumable)

    async def on_submit(self, interaction: discord.Interaction):
        """После того как игрок ввёл название — появляются 2 кнопки"""

        view = SearchChoiceView(self.rarity, self.item_name.value, self.character_name.value, self.consumable.value)
        await interaction.response.send_message(
            f"Вы, **'{self.character_name.value}'**, ищете **{self.item_name.value}** ({self.rarity.lower()} предмет. Является ли он расходником? **{self.consumable.value}**).\n"
            "Как хотите искать?",
            view=view
        )

# === Определение кнопок поиска ===
class SearchChoiceView(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, character_name: str, consumable: str):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.character_name = character_name
        self.consumable = consumable

    @discord.ui.button(label="Искать самому", style=discord.ButtonStyle.primary)
    async def search_self(self, interaction: discord.Interaction, button: discord.ui.Button):
        #await interaction.response.send_message(
            #f"🗺️ {interaction.user.mention} начинает поиск {self.item_name} самостоятельно...")
        await interaction.response.send_modal(SelfSearchInput(self.rarity, self.item_name, self.character_name, self.consumable))

    @discord.ui.button(label="Ищет наёмник", style=discord.ButtonStyle.secondary)
    async def search_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"💰 {interaction.user.mention} нанимает наёмника для поиска {self.item_name}...",view=SearchRollsMerc(self.rarity, self.item_name, self.character_name, self.consumable))

    @discord.ui.button(label="Продать самому", style=discord.ButtonStyle.success)
    async def sell_self(self, interaction: discord.Interaction, button: discord.ui.Button):
        #await interaction.response.send_message(
            #f"🗺️ {interaction.user.mention} начинает продажу {self.item_name} самостоятельно...")
        await interaction.response.send_modal(SelfSellInput(self.rarity, self.item_name, self.character_name, self.consumable))

    @discord.ui.button(label="Продаёт наёмник", style=discord.ButtonStyle.danger)
    async def sell_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"💰 {interaction.user.mention} нанимает наёмника для продажи {self.item_name}...",
            view=SellRollsMerc(self.rarity, self.item_name, self.character_name, self.consumable)
        )

# === Основное меню магазина ===
class ShopView(discord.ui.View):
    @discord.ui.button(label="Обычный предмет", style=discord.ButtonStyle.secondary)
    async def common_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_item_name(interaction, "Обычный",     )

    @discord.ui.button(label="Необычный предмет", style=discord.ButtonStyle.success)
    async def uncommon_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_item_name(interaction, "Необычный")

    @discord.ui.button(label="Редкий предмет", style=discord.ButtonStyle.primary)
    async def rare_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        await ask_item_name(interaction, "Редкий")

class SelfSellInput(discord.ui.Modal):
    def __init__(self, rarity: str, item_name: str, character_name: str, consumable: str):
        super().__init__(title=f"Используем ваш бонус проверки")
        self.rarity = rarity
        self.item_name = item_name
        self.character_name = character_name
        self.search_bonus = discord.ui.TextInput(
            label="Введите ваш бонус проверки расследования:",
            placeholder="например: 0, 7, 4, -1",
            required=True,
            max_length=50
        )
        self.add_item(self.search_bonus)
        self.consumable = consumable

    async def on_submit(self, interaction: discord.Interaction):
        """После того как игрок ввёл название — появляются 2 кнопки"""
        view = SelfSell(self.rarity, self.item_name, self.search_bonus.value, self.character_name, self.consumable)
        await interaction.response.send_message(
            f"Вы продаёте **{self.item_name}** ({self.rarity.lower()} предмет при помощи своего бонуса **{self.search_bonus.value}**).\n"
            ,
            view=view
        )

class SelfSell(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, search_bonus:str, character_name: str, consumable: str, total_spent: float = 0):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.character_name = character_name
        self.dc = RARITY_DATA[rarity]["dc"]
        self.days_dice = RARITY_DATA[rarity]["days_dice"]
        self.base_price = RARITY_DATA[rarity]["base_price"]
        self.search_bonus = search_bonus
        self.total_spent = total_spent
        self.consumable = consumable
    async def self_sell_check(self, interaction: discord.Interaction, search_bonus: str):
        """Основная логика броска и результата"""
        roll_result = random.randint(1, 20)
        total = roll_result + int(search_bonus)
        success = total >= self.dc
        # Сообщение о броске
        msg = (
            f"🎲 **Вы** делаете бросок продажи ({roll_result} + {search_bonus} = {total} против {self.dc}).\n"
        )
        if success:
            days_spent = round(random.randint(1, self.days_dice))
            price_roll, price_mult, base_price, final_price = calculate_final_price(
                self.rarity, self.consumable, "sell"
            )
            self.base_price = base_price

            msg += (
                f"✅ Предмет **{self.item_name}** Может быть продан!\n"
                f"⏳ Потрачено дней: **{days_spent}**\n"
                f"🎲 Кубик д100: **{price_roll}**\n"
                f"Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                f"💰 Цена: **{final_price} золотых** (базовая {self.base_price}, множитель {price_mult}%) = **{final_price}** золотых"
            )
            await interaction.response.send_message(
                msg,
                view=SelfSoldItemView(
                    rarity=self.rarity,
                    item_name=self.item_name,
                    days_spent=days_spent,
                    final_price=final_price,
                    character_name=self.character_name,
                    consumable=self.consumable
                )
            )
            return

        else:
            msg += f"❌ Вы не смогли продать предмет **{self.item_name}**. И потратили в пустую **{self.days_dice}** дней"

        await interaction.response.send_message(msg)

    @discord.ui.button(label=f"Продать с вашим бонусом", style=discord.ButtonStyle.success)
    async def self_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.self_sell_check(interaction, self.search_bonus)

class SellRollsMerc(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, character_name: str, consumable: str, total_spent: float = 0):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.dc = RARITY_DATA[rarity]["dc"]
        self.days_dice = RARITY_DATA[rarity]["days_dice"]
        self.base_price = RARITY_DATA[rarity]["base_price"]
        self.total_spent = total_spent
        self.character_name = character_name
        self.consumable = consumable

    async def sell_check(self, interaction: discord.Interaction, merc_name: str, bonus: int, plata: float):
        """Основная логика броска и результата"""
        shans_naeba = random.randint(1, 100)

        success_flag = False
        final_price = None
        price_mult = None

        if merc_name == "Плохой" and shans_naeba <71:
            naebali = plata * self.days_dice
            self.total_spent += naebali
            msg = (f"Вас развели на деньги. Потерянная сумма составляет: **{round(naebali,1)} зм**\n Шанс развода 70 и ниже. Вам выпало {shans_naeba}\n"
                   f"Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                   )
            await interaction.response.send_message(msg)
            return

        roll_result = random.randint(1, 20)
        total = roll_result + bonus
        success = total >= self.dc
        rounded = round(plata, 1)
        # Сообщение о броске
        msg = (
            f"🎲 **{merc_name} наёмник** делает бросок продажи ({roll_result} + {bonus} = {total} против {self.dc}).\n"
        )

        if success:
            days_spent = round(random.randint(1, self.days_dice))
            price_roll, price_mult, base_price, final_price = calculate_final_price(
                self.rarity, self.consumable, "sell"
            )
            self.base_price = base_price

            round_days = round(days_spent)
            bablo = rounded * round_days

            self.total_spent += bablo

            msg += (
                f"✅ Предмет **{self.item_name}** может быть продан!\n"
                f"⏳ Потрачено дней: **{round_days}**\n"
                f"🎲 Кубик д100: **{price_roll}**\n"
                f"💰 Плата наёмнику **{rounded}** золотых за **{round_days}** = **{round(bablo,1)}** золотых\n"
                f"💰Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                f"💰 Цена: **{final_price} золотых** (базовая {self.base_price}, множитель {round(price_mult,3)}%) - плата наёмнику {round(bablo,1)} - накопленные траты {round(self.total_spent, 1) - round(bablo,1)} = **{final_price - round(self.total_spent, 1) }** золотых"
            )

        else:
            proebali = rounded * self.days_dice
            self.total_spent += proebali
            msg += f"❌ Наёмник не смог продать предмет **{self.item_name}**. И вы отдали ему **{round(proebali,1)}** золотых\n "f"Накопленные траты: **{round(self.total_spent,1)}** золота.\n"
            await interaction.response.send_message(msg)
            return


        await interaction.response.send_message(msg, view=SoldItemView(rarity=self.rarity, item_name=self.item_name, total_spent=self.total_spent, character_name=self.character_name, final_price=final_price, consumable=self.consumable))

    @discord.ui.button(label="Плохой наёмник (+0) 1зм/д", style=discord.ButtonStyle.secondary)
    async def poor_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.sell_check(interaction, "Плохой", 0, 1)

    @discord.ui.button(label="Хороший наёмник (+4) 5зм/д", style=discord.ButtonStyle.primary)
    async def good_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.sell_check(interaction, "Хороший", 4, 5)

    @discord.ui.button(label="Опытный наёмник (+6) 10зм/д", style=discord.ButtonStyle.success)
    async def experienced_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.sell_check(interaction, "Опытный", 6, 10)

    @discord.ui.button(label="Экспертный наёмник (+8) 25зм/д", style=discord.ButtonStyle.danger)
    async def expert_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.sell_check(interaction, "Экспертный", 8, 25)


class SoldItemView(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, total_spent: float, final_price: int, character_name: str, consumable: str):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.total_spent = total_spent
        self.final_price = final_price
        self.character_name = character_name
        self.consumable = consumable

    @discord.ui.button(label="Продать предмет", style=discord.ButtonStyle.success)
    async def buy_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = self.final_price - self.total_spent
        await interaction.response.send_message(
            f"# Продажа\n"
            f"1) {self.item_name}\n"
            f"2) {self.character_name}\n"
            f"💼 3) Траты на поиски: **{round(self.total_spent, 1)}**\n"
            f"💰 4) Цена предмета: **{self.final_price}** Расходдник? **{self.consumable}**\n"

            f"💳 5) **Итого получено: {round(total, 1)} золотых**"
        )


class SearchRollsMerc(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, character_name: str, consumable: str, total_spent: float = 0):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.dc = RARITY_DATA[rarity]["dc"]
        self.days_dice = RARITY_DATA[rarity]["days_dice"]
        self.base_price = RARITY_DATA[rarity]["base_price"]
        self.total_spent = total_spent
        self.character_name = character_name
        self.consumable = consumable
    async def make_check(self, interaction: discord.Interaction, merc_name: str, bonus: int, plata: float):
        """Основная логика броска и результата"""
        shans_naeba = random.randint(1, 100)

        success_flag = False
        final_price = None
        price_mult = None

        if merc_name == "Плохой" and shans_naeba <61:
            naebali = plata * self.days_dice
            self.total_spent += naebali
            msg = (f"Вас развели на деньги. Потерянная сумма составляет: **{round(naebali,1)} зм**\n Шанс развода 60 и ниже. Вам выпало {shans_naeba}\n"
                   f"Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                   )
            await interaction.response.send_message(msg)
            return

        roll_result = random.randint(1, 20)
        total = roll_result + bonus
        success = total >= self.dc
        rounded = round(plata, 1)
        # Сообщение о броске
        msg = (
            f"🎲 **{merc_name} наёмник** делает бросок поиска ({roll_result} + {bonus} = {total} против {self.dc}).\n"
        )

        if success:
            days_spent = round(random.randint(1, self.days_dice))
            # Успех: броски дней и стоимости
            price_roll, price_mult, base_price, final_price = calculate_final_price(
                self.rarity, self.consumable, "buy"
            )
            self.base_price = base_price

            round_days = round(days_spent)
            bablo = rounded * round_days

            self.total_spent += bablo

            msg += (
                f"✅ Предмет **{self.item_name}** найден!\n"
                f"⏳ Потрачено дней: **{round_days}**\n"
                f"🎲 Кубик д100: **{price_roll}**\n"
                f"💰 Плата наёмнику **{rounded}** золотых за **{round_days}** = **{round(bablo,1)}** золотых\n"
                f"💰Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                f"💰 Цена: **{final_price} золотых** (базовая {self.base_price}, множитель {round(price_mult,3)}%) + плата наёмнику {round(bablo,1)} + накопленные траты {round(self.total_spent, 1) - round(bablo,1)} = **{final_price + round(self.total_spent, 1)}** золотых"
            )

        else:
            proebali = rounded * self.days_dice
            self.total_spent += proebali
            msg += f"❌ Наёмник не смог найти предмет **{self.item_name}**. И вы отдали ему **{round(proebali,1)}** золотых\n "f"Накопленные траты: **{round(self.total_spent,1)}** золота.\n"
            await interaction.response.send_message(msg)
            return


        await interaction.response.send_message(msg, view=FoundItemView(rarity=self.rarity, item_name=self.item_name, total_spent=self.total_spent, character_name=self.character_name, final_price=final_price, consumable=self.consumable))

    @discord.ui.button(label="Плохой наёмник (+0) 1зм/д", style=discord.ButtonStyle.secondary)
    async def poor_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_check(interaction, "Плохой", 0, 1)

    @discord.ui.button(label="Хороший наёмник (+4) 5зм/д", style=discord.ButtonStyle.primary)
    async def good_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_check(interaction, "Хороший", 4, 5)

    @discord.ui.button(label="Опытный наёмник (+6) 10зм/д", style=discord.ButtonStyle.success)
    async def experienced_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_check(interaction, "Опытный", 6, 10)

    @discord.ui.button(label="Экспертный наёмник (+8) 25зм/д", style=discord.ButtonStyle.danger)
    async def expert_merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_check(interaction, "Экспертный", 8, 25)


class SelfSearchInput(discord.ui.Modal):
    def __init__(self, rarity: str, item_name: str, character_name: str, consumable: str):
        super().__init__(title=f"Используем ваш бонус проверки")
        self.rarity = rarity
        self.item_name = item_name
        self.character_name = character_name
        self.consumable = consumable
        self.search_bonus = discord.ui.TextInput(
            label="Введите ваш бонус проверки расследования:",
            placeholder="например: 0, 7, 4, -1",
            required=True,
            max_length=50
        )
        self.add_item(self.search_bonus)

    async def on_submit(self, interaction: discord.Interaction):
        """После того как игрок ввёл название — появляются 2 кнопки"""
        view = SelfSearch(self.rarity, self.item_name, self.search_bonus.value, self.character_name, self.consumable)
        await interaction.response.send_message(
            f"Вы ищете **{self.item_name}** ({self.rarity.lower()} предмет при помощи своего бонуса **{self.search_bonus.value}**).\n"
            ,
            view=view
        )

class SelfSearch(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, search_bonus:str, character_name: str, consumable: str, total_spent: float = 0):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.character_name = character_name
        self.dc = RARITY_DATA[rarity]["dc"]
        self.days_dice = RARITY_DATA[rarity]["days_dice"]
        self.base_price = RARITY_DATA[rarity]["base_price"]
        self.search_bonus = search_bonus
        self.total_spent = total_spent
        self.consumable = consumable
    async def self_make_check(self, interaction: discord.Interaction, search_bonus: str):
        """Основная логика броска и результата"""
        roll_result = random.randint(1, 20)
        total = roll_result + int(search_bonus)
        success = total >= self.dc
        # Сообщение о броске
        msg = (
            f"🎲 **Вы** делаете бросок поиска ({roll_result} + {search_bonus} = {total} против {self.dc}).\n"
        )
        if success:
            days_spent = round(random.randint(1, self.days_dice))
            # Успех: броски дней и стоимости

            price_roll, price_mult, base_price, final_price = calculate_final_price(
                self.rarity, self.consumable, "buy"
            )
            self.base_price = base_price

            msg += (
                f"✅ Предмет **{self.item_name}** найден!\n"
                f"⏳ Потрачено дней: **{days_spent}**\n"
                f"🎲 Кубик д100: **{price_roll}**\n"
                f"Накопленные траты: **{round(self.total_spent, 1)}** золота.\n"
                f"💰 Цена: **{final_price} золотых** (базовая {self.base_price}, множитель {price_mult}%) = **{final_price}** золотых"
            )
            await interaction.response.send_message(
                msg,
                view=SelfFoundItemView(
                    rarity=self.rarity,
                    item_name=self.item_name,
                    days_spent=days_spent,
                    final_price=final_price,
                    character_name=self.character_name,
                    consumable=self.consumable
                )
            )
            return
        else:
            msg += f"❌ Вы не смогли найти предмет **{self.item_name}**. И потратили в пустую **{self.days_dice}** дней"

        await interaction.response.send_message(msg)

    @discord.ui.button(label=f"Искать с вашим бонусом", style=discord.ButtonStyle.success)
    async def self_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.self_make_check(interaction, self.search_bonus)

class SelfFoundItemView(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, days_spent: int, final_price: int, character_name: str, consumable: str):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.days_spent = days_spent
        self.final_price = final_price
        self.character_name = character_name
        self.consumable = consumable

    @discord.ui.button(label="Купить предмет", style=discord.ButtonStyle.success)
    async def buy_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = self.final_price
        await interaction.response.send_message(
            f"# Покупка\n"
            f"1) {self.item_name}\n"
            f"2) {self.character_name}\n"
            f"⏳ 3) Потрачено дней: **{self.days_spent}**\n"
            f"💰 4) Цена предмета: **{self.final_price}** Расходник? **{self.consumable}**\n"

            f"💳 5) **Итого к оплате: {round(total, 1)} золотых**"
        )

class SelfSoldItemView(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, days_spent: int, final_price: int, character_name: str, consumable: str):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.days_spent = days_spent
        self.final_price = final_price
        self.character_name = character_name
        self.consumable = consumable

    @discord.ui.button(label="Продать предмет", style=discord.ButtonStyle.success)
    async def sell_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = self.final_price
        await interaction.response.send_message(
            f"# Продажа\n"
            f"1) {self.item_name}\n"
            f"2) {self.character_name}\n"
            f"⏳ 3) Потрачено дней: **{self.days_spent}**\n"
            f"💰 4) Цена предмета: **{self.final_price}** Расходник? **{self.consumable}**\n"

            f"💳 5) **Итого получено: {round(total, 1)} золотых**"
        )

class FoundItemView(discord.ui.View):
    def __init__(self, rarity: str, item_name: str, total_spent: float, final_price: int, character_name: str, consumable: str):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.item_name = item_name
        self.total_spent = total_spent
        self.final_price = final_price
        self.character_name = character_name
        self.consumable = consumable


    @discord.ui.button(label="Купить предмет", style=discord.ButtonStyle.success)
    async def buy_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = self.total_spent + self.final_price
        await interaction.response.send_message(
            f"# Покупка\n"
            f"1) {self.item_name}\n" 
            f"2) {self.character_name}\n" 
            f"💼 3) Траты на поиски: **{round(self.total_spent,1)}**\n"
            f"💰 4) Цена предмета: **{self.final_price}** Расходник? **{self.consumable}**\n"
            
            f"💳 5) **Итого к оплате: {round(total,1)} золотых**"
        )



# === Slash-команда /shop ===
@client.tree.command(name="shop", description="Открыть магазин снаряжения")
async def shop(interaction: discord.Interaction):
    view = ShopView()

    if isinstance(interaction.channel, discord.Thread):

        await interaction.response.send_message(
            ":bank: **Добро пожаловать в Амн, приключенец. Чего желаешь купить в моём прелестном магазине?**",
            view=view
        )
        return



    # Отвечаем "официально", чтобы Discord не ругался

    thread = await interaction.channel.create_thread(
        name=f"Закуп — {interaction.user.display_name}",
        type=discord.ChannelType.public_thread
    )
    await interaction.response.send_message(
        f"🧵 Ветка **{thread.name}** создана! Переходим туда...",
        ephemeral=True
    )

    await thread.send(":bank: **Добро пожаловать в Амн, приключенец. Чего желаешь купить в моём прелестном магазине?**", view=view)

class SuperLeaderboardView(discord.ui.View):
    def __init__(self, data, interaction_user_id, per_page=15):
        super().__init__(timeout=180)
        self.data = data
        self.user_id = interaction_user_id
        self.per_page = per_page
        self.page = 0

    def get_page_content(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        lines = []
        player_line = None
        for i, (user_id, karma) in enumerate(page_data, start=start + 1):
            if user_id == self.user_id:
                user = client.get_user(user_id)
                name = user.mention if user else f"Неизвестный ({user_id})"
                lines.append(f"**{i}.** {name} — {round(karma, 2)}")
        if player_line:
            lines.append(player_line)
            lines.append("────────────")

        for i, (user_id, karma) in enumerate(page_data, start=start + 1):
            user = client.get_user(user_id)
            name = user.mention if user else f"Неизвестный ({user_id})"
            lines.append(f"**{i}.** {name} — {round(karma, 2)}")

        total_pages = (len(self.data) - 1) // self.per_page + 1

        return (
                f"🏆 **Доска Кармы**\n"
                f"Страница {self.page + 1}/{total_pages}\n\n"
                + "\n".join(lines)
        )

    async def update(self, interaction):
        await interaction.response.edit_message(
            content=self.get_page_content(),
            view=self
        )

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.update(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.page + 1) * self.per_page < len(self.data):
            self.page += 1
            await self.update(interaction)


@client.tree.command(name="pizdataya_leaderboard", description="Список игроков")
async def leaderboard(interaction: discord.Interaction):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "SELECT user_id, karma FROM karma ORDER BY karma DESC"
    )
    results = c.fetchall()
    conn.close()

    if not results:
        await interaction.response.send_message(
            "📜 Ничего по карме не найдено!"
        )
        return

    view = SuperLeaderboardView(results, interaction.user.id)

    await interaction.response.send_message(
        view.get_page_content(),
        view=view,
        ephemeral=True
    )

client.run("")

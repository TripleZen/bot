import json
import discord
from discord.ext import commands
import random
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import asyncio

BOT_DEFAULT_ADDRESS = {
    'aus': "ATUZnc6ABwcAUix4p2Lr8hDSuAmT62QEcJ",
    'dingo': "DByTiydZ4cAXyu4tw6kVCqVJDgbZZNhnhy",
    'cash': "qzmjvpc7df5dqqd7vrcp5vcp6z5v5cp5u5vzcp5rpa"
}

def get_config(section):
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config.get(section)

class BetTypeView(discord.ui.View):
    def __init__(self, bot, user_address, amount, currency):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_address = user_address
        self.amount = amount
        self.currency = currency

    @discord.ui.button(label="Number", style=discord.ButtonStyle.primary)
    async def number_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_bet_value_view(interaction, "number")

    @discord.ui.button(label="Color", style=discord.ButtonStyle.primary)
    async def color_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_bet_value_view(interaction, "color")

    @discord.ui.button(label="Even/Odd", style=discord.ButtonStyle.primary)
    async def evenodd_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_bet_value_view(interaction, "evenodd")

    @discord.ui.button(label="High/Low", style=discord.ButtonStyle.primary)
    async def highlow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_bet_value_view(interaction, "highlow")

    async def show_bet_value_view(self, interaction, bet_type):
        await interaction.response.defer()
        view = BetValueView(self.bot, self.user_address, bet_type, self.amount, self.currency)
        await interaction.followup.send(f"Select your bet value for {bet_type}:", view=view)

class BetValueView(discord.ui.View):
    def __init__(self, bot, user_address, bet_type, amount, currency):
        super().__init__(timeout=60)
        self.bot = bot
        self.user_address = user_address
        self.bet_type = bet_type
        self.amount = amount
        self.currency = currency

        if bet_type == "number":
            for i in range(0, 37):
                self.add_item(discord.ui.Button(label=str(i), style=discord.ButtonStyle.secondary, custom_id=str(i)))
        elif bet_type == "color":
            self.add_item(discord.ui.Button(label="Red", style=discord.ButtonStyle.danger, custom_id="red"))
            self.add_item(discord.ui.Button(label="Black", style=discord.ButtonStyle.primary, custom_id="black"))
            self.add_item(discord.ui.Button(label="Green", style=discord.ButtonStyle.success, custom_id="green"))
        elif bet_type == "evenodd":
            self.add_item(discord.ui.Button(label="Even", style=discord.ButtonStyle.primary, custom_id="even"))
            self.add_item(discord.ui.Button(label="Odd", style=discord.ButtonStyle.primary, custom_id="odd"))
        elif bet_type == "highlow":
            self.add_item(discord.ui.Button(label="High (19-36)", style=discord.ButtonStyle.primary, custom_id="high"))
            self.add_item(discord.ui.Button(label="Low (1-18)", style=discord.ButtonStyle.primary, custom_id="low"))

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        view = BetTypeView(self.bot, self.user_address, self.amount, self.currency)
        await interaction.followup.send("Choose your bet type:", view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        bet_value = interaction.data["custom_id"]
        await interaction.response.defer()
        result_number = random.randint(0, 36)
        result_color = self.bot.get_cog('Roulette').get_color(result_number)
        await interaction.followup.send(f"The wheel spins... 🎡 Number: {result_number} Color: {result_color.capitalize()}")

        if self.bot.get_cog('Roulette').is_winner(self.bet_type, bet_value, result_number, result_color):
            await self.bot.get_cog('Roulette').send_cash(interaction, self.user_address, self.amount, self.currency)
            await interaction.followup.send(f"Congratulations! You won {self.amount} {self.currency}!")
        else:
            await self.bot.get_cog(f'Tip{self.currency.capitalize()}').get_withdraw(str(interaction.user.id), BOT_DEFAULT_ADDRESS[self.currency], self.amount)
            await interaction.followup.send("Better luck next time!")
        return False

class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.aus = self.init_rpc('ausd')
        self.dingo = self.init_rpc('dingod')
        self.cash = self.init_rpc('cashd')
        self.red_numbers = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        self.black_numbers = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
        self.green_numbers = {0}

    def init_rpc(self, section):
        config = get_config(section)
        rpc_user = config['rpc_user']
        rpc_password = config['rpc_password']
        rpc_host = config['rpc_host']
        rpc_port = config['rpc_port']
        rpc_url = f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
        return AuthServiceProxy(rpc_url)

    @commands.command(
        aliases=["roul"],
        help="""Roulette game with multiple betting options

Arguments:
amount: The amount of the bet.
currency: The currency for the bet (aus, dingo, cash)."""
    )
    async def roulette(self, ctx, amount: float, currency: str):
        """Roulette game with multiple betting options"""
        user = ctx.author
        tipper = str(user.id).replace('!', '')

        if currency not in ['aus', 'dingo', 'cash']:
            await ctx.send("Invalid currency. Please choose from 'aus', 'dingo', or 'cash'.")
            return

        # Check user's balance using the appropriate cog
        balance = await self.bot.get_cog(f'Tip{currency.capitalize()}').get_balance(tipper)
        if balance < amount:
            await ctx.send("You do not have enough balance to place this bet.")
            return
        elif amount > 100:
            await ctx.send("You cannot place a bet that high.")
            return

        user_address = self.bot.get_cog(f'Tip{currency.capitalize()}').get_address(tipper)

        view = BetTypeView(self.bot, user_address, amount, currency)
        await ctx.send("Choose your bet type:", view=view)

    def get_color(self, number):
        if number in self.red_numbers:
            return "red"
        elif number in self.black_numbers:
            return "black"
        elif number in self.green_numbers:
            return "green"
        return "unknown"

    def is_winner(self, bet_type, bet_value, result_number, result_color):
        if bet_type == "number" and int(bet_value) == result_number:
            return True
        elif bet_type == "color" and bet_value == result_color:
            return True
        elif bet_type == "evenodd" and ((bet_value == "even" and result_number % 2 == 0) or (bet_value == "odd" and result_number % 2 != 0)):
            return True
        elif bet_type == "highlow" and ((bet_value == "high" and 19 <= result_number <= 36) or (bet_value == "low" and 1 <= result_number <= 18)):
            return True
        return False

    async def send_cash(self, interaction, address, amount, currency):
        cog = self.bot.get_cog('Roulette')
        amount_str = f"{amount:.8f}"
        try:
            txid = getattr(cog, currency).sendfrom("728720610968076308", address, amount_str)
            await interaction.followup.send(f"Transaction successful! {txid}")
        except JSONRPCException as e:
            await interaction.followup.send(f"Error: {e}")

async def setup(bot):
    await bot.add_cog(Roulette(bot))

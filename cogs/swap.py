import json
import discord
from discord.ext import commands
from bitcoinrpc.authproxy import AuthServiceProxy
import requests
import logging

BOT_DINGO_ADDRESS = "DEe4TrCFxChzwaGpF4THMXnjKEMdtRfxvM"
BOT_AUS_ADDRESS   = "AJKASHQ2X87qJ6Momrund6VJidoq2DcDKt"
BOT_CASH_ADDRESS  = "EqUBRD33k3bKvjZ6wok5WkYyXiK6966wvd"
DISCORD_BOT_ID    = 728720610968076308

# Example API endpoint for exchange rates
exchange_api_url  = "https://wallet.autradex.systems/api/v2/peatio/public/markets/"
dingo_doge_ticker = "dingodoge/tickers"
aus_doge_ticker   = "ausdoge/tickers"
cash_doge_ticker  = "cashdoge/tickers"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_config(section):
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config.get(section)

class SwapView(discord.ui.View):
    def __init__(self, amount, exchange_rate, user_id, bot, base):
        super().__init__(timeout=60)
        self.amount = amount
        self.exchange_rate = exchange_rate
        self.user_id = user_id
        self.bot = bot
        self.base = base

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            exchange_rate = float(self.exchange_rate)
            amount = float(self.amount)
            doge_amount = amount * exchange_rate
            final_doge_amount = round(doge_amount * 0.99, 8)

            logging.info(f"Exchange rate: 1 {self.base.capitalize()} = {exchange_rate} Doge")
            logging.info(f"Sending {final_doge_amount} Doge to user {self.user_id}")

            # Choose the correct bot address based on the base currency
            bot_address = BOT_DINGO_ADDRESS
            if self.base == 'dingo':
                bot_address = BOT_DINGO_ADDRESS
            elif self.base == 'cash':
                bot_address = BOT_CASH_ADDRESS
            else:
                bot_address = BOT_AUS_ADDRESS
                                 #if self.base == 'dingo' else BOT_AUS_ADDRESS

            # Send base currency to bot's address
            await self.bot.get_cog(f'Tip{self.base.capitalize()}').get_withdraw(str(self.user_id), bot_address, amount)
            logging.info(f"Receiving {amount} {self.base.capitalize()} from user {self.user_id} to Bot Address")

            address = self.bot.get_cog('TipDoge').get_address(str(self.user_id))
            logging.info(f"{address} , {amount}, {doge_amount}, {final_doge_amount}")
            txid = self.bot.get_cog('TipDoge').doge.sendfrom(str(DISCORD_BOT_ID), address, final_doge_amount)

            await interaction.response.send_message(f"Successfully swapped {amount} {self.base.capitalize()} for {final_doge_amount} Doge. Transaction ID: {txid}")

        except Exception as e:
            await interaction.response.send_message(f"Error: {e}")
            logging.error(f"Swap failed: {e}")

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Transaction canceled.")

class Swap(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        doge_config = get_config('doged')
        self.doge_rpc_user = doge_config['rpc_user']
        self.doge_rpc_password = doge_config['rpc_password']
        self.doge_rpc_host = doge_config['rpc_host']
        self.doge_rpc_port = doge_config['rpc_port']
        self.doge_rpc_url = f"http://{self.doge_rpc_user}:{self.doge_rpc_password}@{self.doge_rpc_host}:{self.doge_rpc_port}"
        self.doge = AuthServiceProxy(self.doge_rpc_url)

        config = get_config('dingod')
        self.rpc_user = config['rpc_user']
        self.rpc_password = config['rpc_password']
        self.rpc_host = config['rpc_host']
        self.rpc_port = config['rpc_port']
        self.rpc_url = f"http://{self.rpc_user}:{self.rpc_password}@{self.rpc_host}:{self.rpc_port}"
        self.dingo = AuthServiceProxy(self.rpc_url)

    def get_user_address(self, user_id):
        addresses = self.doge.getaddressesbyaccount(user_id)
        if addresses:
            return addresses[0]
        return self.doge.getnewaddress(user_id)

    @commands.command()
    async def swap(self, ctx, pair: str, amount: float):
        user = ctx.author
        """Swaps based on the pair and given amount"""
        try:
            base, target = pair.split('/')
            if base.lower() not in ['dingo', 'aus', 'cash'] or target.lower() != 'doge':
                await ctx.send("Invalid pair. Only dingo/doge and aus/doge swaps are supported.")
                return

            tipper = str(user.id).replace('!', '')
            balance = await self.bot.get_cog(f'Tip{base.capitalize()}').get_balance(tipper)
            if balance < amount:
                await ctx.send(f"You do not have enough balance to do this {base}/doge swap.")
                return
            if amount > 500000:
                await ctx.send("Please use a smaller amount below 10,000.")
                return
            if amount < 200:
                await ctx.send("Please swap a higher amount above 200.")
                return
            if base.lower() == 'cash' and amount < 50000:
                await ctx.send("Please swap a higher amount above 50000.")
                return

            # Check price from exchange API
            ticker = dingo_doge_ticker
            if base.lower() == 'dingo':
                ticker = dingo_doge_ticker
            elif base.lower() == 'cash':
                ticker = cash_doge_ticker
            else:
                ticker = aus_doge_ticker
#if base.lower() == 'dingo' else aus_doge_ticker
            response = requests.get(exchange_api_url + ticker)
            response.raise_for_status()
            exchange_data = response.json()
            exchange_rate_str = exchange_data['ticker'].get('last')

            if exchange_rate_str is None:
                await ctx.send("Failed to retrieve the exchange rate. Please try again later.")
                logging.error("Exchange rate is None. Response data: %s", exchange_data)
                return

            exchange_rate = float(exchange_rate_str)

            doge_amount = amount * exchange_rate
            check_doge_amount = round(doge_amount, 8)

            # Check bots balance
            bot_id = str(DISCORD_BOT_ID)
            bot_balance = await self.bot.get_cog('TipDoge').get_balance(bot_id)
            if bot_balance < check_doge_amount:
                await ctx.send("The bot does not have enough balance to do this swap.")
                return

            view = SwapView(amount, exchange_rate, user.id, self.bot, base)
            await ctx.send(f"Exchange rate: 1 {base.capitalize()} = {round(exchange_rate, 8)} Doge. Do you want to continue swapping {amount} {base.capitalize()}?", view=view)

        except Exception as e:
            await ctx.send(f"An error occurred during the swap. Please try again later.")
            logging.error(f"Exception: {e}")

async def setup(bot):
    await bot.add_cog(Swap(bot))

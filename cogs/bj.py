import json
import discord
from discord.ext import commands
import random
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import asyncio

BOT_DEFAULT_ADDRESS = "ATUZnc6ABwcAUix4p2Lr8hDSuAmT62QEcJ"

def get_config(section):
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config.get(section)

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = get_config('ausd')
        self.rpc_user = config['rpc_user']
        self.rpc_password = config['rpc_password']
        self.rpc_host = config['rpc_host']
        self.rpc_port = config['rpc_port']
        self.rpc_url = f"http://{self.rpc_user}:{self.rpc_password}@{self.rpc_host}:{self.rpc_port}"
        self.aus = AuthServiceProxy(self.rpc_url)

    @commands.command()
    async def blackjack(self, ctx, user_address: str, amount: float):
        user = ctx.author
        #tipper = str(ctx.author.id).replace('!', '')

        # Check user's balance using aus cog
        tipper = str(user.id).replace('!', '')
        balance = await self.bot.get_cog('TipAus').get_balance(tipper)
        if balance < amount:
            await ctx.send("You do not have enough balance to place this bet.")
            return
        elif amount > 100:
            await ctx.send("You cannot place a bet that high.")
            return

        deck = self.initialize_deck()
        random.shuffle(deck)
        player, dealer = self.initialize_players()

        def get_cards_value(cards):
            sum = 0
            ace_count = 0
            for card in cards:
                if card['rank'] in ["J", "Q", "K"]:
                    sum += 10
                elif card['rank'] == "A":
                    sum += 11
                    ace_count += 1
                else:
                    sum += card['rank']

            while ace_count > 0 and sum > 21:
                sum -= 10
                ace_count -= 1
            return sum

#        def initialize_deck():
#            suits = ["♥", "♦", "♠", "♣"]
#            ranks = [2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A"]
#            return [{"rank": rank, "suit": suit} for suit in suits for rank in ranks]

#        def initialize_players():
#            player = {"cards": [], "score": 0}
#            dealer = {"cards": [], "score": 0}
#            return player, dealer

        def deal_card(deck, player):
            card = deck.pop()
            player["cards"].append(card)
            player["score"] = get_cards_value(player["cards"])
            return card

        def end_msg(player, dealer):
            player_cards = " ".join([f"{card['rank']}{card['suit']}" for card in player["cards"]])
            dealer_cards = " ".join([f"{card['rank']}{card['suit']}" for card in dealer["cards"]])
            return f"You: {player_cards} ({player['score']})\nDealer: {dealer_cards} ({dealer['score']})"

        async def send_cash(address, amount):
            try:
                txid = self.aus.sendfrom("728720610968076308", address, amount)
                await ctx.send(f"Won {amount}! Transaction ID: {txid}")
            except JSONRPCException as e:
                await ctx.send(f"Error: {e}")

        async def end_game(player, dealer):
            if player["score"] > 21:
                await self.bot.get_cog('TipAus').get_withdraw(tipper, BOT_DEFAULT_ADDRESS, amount)
                await ctx.send(f"You lost {amount}! You reached over 21!\n{end_msg(player, dealer)}")
                return True
            elif dealer["score"] > 21 or player["score"] == 21:
                await send_cash(user_address, amount)
                await ctx.send(f"Win! Dealer reached over 21 or you got 21!\n{end_msg(player, dealer)}")
                return True
            elif dealer["score"] == 21:
                await self.bot.get_cog('TipAus').get_withdraw(tipper, BOT_DEFAULT_ADDRESS, amount)
                await ctx.send(f"You lost {amount}! Dealer got 21!\n{end_msg(player, dealer)}")
                return True
            elif dealer["score"] >= 17:
                if player["score"] > dealer["score"]:
                    await send_cash(user_address, amount)
                    await ctx.send(f"Win! You defeated the dealer!\n{end_msg(player, dealer)}")
                    return True
                elif player["score"] < dealer["score"]:
                    await self.bot.get_cog('TipAus').get_withdraw(tipper, BOT_DEFAULT_ADDRESS, amount)
                    await ctx.send(f"You lost {amount}! Dealer won!\n{end_msg(player, dealer)}")
                    return True
                else:
                    await ctx.send(f"Tie! Both have the same score.\n{end_msg(player, dealer)}")
                    return True
            return False

        async def game_loop():
            deal_card(deck, player)
            deal_card(deck, player)
            deal_card(deck, dealer)

            while True:
                if await end_game(player, dealer):
                    break

                buttons = [
                    discord.ui.Button(style=discord.ButtonStyle.primary, label="Hit", custom_id="hit"),
                    discord.ui.Button(style=discord.ButtonStyle.primary, label="Stand", custom_id="stand")
                ]

                # action_row = discord.ui.ActionRow(*buttons)

                view = discord.ui.View()
                for button in buttons:
                    view.add_item(button)

                await ctx.send(f"{end_msg(player, dealer)}\nChoose your action:", view=view)

                def check(interaction):
                    return interaction.user.id == ctx.author.id

                try:
                    interaction = await self.bot.wait_for("interaction", check=check, timeout=120)
                    await interaction.response.defer()

                    if interaction.data['custom_id'] == "hit":
                        deal_card(deck, player)
                    elif interaction.data['custom_id'] == "stand":
                        while dealer["score"] < 17:
                            deal_card(deck, dealer)
                        await end_game(player, dealer)
                        break
                except asyncio.TimeoutError:
                    await ctx.send("Time's up! Game over.")
                    break

        await game_loop()

    def initialize_deck(self):
        suits = ["♥", "♦", "♠", "♣"]
        ranks = [2, 3, 4, 5, 6, 7, 8, 9, 10, "J", "Q", "K", "A"]
        return [{"rank": rank, "suit": suit} for suit in suits for rank in ranks]

    def initialize_players(self):
        player = {"cards": [], "score": 0}
        dealer = {"cards": [], "score": 0}
        return player, dealer

async def setup(bot):
    await bot.add_cog(Blackjack(bot))

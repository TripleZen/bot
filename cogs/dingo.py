import json
import discord
from discord.ext import commands
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

def get_config(section):
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config.get(section)

class TipDingo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = get_config('dingod')
        self.rpc_user = config['rpc_user']
        self.rpc_password = config['rpc_password']
        self.rpc_host = config['rpc_host']
        self.rpc_port = config['rpc_port']
        self.rpc_url = f"http://{self.rpc_user}:{self.rpc_password}@{self.rpc_host}:{self.rpc_port}"
        self.dingo = AuthServiceProxy(self.rpc_url)
#        self.spamchannels = get_config('moderation').get('botspamchannels')

    @commands.command()
    async def dingo(self, ctx, *args):
        """ Dingocoin tipping commands """
        subcommand = args[0] if len(args) > 0 else 'help'
        tipper = str(ctx.author.id).replace('!', '')
        helpmsg = (
            '**!dingo** : Displays This Message\n'
            '**!dingo balance** : get your balance\n'
            '**!dingo deposit** : get address for your deposits\n'
            '**!dingo withdraw <ADDRESS> <AMOUNT>** : withdraw coins to specified address\n'
            '**!dingo send <@user> <amount>** : mention a user with @ and then the amount to tip them\n'
            '**!dingo private send <user> <amount>** : put private before Mentioning a user to tip them privately.'
        )
        channelwarning = 'Please use bot-spam or DMs to talk to bots.'

        if subcommand == 'help':
            await self.private_or_spam_channel(ctx, channelwarning, self.do_help, [helpmsg])
        elif subcommand == 'balance':
            await self.private_or_spam_channel(ctx, channelwarning, self.do_balance, [tipper])
        elif subcommand == 'deposit':
            await self.private_or_spam_channel(ctx, channelwarning, self.do_deposit, [tipper])
        elif subcommand == 'withdraw':
            await self.private_or_spam_channel(ctx, channelwarning, self.do_withdraw, [tipper, args, helpmsg])
        elif subcommand == 'tip':
            await self.private_or_spam_channel(ctx, channelwarning, self.do_tip, [tipper, args, helpmsg])

    async def private_or_spam_channel(self, ctx, wrongchannelmsg, fn, args):
        if not self.in_private_or_spam_channel(ctx):
            await ctx.reply(wrongchannelmsg)
            return
        await fn(ctx, *args)

    async def do_help(self, ctx, helpmsg):
        await ctx.author.send(helpmsg)

    async def get_balance(self, user_id: str):
        tipper = user_id.replace('!', '')
        try:
            # Your logic to get the balance from the blockchain
            balance = self.dingo.getbalance(tipper)
            return balance
        except Exception as e:
            print(f"Error getting balance: {e}")
            await self.reset_bot(ctx)
            return None

    async def do_balance(self, ctx, tipper):
        try:
            balance = self.dingo.getbalance(tipper, 1)
            await ctx.reply(f'You have **{balance}** Dingocoin (DINGO)')
        except JSONRPCException:
            await ctx.reply('Error getting Dingocoin (DINGO) balance.', delete_after=10)

    async def do_deposit(self, ctx, tipper):
        try:
            address = self.get_address(tipper)
            await ctx.reply(f'Your Dingocoin (DINGO) address is {address}')
        except JSONRPCException:
            await ctx.reply('Error getting your Dingocoin (DINGO) deposit address.', delete_after=10)

    async def do_withdraw(self, ctx, tipper, args, helpmsg):
        if len(args) < 4:
            await self.do_help(ctx, helpmsg)
            return

        address = args[2]
        amount = self.get_validated_amount(args[3])

        if amount is None:
            await ctx.reply("I don't know how to withdraw that many Dingocoin (DINGO)...", delete_after=10)
            return

        try:
            tx_id = self.dingo.sendfrom(tipper, address, float(amount))
            await ctx.reply(f'You withdrew {amount} Dingocoin (DINGO) to {address}\n{self.tx_link(tx_id)}')
        except JSONRPCException as e:
            await ctx.reply(str(e), delete_after=10)

    async def get_withdraw(self, user_id: str, address: str, amount: float):
        tipper = user_id.replace('!', '')

        if amount is None:
            print("I don't know how to withdraw that many Dingocoin (DINGO)...")
            return

        try:
            tx_id = self.dingo.sendfrom(tipper, address, amount)
            # await tipper.send(f'You sent {amount} Dingocoin (DINGO) to the Blackjack Dealer\n{self.tx_link(tx_id)}')
            print(f'You withdrew {amount} Dingocoin (DINGO) to {address}\n{self.tx_link(tx_id)}')
        except Exception as e:
            print(f"Error: {e}")
            return


    async def get_withdraw_old(self, user_id: str, address, amount):
        tipper = user_id.replace('!', '')
#        address = args[1]
#        amount = args[2]

        if amount is None:
            await print ("I don't know how to withdraw that many Dingocoin (DINGO)...", delete_after=10)
            return

        try:
#            await print (f"This")
            await self.dingo.sendfrom(tipper, address, float(amount))
            await print (f'You withdrew {amount} Dingocoin (DINGO) to {address}\n{self.tx_link(tx_id)}')
        except Exception as e:
            print (f"error {tx_id}")
            return

    async def do_tip(self, ctx, tipper, args, helpmsg):
        if len(args) < 3:
            await self.do_help(ctx, helpmsg)
            return

        prv = False
        amount_offset = 2
        if args[1] == 'private':
            prv = True
            amount_offset = 3

        amount = self.get_validated_amount(args[amount_offset])

        if amount is None:
            await ctx.reply("I don't know how to tip that many Dingocoin (DINGO)...", delete_after=10)
            return

        if not ctx.message.mentions:
            await ctx.reply('Sorry, I could not find a user in your tip...', delete_after=10)
            return

        recipient = ctx.message.mentions[0].id
        await self.send_dingo(ctx, tipper, str(recipient).replace('!', ''), amount, prv)

    async def send_dingo(self, ctx, tipper, recipient, amount, privacy_flag):
        try:
            address = self.get_address(recipient)
            tx_id = self.dingo.sendfrom(tipper, address, float(amount), 1)
            if privacy_flag:
                user_profile = ctx.guild.get_member(int(recipient))
                await user_profile.send(f'You got privately tipped {amount} Dingocoin (DINGO)\n{self.tx_link(tx_id)}')
                await ctx.author.send(f'You privately tipped {user_profile.name} {amount} Dingocoin (DINGO)\n{self.tx_link(tx_id)}')
                if ctx.message.content.startswith('!dingo private '):
                    await ctx.message.delete(delay=1)
            else:
                await ctx.reply(f'Tipped <@{recipient}> {amount} Dingocoin (DINGO)\n{self.tx_link(tx_id)}')
        except JSONRPCException as e:
            await ctx.reply(str(e), delete_after=10)

    def get_address(self, user_id):
        addresses = self.dingo.getaddressesbyaccount(user_id)
        if addresses:
            return addresses[0]
        return self.dingo.getnewaddress(user_id)

    def in_private_or_spam_channel(self, ctx):
        return isinstance(ctx.channel, discord.DMChannel) or ctx.channel.id
# in self.spamchannels

    def get_validated_amount(self, amount):
        amount = amount.strip()
        if amount.lower().endswith('dingo'):
            amount = amount[:-4]
        return amount if amount.replace('.', '', 1).isdigit() else None

    def tx_link(self, tx_id):
        return f'https://openchains.info/dingocoin/tx/{tx_id}'

async def setup(bot):
    await bot.add_cog(TipDingo(bot))

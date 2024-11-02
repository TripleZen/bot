import discord
from discord.ext import commands

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user != view.current_player:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)

        if self.label != '\u200b':
            return await interaction.response.send_message("This position is already taken!", ephemeral=True)

        self.label = 'X' if view.current_player == view.challenger else 'O'
        self.style = discord.ButtonStyle.success if self.label == 'X' else discord.ButtonStyle.danger
        self.disabled = True

        if view.check_winner():
            view.disable_all_buttons()
            await interaction.response.edit_message(content=f"{interaction.user.mention} has won!", view=view)
            await view.handle_win(interaction, view.current_player)
        elif view.is_tie():
            view.disable_all_buttons()
            await interaction.response.edit_message(content="It's a tie!", view=view)
        else:
            view.current_player = view.opponent if view.current_player == view.challenger else view.challenger
            await interaction.response.edit_message(view=view)

class TicTacToeView(discord.ui.View):
    def __init__(self, ctx, challenger, opponent, amount, currency):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.currency = currency
        self.current_player = challenger

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    async def handle_win(self, interaction, winner):
        loser_id = self.challenger.id if winner.id == self.opponent.id else self.opponent.id
        winner_address = self.ctx.bot.get_cog(f'Tip{self.currency.capitalize()}').get_address(str(winner.id))
        await self.ctx.bot.get_cog(f'Tip{self.currency.capitalize()}').get_withdraw(str(loser_id), winner_address, self.amount)

    def check_winner(self):
        board = [[None for _ in range(3)] for _ in range(3)]
        for item in self.children:
            if isinstance(item, TicTacToeButton):
                board[item.y][item.x] = item.label

        # Check rows
        for row in board:
            if row[0] == row[1] == row[2] and row[0] != '\u200b':
                return True

        # Check columns
        for col in range(3):
            if board[0][col] == board[1][col] == board[2][col] and board[0][col] != '\u200b':
                return True

        # Check diagonals
        if board[0][0] == board[1][1] == board[2][2] and board[0][0] != '\u200b':
            return True
        if board[0][2] == board[1][1] == board[2][0] and board[0][2] != '\u200b':
            return True

        return False

    def is_tie(self):
        for item in self.children:
            if isinstance(item, TicTacToeButton) and item.label == '\u200b':
                return False
        return True

    def disable_all_buttons(self):
        for item in self.children:
            if isinstance(item, TicTacToeButton):
                item.disabled = True

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def tictactoe(self, ctx, member: discord.Member, amount: int, currency: str):
        view = TicTacToeView(ctx, ctx.author, member, amount, currency)
        await ctx.send(f"{ctx.author.mention} vs {member.mention} - Tic Tac Toe!", view=view)

async def setup(bot):
    await bot.add_cog(TicTacToe(bot))

import random
import discord
import datetime
from discord.ext import commands, tasks

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

last_draw = None

@bot.command(name="로또")
async def lotto(ctx, num1: int, num2: int, num3: int, num4: int, num5: int, num6: int):
    lotto_num = [num1, num2, num3, num4, num5, num6]
    sorted(random.sample(range(1, 46), 6))
    if len(set(lotto_num)) != 6 or not all(1 <= n <= 45 for n in lotto_num):
        await ctx.send("1~45 사이의 숫자를 입력해주세요.")
    else:
        await ctx.send(
            f"당신이 선택한 로또 번호는 {lotto_num[0]}, {lotto_num[1]}, {lotto_num[2]}, {lotto_num[3]}, {lotto_num[4]}, {lotto_num[5]} 입니다."
        )

@tasks.loop(minutes=60)
async def lotto_task():
    global last_draw
    today = datetime.date.today()

    if last_draw is None or last_draw.date() != today:
        return

    draw_num = sorted(random.sample(range(1, 46), 6))
    await intents.send_message(f"{datetime}의 로또 당첨 번호는: {draw_num[0]}, {draw_num[1]}, {draw_num[2]}, {draw_num[3]}, {draw_num[4]}, {draw_num[5]} 입니다.")
import discord.ui
from discord import Interaction
from discord._types import ClientT
from service.user_service import register_user


class RegisterForm(discord.ui.Modal,title = "회원가입"):
    username = discord.ui.TextInput(
        label="홈페이지에서 사용 할 아이디",
        style=discord.TextStyle.short,
        required=True,
        max_length=64
    )
    password1 = discord.ui.TextInput(
        label = "비밀번호 (대문자, 숫자, 특수문자 포함)",
        style=discord.TextStyle.short,
        placeholder="••••••••",
        required=True,
        min_length=8,
        max_length=64
    )
    password2 = discord.ui.TextInput(
        label="비밀번호 재입력",
        style=discord.TextStyle.short,
        placeholder="••••••••",
        required=True,
        min_length=8,
        max_length=64
    )
    gender = discord.ui.TextInput(
        label="성별 (남성, 여성)",
        style=discord.TextStyle.short,
        required=True,
        max_length=64
    )
    async def on_submit(self, interaction: Interaction[ClientT]):
        try:
            user = await register_user(
                username=self.username.value,
                raw_password1=self.password1.value,
                raw_password2=self.password2.value,
                discord_id=interaction.user.id,
                gender = self.gender.value,
            )
        except Exception as e:
            return await interaction.response.send_message(f"{e} \n 회원가입을 다시 진행해주세요.", ephemeral=True)

        await interaction.response.send_message(f"가입 완료! 환영합니다, {interaction.user.display_name}님.")


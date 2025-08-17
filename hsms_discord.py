import discord
import asyncio
import os
from discord.ext import commands
# 새로운 모듈 구조에서 클래스 임포트
from HSMS import MainAI
from config import *

# Discord 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# 각 서버별로 MainAI 인스턴스를 관리
ai_instances = {}
debug_mode = False  # 전역 디버그 모드 설정

def get_ai_instance(guild_id, force_search=False):
    """서버별 AI 인스턴스를 가져오거나 생성합니다."""
    if guild_id not in ai_instances:
        ai_instances[guild_id] = MainAI(force_search=force_search, debug=debug_mode)
    return ai_instances[guild_id]

def set_debug_mode(debug):
    """디버그 모드를 설정합니다."""
    global debug_mode
    debug_mode = debug

@bot.event
async def on_ready():
    """봇이 준비되었을 때 실행되는 이벤트"""
    print(f'|| 로그인: {bot.user}(으)로 로그인했습니다!')
    print(f'|| 연결: {len(bot.guilds)}개 서버에 연결되어 있습니다.')
    
    # 봇 상태 설정
    activity = discord.Activity(type=discord.ActivityType.listening, name="계층적 기억 관리")
    await bot.change_presence(activity=activity)

@bot.event
async def on_message(message):
    """메시지를 받았을 때 실행되는 이벤트"""
    # 봇 자신의 메시지는 무시
    if message.author == bot.user:
        return
    
    # 명령어 처리
    await bot.process_commands(message)
    
    # DM이거나 봇이 멘션된 경우에만 응답
    if isinstance(message.channel, discord.DMChannel) or bot.user in message.mentions:
        # 멘션 제거
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        if not content:
            return
        
        # 타이핑 표시
        async with message.channel.typing():
            try:
                # 서버별 AI 인스턴스 가져오기
                guild_id = message.guild.id if message.guild else 'dm'
                ai_instance = get_ai_instance(guild_id)
                
                # AI 응답 생성
                response = await ai_instance.chat_async(content)
                
                # 응답이 너무 길면 잘라서 전송
                if len(response) > 2000:
                    response = response[:1997] + "..."
                
                await message.reply(response)
                
            except Exception as e:
                print(f"|| 오류: 메시지 처리 중 오류: {e}")
                await message.reply("죄송합니다. 처리 중 오류가 발생했습니다.")

@bot.command(name='help', aliases=['도움말'])
async def help_command(ctx):
    """도움말을 표시합니다."""
    embed = discord.Embed(
        title="|| 계층적 의미 기억 시스템 봇",
        description="저는 대화 내용을 기억하고 맥락을 이해하는 AI입니다!",
        color=0x00ff00
    )
    
    embed.add_field(
        name="|| 기본 사용법",
        value="• 봇을 멘션(@봇이름)하고 질문하세요\n• DM으로 직접 대화할 수 있습니다",
        inline=False
    )
    
    embed.add_field(
        name="🎯 명령어",
        value="""
        `!help` - 도움말 표시
        `!tree` - 현재 기억 트리 구조 표시
        `!status` - 봇 상태 정보
        `!clear` - 서버의 기억 초기화 (관리자만)
        `!force [on/off]` - 강제 검색 모드 토글 (관리자만)
        `!debug [on/off]` - 디버그 모드 토글 (관리자만)
        """,
        inline=False
    )
    
    embed.add_field(
        name="🌟 특징",
        value="• 계층적 트리 구조로 기억 관리\n• 비동기 병렬 검색으로 빠른 응답\n• 서버별 독립적인 기억 공간",
        inline=False
    )
    
    embed.set_footer(text="개발자: 계층적 의미 기억 시스템 팀")
    
    await ctx.send(embed=embed)

@bot.command(name='tree', aliases=['트리'])
async def tree_command(ctx):
    """현재 기억 트리 구조를 표시합니다."""
    try:
        guild_id = ctx.guild.id if ctx.guild else 'dm'
        ai_instance = get_ai_instance(guild_id)
        
        status = ai_instance.get_tree_status()
        tree_summary = status['tree_summary']
        
        # 트리 구조가 너무 길면 파일로 전송
        if len(tree_summary) > 1900:
            # 임시 파일 생성
            filename = f"tree_{guild_id}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"=== {ctx.guild.name if ctx.guild else 'DM'} 서버 기억 트리 ===\n")
                f.write(f"총 노드 수: {status['total_nodes']}\n\n")
                f.write(tree_summary)
            
            # 통계 정보는 임베드로 표시
            embed = discord.Embed(
                title="|| 기억 트리 통계",
                color=0x00ff00
            )
            embed.add_field(name="|| 트리 상태", value=f"총 노드 수: {status['total_nodes']}개\n트리가 커서 파일로 전송합니다.", inline=False)
            
            # 파일과 임베드를 함께 전송
            await ctx.send(embed=embed, file=discord.File(filename))
            
            # 임시 파일 삭제
            os.remove(filename)
        else:
            # 트리 구조는 일반 텍스트로 표시
            await ctx.send(f"```\n{tree_summary}\n```")
            
            # 통계 정보는 임베드로 표시
            embed = discord.Embed(
                title="|| 기억 트리 통계",
                color=0x00ff00
            )
            embed.add_field(name="|| 트리 상태", value=f"총 노드 수: {status['total_nodes']}개", inline=True)
            await ctx.send(embed=embed)
            
    except Exception as e:
        print(f"|| 오류: 트리 명령어 처리 중 오류: {e}")
        await ctx.send("트리 구조를 가져오는 중 오류가 발생했습니다.")

@bot.command(name='status', aliases=['상태'])
async def status_command(ctx):
    """봇 상태 정보를 표시합니다."""
    try:
        guild_id = ctx.guild.id if ctx.guild else 'dm'
        ai_instance = get_ai_instance(guild_id)
        status = ai_instance.get_tree_status()
        
        embed = discord.Embed(
            title="|| 봇 상태 정보",
            color=0x0099ff
        )
        
        embed.add_field(
            name="|| 기억 통계",
            value=f"• 총 노드 수: {status['total_nodes']}개\n• 강제 검색: {'ON' if ai_instance.force_search else 'OFF'}",
            inline=False
        )
        
        embed.add_field(
            name="🌐 서버 정보",
            value=f"• 연결된 서버: {len(bot.guilds)}개\n• 활성 AI 인스턴스: {len(ai_instances)}개",
            inline=False
        )
        
        embed.add_field(
            name="|| API 정보",
            value=f"• 메인 API 키: {len([k for k in API_KEY.values() if k])}개\n• LOAD API 키: {len(LOAD_API_KEYS)}개",
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        print(f"|| 오류: 상태 명령어 처리 중 오류: {e}")
        await ctx.send("상태 정보를 가져오는 중 오류가 발생했습니다.")

@bot.command(name='clear', aliases=['초기화'])
@commands.has_permissions(administrator=True)
async def clear_command(ctx):
    """서버의 기억을 초기화합니다. (관리자 전용)"""
    try:
        guild_id = ctx.guild.id if ctx.guild else 'dm'
        
        # 확인 메시지
        embed = discord.Embed(
            title="|| 기억 초기화 확인",
            description="정말로 이 서버의 모든 기억을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다!",
            color=0xff0000
        )
        
        message = await ctx.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message == message
        
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # AI 인스턴스 제거 (새로운 인스턴스가 생성됨)
                if guild_id in ai_instances:
                    del ai_instances[guild_id]
                
                await ctx.send("|| 완료: 서버의 기억이 초기화되었습니다.")
            else:
                await ctx.send("|| 취소: 초기화가 취소되었습니다.")
                
        except asyncio.TimeoutError:
            await ctx.send("|| 시간초과: 시간 초과로 초기화가 취소되었습니다.")
            
    except Exception as e:
        print(f"|| 오류: 초기화 명령어 처리 중 오류: {e}")
        await ctx.send("초기화 중 오류가 발생했습니다.")

@bot.command(name='force', aliases=['강제'])
@commands.has_permissions(administrator=True)
async def force_command(ctx, mode: str = None):
    """강제 검색 모드를 토글합니다. (관리자 전용)"""
    try:
        guild_id = ctx.guild.id if ctx.guild else 'dm'
        ai_instance = get_ai_instance(guild_id)
        
        if mode is None:
            # 현재 상태 표시
            status = "ON" if ai_instance.force_search else "OFF"
            await ctx.send(f"|| 검색모드: 현재 강제 검색 모드: **{status}**")
            return
        
        mode = mode.lower()
        if mode in ['on', '켜기', '활성화']:
            ai_instance.force_search = True
            await ctx.send("|| 활성화: 강제 검색 모드가 **활성화**되었습니다.\n모든 대화에서 기억 탐색을 수행합니다.")
        elif mode in ['off', '끄기', '비활성화']:
            ai_instance.force_search = False
            await ctx.send("|| 비활성화: 강제 검색 모드가 **비활성화**되었습니다.\n효율적인 모드로 동작합니다.")
        else:
            await ctx.send("|| 오류: 올바른 모드를 입력하세요. (on/off, 켜기/끄기)")
            
    except Exception as e:
        print(f"|| 오류: 강제 모드 명령어 처리 중 오류: {e}")
        await ctx.send("강제 모드 설정 중 오류가 발생했습니다.")

@bot.command(name='debug', aliases=['디버그'])
@commands.has_permissions(administrator=True)
async def debug_command(ctx, mode=None):
    """디버그 모드를 켜거나 끕니다."""
    global debug_mode
    
    try:
        if mode is None:
            # 현재 상태 확인
            status = "켜짐" if debug_mode else "꺼짐"
            await ctx.send(f">> 디버그모드: 현재 디버그 모드: **{status}**")
            return
        
        mode_lower = mode.lower()
        if mode_lower in ['on', '켜기', 'true', '1']:
            debug_mode = True
            # 기존 AI 인스턴스들의 디버그 모드도 업데이트
            for guild_id in ai_instances:
                ai_instances[guild_id].debug = True
                ai_instances[guild_id].auxiliary_ai.debug = True
            await ctx.send("|| 활성화: 디버그 모드가 **켜졌습니다**.\n상세 분류 과정이 콘솔에 출력됩니다.")
        elif mode_lower in ['off', '끄기', 'false', '0']:
            debug_mode = False
            # 기존 AI 인스턴스들의 디버그 모드도 업데이트
            for guild_id in ai_instances:
                ai_instances[guild_id].debug = False
                ai_instances[guild_id].auxiliary_ai.debug = False
            await ctx.send("|| 비활성화: 디버그 모드가 **꺼졌습니다**.")
        else:
            await ctx.send("|| 오류: 올바른 모드를 입력하세요. (on/off, 켜기/끄기)")
            
    except Exception as e:
        print(f"|| 오류: 디버그 모드 명령어 처리 중 오류: {e}")
        await ctx.send("디버그 모드 설정 중 오류가 발생했습니다.")

@clear_command.error
@force_command.error
@debug_command.error
async def permission_error(ctx, error):
    """권한 오류 처리"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("|| 오류: 이 명령어는 관리자만 사용할 수 있습니다.")

def run_bot():
    """Discord 봇을 실행합니다."""
    # Discord 토큰 확인
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        print("|| 오류: DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.")
        print("Discord 봇을 실행하려면 .env 파일에 DISCORD_TOKEN을 추가하세요.")
        return
    
    try:
        print("|| 시작: Discord 봇을 시작하는 중...")
        bot.run(discord_token)
    except discord.LoginFailure:
        print("|| 오류: Discord 토큰이 올바르지 않습니다.")
    except Exception as e:
        print(f"|| 오류: Discord 봇 실행 중 오류 발생: {e}")

if __name__ == '__main__':
    run_bot()

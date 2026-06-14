"""
bots/discord_bot.py — Discord bot for kirannn
Requires DISCORD_TOKEN in .env

Commands:
  !ask   <message>  → chat with the main agent
  !code  <task>     → coding agent
  !research <query> → research + analysis pipeline
  !debate <topic>   → 3-model debate with voting
  !memory           → show recent memory
  !health           → check system status
  !help             → list commands
"""
from core.logger import logger
import os
import requests

API_BASE = "http://localhost:8000"
TIMEOUT_CHAT = 120
TIMEOUT_RESEARCH = 180
TIMEOUT_DEBATE = 240


def _api_post(path: str, payload: dict, timeout: int = TIMEOUT_CHAT) -> str:
    """POST to kirannn API, return response text or error string."""
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
        data = r.json()
        return (
            data.get("response")
            or data.get("best_answer")
            or data.get("analysis")
            or data.get("result")
            or str(data)
        )
    except requests.exceptions.Timeout:
        return "⏳ Request timed out — the agent is still thinking. Try a shorter query."
    except Exception as e:
        return f"❌ API error: {e}"


def _api_get(path: str, timeout: int = 10) -> dict:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=timeout)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _truncate(text: str, limit: int = 1900) -> str:
    """Discord messages have a 2000-char limit."""
    if len(text) <= limit:
        return text
    return text[:limit - 20] + "\n…[truncated]"


def run_discord_bot():
    """Entry point called by main.py."""
    try:
        import discord
        from discord.ext import commands
    except ImportError:
        logger.info("[DISCORD] discord.py not installed → pip install discord.py")
        return

    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        logger.info("[DISCORD] DISCORD_TOKEN not set → skipping Discord bot")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    # ── Events ─────────────────────────────────────────────────────────────

    @bot.event
    async def on_ready():
        logger.info(f"[DISCORD] ✅ Logged in as {bot.user} (ID: {bot.user.id})")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for !ask commands"
            )
        )

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("❓ Unknown command. Use `!help` to see available commands.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Missing argument. Usage: `!{ctx.command.name} <your text>`")
        else:
            await ctx.send(f"❌ Error: {error}")

    # ── Commands ───────────────────────────────────────────────────────────

    @bot.command(name="ask", help="Chat with the main kirannn agent")
    async def ask(ctx, *, message: str):
        thinking = await ctx.send("🤔 Thinking...")
        reply = _api_post("/chat", {
            "message": message,
            "session_id": f"discord_{ctx.author.id}"
        })
        await thinking.edit(content=_truncate(f"**kirannn:** {reply}"))

    @bot.command(name="code", help="Ask the coding agent to write or fix code")
    async def code(ctx, *, task: str):
        thinking = await ctx.send("💻 Coding...")
        reply = _api_post("/chat/code", {
            "message": task,
            "session_id": f"discord_{ctx.author.id}"
        })
        # Wrap in code block if response contains code
        if "```" not in reply:
            reply = f"```python\n{reply}\n```" if "def " in reply or "import " in reply else reply
        await thinking.edit(content=_truncate(reply))

    @bot.command(name="research", help="Deep research + analysis on any topic")
    async def research(ctx, *, query: str):
        thinking = await ctx.send("🔍 Researching... (this takes 1-3 min)")
        reply = _api_post("/chat/research", {
            "message": query,
            "session_id": f"discord_{ctx.author.id}"
        }, timeout=TIMEOUT_RESEARCH)
        await thinking.edit(content=_truncate(f"📊 **Research:** {reply}"))

    @bot.command(name="debate", help="3-model AI debate on any topic")
    async def debate(ctx, *, topic: str):
        thinking = await ctx.send("⚖️ Starting debate between 3 AI models...")
        reply = _api_post("/chat/debate", {"message": topic}, timeout=TIMEOUT_DEBATE)
        await thinking.edit(content=_truncate(f"🏆 **Best Answer:** {reply}"))

    @bot.command(name="memory", help="Show kirannn's recent memory")
    async def memory(ctx):
        data = _api_get("/memory")
        mem = data.get("result", "Memory empty or unavailable.")
        await ctx.send(_truncate(f"🧠 **Memory:**\n```\n{mem}\n```"))

    @bot.command(name="health", help="Check kirannn system status")
    async def health(ctx):
        data = _api_get("/health")
        ollama = data.get("ollama", "unknown")
        models = data.get("models", [])
        version = data.get("version", "?")
        mem = data.get("memory", {})
        status = (
            f"**kirannn v{version} Status**\n"
            f"{'✅' if ollama == 'ok' else '❌'} Ollama: `{ollama}`\n"
            f"🤖 Models: `{', '.join(models) or 'none'}`\n"
            f"🧠 Memory: `{mem}`"
        )
        await ctx.send(status)

    @bot.command(name="skills", help="List auto-generated skills")
    async def skills(ctx):
        data = _api_get("/skills")
        skills_list = data.get("skills", [])
        if not skills_list:
            await ctx.send("📦 No skills generated yet. Use `!ask` to trigger self-coding.")
            return
        names = "\n".join(f"• `{s['name']}`" for s in skills_list)
        await ctx.send(f"🔧 **Available Skills ({data.get('count', 0)}):**\n{names}")

    @bot.command(name="plan", help="Generate a multi-step plan for a goal")
    async def plan(ctx, *, goal: str):
        thinking = await ctx.send("📋 Planning...")
        try:
            r = requests.post(f"{API_BASE}/plan",
                json={"goal": goal, "execute": False}, timeout=60)
            data = r.json()
            if "plan" in data or "success" in data:
                from core.planner import format_plan_md
                plan_text = format_plan_md(data)
            else:
                plan_text = data.get("plan_text") or data.get("raw") or str(data)
        except Exception as e:
            plan_text = f"Planning error: {e}"
        await thinking.edit(content=_truncate(f"📋 **Plan:**\n{plan_text}"))

    @bot.remove_command("help")  # remove default ugly help
    @bot.command(name="help", help="Show all commands")
    async def help_cmd(ctx):
        embed = discord.Embed(
            title="🤖 kirannn — Command Reference",
            description="Autonomous AI Agent System",
            color=0x7C3AED
        )
        embed.add_field(name="!ask <message>",    value="Chat with main agent",          inline=False)
        embed.add_field(name="!code <task>",      value="Coding agent (Python/bash)",    inline=False)
        embed.add_field(name="!research <query>", value="Deep research + analysis",      inline=False)
        embed.add_field(name="!debate <topic>",   value="3-model AI debate",             inline=False)
        embed.add_field(name="!plan <goal>",      value="Generate multi-step plan",      inline=False)
        embed.add_field(name="!memory",           value="Show agent memory",             inline=False)
        embed.add_field(name="!health",           value="System status check",           inline=False)
        embed.add_field(name="!skills",           value="List auto-generated skills",    inline=False)
        embed.set_footer(text="Prefix: ! | kirannn v3.0 | by Kiran")
        await ctx.send(embed=embed)

    # ── Run ────────────────────────────────────────────────────────────────
    logger.info("[DISCORD] Starting bot...")
    bot.run(TOKEN)

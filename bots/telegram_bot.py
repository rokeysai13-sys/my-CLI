"""
bots/telegram_bot.py — Full Telegram Gateway for kirannn
"""
from core.logger import logger
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    OK = True
except ImportError:
    OK = False

from core.agent import run_agent, run_debate, run_code_agent, run_research_agent, run_full_pipeline
from core.tools import shell_exec, memory_append, memory_read, file_read, web_search
from core.planner import decompose, format_plan_md

TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

async def notify(app, msg: str):
    """Push proactive message from heartbeat."""
    if CHAT_ID:
        await app.bot.send_message(chat_id=CHAT_ID, text=msg)

async def start(u: Update, c):
    await u.message.reply_text(
        "🦾 *kirannn Agent Online*\n\n"
        "*Agent Commands:*\n"
        "/agent — Master agent (tool-use)\n"
        "/plan — Decompose + execute a big task\n"
        "/debate — 3 models debate\n"
        "/code — Write & run code\n"
        "/research — Deep web research\n\n"
        "*System Commands:*\n"
        "/shell — Run terminal command\n"
        "/read — Read a file\n"
        "/write path|content — Write a file\n"
        "/search — Web search\n"
        "/memory — View memory\n"
        "/remember — Save to memory\n"
        "/reports — List saved reports\n"
        "/selfcode — Create a new skill\n"
        "/status — Health check\n\n"
        "_Or just message me anything!_",
        parse_mode="Markdown"
    )

async def cmd_plan(u: Update, c):
    goal = " ".join(c.args)
    if not goal: await u.message.reply_text("Usage: /plan <your big goal>"); return
    await u.message.reply_text("🧠 Decomposing your goal into a plan...")
    plan = decompose(goal)
    md = format_plan_md(plan)
    await u.message.reply_text(md[:3000])
    if plan.get("success"):
        await u.message.reply_text("⚡ Executing plan with sub-agents... (this may take a few minutes)")
        result = run_full_pipeline(goal)
        resp = result.get("response", "")[:2000]
        path = result.get("report_path", "")
        await u.message.reply_text(f"✅ Done!\n\n{resp}\n\n📄 Report: `{path}`", parse_mode="Markdown")

async def cmd_agent(u: Update, c):
    msg = " ".join(c.args)
    if not msg: await u.message.reply_text("Usage: /agent <request>"); return
    await u.message.reply_text("🔄 Agent working...")
    r = run_agent(msg)
    trace_str = ""
    if r.get("trace"):
        trace_str = "\n\n🔧 " + ", ".join(t["tool"] for t in r["trace"])
    await u.message.reply_text(f"{r.get('response','')[:2000]}{trace_str}")

async def cmd_debate(u: Update, c):
    msg = " ".join(c.args)
    if not msg: await u.message.reply_text("Usage: /debate <question>"); return
    await u.message.reply_text("⚔️ 3 models debating...")
    r = run_debate(msg)
    await u.message.reply_text(f"🏆 *Best ({r['winner']}):\n{r['best'][:1500]}", parse_mode="Markdown")

async def cmd_code(u: Update, c):
    msg = " ".join(c.args)
    if not msg: await u.message.reply_text("Usage: /code <task>"); return
    await u.message.reply_text("💻 Coding...")
    r = run_code_agent(msg)
    resp = r.get("response", r.get("code", ""))[:1500]
    ex = r.get("executed")
    extra = f"\n\n✅ Output:\n```{ex.get('stdout','')[:400]}```" if ex and ex.get("success") else ""
    await u.message.reply_text(f"{resp}{extra}", parse_mode="Markdown")

async def cmd_research(u: Update, c):
    msg = " ".join(c.args)
    if not msg: await u.message.reply_text("Usage: /research <topic>"); return
    await u.message.reply_text("🔬 Researching...")
    r = run_research_agent(msg)
    await u.message.reply_text(r.get("response","")[:2000])

async def cmd_shell(u: Update, c):
    cmd = " ".join(c.args)
    if not cmd: await u.message.reply_text("Usage: /shell <command>"); return
    r = shell_exec(cmd)
    out = (r.get("stdout") or r.get("stderr") or "No output")[:1000]
    await u.message.reply_text(f"```{out}```", parse_mode="Markdown")

async def cmd_search(u: Update, c):
    q = " ".join(c.args)
    if not q: await u.message.reply_text("Usage: /search <query>"); return
    r = web_search(q)
    results = r.get("results", [])
    text = "\n".join(f"• {url}\n  {snip[:100]}" for url, snip in results[:4])
    await u.message.reply_text(f"🔍 *{q}*\n{text}", parse_mode="Markdown")

async def cmd_memory(u: Update, c):
    r = memory_read()
    await u.message.reply_text(f"```{r.get('result','Empty')[:1500]}```", parse_mode="Markdown")

async def cmd_remember(u: Update, c):
    fact = " ".join(c.args)
    if not fact: return
    memory_append(f"[User] {fact}", "Important Facts")
    await u.message.reply_text(f"✅ Saved: {fact}")

async def cmd_read(u: Update, c):
    path = " ".join(c.args)
    r = file_read(path)
    await u.message.reply_text(f"```{r.get('result',r.get('error',''))[:1500]}```", parse_mode="Markdown")

async def cmd_write(u: Update, c):
    text = " ".join(c.args)
    if "|" not in text: await u.message.reply_text("Usage: /write path|content"); return
    path, content = text.split("|",1)
    from core.tools import file_write
    r = file_write(path.strip(), content.strip())
    await u.message.reply_text("✅ " + r.get("result", r.get("error","")))

async def cmd_reports(u: Update, c):
    from core.tools import list_reports
    r = list_reports()
    files = r.get("result", [])
    if not files: await u.message.reply_text("No reports yet."); return
    await u.message.reply_text("📄 Reports:\n" + "\n".join(f"• {f}" for f in files[-10:]))

async def cmd_selfcode(u: Update, c):
    cap = " ".join(c.args)
    if not cap: await u.message.reply_text("Usage: /selfcode <capability description>"); return
    await u.message.reply_text("🧬 Writing new skill code...")
    from core.subagents import self_coder_agent
    r = self_coder_agent(cap)
    if r.get("success"):
        await u.message.reply_text(f"✅ New skill created: `{r['skill_name']}`\n```python\n{r['code'][:800]}\n```", parse_mode="Markdown")
    else:
        await u.message.reply_text(f"❌ Failed: {r.get('error')}")

async def cmd_status(u: Update, c):
    import requests
    lines = ["🖥️ *kirannn Status*"]
    for name, url in [("API", "http://localhost:8000/health"), ("Ollama", "http://localhost:11434/api/tags")]:
        try:
            r = requests.get(url, timeout=3)
            if name == "API":
                d = r.json()
                lines.append(f"✅ API: online | {len(d.get('models',[]))} models")
            else:
                lines.append(f"✅ {name}: online")
        except:
            lines.append(f"❌ {name}: offline")
    reports_count = len(list((Path(__file__).parent.parent/"reports").glob("*.md")))
    lines.append(f"📄 Reports saved: {reports_count}")
    await u.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def handle_msg(u: Update, c):
    """Default message handler — streams response as it generates."""
    msg   = u.message.text
    sid   = f"tg_{u.effective_user.id}"
    # Send a placeholder message we'll edit with streaming chunks
    placeholder = await u.message.reply_text("⏳ Thinking...")
    try:
        import requests as req, json
        r = req.post(
            "http://localhost:8000/chat",
            json={"message": msg, "session_id": sid, "stream": True},
            stream=True, timeout=120
        )
        full = ""
        last_edit_len = 0
        for line in r.iter_lines():
            if not line:
                continue
            raw = line.decode("utf-8") if isinstance(line, bytes) else line
            if not raw.startswith("data:"):
                continue
            try:
                data = json.loads(raw[5:])
            except Exception:
                continue
            if data.get("type") == "token":
                full += data["text"]
                # Edit every ~80 new chars to avoid Telegram rate-limit
                if len(full) - last_edit_len >= 80:
                    try:
                        await placeholder.edit_text(full[-3800:] or "...")
                        last_edit_len = len(full)
                    except Exception:
                        pass
            elif data.get("type") == "done":
                full = data.get("full", full)
                break
        final_text = (full or "No response")[-4000:]
        await placeholder.edit_text(final_text)
    except Exception as e:
        # Fallback to non-streaming if SSE fails
        try:
            r_plain = run_agent(msg)
            await placeholder.edit_text(r_plain.get("response", str(e))[:4000])
        except Exception as e2:
            await placeholder.edit_text(f"❌ Error: {e2}")

async def cmd_stream(u: Update, c):
    """Explicit /stream command to test streaming."""
    msg = " ".join(c.args)
    if not msg:
        await u.message.reply_text("Usage: /stream <your question>")
        return
    # Reuse handle_msg with a fake Update replacement
    u.message.text = msg
    await handle_msg(u, c)

def run_telegram_bot():
    if not OK: print("[TELEGRAM] Not installed — pip install python-telegram-bot"); return
    if not TOKEN: print("[TELEGRAM] TELEGRAM_TOKEN not set"); return
    app = Application.builder().token(TOKEN).build()
    for cmd, fn in [("start",start),("plan",cmd_plan),("agent",cmd_agent),
                    ("debate",cmd_debate),("code",cmd_code),("research",cmd_research),
                    ("shell",cmd_shell),("search",cmd_search),("memory",cmd_memory),
                    ("remember",cmd_remember),("read",cmd_read),("write",cmd_write),
                    ("reports",cmd_reports),("selfcode",cmd_selfcode),("status",cmd_status),
                    ("stream", cmd_stream)]:
        app.add_handler(CommandHandler(cmd, fn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    logger.info("[TELEGRAM] Bot starting with streaming support...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent/".env")
    run_telegram_bot()
import os
import sys
import socket
import requests
import psutil

def system_checkup():
    """Run a comprehensive local system diagnostics checkup."""
    report = []
    report.append("==========================================")
    report.append("       KIRANNN SYSTEM DIAGNOSTICS         ")
    report.append("==========================================")
    
    # 1. OS & Hardware Info
    report.append("\n[1] CPU & OS INFO:")
    report.append(f"  Platform:        {sys.platform}")
    report.append(f"  CPU Count:       {psutil.cpu_count(logical=False)} physical, {psutil.cpu_count(logical=True)} logical")
    try:
        report.append(f"  CPU Usage:       {psutil.cpu_percent(interval=0.5)}%")
    except:
        report.append("  CPU Usage:       Unable to read")
        
    # 2. RAM Memory Info
    mem = psutil.virtual_memory()
    report.append("\n[2] MEMORY (RAM) INFO:")
    report.append(f"  Total Memory:    {mem.total / (1024**3):.2f} GB")
    report.append(f"  Available:       {mem.available / (1024**3):.2f} GB")
    report.append(f"  Used Memory:     {mem.used / (1024**3):.2f} GB ({mem.percent}%)")

    # 3. Disk Usage Info
    report.append("\n[3] DISK USAGE:")
    try:
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt' and 'cdrom' in part.opts:
                continue
            usage = psutil.disk_usage(part.mountpoint)
            report.append(f"  Drive {part.mountpoint} ({part.fstype}):")
            report.append(f"    Total Space:   {usage.total / (1024**3):.2f} GB")
            report.append(f"    Free Space:    {usage.free / (1024**3):.2f} GB ({usage.percent}% used)")
    except Exception as e:
        report.append(f"  Error reading disk usage: {e}")

    # 4. Service Ports check
    report.append("\n[4] LOCAL SERVICES & NETWORK:")
    services = [
        ("FastAPI Server", 8000),
        ("Ollama Service", 11434),
        ("Redis Server", 6379)
    ]
    for name, port in services:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            res = s.connect_ex(('127.0.0.1', port))
            status = "ONLINE (Listening)" if res == 0 else "OFFLINE"
            report.append(f"  - {name} (Port {port}): {status}")
        except Exception as e:
            report.append(f"  - {name} (Port {port}): Error ({e})")
        finally:
            s.close()

    # 5. Check active Ollama models
    report.append("\n[5] OLLAMA INSTALLED MODELS:")
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            if models:
                for m in models:
                    report.append(f"  - {m}")
            else:
                report.append("  - (No models pulled/found)")
        else:
            report.append(f"  - (Error getting models: HTTP {r.status_code})")
    except Exception as e:
        report.append(f"  - (Ollama service offline or unreachable: {e})")

    # 6. Check environment configuration
    report.append("\n[6] APP CONFIG CHECK:")
    try:
        # Resolve config imports relative to project base
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config.loader import cfg
        tg_set = "Yes (Configured)" if os.getenv("TELEGRAM_TOKEN") else "No (Skipped)"
        dc_set = "Yes (Configured)" if os.getenv("DISCORD_TOKEN") else "No (Skipped)"
        report.append(f"  Telegram Bot Token: {tg_set}")
        report.append(f"  Discord Bot Token:  {dc_set}")
        report.append(f"  Database URL:       {cfg('database', 'url', default='sqlite:///my_ai_team.db')}")
    except Exception as e:
        report.append(f"  Error checking config: {e}")

    report.append("\n==========================================")
    report_text = "\n".join(report)
    return {"success": True, "result": report_text}

#!/usr/bin/env python3
"""
cli.py — Kirannn Interactive Command Line Interface Chat
Talks directly to the FastAPI backend with streaming responses.
"""
import sys
import os
import json
import requests
from pathlib import Path

# ANSI colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

BANNER = f"""{Colors.BLUE}{Colors.BOLD}
  ██╗  ██╗██╗██████╗  █████╗ ███╗   ██╗███╗   ██╗███╗   ██╗
  ██║ ██╔╝██║██╔══██╗██╔══██╗████╗  ██║████╗  ██║████╗  ██║
  █████╔╝ ██║██████╔╝███████║██╔██╗ ██║██╔██╗ ██║██╔██╗ ██║
  ██╔═██╗ ██║██╔══██╗██╔══██║██║╚██╗██║██║╚██╗██║██║╚██╗██║
  ██║  ██╗██║██║  ██║██║  ██║██║ ╚████║██║ ╚████║██║ ╚████║
  ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═══╝╚═╝  ╚═══╝
               {Colors.CYAN}Kirannn CLI Workspace v1.0{Colors.ENDC}
"""

API_URL = "http://127.0.0.1:8000"
SESSION_ID = "cli_session"
CURRENT_AGENT = "master" # Options: master, debate, code, research, pipeline
CURRENT_MODEL = None

AGENT_ENDPOINTS = {
    "master": "/chat/agent",
    "debate": "/chat/debate",
    "code": "/chat/code",
    "research": "/chat/research",
    "pipeline": "/chat/pipeline"
}

def check_server():
    try:
        r = requests.get(f"{API_URL}/health", timeout=2)
        return r.status_code == 200
    except:
        return False

def show_status():
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        if r.status_code == 200:
            data = r.json()
            print(f"\n{Colors.GREEN}{Colors.BOLD}● Backend Status: Online{Colors.ENDC}")
            print(f"  Version:     {data.get('version', 'unknown')}")
            print(f"  Ollama link: {data.get('ollama', 'unknown')}")
            print(f"  Vector DB:   {data.get('memory', 'unknown')}")
            print(f"  Loaded Models:")
            for m in data.get("models", []):
                print(f"    - {m}")
        else:
            print(f"\n{Colors.FAIL}Backend health returned status: {r.status_code}{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}Could not get status: {e}{Colors.ENDC}")

def show_help():
    print(f"""
{Colors.BOLD}Available commands:{Colors.ENDC}
  {Colors.CYAN}/help{Colors.ENDC}             Show this help menu
  {Colors.CYAN}/status{Colors.ENDC}           Check backend health and loaded models
  {Colors.CYAN}/agent [name]{Colors.ENDC}    Switch active agent (master, debate, code, research, pipeline)
  {Colors.CYAN}/model [name]{Colors.ENDC}    Specify a target model (default: backend fallback)
  {Colors.CYAN}/clear{Colors.ENDC}            Clear the screen
  {Colors.CYAN}/exit{Colors.ENDC} or {Colors.CYAN}/quit{Colors.ENDC}  Exit the chat
""")

def send_chat(message: str):
    global CURRENT_AGENT, CURRENT_MODEL
    endpoint = AGENT_ENDPOINTS.get(CURRENT_AGENT, "/chat/agent")
    url = f"{API_URL}{endpoint}"
    
    # Only the master agent supports streaming currently
    is_stream = (CURRENT_AGENT == "master")
    
    payload = {
        "message": message,
        "session_id": SESSION_ID,
        "stream": is_stream
    }
    if CURRENT_MODEL:
        payload["model"] = CURRENT_MODEL

    print(f"\n{Colors.CYAN}{Colors.BOLD}kirannn ({CURRENT_AGENT}) > {Colors.ENDC}", end="", flush=True)

    try:
        if is_stream:
            r = requests.post(url, json=payload, stream=True, timeout=120)
            if r.status_code != 200:
                print(f"{Colors.FAIL}Error {r.status_code}: {r.text}{Colors.ENDC}")
                return
                
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        try:
                            data = json.loads(decoded[6:])
                            if data.get("type") == "token":
                                sys.stdout.write(data.get("text", ""))
                                sys.stdout.flush()
                        except:
                            pass
            print() # New line after stream complete
        else:
            print(f"{Colors.WARNING}(Streaming not supported for {CURRENT_AGENT} mode. Waiting for response...){Colors.ENDC}")
            r = requests.post(url, json=payload, timeout=120)
            if r.status_code == 200:
                res = r.json()
                response_text = res.get("response", "") or res.get("result", "")
                if isinstance(response_text, dict):
                    print(json.dumps(response_text, indent=2))
                else:
                    print(response_text)
            else:
                print(f"{Colors.FAIL}Error {r.status_code}: {r.text}{Colors.ENDC}")
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}(Interrupted by user){Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}Error connecting to backend: {e}{Colors.ENDC}")

def main():
    global CURRENT_AGENT, CURRENT_MODEL
    
    # Enable ANSI escape sequences on Windows 10+ CMD
    if sys.platform == "win32":
        os.system("color")
        
    print(BANNER)
    
    if not check_server():
        print(f"{Colors.FAIL}{Colors.BOLD}● Error: Backend server is offline!{Colors.ENDC}")
        print(f"Please run {Colors.BOLD}py main.py{Colors.ENDC} in another terminal before starting the CLI.\n")
        sys.exit(1)
        
    print(f"{Colors.GREEN}Successfully connected to backend on {API_URL}{Colors.ENDC}")
    print(f"Type {Colors.CYAN}/help{Colors.ENDC} for options. Talk to the agent below:")
    
    while True:
        try:
            # Display prompt
            prompt_str = f"\nYou > "
            user_input = input(prompt_str).strip()
            
            if not user_input:
                continue
                
            # Handle commands
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0].lower()
                
                if cmd in ["/exit", "/quit"]:
                    print(f"\n{Colors.BLUE}Goodbye!{Colors.ENDC}")
                    break
                elif cmd == "/help":
                    show_help()
                elif cmd == "/status":
                    show_status()
                elif cmd == "/clear":
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(BANNER)
                elif cmd == "/agent":
                    if len(parts) < 2:
                        print(f"Current agent: {CURRENT_AGENT}. Options: {', '.join(AGENT_ENDPOINTS.keys())}")
                    else:
                        target = parts[1].lower()
                        if target in AGENT_ENDPOINTS:
                            CURRENT_AGENT = target
                            print(f"{Colors.GREEN}Switched agent to: {CURRENT_AGENT}{Colors.ENDC}")
                        else:
                            print(f"{Colors.FAIL}Unknown agent. Options: {', '.join(AGENT_ENDPOINTS.keys())}{Colors.ENDC}")
                elif cmd == "/model":
                    if len(parts) < 2:
                        print(f"Current model: {CURRENT_MODEL or 'Default (backend fallback)'}")
                    else:
                        val = parts[1]
                        if val.lower() in ["clear", "default", "none"]:
                            CURRENT_MODEL = None
                            print(f"{Colors.GREEN}Model set back to default.{Colors.ENDC}")
                        else:
                            CURRENT_MODEL = val
                            print(f"{Colors.GREEN}Target model set to: {CURRENT_MODEL}{Colors.ENDC}")
                else:
                    print(f"{Colors.FAIL}Unknown command: {cmd}. Type /help for options.{Colors.ENDC}")
            else:
                send_chat(user_input)
                
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.BLUE}Goodbye!{Colors.ENDC}")
            break

if __name__ == "__main__":
    main()

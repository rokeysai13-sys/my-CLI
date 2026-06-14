"""
core/multi_agent.py — Multi-Agent Operating System Engine
Implements dynamic agent spawning, message bus routing, shared working memory (blackboard),
step budgeting, prioritizations, and consensus-based council voting.
"""
import os
import re
import json
import time
import datetime
from pathlib import Path
from core.logger import logger
from core.llm import llm_generate
from core.tools import call_tool, tools_manifest

DECISION_LOG_FILE = Path(__file__).parent.parent / "memory" / "decision_log.json"

class SharedWorkingMemory:
    """
    Key-Value Blackboard that acts as the single source of truth for the active mission.
    Maintains a detailed audit log of all write operations.
    """
    def __init__(self):
        self.data = {}
        self.audit_log = []

    def write(self, key: str, value: str, agent_name: str, rationale: str):
        self.data[key] = value
        self.audit_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "agent": agent_name,
            "key": key,
            "value": value,
            "rationale": rationale
        })
        logger.info(f"[BLACKBOARD WRITE] Agent '{agent_name}' updated key '{key}' with rationale: {rationale}")

    def read(self, key: str) -> str:
        return self.data.get(key)

    def get_all(self) -> dict:
        return self.data

    def get_audit_log(self) -> list:
        return self.audit_log

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "audit_log": self.audit_log
        }

    def from_dict(self, state: dict):
        if not state:
            return
        self.data = state.get("data", {})
        self.audit_log = state.get("audit_log", [])


class Message:
    def __init__(self, sender: str, recipient: str, content: str, timestamp: str = None):
        self.sender = sender
        self.recipient = recipient
        self.content = content
        self.timestamp = timestamp or datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp
        }


class MessageBus:
    """
    Routes communication between spawned agents.
    """
    def __init__(self):
        self.inboxes = {}

    def register_agent(self, agent_name: str):
        if agent_name not in self.inboxes:
            self.inboxes[agent_name] = []

    def send_message(self, sender: str, recipient: str, content: str):
        self.register_agent(recipient)
        msg = Message(sender, recipient, content)
        self.inboxes[recipient].append(msg)
        logger.info(f"[MESSAGE BUS] Message from '{sender}' to '{recipient}': {content[:100]}...")

    def get_messages(self, agent_name: str) -> list:
        """Returns and drains messages for the agent."""
        if agent_name not in self.inboxes:
            return []
        msgs = self.inboxes[agent_name]
        self.inboxes[agent_name] = []
        return msgs


class AgentInstance:
    """
    Represents a dynamically spawned specialist agent with a budget, priority, and role prompt.
    """
    def __init__(self, name: str, role: str, role_description: str, budget: int = 10, priority: str = "medium"):
        self.name = name
        self.role = role
        self.role_description = role_description
        self.budget = budget
        self.priority = priority  # high, medium, low
        self.status = "continue"  # continue, done

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "role_description": self.role_description,
            "budget": self.budget,
            "priority": self.priority,
            "status": self.status
        }

    def execute_loop_step(self, blackboard: SharedWorkingMemory, message_bus: MessageBus, goal: str) -> dict:
        """
        Executes a single step in the agent's loop. Parses its input and updates blackboard/sends messages.
        """
        if self.budget <= 0:
            self.status = "done"
            logger.info(f"[AGENT {self.name}] Step budget exhausted.")
            return {"status": "done", "reason": "Budget exhausted"}

        self.budget -= 1

        # Fetch inbox
        inbox_msgs = message_bus.get_messages(self.name)
        inbox_str = ""
        if inbox_msgs:
            inbox_str = "\n".join([f"From {m.sender}: {m.content}" for m in inbox_msgs])
        else:
            inbox_str = "(No new messages)"

        # Compile blackboard state
        blackboard_data = blackboard.get_all()
        blackboard_str = json.dumps(blackboard_data, indent=2) if blackboard_data else "(Blackboard is empty)"

        # Prepare tools
        manifest = tools_manifest()

        system_prompt = (
            f"You are the {self.name} ({self.role}) in a Multi-Agent Operating System team.\n"
            f"Your role description:\n{self.role_description}\n\n"
            f"The team is collaborating to achieve the overall goal: '{goal}'.\n"
            f"You communicate with other agents via the message bus and write key results/designs/code to the shared working memory blackboard.\n"
            f"Always consider information on the blackboard and messages in your inbox. Use tools to query the environment, write files, or execute tests."
        )

        prompt = (
            f"--- MISSION GOAL ---\n{goal}\n\n"
            f"--- SHARED BLACKBOARD ---\n{blackboard_str}\n\n"
            f"--- YOUR INBOX ---\n{inbox_str}\n\n"
            f"--- REMAINING STEP BUDGET ---\n{self.budget} steps remaining.\n\n"
            f"--- AVAILABLE TOOLS ---\n{manifest}\n\n"
            f"Decide your next action. You can perform ONE of the following action types:\n"
            f"1. Update the blackboard (action: 'update_memory')\n"
            f"2. Send a message to another agent (action: 'send_message')\n"
            f"3. Call a tool (action: 'call_tool')\n"
            f"4. Do nothing / wait (action: 'none')\n\n"
            f"If you have completed your contributions and have nothing more to do, set 'status' to 'done'.\n\n"
            f"Response format: Respond ONLY in valid JSON format matching this exact schema:\n"
            f"{{\n"
            f"  \"thought\": \"Your detailed reasoning about what to do next.\",\n"
            f"  \"action\": \"call_tool\" | \"update_memory\" | \"send_message\" | \"none\",\n"
            f"  \"tool_name\": \"name_of_tool_to_call\",\n"
            f"  \"tool_args\": {{}},\n"
            f"  \"memory_update\": {{\n"
            f"    \"key\": \"blackboard_key_to_update\",\n"
            f"    \"value\": \"value_to_write\",\n"
            f"    \"rationale\": \"explanation for this update\"\n"
            f"  }},\n"
            f"  \"message_to_send\": {{\n"
            f"    \"recipient\": \"recipient_agent_name\",\n"
            f"    \"content\": \"message_content\"\n"
            f"  }},\n"
            f"  \"status\": \"continue\" | \"done\"\n"
            f"}}\n"
            f"Do not include any explanation or backticks outside the JSON. Return only the JSON object."
        )

        # Call LLM
        model = "llama3"
        try:
            raw_res = llm_generate(prompt=prompt, system=system_prompt, model=model)
            res = self._parse_json_response(raw_res)
        except Exception as e:
            logger.error(f"[AGENT {self.name}] LLM call or parse error: {e}")
            res = {"action": "none", "thought": f"Failed step: {e}", "status": "continue"}

        thought = res.get("thought", "")
        action = res.get("action", "none")
        self.status = res.get("status", "continue")

        logger.info(f"[AGENT {self.name}] Thought: {thought}")
        result_details = {"thought": thought, "action": action}

        if action == "call_tool":
            tool_name = res.get("tool_name")
            tool_args = res.get("tool_args", {})
            logger.info(f"[AGENT {self.name}] Calling tool {tool_name} with args {tool_args}")
            if tool_name:
                tool_res = call_tool(tool_name, **tool_args)
                logger.info(f"[AGENT {self.name}] Tool response: {str(tool_res)[:200]}")
                # Save tool response to blackboard for current visibility
                blackboard.write(
                    key=f"{self.name}_last_tool_output",
                    value=json.dumps(tool_res),
                    agent_name=self.name,
                    rationale=f"Result of running tool: {tool_name}"
                )
                result_details["tool_name"] = tool_name
                result_details["tool_result"] = tool_res
            else:
                result_details["error"] = "No tool_name provided for call_tool action"

        elif action == "update_memory":
            mem_up = res.get("memory_update", {})
            key = mem_up.get("key")
            val = mem_up.get("value")
            rationale = mem_up.get("rationale", "")
            if key and val:
                blackboard.write(key, val, self.name, rationale)
                result_details["memory_update"] = {"key": key, "rationale": rationale}
            else:
                result_details["error"] = "Invalid memory_update parameters"

        elif action == "send_message":
            msg_data = res.get("message_to_send", {})
            recipient = msg_data.get("recipient")
            content = msg_data.get("content")
            if recipient and content:
                message_bus.send_message(self.name, recipient, content)
                result_details["message"] = {"recipient": recipient}
            else:
                result_details["error"] = "Invalid message parameters"

        return result_details

    def _parse_json_response(self, text: str) -> dict:
        """Helper to extract and parse JSON from the LLM output."""
        text = text.strip()
        # Look for code block wrapper
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            # Look for outer curly braces
            match_braces = re.search(r"(\{.*\})", text, re.DOTALL)
            if match_braces:
                text = match_braces.group(1)
        try:
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Failed to parse JSON directly. Attempting regex cleaning: {e}")
            # Try cleaning comments or trailing commas
            cleaned = re.sub(r"//.*", "", text)
            try:
                return json.loads(cleaned)
            except:
                raise Exception(f"Unparseable LLM output: {text}")


class MissionDirector:
    """
    Mission Director: Manages team composition, collaborative execution phases,
    council vote checking, and final output writing.
    """
    def __init__(self, mission_id: str, goal: str):
        self.mission_id = mission_id
        self.goal = goal
        self.agents = []
        self.blackboard = SharedWorkingMemory()
        self.message_bus = MessageBus()
        self.decision_log = []

    def log_decision(self, decision_type: str, details: str, rationale: str):
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "mission_id": self.mission_id,
            "decision_type": decision_type,
            "details": details,
            "rationale": rationale
        }
        self.decision_log.append(log_entry)
        try:
            DECISION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            log_data = []
            if DECISION_LOG_FILE.exists():
                try:
                    log_data = json.loads(DECISION_LOG_FILE.read_text(encoding="utf-8"))
                except:
                    pass
            log_data.append(log_entry)
            DECISION_LOG_FILE.write_text(json.dumps(log_data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to log decision in director: {e}")

    def spawn_team(self) -> list:
        """
        Dynamically determine team composition using LLM based on user goal.
        """
        prompt = (
            f"Analyze the following goal: '{self.goal}'\n\n"
            f"Determine the optimal team of 3 to 6 specialized AI agents needed to achieve this goal.\n"
            f"Define a clear and helpful role description, budget (integer 5-15), and priority ('high', 'medium', or 'low') for each.\n\n"
            f"Return strictly a JSON object with this format:\n"
            f"{{\n"
            f"  \"agents\": [\n"
            f"    {{\n"
            f"      \"name\": \"Product Manager\",\n"
            f"      \"role\": \"PM\",\n"
            f"      \"description\": \"Responsible for research, feature breakdown, and documentation.\",\n"
            f"      \"budget\": 10,\n"
            f"      \"priority\": \"high\"\n"
            f"    }},\n"
            f"    ...\n"
            f"  ]\n"
            f"}}\n"
            f"Return only the JSON object, no introductory or concluding text."
        )

        system_prompt = "You are an AI engineering director. Break down goals into specialized agent roles."
        
        fallback_agents = [
            {"name": "Product Manager", "role": "PM", "description": "Focusses on research, task formulation, and compiling specifications.", "budget": 10, "priority": "high"},
            {"name": "Architect", "role": "Engineer", "description": "Responsible for structural layout, file paths, and coding standards.", "budget": 8, "priority": "high"},
            {"name": "Developer", "role": "Engineer", "description": "Responsible for writing and executing the core implementation and fixing code issues.", "budget": 12, "priority": "medium"},
            {"name": "Security Auditor", "role": "Analyst", "description": "Reviews the implementation and design for potential security loopholes or flaws.", "budget": 8, "priority": "low"},
            {"name": "QA Engineer", "role": "Analyst", "description": "Writes tests and validates the code for correctness.", "budget": 8, "priority": "low"}
        ]

        try:
            raw = llm_generate(prompt=prompt, system=system_prompt, model="llama3")
            # Parse JSON
            raw_clean = raw.strip()
            match = re.search(r"```json\s*(.*?)\s*```", raw_clean, re.DOTALL)
            if match:
                raw_clean = match.group(1)
            else:
                match_braces = re.search(r"(\{.*\})", raw_clean, re.DOTALL)
                if match_braces:
                    raw_clean = match_braces.group(1)
            
            parsed = json.loads(raw_clean)
            agent_configs = parsed.get("agents", [])
            if not agent_configs:
                agent_configs = fallback_agents
        except Exception as e:
            logger.warning(f"[DIRECTOR] Failed to dynamically spawn team: {e}. Using fallback team.")
            agent_configs = fallback_agents

        self.agents = []
        for cfg in agent_configs:
            agent = AgentInstance(
                name=cfg.get("name"),
                role=cfg.get("role"),
                role_description=cfg.get("description"),
                budget=cfg.get("budget", 10),
                priority=cfg.get("priority", "medium")
            )
            self.agents.append(agent)
            self.message_bus.register_agent(agent.name)

        names = [a.name for a in self.agents]
        self.log_decision(
            decision_type="team_spawning",
            details=f"Spawned {len(self.agents)} agents: {', '.join(names)}",
            rationale=f"Goal '{self.goal}' decomposed into a specialized multi-agent squad."
        )
        return self.agents

    def execute_rounds(self, max_rounds: int = 4) -> dict:
        """
        Runs collaborative development rounds. In each round, eligible agents run in priority order.
        """
        history = []
        round_count = 0

        while round_count < max_rounds:
            active_agents = [a for a in self.agents if a.status == "continue" and a.budget > 0]
            if not active_agents:
                logger.info("[DIRECTOR] All agents are 'done' or out of budget.")
                break

            round_count += 1
            logger.info(f"--- STARTING COLLABORATION ROUND {round_count}/{max_rounds} ---")
            
            # Sort active agents by priority: high first, then medium, then low
            priority_map = {"high": 0, "medium": 1, "low": 2}
            active_agents.sort(key=lambda a: priority_map.get(a.priority, 1))

            round_steps = []
            for agent in active_agents:
                logger.info(f"[DIRECTOR] Running step for Agent: {agent.name} ({agent.priority})")
                step_res = agent.execute_loop_step(self.blackboard, self.message_bus, self.goal)
                round_steps.append({
                    "agent": agent.name,
                    "result": step_res
                })
            
            history.append({
                "round": round_count,
                "steps": round_steps
            })

            # Check if any new messages are in the message bus or if they are idle
            # If all agents chose action="none" or "done" this round, we can fast-track
            all_done_or_none = True
            for step in round_steps:
                act = step["result"].get("action")
                if act not in ("none", "done") and step["result"].get("status") != "done":
                    all_done_or_none = False
                    break
            
            if all_done_or_none:
                logger.info("[DIRECTOR] Collaboration has stabilized (all agents returned none/done). Proceeding to vote.")
                break

        return {"rounds_executed": round_count, "history": history}

    def conduct_council_vote(self) -> dict:
        """
        Asks all agents to review the blackboard contents and vote on whether the output is satisfactory.
        """
        logger.info("[DIRECTOR] Starting Council Vote Phase...")
        blackboard_data = self.blackboard.get_all()
        blackboard_str = json.dumps(blackboard_data, indent=2) if blackboard_data else "(Blackboard is empty)"

        votes = {}
        approvals = 0
        rejections = 0

        for agent in self.agents:
            prompt = (
                f"You are the {agent.name} ({agent.role}) in the Council of Agents.\n"
                f"Review the shared blackboard content and vote on whether it successfully fulfills the mission goal: '{self.goal}'.\n\n"
                f"--- GOAL ---\n{self.goal}\n\n"
                f"--- BLACKBOARD CONTENT ---\n{blackboard_str}\n\n"
                f"Provide your feedback and vote strictly as a JSON object matching this schema:\n"
                f"{{\n"
                f"  \"vote\": \"approve\" | \"reject\",\n"
                f"  \"feedback\": \"Your detailed feedback on the work, highlighting what is missing or incorrect, or confirming why it is complete.\"\n"
                f"}}\n"
                f"Return only the JSON object."
            )

            system_prompt = f"You are voting as {agent.name} to confirm if the project goal is fully achieved."
            
            try:
                raw = llm_generate(prompt=prompt, system=system_prompt, model="llama3")
                raw_clean = raw.strip()
                match = re.search(r"```json\s*(.*?)\s*```", raw_clean, re.DOTALL)
                if match:
                    raw_clean = match.group(1)
                else:
                    match_braces = re.search(r"(\{.*\})", raw_clean, re.DOTALL)
                    if match_braces:
                        raw_clean = match_braces.group(1)
                
                parsed = json.loads(raw_clean)
                vote = parsed.get("vote", "reject").lower()
                feedback = parsed.get("feedback", "No feedback provided.")
            except Exception as e:
                logger.error(f"[COUNCIL] Agent {agent.name} failed to vote: {e}")
                vote = "reject"
                feedback = f"Failed to cast ballot: {e}"

            votes[agent.name] = {"vote": vote, "feedback": feedback}
            if vote == "approve":
                approvals += 1
            else:
                rejections += 1
            logger.info(f"[COUNCIL] Agent '{agent.name}' voted: {vote.upper()} | Feedback: {feedback[:100]}...")

        passed = approvals > rejections
        tally_str = f"Approvals: {approvals}, Rejections: {rejections}"
        
        self.log_decision(
            decision_type="council_vote",
            details=f"Council Vote result: {'PASSED' if passed else 'FAILED'} ({tally_str})",
            rationale=f"Agents peer-reviewed the blackboard content to confirm completion."
        )

        return {
            "passed": passed,
            "approvals": approvals,
            "rejections": rejections,
            "votes": votes
        }


class MultiAgentOrchestrator:
    """
    Top-level orchestrator that interfaces between the Mission state model
    and the Multi-Agent OS director.
    """
    @staticmethod
    def run_mission(mission_id: str, goal: str, saved_state: dict = None) -> dict:
        """
        Runs the full multi-agent flow: spawning, execution rounds, council vote,
        and saves findings/artifacts to disk.
        """
        logger.info(f"[MULTI-AGENT OS] Initiating mission '{goal}' (ID: {mission_id})")
        director = MissionDirector(mission_id, goal)
        
        # Load saved state if resuming
        if saved_state:
            director.blackboard.from_dict(saved_state.get("blackboard", {}))
            # Reconstruct agents
            for a_cfg in saved_state.get("agents", []):
                agent = AgentInstance(
                    name=a_cfg["name"],
                    role=a_cfg["role"],
                    role_description=a_cfg["role_description"],
                    budget=a_cfg["budget"],
                    priority=a_cfg["priority"]
                )
                agent.status = a_cfg["status"]
                director.agents.append(agent)
                director.message_bus.register_agent(agent.name)
        else:
            # Phase 1: Spawn
            director.spawn_team()

        # Phase 2: Collaborative rounds (up to 4 rounds per execution step)
        rounds_res = director.execute_rounds(max_rounds=4)

        # Phase 3: Council Vote
        vote_res = director.conduct_council_vote()

        # Compile final results
        blackboard_all = director.blackboard.get_all()
        
        # If vote did not pass, we don't automatically mark the mission completed.
        # But we still write current status and output.
        success = vote_res["passed"]
        
        # Let's save a detailed markdown report
        report_content = f"# Multi-Agent OS Execution Report: {goal}\n\n"
        report_content += f"**Mission ID:** {mission_id}  \n"
        report_content += f"**Timestamp:** {datetime.datetime.now().isoformat()}  \n"
        report_content += f"**Council Consensus Vote:** {'✅ PASSED' if success else '❌ REJECTED'}  \n"
        report_content += f"**Vote Tally:** Approvals={vote_res['approvals']}, Rejections={vote_res['rejections']}  \n\n"
        
        report_content += "## 👥 Spawned Specialized Team\n"
        for agent in director.agents:
            report_content += f"- **{agent.name}** ({agent.role}) — Priority: `{agent.priority}`, Budget Remaining: `{agent.budget}`  \n"
            report_content += f"  *Description:* {agent.role_description}\n\n"
            
        report_content += "## 🗳️ Council Ballots & Feedback\n"
        for name, ballot in vote_res["votes"].items():
            vote_icon = "✅ APPROVE" if ballot["vote"] == "approve" else "❌ REJECT"
            report_content += f"### {name}: {vote_icon}\n"
            report_content += f"{ballot['feedback']}\n\n"

        report_content += "## 🧠 Blackboard (Shared Working Memory) Contents\n"
        if blackboard_all:
            for k, v in blackboard_all.items():
                if k.endswith("_last_tool_output"):
                    continue # Skip raw tool outputs in report to avoid clutter
                report_content += f"### Key: `{k}`\n{v}\n\n"
        else:
            report_content += "*No blackboard content was written.*\n\n"

        report_content += "## 📜 Blackboard Write Audit Logs\n"
        report_content += "| Timestamp | Agent | Key | Rationale |\n"
        report_content += "| --- | --- | --- | --- |\n"
        for log in director.blackboard.get_audit_log():
            report_content += f"| {log['timestamp']} | {log['agent']} | `{log['key']}` | {log['rationale']} |\n"

        # Save report
        save_res = call_tool("save_report", title=f"multi_agent_{mission_id}", content=report_content)
        report_path = save_res.get("path", "")

        return {
            "success": success,
            "report_path": report_path,
            "vote": vote_res,
            "rounds": rounds_res,
            "state": {
                "blackboard": director.blackboard.to_dict(),
                "agents": [a.to_dict() for a in director.agents],
            }
        }

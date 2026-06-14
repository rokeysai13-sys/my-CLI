"""
core/mission.py — Autonomous Mission Control System
Manages persistent, stateful, multi-step agent missions with self-correction, decision logging, and execution state tracking.
"""
import json
import uuid
import datetime
from pathlib import Path
from core.logger import logger
from core.llm import llm_generate
from core.planner import decompose
from core.subagents import AGENT_MAP
from core.evaluator import SelfEvaluator

MISSIONS_FILE = Path(__file__).parent.parent / "memory" / "missions.json"
DECISION_LOG_FILE = Path(__file__).parent.parent / "memory" / "decision_log.json"

class Mission:
    def __init__(self, goal: str, mission_id: str = None, status: str = "pending", plan: dict = None, progress: dict = None, created_at: str = None, updated_at: str = None, mode: str = "standard"):
        self.mission_id = mission_id or str(uuid.uuid4())[:8]
        self.goal = goal
        self.status = status  # pending, running, completed, failed, paused
        self.mode = mode  # standard, multi_agent
        self.plan = plan or {}
        self.progress = progress or {
            "current_step": 0,
            "completed_tasks": [],
            "failures": [],
            "history": []
        }
        self.created_at = created_at or datetime.datetime.now().isoformat()
        self.updated_at = updated_at or datetime.datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "mission_id": self.mission_id,
            "goal": self.goal,
            "status": self.status,
            "mode": self.mode,
            "plan": self.plan,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class MissionManager:
    def __init__(self):
        self.missions = {}
        self.load_missions()

    def load_missions(self):
        """Load persistent missions from disk."""
        if MISSIONS_FILE.exists():
            try:
                data = json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))
                for m_id, m_data in data.items():
                    self.missions[m_id] = Mission(**m_data)
                logger.info(f"Loaded {len(self.missions)} missions.")
            except Exception as e:
                logger.error(f"Failed to load missions: {e}")

    def save_missions(self):
        """Persist missions to disk."""
        try:
            MISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {m_id: m.to_dict() for m_id, m in self.missions.items()}
            MISSIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save missions: {e}")

    def log_decision(self, mission_id: str, decision_type: str, details: str, rationale: str):
        """Log key architectural/tactical decisions made during execution."""
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "mission_id": mission_id,
            "decision_type": decision_type,
            "details": details,
            "rationale": rationale
        }
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
            logger.error(f"Failed to log decision: {e}")

    def create_mission(self, goal: str, mode: str = "standard") -> Mission:
        """Initialize a new persistent mission and auto-generate the subtask plan."""
        mission = Mission(goal=goal, mode=mode)
        self.missions[mission.mission_id] = mission
        self.log_decision(
            mission_id=mission.mission_id,
            decision_type="creation",
            details=f"Created mission: '{goal}' in {mode} mode",
            rationale="User initiated a long-term goal that requires autonomous planning and execution."
        )
        
        if mode == "multi_agent":
            # In multi-agent mode, the plan is generated dynamically during execution
            mission.plan = {"multi_agent": True, "sub_tasks": []}
            logger.info(f"[MISSION] Created mission in multi-agent mode.")
        else:
            # Decompose the goal into subtasks
            logger.info(f"[MISSION] Decomposing goal for mission {mission.mission_id}...")
            plan_res = decompose(goal)
            if plan_res.get("success"):
                mission.plan = plan_res.get("plan", {})
                logger.info(f"[MISSION] Generated subtask plan with {len(mission.plan.get('sub_tasks', []))} tasks.")
            else:
                mission.status = "failed"
                mission.plan = {"error": plan_res.get("error", "Planning failed")}
            
        mission.updated_at = datetime.datetime.now().isoformat()
        self.save_missions()
        return mission

    async def execute_mission_step(self, mission_id: str) -> dict:
        """Execute the next eligible step in the mission plan with self-correction."""
        mission = self.missions.get(mission_id)
        if not mission:
            return {"error": "Mission not found"}
        
        if mission.status in ("completed", "failed"):
            return {"status": mission.status, "message": "Mission is already finished."}
        
        mission.status = "running"
        mission.updated_at = datetime.datetime.now().isoformat()
        self.save_missions()

        if getattr(mission, "mode", "standard") == "multi_agent":
            from core.multi_agent import MultiAgentOrchestrator
            saved_state = mission.progress.get("multi_agent_state")
            import asyncio
            res = await asyncio.to_thread(
                MultiAgentOrchestrator.run_mission,
                mission.mission_id,
                mission.goal,
                saved_state
            )
            
            mission.progress["multi_agent_state"] = res.get("state", {})
            
            vote_passed = res.get("success", False)
            vote_tally = res.get("vote", {})
            history_entry = f"Multi-Agent round executed. Council vote: {'Passed' if vote_passed else 'Failed'}. Approvals: {vote_tally.get('approvals')}, Rejections: {vote_tally.get('rejections')}."
            mission.progress["history"].append(history_entry)
            
            if vote_passed:
                mission.status = "completed"
                self.log_decision(
                    mission_id=mission.mission_id,
                    decision_type="completion",
                    details=f"Mission goals achieved via multi-agent team consensus.",
                    rationale=f"Council vote passed and final reports saved to: {res.get('report_path')}"
                )
            else:
                # Check if budgets are exhausted
                all_exhausted = True
                for agent_state in res.get("state", {}).get("agents", []):
                    if agent_state.get("budget", 0) > 0 and agent_state.get("status") == "continue":
                        all_exhausted = False
                        break
                if all_exhausted:
                    mission.status = "failed"
                    mission.progress["failures"].append({"error": "All agent budgets exhausted without reaching consensus."})
                    self.log_decision(
                        mission_id=mission.mission_id,
                        decision_type="task_failure",
                        details="Agent budgets exhausted.",
                        rationale="Multi-agent collaboration failed to reach consensus before step budget limit."
                    )
                else:
                    mission.status = "running"
            
            mission.updated_at = datetime.datetime.now().isoformat()
            self.save_missions()
            return {
                "mission_id": mission_id,
                "status": mission.status,
                "success": vote_passed,
                "report_path": res.get("report_path"),
                "result": f"Multi-agent loop execution step complete. Vote: {'Passed' if vote_passed else 'Failed'}."
            }
        
        sub_tasks = mission.plan.get("sub_tasks", [])
        if not sub_tasks:
            mission.status = "failed"
            self.save_missions()
            return {"error": "No subtasks available in mission plan."}
        
        # Find next task that is not completed and dependencies are met
        completed_ids = {t["id"] for t in mission.progress["completed_tasks"]}
        next_task = None
        for t in sub_tasks:
            t_id = t["id"]
            if t_id not in completed_ids:
                deps = t.get("depends_on", [])
                if all(d in completed_ids for d in deps):
                    next_task = t
                    break
        
        if not next_task:
            # All tasks completed?
            if len(completed_ids) == len(sub_tasks):
                mission.status = "completed"
                self.log_decision(
                    mission_id=mission.mission_id,
                    decision_type="completion",
                    details=f"Mission goals achieved.",
                    rationale="All planned subtasks successfully completed and verified."
                )
                self.save_missions()
                return {"status": "completed", "message": "All tasks completed successfully."}
            else:
                mission.status = "paused"
                self.save_missions()
                return {"status": "paused", "message": "Execution paused due to dependency deadlock or blocked tasks."}
        
        task_id = next_task["id"]
        agent_type = next_task["agent"]
        task_desc = next_task["description"]
        
        logger.info(f"[MISSION {mission_id}] Executing subtask {task_id} [{agent_type}]: {next_task.get('title')}")
        agent_fn = AGENT_MAP.get(agent_type)
        if not agent_fn:
            # Fallback to researcher
            agent_fn = AGENT_MAP.get("researcher")
        
        # Assemble context from previously completed tasks
        context_parts = []
        for ct in mission.progress["completed_tasks"]:
            context_parts.append(f"Task {ct['id']} ({ct['agent']}) result: {ct.get('result')}")
        context = "\n".join(context_parts)
        
        evaluator = SelfEvaluator(threshold=6, max_retries=2)
        
        # Execution loop with self-correction
        retry_count = 0
        max_retries = 3
        task_success = False
        task_result = ""
        
        while retry_count < max_retries and not task_success:
            try:
                # Run the agent function
                import asyncio
                res = await asyncio.to_thread(agent_fn, task_desc, context[:1000])
                
                # Format text result for evaluation
                result_text = ""
                for key in ["findings", "analysis", "report", "response", "stdout", "result"]:
                    if key in res and res[key]:
                        result_text = str(res[key])
                        break
                if not result_text:
                    result_text = str(res)
                
                # Self-evaluation step
                eval_res = evaluator.evaluate(task_desc, result_text, agent_name=agent_type)
                
                if eval_res.get("pass", False):
                    task_success = True
                    task_result = result_text
                    self.log_decision(
                        mission_id=mission_id,
                        decision_type="task_execution",
                        details=f"Subtask {task_id} passed evaluation with score {eval_res.get('score')}.",
                        rationale=f"Self-evaluation verified completeness and accuracy of result."
                    )
                else:
                    retry_count += 1
                    logger.warning(f"[MISSION {mission_id}] Subtask {task_id} failed quality check (score: {eval_res.get('score')}). Retrying...")
                    context += f"\nPrevious attempt failed. Feedback: {eval_res.get('feedback')}. Please correct these mistakes."
            except Exception as e:
                retry_count += 1
                logger.error(f"[MISSION {mission_id}] Exception during subtask {task_id}: {e}")
        
        if task_success:
            completed_entry = {
                "id": task_id,
                "title": next_task.get("title"),
                "agent": agent_type,
                "result": task_result,
                "timestamp": datetime.datetime.now().isoformat()
            }
            mission.progress["completed_tasks"].append(completed_entry)
            mission.progress["history"].append(f"Task {task_id} completed successfully.")
        else:
            # Task failed after max retries
            logger.error(f"[MISSION {mission_id}] Subtask {task_id} failed after {max_retries} attempts.")
            mission.status = "failed"
            mission.progress["failures"].append({
                "id": task_id,
                "title": next_task.get("title"),
                "attempts": retry_count
            })
            mission.progress["history"].append(f"Task {task_id} failed.")
            self.log_decision(
                mission_id=mission_id,
                decision_type="task_failure",
                details=f"Subtask {task_id} execution aborted after {max_retries} failures.",
                rationale="Agent could not produce satisfactory results within retry limits."
            )
            
        mission.updated_at = datetime.datetime.now().isoformat()
        self.save_missions()
        
        return {
            "mission_id": mission_id,
            "status": mission.status,
            "task_id": task_id,
            "success": task_success,
            "result": task_result if task_success else "Execution failed."
        }

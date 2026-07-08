"""
Repair Planner Agent: Generates detailed repair strategies and sequences.

Responsibilities:
- Create repair sequence
- Identify required tools
- Identify required parts
- Calculate difficulty level
- Estimate time required
"""

from typing import List, Dict, Any, Optional
from .base_agent import BaseAgent, AgentResult, RepairQuery


class RepairPlannerAgent(BaseAgent):
    """Generates comprehensive repair plans with sequences, tools, and parts."""
    
    def __init__(self):
        super().__init__("RepairPlannerAgent")
        self.tool_database: Dict[str, List[str]] = {}
        self.difficulty_scale = ["trivial", "easy", "moderate", "hard", "expert"]
    
    def initialize(self) -> None:
        """Load repair templates and tool database."""
        self.tool_database = {
            "electrical": ["multimeter", "wire_stripper", "insulation_tape", "soldering_iron"],
            "mechanical": ["wrench", "screwdriver", "pliers", "socket_set", "hammer"],
            "hydraulic": ["pressure_gauge", "hydraulic_jack", "hose_clamp", "pump"],
            "thermal": ["thermometer", "lubricant", "heating_element", "thermal_paste"],
        }
    
    def process(self, query: RepairQuery) -> None:
        """Generate detailed repair plan."""
        root_causes = query.context.get("root_causes", [])
        matched_repairs = query.context.get("matched_repairs", [])
        failure_types = query.context.get("failure_types", [])
        # If matched repairs include diagnostic questions, include testing steps
        testing_sequence = []
        for rep in matched_repairs:
            dq = rep.get("diagnostic_questions") or []
            for q in dq:
                testing_sequence.append({"question": q.get("question"), "possible_answers": q.get("possible_answers", []), "source_repair_id": rep.get("id")})
        
        # Generate repair sequence
        repair_steps = self._generate_repair_sequence(
            root_causes, matched_repairs, failure_types
        )
        
        # Identify required tools
        required_tools = self._identify_tools(failure_types)
        
        # Identify required parts
        required_parts = self._identify_parts(root_causes, matched_repairs)
        
        # Calculate difficulty
        difficulty = self._calculate_difficulty(repair_steps, required_tools)
        
        # Estimate time
        estimated_time_minutes = self._estimate_time(len(repair_steps), difficulty)
        
        self._last_result = AgentResult(
            agent_name=self.agent_name,
            status="success" if repair_steps else "partial",
            confidence=0.75 if repair_steps else 0.3,
            data={
                "repair_plan": {
                    "title": "Repair Plan",
                    "steps": repair_steps,
                    "difficulty": difficulty,
                    "estimated_time_minutes": estimated_time_minutes,
                },
                "tools": required_tools,
                "parts": required_parts,
                "steps": repair_steps,
                "testing_sequence": testing_sequence,
            }
        )
    
    def validate(self) -> bool:
        """Check repair plan quality."""
        if not self._last_result:
            return False
        
        data = self._last_result.data
        
        # Must have repair steps
        if not data.get("steps"):
            return False
        
        # Difficulty must be valid
        if data.get("repair_plan", {}).get("difficulty") not in self.difficulty_scale:
            return False
        
        # Time estimate must be reasonable
        time_est = data.get("repair_plan", {}).get("estimated_time_minutes", 0)
        if time_est < 5 or time_est > 1440:  # 5 minutes to 24 hours
            return False
        
        return True
    
    def return_result(self) -> AgentResult:
        """Return repair plan."""
        return self._last_result or AgentResult(
            agent_name=self.agent_name,
            status="failed",
            confidence=0.0,
        )
    
    def _generate_repair_sequence(
        self,
        root_causes: List[Dict[str, Any]],
        matched_repairs: List[Dict[str, Any]],
        failure_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate ordered repair steps."""
        steps = []
        
        # Safety check first
        steps.append({
            "order": 1,
            "step": "Ensure safety precautions",
            "description": "Disconnect power, wear safety equipment",
            "time_minutes": 5,
        })
        
        # Diagnosis step
        steps.append({
            "order": 2,
            "step": "Verify problem",
            "description": f"Confirm root cause: {root_causes[0].get('cause', 'unknown') if root_causes else 'problem'}",
            "time_minutes": 10,
        })
        
        # Main repair steps
        if matched_repairs:
            for i, repair in enumerate(matched_repairs[:3], start=3):
                steps.append({
                    "order": i,
                    "step": f"Repair step {i - 2}",
                    "description": repair.get("repair", ""),
                    "time_minutes": 15,
                })
        
        # Verification step
        steps.append({
            "order": len(steps) + 1,
            "step": "Verify repair",
            "description": "Test functionality and check for issues",
            "time_minutes": 10,
        })
        
        return steps
    
    def _identify_tools(self, failure_types: List[str]) -> List[Dict[str, str]]:
        """Identify required tools based on failure types."""
        tools = set()
        
        for failure_type in failure_types:
            type_lower = failure_type.lower()
            for category, tool_list in self.tool_database.items():
                if category in type_lower or type_lower in category:
                    tools.update(tool_list)
        
        # Ensure basic tools
        if not tools:
            tools.add("flashlight")
            tools.add("basic_wrench_set")
        
        return [{"tool": tool, "category": "general"} for tool in sorted(tools)]
    
    def _identify_parts(
        self,
        root_causes: List[Dict[str, Any]],
        matched_repairs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify parts that may need replacement."""
        parts = []
        
        for cause in root_causes[:2]:
            cause_name = cause.get("cause", "").replace("_", " ")
            parts.append({
                "part": cause_name,
                "type": "suspected",
                "availability": "check",
            })
        
        # Add common replacement parts
        parts.extend([
            {"part": "seals/gaskets", "type": "common", "availability": "stock"},
            {"part": "belts", "type": "common", "availability": "stock"},
        ])
        
        return parts[:5]
    
    def _calculate_difficulty(
        self,
        repair_steps: List[Dict[str, Any]],
        required_tools: List[Dict[str, str]]
    ) -> str:
        """Calculate repair difficulty."""
        num_steps = len(repair_steps)
        num_tools = len(required_tools)
        
        if num_steps <= 2:
            return "trivial"
        elif num_steps <= 3 and num_tools <= 2:
            return "easy"
        elif num_steps <= 5 and num_tools <= 4:
            return "moderate"
        elif num_steps <= 8:
            return "hard"
        else:
            return "expert"
    
    def _estimate_time(self, num_steps: int, difficulty: str) -> int:
        """Estimate repair time in minutes."""
        base_time = num_steps * 10
        
        difficulty_multipliers = {
            "trivial": 0.5,
            "easy": 1.0,
            "moderate": 1.5,
            "hard": 2.0,
            "expert": 3.0,
        }
        
        multiplier = difficulty_multipliers.get(difficulty, 1.5)
        return max(15, int(base_time * multiplier))

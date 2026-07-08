"""
Central Orchestrator: Coordinates all agents in the FixFinder multi-agent system.

The Orchestrator controls the complete reasoning pipeline:
1. Accept user query
2. Run RQU (Query Understanding)
3. Route through specialized agents
4. Aggregate results
5. Calculate confidence
6. Format response
7. Record learning event

No agent directly calls another agent.
All communication uses structured JSON.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid

from backend.agents import (
    RepairQuery,
    AgentResult,
    DiagnosticAgent,
    RetrievalAgent,
    GraphAgent,
    RepairPlannerAgent,
    SafetyValidationAgent,
    VerificationAgent,
    SimulationAgent,
    LearningAgent,
    ConversationAgent,
)


@dataclass
class OrchestrationContext:
    """Tracks state throughout orchestration pipeline."""
    session_id: str
    user_query: str
    equipment_type: str = ""
    symptoms: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Agent results
    diagnostic_result: Optional[AgentResult] = None
    retrieval_result: Optional[AgentResult] = None
    graph_result: Optional[AgentResult] = None
    repair_result: Optional[AgentResult] = None
    safety_result: Optional[AgentResult] = None
    verification_result: Optional[AgentResult] = None
    simulation_result: Optional[AgentResult] = None
    conversation_result: Optional[AgentResult] = None
    
    # Orchestration state
    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    pipeline_stage: str = "initialized"
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "session_id": self.session_id,
            "user_query": self.user_query,
            "equipment_type": self.equipment_type,
            "symptoms": self.symptoms,
            "context": self.context,
            "diagnostic_result": self.diagnostic_result.to_dict() if self.diagnostic_result else None,
            "retrieval_result": self.retrieval_result.to_dict() if self.retrieval_result else None,
            "graph_result": self.graph_result.to_dict() if self.graph_result else None,
            "repair_result": self.repair_result.to_dict() if self.repair_result else None,
            "safety_result": self.safety_result.to_dict() if self.safety_result else None,
            "verification_result": self.verification_result.to_dict() if self.verification_result else None,
            "simulation_result": self.simulation_result.to_dict() if self.simulation_result else None,
            "conversation_result": self.conversation_result.to_dict() if self.conversation_result else None,
            "start_time": self.start_time,
            "pipeline_stage": self.pipeline_stage,
            "confidence_scores": self.confidence_scores,
        }


class Orchestrator:
    """
    Central coordinator for multi-agent repair diagnosis pipeline.
    
    Pipeline Flow:
    1. Diagnostic Agent → Analyze symptoms, identify problems
    2. Retrieval Agent → Find matching repairs in knowledge base
    3. Graph Agent → Analyze causal relationships
    4. Repair Planner → Generate repair sequence
    5. Safety Agent → Validate safety compliance
    6. Verification Agent → Create testing procedure
    7. Simulation Agent → Generate visualization
    8. Conversation Agent → Format response
    9. Learning Agent → Record outcome
    """
    
    def __init__(self):
        """Initialize orchestrator with all agents."""
        self.diagnostic_agent = DiagnosticAgent()
        self.retrieval_agent = RetrievalAgent()
        self.graph_agent = GraphAgent()
        self.repair_agent = RepairPlannerAgent()
        # diagnostic lookup helper to attach question trees to matched repairs
        try:
            from backend.knowledge_factory.diagnostic_lookup import DiagnosticLookup
            self._diag_lookup = DiagnosticLookup()
        except Exception:
            self._diag_lookup = None
        self.safety_agent = SafetyValidationAgent()
        self.verification_agent = VerificationAgent()
        self.simulation_agent = SimulationAgent()
        self.learning_agent = LearningAgent()
        self.conversation_agent = ConversationAgent()
        
        self.session_contexts: Dict[str, OrchestrationContext] = {}
    
    def process(
        self,
        user_query: str,
        equipment_type: str = "",
        symptoms: List[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process user query through complete orchestration pipeline.
        
        Args:
            user_query: Natural language user input
            equipment_type: Type of equipment being repaired
            symptoms: List of symptoms
            session_id: Optional session identifier (generated if not provided)
            
        Returns:
            Complete orchestration result with all agent outputs
        """
        # Setup
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        if symptoms is None:
            symptoms = []
        
        # Create orchestration context
        context = OrchestrationContext(
            session_id=session_id,
            user_query=user_query,
            equipment_type=equipment_type,
            symptoms=symptoms,
        )
        
        self.session_contexts[session_id] = context
        
        # Execute pipeline
        try:
            self._stage_diagnostic(context)
            self._stage_retrieval(context)
            self._stage_graph_reasoning(context)
            self._stage_repair_planning(context)
            self._stage_safety_validation(context)
            self._stage_verification(context)
            self._stage_simulation(context)
            self._stage_conversation(context)
            self._stage_learning(context)
            
            context.pipeline_stage = "completed"
        
        except Exception as e:
            context.pipeline_stage = "failed"
            context.context["error"] = str(e)
        
        return self._format_response(context)
    
    def _stage_diagnostic(self, context: OrchestrationContext) -> None:
        """Stage 1: Diagnostic analysis."""
        context.pipeline_stage = "diagnostic"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            symptoms=context.symptoms,
            user_query=context.user_query,
        )
        
        result = self.diagnostic_agent.execute(query)
        context.diagnostic_result = result
        context.confidence_scores["diagnostic"] = result.confidence
        
        # Pass diagnostic data to context
        context.context.update(result.data)
    
    def _stage_retrieval(self, context: OrchestrationContext) -> None:
        """Stage 2: Knowledge retrieval."""
        context.pipeline_stage = "retrieval"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            symptoms=context.symptoms,
            user_query=context.user_query,
            context=context.context,
        )
        
        result = self.retrieval_agent.execute(query)
        context.retrieval_result = result
        context.confidence_scores["retrieval"] = result.confidence
        
        # Pass retrieval data to context
        context.context["matched_repairs"] = result.data.get("matched_repairs", [])
        # attach diagnostic question trees to matched repairs when available
        if self._diag_lookup and context.context.get("matched_repairs"):
            for rep in context.context["matched_repairs"]:
                rep_id = rep.get("id")
                if rep_id:
                    rep["diagnostic_questions"] = self._diag_lookup.get_questions_for_repair(rep_id)
    
    def _stage_graph_reasoning(self, context: OrchestrationContext) -> None:
        """Stage 3: Graph-based reasoning."""
        context.pipeline_stage = "graph_reasoning"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            symptoms=context.symptoms,
            context=context.context,
        )
        
        result = self.graph_agent.execute(query)
        context.graph_result = result
        context.confidence_scores["graph"] = result.confidence
        
        # Pass graph data to context
        context.context["root_causes"] = result.data.get("root_causes", [])
        context.context["failure_types"] = result.data.get("failure_chain", [])
    
    def _stage_repair_planning(self, context: OrchestrationContext) -> None:
        """Stage 4: Repair plan generation."""
        context.pipeline_stage = "repair_planning"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            context=context.context,
        )
        
        result = self.repair_agent.execute(query)
        context.repair_result = result
        context.confidence_scores["repair"] = result.confidence
        
        # Pass repair plan to context
        context.context["repair_plan"] = result.data.get("repair_plan", {})
        context.context["tools"] = result.data.get("tools", [])
    
    def _stage_safety_validation(self, context: OrchestrationContext) -> None:
        """Stage 5: Safety validation."""
        context.pipeline_stage = "safety_validation"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            context=context.context,
        )
        
        result = self.safety_agent.execute(query)
        context.safety_result = result
        context.confidence_scores["safety"] = result.confidence
        
        # Pass safety data to context
        context.context["safe"] = result.data.get("safe", False)
        context.context["requires_professional"] = result.data.get("requires_professional", False)
    
    def _stage_verification(self, context: OrchestrationContext) -> None:
        """Stage 6: Verification procedure generation."""
        context.pipeline_stage = "verification"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            context=context.context,
        )
        
        result = self.verification_agent.execute(query)
        context.verification_result = result
        
        # Pass verification data to context
        context.context["verification_steps"] = result.data.get("verification_steps", [])
    
    def _stage_simulation(self, context: OrchestrationContext) -> None:
        """Stage 7: Simulation and visualization."""
        context.pipeline_stage = "simulation"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            context=context.context,
        )
        
        result = self.simulation_agent.execute(query)
        context.simulation_result = result
        
        # Pass simulation data to context
        context.context["simulation"] = {
            "type": result.data.get("simulation_type", ""),
            "steps": result.data.get("animation_steps", []),
        }
    
    def _stage_conversation(self, context: OrchestrationContext) -> None:
        """Stage 8: Conversation formatting."""
        context.pipeline_stage = "conversation"
        
        # Calculate overall confidence
        overall_confidence = self._calculate_overall_confidence(context)
        context.context["overall_confidence"] = overall_confidence
        context.context["diagnostic_confidence"] = context.confidence_scores.get("diagnostic", 0.0)
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            symptoms=context.symptoms,
            context=context.context,
        )
        
        result = self.conversation_agent.execute(query)
        context.conversation_result = result
    
    def _stage_learning(self, context: OrchestrationContext) -> None:
        """Stage 9: Learning event recording."""
        context.pipeline_stage = "learning"
        
        query = RepairQuery(
            session_id=context.session_id,
            equipment_type=context.equipment_type,
            context=context.context,
        )
        
        result = self.learning_agent.execute(query)
    
    def _calculate_overall_confidence(self, context: OrchestrationContext) -> float:
        """Calculate weighted overall confidence."""
        scores = context.confidence_scores
        
        if not scores:
            return 0.0
        
        # Weight each agent's confidence
        weights = {
            "diagnostic": 0.3,
            "retrieval": 0.2,
            "graph": 0.2,
            "repair": 0.15,
            "safety": 0.15,
        }
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for agent, score in scores.items():
            weight = weights.get(agent, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return weighted_sum / total_weight
    
    def _format_response(self, context: OrchestrationContext) -> Dict[str, Any]:
        """Format final orchestration response."""
        return {
            "session_id": context.session_id,
            "status": context.pipeline_stage,
            "timestamp": datetime.utcnow().isoformat(),
            "overall_confidence": context.context.get("overall_confidence", 0.0),
            
            # Main response
            "diagnosis": {
                "problem": context.diagnostic_result.data.get("identified_problem") if context.diagnostic_result else "",
                "confidence": context.confidence_scores.get("diagnostic", 0.0),
                "alternatives": context.diagnostic_result.data.get("possible_failures", []) if context.diagnostic_result else [],
            },
            
            # Repair plan
            "repair_plan": context.context.get("repair_plan", {}),
            "tools": context.context.get("tools", []),
            
            # Safety
            "safety": {
                "safe": context.context.get("safe", False),
                "requires_professional": context.context.get("requires_professional", False),
                "warnings": context.safety_result.data.get("warnings", []) if context.safety_result else [],
            },
            
            # Verification
            "verification_steps": context.context.get("verification_steps", []),
            
            # Visualization
            "simulation": context.context.get("simulation", {}),
            
            # User response
            "message": context.conversation_result.data.get("message", "") if context.conversation_result else "",
            "clarification_questions": context.conversation_result.data.get("clarification_questions", []) if context.conversation_result else [],
            
            # Full context for debugging/analysis
            "context": context.to_dict(),
        }

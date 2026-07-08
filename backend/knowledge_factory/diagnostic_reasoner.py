from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List


class DiagnosticReasoner:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir or Path(__file__).resolve().parent / "diagnostics")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.output_dir / "diagnostic_trees.sqlite3"
        self.graph_path = self.output_dir / "diagnostic_graph.json"

    def _make_question_sequence(self, problem: str) -> List[Dict[str, Any]]:
        base = problem.lower() if problem else ""

        # Common diagnostic tree nodes for any equipment
        qseq: List[Dict[str, Any]] = [
            {
                "id": "engine_crank_check",
                "question": "Does the engine crank when you turn the key or press start?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "power_distribution_check",
                "next_if_no": "starter_circuit_check",
            },
            {
                "id": "power_distribution_check",
                "question": "Are dash lights, gauges, and electronics functioning normally?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "fuel_system_check",
                "next_if_no": "battery_health_check",
            },
            {
                "id": "battery_health_check",
                "question": "Is the battery voltage within the acceptable range?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "alternator_check",
                "next_if_no": "charge_or_replace_battery",
            },
            {
                "id": "alternator_check",
                "question": "Does the alternator charge correctly while the engine is running?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "starter_circuit_check",
                "next_if_no": "inspect_alternator_and_belt",
            },
            {
                "id": "starter_circuit_check",
                "question": "Does the starter motor engage when starting?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "fuel_system_check",
                "next_if_no": "inspect_starter_and_solenoid",
            },
            {
                "id": "fuel_system_check",
                "question": "Is fuel reaching the engine or combustion chamber?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "ignition_check",
                "next_if_no": "inspect_fuel_pump_filter_and_lines",
            },
            {
                "id": "ignition_check",
                "question": "Is ignition occurring properly (spark, flame, or glow plug operation)?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "air_intake_check",
                "next_if_no": "inspect_ignition_system",
            },
            {
                "id": "air_intake_check",
                "question": "Is air intake and filter condition normal?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "compression_check",
                "next_if_no": "clean_or_replace_air_filter",
            },
            {
                "id": "compression_check",
                "question": "Is engine or compression system pressure within specifications?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "diagnosis_resolved",
                "next_if_no": "inspect_compression_components",
            },
        ]

        # Problem-specific subtrees and variations
        if "won't start" in base or "no start" in base or "does not start" in base:
            qseq.extend([
                {
                    "id": "starter_sound_check",
                    "question": "Do you hear clicking, grinding, or silence when trying to start?",
                    "possible_answers": ["clicking", "grinding", "silence", "other"],
                    "next_if_yes": "starter_circuit_check",
                    "next_if_no": "battery_health_check",
                },
                {
                    "id": "fuel_pressure_check",
                    "question": "Does the fuel system build pressure when the ignition is on?",
                    "possible_answers": ["yes", "no", "not sure"],
                    "next_if_yes": "ignition_check",
                    "next_if_no": "inspect_fuel_pump_and_filter",
                },
                {
                    "id": "spark_plug_check",
                    "question": "Are the spark plugs or glow plugs in good condition?",
                    "possible_answers": ["yes", "no", "unknown"],
                    "next_if_yes": "compression_check",
                    "next_if_no": "service_ignition_components",
                },
            ])

        if "overheat" in base or "hot" in base or "temperature" in base:
            qseq.insert(0, {
                "id": "cooling_system_check",
                "question": "Is the cooling system operating and is coolant level correct?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "power_distribution_check",
                "next_if_no": "inspect_cooling_system",
            })
            qseq.extend([
                {
                    "id": "thermostat_check",
                    "question": "Does the thermostat open/close correctly?",
                    "possible_answers": ["yes", "no", "not sure"],
                    "next_if_yes": "radiator_check",
                    "next_if_no": "replace_thermostat",
                },
                {
                    "id": "radiator_check",
                    "question": "Is the radiator and fan working normally?",
                    "possible_answers": ["yes", "no"],
                    "next_if_yes": "coolant_flow_check",
                    "next_if_no": "inspect_radiator_and_fan",
                },
                {
                    "id": "coolant_flow_check",
                    "question": "Is coolant flowing freely through the system?",
                    "possible_answers": ["yes", "no"],
                    "next_if_yes": "diagnosis_resolved",
                    "next_if_no": "check_water_pump_and_hoses",
                },
            ])

        if "leak" in base or "leaking" in base or "drip" in base or "spill" in base:
            qseq.insert(0, {
                "id": "leak_confirmation_check",
                "question": "Is there visible fluid pooling or dripping from the system?",
                "possible_answers": ["yes", "no"],
                "next_if_yes": "inspect_seals_and_connections",
                "next_if_no": "check_internal_leak_paths",
            })
            qseq.extend([
                {
                    "id": "seal_condition_check",
                    "question": "Are seals, gaskets, and hoses intact and tight?",
                    "possible_answers": ["yes", "no"],
                    "next_if_yes": "pressure_test_check",
                    "next_if_no": "replace_damaged_seals_or_hoses",
                },
                {
                    "id": "pressure_test_check",
                    "question": "Does the system hold pressure during a leak test?",
                    "possible_answers": ["yes", "no", "not sure"],
                    "next_if_yes": "diagnosis_resolved",
                    "next_if_no": "locate_and_repair_leak",
                },
            ])

        return qseq

    def _rank_causes(self, problem: str) -> List[Dict[str, Any]]:
        base = problem.lower() if problem else ""
        candidates: List[Dict[str, Any]] = []

        if "won't start" in base or "no start" in base or "does not start" in base:
            candidates = [
                {"cause": "dead_battery", "score": 0.28, "type": "electrical", "evidence": "common no-start failure"},
                {"cause": "starter_motor_fault", "score": 0.22, "type": "electrical", "evidence": "starter circuit symptoms"},
                {"cause": "fuel_delivery_issue", "score": 0.18, "type": "fuel", "evidence": "fuel pressure or pump problem"},
                {"cause": "ignition_system_failure", "score": 0.14, "type": "ignition", "evidence": "spark or ignition fault"},
                {"cause": "compression_loss", "score": 0.10, "type": "mechanical", "evidence": "engine compression deficiency"},
                {"cause": "sensor_failure", "score": 0.08, "type": "electrical", "evidence": "engine control sensor issue"},
            ]
        elif "overheat" in base or "hot" in base or "temperature" in base:
            candidates = [
                {"cause": "coolant_leak", "score": 0.30, "type": "cooling", "evidence": "overheating and fluid loss"},
                {"cause": "thermostat_stuck", "score": 0.25, "type": "cooling", "evidence": "temperature regulation issue"},
                {"cause": "radiator_blockage", "score": 0.20, "type": "cooling", "evidence": "cooling flow restriction"},
                {"cause": "water_pump_failure", "score": 0.15, "type": "cooling", "evidence": "poor coolant circulation"},
                {"cause": "electrical_fan_failure", "score": 0.10, "type": "electrical", "evidence": "fan or control fault"},
            ]
        elif "leak" in base or "leaking" in base or "drip" in base or "spill" in base:
            candidates = [
                {"cause": "seal_or_gasket_failure", "score": 0.34, "type": "mechanical", "evidence": "common fluid leak source"},
                {"cause": "loose_connection", "score": 0.24, "type": "mechanical", "evidence": "fittings and hose failure"},
                {"cause": "cracked_component", "score": 0.18, "type": "structural", "evidence": "physical damage"},
                {"cause": "pressure_overload", "score": 0.14, "type": "hydraulic", "evidence": "system overpressure"},
                {"cause": "corrosion", "score": 0.10, "type": "environmental", "evidence": "wear from contaminants"},
            ]
        else:
            candidates = [
                {"cause": "wear_and_tear", "score": 0.32, "type": "mechanical", "evidence": "aging components"},
                {"cause": "poor_maintenance", "score": 0.24, "type": "operational", "evidence": "lack of routine service"},
                {"cause": "electrical_fault", "score": 0.20, "type": "electrical", "evidence": "wiring or control issue"},
                {"cause": "environmental_exposure", "score": 0.14, "type": "environmental", "evidence": "corrosion, moisture, or debris"},
                {"cause": "software_or_sensor_issue", "score": 0.10, "type": "electronic", "evidence": "sensor or ECU anomaly"},
            ]

        # Normalize scores so they sum to 1.0
        total = sum(item["score"] for item in candidates) or 1.0
        for item in candidates:
            item["score"] = round(item["score"] / total, 4)

        return candidates

    def generate_for_objects(self, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        graph_nodes: List[Dict[str, Any]] = []
        graph_edges: List[Dict[str, Any]] = []

        for obj in objects:
            repair_id = obj.get("id") or str(uuid.uuid4())
            problem = obj.get("metadata", {}).get("problem") or obj.get("description") or obj.get("title")

            qseq = self._make_question_sequence(problem)
            causes = self._rank_causes(problem)

            # persist each question as a tree row
            for node in qseq:
                tree_id = str(uuid.uuid4())
                question = node.get("question")
                possible = json.dumps(node.get("possible_answers", []))
                # next_action is a structured JSON for clarity
                next_action = json.dumps({k: v for k, v in node.items() if k.startswith("next_")})
                rows.append({"tree_id": tree_id, "repair_id": repair_id, "question": question, "possible_answers": possible, "next_action": next_action})

                # graph node/edge
                graph_nodes.append({"id": tree_id, "label": question, "type": "diagnostic_question"})
                graph_edges.append({"from": repair_id, "to": tree_id, "type": "has_diagnostic_question"})

            # cause nodes
            for c in causes:
                cid = str(uuid.uuid4())
                graph_nodes.append({"id": cid, "label": c["cause"], "type": "cause", "score": c["score"]})
                graph_edges.append({"from": repair_id, "to": cid, "type": "possible_cause", "score": c["score"]})

        # write sqlite
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS diagnostic_tree (
                tree_id TEXT PRIMARY KEY,
                repair_id TEXT,
                question TEXT,
                possible_answers TEXT,
                next_action TEXT
            )
            """
        )
        for r in rows:
            cur.execute(
                "INSERT OR REPLACE INTO diagnostic_tree (tree_id,repair_id,question,possible_answers,next_action) VALUES (?,?,?,?,?)",
                (r["tree_id"], r["repair_id"], r["question"], r["possible_answers"], r["next_action"]),
            )
        conn.commit()
        conn.close()

        # write graph
        graph_payload = {"nodes": graph_nodes, "edges": graph_edges}
        self.graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")

        return {"summary": {"total_trees": len(rows)}, "path": str(self.db_path), "graph": str(self.graph_path)}

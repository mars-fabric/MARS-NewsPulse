"""NewsPulse Final Report Phase.

Uses a LangGraph pipeline to generate the 12-section executive report + PDF.
Each section is generated via an independent, bounded LLM call so the
context never exceeds model limits — unlike the old
planning_and_control_context_carryover approach which accumulated 2.5M+ tokens.

Mirrors the pattern of DeepresearchPaperPhase (cmbagent/task_framework/phases/paper.py).
"""

import os
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cmbagent.phases.base import Phase, PhaseConfig, PhaseContext, PhaseResult
from cmbagent.phases.registry import PhaseRegistry
from cmbagent.phases.execution_manager import PhaseExecutionManager

logger = logging.getLogger(__name__)


@dataclass
class NewsPulseReportPhaseConfig(PhaseConfig):
    """Configuration for NewsPulse report generation phase."""
    phase_type: str = "newspulse_report"

    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7

    parent_run_id: str = ""
    stage_name: str = "final_report"


@PhaseRegistry.register("newspulse_report")
class NewsPulseReportPhase(Phase):
    """Generate NewsPulse final report using LangGraph pipeline.

    The graph generates each report section independently with bounded
    context, then assembles them into the final markdown and PDF.
    """

    config_class = NewsPulseReportPhaseConfig

    def __init__(self, config: NewsPulseReportPhaseConfig = None):
        if config is None:
            config = NewsPulseReportPhaseConfig()
        super().__init__(config)
        self.config: NewsPulseReportPhaseConfig = config

    @property
    def phase_type(self) -> str:
        return "newspulse_report"

    @property
    def display_name(self) -> str:
        return "NewsPulse Final Report"

    def get_required_agents(self) -> List[str]:
        return []  # LangGraph manages its own nodes

    async def execute(self, context: PhaseContext) -> PhaseResult:
        from task_framework.newspulse_agents.report_graph import build_newspulse_report_graph

        manager = PhaseExecutionManager(context, self)
        manager.start()

        try:
            work_dir = str(context.work_dir)
            shared = context.shared_state or {}

            # Build graph
            graph = build_newspulse_report_graph(mermaid_diagram=False)

            # LangGraph config (needs thread_id for checkpointer)
            config = {
                "configurable": {"thread_id": "1"},
                "recursion_limit": 50,
            }

            # Build input state
            input_state = {
                "industry": shared.get("industry", ""),
                "companies": shared.get("companies", ""),
                "region": shared.get("region", "Global"),
                "time_window": shared.get("time_window", "7d"),
                "news_collection": shared.get("news_collection", ""),
                "deep_analysis": shared.get("deep_analysis", ""),
                "llm_model": self.config.llm_model,
                "llm_temperature": self.config.llm_temperature,
                "work_dir": work_dir,
            }

            manager.start_step(1, "Generating report sections via LangGraph")

            # Run the graph — all nodes are synchronous so invoke() is fine
            final_state = await graph.ainvoke(input_state, config)

            manager.complete_step(1, "Report sections generated")

            # Extract results
            final_report = final_state.get("final_report", "")
            pdf_path = final_state.get("pdf_path", "")

            # Build output data
            artifacts = {}
            final_report_path = os.path.join(work_dir, "input_files", "final_report.md")
            if os.path.exists(final_report_path):
                artifacts["final_report.md"] = final_report_path
            if pdf_path and os.path.exists(pdf_path):
                artifacts["report.pdf"] = pdf_path

            output_data = {
                "shared": {
                    **shared,
                    "final_report": final_report,
                },
                "artifacts": artifacts,
                "chat_history": [],
            }

            return manager.complete(output_data=output_data)

        except Exception as e:
            logger.error("NewsPulse report phase failed: %s", e, exc_info=True)
            return manager.fail(
                error=str(e),
                traceback_str=traceback.format_exc(),
            )

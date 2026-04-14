"""
LangGraph definition for the NewsPulse final report pipeline.

Graph flow:
  START
    ↓
  preprocess_node  (read inputs, create bounded summaries)
    ↓
  executive_summary_node
    ↓
  sentiment_dashboard_node
    ↓
  headlines_node
    ↓
  in_depth_analysis_node
    ↓
  company_analysis_node
    ↓
  trends_risks_node
    ↓
  regional_outlook_node
    ↓
  sources_node  (compile references from all sections)
    ↓
  assemble_node  (combine into final markdown)
    ↓
  pdf_node  (markdown → PDF)
    ↓
  END

Each section node makes an independent LLM call with bounded context,
avoiding the context-length explosion seen in the old
planning_and_control_context_carryover approach.
"""

from langgraph.graph import START, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .parameters import NewsPulseReportState
from .report_nodes import (
    preprocess_node,
    executive_summary_node,
    sentiment_dashboard_node,
    headlines_node,
    in_depth_analysis_node,
    company_analysis_node,
    trends_risks_node,
    regional_outlook_node,
    sources_node,
    assemble_node,
    pdf_node,
)


def build_newspulse_report_graph(mermaid_diagram: bool = False):
    """Build and compile the NewsPulse report LangGraph.

    Returns a compiled CompiledStateGraph.
    """
    builder = StateGraph(NewsPulseReportState)

    # Add nodes
    builder.add_node("preprocess",           preprocess_node)
    builder.add_node("executive_summary",    executive_summary_node)
    builder.add_node("sentiment_dashboard",  sentiment_dashboard_node)
    builder.add_node("headlines",            headlines_node)
    builder.add_node("in_depth_analysis",    in_depth_analysis_node)
    builder.add_node("company_analysis",     company_analysis_node)
    builder.add_node("trends_risks",         trends_risks_node)
    builder.add_node("regional_outlook",     regional_outlook_node)
    builder.add_node("sources",              sources_node)
    builder.add_node("assemble",             assemble_node)
    builder.add_node("pdf",                  pdf_node)

    # Define sequential edges
    builder.add_edge(START,                  "preprocess")
    builder.add_edge("preprocess",           "executive_summary")
    builder.add_edge("executive_summary",    "sentiment_dashboard")
    builder.add_edge("sentiment_dashboard",  "headlines")
    builder.add_edge("headlines",            "in_depth_analysis")
    builder.add_edge("in_depth_analysis",    "company_analysis")
    builder.add_edge("company_analysis",     "trends_risks")
    builder.add_edge("trends_risks",         "regional_outlook")
    builder.add_edge("regional_outlook",     "sources")
    builder.add_edge("sources",              "assemble")
    builder.add_edge("assemble",             "pdf")
    builder.add_edge("pdf",                  END)

    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)

    if mermaid_diagram:
        try:
            graph_image = graph.get_graph(xray=True).draw_mermaid_png()
            with open("newspulse_report_graph.png", "wb") as f:
                f.write(graph_image)
        except Exception as e:
            print(f"Failed to generate graph diagram: {e}")

    return graph

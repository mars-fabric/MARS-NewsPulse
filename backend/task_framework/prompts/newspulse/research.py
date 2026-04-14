"""
DEPRECATED — replaced by discovery.py and analysis.py.

Kept for backward compatibility. New code should import from
discovery.py (stage 2) and analysis.py (stage 3).
"""

# Re-export discovery prompts for any old imports
from task_framework.prompts.newspulse.discovery import (
    discovery_planner_prompt as research_planner_prompt,
    discovery_researcher_prompt as research_researcher_prompt,
)

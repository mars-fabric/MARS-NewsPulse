"""
Deepresearch task integration framework.

Provides utilities, stage helpers, and phase classes for the multi-stage
research paper workflow (idea -> method -> experiment -> paper).
"""

from task_framework.utils import (
    get_task_result,
    format_prompt,
    format_prompt_safe,
    extract_markdown_content,
    create_work_dir,
    extract_clean_markdown,
    input_check,
    extract_file_paths,
    check_file_paths,
)

from task_framework import stage_helpers

__all__ = [
    "get_task_result",
    "format_prompt",
    "format_prompt_safe",
    "extract_markdown_content",
    "create_work_dir",
    "extract_clean_markdown",
    "input_check",
    "extract_file_paths",
    "check_file_paths",
    "stage_helpers",
]

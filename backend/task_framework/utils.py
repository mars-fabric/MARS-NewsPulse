"""Utilities for Deepresearch task integration."""

import os
import re
import logging
import string
from pathlib import Path

logger = logging.getLogger(__name__)

MD_CODE_BLOCK_PATTERN = r"```(?:markdown)?\s*\n([\s\S]*?)```"


def get_task_result(chat_history: list, name: str) -> str:
    """Extract the last result from a specific agent in chat history.

    Copied from Deepresearch/deepresearch/utils.py:62-68. Iterates backwards through
    chat history to find the last message from the named agent.

    Args:
        chat_history: List of message dicts with 'name' and 'content' keys
        name: Agent name to search for (e.g., 'idea_maker_nest', 'researcher_response_formatter')

    Returns:
        Content string from the agent's last message

    Raises:
        ValueError: If agent name not found in chat history
    """
    for obj in chat_history[::-1]:
        if obj.get('name') == name:
            return obj['content']
    raise ValueError(f"Agent '{name}' not found in chat history")


def format_prompt(template: str, **kwargs) -> str:
    """Format a prompt template with named parameters.

    Uses Python's str.format() — same pattern Deepresearch uses.

    Args:
        template: Prompt string with {placeholder} syntax
        **kwargs: Values to inject

    Returns:
        Formatted prompt string
    """
    try:
        result = template.format(**kwargs)
        logger.debug("Formatted prompt with keys: %s", list(kwargs.keys()))
        return result
    except KeyError as e:
        logger.error("Missing prompt placeholder: %s", e)
        raise ValueError(f"Missing required prompt placeholder: {e}")


def format_prompt_safe(template: str, **kwargs) -> str:
    """Like format_prompt but leaves unfilled placeholders intact."""

    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'

    formatter = string.Formatter()
    return formatter.vformat(template, (), SafeDict(**kwargs))


def extract_markdown_content(text: str) -> str:
    """Extract markdown content from code blocks (Deepresearch's post-processing pattern).

    Used after experiment stage to extract clean markdown from agent response.
    """
    match = re.search(MD_CODE_BLOCK_PATTERN, text)
    if match:
        return match.group(1).strip()
    return text.strip()


def create_work_dir(work_dir: str | Path, name: str) -> Path:
    """Create stage-specific working directory (Deepresearch pattern).

    Each stage creates '<name>_generation_output' subdirectory.
    Source: Deepresearch/deepresearch/utils.py:79-84

    Args:
        work_dir: Parent working directory path
        name: Stage name used to construct subdirectory name

    Returns:
        Path to created stage-specific output directory
    """
    work_dir = os.path.join(str(work_dir), f"{name}_generation_output")
    os.makedirs(work_dir, exist_ok=True)
    return Path(work_dir)


def extract_clean_markdown(text: str) -> str:
    """Extract markdown from code blocks and strip HTML comments.

    Exact regex from Deepresearch method.py:71-73 and experiment.py:109-111.
    Falls back to original text if no code block found.

    Args:
        text: Raw text potentially containing markdown code blocks

    Returns:
        Cleaned markdown content with HTML comments removed
    """
    MD_CLEAN_PATTERN = r"```[ \t]*(?:markdown)[ \t]*\r?\n(.*)\r?\n[ \t]*```"
    matches = re.findall(MD_CLEAN_PATTERN, text, flags=re.DOTALL)
    if matches:
        extracted = matches[0]
        clean = re.sub(r'^<!--.*?-->\s*\n', '', extracted)
        return clean
    return text.strip()


def input_check(str_input: str) -> str:
    """Check if input is string content or path to .md file.

    If path ends with .md, reads the file. Otherwise returns string as-is.
    Source: Deepresearch/deepresearch/utils.py:8-18

    Args:
        str_input: Either raw string content or a path to a .md file

    Returns:
        The content string (read from file if path, or as-is)

    Raises:
        ValueError: If input is not a string or path to a markdown file
    """
    if str_input.endswith(".md"):
        with open(str_input, 'r') as f:
            return f.read()
    elif isinstance(str_input, str):
        return str_input
    else:
        raise ValueError("Input must be a string or a path to a markdown file.")


def extract_file_paths(content: str) -> list[str]:
    """Extract file paths from data description content.

    Finds patterns that look like absolute file paths (starting with /).
    Helper for check_file_paths().
    Source: Deepresearch/deepresearch/utils.py:61-77

    Args:
        content: Text content that may contain file path references

    Returns:
        List of extracted file path strings
    """
    path_pattern = r'(?:/[\w./-]+)'
    return re.findall(path_pattern, content)


def check_file_paths(content: str) -> None:
    """Validate file paths in data description are absolute and exist.

    Warns about hallucination risk if paths are wrong. Should be called
    early in the pipeline to catch invalid data references before stages
    attempt to use them.
    Source: Deepresearch/deepresearch/utils.py:61-77

    Args:
        content: Data description text containing file path references

    Raises:
        FileNotFoundError: If any referenced file path does not exist
        ValueError: If any referenced file path is not absolute
    """
    paths = extract_file_paths(content)
    for p in paths:
        if not os.path.isabs(p):
            raise ValueError(
                f"File path '{p}' is not absolute. Use absolute paths to avoid hallucination risk."
            )
        if not os.path.exists(p):
            raise FileNotFoundError(
                f"File path '{p}' does not exist. Verify data paths to avoid hallucination risk."
            )

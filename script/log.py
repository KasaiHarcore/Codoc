import time
from collections.abc import Callable
from os import get_terminal_size

from loguru import logger
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

welcome_message_chat = """
# Welcome to Codoc, this is the Mixture-of-Agents (MoA) test demo!

Mixture of Agents (MoA) is a novel approach that leverages the collective strengths of multiple LLMs to enhance performance, achieving state-of-the-art results. By employing a layered architecture where each layer comprises several LLM agents, MoA significantly outperforms GPT-4 Omni’s 57.5% on AlpacaEval 2.0 with a score of 65.1%, using only open-source models!

This demo uses the following LLMs as reference models, then passes the results to the aggregate model for the final response:
- groq/llama3-8b-8192
- groq/llama3-70b-8192
- groq/mixtral-8x7b-32768
- groq/gemma-7b-it
"""


def terminal_width():
    return get_terminal_size().columns


WIDTH = min(120, terminal_width() - 10)

console = Console()

print_stdout = True


def log_exception(exception):
    logger.exception(exception)


def print_banner(msg: str) -> None:
    if not print_stdout:
        return

    banner = f" {msg} ".center(WIDTH, "=")
    console.print()
    console.print(banner, style="bold")
    console.print()


def replace_html_tags(content: str):
    """
    Helper method to process the content before printing to markdown.
    """
    replace_dict = {
        "<file>": "[file]",
        "<class>": "[class]",
        "<func>": "[func]",
        "<method>": "[method]",
        "<code>": "[code]",
        "<original>": "[original]",
        "<patched>": "[patched]",
        "</file>": "[/file]",
        "</class>": "[/class]",
        "</func>": "[/func]",
        "</method>": "[/method]",
        "</code>": "[/code]",
        "</original>": "[/original]",
        "</patched>": "[/patched]",
    }
    for key, value in replace_dict.items():
        content = content.replace(key, value)
    return content


def print_px(
    msg: str, desc = "", print_callback: Callable[[dict], None] | None = None
) -> None:
    if not print_stdout:
        return

    msg = replace_html_tags(msg)
    markdown = Markdown(msg)

    name = "Codoc"
    if desc:
        title = f"{name} ({desc})"
    else:
        title = name

    panel = Panel(
        markdown,
        title=title,
        title_align="left",
        border_style="magenta",
        width=WIDTH,
    )
    console.print(panel)

    if print_callback:
        print_callback(
            {"title": f"{name} ({desc})", "message": msg, "category": "Codoc"}
        )
        
def print_chat(
    msg: str, desc = "", print_callback: Callable[[dict], None] | None = None
) -> None:
    if not print_stdout:
        return

    name = "Chat Agent"
    if desc:
        title = f"{name} ({desc})"
    else:
        title = name

    panel = Panel(
        msg,
        title=title,
        title_align="left",
        border_style="green",
        width=WIDTH,
    )
    console.print(panel)

    if print_callback:
        print_callback(
            {"title": f"{name} ({desc})", "message": msg, "category": "chat_agent"}
        
)
        
def print_user(
    msg: str, desc = "", print_callback: Callable[[dict], None] | None = None
) -> None:
    if not print_stdout:
        return

    msg = replace_html_tags(msg)
    markdown = Markdown(msg)

    name = "User"
    if desc:
        title = f"{name} ({desc})"
    else:
        title = name

    panel = Panel(
        markdown,
        title=title,
        title_align="left",
        border_style="cyan",
        width=WIDTH,
    )
    console.print(panel)

    if print_callback:
        print_callback(
            {"title": f"{name} ({desc})", "message": msg, "category": "user"}
        )


def print_retrieval(
    msg: str, desc="", print_callback: Callable[[dict], None] | None = None
) -> None:
    if not print_stdout:
        return

    msg = replace_html_tags(msg)
    markdown = Markdown(msg)

    name = "Context Retrieval Agent"
    if desc:
        title = f"{name} ({desc})"
    else:
        title = name

    panel = Panel(
        markdown,
        title=title,
        title_align="left",
        border_style="blue",
        width=WIDTH,
    )
    console.print(panel)
    if print_callback:
        print_callback(
            {
                "title": f"{name} ({desc})",
                "message": msg,
                "category": "context_retrieval_agent",
            }
        )


def print_doc_generation(
    msg: str, desc="", print_callback: Callable[[dict], None] | None = None
) -> None:
    if not print_stdout:
        return

    msg = replace_html_tags(msg)
    markdown = Markdown(msg)

    name = "Documents Generation"
    if desc:
        title = f"{name} ({desc})"
    else:
        title = name

    panel = Panel(
        markdown,
        title=title,
        title_align="left",
        border_style="yellow",
        width=WIDTH,
    )
    console.print(panel)
    if print_callback:
        print_callback(
            {
                "title": f"{name} ({desc})",
                "message": msg,
                "category": "doc_generation",
            }
        )


def print_description(content: str) -> None:
    if not print_stdout:
        return

    title = "Project description"
    panel = Panel(
        content,
        title=title,
        title_align="left",
        border_style="red",
        width=WIDTH,
    )
    console.print(panel)


def log_and_print(msg):
    logger.info(msg)
    if print_stdout:
        console.print(msg)


def log_and_cprint(msg, **kwargs):
    logger.info(msg)
    if print_stdout:
        console.print(msg, **kwargs)


def log_and_always_print(msg):
    """
    A mode which always print to stdout, no matter what.
    Useful when running multiple tasks and we just want to see the important information.
    """
    logger.info(msg)
    # always include time for important messages
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    console.print(f"\n[{t}] {msg}")


def print_with_time(msg):
    """
    Print a msg to console with timestamp.
    """
    t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    console.print(f"\n[{t}] {msg}")

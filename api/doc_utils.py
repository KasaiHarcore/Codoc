"""
Utility functions for parsing and applying the patch.

Inspired by:
https://github.com/gpt-engineer-org/gpt-engineer/blob/main/gpt_engineer/core/chat_to_files.py
"""

from dataclasses import dataclass
from pprint import pformat
from tempfile import NamedTemporaryFile
from typing import TextIO

from pylint.lint import Run
from pylint.reporters.text import TextReporter


@dataclass
class Edit:
    filename: str
    result: str

    def __str__(self):
        return f"{self.filename}\nResults:\n{pformat(self.result)}\n"

    def __repr__(self):
        return str(self)

class Writable(TextIO):
    "dummy output stream for pylint"

    def __init__(self) -> None:
        self.content: list[str] = []

    def write(self, s: str) -> int:
        self.content.append(s)
        return len(s)

    def read(self, n: int = 0) -> str:
        return "\n".join(self.content)


def lint_python_content(content: str) -> bool:
    """Check if python content lints OK.

    Args:
        content: python file content

    Returns: True if the contents passes linting, False otherwise.

    """
    pylint_out = Writable()
    reporter = TextReporter(pylint_out)

    with NamedTemporaryFile(buffering = 0) as f:
        f.write(content.encode())

        _ = Run(["--errors-only", f.name], reporter=reporter, exit=False)

    return not any(error.endswith("(syntax-error)") for error in pylint_out.content)

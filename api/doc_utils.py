"""
Utility functions for parsing and applying the patch.

Inspired by:
https://github.com/gpt-engineer-org/gpt-engineer/blob/main/gpt_engineer/core/chat_to_files.py
"""

import re
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


def parse_document_changes(chat_string: str) -> list[Edit]:
    """
    Parse changes from a chat string.

    This function extracts code changes from a chat string and returns them as a list
    of Edit objects.

    Args:
        chat_string (str): The chat content containing code changes.

    Returns:
        List[Edit]: A list of Edit objects representing the parsed code changes.
    """
    
    def parsing(lines: list[str]):
        """
        New version of parsing multiple edits within one fence.
        """
        # remove obviously suspicious lines
        sus_contents = ["# Rest of the file..."]
        lines = [line for line in lines if line.strip() not in sus_contents]

        file_start = "<file>"
        file_end = "</file>"
        original_start = "<content>"
        original_end = "</content>"

        all_edits: list[Edit] = []
        content = "\n".join(lines)

        # use regex to find content between <file> and </file>
        file_pattern = re.compile(f"{file_start}(.*?){file_end}", re.DOTALL)
        original_pattern = re.compile(f"{original_start}(.*?){original_end}", re.DOTALL)

        file_matches = file_pattern.findall(content)
        original_matches = original_pattern.findall(content)

        for file, original in zip(
            file_matches, original_matches
        ):
            # for file, we strip all spaces
            file = file.strip()
            # for previous gen and the new one, keep the spaces, since removing spaces at beginning or end
            # may mess up indentation level on some of the lines.
            # However, we should remove the new lines at start and end. These new lines may be
            # inserted by the model
            original = original.strip("\n")
            all_edits.append(Edit(file, original))

        return all_edits

    edits = []

    for line in chat_string.split("\n"):
        edits.extend(parsing(line))

    return edits


def apply_document_changes(edit: Edit, file_path: str) -> str | None:
    """
    Apply one Edit to a document. This function reads the document, tries to match
    the original string (after stripping spaces in the original document and the
    original string to improve the chance of matching), and then replaces the matched region with the updated string.
    Returns:
        - Path to the document containing updated content if successful;
          None otherwise.
    """
    with open(file_path, 'r') as f:
        orig_doc_lines = f.readlines()

    results = edit.result

    # check whether original is in the original document
    results_lines = results.split("\n")
    # NOTE: These are just for matching; do not use to form back the document
    cleaned_orig_lines = [line.strip() for line in orig_doc_lines]
    cleaned_results_lines = [line.strip() for line in results_lines]
    # match original in the original document
    match_start = -1
    match_end = -1
    for i in range(len(cleaned_orig_lines) - len(cleaned_results_lines) + 1):
        # check all possible starting positions in the orig document
        if (
            cleaned_orig_lines[i : i + len(cleaned_results_lines)]
            == cleaned_results_lines
        ):
            match_start = i
            match_end = i + len(cleaned_results_lines)
            break
    if match_start == -1:
        # could not find a match
        return None

    # found a match, replace the matched region with updated

    # form the new document
    prefix = "".join(orig_doc_lines[:match_start])
    suffix = "".join(orig_doc_lines[match_end:])
    new_doc = prefix + "\n".join(results_lines) + "\n" + suffix

    with open(file_path, 'w') as f:
        f.write(new_doc)

    return file_path


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

"""
An agent, which is only responsible for the write_docs tool call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from os.path import join as pjoin
from pathlib import Path

from loguru import logger

from api import agent_common
from script.data_structures import MessageThread
from script.log import print_px, print_doc_generation
from app.model import common

SYSTEM_PROMPT = """
You are a seasoned software developer with extensive experience in various engineering positions within the technology sector, particularly in maintaining large projects. 
You are working on an open-source project with multiple contributors, and there is no guideline, document or code comments available.
Your task is to guide a junior developer how to use and understand the project.
"""

USER_PROMPT_INIT = """
Write a comprehensive documents for the entire project, based on the retrieved context. Focus on each function in the code, how they connect, and how they depend on each other. 

- In the document you made, MUST FOLLOW:
    + Study the dependencies and libraries used in the project to understand the external tools and frameworks being utilized.
    + Explain the code workflow and function relationships (if possible, otherwise skip).
    + Describe the hierarchy and dependency of each lines (based on which code calls, libraries, execution order, etc.).
    + Emphasize clarity and educational value, keeping in mind that the primary audience is junior developers.
    + Have a good structure and organization of the document.

- Thing must HAVE in the document:
    + Markdown file is preferred.
    + Use headers, bullet points, code blocks, etc., to make the document clear and easy to read.

STRUCTURE:

```
File name: ...

0. Code Overview:
...

1. Functions or Classes:
- File Location: <location containing the function/class/variable>
- Library import:
    + Local library: <library 1>, <library 2>, ...
    + 3rd party library: <library 1>, <library 2>, ...
    + base library (build-in Python): <library 1>, <library 2>, ...
    
- <global variable 1>: <type> (if any)
- ...
    
- <function 1> (var1: type, var2: type, ...) -> return_type:
    + Breif explanation of what this function does
    + Explain how it work on every line of code.
- <function ...> ...
    
- <class 1>:
    - <method 1> (var1: type, var2: type, ...) -> return_type:
        + Same as <function>
    
    - <method 2> (...): ...
        + ...
        
* Repeat for all functions and classes in the codebase.
* The output here must have a form of API documents, with clear and concise explanations.

2. Connections between files:
- Function1 calls Function2 in File1
- File1 depends on File2
- Class1 inherits from Class2 in File3
- ...
    
3. Overall summary:
...

```

REMEBER TO NOT MAKING THINGS UP. IF YOU DON'T KNOW, JUST SKIP IT AND WRITE (unidentified) INSTEAD.
"""

def run_with_retries(
    message_thread: MessageThread,
    output_dir: str,
    retries: int = 1,
    print_callback: Callable[[dict], None] | None = None,
) -> tuple[str, float, int, int]:
    """
    Since the agent may not always write an applicable patch, we allow for retries.
    This is a wrapper around the actual run.
    """
    # Build a clean context thread for doc generation.
    # The main conversation contains a lot of "API Calls" chatter that strongly biases
    # the model to keep emitting API calls instead of producing the document.
    cleaned = MessageThread(messages=[{"role": "system", "content": SYSTEM_PROMPT}])

    # Keep only the useful, factual context:
    # - initial README + folder structure (<read>...)</n+    # - tool results ("Result of ...")
    for m in message_thread.messages:
        if m.get("role") != "user":
            continue
        content = m.get("content") or ""
        if content.startswith("<read>") or content.startswith("Result of "):
            cleaned.add_user(content)

    # Add the initial user prompt
    new_thread = cleaned
    new_thread.add_user(USER_PROMPT_INIT)
    print_px(USER_PROMPT_INIT, "Documents generation", print_callback=print_callback)

    result_msg = ""

    for i in range(1, retries + 1):
        debug_file = pjoin(output_dir, f"agent_write_doc_{i}.json")
        with open(debug_file, "w") as f:
            json.dump(new_thread.to_msg(), f, indent=4)

        logger.info(f"Trying to write a doc. Try {i} of {retries}.")

        raw_doc_file = pjoin(output_dir, f"agent_doc_raw_{i}.md")

        # actually calling model
        res_text, *_ = common.SELECTED_MODEL.call(new_thread.to_msg())

        new_thread.add_model(res_text, [])  # no tools

        logger.info(f"Raw doc produced in try {i}. Writing into file.")

        with open(raw_doc_file, "w") as f:
            f.write(res_text)

        print_doc_generation(
            res_text, f"try {i} / {retries}", print_callback=print_callback
        )

        doc_content = Path(raw_doc_file).read_text()
        print_px(
            f"```\n{doc_content}\n```",
            "Extracted doc",
            print_callback=print_callback,
        )

    result_msg = "Doc generation successful."
    return result_msg



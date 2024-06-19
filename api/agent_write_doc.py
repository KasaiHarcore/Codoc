"""
An agent, which is only responsible for the write_docs tool call.
"""

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
from script.doc_extracting import (
    ExtractDoc,
    record_extract_doc,
    check_doc_gen,
)

SYSTEM_PROMPT = """
You are a seasoned software developer with extensive experience in various engineering positions within the technology sector, particularly in maintaining large projects. 
You are working on an open-source project with multiple contributors, and there is no comprehensive documentation available.
The context contains a description marked between <read> and </read>.
Your task is to invoke a few search API calls to gather information, then write a documents to guide a junior developer with basic knowledge on how to use and understand the project.
"""

USER_PROMPT_INIT = """
Write a comprehensive documents with key points for the entire project, based on the retrieved context. Focus on each function in the code, how they connect, and how they depend on each other. 

Return the document in the format below. Replace `...` with the actual file path within `<file></file>`, and the content of the document within `<content></content>`.

- In your document, you should:
    + Provide a detailed explanation of functions, variables, etc.
    + Reconstruct and explain the code workflow and function relationships (if possible, otherwise skip)
    + Describe the hierarchy and dependency of each file (based on which file calls which, libraries, execution order, etc.)
    + Include a description of the codebase structure and app architecture in text or code (flowchart, diagram, etc.)
    + Emphasize clarity and educational value, keeping in mind that the primary audience is junior developers.
    + Use concrete examples and illustrations to aid understanding.
    + Detail mechanisms and best practices.
    + Highlight the modularity and reusability of the code components.
    + Provide a good structure and organization of the document.
    + DO NOT MAKEUP ANY INFORMATION. IF YOU CANNOT FIND THE INFORMATION, REPORT WHERE YOU CAN'T DO IT THEN SKIP.

- The output should look like this:

<file>...</file>
<content>...</content>

- Example structure guide:

**IN THE BEGINNING OF THE DOCUMENT:**

0. Project Overview:
    - Project Name: ...
    - Project Description: ...
    - Project Goal: ...
    - Project Scope: ...
    
**MIDDLE**

1. Functions or Classes:
    - File Location: <location containing the function/class/variable>
    - Starting Line: <line number>
    - <function 1> (var1: type, var2: type, ...):
        + <var_included: type>: (Describe what this variable does and its effect)
        + ...
    Explanation: (Detailed explanation of what this function does, how it works, and how it connects with other functions, variables, classes, etc.)
    Example: (Provide a usage example or snippet if possible.)
    
    - File Location: ...
    - Starting Line: ...
    - <function 2> (...): ...
        + <var: ...>: ...
        + ...
    * Repeat for all functions and classes in the codebase.

2. Connections between files:
    - Function1 calls Function2 in File1
    - File1 depends on File2
    - Class1 inherits from Class2 in File3
    - ...

3. Summary:
    - Summarize the entire project from start to end
    - Mention key takeaways and overall architecture
    
4. Flow of Execution:
    - ...

**IN THE END OF THE DOCUMENT:**

5. Flowchart
    - Describe the code flow using text, flowcharts, diagrams, etc. Use the method you think best explains the workflow.
"""


def run_with_retries(
    message_thread: MessageThread,
    output_dir: str,
    retries: int = 5,
    print_callback: Callable[[dict], None] | None = None,
) -> tuple[str, float, int, int]:
    """
    Since the agent may not always write an applicable patch, we allow for retries.
    This is a wrapper around the actual run.
    """
    # (1) replace system prompt
    messages = deepcopy(message_thread.messages)
    new_thread: MessageThread = MessageThread(messages=messages)
    new_thread = agent_common.replace_system_prompt(new_thread, SYSTEM_PROMPT)

    # (2) add the initial user prompt
    new_thread.add_user(USER_PROMPT_INIT)
    print_px(USER_PROMPT_INIT, "Documents generation", print_callback=print_callback)

    result_msg = ""

    for i in range(1, retries + 1):
        debug_file = pjoin(output_dir, f"agent_write_doc_{i}.json")
        with open(debug_file, "w") as f:
            json.dump(new_thread.to_msg(), f, indent=4)

        logger.info(f"Trying to write a doc. Try {i} of {retries}.")

        raw_doc_file = pjoin(output_dir, f"agent_doc_raw_{i}")

        # actually calling model
        res_text, *_ = common.SELECTED_MODEL.call(new_thread.to_msg())

        new_thread.add_model(res_text, [])  # no tools

        logger.info(f"Raw doc produced in try {i}. Writing into file.")

        with open(raw_doc_file, "w") as f:
            f.write(res_text)

        print_doc_generation(
            res_text, f"try {i} / {retries}", print_callback=print_callback
        )

        # Attempt to extract a real doc from the raw doc
        diff_file = pjoin(output_dir, f"extracted_doc_{i}.diff")
        extract_doc = check_doc_gen(raw_doc_file)

        # record the extracted doc. This is for classifying the task at the end of the workflow
        record_extract_doc(output_dir, extract_doc)

        doc_content = Path(diff_file).read_text()
        print_px(
            f"```\n{doc_content}\n```",
            "Extracted doc",
            print_callback=print_callback,
        )

        if extract_doc != ExtractDoc.RAW_DOC_GENERATED:
            # we don't have a valid doc
            new_prompt = "Task could not be finished."
            new_thread.add_user(new_prompt)
            print_px(
                new_prompt,
                f"Doc generation try {i} / {retries}",
                print_callback=print_callback,
            )
            result_msg = "Failed to write a valid one."
        else:
            result_msg = "Successfully wrote a valid doc."
            break

    return result_msg



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

SYSTEM_PROMPT = """You are a software developer with multiple experience in other engineer position in technology maintaining a large project.
You are working on an open-source project with multiple contributors and there's no fully explained documentation.
The context contains a description marked between <read> and </read>.
Your task is to invoke a few search API calls to gather information, then write a comprehensive document to guild a 12 year-old kids with based knowledge how to use the project and give them a deep understanding of the project.
"""


USER_PROMPT_INIT = """Write a documents for the entire project, based on the retrieved context. Focus on every function inside the code, how it connect, how it depend on each other\n\nYou can import necessary libraries, using what you need for it.\n\n
Return the documents in the format below.\n\nWithin `<file></file>`, replace `...` with actual file path.\n\nWithin `<previous></previous>`, replace `...` with the previous response snippet or leave it blank if it's the first write.\n\nWithin `<patched></patched>`, replace `...` with the newest version of the document. When adding and updated documents, (for coding example please pay attention to indentation, as the code is in Python.)
You can write multiple modifications if needed.

- After finish writing introduction and basic explain of the codebase, you have to write:
    + Explain deeply how each function work, variable type, ...
    + Depending level of each file (Base on which file it call from, the library, running order,...)
    + A code to drawing workflow using Python graphviz library
    + Some running example with the code, remember to pass a REAL variable


# Version 1
<file>...</file>
<previous>...</previous>
<patched>...</patched>

Function:
File Location: <location that contain the function>
- <function 1> (var1: type, var2: type,...): describe it here
    + <var1: type>: Describe the variable effect, what can it do, what it control
    + <var2: type>: ...
- <function 2> (...): ...
    + <var1: type>: ...
    + ...

Depending Level:
- ...

Workflow:
```python
...
```

Running Example:
- ...
- ...

# Version 2
... Same as above if there's more than 1 time you have to write it

# Version ...

"""


def run_with_retries(
    message_thread: MessageThread,
    output_dir: str,
    retries = 3,
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
    print_px(USER_PROMPT_INIT, "Documents generation", print_callback = print_callback)

    can_stop = False
    result_msg = ""

    for i in range(1, retries + 2):
        if i > 1:
            debug_file = pjoin(output_dir, f"agent_write_doc_{i - 1}.json")
            with open(debug_file, "w") as f:
                json.dump(new_thread.to_msg(), f, indent=4)

        if can_stop or i > retries:
            break

        logger.info(f"Trying to write a doc. Try {i} of {retries}.")

        raw_doc_file = pjoin(output_dir, f"agent_doc_raw_{i}")

        # actually calling model
        res_text, *_ = common.SELECTED_MODEL.call(new_thread.to_msg())

        new_thread.add_model(res_text, [])  # no tools

        logger.info(f"Raw doc produced in try {i}. Writing into file.")

        with open(raw_doc_file, "w") as f:
            f.write(res_text)

        print_doc_generation(
            res_text, f"try {i} / {retries}", print_callback = print_callback
        )

        # Attemp to extract a real doc from the raw doc
        diff_file = pjoin(output_dir, f"extracted_doc_{i}.diff")
        extract_doc = check_doc_gen(raw_doc_file)

        # record the extract doc. This is for classifying the task at the end of workflow
        record_extract_doc(output_dir, extract_doc)

        doc_content = Path(diff_file).read_text()
        print_px(
            f"```\n{doc_content}\n```",
            "Extracted doc",
            print_callback = print_callback,
        )

        if extract_doc != ExtractDoc.RAW_DOC_GENERATED:
            # we dont have a valid docs
            new_prompt = (
                "Task could not be finished."
            )
            new_thread.add_user(new_prompt)
            print_px(
                new_prompt,
                f"Doc generation try {i} / {retries}",
                print_callback = print_callback,
            )
            result_msg = "Failed to write valid one."

    return result_msg


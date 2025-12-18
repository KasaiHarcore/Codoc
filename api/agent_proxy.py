from __future__ import annotations

"""
A proxy agent. Process raw response into json format.
"""

import inspect
from typing import Any

from loguru import logger

from script.data_structures import MessageThread
from app.model import common
from script.doc_extracting import ExtractDoc, is_valid_json
from search.search_manage import SearchManager
from script.utils import parse_function_invocation

PROXY_PROMPT = """
You are a helpful assistant that retreive API calls from a text into json format.
The text will consist of two parts:
1. do we need more context?
2. do you have enough information to start writing a good summary document?
Extract API calls from question 1 and confirmation from question 2.

The API calls include:
- extract_fullcode(file_path: str)
- search_method_in_class(method_name: str, class_name: str)
- search_method_in_file(method_name: str, file_path: str)
- search_method(method_name: str)
- search_class_in_file(self, class_name, file_name: str)
- search_class(class_name: str)
- search_code_in_file(code_str: str, file_path: str)
- search_code(code_str: str)

Provide your answer in JSON structure like this, you should ignore the argument placeholders in api calls.
For example, search_code(code_str="str") should be search_code("str")
search_method_in_file("method_name", "path.to.file") should be search_method_in_file("method_name", "path/to/file")
Make sure each API call is written as a valid python expression.

### NOTE
- Return 1 if claim "Yes", else 0 for "No" for question 2.
- Leave API_calls blank if there's no right call make in question 1.

{
    "API_calls": ["api_call_1(args)", "api_call_2(args)", ...],
    "Finish": [1] | [0]
}
"""


def run_with_retries(text: str, retries = 5) -> tuple[str | None, list[MessageThread]]:
    msg_threads = []
    for idx in range(1, retries + 1):
        logger.debug(
            "Trying to select search APIs in json. Try {} of {}.", idx, retries
        )

        res_text, new_thread = run(text)
        msg_threads.append(new_thread)

        extract_status, data = is_valid_json(res_text)

        if extract_status != ExtractDoc.IS_VALID_JSON:
            logger.debug("Invalid json. Retry.")
            continue

        valid, diagnosis = is_valid_response(data)
        if not valid:
            logger.debug(f"{diagnosis}. Retry.")
            continue

        logger.debug("Extracted a valid json")
        return res_text, msg_threads
    return None, msg_threads


def run(text: str) -> tuple[str, MessageThread]:
    """
    Run the agent to extract to json format.
    """

    msg_thread = MessageThread()
    msg_thread.add_system(PROXY_PROMPT)
    msg_thread.add_user(text)
    res_text, *_ = common.SELECTED_MODEL.call(
        msg_thread.to_msg(), response_format = "json_object"
    )

    msg_thread.add_model(res_text, [])  # no tools

    return res_text, msg_thread


def is_valid_response(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Json is not a dict"

    if not data.get("API_calls"):
        finish = data.get("Finish")
        if not isinstance(finish, list) or not finish:
            return False, "Both API_calls and Finish are empty"
        
    else:
        for api_call in data["API_calls"]:
            if not isinstance(api_call, str):
                return False, "Every API call must be a string"

            try:
                func_name, func_args = parse_function_invocation(api_call)
            except Exception:
                return False, "Every API call must be of form api_call(arg1, ..., argn)"

            function = getattr(SearchManager, func_name, None)
            if function is None:
                return False, f"the API call '{api_call}' calls a non-existent function"

            arg_spec = inspect.getfullargspec(function)
            arg_names = arg_spec.args[1:]  # first parameter is self

            if len(func_args) != len(arg_names):
                return False, f"the API call '{api_call}' has wrong number of arguments"

    return True, "OK"

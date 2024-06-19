import inspect
import json
import re
from collections.abc import Callable
from os.path import join as pjoin
from pathlib import Path

from loguru import logger
from termcolor import colored
from app import globals
from app.manage import ProjectApiManager
from script.data_structures import FunctionCallIntent, MessageThread
from script.log import (
    log_and_cprint,
    log_and_print,
    print_px,
    print_banner,
    print_description,
    print_retrieval,
)
from app.model import common, ollama
from search.search_manage import SearchManager
from script.utils import parse_function_invocation, get_directory_structure

# FIXME: the system prompt should be different for stratified/state machine.
SYSTEM_PROMPT = """You are a software developer with multiple experience in other fields in technology maintaining a large project.
You are working on an open-source project with multiple contributors and there's no fully explained documentation.
The README.md file contains some basic information marked between <read> and </read>.
Your task is to invoke a few search API calls to gather information, then write a comprehensive document to guild people how to use the project and give them a deep understanding of the project.
"""


def prepare_readme_prompt(readme: str, path: str) -> str:
    """
    Given the raw problem statement, sanitize it and prepare the readme prompt.
    Args:
        problem_stmt (str): The raw problem statement.
            Assumption: the problem statement is the content of a markdown file.
    Returns:
        str: The readme prompt.
    """
    # remove markdown comments
    rm_wo_comments = re.sub(r"<!--.*?-->", "", readme, flags=re.DOTALL)
    content_lines = rm_wo_comments.split("\n")
    # remove spaces and empty lines
    content_lines = [x.strip() for x in content_lines]
    content_lines = [x for x in content_lines if x != ""]
    problem_stripped = "\n".join(content_lines)
    # add tags
    result = "<read>" + "\nREADME file:\n" + problem_stripped + "\n</read>"
    # add code structure folder
    result += "\nCodebase folder structure:\n"
    sts = get_directory_structure(path)
    print_description(f"Codebase folder structure:\n{sts}")
    result += sts
    return result


def add_step_trigger(orig_prompt: str, is_first: bool = False) -> str:
    """
    Given the original prompt, add the trigger question for the next step.
    Args:
        orig_prompt (str): The original prompt.
        is_first (bool): Whether the trigger is for the first step.
    Returns:
        str: The prompt with trigger question.
    """
    if is_first:
        trigger = "What is the first step?"
    else:
        trigger = "What's the next step to complete the task? Be reminded that you are collecting information to write a comprehensive guild based on code."
    return orig_prompt + "\n" + trigger


def start_conversation_round_stratified(
    output_dir: str,
    msg_thread: MessageThread,
    api_manager: ProjectApiManager,
    start_round_no: int = 0,
    print_callback: Callable[[dict], None] | None = None,
) -> bool:
    """
    This version uses json data to process API calls, instead of using the OpenAI function calling.
    Advantage is that multiple API calls can be made in a single round.
    """
    prompt = (
        "Based on the files, you can use the following search APIs to get more context of the project."
        "\n Recommended that you should run the extract_fullcode first before running the other APIs."
        "\n\nBased on the files from the code structure, you can use the following search APIs to get more context of the project."
        "\n- extract_fullcode(file_path: str): Get all the code from a file"
        "\n- search_class(class_name: str): Search for a class in the codebase"
        "\n- search_method_in_file(method_name: str, file_path: str): Search for a method in a given file"
        "\n- search_method_in_class(method_name: str, class_name: str): Search for a method in a given class"
        "\n- search_method(method_name: str): Search for a method in the entire codebase"
        "\n- search_code(code_str: str): Search for a code snippet in the entire codebase"
        "\n- search_code_in_file(code_str: str, file_path: str): Search for a code snippet in a given file file"
        "\n\n- DO NOT SKIP ANY NONE SPECIAL FILES BECAUSE IT MAYBE CONTAIN A LOT IMPORTANT INFORMATION, PLEASE ANALYZE CAREFULLY BEFORE DECIDE"
        "\n\n- You can make multiple API calls in a single round. Please make sure to provide concrete arguments for each API call."
        "\n\n- Focus on the folder structure to make a right file_path"
        "\n\n- Now analyze the codebase and select necessary APIs to get more context of the project. Each API call must have concrete arguments as inputs."
    )
    msg_thread.add_user(prompt)

    round_no = start_round_no
    for round_no in range(start_round_no, globals.conv_round_limit + 1):
        api_manager.start_new_tool_call_layer()

        conversation_file = pjoin(output_dir, f"conversation_round_{round_no}.json")
        # save current state before starting a new round
        msg_thread.save_to_file(conversation_file)

        print_banner(f"CONTEXT RETRIEVAL ROUND {round_no}")

        print_px(
            prompt,
            f"context retrieval round {start_round_no}",
            print_callback=print_callback,
        )

        res_text, *_ = common.SELECTED_MODEL.call(msg_thread.to_msg())
        msg_thread.add_model(res_text, tools=[])
        print_retrieval(res_text, f"round {round_no}", print_callback = print_callback)

        selected_apis, _, proxy_threads = api_manager.proxy_apis(res_text)

        proxy_log = Path(output_dir, f"agent_proxy_{round_no}.json")
        proxy_messages = [thread.to_msg() for thread in proxy_threads]
        proxy_log.write_text(json.dumps(proxy_messages, indent = 4))

        if selected_apis is None:
            msg = "The search API calls seem not valid. Please check the arguments you give carefully and try again."
            msg_thread.add_user(msg)
            print_px(
                msg,
                f"context retrieval round {round_no}",
                print_callback=print_callback,
            )
            continue

        selected_apis_json = json.loads(selected_apis)

        json_api_calls = selected_apis_json.get("API_calls", [])
        finish = selected_apis_json.get("Finish", [])

        formatted = []
        if json_api_calls:
            formatted.append("API calls:")
            for call in json_api_calls:
                formatted.extend([f"\n- `{call}`"])            

        if finish:
            formatted.append("\nFinish:")
            for check in finish:
                if check == 0:
                    formatted.append("Not enough information, continue to retrieval")
                elif check == 1:
                    formatted.append("Ready to write docs...")
                    
        print_px(
            "\n".join(formatted),
            "Agent-selected API calls",
            print_callback=print_callback,
        )

        # collected enough information to write patch
        if finish and (not json_api_calls):
            print_banner("DOCS GENERATION")
            logger.debug("Gathered enough information. Starting to created docs.")
            print_px(
                collated_tool_response,
                "Doc generation round 1",
                print_callback=print_callback,
            )
            break

        # prepare response from tools
        collated_tool_response = ""

        for api_call in json_api_calls:
            func_name, func_args = parse_function_invocation(api_call)

            arg_spec = inspect.getfullargspec(getattr(SearchManager, func_name))
            arg_names = arg_spec.args[1:]  # first parameter is self

            assert len(func_args) == len(
                arg_names
            ), f"Number of argument is wrong in API call: {api_call}"

            kwargs = dict(zip(arg_names, func_args))
            intent = FunctionCallIntent(func_name, kwargs, None)
            tool_output, _, _ = api_manager.dispatch_intent(intent, msg_thread, print_callback)

            collated_tool_response += f"Result of {api_call}:\n\n"
            collated_tool_response += tool_output + "\n\n"

        msg_thread.add_user(collated_tool_response)
        print_px(
            collated_tool_response,
            f"context retrieval round {round_no}",
            print_callback=print_callback,
        )

        msg = "Let's analyze collected context first"
        msg_thread.add_user(msg)
        print_px(
            msg, f"context retrieval round {round_no}", print_callback=print_callback
        )

        res_text, *_ = common.SELECTED_MODEL.call(msg_thread.to_msg())
        msg_thread.add_model(res_text, tools=[])
        print_retrieval(res_text, f"round {round_no}", print_callback=print_callback)

        if round_no < globals.conv_round_limit:
            msg = (
                "Based on your analysis, answer below questions:"
                "\n- do we need more context: construct search API calls to get more context of the project. (leave it empty if you don't need more context)"
                "\n- do you have enough information to start writing a comprehensive document?"
            )
            if isinstance(common.SELECTED_MODEL, ollama.OllamaModel):
                # llama models tend to always output both.
                msg += "\n\nNOTE: If you have understand and have a deep knowledge about the context and code, do not make any search API calls."
            msg_thread.add_user(msg)
            print_px(
                msg,
                f"context retrieval round {round_no}",
                print_callback=print_callback,
            )
    else:
        logger.info("Too many rounds occured. Try writing docs anyway.")

    round_no += 1

    api_manager.start_new_tool_call_layer()

    write_doc_intent = FunctionCallIntent("write_doc", {}, None)
    api_manager.dispatch_intent(
        write_doc_intent, msg_thread, print_callback=print_callback
    )

    conversation_file = pjoin(output_dir, f"conversation_round_{round_no}.json")
    msg_thread.save_to_file(conversation_file)

    logger.info("Invoked write_doc. Ending workflow.")

    return True


def dump_tool_call_layers_to_file(
    tool_call_layers: list[dict], output_dir: str
) -> None:
    """Dump the layers of tool calls to a file."""
    tool_call_file = pjoin(output_dir, "tool_call_layers.json")
    with open(tool_call_file, "w") as f:
        json.dump(tool_call_layers, f, indent=4)


def start_conversation_round_state_machine(
    output_dir: str,
    msg_thread: MessageThread,
    api_manager: ProjectApiManager,
    start_round_no: int = 0,
) -> bool:
    """
    Start the actual rounds of conversations with model.

    Args:
        output_dir (str): Path to the output directory.
        msg_thread (MessageThread): The message thread to be used.
        api_manager (ProjectApiManager): The API manager to be used.
        start_round_no (int): The round number to start with.
    """
    round_no = start_round_no
    for round_no in range(start_round_no, globals.conv_round_limit + 1):
        conversation_file = pjoin(output_dir, f"conversation_round_{round_no}.json")
        # save current state before starting a new round
        msg_thread.save_to_file(conversation_file)
        log_and_cprint(
            f"\n========== Conversation Round {round_no} ==========", style="red bold"
        )
        log_and_print(f"{colored('Current message thread:', 'green')}\n{msg_thread}")

        allowed_tools = api_manager.next_tools()
        # TODO: configure the list of tools based on state machine
        tools = ProjectApiManager.get_full_funcs_for_openai(allowed_tools)

        log_and_cprint(f"Current tool state: {api_manager.curr_tool}", style="yellow")
        log_and_cprint(f"Allowed next tool states: {allowed_tools}", style="yellow")

        # create a new iteration of conversation
        res_text, raw_tool_calls, func_call_intents, *_ = common.SELECTED_MODEL.call(
            msg_thread.to_msg(), tools=tools
        )
        log_and_print(
            f"{colored('This round model response (text):', 'blue')} {res_text}"
        )
        # model can decide whether to create a function call
        if len(func_call_intents) == 1:
            # good case in which we can check function call
            func_call_intent: FunctionCallIntent = func_call_intents[0]
            log_and_print(
                f"{colored('This round model response (function call):', 'blue')} {func_call_intent}",
            )
            # dispatch this function call
            this_model_response = res_text
            this_model_tools = raw_tool_calls
            # add previous call information to user message
            tool_output, summary, _ = api_manager.dispatch_intent(
                func_call_intent, msg_thread
            )
        else:
            # no function call, let's force the model to make one
            this_model_tools = []
            this_model_response = res_text
            tool_output = ""
            summary = "There is no function call in your previous response. Make sure you include one function call. "

        next_user_message = add_step_trigger(summary)

        # form message thread for next round. should include what the model said as well
        msg_thread.add_model(this_model_response, this_model_tools)
        if this_model_tools:
            tool_call_id = this_model_tools[0].id
            msg_thread.add_tool(tool_output, tool_call_id)
            msg_thread.add_user(next_user_message)
        else:
            msg_thread.add_user(next_user_message)

        if len(func_call_intents) == 1:
            func_call_name = func_call_intents[0].func_name
            if func_call_name == "write_doc":
                log_and_print("Ending workflow. write_doc has been invoked.")
                break

        log_and_print("Going to next round ..........")
    else:
        log_and_print("Too many rounds. Try writing docs anyway.")
        write_doc_intent = FunctionCallIntent("write_doc", {}, None)
        api_manager.dispatch_intent(write_doc_intent, msg_thread)

    round_no += 1

    # if we end the workflow normally, there is one more round of conversation to store
    conversation_file = pjoin(output_dir, f"conversation_round_{round_no}.json")
    msg_thread.save_to_file(conversation_file)
    return True


def run_one_task(
    output_dir: str,
    api_manager: ProjectApiManager,
    des: str,
    file_path: str,
    print_callback: Callable[[dict], None] | None = None,
) -> bool:
    """
    Main entry point to run inference on one task.
    Args:
        output_dir (str): Path to the output directory.
        api_manager (ProjectApiManager): The already-initialized API manager.
        problem_stmt (str): The original problem statement submitted to the task issue.
    """
    print_banner("Starting on the following task")
    print_description(des)  
    msg_thread = MessageThread()

    system_prompt = SYSTEM_PROMPT
    if (not globals.enable_layered) and common.SELECTED_MODEL.parallel_tool_call:
        # these models support parallel tool calls, let's try to make them not do it
        system_prompt += " In your response, DO NOT make more than one tool call."

    msg_thread.add_system(system_prompt)
    original_prompt = prepare_readme_prompt(des, file_path)
    msg_thread.add_user(original_prompt)

    if globals.enable_layered:
        return start_conversation_round_stratified(
            output_dir, msg_thread, api_manager, print_callback=print_callback
        )
    else:
        return start_conversation_round_state_machine(
            output_dir, msg_thread, api_manager
        )


# NOTE: deprecated
def continue_task_from_cache(
    cache_path: str, output_dir: str, api_manager: ProjectApiManager
) -> bool:
    """
    Run inference on one task, but load conversation history from cache.
    Args:
        cache_path (str): Path to the old conversation history file.
        output_dir (str): Path to the output directory.
        api_manager (ProjectApiManager): The already-initialized API manager.
    """
    # (1) load the existing message thread
    msg_thread = MessageThread.load_from_file(cache_path)
    completed_round_no = msg_thread.get_round_number()

    # (2) start the actual workflow
    return start_conversation_round_state_machine(
        output_dir, msg_thread, api_manager, start_round_no=completed_round_no
    )
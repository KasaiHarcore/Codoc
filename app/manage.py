from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from copy import deepcopy
from os.path import join as pjoin

from docstring_parser import parse
from loguru import logger

from api import agent_proxy, agent_write_doc
from script.data_structures import FunctionCallIntent, MessageThread
from script.log import log_exception
from search.search_manage import SearchManager

from app.task.task_process import Task


class ProjectApiManager:
    ################# State machine specific ################
    # NOTE: this section is for state machine; APIs in stratified mode are specified
    # in agent_api_selector.py
    api_functions = [
        "search_class",
        "search_class_in_file",
        "search_method",
        "search_method_in_class",
        "search_method_in_file",
        "search_code",
        "search_code_in_file",
        "extract_fullcode",
        "write_doc",
    ]

    def next_tools(self) -> list[str]:
        """
        Return the list of tools that should be used in the next round.
        """
        search_tools = [
            "search_class",
            "search_class_in_file",
            "search_method",
            "search_method_in_class",
            "search_method_in_file",
            "search_code",
            "search_code_in_file",
            "extract_fullcode",
        ]
        all_tools = search_tools + ["write_doc"]
        if not self.curr_tool:
            # this means we are at the beginning of the conversation
            # you have to start from doing some search
            return search_tools

        state_machine = {
            "search_class": search_tools,
            "search_class_in_file": search_tools,
            "extract_fullcode": search_tools,
            "search_method": all_tools,
            "search_method_in_class": all_tools,
            "search_method_in_file": all_tools,
            "search_code": all_tools,
            "search_code_in_file": all_tools,
            "write_doc": [],
        }
        return state_machine[self.curr_tool]

    def __init__(self, task: Task, output_dir: str):
        # for logging of this task instance
        self.task = task

        # where to write our output
        self.output_dir = os.path.abspath(output_dir)

        self.task.setup_project()
        # self.setup_project(self.task)

        # build search manager
        self.search_manager = SearchManager(self.task.project_path)

        # keeps track which tools is currently being used
        self.curr_tool: str | None = None

        # record the sequence of tools used, and their return status
        self.tool_call_sequence: list[Mapping] = []

        # record layered API calls
        self.tool_call_layers: list[list[Mapping]] = []

        # record cost and token information
        self.cost: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0

    @classmethod
    def get_short_func_summary_for_openai(cls) -> str:
        """
        Get a short summary of all tool functions.
        Intended to be used for constructing the initial system prompt.
        """
        summary = ""
        for fname in cls.api_functions:
            if not hasattr(cls, fname):
                continue
            func_obj = getattr(cls, fname)
            doc = parse(func_obj.__doc__)
            short_desc = (
                doc.short_description if doc.short_description is not None else ""
            )
            summary += f"\n- {fname}: {short_desc}"
        return summary

    @classmethod
    def get_full_funcs_for_openai(cls, tool_list: list[str]) -> list[dict]:
        """
        Return a list of function objects which can be sent to OpenAI for
        the function calling feature.

        Args:
            tool_list (List[str]): The available tools to generate doc for.
        """
        tool_template = {
            "type": "function",
            "function": {
                "name": "",
                "description": "",
                "parameters": {
                    "type": "object",
                    "properties": {},  # mapping from para name to type+description
                    "required": [],  # name of required parameters
                },
            },
        }
        all_tool_objs = []

        for fname in tool_list:
            if not hasattr(cls, fname):
                continue
            tool_obj = deepcopy(tool_template)
            tool_obj["function"]["name"] = fname
            func_obj = getattr(cls, fname)
            # UPDATE: we only parse docstring now
            # there are two sources of information:
            # 1. the docstring
            # 2. the function signature
            # Docstring is where we get most of the textual descriptions; for accurate
            # info about parameters (whether optional), we check signature.

            ## parse docstring
            doc = parse(func_obj.__doc__)
            short_desc = (
                doc.short_description if doc.short_description is not None else ""
            )
            long_desc = doc.long_description if doc.long_description is not None else ""
            description = short_desc + "\n" + long_desc
            tool_obj["function"]["description"] = description
            doc_params = doc.params
            for doc_param in doc_params:
                param_name = doc_param.arg_name
                if param_name == "self":
                    continue
                typ = doc_param.type_name
                desc = doc_param.description
                is_optional = doc_param.is_optional
                # now add this param to the tool object
                tool_obj["function"]["parameters"]["properties"][param_name] = {
                    "type": typ,
                    "description": desc,
                }
                if not is_optional:
                    tool_obj["function"]["parameters"]["required"].append(param_name)

            all_tool_objs.append(tool_obj)

        return all_tool_objs

    def dispatch_intent(
        self,
        intent: FunctionCallIntent,
        message_thread: MessageThread,
        print_callback: Callable[[dict], None] | None = None,
    ) -> tuple[str, str, bool]:
        """Dispatch a function call intent to actually perform its action.

        Args:
            intent (FunctionCallIntent): The intent to dispatch.
            message_thread (MessageThread): the current message thread,
                since some tools require it.
        Returns:
            The result of the action.
            Also a summary that should be communicated to the model.
        """
        if (intent.func_name not in self.api_functions) and (
            intent.func_name != "get_class_full_snippet"
        ):
            error = f"Unknown function name {intent.func_name}."
            summary = "You called a tool that does not exist. Please only use the tools provided."
            return error, summary, False
        func_obj = getattr(self, intent.func_name)
        try:
            # ready to call a function
            self.curr_tool = intent.func_name
            if intent.func_name in ["write_doc"]:
                # these two functions require the message thread
                call_res = func_obj(message_thread, print_callback = print_callback)
            else:
                call_res = func_obj(**intent.arg_values)
        except Exception as e:
            # TypeError can happen when the function is called with wrong parameters
            # we just return the error message as the call result
            log_exception(e)
            error = str(e)
            summary = "The tool returned error message."
            call_res = (error, summary, False)

        logger.debug("Result of dispatch_intent: {}", call_res)

        # record this call and its result separately
        _, _, call_is_ok = call_res
        self.tool_call_sequence.append(intent.to_dict_with_result(call_is_ok))

        if not self.tool_call_layers:
            self.tool_call_layers.append([])
        self.tool_call_layers[-1].append(intent.to_dict_with_result(call_is_ok))

        return call_res

    def start_new_tool_call_layer(self):
        self.tool_call_layers.append([])

    def dump_tool_call_sequence_to_file(self):
        """Dump the sequence of tool calls to a file."""
        tool_call_file = pjoin(self.output_dir, "tool_call_sequence.json")
        with open(tool_call_file, "w") as f:
            json.dump(self.tool_call_sequence, f, indent=4)

    def dump_tool_call_layers_to_file(self):
        """Dump the layers of tool calls to a file."""
        tool_call_file = pjoin(self.output_dir, "tool_call_layers.json")
        with open(tool_call_file, "w") as f:
            json.dump(self.tool_call_layers, f, indent=4)

    ###################################################################
    ########################## API functions ##########################
    ###################################################################

    # not a search API - just to get full class definition when bug_location only specifies a class
    def get_class_full_snippet(self, class_name: str):
        return self.search_manager.get_class_full_snippet(class_name)

    def search_class(self, class_name: str) -> tuple[str, str, bool]:
        """Search for a class in the codebase.

        Only the signature of the class is returned. The class signature
        includes class name, base classes, and signatures for all of its methods/properties.

        Args:
            class_name (string): Name of the class to search for.

        Returns:
            string: the class signature in string if success;
                    an error message if the class cannot be found.
            string: a message summarizing the method.
        """
        return self.search_manager.search_class(class_name)

    def search_class_in_file(
        self, class_name: str, file_name: str
    ) -> tuple[str, str, bool]:
        """Search for a class in a given file.

        Returns the actual code of the entire class definition.

        Args:
            class_name (string): Name of the class to search for.
            file_name (string): The file to search in. Must be a valid python file name.

        Returns:
            part 1 - the searched class code or error message.
            part 2 - summary of the tool call.
        """
        return self.search_manager.search_class_in_file(class_name, file_name)

    def search_method_in_file(
        self, method_name: str, file_name: str
    ) -> tuple[str, str, bool]:
        """Search for a method in a given file.

        Returns the actual code of the method.

        Args:
            method_name (string): Name of the method to search for.
            file_name (string): The file to search in. Must be a valid python file name.

        Returns:
            part 1 - the searched code or error message.
            part 2 - summary of the tool call.
        """
        return self.search_manager.search_method_in_file(method_name, file_name)

    def search_method_in_class(
        self, method_name: str, class_name: str
    ) -> tuple[str, str, bool]:
        """Search for a method in a given class.

        Returns the actual code of the method.

        Args:
            method_name (string): Name of the method to search for.
            class_name (string): Consider only methods in this class.

        Returns:
            part 1 - the searched code or error message.
            part 2 - summary of the tool call.
        """
        return self.search_manager.search_method_in_class(method_name, class_name)

    def search_method(self, method_name: str) -> tuple[str, str, bool]:
        """Search for a method in the entire codebase.

        Returns the actual code of the method.

        Args:
            method_name (string): Name of the method to search for.

        Returns:
            part 1 - the searched code or error message.
            part 2 - summary of the tool call.
        """
        return self.search_manager.search_method(method_name)

    def search_code(self, code_str: str) -> tuple[str, str, bool]:
        """Search for a code snippet in the entire codebase.

        Returns the method that contains the code snippet, if it is found inside a file.
        Otherwise, returns the region of code surrounding it.

        Args:
            code_str (string): The code snippet to search for.

        Returns:
            The region of code containing the searched code string.
        """
        return self.search_manager.search_code(code_str)
    
    def extract_fullcode(
        self, file_path: str
    ) -> str:
        """Extract the entire code of a file.
        
        Returns the entire code of a file.
        
        Args:
            file_path (string): The file to extract the code from.
            
        Returns:
                The code of the file.
        """
        return self.search_manager.extract_fullcode(file_path)

    def search_code_in_file(
        self, code_str: str, file_name: str
    ) -> tuple[str, str, bool]:
        """Search for a code snippet in a given file file.

        Returns the entire method that contains the code snippet.

        Args:
            code_str (string): The code snippet to search for.
            file_name (string): The file to search in. Must be a valid python file name in the project.

        Returns:
            The method code that contains the searched code string.
        """
        return self.search_manager.search_code_in_file(code_str, file_name)
    
    def write_doc(
        self,
        message_thread: MessageThread,
        print_callback: Callable[[dict], None] | None = None,
    ) -> tuple[str, str, bool]:
        """Based on the current context, ask another agent to write a document.

        When you think the current information is sufficient to write a comprehence document, invoke this tool.

        The tool returns a document based on the current available information.
        """
        tool_output = agent_write_doc.run_with_retries(
            message_thread,
            self.output_dir,
            print_callback = print_callback,
        )
        summary = "The tool returned the patch written by another agent."
        # The return status of write_patch does not really matter, so we just use True here
        return tool_output, summary, True

    def proxy_apis(self, text: str) -> tuple[str | None, str, list[MessageThread]]:
        """Proxy APIs to another agent."""
        tool_output, new_thread = agent_proxy.run_with_retries(
            text
        )  # FIXME: type of `text`
        if tool_output is None:
            summary = "The tool returned nothing. The main agent probably did not provide enough clues."
        else:
            summary = "The tool returned the selected search APIs in json format generaetd by another agent."
        return tool_output, summary, new_thread

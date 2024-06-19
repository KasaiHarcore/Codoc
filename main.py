"""
The main driver.
"""

import os
import json
from argparse import ArgumentParser
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from itertools import chain
from os.path import abspath
from os.path import join as pjoin

from loguru import logger

from app import globals, globals_mut
from script import inference, log
from script import utils as apputils
from app.manage import ProjectApiManager
from app.model import common
from app.model.register import register_all_models
from script.doc_extracting import (
    get_final_doc_version,
)
from app.task.tasks import Github, RawTask, Local
from app.task.task_process import Task

from app.rag.chat import chat
from app.rag import util


def get_args(
    from_command_line_str: str = None, subparser_dest_attr_name: str = "command"
):
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest = subparser_dest_attr_name)

    github_parser = subparsers.add_parser(
        "github-code",
        help = "Run online github codebase",
    )
    set_github_parser_args(github_parser)
    
    chat_parser = subparsers.add_parser(
        "chat",
        help = "Run in chat mode."
    )
    set_chat_parser_args(chat_parser)

    local_parser = subparsers.add_parser(
        "local-code", 
        help = "Run on local codebase.")
    
    set_local_parser_args(local_parser)
    
    if not from_command_line_str:
        return parser.parse_args()
    return parser.parse_args(from_command_line_str.split())


def main(args, subparser_dest_attr_name: str = "command"):
    """
    Main function that handles different subcommands based on the value of `subparser_dest_attr_name`.

    Args:
        args: Command-line arguments passed to the script.
        subparser_dest_attr_name: Name of the attribute in `args` that determines the subcommand.

    Returns:
        None
    """

    ## common options
    globals.output_dir = args.output_dir
    if globals.output_dir is not None:
        globals.output_dir = abspath(globals.output_dir)
    num_processes: int = int(args.num_processes)
    # set whether brief or verbose log
    print_stdout: bool = not args.no_print
    log.print_stdout = print_stdout
    # model related
    common.set_model(args.model)
    # FIXME: make temperature part of the Model class
    common.MODEL_TEMP = args.model_temperature
    globals.conv_round_limit = args.conv_round_limit
    globals.enable_layered = args.enable_layered
    common.MODEL_CHUNK_OVERLAP = args.chunk_overlap
    common.MODEL_CHUNK_SIZE = args.chunk_size
    
    subcommand = getattr(args, subparser_dest_attr_name)
    if subcommand == "github-code":
        # Setup directory for GitHub task
        setup_dir = args.setup_dir
        if setup_dir is not None:
            setup_dir = abspath(setup_dir)
        else:
            os.makedirs(setup_dir)
            
        print("Setup location: ", setup_dir)

        # Create GitHub task
        task = Github(
            args.task_id,
            args.clone_link,
            args.commit_hash,
            repo_url=args.clone_link[:-4],
            setup_dir=setup_dir,
        )
        groups = {"github": [task]}
        
        run_task_groups(groups, num_processes)
        
    elif subcommand == "chat":
        print("Starting chat mode")
        util.ROOT_DIR = args.document_folder
        chat(args.model)
            
        
    # Work in progress
    elif subcommand == "local-code":
        # Local repository 
        local_repo = args.local_repo
        if local_repo is not None:
            local_repo = abspath(local_repo)
        code_folder = args.code_folder
        if issue_file is not None:
            issue_file = abspath(issue_file)
        
        # Create Local task
        task = Local(
            args.task_id,
            local_repo,
            issue_file,
        )
        groups = {"local": [task]}
        run_task_groups(groups, num_processes)
        
def set_github_parser_args(parser: ArgumentParser) -> None:
    add_task_related_args(parser)
    parser.add_argument(
        "--task-id",
        type=str,
        help="Assign an id to the current task.",
    )
    parser.add_argument(
        "--clone-link",
        type=str,
        help="The link to the repository to clone.",
    )
    parser.add_argument("--commit-hash", type = str, help = "The commit hash to checkout.")
    parser.add_argument(
        "--setup-dir",
        type=str,
        help="The directory where repositories should be cloned to.",
    )
    
def set_chat_parser_args(parser: ArgumentParser) -> None:
    add_task_related_args(parser)
    parser.add_argument(
        "--document-folder",
        type=str,
        help="The folder where the documents are stored.",
    )

def set_local_parser_args(parser: ArgumentParser) -> None:
    add_task_related_args(parser)
    parser.add_argument(
        "--task-id", type = str, help = "Assign an id to the current local code task."
    )
    parser.add_argument(
        "--local-repo", type = str, help = "Path to a local copy of the target repo."
    )
    parser.add_argument("--local-file", type = str, help = "Path to a local code file.")


def add_task_related_args(parser: ArgumentParser) -> None:
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Path to the directory that stores the run results.",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        default=False,
        help="Do not print most messages to stdout.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-3.5-turbo-0125",
        choices=list(common.MODEL_HUB.keys()),
        help="The model to use. Currently only OpenAI models are supported.",
    )
    parser.add_argument(
        "--model-temperature",
        type=float,
        default=0.0,
        help="The temperature for the model.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2056,
        help="The chunk size for the model.",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=256,
        help="The chunk overlap for the model.",
    )
    parser.add_argument(
        "--conv-round-limit",
        type=int,
        default=10,
        help="Conversation round limit for the main agent.",
    )
    parser.add_argument(
        "--enable-layered",
        action="store_true",
        default=True,
        help="Enable layered code search.",
    )
    parser.add_argument(
        "--num-processes",
        type=str,
        default=1,
        help="Number of processes to run the tasks in parallel.",
    )


def run_task_groups(
    task_groups: Mapping[str, Sequence[RawTask]],
    num_processes: int,
):
    """
    Main entry for running tasks.
    """
    all_tasks = list(chain.from_iterable(task_groups.values()))
    num_tasks = len(all_tasks)

    globals_mut.init_total_num_tasks(num_tasks)

    # print some info about task
    log.print_with_time(f"Total number of tasks: {num_tasks}")
    log.print_with_time(f"Total number of processes: {num_processes}")
    log.print_with_time(f"Task group info: (number of groups: {len(task_groups)})")
    for key, tasks in task_groups.items():
        log.print_with_time(f"\t{key}: {len(tasks)} tasks")

    # single process mode
    if num_processes == 1:
        log.print_with_time("Running in single process mode.")
        run_tasks_serial(all_tasks)
        log.print_with_time("Finished all tasks sequentially.")
    else:
        run_task_groups_parallel(task_groups, num_processes)


def run_tasks_serial(tasks: list[RawTask]) -> None:
    for task in tasks:
        run_task_in_subprocess(task)


def run_task_groups_parallel(
    task_groups: Mapping[str, Sequence[RawTask]],
    num_processes: int,
):
    num_task_groups = len(task_groups)
    globals_mut.init_total_num_task_groups(num_task_groups)
    num_processes = min(num_processes, num_task_groups)

    task_group_ids_items = sorted(
        task_groups.items(),
        key=lambda x: len(x[1]),
        reverse=True,
    )
    log.print_with_time(f"Sorted task groups: {[x[0] for x in task_group_ids_items]}")
    try:
        # Use ProcessPoolExecutor instead of multiprocessing.Pool,
        # to support nested sub-processing

        group_ids, group_tasks = zip(*task_group_ids_items)
        with ProcessPoolExecutor(num_processes) as executor:
            executor.map(run_task_group, group_ids, group_tasks)
    finally:
        log.print_with_time("Finishing all tasks in the pool.")


def run_task_group(task_group_id: str, task_group_items: list[RawTask]) -> None:
    """
    Run all tasks in a task group sequentially.
    Main entry to parallel processing.
    """
    log.print_with_time(
        f"Starting process for task group {task_group_id}. Number of tasks: {len(task_group_items)}."
    )
    for task in task_group_items:
        # within a group, the runs are always sequential
        run_task_in_subprocess(task)
        log.print_with_time(globals_mut.incre_task_return_msg())

    log.print_with_time(
        f"{globals_mut.incre_task_group_return_msg()} Finished task group {task_group_id}."
    )


def run_task_in_subprocess(task: RawTask) -> None:
    with ProcessPoolExecutor(max_workers=1) as executor:
        executor.submit(run_raw_task, task)


def run_raw_task(
    task: RawTask, print_callback: Callable[[dict], None] | None = None
) -> bool:
    """
    High-level entry for running one task.

    Args:
        - task: The Task instance to run.

    Returns:
        Whether the task completed successfully.
    """
    task_id = task.task_id

    start_time_s = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    task_output_dir = pjoin(globals.output_dir, f"{task_id}_{start_time_s}")
    apputils.create_dir_if_not_exists(task_output_dir)

    task.dump_meta_data(task_output_dir)

    log.log_and_always_print(
        f"============= Running task {task_id} =============",
    )

    run_ok = False

    try:
        run_ok = do_inference(task.to_task(), task_output_dir, args.setup_dir, print_callback)

        if run_ok:
            run_status_message = f"Task {task_id} completed successfully."
        else:
            run_status_message = f"Task {task_id} failed without exception."
    except Exception as e:
        logger.exception(e)
        run_status_message = f"Task {task_id} failed with exception: {e}."

    log.log_and_always_print(run_status_message)

    final_doc_path = get_final_doc_version(task_output_dir)
    if final_doc_path is not None:
        log.log_and_always_print(
            f"Please find the generated documents at: {final_doc_path}"
        )
    else:
        log.log_and_always_print("No documents generated. You can try again.")

    return run_ok


def do_inference(
    python_task: Task,
    task_output_dir: str,
    file_path: str,
    print_callback: Callable[[dict], None] | None = None,
) -> bool:

    apputils.create_dir_if_not_exists(task_output_dir)

    logger.add(
        pjoin(task_output_dir, "info.log"),
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level>"
            " | <level>{message}</level>"
        ),
    )

    start_time = datetime.now()

    api_manager = ProjectApiManager(python_task, task_output_dir)

    try:
        run_ok = inference.run_one_task(
            api_manager.output_dir,
            api_manager,
            python_task.get_description(),
            file_path,
            print_callback = print_callback,
        )

        api_manager.dump_tool_call_sequence_to_file()
        api_manager.dump_tool_call_layers_to_file()

        end_time = datetime.now()

        dump_cost(start_time, end_time, task_output_dir)
    finally:
        python_task.reset_project()

    return run_ok


def dump_cost(
    start_time: datetime,
    end_time: datetime,
    task_output_dir: str,
):
    model_stats = common.SELECTED_MODEL.get_overall_exec_stats()
    stats = {
        "commit": apputils.get_current_commit_hash(),
        "start_epoch": start_time.timestamp(),
        "end_epoch": end_time.timestamp(),
        "elapsed_seconds": (end_time - start_time).total_seconds(),
    }
    stats.update(model_stats)

    with open(pjoin(task_output_dir, "cost.json"), "w") as f:
        json.dump(stats, f, indent=4)


if __name__ == "__main__":
    logger.remove()
    register_all_models()
    args = get_args()
    main(args)
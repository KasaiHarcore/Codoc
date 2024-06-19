"""
Post-process the output of the inference workflow.
"""

import json
import os
import shutil
import subprocess
from enum import Enum
from glob import glob
from os.path import join as pjoin
from shutil import move

from script import utils as apputils
from api.doc_utils import parse_document_changes, apply_document_changes


def count_and_organize_tasks(
    task_list: list[str], task_list_name: str, task_exp_names: list[str], expr_dir: str
):
    """
    Generate a message to log the number of tasks in one list.
    Also organizes tasks in this list to a new folder in the experiment directory.

    Args:
        - task_list: a list of task ids
        - task_list_name: name for this list (one of the four categories)
        - task_exp_names: list of individual experiment result dir names
        - expr_dir: the overall experiment directory.

    Returns:
        - message, a string message to be written to log file.
    """
    total_num_tasks = len(task_exp_names)

    # (1) get the message ready
    message = f"Total number of tasks in {task_list_name}: {len(task_list)}/{total_num_tasks}.\n"
    for task in task_list:
        message += f"\t {task}\n"

    # (2) create a new dir and move the experiment results of these tasks there
    new_dir = pjoin(expr_dir, task_list_name)
    os.makedirs(new_dir, exist_ok=True)
    for task_exp_name in task_exp_names:
        if any([task_exp_name.startswith(x) for x in task_list]):
            # this expr dir belongs to a task in the list
            old_dir = pjoin(expr_dir, task_exp_name)
            shutil.move(old_dir, new_dir)

    return message


# track generate of document
class ExtractDoc(str, Enum):
    """
    Enumeration class representing different statuses related to document extraction.
    
    The `ExtractDoc` class defines a set of string constants representing different statuses that can occur during the document extraction process. These statuses are used to indicate the outcome of the extraction, such as whether the document is valid JSON, whether a raw document was generated, or whether there were any issues with the code matching or the origin data.
    
    The class also provides utility methods for working with these statuses, such as comparing them, hashing them, and generating directory names based on the status.
    """
    """
    Defines an enumeration of status codes for document extraction operations.
    
    The `ExtractDoc` enum represents the different statuses that can occur during the
    document extraction process. Each status code has a corresponding string value
    that can be used to identify the status.
    
    The enum also provides utility methods for working with the status codes, such
    as comparing them, hashing them, and generating directory names based on the
    status.
    """
    NO_DOCS = "NO_DOCS"
    IS_VALID_JSON = "IS_VALID_JSON"
    RAW_DOC_GENERATED = "RAW_DOC_GENERATED"
    NOT_VALID_JSON = "NOT_VALID_JSON"
    MATCHED_BUT_EMPTY_ORIGIN = "MATCHED_BUT_EMPTY_ORIGIN"
    MATCHED_BUT_EMPTY_DIFF = "MATCHED_BUT_EMPTY_DIFF"
    RAW_DOCS_BUT_UNMATCHED = "RAW_DOCS_BUT_UNMATCHED"
    RAW_DOCS_BUT_UNPARSED = "RAW_DOCS_BUT_UNPARSED"
    FINISHED = "FINISHED"
    

    def __lt__(self, other):
        order = [
            self.NO_DOCS,
            self.RAW_DOC_GENERATED,
            self.RAW_DOCS_BUT_UNPARSED,
            self.RAW_DOCS_BUT_UNMATCHED,
            self.MATCHED_BUT_EMPTY_ORIGIN,
            self.MATCHED_BUT_EMPTY_DIFF,
        ]
        self_index = order.index(self)
        other_index = order.index(other)
        return self_index < other_index

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return hash(self.value)

    def to_dir_name(self, expr_dir: str):
        return pjoin(expr_dir, self.value.lower())

    @staticmethod
    def max(statuses):
        return sorted(statuses)[-1]


def record_extract_doc(individual_expr_dir: str, extract_doc: ExtractDoc):
    """
    Record the document extraction status into a file.
    """
    record_file = pjoin(individual_expr_dir, "extract_doc.json")
    try:
        with open(record_file, "r") as f:
            record = json.load(f)
    except FileNotFoundError:
        record = {"extract_doc": []}  # If the file does not exist, create a new one

    record["extract_doc"].append(extract_doc.value)
    with open(record_file, "w") as f:
        json.dump(record, f, indent=4)


def read_extract_doc(individual_expr_dir: str) -> tuple[ExtractDoc | None, int]:
    """
    Read the document extraction status from the file. Return the best status and its index.
    """
    record_file = pjoin(individual_expr_dir, "extract_doc.json")
    try:
        with open(record_file) as f:
            record = json.load(f)
            all_doc = [ExtractDoc(s) for s in record["extract_doc"]]
            best_doc = ExtractDoc.max(all_doc)
            best_idx = all_doc.index(best_doc)
            return best_doc, best_idx
    except FileNotFoundError:
        return None, -1  # File not found, return None


def get_final_doc_version(individual_expr_dir: str) -> str | None:
    """
    Get the final version from the experiment directory.
    """
    best_doc, best_index = read_extract_doc(individual_expr_dir)
    if best_doc is None or best_doc != ExtractDoc.FINISHED:
        return None  # Did not find the 'FINISHED' status

    best_patch_name = f"extracted_patch_{best_index + 1}.diff"
    final_patch_path = pjoin(individual_expr_dir, best_patch_name)
    return final_patch_path if os.path.isfile(final_patch_path) else None


def check_doc_gen(raw_doc_file: str) -> tuple[ExtractDoc, str]:
    """
    Check whether the document has been created and return the extraction status.
    """
    task_dir = os.path.dirname(raw_doc_file)
    meta_file = pjoin(task_dir, "meta.json")
    with open(meta_file) as f:
        meta = json.load(f)

    if not os.path.isfile(raw_doc_file):
        return ExtractDoc.NO_DOCS, "No file is found."

    with open(raw_doc_file) as f:
        doc_content = f.read()

    try:
        parse_document_changes(doc_content)
        status, message = ExtractDoc.FINISHED, ""
    except Exception as e:
        status, message = ExtractDoc.RAW_DOC_GENERATED, f"Exception {e} happened when parsing edits."
    return status, message

def extract_document_changes(
    raw_document_file: str, extracted_file: str, standalone_mode: bool = False
) -> tuple[ExtractDoc, str]:
    """
    Extract changes made to a document instance.
    Args:
        - raw_document_file: Path to the raw document file produced by model.
        - extracted_file: Path where the extracted changes file goes.
        - standalone_mode: If True, the function is called from the special --extract-changes mode.
                           Specify this to True if using this function as it is for testing.
    Returns:
        - ExtractDoc.
        - An additional string containing more explanation on how document changes extraction failed.
          If everything is successful, this string is empty.
    """
    # (1) get the meta data for this task
    task_dir = os.path.dirname(raw_document_file)
    meta_file = pjoin(task_dir, "meta.json")
    with open(meta_file) as f:
        meta = json.load(f)
    task_info = meta["task_info"]
    setup_info = meta["setup_info"]
    repo_path = setup_info["repo_path"]  # the project dir
    base_commit = task_info["base_commit"]  # the commit to checkout
    if not os.path.isfile(raw_document_file):
        return ExtractDoc.NO_DOCS, "No raw document file is found."
    with open(raw_document_file) as f:
        content = f.read()
    # (2) try parsing the edits
    try:
        edits = parse_document_changes(content)
    except Exception as e:
        return (
            ExtractDoc.RAW_DOCS_BUT_UNPARSED,
            f"Exception {e} happend when parsing edits.",
        )
    if not edits:
        return ExtractDoc.RAW_DOCS_BUT_UNPARSED, "No edits can be parsed."
    # (3) edit parsed. check whether it can match the original document
    with apputils.cd(repo_path):
        if standalone_mode:
            # in special --extract-doc mode
            apputils.repo_reset_and_clean_checkout(base_commit)
        else:
            # extracting patch in the write_patch loop
            # we should not reset to base commit, because previous we created a new commit
            # containing the test_patch content. We should just clean the changes until HEAD.
            apputils.repo_clean_changes()
        # try to match and apply each edit
        unmatched_edit_indexes = []
        for idx, edit in enumerate(edits):
            # NOTE: do not clean here, since we want to accumulate changes from all edits
            target_file = edit.filename
            # find the target file. The model may only use the short name of the file,
            # so we need to search for it here
            found_file = apputils.find_file(repo_path, target_file)
            if found_file is None:
                unmatched_edit_indexes.append(idx)
                continue
            # try to apply this edit and update the actual file content
            applied_file = apply_document_changes(edit, found_file)
            if applied_file is None:
                unmatched_edit_indexes.append(idx)
                continue
        if len(unmatched_edit_indexes) == len(edits):
            # non of the edits can be matched
            # there is obvious error, and we definitely cannot extract patch
            apputils.repo_clean_changes()
            return (
                ExtractDoc.RAW_DOCS_BUT_UNMATCHED,
                "None of the edits can match the original document.",
            )
        # let's have a message describing which edits can be matched
        if unmatched_edit_indexes:
            unmatched_msg = f"Edits number {','.join([str(x+1) for x in unmatched_edit_indexes])} cannot be matched to the original document. "
        else:
            unmatched_msg = ""
        # at this point, at least some of the edits could be applied (some others may be unmatched)
        # we first try to get the diff
        diff = apputils.run_command(
            ["git", "diff"], stdout=subprocess.PIPE
        ).stdout.decode()
        # After extracting diff, we have nothing more to do in the actual code base
        apputils.repo_clean_changes()
        if not diff:
            # diff file is empty, meaning the patched document is the same as original
            # effectively, there is no edits that matched and introduced a real diff
            msg = (
                unmatched_msg
                + "The matched edits do not introduce any change to the document."
            )
            return ExtractDoc.MATCHED_BUT_EMPTY_DIFF, msg
        edits_with_empty_before = [
            str(idx + 1) for idx, edit in enumerate(edits) if not edit.before.strip()
        ]
        if edits_with_empty_before:
            numbers = ", ".join(edits_with_empty_before)
            msg = f"Please contain **non-whitespace** original document snippet in edits number {numbers}."
            return ExtractDoc.MATCHED_BUT_EMPTY_ORIGIN, msg
        # the edits resulted in a non-empty diff. We should at least save and return it
        with open(extracted_file, "w") as f:
            f.write(diff)
        # if all edits are matched, the `unmatched_msg` is empty string
        return ExtractDoc.FINISHED, unmatched_msg


def is_valid_json(json_str: str) -> tuple[ExtractDoc, list | dict | None]:
    """
    Check whether a json string is valid.
    """
    try:
        data = json.loads(json_str)
    except json.decoder.JSONDecodeError:
        return ExtractDoc.NOT_VALID_JSON, None
    return ExtractDoc.IS_VALID_JSON, data


"""
Main entries of the module.
"""

def un_classify_expr_dir(expr_dir: str):
    individual_expr_dirs = []
    for individual_expr_dir in glob(pjoin(expr_dir, "*", "*__*")):
        assert "info.log" in os.listdir(
            individual_expr_dir
        ), f"{individual_expr_dir} has no info.log"
        individual_expr_dirs.append(individual_expr_dir)

    for d in individual_expr_dirs:
        move(d, expr_dir)

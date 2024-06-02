"""
Post-process the output of the inference workflow.
"""

import json
import os
import shutil
from collections import defaultdict
from collections.abc import Mapping
from enum import Enum
from glob import glob
from os.path import join as pjoin
from shutil import move

from api.doc_utils import parse_edits


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
    NO_DOCS = "NO_PATCH"
    IS_VALID_JSON = "IS_VALID_JSON"
    RAW_DOC_GENERATED = "RAW_DOC_GENERATED"
    NOT_VALID_JSON = "NOT_VALID_JSON"
    CODE_MATCHED_BUT_EMPTY_DIFF = "CODE_MATCHED_BUT_EMPTY_DIFF"
    CODE_MATCHED_BUT_EMPTY_ORIGIN = "CODE_MATCHED_BUT_EMPTY_ORIGIN"
    # APPLICABLE_CODE = "APPLICABLE_CODE"
    FINISHED = "FINISHED"
    

    def __lt__(self, other):
        order = [
            self.NO_DOCS,
            self.RAW_DOC_GENERATED,
            self.CODE_MATCHED_BUT_EMPTY_DIFF,
            self.CODE_MATCHED_BUT_EMPTY_ORIGIN,
            # self.APPLICABLE_CODE,
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
    Ghi lại trạng thái trích xuất tài liệu vào tệp.
    """
    record_file = pjoin(individual_expr_dir, "extract_doc.json")
    try:
        with open(record_file, "r") as f:
            record = json.load(f)
    except FileNotFoundError:
        record = {"extract_doc": []}  # Nếu tệp chưa tồn tại, tạo mới

    record["extract_doc"].append(extract_doc.value)
    with open(record_file, "w") as f:
        json.dump(record, f, indent=4)


def read_extract_doc(individual_expr_dir: str) -> tuple[ExtractDoc | None, int]:
    """
    Đọc trạng thái trích xuất tài liệu từ tệp. Trả về trạng thái tốt nhất và chỉ số của nó.
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
        return None, -1  # Không tìm thấy tệp, trả về None


def get_final_doc_version(individual_expr_dir: str) -> str | None:
    """
    Lấy phiên bản cuối cùng từ thư mục thí nghiệm.
    """
    best_doc, best_index = read_extract_doc(individual_expr_dir)
    if best_doc is None or best_doc != ExtractDoc.FINISHED:
        return None  # Không tìm thấy trạng thái "FINISHED"

    best_patch_name = f"extracted_patch_{best_index + 1}.diff"
    final_patch_path = pjoin(individual_expr_dir, best_patch_name)
    return final_patch_path if os.path.isfile(final_patch_path) else None


def check_doc_gen(raw_doc_file: str) -> tuple[ExtractDoc, str]:
    """
    Kiểm tra xem tài liệu đã được tạo hay chưa và trả về trạng thái trích xuất.
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
        parse_edits(doc_content)
        status, message = ExtractDoc.FINISHED, ""
    except Exception as e:
        status, message = ExtractDoc.RAW_DOC_GENERATED, f"Exception {e} happened when parsing edits."
    return status, message


def organize_experiment_results(expr_dir: str):
    """
    Giả sử các bản tài liệu đã được giải nén, hãy sắp xếp kết quả thử nghiệm
    thư mục thành một vài danh mục và di chuyển chúng đến đó.
    """
    # (1) tìm tất cả các thư mục thử nghiệm nhiệm vụ
    task_exp_names = [
        x
        for x in os.listdir(expr_dir)
        if os.path.isdir(pjoin(expr_dir, x))
        and "__" in x  # để lọc các thư mục khác như "applicable_doc"
    ]
    task_exp_dirs = [pjoin(expr_dir, x) for x in task_exp_names]

    # start organizing
    for extract_doc in ExtractDoc:
        os.makedirs(extract_doc.to_dir_name(expr_dir), exist_ok=True)

    for task_dir in task_exp_dirs:
        extract_doc, _ = read_extract_doc(task_dir)
        corresponding_dir = extract_doc.to_dir_name(expr_dir)
        shutil.move(task_dir, corresponding_dir)


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

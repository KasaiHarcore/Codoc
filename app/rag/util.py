import os
from git import Repo
import traceback

from langchain_community.vectorstores import FAISS

from app.globals import LOADER_MAPPING, EXCLUDE_FILES

ROOT_DIR = ""

def get_repo():
    """
    Get the git repository.

    Returns:
        The git repository.
    """
    try:
        return Repo(ROOT_DIR)
    except:
        return None

def load_files():
    """
    Load files from the repository.

    Returns:
        A list of loaded files.
    """
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(path, ROOT_DIR)  # Get the relative path
            if any(rel_path.endswith(exclude_file) for exclude_file in EXCLUDE_FILES):
                continue
            for ext in LOADER_MAPPING:
                if path.endswith(ext):
                    print(f'Loading files: {path}')  # Print full path for debugging
                    args = LOADER_MAPPING[ext]['args']
                    loader = LOADER_MAPPING[ext]['loader'](path, *args)
                    try:
                        files.extend(loader.load())
                    except Exception as e:
                        print(f"Error loading {path}: {e}")
                        print(traceback.format_exc())
    return files

def get_local_vector_store(embeddings, path):
    try:
        return FAISS.load_local(path, embeddings)
    except:
        return None
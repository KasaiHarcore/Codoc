import json
import os
import shutil
from abc import ABC, abstractmethod

from os.path import join as pjoin
from pathlib import Path

import requests

from app.task.task_process import PlainTask, Task
from script import utils as app_utils
from script.log import log_and_print

# Define abstract base class for raw tasks
class RawTask(ABC):
    @property
    @abstractmethod
    def task_id(self) -> str:
        raise NotImplementedError("abstract base class")

    @abstractmethod
    def to_task(self) -> Task:
        raise NotImplementedError("abstract base class")
    
    @abstractmethod
    def dump_meta_data(self, output_dir: str) -> None:
        raise NotImplementedError("abstract base class")

# Open-source repository
class Github(RawTask): # Github class is a subclass of RawTask
    def __init__(
        self,
        task_id: str,
        clone_link: str,
        commit_hash: str,
        repo_url: str,
        setup_dir: str,
    ):
        self._task_id = task_id
        self.clone_link = clone_link
        self.commit_hash = commit_hash
        self.clone_link, self.commit_hash, _ = self.fetch_github_repo(repo_url)
        self.setup_dir = setup_dir
        self.clone_path = pjoin(self.setup_dir, self.task_id)
        self.readme = None
        self.clone_repo()

    @property
    def task_id(self) -> str:
        return self._task_id

    def clone_repo(self):
        clone_path = Path(self.clone_path)
        if os.path.exists(clone_path):
            log_and_print(
                f"Path {clone_path} already exists. Removing to get a fresh clone."
            )
            shutil.rmtree(clone_path)
        app_utils.clone_repo(self.clone_link, str(clone_path.parent), clone_path.name)
        log_and_print(f"Cloned source code to {clone_path}.")

    def dump_meta_data(self, output_dir: str):
        meta = {
            "task_info": {
                "base_commit": self.commit_hash,
                "description": self.readme,
                "instance_id": self.task_id,
            },
            "setup_info": {
                "repo_path": self.clone_path,
            },
        }

        meta_file = pjoin(output_dir, "meta.json")

        with open(meta_file, "w") as f:
            json.dump(meta, f, indent = 4)

    @classmethod
    def fetch_github_repo(cls, repo_url: str) -> tuple[str, str, str]:
        """Extract infomation from URL"""

        # Example issue URL: https://github.com/owner/repo/

        _, owner, repo = repo_url.rstrip('/').rsplit('/', 2)

        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url)

        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch github repo: {response.status_code}"
            )

        repo_info = response.json()
        clone_url = repo_info['clone_url']
        default_branch = repo_info['default_branch']

        # Fetch the latest commit hash from the default branch
        commits_api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}"
        commits_response = requests.get(commits_api_url)

        if commits_response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch commits: {commits_response.status_code}"
            )

        commit_info = commits_response.json()
        commit_hash = commit_info['sha']

        return clone_url, commit_hash, default_branch

    def to_task(self) -> PlainTask:
        self.readme = app_utils.read_readme_file(self.clone_path)
        return PlainTask(
            commit_hash = self.commit_hash,
            local_path = self.clone_path,
            description = self.readme,
        )
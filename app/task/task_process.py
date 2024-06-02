from abc import ABC, abstractmethod
import script.utils as apputils

class Task(ABC):
    @property
    @abstractmethod
    def project_path(self) -> str:
        raise NotImplementedError("abstract method")

    @abstractmethod
    def get_description(self) -> str:
        raise NotImplementedError("abstract method")

    @abstractmethod
    def setup_project(self) -> None:
        """Set up the project before starting to resolve the task."""
        raise NotImplementedError("abstract method")

    @abstractmethod
    def reset_project(self) -> None:
        """Reset project to initial state."""
        raise NotImplementedError("abstract method")
    
class PlainTask(Task):
    """
    Tasks that only contain a codebase and an readme file (no test suite).
    """

    def __init__(self, commit_hash: str, local_path: str, description: str):
        self.commit_hash = commit_hash
        self.local_path = local_path
        self.description = description

    @property
    def project_path(self) -> str:
        return self.local_path

    def setup_project(self) -> None:
        with apputils.cd(self.project_path):
            apputils.repo_reset_and_clean_checkout(self.commit_hash)
            
    def reset_project(self) -> None:
        with apputils.cd(self.project_path):
            apputils.repo_reset_and_clean_checkout(self.commit_hash)
            
    def get_description(self) -> str:
        return self.description

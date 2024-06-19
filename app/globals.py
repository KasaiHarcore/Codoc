"""
Values of global configuration variables.
"""
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredEPubLoader, CSVLoader, PDFMinerLoader, UnstructuredMarkdownLoader, TextLoader

# Overall output directory for results
output_dir: str = ""

# upper bound of the number of conversation rounds for the agent
conv_round_limit: int = 15

# whether to perform layered search
enable_layered: bool = True

# timeout for test cmd execution, currently set to 5 min
test_exec_timeout: int = 300

# Folder can be skipped during the search
EXCLUDE_DIRS = ['__pycache__', '.venv', '.git', '.idea', 'venv', 'env', 'node_modules', 'dist', 'build', '.vscode',
                '.github', '.gitlab']

# File extensions that can be searched
ALLOW_FILES = ['.txt', '.js', '.mjs', '.ts', '.tsx', '.css', '.scss', '.less', '.html', '.htm', '.json', '.py',
               '.java', '.c', '.cpp', '.cs', '.go', '.php', '.rb', '.rs', '.swift', '.kt', '.scala', '.m', '.h',
               '.sh', '.pl', '.pm','.lua', '.sql']

# File extensions that should be excluded from search
EXCLUDE_FILES = ['requirements.txt', 'package.json', 'package-lock.json', 'yarn.lock', '__init__.py']

# Loader mapping
LOADER_MAPPING = {
    ".csv": {
        "loader": CSVLoader,
        "args": {}
    },
    ".doc": {
        "loader": UnstructuredWordDocumentLoader,
        "args": {}
    },
    ".docx": {
        "loader": UnstructuredWordDocumentLoader,
        "args": {}
    },
    ".epub": {
        "loader": UnstructuredEPubLoader,
        "args": {}
    },
    ".md": {
        "loader": UnstructuredMarkdownLoader,
        "args": {}
    },
    ".pdf": {
        "loader": PDFMinerLoader,
        "args": {}
    }
}

for ext in ALLOW_FILES:
    if ext not in LOADER_MAPPING:
        LOADER_MAPPING[ext] = {
            "loader": TextLoader,
            "args": {}
        }
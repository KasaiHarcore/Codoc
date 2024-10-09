"""
Values of global configuration variables.
"""
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, UnstructuredEPubLoader, CSVLoader, PDFMinerLoader, UnstructuredMarkdownLoader, TextLoader

# Overall output directory for results
output_dir: str = ""

# upper bound of the number of conversation rounds for the agent
conv_round_limit: int = 50

# whether to perform layered search
enable_layered: bool = True

# timeout for test cmd execution, currently set to 5 min
test_exec_timeout: int = 300

# Folder can be skipped during the search
EXCLUDE_DIRS = ['__pycache__', '.venv', '.git', '.idea', 'venv', 'env', 'node_modules', 'dist', 'build', '.vscode',
                '.github', '.gitlab', 'CHANGELOG', 'changelog', 'docs', 'doc', 'test', 'tests', 'example', 'examples', 'docker',
                'version', 'versions', 'pynixify', 'www'
            ]

# File extensions that can be searched
ALLOW_FILES = ['.txt', '.js', '.mjs', '.ts', '.tsx', '.css', '.scss', '.less', '.html', '.htm', '.json', '.py',
               '.java', '.c', '.cpp', '.cs', '.go', '.php', '.rb', '.rs', '.swift', '.kt', '.scala', '.m', '.h',
               '.sh', '.pl', '.pm','.lua', '.sql',
                
                # Example of other file extensions that can be used
                # # Compiled executables and libraries
                # '.exe', '.dll', '.so', '.a', '.lib', '.dylib', '.o', '.obj',
                # # Compressed archives
                # '.zip', '.tar', '.tar.gz', '.tgz', '.rar', '.7z', '.bz2', '.gz', '.xz', '.z', '.lz', '.lzma', '.lzo', '.rz', '.sz', '.dz',
                # # Application-specific files
                # '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp',
                # # Media files (less common)
                # '.png', '.jpg', '.jpeg', '.gif', '.mp3', '.mp4', '.wav', '.flac', '.ogg', '.avi', '.mkv', '.mov', '.webm', '.wmv', '.m4a', '.aac',
                # # Virtual machine and container images
                # '.iso', '.vmdk', '.qcow2', '.vdi', '.vhd', '.vhdx', '.ova', '.ovf',
                # # Database files
                # '.db', '.sqlite', '.mdb', '.accdb', '.frm', '.ibd', '.dbf',
                # # Java-related files
                # '.jar', '.class', '.war', '.ear', '.jpi',
                # # Python bytecode and packages
                # '.pyc', '.pyo', '.pyd', '.egg', '.whl',
                # # Other potentially important extensions
                # '.deb', '.rpm', '.apk', '.msi', '.dmg', '.pkg', '.bin', '.dat', '.data',
                # '.dump', '.img', '.toast', '.vcd', '.crx', '.xpi', '.lockb', 'package-lock.json', '.svg' ,
                # '.eot', '.otf', '.ttf', '.woff', '.woff2',
                # '.ico', '.icns', '.cur',
                # '.cab', '.dmp', '.msp', '.msm',
                # '.keystore', '.jks', '.truststore', '.cer', '.crt', '.der', '.p7b', '.p7c', '.p12', '.pfx', '.pem', '.csr',
                # '.key', '.pub', '.sig', '.pgp', '.gpg',
                # '.nupkg', '.snupkg', '.appx', '.msix', '.msp', '.msu',
                # '.deb', '.rpm', '.snap', '.flatpak', '.appimage',
                # '.ko', '.sys', '.elf',
                # '.swf', '.fla', '.swc',
                # '.rlib', '.pdb', '.idb', '.pdb', '.dbg',
                # '.sdf', '.bak', '.tmp', '.temp', '.log', '.tlog', '.ilk',
                # '.bpl', '.dcu', '.dcp', '.dcpil', '.drc',
                # '.aps', '.res', '.rsrc', '.rc', '.resx',
                # '.prefs', '.properties', '.ini', '.cfg', '.config', '.conf',
                # '.DS_Store', '.localized', '.svn', '.git', '.gitignore', '.gitkeep'
                ]

# File extensions that should be excluded from search
EXCLUDE_FILES = [
        'requirements.txt', 'package.json', 'package-lock.json', 'yarn.lock', '__init__.py', 'Dockerfile', 'docker-compose.yml'
    ]

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
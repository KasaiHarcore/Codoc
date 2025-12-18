# Codoc

Generate human-readable documentation from a codebase (GitHub repo) using an agentic workflow.

This repo supports two primary modes:

- **`github-code`**: clone a GitHub repository (optionally checkout a commit) and generate docs into an `outputs/` run folder.
- **`chat`**: lightweight RAG chat over a local folder using a FAISS vector store.

## Requirements

- Python 3.9.xx recommended

Install dependencies:

~~~bash
pip install -r requirements.txt
~~~

## Configuration

Set provider API keys depending on the model you use:

- **Groq**: `GROQ_API_KEY`
- **OpenAI**: `OPENAI_API_KEY`
- Same for other

Example:

~~~bash
export GROQ_API_KEY="..."
export OPENAI_API_KEY="..."
~~~

## Usage

### 1) Generate docs from a GitHub repo

~~~bash
python3 main.py github-code \
	--task-id mytask \
	--clone-link https://github.com/<owner>/<repo>.git \
	--commit-hash <optional_commit_hash> \
	--setup-dir ./setup_dirs \
	--output-dir ./outputs \
	--model groq/openai/gpt-oss-120b
~~~

Notes:

- `--setup-dir` is where repositories are cloned.
- `--output-dir` is where run artifacts are written.
- `--model` must be one of the entries in the model hub (`app/model/common.py`).

### 2) Chat with RAG over a local folder

Point `--document-folder` at a local project folder. The first run builds a FAISS vector store at:

`<document-folder>/vector_store/<model_name>/`

~~~bash
python3 main.py chat \
	--document-folder /path/to/your/docs/folder \
	--model groq/openai/gpt-oss-120b
~~~

Type your question and press Enter. Use `exit` / `quit` to stop.

## Output structure

Each run creates a timestamped folder under `--output-dir`:

~~~text
outputs/
	<task_id>_<YYYY-MM-DD_HH-MM-SS>/
		info.log
		cost.json
		tool_call_sequence.json
		agent_doc_raw_*.md
		...
~~~

If docs look empty or off-format, check `tool_call_sequence.json` first (it shows whether code extraction/search tools succeeded).

## What files are indexed in RAG?

RAG indexing uses file loader mapping and exclusions from [app/globals.py](app/globals.py):

- `ALLOW_FILES` and `LOADER_MAPPING` decide which file types can be loaded.
- `EXCLUDE_DIRS` and `EXCLUDE_FILES` skip common noise (virtualenvs, git folders, lockfiles, etc).

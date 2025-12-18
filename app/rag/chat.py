import sys

from app.rag.retrieval import LiteLLM
from app.rag.util import get_root_dir

from script.log import print_chat, print_user

def chat_loop(llm):
    while True:
        query = input("User: ").strip()
        print_user(query)
        if not query:
            print_chat("Please enter a query")
            continue
        if query in ('exit', 'quit'):
            break
        llm.send_query(query)

def chat(model_name: str):
    root_dir = get_root_dir()
    if not root_dir:
        print("Missing document folder. Please provide --document-folder.")
        sys.exit(1)

    try:
        llm = LiteLLM(model_name, root_dir=root_dir)
    except Exception as e:
        print(f"Failed to initialize RAG: {e}")
        sys.exit(1)

    chat_loop(llm)
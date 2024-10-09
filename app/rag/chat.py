import sys

from app.rag.retrieval import LiteLLM
from app.rag.util import get_repo

from script.log import print_chat, print_user

def chat_loop(llm):
    while True:
        query = input("User: ").lower().strip()
        print_user(query)
        if not query:
            print_chat("Please enter a query")
            continue
        if query in ('exit', 'quit'):
            break
        llm.send_query(query)

def chat(model_name: str):
    repo = get_repo()
    
    if not repo:
        print("Git repository not found, for now we only support github repo")
        sys.exit(1)
        
    if model_name.startswith("groq"):
        llm = LiteLLM(model_name)
        chat_loop(llm)
    else:
        print("Only support groq model for now")
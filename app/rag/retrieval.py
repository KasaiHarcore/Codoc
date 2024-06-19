import os
import warnings
import sys
import time
from halo import Halo
from typing import Optional
from abc import ABC, abstractmethod

from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_community.chat_models import ChatLiteLLM
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_core.vectorstores import VectorStoreRetriever
from langchain.memory import ConversationSummaryMemory
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.util import get_local_vector_store, load_files, ROOT_DIR
from script.log import log_and_print, print_chat
from app.model import common

warnings.filterwarnings("ignore")

PROMPT_TEMPLATE = "{context}<|im_start|>system\nYou are a seasoned software developer with extensive experience in various engineering positions within the technology sector, particularly in maintaining large projects.\n \
                You are working on an open-source project with multiple contributors, and there is no comprehensive documentation available.\n \
                Your task is to use all the information available to guide a junior developer through the project.<|im_end|> \n\n\
                <|im_start|> User: \n{question}"


class BaseRetrieval(ABC):
    def __init__(self):
        self.llm = self._create_model()
        self.root_dir = ROOT_DIR
        self.vector_store = self._create_store(ROOT_DIR)
    
    @abstractmethod
    def _create_store(self, root_dir: str) -> Optional[FAISS]:
        raise NotImplementedError("abstract method")
    
    @abstractmethod
    def _create_model(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def _create_vector_store(self, embeddings, model, root_dir):
        """
        Create a vector store.
        """
        k = 3
        index_path = os.path.join(root_dir, f"vector_store/{model}")
        new_db = get_local_vector_store(embeddings, index_path)
        if new_db is not None:
            return new_db.as_retriever(search_kwargs = {"k": k})

        try:
            docs = load_files()
        except Exception as e:
            log_and_print(f"An error has occur: {e}")
            sys.exit(1)
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size = int(common.MODEL_CHUNK_SIZE),
                                                        chunk_overlap = int(common.MODEL_CHUNK_OVERLAP),
                                                        length_function=len,
                                                        separators=[
                                                        "\n\n",
                                                        "\n",
                                                        " ",
                                                        ".",
                                                        ",",
                                                        "\u200B",  # Zero-width space
                                                        "\uff0c",  # Fullwidth comma
                                                        "\u3001",  # Ideographic comma
                                                        "\uff0e",  # Fullwidth full stop
                                                        "\u3002",  # Ideographic full stop
                                                        "",]
                                                    )
        
        texts = text_splitter.split_documents(docs)
        

        print("Creating vector store")
        spinners = Halo(text = f"Creating vector store", spinner = 'bouncingBar').start()
        db = FAISS.from_documents([texts[0]], embeddings)
        
        for i, text in enumerate(texts[1:]):
            spinners.text = f"Creating vector store ({i + 1}/{len(texts)})"
            db.add_documents([text])
            db.save_local(index_path)
            time.sleep(1.5)

        spinners.succeed("Vector store created")
        
        return db
    
    def prompt_gen(self, template):
        return PromptTemplate(
            template = template,
            max_tokens = 4096,
            temperature = 0.01,
            top_p = 0.95,
            frequency_penalty = 0.0, 
            presence_penalty = 0.0, 
            stop_sequences = ["\n"],
            input_variables = ["question"],
            return_only_outputs = False
        )

    def send_query(self, query):
        # For more model options, see: https://litellm.vercel.app/docs/providers
        # Make sure to set the correct model name and API key
        pt = self.prompt_gen(template = PROMPT_TEMPLATE)
        qa = RetrievalQA.from_chain_type(
            llm = self.llm,
            chain_type = "stuff",
            retriever = VectorStoreRetriever(vectorstore = self.vector_store),
            memory = ConversationSummaryMemory(llm = self.llm, output_key="result"),  # Set 'output_key' explicitly
            chain_type_kwargs = {"prompt": pt, "verbose": True},
            return_source_documents = True
        )
        docs = qa.invoke(query)
        docs_str = f"Query: {docs['query']}\n\nResult: {docs['result']}\n\nHistory: {docs['history']}\n\nSources:\n"
        for doc in docs['source_documents']:
            docs_str += f"\n- {doc.metadata['source']}: {doc.page_content}\n"
        print_chat(docs_str)
        
class LiteLLM(BaseRetrieval):
    def __init__(self, name):
        self.name = name
        super().__init__()

    def _create_store(self, root_dir: str) -> Optional[FAISS]:
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        return self._create_vector_store(embeddings, self.name, root_dir)

    def _create_model(self):
        return ChatLiteLLM(model = self.name)
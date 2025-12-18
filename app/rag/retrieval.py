from __future__ import annotations

import os
from abc import ABC, abstractmethod

from loguru import logger
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.chat_models import ChatLiteLLM
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.model import common
from app.rag.util import get_local_vector_store, load_files
from script.log import print_chat


DEFAULT_QA_TEMPLATE = (
    "You are a senior software engineer. Answer the user's question using the provided context.\n"
    "If the answer is not in the context, say you don't know.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}\n\n"
    "Answer:\n"
)


def _safe_model_dirname(model_name: str) -> str:
    return model_name.replace("/", "_").replace(" ", "_")


class BaseRetrieval(ABC):
    def __init__(self):
        self.llm = self._create_model()
        self.db = self._create_store()
        self.retriever = self.db.as_retriever(search_kwargs={"k": self.k})
        self.prompt = PromptTemplate(
            template=DEFAULT_QA_TEMPLATE,
            input_variables=["context", "question"],
        )
        self.qa = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
            chain_type_kwargs={"prompt": self.prompt},
            return_source_documents=True,
        )

    @property
    def k(self) -> int:
        return 3

    @abstractmethod
    def _create_store(self) -> FAISS:
        raise NotImplementedError("abstract method")

    @abstractmethod
    def _create_model(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def send_query(self, query: str) -> None:
        try:
            result = self.qa.invoke({"query": query})
        except Exception:
            # Some langchain versions accept plain string.
            result = self.qa.invoke(query)

        answer = result.get("result", "")
        sources = result.get("source_documents") or []

        lines: list[str] = [f"Q: {query}", "", answer.strip()]
        if sources:
            lines.append("\nSources:")
            seen = set()
            for doc in sources:
                src = (doc.metadata or {}).get("source") or "(unknown)"
                if src in seen:
                    continue
                seen.add(src)
                snippet = (doc.page_content or "").strip().replace("\n", " ")
                if len(snippet) > 240:
                    snippet = snippet[:240] + "…"
                lines.append(f"- {src}: {snippet}")

        print_chat("\n".join(lines))


class LiteLLM(BaseRetrieval):
    def __init__(self, name: str, root_dir: str):
        self.name = name
        self.root_dir = os.path.abspath(root_dir)
        super().__init__()

    def _create_store(self) -> FAISS:
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

        index_path = os.path.join(
            self.root_dir,
            "vector_store",
            _safe_model_dirname(self.name),
        )
        os.makedirs(os.path.dirname(index_path), exist_ok=True)

        existing = get_local_vector_store(embeddings, index_path)
        if existing is not None:
            logger.info(f"RAG: loaded vector store from {index_path}")
            return existing

        docs = load_files(self.root_dir)
        if not docs:
            raise RuntimeError(f"RAG: no documents found under {self.root_dir}")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(common.MODEL_CHUNK_SIZE),
            chunk_overlap=int(common.MODEL_CHUNK_OVERLAP),
            length_function=len,
            separators=["\n\n", "\n", " ", ".", ",", ""],
        )
        chunks = splitter.split_documents(docs)
        logger.info(f"RAG: building vector store ({len(chunks)} chunks)")

        db = FAISS.from_documents(chunks, embeddings)
        db.save_local(index_path)
        logger.info(f"RAG: saved vector store to {index_path}")
        return db

    def _create_model(self):
        return ChatLiteLLM(model=self.name)
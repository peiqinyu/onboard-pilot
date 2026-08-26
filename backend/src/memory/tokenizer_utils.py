from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from backend.src.memory.logger_utils import logger


class TokenizerService:
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 128):
        # =========================================================================
        # INITIALIZE OR CONNECT TO THE DATABASE
        # =========================================================================
        self.embedding_model = OllamaEmbeddings(model="nomic-embed-text")

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def get_chunks(self, knowledge_document: str):
        # 1. Split the raw text into manageable pieces first
        text_chunks = self.text_splitter.split_text(knowledge_document)
        """
        Takes a list of chunks and adds them to the database,
        attaching metadata to each chunk so you can trace its source later.
        """
        if not text_chunks:
            logger.info("No chunks provided.")
            return
        return text_chunks

    # def add_new_document_to_db(self, knowledge_document: str, document_name: str):
    #     # 1. Split the raw text into manageable pieces first
    #     text_chunks = self.get_chunks(knowledge_document)
    #
    #     # Generate metadata for each chunk (e.g., attaching the filename)
    #     # The metadata list must be exactly the same length as the chunks list
    #     chunk_metadata = [{"source": document_name} for _ in text_chunks]
    #
    #     # Add texts and metadata to the database
    #     self.vector_db.add_texts(
    #         texts=text_chunks,
    #         metadatas=chunk_metadata
    #     )
    #     logger.info(f"Added {len(text_chunks)} chunks from '{document_name}' to the vector database.")


if __name__ == "__main__":
    rag = TokenizerService()
    text = """Project Alpha is a confidential company initiative launched in 2026.
        The primary goal of Project Alpha is to transition all corporate infrastructure
        to a 100% renewable energy grid by Q4. The budget allocated is $5 million,
        and it is being managed by Sarah Jenkins from the Operations department.
        Any security breaches regarding Project Alpha must be reported immediately to security@company.com.
        """
    docName = "test.txt"
    # rag.add_new_document_to_db(text, docName)
    # logger.info(rag.vector_db)

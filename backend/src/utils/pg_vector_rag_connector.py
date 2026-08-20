# pip install langchain-postgres psycopg2-binary
from langchain_postgres.vectorstores import PGVector
from semantic_kernel.functions import kernel_function
from typing import Annotated

from backend.src.utils.base_connector import BaseConnector
from backend.src.utils.tokenizer_utils import TokenizerService
from backend.src.utils.logger_utils import logger
from backend.src.utils.utils import my_properties


class PgVectorRAGStoreConnector(BaseConnector):
    def __init__(self):
        self.name = "PgVectorRAGStoreConnector"
        self.tokenizer = TokenizerService()
        # Make sure this matches the user and database you created in your terminal
        connection_string = f"postgresql://{my_properties.db_username}:{my_properties.db_password}" \
                            f"@{my_properties.db_host}:5432/{my_properties.db_schema}"

        # Initialize the connection to the existing database
        self.vector_db = PGVector(
            embeddings=self.tokenizer.embedding_model,
            connection=connection_string,
            collection_name="company_knowledge_base",
            use_jsonb=True,  # Stores metadata safely
            create_extension=False
        )

    @kernel_function(
        name="add_new_document_to_rag",
        description="""Gets the related content for a given sentence."""
    )
    def add_new_document_to_rag(self, knowledge_document: Annotated[str, "the content of RAG"],
                                document_name: Annotated[str, "the file name of the RAG content"]):
        text_chunks = self.tokenizer.get_chunks(knowledge_document)
        # Generate metadata for each chunk (e.g., attaching the filename)
        # The metadata list must be exactly the same length as the chunks list
        chunk_metadata = [{"source": document_name} for _ in text_chunks]

        # Add texts and metadata to the PostgreSQL database
        self.vector_db.add_texts(
            texts=text_chunks,
            metadatas=chunk_metadata
        )

        logger.info(f"Successfully added {len(text_chunks)} chunks from '{document_name}' to PostgreSQL.")

    # @kernel_function(
    #     name="retrieve_documents",
    #     description="""Search and get top k similar items in RAG for a given sentence."""
    # )
    def retrieve_documents(self,
                           query: Annotated[str, "filtered sentence, e.g. testing process looks like"],
                           top_k: Annotated[int, "The first k related content to return"] = 3,
                           document_filter: Annotated[str, "filtered key words"] = None) -> str:
        """
        Searches the vector database for the closest chunks to the user's query.
        Optionally filters the search to a specific document.
        """
        logger.info(f"Searching for: '{query}'")

        # If a filter is provided, LangChain will ONLY search chunks that
        # match that specific metadata source
        search_kwargs = {}
        if document_filter:
            logger.info(f"(Filtering search to only look inside: {document_filter})")
            search_kwargs["filter"] = {"source": document_filter}

        # Perform the similarity search
        # k = how many chunks to return
        results = self.vector_db.similarity_search(
            query=query,
            k=top_k,
            **search_kwargs
        )

        if not results:
            return "No relevant information found in the database."

        # Format the results into a single readable string for the LLM
        context_blocks = []
        for i, doc in enumerate(results):
            source_name = doc.metadata.get("source", "Unknown Document")
            context_blocks.append(f"--- Result {i + 1} (Source: {source_name}) ---\n{doc.page_content}")

        combined_context = "\n\n".join(context_blocks)
        return combined_context

    @kernel_function(
        name="search_k_content",
        description="""Search and get top k similar items in RAG for a given sentence."""
    )
    def search_k_content(self, query: str, top_k: int = 3) -> str:
        return self.retrieve_documents(query, top_k, None)


if __name__ == "__main__":
    text = """Project Alpha is a confidential company initiative launched in 2026.
           The primary goal of Project Alpha is to transition all corporate infrastructure
           to a 100% renewable energy grid by Q4. The budget allocated is $5 million,
           and it is being managed by Sarah Jenkins from the Operations department.
           Any security breaches regarding Project Alpha must be reported immediately to security@company.com.
           """
    store = PgVectorRAGStoreConnector()
    store.add_new_document_to_rag(text, "test.txt")
    result = store.search_k_content("security breaches", 1)
    logger.info(f"RAG search result: {result}")

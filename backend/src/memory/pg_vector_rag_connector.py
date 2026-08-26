from langchain_postgres.vectorstores import PGVector
from semantic_kernel.functions import kernel_function
from typing import Annotated
from backend.src.memory.base_connector import BaseConnector
from backend.src.memory.tokenizer_utils import TokenizerService
from backend.src.memory.logger_utils import logger
from backend.src.memory.utils import my_properties, read_file, load_raga_parquet
from pathlib import Path
import os


class PgVectorRAGStoreConnector(BaseConnector):
    def __init__(self):
        self.chunk_size = 2048
        self.chunk_overlap = 256
        self.name = "PgVectorRAGStoreConnector"
        self.tokenizer = TokenizerService(self.chunk_size, self.chunk_overlap)
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

    def add_batch_new_document_to_rag(
            self,
            knowledge_document: Annotated[str, "the content of RAG"],
            document_name: Annotated[str, "the file name of the RAG content"]
    ):
        # 1. Chunk the document
        text_chunks = self.tokenizer.get_chunks(knowledge_document)
        total_chunks = len(text_chunks)

        if total_chunks == 0:
            logger.warning(f"No text chunks generated from '{document_name}'. Skipping.")
            return

        logger.warning(f"Total {total_chunks} chunks with truck size {self.chunk_size} "
                       f"generated from '{document_name}' with size {len(knowledge_document)}.")

        # 2. Process and upload in safe batch sizes to prevent Ollama TCP connection reset
        batch_size = 32
        for i in range(0, total_chunks, batch_size):
            batch_texts = text_chunks[i: i + batch_size]
            batch_metadata = [{"source": document_name} for _ in batch_texts]
            # Add current batch to the PostgreSQL database
            self.vector_db.add_texts(
                texts=batch_texts,
                metadatas=batch_metadata
            )

            logger.debug(f"Uploaded batch {i // batch_size + 1} ({len(batch_texts)} chunks) for '{document_name}'.")

        logger.info(f"Successfully added {total_chunks} chunks from '{document_name}' to PostgreSQL.")

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

    def retrieve_documents(self,
                           query: Annotated[str, "filtered sentence, e.g. testing process looks like"],
                           top_k: Annotated[int, "The first k related content to return"] = 3,
                           document_filter: Annotated[str, "filtered key words"] = None) -> str:
        """
        Searches the vector database for the closest chunks to the user's query.
        Optionally filters the search to a specific document.
        """
        # logger.debug(f"Searching in RAG for: '{query}'")
        logger.info(f"Searching in RAG")

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
            # trunk_id = doc.metadata
            logger.debug(f"🔗 RAG source retrieved {source_name}")
            context_blocks.append(f"--- Result {i + 1} (Source: {source_name}) ---\n{doc.page_content}")

        combined_context = "\n\n".join(context_blocks)
        return combined_context

    @kernel_function(
        name="search_k_content",
        description="""Search and get top k similar items in RAG for a given sentence."""
    )
    def search_k_content(self, query: str, top_k: int = 3) -> str:
        return self.retrieve_documents(query, top_k, None)

    def print_all_stored_documents(self, limit: int = 50):
        """
        Retrieves and prints stored chunks natively using LangChain's vector API.
        Does not depend on raw PostgreSQL connections or table names.
        """
        logger.info("Fetching documents from pgvector database...")

        try:
            # We pass an empty string or whitespace as a broad query.
            # k controls the max number of document chunks returned.
            docs = self.vector_db.similarity_search(query=" ", k=limit)

            if not docs:
                print("\n Database is empty. No documents found.")
                return

            print(f"\n--- SHOWING UP TO {limit} STORED CHUNKS ---")
            for idx, doc in enumerate(docs):
                # Extract metadata safely
                source_file = doc.metadata.get("source", "Unknown Source")

                print(f"\n[Chunk {idx + 1}]")
                print(f"[Source File]: {source_file}")
                print(f"[Content]: {doc.page_content}...")  # Previews first 150 chars
                # print(f"[Content Snippet]: {doc.page_content[:150]}...")  # Previews first 150 chars
                print("-" * 50)

            print(f"\nSuccessfully displayed {len(docs)} items.")

        except Exception as e:
            logger.error(f"Failed to retrieve data from vector store: {e}")

    def truncate_vector_db(self):
        """
        Safely deletes all entries inside the active collection using the
        native public framework methods.
        """
        logger.info("Attempting to delete all records from the collection...")
        try:
            # 1. Pull the IDs natively using your existing vector_db instance
            # We run a broad search to pull back document instances
            docs = self.vector_db.similarity_search(query=" ", k=10000)

            if not docs:
                logger.info("The collection is already empty.")
                return

            # 2. Extract the unique IDs LangChain generated for them
            # In newer versions of langchain_postgres, doc.id contains the DB row identifier
            ids_to_delete = [doc.id for doc in docs if doc.id is not None]

            if ids_to_delete:
                self.vector_db.delete(ids=ids_to_delete)
                logger.info(f"Successfully deleted {len(ids_to_delete)} entries from the vector store.")
            else:
                # Fallback if IDs aren't attached directly to the returned objects
                logger.warning("Could not gather document IDs. Trying Option 2 instead.")
                self._truncate_via_sql_engine()

        except Exception as e:
            logger.error(f"Failed native truncation: {e}. Trying raw engine fallback...")
            self._truncate_via_sql_engine()


if __name__ == "__main__":
    # file_loc = str(Path(__file__).parent.resolve()) + os.sep \
    #            + '..' + os.sep + '..' \
    #            + os.sep + 'tests' \
    #            + os.sep + 'golden_dataset' \
    #            + os.sep + 'train-00000-of-00001.parquet'
    # df = load_raga_parquet(file_loc, ['user_input',
    #                                   'reference_contexts',
    #                                   'reference'])

    store = PgVectorRAGStoreConnector()

    # for index, row in df.iterrows():
    #     ip = row["user_input"]
    #     con = row['reference_contexts']
    #     ref = row['reference']
    #     if isinstance(ref, bytes):
    #         ref = ref.decode('utf-8')
    #     if isinstance(con, bytes):
    #         con = con.decode('utf-8')
    #     knowledge_doc = ref + "\n" + con
    #     if isinstance(knowledge_doc, bytes):
    #         knowledge_doc = knowledge_doc.decode('utf-8')
    #     file_name = "ragas_row"+str(index+1)
    #     print(f"filename {file_name}\ninput: [{ip}]\ncontent: [{knowledge_doc}]")
    #     store.add_batch_new_document_to_rag(str(knowledge_doc), file_name)

    # store.truncate_vector_db()
    store.print_all_stored_documents()

    # result = store.search_k_content("", 100)
    # logger.info(f"RAG search result: {result}")
    # data_dir = str(Path(__file__).parent.resolve()) + os.sep + '..' + os.sep + 'data'
    # file = data_dir + os.sep + 'google_java_style_guideline'
    # for k in range(0, 8):
    #     filedir = read_file(file+str(k))
    #     print(filedir)
    #     store.add_batch_new_document_to_rag(filedir['file_content'], filedir['file_name'])
    #
    # file = data_dir + os.sep + 'open_ai_production_best_practice'
    # for k in range(0, 8):
    #     filedir = read_file(file + str(k))
    #     print(filedir)
    #     store.add_batch_new_document_to_rag(filedir['file_content'], filedir['file_name'])

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.vectordb import add_documents

def ingest_pdf(file_path):
    loader = PyPDFLoader(file_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )

    chunks = splitter.split_documents(docs)

    texts = [chunk.page_content for chunk in chunks]
    metadatas = [{"source": file_path} for _ in texts]

    add_documents(texts, metadatas)

    return len(texts)
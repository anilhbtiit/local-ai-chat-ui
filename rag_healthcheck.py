import langchain
import chromadb
import sentence_transformers
import pypdf
import docx
import bs4
import git

print("All imports successful ✅")

from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
emb = model.encode("test sentence")

print(len(emb))

import chromadb

client = chromadb.Client()
collection = client.create_collection(name="test_collection")

collection.add(
    documents=["Hello world"],
    ids=["1"]
)

results = collection.query(query_texts=["Hello"], n_results=1)

print(results)

from langchain_text_splitters import RecursiveCharacterTextSplitter

text = "This is a test " * 200

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = splitter.split_text(text)

print(len(chunks))

from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader("DesignPatterns.pdf")
docs = loader.load()

print(len(docs))

from langchain_community.document_loaders import Docx2txtLoader

loader = Docx2txtLoader("sample.docx")
docs = loader.load()

print(len(docs))

import requests
from bs4 import BeautifulSoup

res = requests.get("https://example.com")
soup = BeautifulSoup(res.text, "html.parser")

print(soup.title.text)

from git import Repo

Repo.clone_from("https://github.com/git/git", "test_repo")
print("Cloned successfully")

import chromadb

client = chromadb.Client(
    settings=chromadb.config.Settings(
        persist_directory="./vector_db"
    )
)

collection = client.get_or_create_collection("persist_test")

collection.add(documents=["persist test"], ids=["1"])

client.persist()

print("Persisted successfully")


import json
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from sentence_transformers import SentenceTransformer
import numpy as np

print("RAG FINAL Qwen3-Embedding...")

# Connexion Milvus
connections.connect("default", host="milvus", port="19530")
print("Milvus OK")

# TON MODÈLE EXACT
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
DIM = model.get_sentence_embedding_dimension()
print(f"Qwen3 dim: {DIM}")

COLLECTION_NAME = "wikichess_openings"
if utility.has_collection(COLLECTION_NAME):
    utility.drop_collection(COLLECTION_NAME)
    print("Reset collection")

# Schéma avec dimensions
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="opening", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
]
schema = CollectionSchema(fields, description="Wikichess Qwen3")
collection = Collection(COLLECTION_NAME, schema=schema)
print("Collection {COLLECTION_NAME}")

# REGÉNÈRE les embeddings proprement avec modèle
with open("rag/wikichess_articles.json") as f:  # Fichier SOURCE
    articles = json.load(f)

print(f"{len(articles)} articles à embedder")

# REGÉNÉRATION propre
contents = [a["content"] for a in articles]
embeddings = model.encode(contents, batch_size=8, show_progress_bar=True)

# VALIDATION + INSERT
valid_articles = []
for i, (article, emb) in enumerate(zip(articles, embeddings)):
    if len(emb) == DIM:
        valid_articles.append({
            "opening": article["opening"],
            "content": article["content"],
            "embedding": emb.tolist()
        })
    else:
        print(f"Article {i} ignoré: {len(emb)} != {DIM}")

print(f"{len(valid_articles)}/{len(articles)} OK")

# Insert batchs
batch_size = 10
for i in range(0, len(valid_articles), batch_size):
    batch = valid_articles[i:i+batch_size]
    openings = [a["opening"] for a in batch]
    contents = [a["content"] for a in batch]
    embeddings_batch = [a["embedding"] for a in batch]
    collection.insert([openings, contents, embeddings_batch])
    print(f" Batch {i//batch_size+1}: {len(batch)}")

# Index + load
index_params = {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}}
collection.create_index("embedding", index_params)
collection.load()
print(f" RAG Qwen3 PRÊT ! {collection.num_entities} entités")

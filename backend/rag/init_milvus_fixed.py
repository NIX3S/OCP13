import json
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import numpy as np

print("FIX Milvus RAG...")

connections.connect("default", host="milvus", port="19530")
print("Milvus connecté")

COLLECTION_NAME = "wikichess_openings"
if utility.has_collection(COLLECTION_NAME):
    utility.drop_collection(COLLECTION_NAME)
    print("Collection reset")

# Schéma (1536 dim)
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="opening", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]
schema = CollectionSchema(fields, description="Wikichess")
collection = Collection(COLLECTION_NAME, schema=schema)
print("Collection créée")

# Valide et corrige embeddings
with open("rag/wikichess_articles_with_embeddings.json") as f:
    articles = json.load(f)

valid_articles = []
for i, article in enumerate(articles):
    embedding = article["embedding"]
    if isinstance(embedding, list) and len(embedding) == 1536:
        valid_articles.append(article)
    else:
        print(f" Article {i} ignoré: embedding invalide (len={len(embedding) if embedding else 0})")

print(f" {len(valid_articles)}/{len(articles)} articles valides")

# Insert par batchs de 10 (SAFE)
batch_size = 10
for i in range(0, len(valid_articles), batch_size):
    batch = valid_articles[i:i+batch_size]
    openings = [a["opening"] for a in batch]
    contents = [a["content"] for a in batch]
    embeddings = [a["embedding"] for a in batch]
    
    collection.insert([openings, contents, embeddings])
    print(f" Batch {i//batch_size + 1}: {len(batch)} inserés")

# Index + load
index_params = {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}}
collection.create_index("embedding", index_params)
collection.load()
print(" RAG PRÊT !")
print("X", collection.num_entities, "entités")

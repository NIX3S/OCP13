import json
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
import os

print("Initialisation Milvus RAG...")

# Connexion
connections.connect("default", host="milvus", port="19530")
print("Connecté à Milvus")

# Schéma
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="opening", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
]
schema = CollectionSchema(fields, description="Wikichess openings")

COLLECTION_NAME = "wikichess_openings"

# Reset collection
if utility.has_collection(COLLECTION_NAME):
    utility.drop_collection(COLLECTION_NAME)
    print("Collection supprimée")

collection = Collection(COLLECTION_NAME, schema=schema)
print("Collection créée")

# Données de test (1536 dim)
test_articles = [
    {"opening": "Sicilian Defense", "content": "1.e4 c5 Najdorf Dragon - Défense agressive contre e4", "embedding": [0.1]*1536},
    {"opening": "Ruy Lopez", "content": "1.e4 e5 2.Cf3 Cc6 3.Ab5 - Espagnole Berlin Marshall", "embedding": [0.2]*1536},
    {"opening": "Italian Game", "content": "1.e4 e5 2.Cf3 Cc6 3.Ac4 - Giuoco Piano Evans", "embedding": [0.3]*1536},
    {"opening": "Queen's Gambit", "content": "1.d4 d5 2.c4 - Accepté Refusé Slav Tarrasch", "embedding": [0.4]*1536}
]

# JSON
if os.path.exists("rag/wikichess_articles_with_embeddings.json"):
    with open("rag/wikichess_articles_with_embeddings.json") as f:
        articles = json.load(f)
    print(f"{len(articles)} articles JSON trouvés")
else:
    articles = test_articles
    print("Données de test utilisées")

# Insert
openings = [a["opening"] for a in articles]
contents = [a["content"] for a in articles]
embeddings = [a["embedding"] for a in articles]
collection.insert([openings, contents, embeddings])
print(f"{len(articles)} embeddings insérés")

# Index
index_params = {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}}
collection.create_index("embedding", index_params)
collection.load()
print(" Milvus RAG PRÊT !")

# Vérif
print(" Collections:", utility.list_collections())
print(" Entités:", collection.num_entities)
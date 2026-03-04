import json
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection

# Connexion à Milvus (nom du service Docker)
connections.connect("default", host="milvus", port="19530")
from pymilvus import utility

COLLECTION_NAME = "wikichess_openings"

# Si la collection existe déjà, on la supprime
if utility.has_collection(COLLECTION_NAME):
    utility.drop_collection(COLLECTION_NAME)
    print("🗑️ Collection supprimée:", COLLECTION_NAME)

# Définir le schéma
fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="opening", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024)
]
schema = CollectionSchema(fields, description="Wikichess openings embeddings")

# Créer la collection
collection_name = "wikichess_openings"
collection = Collection(name=collection_name, schema=schema)

# Charger les embeddings générés
with open("rag/wikichess_articles_with_embeddings.json", "r", encoding="utf-8") as f:
    articles = json.load(f)

# Préparer les données
openings = [a['opening'] for a in articles]
contents = [a['content'] for a in articles]
embeddings = [a['embedding'] for a in articles]

# Insérer dans Milvus
collection.insert([openings, contents, embeddings])


# Créer l'index vectoriel
collection.create_index("embedding", {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}})
collection.load()

print("Données indexées dans Milvus !")
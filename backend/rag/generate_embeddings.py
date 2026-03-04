print("Script lancé !")
import json
import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from sentence_transformers import SentenceTransformer

print("1/5 - Chargement des articles...")
with open("backend/rag/wikichess_articles.json", "r", encoding="utf-8") as f:
    articles = json.load(f)
print(f"  → {len(articles)} articles chargés")

print("2/5 - Chargement du modèle...")
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
print("  → Modèle chargé, dim embedding :", model.get_sentence_embedding_dimension())

print("3/5 - Récupération des contenus...")
contents = [article["content"] for article in articles]

print("4/5 - Génération des embeddings (cette étape peut être longue)...")
embeddings = model.encode(
    contents,
    batch_size=16,
    show_progress_bar=True,
)

print("5/5 - Ajout des embeddings et sauvegarde...")
for article, emb in zip(articles, embeddings):
    article["embedding"] = emb.tolist()

with open("backend/rag/wikichess_articles_with_embeddings.json", "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print("Embeddings générés et sauvegardés !")

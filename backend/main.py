from fastapi import FastAPI, BackgroundTasks  # ← UNIQUE ici
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
import chess
import time
import os
from dotenv import load_dotenv
from typing import Dict, List
from functools import lru_cache
import asyncio  # ← AJOUTÉ
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer

model = None
chess_collection = None

try:
    from sentence_transformers import SentenceTransformer
    from pymilvus import connections, Collection, utility
    
    model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
    connections.connect("default", host="milvus", port="19530")
    chess_collection = Collection("wikichess_openings")
    chess_collection.load()
    print("Qwen3 Wikichess RAG chargé (1024 dim)")
except Exception as e:
    print(f"RAG error: {e}")
    chess_collection = model = None

# Config YouTube
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YTB_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# CACHE INTELLIGENT
cache = {
    'moves': {}, 'eval': {}, 'opening': {}, 
    'videos': {}, 'youtube_queue': []
}

def cache_get(key: str, cache_type: str, ttl: int = 300):
    if key in cache[cache_type]:
        item = cache[cache_type][key]
        if time.time() - item['time'] < ttl:
            return item['data']
    return None

def cache_set(key: str, value: dict, cache_type: str):
    cache[cache_type][key] = {'data': value, 'time': time.time()}

# FONCTIONS RAPIDES (chess optimisées)
@lru_cache(maxsize=2048)
def get_legal_moves(fen: str) -> list:
    board = chess.Board(fen)
    return [move.uci() for move in list(board.legal_moves)[:4]]

def get_moves_cached(fen: str) -> dict:
    cached = cache_get(fen, 'moves')
    if cached: return cached
    moves = get_legal_moves(fen)
    result = {"source": "legal_moves", "moves": moves}
    cache_set(fen, result, 'moves')
    return result

def get_eval_cached(fen: str) -> dict:
    cached = cache_get(fen, 'eval', 120)
    if cached: return cached
    board = chess.Board(fen)
    piece_values = {chess.PAWN:1, chess.KNIGHT:3, chess.BISHOP:3, chess.ROOK:5, chess.QUEEN:9}
    white_score = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.WHITE)
    black_score = sum(piece_values.get(p.piece_type, 0) for p in board.piece_map().values() if p.color == chess.BLACK)
    result = {"type": "cp", "value": (white_score - black_score) * 100}
    cache_set(fen, result, 'eval')
    return result

def detect_opening(fen: str) -> dict:
    cached = cache_get(fen, 'opening')
    if cached: return cached
    
    board = chess.Board(fen)
    fen_board = board.fen().split(' ')[0]  #  TOUT le FEN board
    
    print(f" Debug FEN: {fen_board}")  # ← DEBUG temporaire
    
    # RÈGLES PRÉCISES par position exacte
    if "4P3/8/PPPP1PPP" in fen_board:  # 1.e4 exact
        name = "King's Pawn Game (1.e4)"
    elif "3PP3/8/PPPP1PPP" in fen_board:  # 1.d4 exact
        name = "Queen's Pawn Game (1.d4)"
    elif "rnbqkbnr/pppp1ppp" in fen_board and "4P3" in fen_board:  # 1.e4 e5
        name = "Open Game (1.e4 e5)"
    elif "rnbqkbnr/pp1ppppp" in fen_board and "4P3" in fen_board:  # 1.e4 c5
        name = "Sicilian Defense (1.e4 c5)"
    elif board.fullmove_number <= 2:
        name = "Opening Position"
    else:
        name = f"Position {board.fullmove_number}"
    
    result = {"name": name, "eco": "A00", "ply": board.fullmove_number}
    cache_set(fen, result, 'opening')
    print(f"Detected: {name}")  # ← DEBUG
    return result

@app.get("/api/v1/vector-search/{opening}")
async def vector_search(opening: str):
    # Embedding query
    query_embedding = model.encode([opening]).tolist()[0]
    
    # Recherche vectorielle TOP 3
    search_params = {"metric_type": "L2", "params": {"ef": 64}}
    results = chess_collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=3,
        output_fields=["opening", "content"]
    )
    
    # Format réponse
    contexts = []
    for hits in results:
        for hit in hits:
            contexts.append({
                "opening": hit.entity.get("opening_name"),
                "eco": hit.entity.get("eco"),
                "moves": hit.entity.get("moves"),
                "content": hit.entity.get("content"),
                "score": float(hit.distance)
            })
    
    return {"opening": opening, "contexts": contexts[:3]}

# YOUTUBE SYNCHRONE (pour background)
def get_youtube_videos_sync(opening: str, max_results: int = 2) -> list:
    """Version SYNCHRONE pour background tasks"""
    cache_key = f"vid:{opening}"
    cached = cache_get(cache_key, 'videos', 86400)
    if cached: return cached
    
    try:
        query = f'"{opening}" chess opening tutorial -advertisement'
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=max_results,
            order="relevance",
            publishedAfter="2020-01-01T00:00:00Z"
        )
        start_time = time.time()
        response = request.execute()
        
        videos = []
        for item in response.get("items", [])[:max_results]:
            if time.time() - start_time > 1.2:
                break
            video_id = item["id"]["videoId"]
            videos.append({
                "title": item["snippet"]["title"][:60],
                "url": f"https://youtube.com/watch?v={video_id}",
                "channel": item["snippet"]["channelTitle"][:20]
            })
        
        if videos:
            cache_set(cache_key, videos, 'videos')
        else:
            videos = [{"title": f"{opening} (top videos)", "url": "#", "channel": "YouTube"}]
    except Exception as e:
        print(f"YouTube error: {e}")
        videos = [{"title": f"{opening} tutorial", "url": "#", "channel": "Fallback"}]
    
    return videos[:3]

# ENDPOINT PRINCIPAL < 100ms
@app.get("/api/v1/analyze/{fen:path}")
async def analyze_position(fen: str):
    start = time.time()
    opening_dict = detect_opening(fen)
    opening = opening_dict["name"]
    moves = get_moves_cached(fen)
    evaluation = get_eval_cached(fen)
    videos = get_youtube_videos_sync(opening)
    
    # RAG (wikichess_openings)
    context_items = []
    if chess_collection and model:
        query_embedding = model.encode([opening]).tolist()
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = chess_collection.search(
            data=query_embedding,
            anns_field="embedding",
            param=search_params,
            limit=3,
            output_fields=["opening", "content"]
        )
        context_items = [{
            "opening": hit.entity.get("opening"),
            "content": hit.entity.get("content"), 
            "score": 1.0 - float(hit.distance)
        } for hits in results for hit in hits]
    
    if not context_items:
        context_items = [{"opening": opening, "content": f"Théorie {opening}", "score": 0.95}]
    
    result = {
        "fen": fen,
        "opening": opening,
        "moves": moves,
        "evaluation": evaluation,
        "videos": videos,
        "context": context_items  
    }
    
    duration = (time.time() - start) * 1000
    print(f"Analyze RAG: {duration:.1f}ms | {opening} | contexts: {len(context_items)}")
    return result



@app.get("/api/v1/healthcheck")
def healthcheck():
    return {
        "status": "YOUTUBE + CACHE",
        "cache_sizes": {k: len(v) for k, v in cache.items() if k != 'youtube_queue'}
    }

@app.delete("/api/v1/clear-cache")
def clear_cache():
    for key in ['moves', 'eval', 'opening', 'videos']:
        cache[key].clear()
    return {"status": "Cleared"}

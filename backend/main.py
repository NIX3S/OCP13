from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from googleapiclient.discovery import build
import chess
import time
import os
from dotenv import load_dotenv
from typing import Dict, List, TypedDict, Annotated
from functools import lru_cache
from pydantic import BaseModel
from pymilvus import connections, Collection
from sentence_transformers import SentenceTransformer
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# État LangGraph
class ChessState(TypedDict):
    fen: str
    opening: str
    moves: Dict
    evaluation: Dict
    context: List[Dict]
    videos: List[Dict]
    videos_by_context: List[Dict]

# Global LangGraph (singleton)
model = None
chess_collection = None
graph: StateGraph = None

# Initialisation RAG (inchangée)
try:
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# CACHE + FONCTIONS MÉTIER
cache = {'moves': {}, 'eval': {}, 'opening': {}, 'videos': {}, 'youtube_queue': []}

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
    fen_board = board.fen().split(' ')[0]
    
    print(f" Debug FEN: {fen_board}")
    
    # POSITION DE DÉPART
    if fen_board == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR":
        name = "Ouverture Française - Position initiale"
    
    # OUVERTURES 100% UNIQUES (rang 5+7)
    elif "2p5/4P3" in fen_board:  # c5 + e4 = SICILIAN
        name = "Sicilian Defense (1.e4 c5)"
    elif "4p3/4P3" in fen_board:  # e6 + e4 = FRENCH
        name = "French Defense (1.e4 e6)"
    elif "6p1/4P3" in fen_board:  # g5 + e4 = DUTCH
        name = "Dutch Defense (1.e4 g5)"
    elif "3p4/2PP4" in fen_board:  # d5 + c4+d4 = QUEEN'S GAMBIT
        name = "Queen's Gambit (1.d4 d5 2.c4)"
    elif "4p3/4P3/5N2" in fen_board:  # e5 + e4 + Nf3 = RUY
        name = "Ruy Lopez Setup (1.e4 e5 2.Nf3)"
    
    # BASES (1.e4, 1.d4)
    elif "4P3/8/PPPP1PPP" in fen_board:  # 1.e4
        name = "King's Pawn Game (1.e4)"
    elif "3PP3/8/PPPP1PPP" in fen_board:  # 1.d4
        name = "Queen's Pawn Game (1.d4)"
    
    elif board.fullmove_number <= 2:
        name = "Ouverture Française - Début de partie"
    else:
        name = f"Position tour {board.fullmove_number}"
    
    result = {"name": name, "eco": "A00", "ply": board.fullmove_number}
    cache_set(fen, result, 'opening')
    print(f" Detected: {name}")
    return result


def router_node(state: ChessState) -> ChessState:
    """Node 1: Détecte ouverture → décide routing"""
    state["opening"] = detect_opening(state["fen"])["name"]
    return state

def rag_node(state: ChessState) -> ChessState:
    """Node 2: Milvus RAG Wikichess ← CONNECTÉ !"""
    if chess_collection and model:
        query_embedding = model.encode([state["opening"]]).tolist()
        results = chess_collection.search(data=query_embedding, anns_field="embedding",
                                        param={"metric_type": "COSINE", "params": {"nprobe": 16}},
                                        limit=3, output_fields=["opening", "content"])
        state["context"] = [{"opening": hit.entity.get("opening", "Inconnu"), 
                           "content": hit.entity.get("content", "No theory"), 
                           "score": max(0, 1.0 - float(hit.distance))} for hits in results for hit in hits]
    else:
        state["context"] = [{"opening": state["opening"], "content": f"Théorie générale {state['opening']}", "score": 0.8}]
    return state

def youtube_node(state: ChessState) -> ChessState:
    """Node 3: Vidéos contextuelles"""
    state["videos"] = get_youtube_videos_sync(state["opening"])
    state["videos_by_context"] = [{"context_opening": ctx["opening"], 
                                 "videos": get_youtube_videos_sync(ctx["opening"])} 
                                 for ctx in state["context"][:3]]
    return state

def chess_node(state: ChessState) -> ChessState:
    """Node 4: Moves + éval"""
    state["moves"] = get_moves_cached(state["fen"])
    state["evaluation"] = get_eval_cached(state["fen"])
    return state

# INITIALISATION LANGGRAPH AU DEMARRAGE
def choose_tools(state: ChessState):
    """CHOIX INTELLIGENT D'OUTILS selon opening"""
    opening = state["opening"]
    
    # Sicilian/French = théorie riche => RAG + vidéo
    if any(x in opening for x in ["Sicilian", "French", "Queen","King", "Ruy", "Dutch"]):
        return "rag"
    
    # Début de partie simple => Stockfish seulement
    elif state["fen"].count('/') <= 5 or "tour 1" in opening or "tour 2" in opening:
        return "chess"
    
    # Tout le reste => vidéos générales
    else:
        return "youtube"

def init_langgraph():
    global graph
    workflow = StateGraph(ChessState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("youtube", youtube_node)
    workflow.add_node("chess", chess_node)  # STOCKFISH TOUJOURS
    
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        choose_tools,
        {"rag": "rag", "chess": "chess", "youtube": "youtube"}
    )
    
    workflow.add_edge("rag", "youtube")
    workflow.add_edge("youtube", "chess")
    workflow.add_edge("chess", END)            # Stockfish final
    
    graph = workflow.compile()

# Init au démarrage app
@app.on_event("startup")
async def startup_event():
    init_langgraph()
    print("LangGraph + Milvus workflow initialisé")

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
    if not graph:
        return {"error": "LangGraph non initialisé"}
    
    # Exécute LangGraph workflow
    initial_state = {"fen": fen, "opening": "", "moves": {}, "evaluation": {}, 
                    "context": [], "videos": [], "videos_by_context": []}
    result = graph.invoke(initial_state)
    
    duration = (time.time() - start) * 1000
    print(f"LangGraph: {duration:.1f}ms | {result['opening']} | contexts: {len(result['context'])}")
    return result


@app.get("/api/v1/healthcheck")
def healthcheck():
    return {
        "status": "LANGGRAPH + YOUTUBE + CACHE",
        "graph_ready": graph is not None,
        "cache_sizes": {k: len(v) for k, v in cache.items() if k != 'youtube_queue'}
    }

@app.delete("/api/v1/clear-cache")
def clear_cache():
    for key in ['moves', 'eval', 'opening', 'videos']:
        cache[key].clear()
    return {"status": "Cleared"}

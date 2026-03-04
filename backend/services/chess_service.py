import chess
import requests
from stockfish import Stockfish
import os

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/local/bin/stockfish")  # chemin du conteneur ou local
stockfish = Stockfish(path=STOCKFISH_PATH, depth=15)

LICHESS_API_BASE = "https://explorer.lichess.ovh/master"  # endpoint public Lichess Opening Explorer

class ChessService:
    @staticmethod
    def get_theoretical_moves(fen: str):
        """Récupère les coups théoriques depuis Lichess, fallback sur Stockfish si aucun trouvé"""
        # Valider FEN
        try:
            board = chess.Board(fen)
        except ValueError:
            return {"error": "FEN invalide"}

        # Appel Lichess Opening Explorer
        try:
            response = requests.get(LICHESS_API_BASE, params={"fen": fen}, timeout=5)
            if response.status_code == 200:
                data = response.json()
                moves = [m['san'] for m in data.get('moves', [])]
                if moves:  # Si on a trouvé des coups théoriques
                    return {"source": "lichess", "moves": moves}
        except requests.RequestException:
            pass  # On passe au fallback Stockfish

        # Fallback Stockfish
        stockfish.set_fen_position(fen)
        best_move = stockfish.get_best_move()
        return {"source": "stockfish", "moves": [best_move] if best_move else []}

    @staticmethod
    def evaluate_position(fen: str):
        """Évalue une position avec Stockfish"""
        try:
            board = chess.Board(fen)
        except ValueError:
            return {"error": "FEN invalide"}

        stockfish.set_fen_position(fen)
        evaluation = stockfish.get_evaluation()  # Retourne dict type {"type":"cp","value":20} ou {"type":"mate","value":3}
        return evaluation
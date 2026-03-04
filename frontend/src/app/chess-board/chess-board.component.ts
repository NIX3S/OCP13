import { Component, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { NgxChessBoardModule, NgxChessBoardView } from 'ngx-chess-board';
import { catchError } from 'rxjs/operators';
import {
  ChessService,
  ChessMove,
  TheoreticalMovesResponse,
  AgentRecommendation
} from '../services/chess.service';



interface AnalysisResponse {
  fen: string;
  opening: string;
  moves: { moves_info: { moves: string[] } };
  evaluation: { evaluation: { value: number } };
  videos: any[];
}
@Component({
  selector: 'app-chess-board',
  standalone: true,
  imports: [CommonModule, HttpClientModule, NgxChessBoardModule],
  templateUrl: './chess-board.component.html',
  styleUrls: ['./chess-board.component.scss']
})
export class ChessBoardComponent implements OnInit {
  @ViewChild('board', { static: false }) board!: NgxChessBoardView;

  fen = 'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1';
  theoreticalMoves: ChessMove[] = [];
  stockfishEval: any = null;
  loading = false;
  agentRecommendation: AgentRecommendation | null = null;

  constructor(private chessService: ChessService) {}

ngOnInit() {
  // Mock instantané
  this.mockData();
  
  // Analyse après board prêt
  setTimeout(() => {
    if (this.board) {
      this.fen = this.board.getFEN();
      console.log(' Init FEN:', this.fen.substring(0, 30) + '...');
      this.loadAnalysis();
    }
  }, 300);
}

resetBoard() {
  if (this.board) {
    this.board.reset();
    // FEN précis après reset
    setTimeout(() => {
      this.fen = this.board.getFEN();
      console.log(' Reset FEN:', this.fen.substring(0, 30) + '...');
      this.loadAnalysis();
    }, 100);
  }
}



onMoveChange(event: any) {
  if (!event?.move || !this.board) return;
  
  //  ATTEND que le board soit à jour + récupère VRAI FEN
  setTimeout(() => {
    this.fen = this.board.getFEN();  // FEN réel après coup
    console.log(' FEN mis à jour:', this.fen.substring(0, 30) + '...');
    this.loadAnalysis();  // Nouvelle analyse avec VRAI FEN
  }, 50);  // Délai pour board.update()
}
getAgentFirstMove(): string | null {
  return this.agentRecommendation?.moves?.moves?.[0] ?? null;  // "e7e5"
}

  loadAgentRecommendation() {
    const opening = this.guessOpeningFromFen(this.fen) || 'Unknown';
    this.chessService.getAgentRecommendation(this.fen, opening).subscribe({
      next: (rec) => {
        this.agentRecommendation = rec;
        console.log('Agent reçu:', rec);
      },
      error: (err) => {
        console.error('Agent KO:', err);
      }
    });
  }

  guessOpeningFromFen(fen: string): string {
    // Détection plus intelligente
    if (fen.includes('e4 e5')) return "King's Pawn Game";
    if (fen.includes('e4 c5')) return "Sicilian Defense"; 
    if (fen.includes('e4') && !fen.includes('e5')) return "Open Game";
    if (fen.includes('d4')) return "Queen's Pawn Game";
    if (fen.includes('e7e5')) return "e5 Response";
    return "Early Game";
  }


loadAnalysis() {
  this.loading = true;
  
  this.chessService.analyzePosition(this.fen).subscribe({
    next: (analysis: any) => {
      console.log(' Analyse:', analysis);
      
      // 1. Moves théoriques 
      this.theoreticalMoves = analysis.moves.moves.map((uci: string) => ({
        uci, whiteWins: 52
      }));
      
      // 2. Stockfish 
      this.stockfishEval = {
        score: Math.abs(analysis.evaluation.value) / 100,
        bestMove: analysis.moves.moves[0] || 'e7e5',
        raw: analysis.evaluation
      };
      
      // 3. Agent Recommendation TOUJOURS initialisé
      this.agentRecommendation = {
        fen: analysis.fen,
        opening: analysis.opening,
        moves: analysis.moves,
        context: [{
          opening: analysis.opening,
          content: `Théorie ${analysis.opening}`,
          score: 0.95
        }],
        videos: analysis.videos  // Vidéos du 1er appel (Chargement...)
      };
      
      // GESTION VIDÉOS INTELLIGENTE 
      if (analysis.videos[0]?.title === "Chargement...") {
        console.log(' Vidéos en chargement, refresh dans 1s...');
        setTimeout(() => {
          this.refreshVideosOnly();  
        }, 1000);
      }
      
      this.loading = false;
    },
    error: (err) => {
      console.error(' Analyse KO:', err);
      this.mockData();
      this.loading = false;
    }
  });
}

refreshVideosOnly() {
  if (!this.agentRecommendation) {
    console.error(' agentRecommendation null');
    return;
  }
  
  this.chessService.analyzePosition(this.fen).subscribe({
    next: (analysis) => {
      this.agentRecommendation!.videos = analysis.videos;
      console.log(' Vidéos chargées:', analysis.videos[0]?.title);
    },
    error: (err) => console.error('Refresh vidéos KO:', err)
  });
}




loadRealData() {
  this.loading = true;
  this.chessService.getTheoreticalMoves(this.fen).subscribe({
    next: (response: TheoreticalMovesResponse) => {
      this.theoreticalMoves = response.moves_info?.moves?.map((uci: string) => ({
        uci,
        whiteWins: 50
      })) || [];
      this.loading = false;
    },
    error: (err) => {
      console.error('❌ Backend KO:', err);
      this.mockData();
      this.loading = false;
    }
  });

  this.chessService.evaluatePosition(this.fen).subscribe({
    next: (response) => {
      this.stockfishEval = {
        score: Math.abs(response.evaluation.value) / 100, // -43 → 0.43
        bestMove: 'e7e5', 
        raw: response.evaluation
      };
      console.log('Stockfish:', this.stockfishEval);
    },
    error: (err) => {
      console.error('Eval KO:', err);
      this.stockfishEval = null;
    }
  });
}


  private mockData() {
    this.theoreticalMoves = [
      { uci: 'e7e5', whiteWins: 52 },
      { uci: 'c7c5', whiteWins: 48 },
      { uci: 'g8f6', whiteWins: 45 }
    ];
    this.stockfishEval = { score: 0.45, bestMove: 'e7e5' };
  }
}

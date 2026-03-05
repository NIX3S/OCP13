import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChessMove {
  uci: string;
  whiteWins: number;
}

export interface TheoreticalMovesResponse {
  fen: string;
  moves_info: {
    source: string;
    moves: string[];
  };
}

export interface Video {
  title: string;
  description: string;
  url: string;
  channel: string;
  published_at: string;
}

export interface ContextItem {
  opening: string;
  content: string;
  score: number;
}

export interface AgentRecommendation {
  fen: string;
  opening: string;
  moves: {
    source: string;
    moves: string[];
  };
  context: ContextItem[];
  videos: Video[];
  videosByContext?: {     
    context_opening: string;
    videos: Video[];
  }[]; 
}

@Injectable({
  providedIn: 'root'
})
export class ChessService {
  private apiUrl = 'http://localhost:8000/api/v1';

  constructor(private http: HttpClient) {}

  getTheoreticalMoves(fen: string): Observable<TheoreticalMovesResponse> {
    const encodedFen = encodeURIComponent(fen);
    console.log('🔥 API:', `${this.apiUrl}/moves/${encodedFen}`);
    return this.http.get<TheoreticalMovesResponse>(`${this.apiUrl}/moves/${encodedFen}`);
  }

  moveFen(fen: string, uci: string): Observable<{ new_fen: string }> {
    return this.http.post<{ new_fen: string }>(`${this.apiUrl}/move`, { fen, uci });
  }

  evaluatePosition(fen: string): Observable<any> {
    const encodedFen = encodeURIComponent(fen);
    return this.http.get(`${this.apiUrl}/evaluate/${encodedFen}`);
  }

  getAgentRecommendation(fen: string, opening: string): Observable<AgentRecommendation> {
    const encodedFen = encodeURIComponent(fen);
    const encodedOpening = encodeURIComponent(opening);
    return this.http.get<AgentRecommendation>(
      `${this.apiUrl}/agent/${encodedFen}/${encodedOpening}`
    );
  }
  analyzePosition(fen: string): Observable<any> {
  const encodedFen = encodeURIComponent(fen);
  return this.http.get(`${this.apiUrl}/analyze/${encodedFen}`);
}

}

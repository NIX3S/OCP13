import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NgxChessBoardModule } from 'ngx-chess-board';
import { ChessBoardComponent } from './chess-board/chess-board.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    NgxChessBoardModule,
    ChessBoardComponent
  ],
  template: `
    <div class="app">
      <app-chess-board></app-chess-board>
    </div>
  `,
  styles: [`
    .app {
      min-height: 100vh;
      padding: 1rem;
      box-sizing: border-box;
      background: #111827;
      color: #e5e7eb;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
  `]
})
export class AppComponent {}

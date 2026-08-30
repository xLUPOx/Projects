import { ChangeDetectionStrategy, Component, inject, OnInit } from '@angular/core';
import { Chat } from './chat';
import { MapView } from './map';
import { State } from './state';

@Component({
  selector: 'app-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [MapView, Chat],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  readonly state = inject(State);

  ngOnInit(): void {
    void this.state.load();
  }
}

import {
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { Chart } from './chart';
import { Chip } from './chip';
import { citedCodes, Line, segment } from './format';
import { State } from './state';
import { Message, Tree } from './types';

@Component({
  selector: 'app-chat',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Chip, Chart],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class Chat {
  readonly state = inject(State);

  private readonly conversation =
    viewChild<ElementRef<HTMLDivElement>>('conversation');
  private readonly box = viewChild<ElementRef<HTMLTextAreaElement>>('box');

  readonly draft = signal('');

  /**
   * Le quattro domande della demo, in difficolta' crescente.
   * L'etichetta corta serve a tenerle sempre a portata sopra la casella senza
   * rubare spazio alla conversazione; la domanda intera finisce nella casella.
   */
  readonly prompts = [
    {
      label: 'Conteggio',
      question: 'Quanti tigli ci sono nel quartiere Gries?',
    },
    {
      label: 'Rischio vicino a una scuola',
      question:
        'Alberi a rischio moderato o elevato non ispezionati da almeno 24 mesi entro 400 m dalla Scuola Primaria Gries',
    },
    {
      label: 'Norma di potatura',
      question: 'Ogni quanto va potato un platano secondo il regolamento?',
    },
    {
      label: 'Dato che non esiste',
      question: 'Qual è il valore economico stimato degli alberi di Oltrisarco?',
    },
  ];

  constructor() {
    // Segue lo stream: il testo cresce di continuo, la vista deve restare in fondo.
    effect(() => {
      this.state.messages();
      queueMicrotask(() => {
        const element = this.conversation()?.nativeElement;
        if (element) element.scrollTop = element.scrollHeight;
      });
    });
  }

  /**
   * Il testo gia' segmentato, ma solo per i messaggi finiti.
   *
   * Il template chiama `lines()` a ogni ciclo di rilevamento, e in una
   * conversazione lunga rifare la segmentazione di tutte le risposte a ogni
   * ciclo si sente. Mentre la risposta arriva pero' il testo cambia a ogni
   * token: metterlo in cache vorrebbe dire conservare una voce per ogni
   * prefisso, cioe' perdere memoria a ogni carattere. Durante lo stream si
   * rifa' il lavoro, a stream chiuso lo si ricorda.
   */
  private readonly parsed = new Map<string, Line[]>();

  lines(text: string, pending = false): Line[] {
    if (pending) return segment(text);
    let value = this.parsed.get(text);
    if (!value) {
      value = segment(text);
      this.parsed.set(text, value);
    }
    return value;
  }

  /**
   * Gli alberi da mostrare fra le fonti: solo quelli che la risposta nomina
   * davvero.
   *
   * Il backend manda tutti gli alberi toccati dai tool, e fa bene: servono ad
   * accendere la mappa. Ma una risposta come "questo dato non e' presente nel
   * catasto" non afferma niente su quei cinque alberi sondati, e mettergli
   * sotto una fila di targhette e' esattamente la citazione che non regge —
   * proprio il patto che le targhette esistono per garantire.
   */
  citedTrees(message: Message): Tree[] {
    const named = citedCodes(this.lines(message.text));
    return message.trees.filter((tree) => named.has(tree.id));
  }

  /** Gli argomenti del tool in chiaro: e' meta' della fiducia nella risposta. */
  readableArgs(args: Record<string, unknown>): string {
    const entries = Object.entries(args).filter(
      ([, value]) => value !== null && value !== undefined && value !== '',
    );
    if (!entries.length) return '';
    return entries
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${formatValue(value)}`)
      .join(' · ');
  }

  /** Le scorciatoie riempiono la casella: la domanda la manda comunque l'utente. */
  suggest(question: string): void {
    this.draft.set(question);
    this.box()?.nativeElement.focus();
  }

  send(question: string): void {
    if (!question.trim() || this.state.pending()) return;
    this.draft.set('');
    this.state.openArticle.set(null);
    void this.state.ask(question);
  }
}

function formatValue(value: unknown): string {
  return Array.isArray(value) ? value.join(', ') : String(value);
}

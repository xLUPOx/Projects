import { inject, Injectable, signal } from '@angular/core';
import { Api } from './api';
import { citedCodes, segment } from './format';
import { Article, Chart, Message, Place, Step, Tree } from './types';

/**
 * Stato condiviso fra chat e mappa.
 *
 * E' qui che vive il patto centrale dell'applicazione: la risposta e le feature
 * sulla mappa sono la stessa cosa vista due volte. `highlighted` e `selected`
 * sono scritti sia dalla chat sia dalla mappa, e letti da entrambe.
 */
@Injectable({ providedIn: 'root' })
export class State {
  private readonly api = inject(Api);

  readonly cadastre = signal<Tree[]>([]);
  readonly places = signal<Place[]>([]);
  readonly messages = signal<Message[]>([]);
  readonly pending = signal(false);
  readonly startupError = signal<string | null>(null);

  /** Alberi citati dall'ultima risposta: sulla mappa restano accesi, gli altri sbiadiscono. */
  readonly highlighted = signal<Set<string>>(new Set());
  /** Albero aperto: click su una targhetta in chat o su un punto in mappa. */
  readonly selected = signal<string | null>(null);
  /** Albero sotto il puntatore: anticipa la selezione senza committarla. */
  readonly hovered = signal<string | null>(null);
  /** Articolo del regolamento aperto in lettura. */
  readonly openArticle = signal<Article | null>(null);

  private aborter: AbortController | null = null;

  async load(): Promise<void> {
    // Prima si controlla *cosa* risponde, poi si scaricano i dati: cosi' l'errore
    // dice quale e' il problema invece di limitarsi a fallire.
    const status = await this.api.check();
    if (!status.ok) {
      this.startupError.set(status.reason);
      return;
    }

    try {
      const [cadastre, places] = await Promise.all([this.api.cadastre(), this.api.places()]);
      this.cadastre.set(cadastre);
      this.places.set(places);
      this.startupError.set(null);
    } catch (e) {
      this.startupError.set(`Il backend risponde ma i dati non arrivano: ${(e as Error).message}`);
    }
  }

  /**
   * Azzera la selezione e tutto cio' che ne dipende: il quadrante in testata,
   * la targhetta accesa in chat, il punto ingrandito sulla mappa.
   * E' un metodo e non tre `set` sparsi perche' dimenticarne uno lascia in
   * pagina un riferimento che non rimanda piu' a niente.
   */
  deselect(): void {
    this.selected.set(null);
    this.hovered.set(null);
  }

  findTree(id: string): Tree | undefined {
    return this.cadastre().find((t) => t.id === id);
  }

  stop(): void {
    this.aborter?.abort();
  }

  async ask(question: string): Promise<void> {
    if (!question.trim() || this.pending()) return;

    const history = this.messages()
      .filter((m) => !m.error)
      .map((m) => ({ role: m.role, text: m.text }));

    this.messages.update((m) => [
      ...m,
      empty('user', question),
      empty('assistant', '', true),
    ]);
    this.pending.set(true);
    this.highlighted.set(new Set());
    this.deselect();
    this.aborter = new AbortController();

    try {
      for await (const event of this.api.chat(question, history, this.aborter.signal)) {
        switch (event.type) {
          case 'status':
            this.updateLast((m) => ({
              ...m,
              steps: [
                ...m.steps,
                {
                  name: event.name,
                  label: event.text,
                  args: event.args,
                  done: false,
                },
              ],
            }));
            break;

          case 'tool':
            this.updateLast((m) => ({
              ...m,
              steps: closeStep(m.steps, event.name, event.result),
            }));
            break;

          case 'text':
            this.updateLast((m) => ({ ...m, text: m.text + event.delta }));
            break;

          case 'end':
            this.updateLast((m) => ({
              ...m,
              trees: event.trees,
              articles: event.articles,
              chart: event.chart,
            }));
            this.highlighted.set(
              highlightFor(this.lastText(), event.trees, event.chart),
            );
            break;

          case 'error':
            this.updateLast((m) => ({ ...m, error: event.message }));
            break;
        }
      }
    } catch (e) {
      const message =
        e instanceof DOMException && e.name === 'AbortError'
          ? 'Richiesta interrotta.'
          : `Connessione interrotta: ${(e as Error).message}`;
      this.updateLast((m) => ({ ...m, error: message }));
    } finally {
      this.updateLast((m) => ({ ...m, pending: false }));
      this.pending.set(false);
      this.aborter = null;
    }
  }

  private lastText(): string {
    const messages = this.messages();
    return messages.length ? messages[messages.length - 1].text : '';
  }

  private updateLast(transform: (m: Message) => Message): void {
    this.messages.update((messages) => {
      if (!messages.length) return messages;
      const copy = [...messages];
      copy[copy.length - 1] = transform(copy[copy.length - 1]);
      return copy;
    });
  }
}

/**
 * Gli alberi da accendere in mappa.
 *
 * La mappa segue la risposta, non la ricerca. Se il testo non nomina nemmeno un
 * albero — "questo dato non e' presente nel catasto" — quegli alberi il modello
 * li ha soltanto sondati per capire quali campi esistono: accenderli
 * significherebbe dire "guarda qui" indicando esemplari di cui la risposta non
 * afferma niente. Se invece ne cita anche uno solo si accendono tutti quelli
 * trovati, perche' li' l'elenco in chat e' troncato ma la mappa non deve esserlo.
 *
 * Il grafico vale quanto un codice citato: le barre sono un'affermazione su un
 * insieme preciso, solo aggregata invece che nominativa. Senza questa
 * eccezione una risposta fatta di solo grafico lascerebbe la mappa spenta
 * proprio quando ha piu' da mostrare.
 */
export function highlightFor(text: string, trees: Tree[], chart: Chart | null): Set<string> {
  const asserted = citedCodes(segment(text)).size > 0 || chart !== null;
  return asserted ? new Set(trees.map((t) => t.id)) : new Set();
}

function empty(role: 'user' | 'assistant', text: string, pending = false): Message {
  return { role, text, steps: [], trees: [], articles: [], chart: null, pending };
}

/** Chiude il primo passo ancora aperto con quel nome: i tool possono ripetersi. */
function closeStep(steps: Step[], name: string, result: string): Step[] {
  const index = steps.findIndex((s) => s.name === name && !s.done);
  if (index < 0) return steps;
  const copy = [...steps];
  copy[index] = { ...copy[index], result, done: true };
  return copy;
}

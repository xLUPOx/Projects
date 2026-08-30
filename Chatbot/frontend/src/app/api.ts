import { Injectable } from '@angular/core';
import { Place, StreamEvent, Tree } from './types';

/**
 * Porta del backend: 8000 di default, sovrascrivibile con ?api=8001 nell'URL.
 * Serve quando 8000 e' gia' occupata da un altro progetto in esecuzione.
 */
function port(): string {
  const requested = new URLSearchParams(location.search).get('api');
  return requested && /^\d{2,5}$/.test(requested) ? requested : '8000';
}

export const BASE = `http://127.0.0.1:${port()}`;

@Injectable({ providedIn: 'root' })
export class Api {
  /**
   * Verifica che su quella porta ci sia *questo* backend e non un altro.
   * Senza il controllo, un'altra app in ascolto su 8000 produce errori
   * incomprensibili invece di dire qual e' il problema.
   */
  async check(): Promise<{ ok: true } | { ok: false; reason: string }> {
    let data: Record<string, unknown>;
    try {
      const response = await fetch(`${BASE}/api/health`);
      data = await response.json();
    } catch {
      return {
        ok: false,
        reason: `Backend non raggiungibile su ${BASE}. Avvia uvicorn (vedi COMANDI.md) e ricarica la pagina.`,
      };
    }

    if (!('trees_loaded' in data)) {
      return {
        ok: false,
        reason: `Su ${BASE} risponde un'altra applicazione, non l'assistente del catasto. Ferma quel server, oppure avvia questo su un'altra porta e apri la pagina con ?api=<porta>.`,
      };
    }

    if (data['llm_configured'] === false) {
      return {
        ok: false,
        reason:
          'Il backend è attivo ma manca GEMINI_API_KEY: crea backend/.env a partire da .env.example e riavvia uvicorn.',
      };
    }

    return { ok: true };
  }

  async cadastre(): Promise<Tree[]> {
    const response = await fetch(`${BASE}/api/cadastre`);
    if (!response.ok) throw new Error(`Catasto non disponibile (${response.status})`);
    const geojson = await response.json();
    return geojson.features.map((f: { properties: Tree }) => f.properties);
  }

  async places(): Promise<Place[]> {
    const response = await fetch(`${BASE}/api/places`);
    if (!response.ok) throw new Error(`Luoghi non disponibili (${response.status})`);
    return response.json();
  }

  /**
   * Consuma lo stream SSE di /api/chat.
   *
   * EventSource non fa POST e la domanda va nel body, quindi lo stream lo
   * leggiamo a mano dal ReadableStream: il buffer accumula finche' non trova il
   * separatore di evento, perche' un chunk di rete puo' spezzare un JSON a meta'.
   *
   * Una libreria (`@microsoft/fetch-event-source`) farebbe questo parsing al
   * posto nostro, ma porta con se' riconnessione automatica e chiusura dello
   * stream quando la scheda passa in secondo piano: due comportamenti giusti
   * per un flusso di eventi riconnettibile e sbagliati qui, dove riconnettersi
   * rifa' la POST e quindi riesegue l'agente. Andrebbero spenti entrambi, e a
   * quel punto resterebbe solo il parsing di un formato che il nostro server
   * emette in una forma sola: `data: {json}` separato da riga vuota.
   */
  async *chat(
    question: string,
    history: { role: string; text: string }[],
    signal: AbortSignal,
  ): AsyncGenerator<StreamEvent> {
    const response = await fetch(`${BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Il backend ha risposto ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() ?? '';

      for (const block of blocks) {
        const line = block.trim();
        if (!line.startsWith('data:')) continue;
        yield JSON.parse(line.slice(5).trim()) as StreamEvent;
      }
    }
  }
}

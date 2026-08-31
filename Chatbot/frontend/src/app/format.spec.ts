/**
 * Test di `segment()`, l'unico punto del frontend dove una regressione non si
 * vede a occhio.
 *
 * Le targhette cliccabili sono la meta' visibile del patto sulla provenienza:
 * il backend decide quali articoli finiscono in "Fonti" (`_article_cited`), qui
 * si decide quali pezzi di testo diventano un riferimento. Se le due meta' non
 * concordano — "Art. 5" riconosciuto dentro "Art. 50", per dirne una — la
 * targhetta rimanda all'articolo sbagliato e nessuno se ne accorge finche' non
 * ci clicca sopra qualcuno.
 *
 *     npm test
 */
import { citedCodes, normalizeArticle, segment } from './format';

/** Solo i pezzi di un certo tipo, su tutte le righe: rende leggibili le attese. */
function values(text: string, kind: 'tree' | 'article'): string[] {
  return segment(text)
    .flatMap((line) => line.pieces)
    .filter((piece) => piece.kind === kind)
    .map((piece) => piece.value);
}

describe('segment', () => {
  it('isola i codici degli alberi', () => {
    expect(values('Vedi ALB-0042 e ALB-0007.', 'tree')).toEqual(['ALB-0042', 'ALB-0007']);
  });

  it('non scambia un articolo per un altro che ne condivide il prefisso', () => {
    // lo stesso confine che il backend applica in _article_cited
    expect(values('Vedi Art. 50 e Art. 5.', 'article')).toEqual(['Art. 50', 'Art. 5']);
    expect(values('Vedi Art. 15.', 'article')).toEqual(['Art. 15']);
  });

  it('riconosce Art.10 e Art. 10 come lo stesso riferimento', () => {
    expect(values('Art.10 e Art. 10', 'article')).toEqual(['Art. 10', 'Art. 10']);
    expect(normalizeArticle('Art.10')).toBe('Art. 10');
  });

  it('rende grassetto e corsivo senza lasciare gli asterischi a schermo', () => {
    const pieces = segment('Il **platano** e il *tiglio*.')[0].pieces;
    expect(pieces.filter((p) => p.kind === 'strong').map((p) => p.value)).toEqual(['platano']);
    expect(pieces.filter((p) => p.kind === 'emphasis').map((p) => p.value)).toEqual(['tiglio']);
    expect(pieces.map((p) => p.value).join('')).not.toContain('*');
  });

  it('riconosce un riferimento anche se il modello lo mette in grassetto', () => {
    // la stessa domanda, chiesta due volte, tornava una volta "ALB-0048" e una
    // volta "**ALB-0048**": la seconda forma non diventava una targhetta
    expect(values('- **ALB-0048** - Pino nero', 'tree')).toEqual(['ALB-0048']);
    expect(values('(classe C, **Art. 4**)', 'article')).toEqual(['Art. 4']);
    expect(values('(**Art.4**)', 'article')).toEqual(['Art. 4']);
  });

  it('estrae i riferimenti anche da dentro un grassetto piu lungo', () => {
    const pieces = segment('**ALB-0048 - Pino nero**')[0].pieces;
    expect(pieces.filter((p) => p.kind === 'tree').map((p) => p.value)).toEqual(['ALB-0048']);
    expect(pieces.map((p) => p.value).join('')).not.toContain('*');
  });

  it('lascia in grassetto cio che non e un riferimento', () => {
    const pieces = segment('Il **platano** e ALB-0001.')[0].pieces;
    expect(pieces.filter((p) => p.kind === 'strong').map((p) => p.value)).toEqual(['platano']);
    expect(pieces.filter((p) => p.kind === 'tree').map((p) => p.value)).toEqual(['ALB-0001']);
  });

  it('riconosce gli elenchi puntati', () => {
    const lines = segment('- ALB-0001\n* ALB-0002\ntesto');
    expect(lines.map((l) => l.bullet)).toEqual([true, true, false]);
  });

  it('non lascia mai i backtick a schermo e non interpreta cio che sta dentro', () => {
    // il prompt vieta i grafici in ASCII, ma se il modello li disegna lo stesso
    // la resa deve restare leggibile invece di sfaldarsi
    const lines = segment('prima\n```\nA ** 12\n```\ndopo');
    expect(lines.map((l) => l.code)).toEqual([false, true, false]);
    expect(lines[1].pieces[0].value).toBe('A ** 12');
    expect(lines.some((l) => l.pieces.some((p) => p.value.includes('```')))).toBe(false);
  });

  it('collassa le righe vuote e non ne apre una in testa', () => {
    expect(segment('\n\nprima\n\n\ndopo').map((l) => l.pieces.length > 0)).toEqual([
      true,
      false,
      true,
    ]);
  });
});

describe('citedCodes', () => {
  /** Come il footer delle fonti: gli alberi tornati dai tool, filtrati sul testo. */
  function sources(text: string, returned: string[]): string[] {
    const named = citedCodes(segment(text));
    return returned.filter((id) => named.has(id));
  }

  it('non cita gli alberi che la risposta non nomina', () => {
    // la ricerca a vuoto su Oltrisarco: cinque alberi sondati, nessuna
    // affermazione su di loro, quindi nessuna targhetta
    const text = "Questo dato non e' presente nel catasto.";
    expect(sources(text, ['ALB-0061', 'ALB-0138', 'ALB-0040'])).toEqual([]);
  });

  it('cita gli alberi nominati, nell ordine del catasto', () => {
    const text = '- ALB-0044\n- ALB-0117';
    expect(sources(text, ['ALB-0044', 'ALB-0085', 'ALB-0117'])).toEqual([
      'ALB-0044',
      'ALB-0117',
    ]);
  });

  it('conta come citato anche un codice scritto in grassetto', () => {
    expect(sources('- **ALB-0048** - Pino nero', ['ALB-0048'])).toEqual(['ALB-0048']);
  });

  it('distingue la risposta che cita dalla ricerca a vuoto', () => {
    // e' la stessa condizione che in state.ts decide se accendere la mappa:
    // nessun codice nel testo, nessun albero evidenziato
    expect(citedCodes(segment("Questo dato non e' presente nel catasto.")).size).toBe(0);
    expect(citedCodes(segment('Nel quartiere Gries: ALB-0044.')).size).toBe(1);
  });
});

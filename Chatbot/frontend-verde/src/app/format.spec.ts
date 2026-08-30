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
import { normalizeArticle, segment } from './format';

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

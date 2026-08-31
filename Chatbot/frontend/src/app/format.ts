/**
 * Trasforma il testo del modello in una struttura renderizzabile.
 *
 * Non e' un parser Markdown: serve solo a due cose. Riconoscere il minimo che il
 * modello produce (grassetto, corsivo, elenchi) e — soprattutto — isolare i
 * riferimenti (ALB-0042, Art. 10) perche' diventino targhette cliccabili invece
 * che testo morto. E' la provenienza a giustificare questo modulo, non lo stile.
 */

export type Piece =
  | { kind: 'text'; value: string }
  | { kind: 'strong'; value: string }
  | { kind: 'emphasis'; value: string }
  | { kind: 'tree'; value: string }
  | { kind: 'article'; value: string };

export interface Line {
  bullet: boolean;
  /** Riga dentro un recinto ``` : resa a spaziatura fissa, senza interpretazione. */
  code: boolean;
  pieces: Piece[];
}

// Regex per individuare: testo in grassetto (**testo**), corsivo (*testo*), riferimenti ALB-0000 e Art. n
const INLINE = /(\*\*[^*]+\*\*|\*[^*\n]+\*|ALB-\d{4}|Art\.\s?\d+)/g;

export function segment(text: string): Line[] {
  const lines: Line[] = [];
  let inCode = false;

  for (const raw of text.split('\n')) {
    const line = raw.trimEnd();

    // I recinti ``` non devono mai finire a schermo come backtick letterali.
    // Il prompt vieta al modello di disegnare grafici in ASCII, ma se lo fa
    // lo stesso la resa deve restare dignitosa invece di sfaldarsi.
    if (line.trimStart().startsWith('```')) {
      inCode = !inCode;
      continue;
    }

    if (inCode) {
      lines.push({ bullet: false, code: true, pieces: [{ kind: 'text', value: raw }] });
      continue;
    }

    // una riga vuota di stacco, mai due di fila, mai in apertura
    if (line === '') {
      const last = lines[lines.length - 1];
      if (!last || !last.pieces.length) continue;
    }

    const bullet = /^\s*[*-]\s+/.test(line);
    const content = bullet ? line.replace(/^\s*[*-]\s+/, '') : line;
    lines.push({ bullet, code: false, pieces: piecesOf(content) });
  }

  return lines;
}

function piecesOf(line: string): Piece[] {
  const pieces: Piece[] = [];

  for (const fragment of line.split(INLINE)) {
    if (!fragment) continue;

    if (/^ALB-\d{4}$/.test(fragment)) {
      pieces.push({ kind: 'tree', value: fragment });
    } else if (/^Art\.\s?\d+$/.test(fragment)) {
      pieces.push({ kind: 'article', value: normalizeArticle(fragment) });
    } else if (fragment.startsWith('**') && fragment.endsWith('**')) {
      pieces.push(...emphasized(fragment.slice(2, -2), 'strong'));
    } else if (fragment.startsWith('*') && fragment.endsWith('*') && fragment.length > 2) {
      pieces.push(...emphasized(fragment.slice(1, -1), 'emphasis'));
    } else {
      pieces.push({ kind: 'text', value: fragment });
    }
  }

  return pieces;
}

/**
 * Il contenuto di **grassetto** o *corsivo*, con i riferimenti che restano
 * riferimenti.
 *
 * Il modello scrive indifferentemente `ALB-0048` o `**ALB-0048**`, e senza
 * questo passaggio la seconda forma diventava testo in grassetto: stessa
 * risposta, elenco non cliccabile. Un codice e' sempre una targhetta, anche a
 * costo di perdere il grassetto — qui conta la provenienza, non lo stile.
 */
function emphasized(inner: string, kind: 'strong' | 'emphasis'): Piece[] {
  const parts = piecesOf(inner);
  if (!parts.some((p) => p.kind === 'tree' || p.kind === 'article')) {
    return [{ kind, value: inner }];
  }
  return parts;
}

/** "Art.10" e "Art. 10" devono corrispondere allo stesso riferimento del backend. */
export function normalizeArticle(reference: string): string {
  return reference.replace(/^Art\.\s*/, 'Art. ');
}

/**
 * I codici degli alberi che il testo nomina davvero.
 *
 * Il backend manda fra le fonti tutti gli alberi toccati dai tool, perche'
 * servono ad accendere la mappa. Ma una risposta come "questo dato non e'
 * presente nel catasto" non afferma niente sugli alberi che la ricerca ha
 * sondato: mettergli sotto una fila di targhette e' la citazione che non
 * regge, proprio cio' che le targhette dovrebbero escludere.
 */
export function citedCodes(lines: Line[]): Set<string> {
  return new Set(
    lines
      .flatMap((line) => line.pieces)
      .filter((piece) => piece.kind === 'tree')
      .map((piece) => piece.value),
  );
}

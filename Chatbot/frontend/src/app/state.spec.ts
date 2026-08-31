/**
 * Test di `highlightFor()`, che decide quali alberi si accendono in mappa.
 *
 * E' l'altra meta' del patto sulla provenienza, quella che `format.spec.ts`
 * non copre: li' si verifica cosa diventa una targhetta in chat, qui cosa si
 * accende sulla mappa. Le due decisioni condividono la stessa regola — un
 * albero solo sondato non e' una fonte — ma sono due funzioni diverse, ed e'
 * proprio perche' non erano mai state controllate insieme che un rifiuto
 * poteva restare corretto in chat e ambiguo in mappa senza che nessun test se
 * ne accorgesse.
 *
 *     npm test
 */
import { highlightFor } from './state';
import { Chart, Tree } from './types';

function tree(id: string): Tree {
  return {
    id,
    species: 'Tilia cordata',
    common_name: 'Tiglio',
    district: 'Gries',
    street: 'Via dei Tigli',
    risk_class: 'D',
    health_status: 'buono',
    last_inspection: '2023-10-24',
    months_since_inspection: 30,
    height_m: 12,
    protected: false,
    lat: 46.5,
    lng: 11.35,
  };
}

const chart: Chart = { title: 'Alberi per classe di rischio', subtitle: '', items: [] };

describe('highlightFor', () => {
  it('non accende nessun albero se il testo non ne nomina uno', () => {
    const trees = [tree('ALB-0001'), tree('ALB-0002')];
    const result = highlightFor('Questo dato non e\' presente nel catasto.', trees, null);
    expect(result.size).toBe(0);
  });

  it('accende tutti gli alberi trovati se il testo ne cita anche uno solo', () => {
    const trees = [tree('ALB-0001'), tree('ALB-0002'), tree('ALB-0003')];
    const result = highlightFor('Vedi **ALB-0001** fra gli altri.', trees, null);
    expect(result).toEqual(new Set(['ALB-0001', 'ALB-0002', 'ALB-0003']));
  });

  it('accende tutti gli alberi trovati se c\'e\' un grafico, anche senza codici nel testo', () => {
    const trees = [tree('ALB-0001'), tree('ALB-0002')];
    const result = highlightFor('Distribuzione per classe di rischio.', trees, chart);
    expect(result).toEqual(new Set(['ALB-0001', 'ALB-0002']));
  });

  it('non accende nulla se non ci sono ne codici ne grafico, anche con alberi nel payload', () => {
    const trees = [tree(`ALB-${'0'.repeat(4)}`)];
    const result = highlightFor('Nel quartiere Gries sono presenti 6 tigli.', trees, null);
    expect(result.size).toBe(0);
  });
});

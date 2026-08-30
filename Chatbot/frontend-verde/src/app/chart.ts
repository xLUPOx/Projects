import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { Chart as ChartData } from './types';

interface Bar {
  key: string;
  count: number;
  percent: number;
  color: string;
  border: string;
}

/**
 * Il pannello di sintesi che segue la chat.
 *
 * Barre orizzontali perche' il lavoro del dato e' il confronto di grandezze fra
 * categorie con etichette lunghe (nomi di specie, di quartiere). Il colore lo
 * usiamo solo quando porta informazione: sulle classi di rischio, che hanno una
 * scala ordinata propria. Per ogni altro raggruppamento le barre sono di un solo
 * tono — l'identita' la porta gia' l'etichetta, ripeterla in hue sarebbe rumore.
 */
@Component({
  selector: 'app-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <figure>
      <figcaption>
        <span class="heading">
          <b>{{ data().title }}</b>
          @if (data().subtitle) {
            <span class="filters">{{ data().subtitle }}</span>
          }
        </span>
        <span class="total">{{ total() }} alberi</span>
      </figcaption>

      <ul>
        @for (bar of bars(); track bar.key) {
          <li>
            <span class="label" [title]="bar.key">{{ bar.key }}</span>
            <span class="track">
              <span
                class="bar"
                [style.width.%]="bar.percent"
                [style.background]="bar.color"
                [style.border-color]="bar.border"
              ></span>
            </span>
            <span class="value">{{ bar.count }}</span>
          </li>
        }
      </ul>
    </figure>
  `,
  styles: `
    figure {
      margin: 0;
    }

    figcaption {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 11px;
    }

    /* Titolo in tondo e filtri sotto: in maiuscoletto spaziato una riga come
       "alberi per classe rischio - a gries-san quirino - classe c/d - non
       ispezionati da 24 mesi" andava a capo ed era illeggibile. */
    .heading {
      display: grid;
      gap: 1px;
      min-width: 0;
    }

    .heading b {
      font-family: var(--font-display);
      font-size: 14px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }

    .filters {
      font-size: 11.5px;
      line-height: 1.35;
      color: var(--ink-faint);
    }

    .total {
      flex: none;
      font-family: var(--font-data);
      font-size: 11px;
      color: var(--ink-faint);
    }

    ul {
      display: grid;
      gap: 5px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    li {
      display: grid;
      grid-template-columns: minmax(56px, 27%) 1fr 34px;
      align-items: center;
      gap: 9px;
    }

    .label {
      overflow: hidden;
      font-size: 12px;
      color: var(--ink-soft);
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .track {
      height: 12px;
      border-bottom: 1px solid var(--rule);
    }

    .bar {
      display: block;
      height: 11px;
      border: 1px solid;
      /* estremita' arrotondata solo in punta: la barra resta ancorata all'asse */
      border-radius: 0 2px 2px 0;
      transition: width 320ms cubic-bezier(0.2, 0.7, 0.3, 1);
    }

    .value {
      font-family: var(--font-data);
      font-size: 12px;
      text-align: right;
      color: var(--ink);
      font-variant-numeric: tabular-nums;
    }
  `,
})
export class Chart {
  readonly data = input.required<ChartData>();

  readonly total = computed(() =>
    this.data().items.reduce((sum, i) => sum + i.count, 0),
  );

  readonly bars = computed<Bar[]>(() => {
    const items = this.data().items;
    const max = Math.max(...items.map((i) => i.count), 1);
    const byRisk = items.every((i) => ['A', 'B', 'C', 'D'].includes(i.key));

    return items.map((i) => ({
      key: i.key,
      count: i.count,
      percent: Math.max((i.count / max) * 100, 1.5),
      color: byRisk ? `var(--class-${i.key.toLowerCase()})` : 'var(--moss-light)',
      border: byRisk ? `var(--class-${i.key.toLowerCase()}-border)` : 'var(--moss)',
    }));
  });
}

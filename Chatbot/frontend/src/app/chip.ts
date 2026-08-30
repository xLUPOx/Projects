import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { State } from './state';

/**
 * La targhetta.
 *
 * E' l'elemento firma dell'interfaccia e non e' un vezzo: nel rilievo arboreo
 * ogni esemplare porta una targhetta di alluminio punzonata inchiodata al fusto,
 * ed e' quella a rendere il dato verificabile in campo. Qui fa lo stesso lavoro:
 * ogni affermazione dell'assistente e' agganciata al codice della sua fonte, e il
 * codice e' cliccabile. Se una frase non ha targhetta, non ha fonte.
 */
@Component({
  selector: 'app-chip',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      type="button"
      class="plate"
      [class.article]="kind() === 'article'"
      [class.active]="active()"
      [class.unknown]="kind() === 'tree' && !tree()"
      [style.--class-color]="color()"
      [attr.aria-label]="description()"
      (click)="open()"
      (mouseenter)="hover(true)"
      (mouseleave)="hover(false)"
      (focus)="hover(true)"
      (blur)="hover(false)"
    >
      <span class="hole" aria-hidden="true"></span>
      <span class="code">{{ code() }}</span>
    </button>
  `,
  styles: `
    .plate {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 1px 7px 1px 5px;
      border: 1px solid var(--rule-strong);
      border-left: 3px solid var(--class-color, var(--rule-strong));
      border-radius: 2px;
      background: linear-gradient(180deg, #f7f9f5, #e6eae2);
      font-family: var(--font-data);
      font-size: 0.86em;
      font-weight: 500;
      letter-spacing: 0.01em;
      line-height: 1.5;
      white-space: nowrap;
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
    }

    .plate:hover,
    .plate.active {
      background: linear-gradient(180deg, #ffffff, #eef2ec);
      box-shadow: 0 1px 0 var(--rule-strong), 0 2px 6px -2px rgb(24 36 32 / 0.35);
      transform: translateY(-1px);
    }

    .plate.active {
      border-color: var(--ink);
    }

    /* Il foro del chiodo: e' cio' che la fa leggere come targhetta e non come chip. */
    .hole {
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: var(--paper-etched);
      box-shadow: inset 0 0 0 1px var(--rule-strong);
    }

    .article {
      border-left-style: dashed;
      background: linear-gradient(180deg, #f6f8f8, #e4ebea);
    }

    .unknown {
      opacity: 0.55;
      cursor: default;
    }

    .code {
      color: var(--ink);
    }
  `,
})
export class Chip {
  private readonly state = inject(State);

  readonly code = input.required<string>();
  readonly kind = input<'tree' | 'article'>('tree');

  readonly tree = computed(() => this.state.findTree(this.code()));

  readonly active = computed(() => {
    if (this.kind() === 'article') {
      return this.state.openArticle()?.reference === this.code();
    }
    return this.state.selected() === this.code() || this.state.hovered() === this.code();
  });

  readonly color = computed(() => {
    const tree = this.tree();
    return tree ? `var(--class-${tree.risk_class.toLowerCase()})` : '';
  });

  readonly description = computed(() => {
    const tree = this.tree();
    if (this.kind() === 'article') return `Apri ${this.code()} del regolamento`;
    if (!tree) return `${this.code()}: non presente nel catasto caricato`;
    return `${tree.common_name} ${tree.id}, classe ${tree.risk_class}, ${tree.district}`;
  });

  open(): void {
    if (this.kind() === 'article') {
      const article = this.state.articles().find((a) => a.reference === this.code());
      this.state.openArticle.set(article ?? null);
      return;
    }
    if (this.tree()) this.state.selected.set(this.code());
  }

  hover(inside: boolean): void {
    if (this.kind() !== 'tree' || !this.tree()) return;
    this.state.hovered.set(inside ? this.code() : null);
  }
}

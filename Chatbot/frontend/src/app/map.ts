import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  effect,
  ElementRef,
  inject,
  OnDestroy,
  viewChild,
} from '@angular/core';
import * as L from 'leaflet';
import { State } from './state';
import { Place, Tree } from './types';

const CENTER: L.LatLngExpression = [46.4933, 11.3398];

/**
 * La mappa e' la seconda faccia della risposta.
 *
 * Quando arriva un risultato, gli alberi citati restano accesi e tutto il resto
 * del catasto sbiadisce: si vede subito *dove* vale l'affermazione, non solo che
 * e' stata fatta. Il puntamento va nei due sensi — targhetta in chat -> punto in
 * mappa, e punto in mappa -> targhetta in chat.
 */
@Component({
  selector: 'app-map',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="canvas" #canvas></div>

    <figure class="legend">
      <figcaption class="eyebrow">Propensione al cedimento</figcaption>
      <ul>
        @for (entry of legend; track entry.class) {
          <li>
            <span class="dot" [style.background]="'var(--class-' + entry.lower + ')'"></span>
            <b>{{ entry.class }}</b>
            <span>{{ entry.description }}</span>
          </li>
        }
      </ul>
    </figure>
  `,
  styles: `
    :host {
      position: relative;
      display: block;
      height: 100%;
    }

    .canvas {
      height: 100%;
    }

    .legend {
      position: absolute;
      left: 16px;
      bottom: 22px;
      z-index: 500;
      margin: 0;
      padding: 10px 13px 11px;
      border: 1px solid var(--rule);
      border-radius: var(--radius);
      background: rgb(244 246 242 / 0.94);
      backdrop-filter: blur(3px);
      box-shadow: var(--shadow);
    }

    .legend ul {
      display: grid;
      gap: 3px;
      margin: 7px 0 0;
      padding: 0;
      list-style: none;
    }

    .legend li {
      display: grid;
      grid-template-columns: 10px 12px auto;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--ink-soft);
    }

    .legend b {
      font-family: var(--font-data);
      font-size: 11px;
      color: var(--ink);
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
  `,
})
export class MapView implements AfterViewInit, OnDestroy {
  private readonly state = inject(State);
  private readonly canvasRef = viewChild.required<ElementRef<HTMLDivElement>>('canvas');

  private map?: L.Map;
  private readonly circles = new Map<string, L.CircleMarker>();
  private placesDrawn = false;
  private observer?: ResizeObserver;
  /* Una sola tela condivisa da tutti i punti. Crearne una per marker significa
     140 canvas sovrapposti, ognuno grande quanto la mappa: solo quello in cima
     riceve i click, e gli altri 139 alberi risultano non cliccabili. */
  private readonly renderer = L.canvas({ padding: 0.5 });

  readonly legend = [
    { class: 'A', lower: 'a', description: 'trascurabile' },
    { class: 'B', lower: 'b', description: 'bassa' },
    { class: 'C', lower: 'c', description: 'moderata' },
    { class: 'D', lower: 'd', description: 'elevata' },
  ];

  constructor() {
    effect(() => {
      const trees = this.state.cadastre();
      const places = this.state.places();
      if (!this.map) return;
      this.drawTrees(trees);
      this.drawPlaces(places);
    });

    effect(() => {
      const highlighted = this.state.highlighted();
      const selected = this.state.selected();
      const hovered = this.state.hovered();
      if (!this.map) return;
      for (const [id, circle] of this.circles) {
        circle.setStyle(this.styleFor(id, highlighted, selected, hovered));
        if (id === selected || id === hovered) circle.bringToFront();
      }
    });

    effect(() => {
      const selected = this.state.selected();
      const circle = selected ? this.circles.get(selected) : undefined;
      if (!this.map || !circle) return;
      this.map.flyTo(circle.getLatLng(), Math.max(this.map.getZoom(), 16), {
        duration: 0.6,
      });
      circle.openPopup();
    });
  }

  ngAfterViewInit(): void {
    this.map = L.map(this.canvasRef().nativeElement, {
      center: CENTER,
      zoom: 13,
      zoomControl: false,
      attributionControl: true,
    });

    L.control.zoom({ position: 'topright' }).addTo(this.map);
    // Tessere OpenStreetMap: non richiedono chiave. Il basemap di CARTO, piu'
    // adatto come tono, adesso la pretende e stampa "API KEY REQUIRED" sopra la
    // mappa. La desaturazione la fa il CSS (.leaflet-tile-pane), cosi' il colore
    // forte resta quello dei dati.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap — dati alberi dimostrativi',
      maxZoom: 19,
    }).addTo(this.map);

    this.drawTrees(this.state.cadastre());
    this.drawPlaces(this.state.places());

    // Chiudere il popup — con la X, con Esc o cliccando sulla mappa — deve
    // spegnere anche la selezione. Il controllo sul popup evita l'autogol:
    // aprire il popup di B chiude quello di A, e senza il confronto la
    // selezione di B verrebbe cancellata nell'istante in cui nasce.
    this.map.on('popupclose', (event: L.PopupEvent) => {
      const selected = this.state.selected();
      if (!selected) return;
      if (this.circles.get(selected)?.getPopup() !== event.popup) return;
      this.state.deselect();
    });

    // Leaflet calcola le dimensioni una volta sola: se il contenitore cambia
    // (finestra ridimensionata, banner di errore che compare) va avvisato,
    // altrimenti resta una fascia grigia al posto delle tessere mancanti.
    this.observer = new ResizeObserver(() => this.map?.invalidateSize());
    this.observer.observe(this.canvasRef().nativeElement);
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
    this.map?.remove();
  }

  private drawTrees(trees: Tree[]): void {
    if (!this.map || !trees.length || this.circles.size) return;

    for (const tree of trees) {
      const circle = L.circleMarker([tree.lat, tree.lng], {
        renderer: this.renderer,
        ...this.styleFor(tree.id, this.state.highlighted(), null, null),
      })
        .bindPopup(this.popupCard(tree))
        .on('click', () => this.state.selected.set(tree.id))
        .on('mouseover', () => this.state.hovered.set(tree.id))
        .on('mouseout', () => this.state.hovered.set(null))
        .addTo(this.map);

      this.circles.set(tree.id, circle);
    }
  }

  private drawPlaces(places: Place[]): void {
    // L'effect che chiama questo metodo ri-parte a ogni cambio di stato dei dati:
    // senza guardia i segnaposto si accatasterebbero uno sull'altro.
    if (!this.map || !places.length || this.placesDrawn) return;
    this.placesDrawn = true;
    for (const place of places) {
      L.marker([place.lat, place.lng], {
        icon: L.divIcon({
          className: '',
          html: `<span class="place-marker" title="${place.name}">${place.type[0].toUpperCase()}</span>`,
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        }),
        interactive: true,
      })
        .bindPopup(`<b>${place.name}</b><br><span>${place.type}</span>`)
        .addTo(this.map);
    }
  }

  private styleFor(
    id: string,
    highlighted: Set<string>,
    selected: string | null,
    hovered: string | null,
  ): L.CircleMarkerOptions {
    const tree = this.state.findTree(id);
    const color = classColor(tree?.risk_class ?? 'A');
    const filterActive = highlighted.size > 0;
    const lit = !filterActive || highlighted.has(id);
    const pointed = id === selected || id === hovered;

    return {
      radius: pointed ? 9 : lit && filterActive ? 6.5 : 4.5,
      // Il bordo scuro e' quello che rende leggibile l'ocra della classe B,
      // che come riempimento non arriva a 3:1 sul fondo chiaro.
      color: pointed ? '#182420' : color.border,
      weight: pointed ? 2 : lit ? 1.25 : 0.5,
      opacity: lit ? 1 : 0.25,
      fillColor: color.fill,
      fillOpacity: lit ? 0.85 : 0.12,
    };
  }

  private popupCard(tree: Tree): string {
    const protectedNote = tree.protected ? '<br><b>Esemplare tutelato</b>' : '';
    return `
      <div style="font-family: var(--font-body)">
        <div style="font-family: var(--font-data); font-size: 12px">${tree.id}</div>
        <b>${tree.common_name}</b> <i>${tree.species}</i><br>
        ${tree.street}, ${tree.district}<br>
        Classe ${tree.risk_class} &middot; ${tree.health_status}<br>
        Ultima ispezione: ${tree.last_inspection} (${tree.months_since_inspection} mesi fa)${protectedNote}
      </div>`;
  }
}

const COLORS: Record<string, { fill: string; border: string }> = {
  A: { fill: '#2f7d52', border: '#1d5335' },
  B: { fill: '#d0a80e', border: '#8a6f07' },
  C: { fill: '#d94f14', border: '#94330a' },
  D: { fill: '#93273f', border: '#631a2a' },
};

function classColor(riskClass: string): { fill: string; border: string } {
  return COLORS[riskClass] ?? COLORS['A'];
}

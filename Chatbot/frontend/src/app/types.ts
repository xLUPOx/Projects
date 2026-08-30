export type RiskClass = 'A' | 'B' | 'C' | 'D';

export interface Tree {
  id: string;
  species: string;
  common_name: string;
  district: string;
  street: string;
  risk_class: RiskClass;
  health_status: string;
  last_inspection: string;
  months_since_inspection: number;
  height_m: number;
  protected: boolean;
  lat: number;
  lng: number;
}

export interface Place {
  name: string;
  type: string;
  lat: number;
  lng: number;
}

export interface Article {
  reference: string;
  title: string;
  text: string;
  source: string;
  relevance: number;
}

export interface Chart {
  title: string;
  /** I filtri applicati, in chiaro: dice su quali alberi e' stato contato. */
  subtitle: string;
  items: { key: string; count: number }[];
}

/** Un passo dell'agente, mostrato in chat mentre avviene. */
export interface Step {
  name: string;
  label: string;
  args: Record<string, unknown>;
  result?: string;
  done: boolean;
}

export interface Message {
  role: 'user' | 'assistant';
  text: string;
  steps: Step[];
  trees: Tree[];
  articles: Article[];
  chart: Chart | null;
  error?: string;
  pending: boolean;
}

/** Eventi dello stream SSE del backend. */
export type StreamEvent =
  | { type: 'status'; name: string; text: string; args: Record<string, unknown> }
  | { type: 'tool'; name: string; args: Record<string, unknown>; result: string }
  | { type: 'text'; delta: string }
  | {
      type: 'end';
      trees: Tree[];
      articles: Article[];
      chart: Chart | null;
      tools_used: string[];
    }
  | { type: 'error'; message: string };

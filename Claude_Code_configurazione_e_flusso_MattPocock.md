# Claude Code: configurazione coerente e flusso di sviluppo con le skills di Matt Pocock

Oct 7, 2026 · @Matteo

Tieni CLAUDE.md quasi vuoto, sposta le procedure nelle skills, i divieti negli hooks, e sviluppa con il flusso di Pocock: grill, spec, ticket, implementazione test-first, review, retro. Il documento contiene solo decisioni e il modo di applicarle: la Parte 1 configura e mantiene Claude Code, la Parte 2 descrive come sviluppare, la checklist dice da dove partire. Video e fonti sono in fondo.

Chiavi e comandi sono stati ricontrollati il 7 ottobre 2026 sulla documentazione ufficiale di Claude Code e sulla repo di Pocock alla versione 1.3.1. Nulla è stato eseguito: cosa è verificato e cosa è solo riportato dai video è scritto nei limiti, in fondo.

## Indice

- **Per orientarsi**
  - [Le regole in sintesi](#le-regole-in-sintesi)
- **Parte 1 · Configurare e mantenere Claude Code**
  - [Cosa va dove](#parte-1--cosa-va-dove): CLAUDE.md, skills, hooks, esempi minimi, codebase grandi
  - [La base da configurare](#parte-1--la-base-da-configurare): file, permessi, sandbox, status line, compattazione, subagent, browser, settings di partenza, CI
  - [Skills, plugin e MCP: il set consigliato](#parte-1--skills-plugin-e-mcp-il-set-consigliato)
  - [Hooks: come usarli bene](#parte-1--hooks-come-usarli-bene)
  - [Impostazioni consigliate](#parte-1--impostazioni-consigliate): comandi, chiavi, auto mode, modelli, contesto, prompt
  - [Le preferenze tue e del team](#parte-1--le-preferenze-tue-e-del-team): lingua, stile, docstring, git, changelog
  - [Le decisioni di configurazione](#parte-1--le-decisioni-di-configurazione)
- **Parte 2 · Sviluppare**
  - [Il flusso di sviluppo con le skills di Pocock](#parte-2--il-flusso-di-sviluppo-con-le-skills-di-pocock), con [le decisioni sul processo](#le-decisioni-sul-processo)
  - [intent.md e la catena di artefatti](#parte-2--intentmd-e-la-catena-di-artefatti)
  - [Cosa aggiungere da Karpathy e da Cole Medin](#parte-2--cosa-aggiungere-da-karpathy-e-da-cole-medin)
  - [Lavoro autonomo: loop, verifiche e sessioni parallele](#parte-2--lavoro-autonomo-loop-verifiche-e-sessioni-parallele)
  - [Jev e le alternative open source](#jev-e-le-alternative-open-source)
- **Da usare subito**
  - [Checklist di avvio](#checklist-di-avvio)
- **Appendice**
  - [Video analizzati](#video-analizzati)
  - [Limiti di questo report](#limiti-di-questo-report)
  - [Fonti](#fonti)

## Le regole in sintesi

Tredici decisioni, ordinate per impatto. Ognuna è spiegata più sotto.

1. **CLAUDE.md quasi vuoto.** Tieni solo ciò che è insieme non ricavabile dal codice e valido in ogni sessione. Per ogni riga chiediti: "Claude l'avrebbe capito da solo?". Se sì, cancellala. Il tetto ufficiale è 200 righe per file; l'obiettivo è molto meno.
2. **Procedure nelle skills, divieti negli hooks.** Una regola in CLAUDE.md è un consiglio; un hook è una garanzia. Ciò che deve valere al 100% diventa hook, lint o controllo in CI.
3. **Push e segreti fuori dalla portata dell'agente.** Il guardrail git blocca ogni `git push`: lo fai tu. I file con i segreti si chiudono con regole `deny` e con la sandbox, non con una frase in CLAUDE.md.
4. **MCP solo quando Claude non può arrivarci in altro modo.** A parità di funzione preferisci una CLI più una skill: non aggiunge un server di cui fidarti. Gli strumenti MCP oggi si caricano su richiesta, quindi il divario di costo si è ridotto.
5. **Non lanciare il vecchio `/init`.** Il nuovo init a intervista è utilizzabile, ma contesta ogni riga che propone prima di accettarla.
6. **Rifai la pulizia a ogni nuovo modello** con `/doctor prompt-audit`. Le istruzioni scritte per correggere un modello vecchio peggiorano quello nuovo.
7. **Effort medio di default.** Su Opus 5.5 e Sonnet 5.5 lo è già; su Fable 5.1 prova `low`. Alzalo per un singolo compito difficile, mai fisso su `xhigh`.
8. **Modello forte per pianificare e giudicare, modello più economico per eseguire.** Il modello forte è quello a cui punta l'alias `best`: Fable dove è disponibile, altrimenti Opus. Il nodo che fa la review non si risparmia mai.
9. **Chi costruisce non verifica.** La review la fa un agente diverso, a contesto pulito. I test si scrivono prima del codice, uno alla volta, nei punti concordati con te.
10. **Allineati prima di scrivere codice.** Ogni funzionalità parte da `/grill-with-docs`, non dalla plan mode. Una correzione piccola e già chiara si chiede direttamente, con il criterio di successo scritto.
11. **Grilling, spec e ticket nella stessa finestra; poi una sessione per ticket.** Resta sotto circa 150k token, da tenere a vista nella status line; ai confini di fase segui l'ordine continua, `/clear`, `/handoff`, subagent, `/compact`.
12. **Niente loop sull'MVP e niente piani enormi.** I loop servono per funzionalità ripetibili con un punteggio verificabile; le mappe grandi invecchiano prima di essere finite.
13. **Usa i nomi attuali delle skills.** `GLOSSARY.md` (non più `CONTEXT.md`), `/to-spec` (non `/to-prd`), `/to-tickets` (non `/to-issues`), `/writing-for-agents`.

## Parte 1 · Cosa va dove

Ogni cosa che vuoi insegnare a Claude ha un solo posto giusto, e il criterio è quando viene caricata nel contesto. Scegli sempre il meccanismo più economico che risolve il problema.

| Il problema | Dove metterlo | Quando si carica | Costo |
| --- | --- | --- | --- |
| L'istruzione era poco chiara | Nel prompt | Solo quella volta | Nullo |
| Claude deve saperlo in ogni sessione e non può scoprirlo | `CLAUDE.md` alla radice | A ogni avvio, per tutta la sessione | Pagato a ogni turno |
| Vale solo in una parte del progetto | `CLAUDE.md` nella sottocartella | Quando Claude legge un file lì | Basso |
| Vale solo per certi tipi di file | Regola in `.claude/rules/` con il campo `paths` | Quando Claude lavora su file che corrispondono | Basso |
| Lo stai spiegando per la quinta volta | Skill | La descrizione sempre, il corpo solo quando serve. Se la skill è solo invocabile da te, nemmeno la descrizione | Quasi nullo finché non usata |
| Deve succedere sempre, senza eccezioni | Hook, regola di lint o controllo in CI | A ogni evento | Nullo sul contesto |
| L'informazione sta dove Claude non arriva | MCP, o meglio CLI più skill | MCP: definizioni caricate su richiesta, con il tool search attivo di default. CLI: solo all'uso | MCP medio, CLI basso |
| Lavoro isolato che sporcherebbe il contesto | Subagent | Contesto proprio; torna solo il risultato | Token extra, contesto pulito |
| Stesso setup per tutto il team | Plugin | Come i suoi componenti | Come i suoi componenti |

### CLAUDE.md

- **Cosa resta.** Le cose che farebbero inciampare un agente e che non si leggono dal codice: una particolarità dell'ambiente, una convenzione non scritta, il motivo di una scelta. Il CLAUDE.md globale di Pocock è una riga sola, sull'ambiente WSL; quello della sua repo di skills è di una trentina di righe, tutte convenzioni che il codice non dichiara.
- **Cosa esce.** Elenchi di comandi già in `package.json`, descrizioni dell'architettura, riferimenti a file e servizi, pattern di implementazione. Si ricavano dal codice e invecchiano al primo rename.
- **Frasi che non cambiano nulla.** "Scrivi codice pulito e leggibile" è un no-op: cancellala.
- **Dimensione.** La documentazione ufficiale indica meno di 200 righe per file, perché file più lunghi vengono seguiti peggio. Gli import con `@percorso` aiutano a organizzare ma non riducono il costo: si caricano comunque all'avvio.
- **Coerenza.** Se due istruzioni si contraddicono, Claude ne sceglie una in modo arbitrario. Vale anche tra CLAUDE.md, file nelle sottocartelle e regole.
- **Monorepo.** Un CLAUDE.md per sottocartella, oppure regole in `.claude/rules/` limitate a certi percorsi.
- **Più agenti nello stesso repo.** Da Claude Code 2.1.277 un `AGENTS.md` viene letto direttamente, ma solo se non esiste alcun CLAUDE.md. Se esistono entrambi viene letto solo CLAUDE.md: tieni un solo file vero e fai dell'altro un import (`@AGENTS.md`) o un link simbolico, come fa Pocock nella sua repo.
- **Come lo usa `/retro`.** CLAUDE.md va usato "con estrema parsimonia", di norma solo per puntatori ad altri file. Gli standard di codice stanno in `CODING_STANDARDS.md`, che viene letto in fase di review e non durante l'implementazione.

### Skills

- **Solo ciò che è specifico tuo o del team.** Le buone pratiche generiche Claude le conosce già.
- **File principale corto.** Tieni sotto le 500 righe `SKILL.md`, con il dettaglio in file di riferimento accanto: è il tetto, e sotto le 200 è meglio. Quelle di Pocock vanno da 7 a 170 righe.
- **Invocate da te o dal modello.** Con `disable-model-invocation: true` la skill si attiva solo quando la digiti e la sua descrizione non entra nel contesto. Nella repo di Pocock 16 skills su 27 sono così: per questo installarle tutte costa poco.
- **Leggi una skill per intero prima di usarla.** Lo raccomanda Pocock, e i suoi file sono brevi.
- **Controlla le skills di terzi prima di installarle.** Una skill è un file di istruzioni di cui l'agente si fida.
- **Attenzione ai nomi.** Una skill tua o di progetto con lo stesso nome di un comando integrato lo sostituisce, ma non ne sostituisce gli alias. Succede con `code-review`: installata come file, la skill di Pocock prende il posto di `/code-review` e la review integrata resta raggiungibile solo come `/review`. Le skills di un plugin hanno invece il prefisso del plugin e convivono con quelle integrate.

### Hooks

Si configurano in `.claude/settings.json`, con gli script in `.claude/hooks/`. Un hook `PreToolUse` sul tool `Bash` che esce con codice 2 blocca il comando e restituisce il messaggio a Claude, che riprova nel modo giusto. Quattro usi che valgono subito; la sezione dedicata più sotto spiega eventi, regole e hook già pronti:

- **Imporre la CLI giusta**, per esempio `pnpm` al posto di `npm`, invece di scriverlo in CLAUDE.md.
- **Bloccare i comandi git distruttivi.** La repo di Pocock include la skill `git-guardrails-claude-code`, che installa un hook contro `git push`, `git reset --hard`, `git clean -f`, `git branch -D`, `git checkout .` e `git restore .`. Blocca ogni push, anche verso un ramo di lavoro: il push resta a te. Lo script confronta il testo del comando con un elenco di pattern, che durante l'installazione puoi allungare o accorciare. Non fa parte del plugin: si installa con `npx skills@latest add mattpocock/skills --skill=git-guardrails-claude-code`.
- **Filtrare l'output dei test**, lasciando nel contesto solo quelli falliti.
- **Impedire la chiusura finché un controllo non passa**, con un hook di stop.

Non serve scriverli a mano: chiedi a Claude Code di convertire in hook le istruzioni deterministiche del tuo CLAUDE.md, fatti mostrare l'elenco prima, e provali: le modifiche ai settings valgono senza riavviare.

### Quattro esempi minimi

Una regola che vale solo per certi file, in `.claude/rules/api.md`. Senza il campo `paths` la regola si carica sempre:

```markdown
---
paths:
  - "src/api/**/*.ts"
---

- Ogni endpoint valida l'input.
- Gli errori usano il formato di risposta standard.
```

Un subagent, in `.claude/agents/code-reviewer.md`. Il frontmatter lo configura e il corpo è il suo prompt di sistema: oltre alla cartella di lavoro, non riceve altro.

```markdown
---
name: code-reviewer
description: Rivede le modifiche senza toccare i file. Da usare dopo ogni modifica al codice.
tools: Read, Grep, Glob, Bash
model: opus
---

Sei un revisore. Leggi il diff con git, concentrati sui file modificati e riporta i problemi per gravità, con la correzione proposta.
```

Una skill del progetto, in `.claude/skills/api-testing/SKILL.md`. Il corpo si carica solo quando la descrizione corrisponde al compito:

```markdown
---
name: api-testing
description: Come si scrivono i test del pacchetto API. Da usare quando si creano o modificano test in packages/api/.
---

- Tutti i test: `npm test`
- Un solo file: `npm test -- src/__tests__/routes/users.test.ts`
- I test sul database girano in una transazione che viene annullata.
```

Un plugin uguale per tutto il team, in `.claude/settings.json`: la prima chiave registra il marketplace, la seconda accende il plugin. Ognuno lo installa comunque una volta, con `claude plugin install code-formatter@acme-tools --scope project`.

```json
{
  "extraKnownMarketplaces": {
    "acme-tools": {
      "source": { "source": "github", "repo": "acme-corp/claude-plugins" }
    }
  },
  "enabledPlugins": {
    "code-formatter@acme-tools": true
  }
}
```

### Codebase grandi

- **Configura un LSP per ogni linguaggio prima di iniziare**, soprattutto con linguaggi poco comuni: senza, l'agente cerca per testo e può finire sul simbolo sbagliato.
- **Tieni i test separati per sottocartella**, così si lanciano per zona e non vanno in timeout.
- **Aggiungi una mappa del codice solo con stack poco comuni.** Con React o Next.js non serve.
- **Non esiste un file di ignore dedicato.** Le ricerche rispettano già `.gitignore`. Per ciò che è nel repo ma l'agente non deve aprire, come codice generato o dipendenze copiate, usa regole `Read(...)` in `permissions.deny`, per esempio `Read(./**/dist/**/*)` e `Read(./**/vendor/**/*)`. Per saltare i CLAUDE.md dei pacchetti su cui non lavori usa `claudeMdExcludes`.
- **Parti dalla cartella su cui lavori.** Avviando `claude` dentro un pacchetto si caricano il suo CLAUDE.md e quelli delle cartelle superiori, non quelli dei pacchetti accanto. I settings di progetto invece non si ereditano dalle cartelle superiori.
- **Worktree più leggeri.** `worktree.sparsePaths` estrae solo le cartelle che servono; `worktree.symlinkDirectories` collega `node_modules` invece di copiarlo.

## Parte 1 · La base da configurare

Otto cose da sistemare in ogni repo prima di aggiungere skills e plugin: i file al posto giusto, i permessi, la sandbox, la status line, la compattazione, i subagent, i controlli del progetto e il browser. Chiudono la sezione un `settings.json` di partenza e l'uso fuori dal terminale. Nomi e sintassi vengono dalla documentazione ufficiale, letta il 7 ottobre 2026.

### I file, a regime

```text
repo/
  CLAUDE.md                   poche righe non ricavabili dal codice
  CODING_STANDARDS.md         scelte di giudizio, lette da chi fa la review
  .mcp.json                   server MCP condivisi con il team
  .worktreeinclude            file ignorati da git da copiare nei worktree, come .env
  .claude/
    settings.json             permessi, hook, sandbox, plugin: committato
    settings.local.json       i tuoi scostamenti: non committato
    rules/                    regole per tipo di file, con il campo paths
    skills/<nome>/SKILL.md    procedure
    agents/<nome>.md          subagent
    hooks/                    gli script richiamati dagli hook
    output-styles/            stili di risposta
    worktrees/                creata da claude --worktree: mettila in .gitignore

~/.claude/
  settings.json               le tue impostazioni, in ogni progetto
  CLAUDE.md                   le tue preferenze, in ogni progetto
  skills/  agents/  rules/    come nel repo, ma solo tue
```

Se una chiave è scritta in più file, l'ordine di precedenza è: settings dell'organizzazione, riga di comando, `settings.local.json`, `settings.json` del progetto e, per ultimi, i tuoi in `~/.claude`. Claude Code rilegge i file quando cambiano: quasi tutte le modifiche, comprese quelle a permessi e hook, valgono senza riavviare.

### Permessi: allow, ask, deny

Le regole stanno in `permissions`, in tre liste: `allow` lascia passare senza chiedere, `ask` chiede sempre, `deny` blocca.

- **L'ordine è fisso: `deny`, poi `ask`, poi `allow`.** Vince la prima che corrisponde. Una regola `allow` più precisa non apre un'eccezione dentro un `deny` più largo.
- **Un `deny` vale in ogni modalità di permesso**, anche con i permessi disattivati. Per questo i divieti si scrivono qui o in un hook, mai in CLAUDE.md.
- **Comandi.** `Bash(npm run *)` copre ogni comando che inizia con `npm run`. Lo spazio prima dell'asterisco conta: `Bash(git diff*)` coprirebbe anche `git diff-index`. La regola guarda il comando com'è scritto: `Bash(git push *)` non copre `git -C . push`.
- **File.** Usa solo `Read(...)` ed `Edit(...)`: una regola `Write(percorso)` viene accettata ma mai consultata. Un `deny` su `Read` blocca anche modifica e scrittura dello stesso percorso.
- **Percorsi.** `./percorso` parte dalla cartella corrente; `/percorso` dalla cartella a cui appartiene il file di settings, che nel progetto è quella da cui avvii Claude; `~/percorso` dalla tua home; `//percorso` dalla radice del disco.
- **Il limite.** Le regole sui file coprono gli strumenti di Claude e i comandi che nominano il file, come `cat .env`. Non coprono un `grep -r` lanciato sulla cartella né uno script che apre il file da sé: quel buco lo chiude la sandbox.

`/permissions` mostra tutte le regole attive e il file da cui arriva ciascuna. `/fewer-permission-prompts` propone regole `allow` a partire dai comandi di sola lettura che usi più spesso.

Cosa metterci: in `deny` i file con i segreti, in `allow` i comandi sicuri del progetto. Sul push questo documento segue il guardrail di Pocock, che lo blocca del tutto. L'esempio ufficiale per i team mette invece `Bash(git push *)` in `ask`, cioè push con la tua conferma: con il guardrail quella regola non serve.

### Modalità di permesso

Dalla versione 2.1.283 le sessioni interattive partono in auto mode su tutti i piani: un classificatore esamina le azioni al posto tuo e blocca quelle rischiose. `Shift+Tab` cambia modalità durante la sessione.

| Modalità | Cosa passa senza chiedere | Quando |
| --- | --- | --- |
| `default`, detta Manual | Solo le letture | Lavoro delicato, quando vuoi rivedere ogni azione |
| `acceptEdits` | Letture, modifiche ai file e comandi comuni sui file, come `mkdir` e `mv` | Mentre rivedi tu il codice |
| `plan` | Letture: Claude analizza e propone prima di modificare | Esplorare una codebase |
| `auto` | Tutto, con i controlli del classificatore | Compiti lunghi |
| `dontAsk` | Letture e ciò che è già in `allow`; il resto viene negato | CI e script |
| `bypassPermissions` | Tutto | Solo dentro un container o una VM |

Il default si imposta con `permissions.defaultMode`. I valori `auto` e `bypassPermissions` hanno effetto solo dai tuoi settings in `~/.claude`, non da quelli del progetto.

### Sandbox

La sandbox limita, a livello di sistema operativo, i file e i domini che i comandi shell possono raggiungere, compresi i processi che lanciano.

- **Come si accende.** `/sandbox` apre il pannello e salva la scelta in `.claude/settings.local.json`. Per tutto il team: `"sandbox": { "enabled": true }` nei settings del progetto.
- **Dove funziona.** Su macOS senza installare nulla; su Linux e WSL2 con i pacchetti `bubblewrap` e `socat`. Su Windows nativo no: lì Claude Code avvisa ed esegue senza sandbox.
- **Cosa permette di default.** Scrittura nella cartella di lavoro e in una cartella temporanea. Nessun dominio è già ammesso: al primo accesso chiede. I domini abituali si elencano in `sandbox.network.allowedDomains`.
- **Due modi.** Con "auto-allow" i comandi che girano nella sandbox partono senza chiedere; con i permessi normali chiedono comunque. Le regole `deny` e le regole `ask` su un comando preciso valgono in entrambi.
- **Cosa non copre.** Gli strumenti di lettura e modifica dei file, che seguono le regole di permesso; i server MCP e gli hook, che girano sul tuo sistema. E non è un ambiente separato: dipendenze, database e porte restano quelli della tua macchina. Per isolare quelli serve un container o una VM.
- **Insieme ai permessi.** Con la sandbox accesa, i percorsi vietati dalle regole `Read` ed `Edit` diventano irraggiungibili anche per i comandi shell.

### Status line: vedere quanto contesto stai usando

La status line è una riga in fondo al terminale, prodotta da un comando che riceve i dati della sessione. Serve a rispettare la soglia dei 150k token senza lanciare `/context` ogni volta.

Il modo rapido è chiederla: `/statusline mostra il modello e i token nel contesto`. A mano, nei tuoi settings:

```json
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\((.context_window.total_input_tokens // 0) / 1000 | floor)k token\"'"
  }
}
```

Mostra, per esempio, `[Opus 5.5] 152k token`, e richiede `jq`. È adattata dall'esempio ufficiale, che mostra la percentuale: con i modelli a finestra da 1M, a 150k token la percentuale è appena il 15%, quindi qui conta il numero. L'espressione l'ho provata su un input di esempio, non dentro Claude Code.

### Compattazione

Quando il contesto si riempie, Claude Code riassume la conversazione da solo. Con i modelli attuali però la soglia automatica è molto oltre la zona utile: Opus 5.5, Sonnet 5 e i modelli Fable hanno una finestra da 1M e compattano intorno a 967k token.

- **A mano.** `/compact <cosa conservare>`, ai confini di fase e come ultima scelta: l'ordine è nella Parte 2.
- **Soglia automatica.** `/autocompact 200k` la abbassa per il modello in uso e la salva; accetta valori da 100k a 1M. Per tutti i modelli c'è la chiave `autoCompactWindow`; `autoCompactEnabled` accende o spegne la compattazione automatica.
- **Cosa fare.** Tieni il contesto a vista con la status line e decidi tu ai confini di fase. Se vuoi una rete di sicurezza, `/autocompact 200k`: è una scelta di questo documento, non un'indicazione dei video.

### Subagent

Un subagent lavora in un contesto proprio e riporta solo il risultato. È un file markdown in `.claude/agents/`, da committare, oppure in `~/.claude/agents/`, tuo in ogni progetto; a parità di nome vince quello del progetto. Un esempio è tra i quattro esempi minimi.

- **Campi più usati.** `name` e `description` sono obbligatori. `tools` limita gli strumenti: senza, li eredita tutti. `model` accetta `sonnet`, `opus`, `haiku`, `fable`, un identificativo completo o `inherit`. `effort` fissa il livello. `isolation: worktree` gli dà una copia isolata del repo.
- **Quale modello usa.** Nell'ordine: quello chiesto da Claude per quella chiamata, il campo `model` del file, la variabile `CLAUDE_CODE_SUBAGENT_MODEL`, il modello della sessione.
- **Come si creano.** Chiedilo a Claude o scrivi il file: dalla versione 2.1.198 `/agents` non apre più un pannello. Le modifiche valgono dopo pochi secondi, senza riavviare.
- **A cosa servono qui.** Un revisore sul modello forte, con soli strumenti di lettura, da chiamare quando vuoi un secondo parere.

### I controlli del progetto

Test, controllo dei tipi e lint: un comando ciascuno, e qualcosa che li esegua davvero, cioè un hook di pre-commit o la CI. È ciò che rende verificabile il lavoro dell'agente: `/implement` controlla i tipi e i singoli file di test di continuo e lancia la suite completa alla fine, e per `/retro` un repo senza alcun controllo automatico è già un problema da segnalare.

Nei repo JavaScript la skill `setup-pre-commit` di Pocock installa Husky, lint-staged con Prettier, controllo dei tipi e test. Non è nel plugin: `npx skills@latest add mattpocock/skills --skill=setup-pre-commit`.

### Vedere l'app nel browser: Claude in Chrome

Se il progetto ha un'interfaccia web, Claude deve poterla guardare. Claude in Chrome collega Claude Code al tuo browser: apre una scheda, usa la pagina e legge console e DOM, anche su `localhost`.

- **Cosa serve.** L'estensione Claude in Chrome, versione 1.0.36 o successiva, in Chrome, Edge o un altro browser basato su Chromium. Un piano Pro, Max, Team o Enterprise, con l'accesso fatto tramite `/login`: con una chiave API l'integrazione resta spenta. Dentro WSL non è supportata.
- **Come si usa.** `claude --chrome` avvia la sessione con il browser collegato; `/chrome` mostra lo stato, ricollega l'estensione e gestisce i permessi. Poi lo chiedi a parole: "apri localhost:3000, invia il form con dati non validi e controlla che compaiano i messaggi di errore".
- **A cosa serve.** Provare un flusso dopo una modifica, leggere gli errori in console e correggere il codice che li causa, confrontare l'interfaccia con un mockup, salvare uno screenshot o registrare una GIF di ciò che ha fatto.
- **Accendilo quando serve.** Con l'opzione "Enabled by default" gli strumenti del browser restano sempre caricati e occupano contesto: meglio `--chrome` nelle sole sessioni in cui provi l'interfaccia.
- **È il tuo browser vero.** Lavora in una finestra visibile e condivide i tuoi accessi, quindi può entrare in ogni sito in cui sei già autenticato. I siti su cui può agire si limitano dai permessi dell'estensione. Davanti a un login o a un CAPTCHA si ferma e ti chiede di intervenire.
- **Se smette di rispondere.** Una finestra di dialogo JavaScript rimasta aperta blocca i comandi: chiudila a mano. Dopo una lunga inattività ricollega l'estensione da `/chrome`.

Dove Chrome non arriva, cioè in WSL, in CI o senza un account claude.ai, restano le alternative elencate tra gli MCP: una skill con CLI come `agent-browser`, oppure il plugin `playwright`.

### Un settings.json di partenza

Per il repo, in `.claude/settings.json`, committato. I file di settings non accettano commenti. Adatta i comandi al tuo gestore di pacchetti; `language`, `outputStyle` e `attribution` sono spiegate nelle preferenze del team.

```json
{
  "language": "italian",
  "outputStyle": "Diretto",
  "attribution": { "commit": false, "pr": false },
  "permissions": {
    "allow": [
      "Bash(pnpm run *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "network": {
      "allowedDomains": ["registry.npmjs.org"]
    }
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  },
  "enabledPlugins": {
    "typescript-lsp@claude-plugins-official": true
  }
}
```

L'hook è il guardrail git di Pocock, nella forma in cui lo registra la sua skill. Il plugin acceso in `enabledPlugins` va comunque installato una volta da ciascuno.

Per te, in `~/.claude/settings.json`. Ogni chiave è spiegata nelle impostazioni consigliate:

```json
{
  "statusLine": {
    "type": "command",
    "command": "jq -r '\"[\\(.model.display_name)] \\((.context_window.total_input_tokens // 0) / 1000 | floor)k token\"'"
  },
  "preferredNotifChannel": "terminal_bell",
  "autoMemoryEnabled": false,
  "enableWorkflows": false,
  "showThinkingSummaries": true,
  "env": {
    "CLAUDE_CODE_NEW_INIT": "1"
  }
}
```

### Fuori dal terminale: script e CI

- **Da script.** `claude -p "<richiesta>"` esegue senza sessione interattiva. Con `--bare` non carica hook, skills, plugin, server MCP, memoria né CLAUDE.md, così il risultato è lo stesso su ogni macchina; richiede `ANTHROPIC_API_KEY`. Gli strumenti ammessi si passano con `--allowedTools`, il formato con `--output-format json`. In un job che nessuno guarda aggiungi `--permission-prompts none`: ciò che avrebbe chiesto conferma viene negato.
- **Su GitHub.** `/install-github-app` installa l'app, salva il secret (`ANTHROPIC_API_KEY`, oppure `CLAUDE_CODE_OAUTH_TOKEN` se usi l'abbonamento) e apre una PR con i workflow, compreso quello di review. L'action è `anthropics/claude-code-action@v1`.
- **Code Review gestita.** Per i piani Team ed Enterprise, ancora in anteprima: commenta ogni PR senza workflow da mantenere, legge `REVIEW.md` alla radice del repo e costa in media 15-25 dollari a review.

## Parte 1 · Skills, plugin e MCP: il set consigliato

Installa poco e misura tutto: il set di base sono quattro cose, il resto si aggiunge solo quando il progetto lo richiede. I comandi vengono dai README delle repo e dalla documentazione ufficiale, letti il 6 ottobre 2026.

### Tre modi di installare

| Modo | Comando | Cosa ottieni | Quando sceglierlo |
| --- | --- | --- | --- |
| Plugin da un marketplace | `/plugin install <nome>@<marketplace>`. Per un marketplace non ufficiale, prima `/plugin marketplace add <owner>/<repo>` | Skills, hooks e server MCP gestiti dall'autore, in sola lettura e con aggiornamenti. Le skills prendono il prefisso del plugin | Vuoi restare allineato all'autore |
| File nel repo | `npx skills add <owner>/<repo>`, con `--skill <nome>` per sceglierne una e `-g` per installarla in tutti i tuoi progetti | File tuoi in `.claude/skills/`, modificabili. Si aggiornano con `npx skills update` | Vuoi adattare le skills o condividerle con il team via git |
| Server MCP | `claude mcp add --transport http <nome> <url> --scope project` | Strumenti esterni. Con `--scope project` la configurazione finisce in `.mcp.json` e si condivide; con `user` vale in tutti i tuoi progetti; senza opzione resta locale | Solo se non esiste una CLI |

Per ogni fonte scegli un solo modo: plugin e file insieme duplicano ogni skill. Fa eccezione il guardrail git di Pocock, che non è nel plugin e si aggiunge con `npx` in entrambi i casi.

Le forme del comando si equivalgono: `claude plugins` è un alias di `claude plugin`, `/plugin install` è lo stesso comando dentro una sessione, e il nome del marketplace si può omettere finché il nome del plugin è unico. Per le skills di Pocock, `/plugin install mattpocock-skills`, `claude plugins install mattpocock-skills` e la forma con `mattpocock-skills@claude-plugins-official` installano lo stesso plugin.

### Il set di base

| Cosa | Perché | Comando | Costo e note |
| --- | --- | --- | --- |
| Le skills di Pocock | Sono il processo di sviluppo della Parte 2 | `/plugin install mattpocock-skills`, oppure `npx skills@latest add mattpocock/skills` | 27 skills; 16 non occupano contesto finché non le digiti |
| LSP del tuo linguaggio | Senza, l'agente cerca per testo e può finire sul simbolo sbagliato | `/plugin install typescript-lsp@claude-plugins-official`, più il language server: `npm install -g typescript-language-server typescript` | Nel marketplace ufficiale ci sono anche Python (`pyright-lsp`), Go, Rust, Java, C#, PHP, Ruby, Swift, Kotlin, C/C++ e Lua |
| Guardrail git | Blocca ogni push, i reset e le cancellazioni distruttive | `npx skills@latest add mattpocock/skills --skill=git-guardrails-claude-code`, poi esegui la skill | È un hook: non costa contesto |
| Le skills del tuo stack, e solo quelle | Le librerie cambiano più in fretta del modello | Supabase: `npx skills add supabase/agent-skills`. GSAP: `npx skills add https://github.com/greensock/gsap-skills` | Ogni descrizione resta in contesto: non installare ciò che non usi |

### Facoltativi

- **Scrivere le tue skills.** `/writing-for-agents` di Pocock, oppure `skill-creator` di Anthropic: `/plugin install skill-creator@claude-plugins-official`.
- **Design.** UI-Skills è un registro di skills di design: da terminale con `npx ui-skills start`, oppure come MCP con `claude mcp add --transport http ui-skills https://www.ui-skills.com/mcp`.
- **Registro delle lezioni.** task-observer annota in un `log.md`, fuori dal progetto, i miglioramenti possibili alle tue skills e non le modifica da solo: decidi tu quali applicare. Il video del 1 settembre non ne indica autore né repo, quindi qui manca il comando.
- **Le quattro regole di Karpathy.** Leggi il confronto nella Parte 2 prima di adottarle: sono 65 righe sempre in contesto.

Altri strumenti facoltativi sono nella tabella in fondo alla Parte 2.

### MCP: quando sì e quando no

Un MCP serve quando l'informazione sta dove Claude non può arrivare in nessun altro modo. Se lo strumento offre anche una CLI, usa CLI più skill.

**Quanto costa un MCP.** Il tool search è attivo di default: le definizioni degli strumenti si caricano quando Claude le cerca, non all'avvio. Restano il costo dei risultati (25.000 token al massimo per chiamata, modificabile con `MAX_MCP_OUTPUT_TOKENS`) e il rischio di prompt injection dai server che leggono contenuti esterni. Misura il tuo caso con `/context`.

| Bisogno | Prima scelta | MCP, se serve |
| --- | --- | --- |
| Issue e pull request su GitHub | La CLI `gh`; il tracker si descrive in `docs/agents/issue-tracker.md` durante il setup delle skills | Nessuno |
| Jira e Confluence | Nessuna CLI consigliata | Atlassian, in `.mcp.json`: `npx -y mcp-remote@latest https://mcp.atlassian.com/v1/mcp` |
| Database Supabase | CLI più skills | Il plugin `supabase` del marketplace ufficiale |
| Prova dell'app nel browser | Claude in Chrome, con `claude --chrome`: usa il tuo browser, anche su `localhost`, e legge la console. Dove non arriva, come in WSL o in CI, una skill con CLI, come `agent-browser` o Reticle. Per verificare una modifica senza browser c'è `/verify` integrato, che costruisce ed esegue l'app e osserva il risultato | Il plugin `playwright` del marketplace ufficiale |
| Skills di design | `npx ui-skills`, da richiamare nel prompt | UI-Skills come MCP, se vuoi che l'agente lo trovi da solo |
| Strumenti interni dell'azienda | Nessuna | Un MCP tuo, costruito quando l'app funziona già |

Tre regole di igiene: imposta `disableClaudeAiConnectors` a `true` se non usi in Claude Code i connettori dell'app; collega solo server di cui ti fidi; controlla lo stato con `/mcp`.

### Manutenzione

- **Ogni tanto:** `/skill-doctor` per vedere quanto costa ogni skill e quanto la usi, `/doctor` per skills e server MCP inutilizzati, `/context` in una sessione vuota per il totale.
- **Dopo un aggiornamento:** `npx skills update` per i file, `/plugin marketplace update` per i marketplace aggiunti a mano; cancella le cartelle delle skills rimosse.
- **Per nascondere una skill senza disinstallarla:** `skillOverrides`.
- **Per sapere se una skill o una regola serve davvero:** un confronto con e senza. Caliper lo fa per skills e MCP; la skill `ablate-ai-layer` di Cole Medin lo fa per le regole sempre caricate. Nel suo lessico l'AI Layer è tutto ciò che sta nel repo per l'agente: regole, skills, subagent, MCP, hook e LSP.
- **A ogni nuovo modello:** `/doctor prompt-audit`.

## Parte 1 · Hooks: come usarli bene

Usa un hook per ciò che deve valere sempre, e solo per quello: una regola in CLAUDE.md chiede, un hook garantisce. Le istruzioni si sfocano quando l'agente ha troppe cose a cui badare; un hook gira comunque.

Il criterio per scegliere: se ignorare la regola è un fastidio, scrivi una regola; se è un incidente in produzione, un segreto esposto o un deploy rotto, scrivi un hook.

### Quale evento per quale scopo

| Scopo | Evento e filtro | Come si comporta |
| --- | --- | --- |
| Bloccare un comando o un file: git distruttivi, `.env`, cartelle protette, `npm` al posto di `pnpm` | `PreToolUse`, con matcher `Bash` oppure `Edit` e `Write` | Uscita con codice 2: l'azione si ferma e il messaggio su stderr torna a Claude, che riprova in altro modo |
| Formattare o fare lint dopo una modifica | `PostToolUse`, con matcher `Edit` e `Write` | Non può bloccare né annullare: lo strumento ha già agito |
| Tenere nel contesto solo i test falliti | `PreToolUse` su `Bash`, che riscrive il comando dei test | L'output dei test passati non entra nel contesto |
| Non lasciar chiudere finché i controlli non passano | `Stop` | Codice 2: Claude continua a lavorare. Serve il controllo su `stop_hook_active` |
| Caricare il contesto di oggi: branch, file modificati, note | `SessionStart` | Il testo va in `hookSpecificOutput.additionalContext` |
| Far rispettare regole che richiedono giudizio | `PreToolUse` di tipo `prompt`, oppure un modello di decisione come Jev | Un modello piccolo risponde sì o no. È più lento e meno prevedibile di uno script |
| Proteggere la configurazione stessa | `PreToolUse` sulle modifiche a `settings.json`, `.claude/hooks/` e `.mcp.json`; oppure, senza script, regole `Edit(...)` in `permissions.deny` | Impedisce all'agente di riscrivere i propri guardrail. Con le regole `deny` nemmeno tu puoi farglieli modificare, finché non le togli |

La guida ufficiale elenca 33 eventi e cinque tipi di hook: `command`, `http`, `mcp_tool`, `prompt` e `agent`, quest'ultimo sperimentale. Quasi tutto ciò che serve si fa con `command` su quattro eventi: `PreToolUse`, `PostToolUse`, `Stop` e `SessionStart`.

### Un esempio completo

In `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(npm *)",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/use-pnpm.sh"
          }
        ]
      }
    ]
  }
}
```

E lo script `.claude/hooks/use-pnpm.sh`, reso eseguibile con `chmod +x`:

```bash
#!/bin/bash
COMMAND=$(jq -r '.tool_input.command')
if echo "$COMMAND" | grep -qE '(^|[;&|] *)npm '; then
  echo "Bloccato: in questo progetto si usa pnpm, non npm" >&2
  exit 2
fi
exit 0
```

### Un secondo esempio: non chiudere finché i test non passano

È l'hook con cui si impone un cancello. In `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/tests-must-pass.sh"
          }
        ]
      }
    ]
  }
}
```

E lo script `.claude/hooks/tests-must-pass.sh`, reso eseguibile con `chmod +x`:

```bash
#!/bin/bash
INPUT=$(cat)
# Se questo hook ha già fatto proseguire Claude, lascialo chiudere
if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
  exit 0
fi
if ! OUTPUT=$(pnpm test 2>&1); then
  echo "I test falliscono: correggili prima di chiudere." >&2
  echo "$OUTPUT" | tail -n 30 >&2
  exit 2
fi
exit 0
```

Con il controllo su `stop_hook_active`, che è la forma della guida ufficiale, l'hook rimanda Claude al lavoro una volta per ogni chiusura. Togliendolo insiste a ogni tentativo, fino al tetto di otto blocchi consecutivi: è la forma adatta a un loop non presidiato. Il resto dello script è mio: l'ho provato con comandi di test finti, non dentro Claude Code.

### Le regole d'uso

1. **Solo il codice 2 blocca.** Il codice 1, quello che linter e test restituiscono quando falliscono, è un errore non bloccante: Claude prosegue e nessuno ti avvisa.
2. **PostToolUse non annulla nulla.** Per impedire un'azione serve `PreToolUse`.
3. **Uno Stop hook scatta a ogni fine risposta, non solo a lavoro finito.** Leggi `stop_hook_active` ed esci subito se è vero. Dopo otto blocchi consecutivi Claude Code scavalca l'hook e chiude il turno con un avviso.
4. **Un divieto dato da un hook vale in ogni modalità di permesso,** anche con i permessi disattivati. Un via libera invece non scavalca i divieti scritti nei settings.
5. **Restringi con matcher e if.** Con `"if": "Bash(git *)"` lo script parte solo sui comandi git. Il filtro è approssimativo: per un divieto assoluto aggiungi una regola di permesso.
6. **Più hook sullo stesso evento girano in parallelo** e vince la risposta più restrittiva. Non contare sull'ordine.
7. **La shell non è interattiva.** Il tuo `.zshrc` non viene letto: usa percorsi assoluti o `$CLAUDE_PROJECT_DIR`.
8. **Prova ogni hook nei due sensi prima di fidarti:** un payload finto che deve passare e uno che deve essere bloccato. `/hooks` mostra gli hook attivi, `claude --debug` la loro esecuzione.
9. **Leggi gli hook di terzi come leggeresti uno script di CI.** Girano con le tue credenziali e senza sandbox.
10. **Niente richieste di approvazione durante la build.** Un hook che chiede conferma a una persona va messo al rilascio: durante l'implementazione la rimette sul percorso critico.

Un file che alleghi tu con `@` nel prompt può non passare da `PreToolUse`: l'hook protegge da ciò che l'agente va a cercare, non da ciò che gli dai tu.

### Dove metterli

In `.claude/settings.json`, committato, valgono per tutto il team. In `~/.claude/settings.json` valgono solo per te, in ogni progetto. Un plugin li porta con sé, e una skill può dichiararne nel proprio frontmatter: restano attivi dal momento in cui la invochi.

### Hook già pronti

| Fonte | Cosa contiene | Come si installa |
| --- | --- | --- |
| Pocock, `git-guardrails-claude-code` | Il blocco dei comandi git distruttivi | Vedi il set di base |
| Cole Medin, cartella `hooks/` di `coleam00/skills` | Sei script Python: segreti e `rm -rf`, dipendenze tra file, log delle azioni, contesto all'avvio, test che devono passare allo stop, notifica a fine turno | Copia i file in `.claude/hooks/`, unisci `settings.json.example` ai tuoi settings e imposta `TEST_COMMAND` |
| `karanb192/claude-code-hooks` | 22 plugin, tra cui `protect-secrets`, `block-dangerous-commands`, `git-safety`, `protect-tests` e `config-guard`. `guard-pack` riunisce i guardrail in un solo processo | `/plugin marketplace add karanb192/claude-code-hooks`, poi `/plugin install guard-pack@claude-code-hooks`. Installalo per ultimo: `config-guard` blocca anche l'installazione di altri plugin |
| Anthropic, plugin `hookify` | Crea una regola da una frase, o dagli errori della conversazione | `/plugin install hookify@claude-plugins-official`, poi `/hookify <regola>` |
| Cole Medin, skill `hooks-create` | Sceglie l'evento, scrive lo script, lo registra e lo prova | `/hooks-create "<la garanzia che vuoi>"` |
| Claude Code | Converte in hook le istruzioni deterministiche del tuo CLAUDE.md | Chiedilo nel prompt e fatti mostrare l'elenco prima di accettare |

### Il set minimo

Guardrail git e protezione dei segreti, sempre; per i segreti bastano anche le regole `deny` della base da configurare. Formattazione dopo ogni modifica, se il progetto ha un formatter. Lo stop finché i test non passano solo nelle sessioni non presidiate: in una sessione interattiva allunga ogni risposta.

A ogni nuovo modello rivedi anche gli hook, come il resto del setup: non costano contesto, ma costano tempo a ogni azione.

## Parte 1 · Impostazioni consigliate

Le chiavi vanno in `~/.claude/settings.json` per valere ovunque, oppure in `.claude/settings.json` del progetto. I nomi sono quelli della documentazione ufficiale di Claude Code.

### Comandi per creare e ripulire il setup

| Comando | Cosa fa | Quando usarlo |
| --- | --- | --- |
| `/init` con `CLAUDE_CODE_NEW_INIT=1` | Chiede quali file creare (CLAUDE.md, skills, hooks), esplora il codice, poi scrive. La variabile si imposta nella shell o nel blocco `env` dei settings | Su un progetto nuovo, al posto del vecchio init |
| `/import codex` oppure `cursor` o `gemini` | Porta in Claude Code istruzioni, server MCP, comandi, subagent e skills. Con `--dry-run` mostra soltanto | Una volta, se arrivi da un altro agente |
| `/doctor prompt-audit` | Controlla CLAUDE.md, regole, skills, comandi e subagent: segnala percorsi e comandi obsoleti, istruzioni che si contraddicono e formule scritte per modelli vecchi. Esiste anche come `/claude-api prompt-audit` | Dopo ogni nuovo modello |
| `/doctor` | Controllo generale del setup: installazione, settings non leggibili, skills e server MCP inutilizzati | Ogni tanto |
| `/skill-doctor` | Mostra quanto contesto costa ogni skill e quanto spesso la usi. Richiede la versione 2.1.252 o successiva | Per eliminare le skills inutilizzate |
| `/context` in una sessione vuota, e `claude --safe-mode` | Misura quanto consuma il tuo setup; la safe mode avvia senza CLAUDE.md, plugin, skills, hooks e MCP | Per decidere cosa tagliare |
| `/usage` | Mostra finestra di 5 ore, limite settimanale e cosa li consuma di più | Quando finisci i limiti troppo presto |

Nessuno di questi comandi modifica nulla senza la tua approvazione.

### Impostazioni da attivare

| Chiave | Valore | Effetto |
| --- | --- | --- |
| `disableClaudeAiConnectors` | `true` | I connettori dell'app Claude (Notion, Slack e simili) non vengono più caricati. Perdi il loro uso dentro Claude Code: lasciala stare se ne usi uno |
| `enableArtifact` | `false` | Spegne lo strumento degli artifact, cioè le pagine interattive che Claude Code pubblica su claude.ai a partire dal lavoro della sessione. Perdi quelle pagine, e nessun altro file di settings può riaccenderlo |
| `autoMemoryEnabled` | `false` | Spegne la memoria automatica: gli appunti che Claude scrive per sé su correzioni e preferenze, caricati a ogni sessione (le prime 200 righe o 25 KB). Perdi ciò che avrebbe ricordato da solo, in coerenza con la regola di non far scrivere lezioni in automatico |
| `awaySummaryEnabled` | `false` | Niente riepilogo automatico quando torni al terminale; resta `/recap` a richiesta |
| `enableWorkflows` | `false` | Spegne per te i workflow dinamici: script che Claude scrive per far lavorare molti subagent e incrociarne i risultati. Sono pensati per lavori molto larghi e consumano molto. Per spegnerli a tutto il team la chiave è `disableWorkflows: true`. Con i workflow spenti non è disponibile nemmeno Ultracode |
| `bashOutputMaxChars` | per esempio `10000` | Limita l'output dei comandi che entra nel contesto. La variabile equivalente è `BASH_MAX_OUTPUT_LENGTH`, con 30.000 caratteri di default |
| `showClearContextOnPlanAccept` | `true` | Mostra l'opzione di svuotare il contesto quando accetti un piano. Serve solo se usi la plan mode |
| `plansDirectory` | una cartella del progetto | I piani si salvano nel repo, condivisibili con il team. Serve solo se usi la plan mode |
| `showThinkingSummaries` | `true` | Tornano i riassunti del ragionamento |
| `askUserQuestionTimeout` | solo per sessioni non presidiate, per esempio `60000` | In millisecondi, non secondi: dopo quel tempo una domanda senza risposta prosegue da sola. Solo nei settings utente o dell'organizzazione. Non impostarla se lavori con il grilling: una domanda che prosegue da sola decide al posto tuo |
| `preferredNotifChannel` | `"terminal_bell"` | Suona il campanello del terminale quando una sessione finisce o ti aspetta. Senza, la notifica desktop arriva solo in Ghostty, Kitty e iTerm2 |
| `effortLevel` | `"medium"` | Effort di default per i modelli senza un livello salvato. Nei tuoi settings vale solo per Opus 5, Fable 5.1 e modelli precedenti: Opus 5.5 e successivi la ignorano, e per loro si usa `/effort <livello>`, che salva per modello. Nei settings del progetto vale per ogni modello. Non accetta `max` |
| `skillOverrides` | per skill | Nasconde una singola skill senza toccarne il file |
| `CLAUDE_CODE_SUBAGENT_MODEL` (variabile) | un modello più piccolo | Modello di default dei subagent. Con `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` vale per tutti, anche per quelli che dichiarano un proprio modello: non attivarla, o i subagent di review perdono il modello forte. Da sola la prima variabile non cambia il modello dei subagent integrati Explore e Plan |

Status line, soglia di compattazione, permessi e sandbox sono nella base da configurare.

**Non attivare `disableBundledSkills` senza pensarci.** Risparmia contesto, ma toglie anche `/code-review`, `/loop`, `/claude-api`, `/verify` e gli altri comandi integrati usati in questo documento; solo `/doctor` resta digitabile. Per nascondere una skill sola usa `skillOverrides`.

### Auto mode: tre strumenti per adattarla

Dalla versione 2.1.283 le sessioni interattive partono in auto mode su tutti i piani, se non è configurata un'altra modalità: un classificatore blocca le azioni rischiose. Regole `allow`, `ask` e `deny`, modalità e sandbox sono nella base da configurare. Tre strumenti adattano l'auto mode a te. `/auto-mode-setup` prepara le regole a partire dal progetto e dalle sessioni recenti e te le fa rivedere prima di salvarle. `/fewer-permission-prompts` cerca nelle sessioni passate i comandi di sola lettura più frequenti e li aggiunge alla allow list in `.claude/settings.json` del progetto. La scheda Auto mode di `/permissions` permette di vedere e modificare le regole a mano.

### Modelli ed effort

- **Modello di default.** Dalla versione 2.1.280 è Opus 5.5 su tutti i piani a pagamento; prima, su Pro, era Sonnet 5. I modelli Fable non sono il default su nessun piano: si scelgono con `/model`.
- **Per far durare i limiti.** Sul piano Pro i video consigliano Sonnet per il lavoro quotidiano e Opus solo per i compiti difficili; sul piano Max, Opus come modello quotidiano. Con `/model opusplan` Opus lavora in plan mode e Sonnet esegue: scatta solo se usi la plan mode, quindi non dentro il flusso di Pocock.
- **Effort.** I livelli sono `low`, `medium`, `high`, `xhigh` e `max`. Opus 5.5 e Sonnet 5.5 partono da `medium`, quasi tutti gli altri modelli da `high`. Su Fable 5.1, nel video del 5 settembre, `low` ha dato risultati migliori di `high`. Sempre secondo i video, sopra `high` l'output non migliora e i limiti finiscono prima. Si cambia con `/effort <livello>`, che lo salva per modello.
- **Ultracode.** Non è un livello di effort: è un interruttore, dentro `/effort`, che fa pianificare a Claude un workflow dinamico per ogni compito sostanzioso. Dalla versione 2.1.284 non forza più `xhigh`. Tienilo spento per la stessa ragione dei workflow.
- **`ultrathink`.** Scritta in un prompt, la parola chiede un ragionamento più profondo per quel solo turno, senza cambiare l'effort della sessione.
- **Giudizio e pianificazione.** Usa il modello più forte per il grilling e per gli agenti di review: è quello a cui punta l'alias `best`, cioè Fable dove è disponibile sul tuo account, altrimenti Opus. Per l'implementazione guidata da un piano o da un ticket basta un modello più piccolo.
- **Advisor.** Si accende e si spegne con `/advisor`. Tienilo spento: decide lui quando consultare il modello forte, e lo paghi tu.

### Contesto e limiti d'uso

- **Guarda i token, non la percentuale.** Tieni nella status line i token nel contesto: con le finestre da 1M la percentuale resta bassa anche oltre i 150k. `/context` mostra cosa li occupa.
- **`/clear` tra compiti non collegati.**
- **`/rewind` invece di correggere.** Una correzione nel prompt successivo lascia nel contesto sia l'errore sia la correzione.
- **Un prompt lungo invece di tanti piccoli.** Ogni turno rimanda l'intera conversazione.
- **Se devi compattare, fallo prima di una pausa** e scrivi cosa conservare: dopo la pausa la cache è scaduta e rileggi tutto a prezzo pieno.
- **CLI più skill al posto di un MCP**, quando lo strumento offre entrambi.

### Come scrivere i prompt per i modelli attuali

- **Di' cosa vuoi, non come farlo.** Descrivi il risultato, i limiti e cosa significa "finito".
- **Dai il compito intero.** I modelli recenti rendono meglio sui lavori grandi che su tanti passi piccoli.
- **Per i lavori lunghi di' che nessuno sta guardando** e che può procedere con tutto ciò che è coperto dalla richiesta ed è reversibile.
- **Di' cosa lasciare stare.** Modifica solo ciò che serve; gli altri problemi li segnala alla fine.
- **Chiedi modifiche puntuali, non riscritture di file interi.**
- **Descrivi invece di mostrare.** Un'immagine o un esempio concreto vengono copiati quasi identici.

## Parte 1 · Le preferenze tue e del team

Lingua, stile delle risposte, commenti, git e changelog vanno ognuno nel posto più economico che li fa rispettare: tre chiavi nei settings, uno stile di output, poche righe in CLAUDE.md, un file di standard e due controlli automatici. Tutto sta nel repo, così vale per te e per il team.

### Cosa va dove

| Preferenza | Dove | Perché lì |
| --- | --- | --- |
| Risposte in italiano | `language` in `.claude/settings.json` | È un'impostazione: non costa istruzioni |
| Risposte dirette, non prolisse | Uno stile di output in `.claude/output-styles/` | Vale per ogni risposta e si cambia con `/output-style` |
| Inglese per codice, commit e changelog; italiano per commenti, docstring e file `.md` | Due righe in CLAUDE.md | Non si ricava dal codice e vale in ogni sessione |
| Docstring adatte a un LLM | `CODING_STANDARDS.md`, più una regola di lint | Il lint garantisce a chi implementa che ci siano e abbiano la forma giusta; lo standard lo applica chi fa la review |
| Blocco "Scelte" in fondo ai file | Il CLAUDE.md dei soli progetti legati a compiti | Vale solo lì |
| Rami, commit e PR | Guardrail git, controllo sul messaggio di commit, skill `/pr` | I divieti devono valere sempre |
| Changelog a ogni modifica | Una riga in CLAUDE.md, più un controllo in CI | La riga lo chiede, il controllo lo garantisce |

### Settings

In `.claude/settings.json`, committato:

```json
{
  "language": "italian",
  "outputStyle": "Diretto",
  "attribution": { "commit": false, "pr": false }
}
```

`attribution` toglie la firma di Claude da commit e PR. Il valore di `outputStyle` distingue maiuscole e minuscole: deve coincidere con il `name` dello stile.

### Stile di output

In `.claude/output-styles/diretto.md`:

```markdown
---
name: Diretto
description: Risultato per primo, niente preamboli, una riga per ogni scelta non ovvia
keep-coding-instructions: true
---

Rispondi in modo diretto.

- La prima frase dice cosa è successo o qual è la risposta.
- Niente preamboli, niente racconto dei passi, niente riepilogo finale.
- Per ogni scelta non ovvia aggiungi una riga: cosa hai scelto e perché. Le scelte ovvie non si giustificano.
- A una domanda semplice rispondi in una, due o tre frasi.
- Resta completo su errori, test falliti, avvisi di sicurezza e conferme di azioni distruttive.
```

`keep-coding-instructions` conserva le istruzioni di Claude Code per il codice: senza, uno stile personalizzato le toglie. Riavvia Claude Code dopo aver creato il file. Se non vuoi mantenerne uno, lo stile integrato `Concise` fa quasi lo stesso, senza la riga sulle scelte.

### Righe per CLAUDE.md

```markdown
## Lingue
- Inglese: nomi nel codice, messaggi di commit, changelog.
- Italiano: commenti nel codice, docstring, file .md escluso il changelog.

## Changelog
- Ogni modifica al codice aggiunge un frammento in `changelog.d/` con `scriv create`. Non modificare `CHANGELOG.md` a mano.
```

Sono tre istruzioni e nessuna si ricava dal codice: è il caso in cui CLAUDE.md serve. Manca di proposito un rimando a `CODING_STANDARDS.md`: quel file lo legge chi fa la review, mentre a chi implementa la forma delle docstring la impone il lint.

### Docstring e commenti

Da mettere in `CODING_STANDARDS.md`. Una docstring adatta a un LLM dice ciò che la firma non dice:

- **Prima riga.** Cosa fa, in una frase, senza ripetere il nome della funzione.
- **Parametri.** Significato, unità di misura, vincoli e valori ammessi. Non il tipo, che è già nella firma.
- **Ritorno.** Cosa rappresenta, e cosa torna nel caso vuoto.
- **Errori.** Quali eccezioni e in quale condizione.
- **Effetti collaterali.** File, rete, database, stato condiviso.
- **Esempio.** Uno, quando la chiamata non è ovvia.
- **Commenti.** In italiano; spiegano il perché, mai il cosa.

In Python, stile Google:

```python
def monthly_payment(principal: float, annual_rate: float, months: int) -> float:
    """Calcola la rata mensile di un prestito a tasso fisso.

    Args:
        principal: Capitale finanziato, in euro. Maggiore di 0.
        annual_rate: Tasso annuo nominale come frazione (0.05 = 5%).
        months: Numero di rate mensili. Almeno 1.

    Returns:
        La rata in euro, non arrotondata.

    Raises:
        ValueError: Se principal <= 0 o months < 1.

    Example:
        >>> round(monthly_payment(10_000, 0.05, 12), 2)
        856.07
    """
```

In TypeScript, con TSDoc:

```ts
/**
 * Calcola la rata mensile di un prestito a tasso fisso.
 *
 * @param principal - Capitale finanziato, in euro. Maggiore di 0.
 * @param annualRate - Tasso annuo nominale come frazione (0.05 = 5%).
 * @param months - Numero di rate mensili. Almeno 1.
 * @returns La rata in euro, non arrotondata.
 * @throws RangeError se principal <= 0 o months < 1.
 */
export function monthlyPayment(principal: number, annualRate: number, months: number): number
```

Il lint garantisce che le docstring ci siano e abbiano la forma giusta; la qualità resta alla review. In Python, in `pyproject.toml`:

```toml
[tool.ruff.lint]
extend-select = ["D"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

In TypeScript, il plugin `eslint-plugin-jsdoc` con la regola `jsdoc/require-jsdoc` e l'opzione `publicOnly`.

### Blocco "Scelte" in fondo ai file

Solo nei progetti legati a compiti. La regola va nel CLAUDE.md di quei progetti, oppure in quello della cartella che li contiene tutti; non nel CLAUDE.md globale.

```markdown
## Scelte in fondo ai file
Ogni file di codice termina con un blocco di commento "Scelte": al massimo cinque righe, una per scelta non ovvia, nella forma "scelta: motivo". Aggiorna il blocco quando una scelta cambia. Se non ci sono scelte non ovvie, niente blocco.
```

Il risultato in un file:

```python
# --- Scelte ---
# Dizionario al posto di una classe: i dati arrivano già come JSON e non hanno comportamento.
# Ricerca lineare: la lista non supera i 50 elementi.
```

### Git

- **Rami.** Un solo ramo base, `main`. Un ramo breve per ticket, per esempio `feat/123-export-csv`; per una specifica intera, il ramo di integrazione che crea `/implement-spec`.
- **Push.** Lo fai tu: il guardrail git di Pocock blocca ogni `git push` dell'agente, anche verso un ramo di lavoro. È una scelta: l'esempio ufficiale per i team mette `Bash(git push *)` tra le regole `ask`, cioè push con la tua conferma. Proteggi comunque `main` sul server.
- **Commit.** Conventional Commits, in inglese, con il riferimento alla issue: `feat(export): add CSV export for meetings (#123)`.
- **Controllo sul formato.** Un hook git `commit-msg`, che vale per le persone e per l'agente: commitlint nei repo TypeScript, `conventional-pre-commit` con il framework pre-commit nei repo Python.
- **Firma.** Tolta con `attribution`, come nei settings qui sopra.
- **PR.** Pubblichi tu il ramo; poi apri tu la PR, oppure la fai aprire all'agente con `gh pr create`, che a ramo già pubblicato non ha bisogno del push. Il corpo ha la forma della skill `/pr`: riepilogo visivo, prova prima e dopo, pericolo di merge.

### Versione e changelog

- **Standard.** SemVer per la versione. Keep a Changelog per `CHANGELOG.md`, in inglese, con le categorie Added, Changed, Deprecated, Removed, Fixed e Security.
- **A ogni modifica un frammento, non una riga nel file.** Con più sessioni o worktree sullo stesso repo, scrivere tutti in `CHANGELOG.md` produce conflitti. Ogni modifica aggiunge un file in `changelog.d/`; al rilascio i frammenti vengono raccolti in `CHANGELOG.md` e cancellati.
- **Strumento.** scriv usa `changelog.d/` e le sei categorie di Keep a Changelog già di default, e funziona in qualsiasi repo: `scriv create` crea il frammento, `scriv collect --version 1.4.0` li raccoglie.
- **Quale numero alzare.** `fix` alza la patch, `feat` la minor, un `!` o `BREAKING CHANGE` la major.
- **Chi rilascia.** Tu: l'agente aggiunge solo i frammenti. Al rilascio lanci `scriv collect --version <numero>`, alzi la versione e fai il push.
- **Alternativa per i pacchetti npm.** Changesets, che usa Pocock: alza anche la versione in `package.json`, ma il suo formato non è Keep a Changelog.

La configurazione di scriv in `pyproject.toml`; nei repo senza `pyproject.toml` le stesse chiavi vanno in `changelog.d/scriv.ini`, sezione `[scriv]`:

```toml
[tool.scriv]
format = "md"
changelog = "CHANGELOG.md"
md_header_level = "2"
entry_title_template = "[{{ version }}] - {{ date.strftime('%Y-%m-%d') }}"
```

Le ultime due righe danno i titoli di Keep a Changelog: `## [1.4.1] - 2026-10-06`, poi `### Fixed`. Metti in `CHANGELOG.md` il commento `<!-- scriv-insert-here -->` sotto l'intestazione: le nuove versioni vengono inserite lì.

Il controllo in CI, che fa fallire una PR senza frammento:

```bash
git diff --name-only origin/main...HEAD | grep -q '^changelog.d/' \
  || { echo "Manca il frammento di changelog in changelog.d/" >&2; exit 1; }
```

Aggiungi un filtro sui percorsi se vuoi esentare le PR di sola documentazione.

### Cosa è del team e cosa è solo tuo

- **Del team, committato nel repo:** `.claude/settings.json`, `.claude/output-styles/`, CLAUDE.md, `CODING_STANDARDS.md`, gli hook e i controlli in CI.
- **Solo tuo, su tutti i progetti:** `~/.claude/settings.json` e `~/.claude/output-styles/`. I settings del progetto hanno la precedenza sui tuoi.
- **Solo tuo, in un progetto:** `.claude/settings.local.json`, per scostarti dal team senza toccare i file condivisi.

## Parte 1 · Le decisioni di configurazione

Venti decisioni, ciascuna con il modo di applicarla.

| Tema | Decisione | Come si applica |
| --- | --- | --- |
| Contenuto di CLAUDE.md | Quasi vuoto. 200 righe è il tetto, non l'obiettivo | Per ogni riga chiediti se Claude l'avrebbe capito dal codice: se sì, cancellala. Restano le particolarità dell'ambiente, le convenzioni non scritte e il motivo di una scelta. Niente mappa del codice né comandi già presenti in `package.json` |
| `/init` | Mai il vecchio; il nuovo a intervista sì | Avvia con `CLAUDE_CODE_NEW_INIT=1` e contesta ogni riga proposta: "cosa aggiunge che il codice o un hook non garantiscono già?". È normale arrivare a un file di una o due righe |
| Lezioni di una sessione | Mai scritte in automatico in CLAUDE.md | Finiscono in un log o in `/retro`, e le rivedi tu. Una procedura diventa una skill, un divieto diventa un hook; in CLAUDE.md va solo ciò che vale in ogni sessione |
| Dopo un bug | Sempre un test di regressione; una regola solo se il problema si ripete | Chiedi la causa e un test che la riproduce, poi la correzione. Alla seconda volta scrivi la regola; se deve valere sempre, fanne un hook |
| Regole di comportamento generiche | Facoltative | Le quattro regole di Karpathy sono 65 righe sempre in contesto. Provale nel CLAUDE.md della cartella che contiene i tuoi progetti e confronta lo stesso compito con e senza: se non cambia nulla, toglile |
| `AGENTS.md` | Un solo file vero | Claude Code legge `AGENTS.md` solo se non esiste un CLAUDE.md. Se usi più agenti tieni `AGENTS.md` e in CLAUDE.md scrivi soltanto `@AGENTS.md`, oppure usa un link simbolico |
| Lunghezza delle skills | Brevi; 500 righe è il tetto | Il corpo sotto le 200 righe; il dettaglio in file di riferimento nella stessa cartella, che si caricano solo quando servono |
| Skills integrate di Claude Code | Non spegnerle in blocco | `disableBundledSkills` toglie anche `/code-review`, `/loop` e `/claude-api`. Per nasconderne una usa `skillOverrides` |
| Skills di terzi | Leggile prima di installarle | Una skill è un file di istruzioni di cui l'agente si fida. Leggi `SKILL.md` e gli script allegati; se sono molte usa uno scanner. Preferisci il marketplace ufficiale |
| Servizi esterni | CLI più skill dove esiste una CLI; MCP per il resto | GitHub e Supabase via CLI; Jira e Confluence via MCP. Aggiungi gli MCP con `--scope project` e controlla quanto pesano con `/context` |
| Workflow dinamici | Spenti | `enableWorkflows` a `false` nei tuoi settings; `disableWorkflows` a `true` per spegnerli a tutto il team. Riaccendili solo per compiti larghi, indipendenti tra loro e verificabili: consumano molto |
| Advisor | Spento | `/advisor off`. Se vuoi un secondo parere crea un subagent con il modello forte e chiamalo tu quando serve |
| Più agenti che collaborano | Sessioni con nome che si scrivono | Apri sessioni separate, dai a ciascuna un nome con `claude -n <nome>` o `/rename`, e nel prompt indica l'altra con `@nome`. Non usare gli agent teams: sono sperimentali, disattivati di default e non isolano gli agenti in worktree |
| Effort | Medio; basso su Fable 5.1 | `/effort medium`, che salva il livello per modello; su Opus 5.5 e Sonnet 5.5 è già il default. Alzalo con `/effort` per un singolo compito difficile, poi riabbassalo |
| `/goal` | Solo con una condizione che l'output può dimostrare | Il valutatore legge la conversazione e non esegue comandi. Scrivi "`npm test` esce con 0", non "il codice è corretto" |
| Pulizia del setup | A ogni nuovo modello | `/doctor prompt-audit`, poi `/skill-doctor` e `/context` in una sessione vuota. Togli ciò che il modello fa già da solo |
| Permessi | Segreti in `deny`; push bloccato dal guardrail | `Read(./.env)`, `Read(./.env.*)` e `Read(./secrets/**)` in `permissions.deny` del progetto. Nessuna regola `ask` sul push: lo blocca l'hook e lo fai tu |
| Sandbox | Accesa dove è supportata | `"sandbox": { "enabled": true }` nei settings del progetto, con i domini abituali in `allowedDomains`. Chiude ciò che le regole sui file non coprono; non sostituisce un container |
| Contesto a vista | Token nella status line | `/statusline`, mostrando i token e non la percentuale. Decidi ai confini di fase; `/autocompact 200k` solo come rete di sicurezza |
| Prova nel browser | Claude in Chrome, acceso solo quando serve | `claude --chrome` nelle sessioni in cui provi l'interfaccia, non "Enabled by default". In WSL o in CI: una skill con CLI oppure Playwright |

## Parte 2 · Il flusso di sviluppo con le skills di Pocock

Il flusso principale ha sette passi e due bivi: uno per i prototipi, uno per decidere se servono specifica e ticket. Quello che segue è lo stato alla versione 1.3.1.

**Due review con lo stesso nome.** La skill `code-review` di Pocock controlla standard e aderenza alla specifica; quella integrata di Claude Code cerca bug. Con l'installazione a plugin quella di Pocock è `/mattpocock-skills:code-review` e `/code-review` resta l'integrata. Con l'installazione a file quella di Pocock prende il nome `/code-review` e l'integrata resta raggiungibile come `/review`. In questa sezione `/code-review` indica sempre quella di Pocock.

### Installazione, una volta

1. **Scegli un solo metodo di installazione.** Con entrambi ti ritrovi ogni skill due volte.
   - Plugin gestito, in sola lettura, dal marketplace ufficiale: `claude plugins install mattpocock-skills` da terminale, oppure `/plugin install mattpocock-skills` dentro una sessione. Si aggiorna da solo quando il marketplace di Anthropic recepisce una nuova versione, anche giorni o settimane dopo la repo. Le skills prendono il prefisso `mattpocock-skills:`. Il guardrail git non è nel plugin: aggiungilo con `npx`, come nel set di base.
   - File modificabili nel tuo repo: `npx skills@latest add mattpocock/skills`, da aggiornare con `npx skills update`. Includi `setup-matt-pocock-skills` tra quelle selezionate.
2. **Scegli l'ambito.** A livello di progetto se lavori in team, globale se lavori da solo.
3. **Esegui `/setup-matt-pocock-skills` una volta per repo.** Ti chiede dove vivono le issue (GitHub, GitLab, markdown locale in `.scratch/`, oppure qualsiasi altro tracker descritto a parole, come Jira o Linear), quali etichette di triage usi e dove stanno i documenti di dominio. Scrive `issue-tracker.md`, `domain.md` e `triage-labels.md` in `docs/agents/` e un blocco "Agent skills" nel tuo CLAUDE.md o AGENTS.md.
4. **Crea a mano le etichette nel tracker.** Il setup le mappa ma non le crea: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`, più quelle di `/wayfinder`.
5. **Metti le tue preferenze in CLAUDE.md, non dentro i file delle skills.** Le modifiche a un `SKILL.md` vengono sovrascritte dal prossimo aggiornamento.
6. **Dopo un aggiornamento con `npx skills update`, cancella le cartelle delle skills rimosse**, come `resolving-merge-conflicts`: l'aggiornamento non sempre le elimina.

Se non sai quale skill usare, `/ask-matt` ti indica la prossima cosa da digitare.

### Il flusso principale

1. **`/grill-with-docs`: allineati.** L'agente ti intervista a round: ogni round contiene tutte le domande a cui si può già rispondere, numerate e con la risposta che consiglia. I fatti li cerca lui nel codice; le decisioni sono tue. Intanto aggiorna `GLOSSARY.md` e scrive un ADR solo per decisioni difficili da invertire, sorprendenti senza contesto e frutto di un vero compromesso. Non costruisce nulla finché non confermi.
2. **Bivio: serve vedere qualcosa?** Se una domanda riguarda come deve apparire o comportarsi una cosa, non risolverla a parole: `/handoff`, sessione nuova, `/prototype`, poi `/handoff` di ritorno. Per una domanda di logica o di stato il prototipo è un solo file HTML; per una di interfaccia sono più varianti sulla stessa pagina, con un selettore. La decisione validata entra nel codice vero; il prototipo resta su un branch `prototype/<nome>` come riferimento per chi implementa.
3. **Bivio: entra in una sessione?** Se sì, digita `/implement` qui e salta al passo 6. Se no, prosegui.
4. **`/to-spec`: scrivi la destinazione.** Non fa altre domande: sintetizza la conversazione, ti propone i punti in cui testare (il meno possibile, idealmente uno) e pubblica la specifica nel tracker.
5. **`/to-tickets`: scrivi il percorso.** Spezza la specifica in fette verticali che attraversano tutti i livelli, ognuna grande quanto una sessione, con le dipendenze dichiarate. Fino a qui resta nella stessa finestra di contesto: non compattare e non svuotare prima.
6. **`/implement`: costruisci, un ticket per sessione.** Usa `/tdd` nei punti concordati, controlla i tipi e i singoli file di test spesso, lancia la suite completa una volta alla fine, chiama `/code-review` e fa il commit sul branch corrente. Fai `/clear` tra un ticket e l'altro.
7. **Chiudi.**
   - `/code-review` chiede un punto fisso da cui confrontare (un branch o un commit) e usa due subagent paralleli: uno confronta il diff con gli standard documentati nel repo più dodici "code smell" di Fowler (nomi che non dicono cosa fanno, codice duplicato, astrazioni aggiunte per bisogni che non ci sono, e simili), trattati come giudizi e mai come violazioni; l'altro con la specifica.
   - `/pr` scrive il corpo della pull request in tre parti: un riassunto visivo, la prova prima e dopo, e il rischio di merge (reversibile o no, e quanto danno può fare). Si attiva da sola quando l'agente scrive il corpo di una pull request. Con il guardrail attivo il ramo lo pubblichi prima tu.
   - `/retro` rilegge la sessione e propone modifiche all'ambiente dell'agente, non al codice. Lanciala prima di svuotare il contesto; se l'hai già svuotato, indicale il log di quella sessione. Usala su un campione di sessioni e non in automatico: decidi tu cosa applicare.

Per lavorare molti ticket Pocock indica tre modi, dal migliore al peggiore. Uno script deterministico che legge ogni ticket e lancia `/implement`: è quello che consiglia ai più, perché gira sempre allo stesso modo e costa poco, ma richiede pazienza per metterlo a punto. La sua libreria [Sandcastle](https://github.com/mattpocock/sandcastle) fa questo, eseguendo gli agenti in sandbox Docker, Podman o Vercel. `/implement-spec`, dove un agente fa da supervisore: legge i ticket come un grafo, lancia un subagent per ticket nel proprio worktree, unisce tutto su un branch di integrazione e chiude con una review. È meno affidabile dello script ma è il modo più semplice per iniziare; produce un unico branch grande e sposta i conflitti al momento del merge. Infine a mano, un ticket alla volta.

Sul push i modi si comportano in modo diverso. `/implement-spec` apre una bozza di PR solo se il tracker chiude il lavoro tramite PR o se gliela chiedi: con il guardrail attivo non può pubblicare il ramo, quindi si ferma al ramo di integrazione e il push lo fai tu. In Sandcastle, nel video di Pocock, è un agente a unire i rami, dentro la sandbox e senza PR: è un'alternativa al guardrail, da scegliere sapendolo.

### Deviazioni dal flusso

| La situazione | Cosa usare |
| --- | --- |
| Un fatto esterno al repo blocca una decisione | `/research`, come agente in background; lascia un file markdown con le fonti |
| Il lavoro non si pianifica in una sessione e la strada non è chiara | `/wayfinder` per tracciare la mappa, poi `/wayfinder` con il link del ticket in una sessione nuova per ciascuno. A mappa chiusa, `/to-spec` |
| Bug e richieste che arrivano da altri | `/triage`. Non serve per i ticket creati da `/to-tickets` |
| Un bug difficile | `/diagnosing-bugs`, poi `/retro` nella stessa sessione |
| Il codice sta diventando difficile da cambiare | `/improve-codebase-architecture`, ogni pochi giorni |
| Una codebase esistente, senza test e già difficile da cambiare | Prima una rete di test sul comportamento attuale, poi `/improve-codebase-architecture` un'area alla volta; il flusso normale viene dopo |
| La decisione spetta a un'altra persona | `/to-questionnaire` |
| Un passo che solo un umano può fare, come credenziali o dashboard | `/wizard` |
| Un messaggio dell'agente che non capisci | `/wait-what` |

`/wayfinder` produce decisioni, non codice. I suoi ticket sono di quattro tipi: discussione, prototipo, ricerca e compito manuale. Pocock dice che sono i prototipi a impedirgli di diventare pianificazione a cascata.

`/improve-codebase-architecture` cerca dove trasformare moduli superficiali in moduli profondi, cioè molta implementazione dietro un'interfaccia semplice: più facili da testare e da leggere per un agente. Presenta le proposte in un report HTML e passa al grilling su quella che scegli.

### Le review integrate di Claude Code

Si affiancano a quella di Pocock, non la sostituiscono: lei controlla standard e specifica, queste cercano altro.

| Comando | Cosa controlla | Note |
| --- | --- | --- |
| `/code-review`, alias `/review` | Bug di correttezza nel diff; a effort alto anche pulizie | Gira come subagent in background, con un contesto proprio. `--fix` applica le correzioni, `--comment` le pubblica sulla PR. Segue CLAUDE.md ma non legge `REVIEW.md` |
| `/simplify` | Pulizia: riuso, semplificazione, efficienza | Applica le correzioni; non cerca bug |
| `/security-review` | Vulnerabilità nelle modifiche del ramo | Confronta con il ramo di default di `origin` |
| `/verify` | Che la modifica faccia ciò che deve | Costruisce ed esegue l'app e osserva il risultato, invece di fidarsi di test e tipi |
| `/code-review ultra` | Review profonda, con più agenti, nel cloud | Tre esecuzioni incluse sui piani Pro e Max, poi a crediti |

### Cosa fare del contesto ai confini di fase

La domanda si pone solo tra una fase e l'altra: a metà fase si prosegue, oppure si divide il lavoro che resta in subagent, perché compattare lì fa perdere il filo. Le opzioni si scartano in quest'ordine:

1. **Continua**, se la fase successiva ha bisogno di questa parola per parola o hai ancora margine.
2. **`/clear`**, se tutto ciò che hai dietro è sacrificabile.
3. **`/handoff`**, solo se qualcosa deve viaggiare: altro agente, altra cartella, un collega, un compito laterale.
4. **Subagent**, se il compito è abbastanza circoscritto da girare senza di te.
5. **`/compact`**, se nessuna delle precedenti vale.

### Errori frequenti nel grilling

- **Rispondere a parole a domande che richiedono di vedere qualcosa.** Fai un prototipo e torna.
- **Partire da un ambito troppo grande.** Chiedi all'agente di spezzarlo e interroga un pezzo alla volta.
- **Subire le domande.** È una conversazione: guidi tu, e decidi tu quando smettere di pianificare.
- **Usare un modello debole.** Nel grilling contano le idee che il modello porta da sé.

### Problemi noti

- **`/ask-matt` può dire che metà delle skills non sono installate.** Lo sono: digita comunque il comando.
- **`/ask-matt` descrive le altre skills dal proprio riassunto.** Prima di agire su una sua affermazione, chiedigli di aprire il relativo `SKILL.md`.
- **I subagent di `/code-review` possono richiamare `/code-review` e moltiplicarsi.** È un bug aperto: una segnalazione parla di oltre 50 agenti. Se lo lanci senza presidio, controlla quanti ne partono.
- **La review dentro `/implement` parte dalla sessione che ha scritto il codice.** I due assi girano in subagent a contesto pulito, ma a lanciarli e a riceverne i rapporti è la sessione che ha implementato. Per una review davvero indipendente, lancia `/code-review` da una sessione pulita.
- **Con il plugin, controlla quale review parte dentro `/implement`.** La skill chiama `code-review` per nome, e con il plugin quel nome è anche della review integrata: non ho verificato quale delle due venga scelta. Se il resoconto ha i due titoli Standards e Spec è quella di Pocock.
- **`/wayfinder` a volte inizia a scrivere codice di produzione.** Tieni l'implementazione in sessioni separate e limita la mappa a un obiettivo circoscritto.

### Le decisioni sul processo

| Tema | Decisione | Come si applica |
| --- | --- | --- |
| Punto di partenza | `/grill-with-docs` in un repo, `/grill-me` fuori. Non la plan mode | Non far costruire nulla finché non hai confermato. Se chi ha l'idea non è chi sviluppa, salva il risultato come `intent.md`. Pocock critica la plan mode perché produce un piano troppo presto |
| Modifiche piccole | Fuori dal flusso | Un refuso, una riga di configurazione, un bug di cui hai già il test che lo riproduce: chiedili direttamente, con il criterio di successo scritto. Se il lavoro sta in una sessione ma richiede decisioni: grilling, poi `/implement`, senza specifica né ticket. La soglia è una scelta di questo documento: Pocock non ne indica una |
| Come rispondere al grilling | A round, usando le risposte consigliate | Accetta in blocco ciò che va bene ("ok ai consigli, tranne 3 e 5") e discuti solo le decisioni vere. I fatti falli cercare all'agente nel codice |
| Ampiezza del grilling | Uno scopo piccolo per sessione | Con uno scopo troppo grande finisci il contesto prima delle conclusioni. Se una domanda riguarda aspetto o comportamento passa a `/prototype`. Usa il modello più forte che hai |
| Nomi dei file e delle skills | Quelli attuali | `git mv CONTEXT.md GLOSSARY.md` in un solo commit; `/to-spec`, `/to-tickets`, `/writing-for-agents`, `/domain-modeling`, `/triage`. Cancella a mano le cartelle delle skills rimosse |
| La specifica | Non è un documento vivo | A lavoro finito chiudi la issue. Ciò che deve durare va in `GLOSSARY.md`, negli ADR e nel codice. Se serve una traccia di audit usa come tracker i file markdown |
| Piano per ogni ticket | Nessuno: il ticket è il piano | Taglia ticket piccoli e verticali, eseguibili senza rileggere la specifica. Aggiungi un piano scritto solo se il team deve approvarlo prima del codice |
| Test | Prima del codice, uno alla volta, nei punti concordati con te | Mai tutti i test e poi tutto il codice. I controlli scritti in anticipo e bloccati servono solo ai loop non presidiati: pochi, sul comportamento, presi dai criteri della specifica |
| Refactor | Fuori dal ciclo rosso-verde | Si fa in review, non mentre si implementa |
| Review | Due, con scopi diversi | Quella di Pocock controlla standard e aderenza alla specifica; quella integrata cerca bug. Con il plugin sono `/mattpocock-skills:code-review` e `/code-review`; con i file sono `/code-review` e `/review`. In team aggiungi la review automatica in CI |
| Prototipo | Usa e getta, su un branch dedicato | Per la logica un solo file HTML, apribile anche da chi non sviluppa; per l'interfaccia più varianti sulla stessa pagina. Nel codice vero entra la decisione validata, non il prototipo |
| Molti ticket | `/implement-spec`; uno script deterministico quando il flusso è stabile | A mano, un ticket alla volta con `/clear` in mezzo, è l'ultima scelta |
| Push e PR | Il push lo fai tu | Il guardrail blocca ogni `git push` dell'agente. L'agente fa i commit sul ramo; tu pubblichi il ramo e apri la PR, o gliela fai aprire a ramo pubblicato |
| `/wayfinder` | Solo se la pianificazione non sta in una sessione | Produce ticket di decisione e poi consegna a `/to-spec` |
| Contesto | Sotto circa 150k token | È la "smart zone" che la skill `ask-matt` indica per i modelli attuali: tienila a vista nella status line. Grilling, specifica e ticket nella stessa finestra; poi una sessione per ticket. Ai confini di fase: continua, `/clear`, `/handoff`, subagent, `/compact` |
| Loop autonomi | Solo con una metrica che l'agente non può modificare | Mai sull'MVP. I dettagli sono nella sezione sul lavoro autonomo |

## Parte 2 · intent.md e la catena di artefatti

`intent.md` non è una funzione di Claude Code: è una convenzione proposta da Anthropic in [The AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook), un file che scrivi e committi tu prima di ogni specifica. Adottalo in due casi: quando chi ha l'idea non è chi sviluppa, e quando serve una traccia di audit.

### Cos'è

- **Cosa contiene.** Ciò che si vuole, perché, e sotto quali vincoli, nelle parole di chi ha il problema. Il playbook lo chiama "proto-spec".
- **Chi lo scrive.** L'originatore: chiunque abbia l'idea, il bug o l'incidente, anche un cliente o un product manager. Descrive il problema a Claude, che lo intervista e scrive il file; poi l'originatore lo rilegge e lo corregge.
- **Dove sta.** In una cartella `intent/` del repo, committato: autore e data entrano nella cronologia.
- **Chi lo approva.** Il product owner, che lo prende in carico dal backlog.
- **Come si crea.** Con una skill di intervista, per esempio `/grill-me`. Non esiste un template ufficiale: bastano quattro titoli, cosa si vuole, perché, vincoli, cosa resta fuori.

### La catena accanto al flusso di Pocock

| Fase del playbook | Artefatto | Chi approva | Nel flusso di Pocock |
| --- | --- | --- | --- |
| Plan | `intent.md` | Product owner | La conversazione di `/grill-with-docs`; di persistente restano `GLOSSARY.md` e gli ADR |
| Design | `spec.md`, con requisiti e design | Product owner; tech lead per i lavori più rischiosi | `/to-spec`, che scrive una issue nel tracker |
| Build | `plan.md`, prodotto in plan mode e committato | L'ingegnere, prima di implementare | `/to-tickets`, poi `/implement`: il ticket fa da piano |
| Test | Output di test e build | Chi possiede il codice, nella PR | `/tdd` dentro `/implement`, poi `/code-review` |
| Deploy | La PR con i rilievi della review automatica | Chi possiede il codice, tramite branch protection | `/pr` |
| Maintain | Un nuovo `intent.md`, scritto da Claude a partire da un alert o da un ticket | Chi possiede il servizio | `/triage` per le issue in arrivo, `/retro` a fine lavoro |

### Come adottarlo senza cambiare flusso

1. Crea la cartella `intent/` nel repo.
2. Chi ha l'idea esegue `/grill-me`, oppure `/grill-with-docs` se lavora nel repo, e chiude chiedendo di scrivere il risultato in `intent/<nome>.md`: cosa si vuole, perché, vincoli, cosa resta fuori. Lo rilegge e lo committa.
3. Chi sviluppa parte da quel file: `/grill-with-docs` solo sulle decisioni tecniche rimaste aperte, poi `/to-spec`.
4. Se ti serve la traccia di audit, scegli come tracker i file markdown locali durante `/setup-matt-pocock-skills`: specifica e ticket restano nel repo accanto all'intent.
5. Se lavori da solo puoi saltarlo: il grilling contiene già l'intento.

### Due pratiche da aggiungere in team

- **Valutare il processo.** Parti leggero: la review delle PR è già la tua valutazione, e se le PR respinte aumentano il sistema va corretto. Quando il flusso è stabile, raccogli una ventina di compiti già risolti con il risultato atteso e rieseguili a ogni cambio di skill o di modello; ogni incidente ne aggiunge uno.
- **Review automatica delle PR.** Due strade. La Code Review gestita da Anthropic, per i piani Team ed Enterprise e ancora in anteprima, commenta ogni PR e segue la politica scritta in `REVIEW.md` alla radice del repo; costa in media 15-25 dollari a review. Oppure un workflow tuo con la GitHub Action, che `/install-github-app` prepara: lì la politica va nel prompt del workflow o in CLAUDE.md, perché la documentazione non dice che `REVIEW.md` venga letto. In entrambi i casi chi possiede il codice approva tramite branch protection, e la PR resta il registro di ciò che è stato controllato.

## Parte 2 · Cosa aggiungere da Karpathy e da Cole Medin

Il flusso resta quello di Pocock. Da Karpathy e da Cole Medin si prendono sei pezzi che lo completano, più una pratica che è già nelle skills di Pocock; il resto dei loro metodi si sovrappone e non va installato accanto.

### Cosa aggiungere

| Cosa | Da dove | Come si fa | Quando serve |
| --- | --- | --- | --- |
| Criteri di successo scritti prima | Karpathy | Trasforma la richiesta in un obiettivo verificabile: non "correggi il bug" ma "scrivi un test che lo riproduce, poi fallo passare". Per i lavori a più passi chiedi un piano di tre righe, ognuna con la sua verifica | Nelle richieste rapide, fuori dal flusso. Dentro il flusso lo fa già `/tdd` |
| Loop su una metrica bloccata | Karpathy, `autoresearch` | Tre file: quello che l'agente modifica, quello di valutazione che non può toccare, e un `program.md` con le istruzioni del giro. Ogni giro ha un tempo fisso; la modifica si tiene o si scarta in base al numero | Solo per migliorare un numero misurabile: prestazioni, costo, punteggio di un test |
| Hook già pronti | Cole Medin, `coleam00/skills` | Copia in `.claude/hooks/` solo gli script che ti servono e unisci ai tuoi settings le voci corrispondenti del suo `settings.json.example` | La protezione di segreti e `rm -rf` sempre; lo stop sui test solo nelle sessioni non presidiate; gli altri a scelta. È un giudizio di questo documento sulla sua repo: nel workshop Cole Medin non tratta gli hook |
| Review automatica delle PR in CI | Cole Medin, starter pack | Copia `.github/workflows/claude-review.yml` e aggiungi al repo il secret `CLAUDE_CODE_OAUTH_TOKEN`; oppure lancia `/install-github-app`, che prepara workflow e secret da solo | Team su GitHub |
| Test di regressione dopo ogni bug | Pocock, `/diagnosing-bugs` | Prima della correzione chiedi la causa e una riproduzione minima, che diventa il test di regressione. La regola in più solo se il problema si ripete. Cole Medin nel workshop fa una scelta diversa: usa ogni bug per migliorare regole e skills | Sempre |
| MCP Atlassian | Cole Medin, starter pack | Copia il suo `.mcp.json` nel repo; al primo uso si apre l'accesso nel browser | Team su Jira o Confluence |
| Misurare se una regola serve | Cole Medin, skill `ablate-ai-layer` | Esegue lo stesso compito più volte con e senza le regole sempre caricate, in worktree usa e getta, e ti dice quali regole cambiano il risultato | Prima di aggiungere una regola a CLAUDE.md, e a ogni nuovo modello |

### Cosa lasciare

- **Le quattro regole di Karpathy come default.** Sono: pensa prima di scrivere codice (non dare per scontato, dichiara i dubbi), semplicità prima di tutto (niente oltre il richiesto), modifiche chirurgiche (tocca solo ciò che serve), esecuzione guidata dall'obiettivo (definisci prima risultato e verifica). Sono 65 righe a ogni sessione, e dentro il flusso il grilling e `/tdd` fanno già lo stesso lavoro. Restano facoltative: se vuoi provarle, `/plugin marketplace add forrestchang/andrej-karpathy-skills`, poi `/plugin install andrej-karpathy-skills@karpathy-skills`, e misura con e senza.
- **Le skills di Cole Medin accanto a quelle di Pocock.** I due set si sovrappongono: due modi di pianificare, due `code-review`. Insieme confondono te e l'agente, e le sole descrizioni delle 34 skills costano circa 4.400 token sempre in contesto.
- **CLAUDE.md come mappa del codice.** L'agente la ricava dal codice quando serve, e una mappa scritta invecchia al primo rename.
- **Un piano scritto per ogni ticket e i test dopo il codice.** Con ticket piccoli e verticali il piano è il ticket, e i test si scrivono prima.

## Parte 2 · Lavoro autonomo: loop, verifiche e sessioni parallele

Usa le skills di Pocock come spina dorsale e prendi dai loop solo i meccanismi di verifica qui sotto. Non sono pronti all'uso: il loop mostrato da AI LABS il 24 settembre usa una skill orchestratore, un agente che pianifica, una pagina per rivedere il piano, quattro skill di supporto e un hook di stop, e le loro skills sono nella community a pagamento. Qui trovi i principi e, dove esiste, la sintassi ufficiale.

### Quando un loop vale la pena

Servono tutte e quattro le condizioni:

1. Ripeti spesso quel tipo di compito.
2. I tuoi limiti d'uso lo reggono: un loop lungo esaurisce il piano da 20 dollari prima di finire.
3. Il risultato si verifica senza un umano, con un punteggio chiaro.
4. L'agente può eseguire ciò che ha costruito e vedere cosa si rompe.

Non mettere in loop l'MVP: definire "finito" richiede più tempo che costruirlo a mano. Usa i loop per una funzionalità alla volta.

### Tre comandi che si confondono

| Comando | Cosa fa | Quando |
| --- | --- | --- |
| `/goal` | Lavora finché la condizione che hai scritto è soddisfatta. Dopo ogni turno un modello piccolo la giudica leggendo la conversazione, senza eseguire comandi | Compiti con un controllo meccanico: "tutti i test passano" |
| `/loop` | Riesegue un prompt a intervalli, finché la sessione resta aperta | Attività periodiche locali, come aggiornare una base di conoscenza |
| Routine | Lavori ricorrenti nel cloud, attivi anche a portatile chiuso | Pulizia del codice, test mancanti, duplicati da unire |

### Le regole di verifica

Valgono per qualsiasi loop. Dove divergono dalle skills di Pocock è detto nella tabella più sotto.

- **I controlli si scrivono prima del codice, da un agente diverso.** Chi scrive il codice tende a scrivere test che il proprio codice supera. Questo vale per i controlli di accettazione di un loop; dentro un singolo ticket i test si scrivono uno alla volta, come prescrive la skill di Pocock.
- **I controlli sono bloccati.** Spostali in una cartella che una regola nei settings vieta all'agente di modificare, e fai un commit. Per esempio `"deny": ["Edit(/checks/**)"]` dentro `permissions`, nei settings del progetto. La regola ferma gli strumenti di modifica e i comandi che nominano quei file; con la sandbox accesa il divieto vale anche per gli script. Il video del 2 ottobre non indica né la cartella né la regola: queste vengono dalla documentazione.
- **Un controllo deve poter fallire.** "Guardalo e dimmi se è meglio" non è un controllo.
- **Serve la prova, non la dichiarazione.** Per ogni controllo: il comando, l'output atteso, l'output ottenuto.
- **La review è avversariale e a contesto pulito.** Un subagent o una nuova sessione avviata con `claude -p`, sul modello più forte.
- **I cancelli si impongono con un hook di stop**, non con una frase nelle istruzioni: l'esempio è nella sezione sugli hook.
- **Due momenti restano tuoi:** approvare il piano e provare il risultato finale.

### Pocock e i loop di AI LABS: cosa corrisponde e cosa no

I due mondi sono il flusso di Pocock, dove decidi a ogni passo, e i loop autonomi mostrati da AI LABS, dove decidi all'inizio e alla fine. I loop sono tre sistemi diversi, da non sommare:

- **Loop a cancelli** (24 settembre, ricostruito da AI LABS sul metodo Helix di Shopify). Una funzionalità viene divisa in checkpoint, dal più semplice al più complesso. Ognuno deve superare quattro cancelli prima che parta il successivo: comportamento (test che non richiedono il browser), interfaccia (confronto con un prototipo HTML), review avversariale (un agente critica, un altro corregge, finché il primo approva) e prova finale tua. Un hook di stop con codice 2 impedisce di passare oltre.
- **Coda di funzionalità** (18 agosto, la "software factory"). Un file markdown con una riga per funzionalità e tre stati: da fare, in costruzione, fatto. Un subagent per riga, su un branch proprio, con una pull request e gli screenshot. `/goal` si ferma quando non restano righe aperte.
- **Loop che si migliora** (2 ottobre). I controlli, dopo la tua approvazione, vengono spostati in una cartella protetta. Dopo ogni funzionalità un secondo loop rilegge i risultati e riscrive la parte "come lavorare" delle istruzioni (`program.md`), senza poter toccare i controlli.

| Passo di Pocock | Cosa gli somiglia nei loop | Dove divergono |
| --- | --- | --- |
| `/grill-with-docs` | Le domande dell'agente che pianifica i checkpoint | Nel loop le domande sono poche e iniziali; nel grilling sono il lavoro |
| `/to-spec` | La descrizione della funzionalità data all'orchestratore | Nel loop non c'è una specifica nel tracker: il piano è il file dei checkpoint, che approvi tu |
| `/to-tickets` | I checkpoint; le righe della coda | I checkpoint sono in sequenza stretta; i ticket sono fette verticali con dipendenze dichiarate, lavorabili in parallelo |
| `/implement` con `/tdd` | Il cancello di comportamento | Opposti sui test. Nel loop altri subagent scrivono prima tutti i test del checkpoint, poi un altro scrive il codice. Per Pocock li scrive lo stesso agente, uno alla volta, e scriverli tutti prima è un errore |
| `/prototype` | Il prototipo HTML del cancello di interfaccia | Nel loop è il riferimento contro cui si verifica l'interfaccia; per Pocock risponde a una domanda e poi resta su un branch a parte |
| `/code-review` | Il cancello di review avversariale | Nel loop critica e correzione si alternano da sole finché la critica approva; la review di Pocock riporta su due assi, standard e specifica |
| `/implement-spec` | La coda di funzionalità | Entrambi usano un subagent per unità di lavoro. `/implement-spec` unisce tutto su un ramo di integrazione; la coda apre una pull request per funzionalità |
| `/retro` | Il file delle lezioni; il secondo loop | Opposti. Il loop a cancelli scrive i tuoi rilievi in un file che ogni agente legge, e il secondo loop riscrive le istruzioni da solo; `/retro` propone e decidi tu. Questo documento sceglie `/retro` |

### Sessioni parallele

- **Un worktree per sessione.** `claude --worktree <nome>`, o `-w`, crea una copia di lavoro in `.claude/worktrees/<nome>/`, su un ramo nuovo `worktree-<nome>` che parte dal ramo di default remoto. Evita che le sessioni sovrascrivano gli stessi file o litighino sui branch. Metti `.claude/worktrees/` in `.gitignore`.
- **I file che git ignora non ci sono.** Un worktree è un checkout pulito: elenca in `.worktreeinclude`, alla radice del repo, i file da copiarci, come `.env`. Le dipendenze vanno installate lì, oppure collegate con `worktree.symlinkDirectories`.
- **Sessioni in background.** `claude agents` apre l'elenco; `/bg` manda in background la sessione corrente, `claude --bg "<compito>"` ne avvia una nuova, `claude attach <id>` la riapre e `claude stop <id>` la ferma. Quelle avviate dall'elenco passano da sole in un worktree proprio prima di modificare file. La vista è ancora in anteprima.
- **Un container o una VM per sessione** se cambiano dipendenze, database o porte locali. I worktree isolano solo i file, e la sandbox di Claude Code limita file e rete dei comandi ma non separa database e porte. Il video del 20 luglio usa Docker Sandboxes, che ne era lo sponsor.
- **Un solo proprietario per file condiviso.** Le altre sessioni lo leggono soltanto.
- **Pianifica prima la scomposizione** in compiti indipendenti, poi affida ogni compito a una sessione in background.
- **Fai parlare le sessioni tra loro** invece di copiare contesto. Dai un nome a ciascuna con `claude -n <nome>` o `/rename <nome>`; poi nel prompt scrivi `@nome` e Claude manda all'altra sessione solo ciò che serve. `/list-agents` mostra quelle raggiungibili. È attivo di default dalla versione 2.1.224. Un messaggio arrivato da un'altra sessione non può approvare permessi né cambiare la configurazione.
- **Subagent isolati.** Chiedi a Claude di usare i worktree per i suoi subagent, oppure metti `isolation: worktree` nel file del subagent.
- **Tenere d'occhio qualcosa.** Il Monitor non è un comando: è uno strumento che Claude usa quando glielo chiedi a parole, per esempio "segui i log del server e avvisami agli errori". Lancia un comando in background e reagisce a ogni riga di output.
- **Per riprendere:** `claude --continue`, `claude --resume <nome>`, `/recap`. Per provare un'altra strada: `/branch`, che copia la conversazione e ti ci sposta. Per un compito laterale: `/subtask`, che lo affida a un subagent e riporta qui il risultato, oppure `/fork`, che copia la conversazione in una nuova sessione in background.
- **Niente agent teams.** Sono sperimentali, disattivati di default e non isolano gli agenti in worktree. Il video del 29 giugno li usa: tenerli fuori è una scelta di questo documento.

### Quanto costa l'autonomia

| Esecuzione | Costo riportato |
| --- | --- |
| Loop con /goal su una landing page animata | 38 minuti senza supervisione, con un errore rimasto da correggere a mano |
| Costruzione di un'app intera con il loop "gauntlet": un prompt di tre righe di Matt Shumer, con agenti che costruiscono e agenti che criticano | 1 ora e 33 minuti, circa il 40% del limite di sessione, circa 116 dollari a prezzi API |
| Workflow di ricerca approfondita su un tema piccolo | Circa 1 milione di token |
| Riscrittura di un milione di righe con workflow dinamici | Circa 165.000 dollari a prezzi API, e 19 rotture non rilevate dai controlli |

### Strumenti di terzi facoltativi

Sono facoltativi. Installane uno alla volta e misura con `/context` quanto contesto aggiunge: quasi tutti installano hooks e skills proprie, e sommati ricreano il problema che volevi risolvere.

| Strumento | Cosa fa | Avvertenza |
| --- | --- | --- |
| Graft | Mappa del codice che indica all'agente dove guardare, mantenuta da hooks | Mappa solo il codice. I risparmi dichiarati (42% di token in meno) sono degli autori; in una prova, 39 minuti contro 47 |
| Reticle | Fa provare l'app in un browser prima di dichiararla finita | Nessuna segnalata |
| Caliper | Misura se una skill migliora davvero il risultato, con e senza | Consuma token per ogni prova |
| Skill Spector | Scansiona una skill alla ricerca di istruzioni nascoste e codice malevolo | La scansione con modello è disattivata di default |
| Chisle | Risposte più corte e output degli strumenti ripulito | Installa quattro skills e tre hooks |
| Anti-Slop | Controlli automatici sui difetti tipici del codice generato | Solo JavaScript e TypeScript |
| unlazy | Registro di controlli con prova obbligatoria per ogni voce | Lento così com'è: 3-4 ore per una pagina di login in una prova |
| Agit | Versiona e condivide le conversazioni, anche tra agenti diversi | Le password senza un formato riconoscibile possono finire nello storico; un repo reso pubblico non torna privato |

Le repo di Chisle, Caliper, Reticle e Anti-Slop sono nelle fonti. Per Graft, unlazy, Skill Spector e Agit non ho annotato l'indirizzo: si parte dal video corrispondente, nella tabella dei video.

## Jev e le alternative open source

Jev è un modello che decide invece di scrivere: gli dai una situazione e delle domande chiuse, e risponde con valori tipizzati e una probabilità. In Claude Code serve dentro gli hook, dove una regex sbaglia troppo e un LLM costa troppo. Per provarlo senza dipendere da un servizio chiuso, l'alternativa open source più pronta è Rizzo Flow di Simone Rizzo.

### Cos'è

- **Chi e quando.** TypeSafe AI, in accesso anticipato dal 15 settembre 2026. È un servizio chiuso, raggiungibile solo via API.
- **Cosa fa.** Tre tipi di domanda: sì o no (`noul`), scelta tra opzioni (`choice`, fino a 255) e punteggio su una scala (`score`). Non genera testo.
- **Quanto costa.** 0,042 dollari per milione di token in ingresso; le risposte sono gratuite. TypeSafe dichiara tempi tra 70 e 500 millisecondi e una velocità da 40 a 200 volte quella di un LLM sugli stessi compiti: sono numeri del produttore. Cole Medin, nel suo video, riporta numeri diversi: da 20 a 200 volte più veloce e da 40 a 1.000 volte più economico.
- **Come si accede.** A fine settembre le iscrizioni dirette erano in pausa; è disponibile tramite OpenRouter e Vercel AI Gateway.
- **Non lavora mai da solo.** Un LLM prepara situazione e domande, Jev decide, un LLM agisce sul risultato.
- **Il limite da ricordare.** Tutto ciò che metti nella situazione va al provider: niente segreti.

### Dove serve in Claude Code

| Uso | Dove si aggancia | Cosa aspettarsi |
| --- | --- | --- |
| Guardia di sicurezza: segreti, dati distrutti, esfiltrazione, agente fuori tema | Hook `PreToolUse` | Sostituisce una lista di regex piena di falsi positivi. Circa un quarto di secondo a controllo, contro oltre un secondo con un LLM piccolo |
| Rispetto delle regole di un file | Hook prima di ogni modifica | Manda a Jev la modifica e le regole di quel file; blocca sopra l'80% di certezza e dice a Claude quale regola ha violato |
| Scelta della skill adatta al prompt | Hook `UserPromptSubmit` | Soglia utile intorno a 0,7. Costa 2-3 secondi a turno e sbaglia sulle frasi generiche: provalo prima in ombra. Soglia e tempi non compaiono nei due video riletti: ricontrollali sulla repo degli hook prima di fidarti |
| Scelta del modello per un subagent, o del percorso di un lavoro | Hook prima del subagent, o primo passo di un workflow | Classifica bug o funzionalità e il livello di modello necessario. Cole Medin riporta 12 classificazioni su 12 condivise e 15 su 16 nella scelta del tipo di review, giudicate da lui stesso |
| Pre-esame della code review | Prima della review completa | Sette domande sì o no decidono se serve la review intera o una breve. Non sostituisce il revisore |
| Compattazione, ricerca dei file, prova nel browser | Plugin e skills dedicati | Utile dove conta la velocità: per esempio ordinare 35 file candidati in meno di due secondi. Gli strumenti pronti sono nella tabella qui sotto |

### Otto strumenti pronti che usano Jev

Vengono dal video di AI LABS "Insane Tools That Actually Fix Your Claude Code Setup With Jev", letto il 7 ottobre. I comandi di installazione e gli indirizzi delle repo sono mostrati a schermo e non detti a voce: qui mancano. Tutti richiedono una chiave per Jev: quella di TypeSafe oppure, dove lo strumento lo consente, OpenRouter o Vercel AI Gateway.

| Strumento | Cosa fa | Come si aggancia | Cosa riporta il video |
| --- | --- | --- | --- |
| Toolgate | Prima di ogni azione chiede a Jev se è permessa: è più severo dell'auto mode. Blocca ciò che non si può annullare, i tentativi di prompt injection, l'invio di dati all'esterno, l'uso di permessi mai concessi, le azioni fuori dal compito e le decisioni che avevi riservato a te | Installazione da terminale, comando per la chiave, poi `toolgate init`, che lo collega a Claude Code | Su una cancellazione fatta senza copia ha dato un rischio del 77%: di norma chiede conferma, con i permessi disattivati blocca. Limite: ferma anche le cancellazioni necessarie, che restano a te |
| Abide | Trasforma `AGENTS.md` e `CLAUDE.md` in una rubrica di domande sì o no, controlla ogni modifica e fa correggere a Claude ciò che viola una regola prima di chiudere | Installazione con scelta della chiave e dell'ambito, poi il suo comando di init; la rubrica la fai creare a Claude dentro la sessione | Nella prova: 49 regole, 33 delle quali affidate a Jev. Funziona anche con Codex |
| Jev Browser | Prova dell'app nel browser: Claude guida il test, Jev decide sì o no su ciò che è a schermo | Server MCP; nel prompt chiedi di usare i suoi strumenti | Il comando unico ha installato una versione vecchia: meglio far installare a Claude l'ultima. Di default accetta solo la chiave di TypeSafe. Un test in circa 2 minuti, chiuso da un elenco dei bug |
| Jev Belay (nome incerto nella trascrizione) | Impedisce a Claude di dichiarare finito un compito che non lo è: a ogni chiusura Jev rilegge la conversazione e cerca la prova; se manca, rimanda Claude al lavoro | Plugin da un marketplace; chiede ambito, chiave e soglia | Soglia usata: 75%. Ha un registro delle decisioni e un'opzione che mostra cosa sarebbe successo senza di lui |
| Jev Steer or Queue | Decide cosa fare di un messaggio che invii mentre Claude lavora: consegnarlo a fine passo, che è il comportamento normale; tenerlo in coda fino a lavoro finito; interrompere subito | Plugin, anche per Codex | Agisce solo quando Jev è sicuro almeno al 90% |
| Compact Advisor | Dopo ogni risposta dice se è il momento giusto per compattare | Installazione dalla repo; al primo avvio chiede la chiave e il contesto minimo | Ha consigliato di compattare intorno a 100k token, a lavoro concluso, e mai con una domanda in sospeso |
| Quicksilver | Fa scegliere a Jev i file rilevanti, così Claude legge solo quelli | Un comando da terminale; poi lo chiedi nel prompt | 37 file esaminati in circa 2 secondi, circa 67.000 token che Claude non ha dovuto leggere |
| Jev SEO | Analizza un sito e produce un report SEO in PDF, con un punteggio per area, e un foglio Excel di correzioni | Skill, con un comando seguito dall'indirizzo del sito | Fuori tema per la configurazione; il sito di prova ha ottenuto circa 76 |

Come si collocano rispetto alle scelte di questo documento:

- **Toolgate e Abide sono la versione pronta delle prime due righe della tabella precedente.** Prima di adottarli vale l'ordine di introduzione più sotto: script, poi ombra, poi blocco.
- **Jev Belay è un cancello basato su un giudizio, non su un controllo.** Dove esiste un test o uno script resta preferibile l'hook di stop: un controllo deve poter fallire. Belay serve dove un controllo meccanico non c'è.
- **Per la prova nel browser parti da Claude in Chrome**, che non richiede altre chiavi. Jev Browser ha senso se vuoi test più rapidi e hai già una chiave di TypeSafe.
- **Compact Advisor non sostituisce la regola dei confini di fase.** La applica con un consiglio automatico; i 100k token del video sono sotto la soglia dei 150k.
- **Tutti mandano dati al provider di Jev.** Per come sono descritti, Toolgate invia ogni azione, Abide ogni modifica e Jev Belay l'intera conversazione: vale il limite già detto sui segreti.
- **Uno alla volta.** Ognuno aggiunge hook, plugin o un server MCP: misura con `/context` e tieni solo ciò che cambia il risultato.

### Le alternative open source

| Progetto | Cos'è | Licenza | Numeri dichiarati | Limiti |
| --- | --- | --- | --- | --- |
| [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow), di Simone Rizzo | Un server locale su llama.cpp, con un modello da 4 miliardi di parametri affinato per le decisioni. Espone la stessa API di Jev: il codice scritto per TypeSafe punta a `localhost` cambiando un indirizzo. Include una skill per gli agenti | Apache-2.0 | Accuratezza 0,648 contro 0,727 di Jev sul benchmark typed-decisions; circa 50 ms a decisione su una RTX 5060 Ti; 5,6 GB di memoria GPU | Fino a 26 opzioni per domanda; probabilità non calibrate; provato dagli autori su una sola macchina; l'inglese è la lingua più solida |
| [Open Alternative to Jev](https://github.com/ikermoel/open-alternative-jev) | Una libreria Python che ottiene decisioni tipizzate da qualsiasi modello open, senza addestramento. Non offre un server HTTP | Apache-2.0 | 73,7% con un modello da 27 miliardi di parametri, sopra Jev; 59% con uno da 4 | Per superare Jev serve una GPU da data center |
| [SemIf](https://github.com/TheoLeeCJ/SemIf) | Il progetto che ha ispirato Rizzo Flow | MIT | Non letti | L'ho solo clonato |

Rizzo Flow si avvia con quattro comandi: `git clone` della repo, `uv sync --locked`, `uv run rizzo download` (circa 4,4 GB) e `uv run rizzo serve`. Gli hook pronti di `jev-agent-hooks` chiamano invece il servizio di TypeSafe, con l'indirizzo scritto nel codice: per usarli con Rizzo Flow vanno modificati. Esistono altri progetti, come Laya, che non ho letto.

### Come introdurlo

1. Parti dagli hook a script: sono gratuiti e prevedibili.
2. Aggiungi un modello di decisione solo dove lo script blocca troppo o troppo poco.
3. Provalo prima in modalità ombra: registra cosa avrebbe deciso, senza bloccare. `jev-agent-hooks` la offre già.
4. Fallo fallire aperto: se il servizio non risponde, l'azione passa. Per i divieti assoluti tieni comunque uno script.
5. Non mettere soglie vicino a 0,5: la repo di Rizzo Flow avverte che i quasi pareggi possono ribaltarsi.

## Checklist di avvio

L'ordine conta: prima misuri e pulisci, poi configuri il repo, poi sviluppi.

### Una volta, sul tuo computer

- [ ] Apri una sessione vuota ed esegui `/context` per vedere quanto consuma il setup attuale
- [ ] Esegui `/doctor prompt-audit` e `/doctor`, e applica solo le correzioni che condividi
- [ ] Esegui `/skill-doctor` ed elimina le skills che non usi
- [ ] Aggiungi a `~/.claude/settings.json` le chiavi della Parte 1 che ti servono
- [ ] Configura la status line con i token nel contesto: `/statusline`
- [ ] Se lavori su interfacce web, installa l'estensione Claude in Chrome e controlla il collegamento con `/chrome`
- [ ] Esegui `/fewer-permission-prompts` nei progetti su cui lavori di più
- [ ] Scegli modello ed effort di default in base al tuo piano
- [ ] Installa le skills di Pocock con un solo metodo

### Per ogni repo: la base

- [ ] Riduci `CLAUDE.md` alle sole righe non ricavabili dal codice e valide sempre
- [ ] Se usi più agenti, tieni un solo file tra `CLAUDE.md` e `AGENTS.md` e collega l'altro
- [ ] Metti in `permissions.deny` i file con i segreti e controlla il risultato con `/permissions`
- [ ] Accendi la sandbox dove è supportata ed elenca i domini abituali
- [ ] Aggiungi il guardrail git e provalo nei due sensi con un payload finto
- [ ] Converti in hook le altre regole deterministiche, come la CLI da usare
- [ ] Controlla con `/hooks` che compaiano e con `/context` quanto costa il setup
- [ ] Installa il plugin LSP del tuo linguaggio e il relativo language server
- [ ] Verifica che test, controllo dei tipi e lint si lancino con un solo comando ciascuno, e che qualcosa li esegua davvero: un hook di pre-commit o la CI
- [ ] Scrivi un `CODING_STANDARDS.md` solo per le scelte di giudizio; il resto va in lint o CI
- [ ] Aggiungi `.claude/worktrees/` a `.gitignore` e, se usi i worktree, crea `.worktreeinclude`

### Per ogni repo: skills, MCP e intent.md

- [ ] Esegui `/setup-matt-pocock-skills` e crea le etichette nel tracker
- [ ] Se esiste un `CONTEXT.md`, rinominalo in `GLOSSARY.md` con `git mv`
- [ ] Per ogni servizio esterno scegli CLI più skill se esiste una CLI; altrimenti aggiungi l'MCP con `--scope project`
- [ ] Imposta `disableClaudeAiConnectors` a `true` se in Claude Code non usi i connettori dell'app
- [ ] Decidi se ti serve la cartella `intent/`: sì se chi ha l'idea non è chi sviluppa, o se serve una traccia di audit
- [ ] Se il team lavora su GitHub, aggiungi la review automatica delle PR con `/install-github-app`

### Per ogni repo: preferenze del team

- [ ] Aggiungi a `.claude/settings.json` le chiavi `language`, `outputStyle` e `attribution`
- [ ] Crea `.claude/output-styles/diretto.md` e riavvia Claude Code
- [ ] Incolla in CLAUDE.md le righe su lingue e changelog
- [ ] Scrivi in `CODING_STANDARDS.md` le regole per docstring e commenti, e attiva il lint
- [ ] Configura scriv, crea `changelog.d/` e aggiungi il controllo in CI
- [ ] Attiva il controllo sul formato dei commit e proteggi `main` sul server
- [ ] Nei progetti legati a compiti, aggiungi al loro CLAUDE.md la regola sul blocco "Scelte"

### Per ogni funzionalità

- [ ] `/grill-with-docs` fino alla conferma di comprensione condivisa
- [ ] Se serve vedere qualcosa: `/handoff`, `/prototype` in una sessione nuova, `/handoff` di ritorno
- [ ] Se servono più sessioni: `/to-spec`, poi `/to-tickets`, senza svuotare il contesto in mezzo
- [ ] `/implement` un ticket per sessione, con `/clear` in mezzo; oppure `/implement-spec`
- [ ] Per una review indipendente, la `/code-review` di Pocock da una sessione pulita
- [ ] Pubblica tu il ramo, poi apri la pull request o falla aprire all'agente
- [ ] Leggi il corpo della pull request e la sezione sul rischio di merge prima di approvare
- [ ] `/retro` sulle sessioni in cui l'agente ha fatto qualcosa di strano, prima di svuotarle

### A ogni nuovo modello

- [ ] Riesegui `/doctor prompt-audit`
- [ ] Prova i compiti abituali con `claude --safe-mode`: ciò che funziona senza setup si può togliere
- [ ] Aggiorna le skills di Pocock e leggi il changelog per rinomine e rimozioni
- [ ] Rivedi effort e modello di default

## Video analizzati

Ho scelto i video tra i 50 più recenti di AI LABS (18 maggio – 5 ottobre 2026) e tra tutti quelli di Pocock da gennaio 2026, privilegiando i più recenti. Tutte le date sono del 2026.

Il 6 e 7 ottobre ho letto o riletto 38 dei video elencati qui sotto, tutti tranne quello di Rob Shocks, tramite youtubetotranscript.com: un video per lettura, con domande mirate sui punti dubbi. Ogni lettura restituisce una sintesi con brevi citazioni, non il testo intero. I titoli su YouTube cambiano: una decina di questi video oggi ne mostra uno diverso da quello in tabella, quindi a identificarli è il link.

### AI LABS: 20 video

| Data | Video | Cosa ne ho preso |
| --- | --- | --- |
| 5 ott | [You Need To Add This In Your Claude Code Setup Right Now](https://www.youtube.com/watch?v=i6Q7bXnWGlM) | Nuovo init, import, prompt audit, impostazioni di contesto, sessioni che si scrivono |
| 2 ott | [He Finally 10x Claude Code With This Method](https://www.youtube.com/watch?v=qLfSDQ5NGh0) | Quando usare un loop, controlli bloccati, loop che migliora le proprie istruzioni |
| 24 set | [Shopify Just Released The Greatest AI Coding Workflow Ever](https://www.youtube.com/watch?v=bBMp5tLxShQ) | Checkpoint e quattro cancelli imposti con un hook |
| 22 set | [This New Open Source Tool Just Fixed Your Claude Code Workflow](https://www.youtube.com/watch?v=CHHEjuNBxoQ) | Agit: versionare e condividere le conversazioni |
| 14 set | [Insane GitHub Repos That 10x Your Codex And Claude Code Setup](https://www.youtube.com/watch?v=Ua0APTMVcb8) | Reticle, Chisle, Caliper, Anti-Slop |
| 8 set | [Github Top Trending Tool Just Fixed The AI Agent's Biggest Problem](https://www.youtube.com/watch?v=cyIWQHYoUg8) | Graft: mappa del codice per ridurre le ricerche |
| 5 set | [You Are Using Fable 5.1 Wrong (Do This Instead)](https://www.youtube.com/watch?v=7au4tWVG8a0) | Effort basso, togliere le istruzioni vecchie, prompt per lavori lunghi |
| 1 set | [These New Claude Skills Are Actually Insane](https://www.youtube.com/watch?v=jyLKRN36-Dc) | Registro delle lezioni, le 4 regole di Karpathy |
| 28 ago | [How To Never Run Out Of Codex and Claude Usage Limits](https://www.youtube.com/watch?v=jwje1JK8Nqs) | 24 consigli su contesto e limiti d'uso |
| 20 ago | [GitHub's #1 Trending Author's New Claude Skill Is Insane](https://www.youtube.com/watch?v=c47uqR7XB_c) | unlazy: controlli con prova obbligatoria |
| 18 ago | [Every Level Of Claude Code Loop Engineering Explained](https://www.youtube.com/watch?v=PLyRe6Zk--8) | `/goal` contro `/loop`, niente loop sull'MVP, "software factory" |
| 14 ago | [This Claude Skill Just Fixed Loop Engineering](https://www.youtube.com/watch?v=D_uojDHkbw4) | Limiti del loop "gauntlet"; `/wayfinder` come fonte dei requisiti |
| 10 ago | [This Claude Code Skill make Building 10x Faster](https://www.youtube.com/watch?v=b9k-AE4v5yI) | Cercare ciò che esiste già prima di costruire |
| 31 lug | [Claude Code Setup Guide By The Creator Himself](https://www.youtube.com/watch?v=pGro_uKt-_M) | Ripulire il setup a ogni modello; prompt, CLAUDE.md, skill, MCP in ordine di costo |
| 29 lug | [Anthropic Just Fixed Graph Engineering's Greatest Flaw](https://www.youtube.com/watch?v=H7t3uUp3HVw) | Verifica nei lavori multi-agente; il modello del revisore |
| 20 lug | [Fleet Engineering Is Insane...](https://www.youtube.com/watch?v=qxjII6x2yPY) | Sessioni parallele, worktree, sandbox |
| 6 lug | [How To Use Claude Fable 5 Better Than 90% Of The People](https://www.youtube.com/watch?v=GM7-ei-4Xc8) | Effort, modello grande per pianificare, autore dei test separato |
| 29 giu | [The Top Claude Code Features We Use](https://www.youtube.com/watch?v=ECQA6oOyfIk) | Auto mode, goal, loop, monitor, comandi di review |
| 3 giu | [These Claude Workflows Turn Claude Code Into A Whole OS](https://www.youtube.com/watch?v=5LnwJyi1il4) | Workflow dinamici: quando servono e quanto costano |
| 21 mag | [Anthropic Just Revealed The Best Claude Code Setup](https://www.youtube.com/watch?v=lGalJmyI78w) | I pezzi del setup per codebase grandi, LSP compreso |

### Matt Pocock: 10 video

Sei li ho letti dalla trascrizione, compreso quello del 5 ottobre sulla v1.3; gli altri quattro dagli articoli e dalle pagine che Pocock pubblica per gli stessi video. Il 6 ottobre ho ricontrollato sulla trascrizione anche i changelog v1.1 e v1.2 e il video sui nove errori del grilling. Tutto è stato poi confrontato con i file delle skills nella repo.

| Data | Video | Come l'ho letto | Ancora valido? |
| --- | --- | --- | --- |
| 5 ott | [New Skills! v1.3 brings /pr, /implement-spec, and /retro](https://www.youtube.com/watch?v=BsJGo1wFTvQ) | Trascrizione, changelog e repo | Sì: è lo stato attuale |
| 5 ago | [New Skills! v1.2 brings /wait-what, /writing-for-agents, and fixes /grill-me](https://www.youtube.com/watch?v=gaDdrDdczO4) | Articolo completo | Sì, salvo il nome `CONTEXT.md` |
| 30 lug | [/wayfinder: Nothing is too big to plan anymore](https://www.youtube.com/watch?v=F3lL98Pj90o) | Trascrizione e pagina della skill | Sì |
| 23 lug | [Don't waste time on specs: /prototype instead](https://www.youtube.com/watch?v=n0VhIVtviC0) | Trascrizione e skill | Sì; il prototipo di logica oggi è un file HTML |
| 16 lug | [mattpocock/skills: A complete AI Coding workflow, end-to-end](https://www.youtube.com/watch?v=M6mYodf0dJM) | Trascrizione | Sì; da allora plugin, `/implement-spec`, `/pr`, `/retro` |
| 8 lug | [New Skills! v1.1 brings /wayfinder, /research, /implement, /to-spec, /to-tickets](https://www.youtube.com/watch?v=A8mokin_YOs) | Articolo completo | Sì; le domande ora sono a round |
| 25 mag | [9 Things People Get Wrong With My /grill-\* skills](https://www.youtube.com/watch?v=UzMNBN6xLLA) | Articolo completo | Sì nei principi; nomi e soglia di contesto superati |
| 21 mag | [/handoff is my new favourite skill](https://www.youtube.com/watch?v=dtAJ2dOd3ko) | Pagina della skill, aggiornata il 24 agosto | Ridimensionato: solo quando il lavoro deve viaggiare |
| 14 mag | [I stopped using /grill-me for coding. Here's what I use instead](https://www.youtube.com/watch?v=6BB6exR8Zd8) | Trascrizione | Sì, salvo il nome `CONTEXT.md` |
| 16 mar | [5 Claude Code skills I use every single day](https://www.youtube.com/watch?v=EJyuu6zlQCg) | Trascrizione | Principi sì; nomi delle skills superati |

Fuori dai dieci, per la parte di configurazione ho letto anche [Claude Code tried to improve /init... Is it any better?](https://www.youtube.com/watch?v=llwTBpPqo9A) del 23 marzo (trascrizione), l'articolo [My 7 Phases Of AI Development](https://www.aihero.dev/my-7-phases-of-ai-development) del 3 marzo e due articoli di febbraio: [Never Run Claude /init](https://www.aihero.dev/never-run-claude-init) e [How To Use Claude Code Hooks To Enforce The Right CLI](https://www.aihero.dev/how-to-use-claude-code-hooks-to-enforce-the-right-cli).

### Fonti di confronto, lette il 6 e 7 ottobre

Con i crediti vidIQ esauriti ho letto queste trascrizioni tramite youtubetotranscript.com. Lo strumento con cui le recupero restituisce il testo passando da un riassunto automatico: per i video lunghi ho chiesto le citazioni testuali dei passaggi su cui si basa il report.

| Video | Canale | Come l'ho letto | Cosa ne ho preso |
| --- | --- | --- | --- |
| [The BEST Jev Use Cases for AI Coding](https://www.youtube.com/watch?v=qwnJJMNGwgY) | Cole Medin | Trascrizione integrale | I quattro usi di Jev e lo schema LLM, Jev, LLM |
| [The Ultimate Guide to Making Your Entire Development Cycle AI Native](https://www.youtube.com/watch?v=Tliio-33w4g) | Cole Medin | Sintesi della trascrizione, due ore, più citazioni testuali | L'AI Layer e il flusso da Confluence e Jira fino alla PR |
| [Claude Codes New INTENT.MD, What is It?](https://www.youtube.com/watch?v=LoMOPj-lO8U) | Rob Shocks, 10 settembre | Trascrizione integrale | `intent.md` e la catena di artefatti |
| [Insane Jev Use Cases You Need To Use Right Now](https://www.youtube.com/watch?v=2nc_QMuNp18) | AI LABS, 28 settembre | Sintesi più citazioni testuali | Sette usi di Jev in Claude Code |
| [Insane Tools That Actually Fix Your Claude Code Setup With Jev](https://www.youtube.com/watch?v=jlEMo6Dsh9E) | AI LABS, data non rilevata | Trascrizione, il 7 ottobre | Otto strumenti pronti che usano Jev |
| [I Open-Sourced My Own AFK Software Factory](https://www.youtube.com/watch?v=E5-QK3CDVQM) | Matt Pocock, 30 aprile | Sintesi | Sandcastle: planner, implementer, reviewer e merger |
| [How To De-Slop A Codebase Ruined By AI](https://www.youtube.com/watch?v=3MP8D-mdheA) | Matt Pocock, 29 aprile | Sintesi | `/improve-codebase-architecture` e i moduli profondi |
| [I'm using claude --worktree for everything now](https://www.youtube.com/watch?v=yv8VZpov8bk) | Matt Pocock, 21 febbraio | Sintesi | Un worktree per sessione; se `main` non è protetto, l'agente può finire a fare push lì |
| Changelog [v1.1](https://www.youtube.com/watch?v=A8mokin_YOs) e [v1.2](https://www.youtube.com/watch?v=gaDdrDdczO4), e [9 Things People Get Wrong With My /grill-\* skills](https://www.youtube.com/watch?v=UzMNBN6xLLA) | Matt Pocock | Verifica puntuale di ciò che il report afferma | Confermati: nuovi nomi delle skills, refactor fuori dal ciclo TDD, grilling a round |

## Limiti di questo report

Nulla di ciò che è scritto qui è stato eseguito dentro Claude Code: né le impostazioni, né gli hook, né le skills. Da un punto all'altro cambia la fonte.

### Cosa è verificato, e dove

- **Sulla documentazione ufficiale, il 7 ottobre.** Regole e modalità di permesso, sandbox, status line, Claude in Chrome, sessioni e messaggi tra sessioni, worktree, subagent, compattazione, modelli ed effort, comandi integrati, plugin, memoria, hook, uso da script, GitHub Actions e Code Review. Le pagine sono nelle fonti.
- **Sulla repo di Pocock, clonata il 7 ottobre alla v1.3.1.** Quante skills contiene il plugin e quante sono solo invocabili da te, cosa blocca il guardrail git, i passi di `/implement`, `/implement-spec`, `/code-review`, `/prototype`, `/retro` e `/pr`, la soglia dei 150k token e l'ordine ai confini di fase.
- **Solo riportato dai video.** I loop di AI LABS, i costi dell'autonomia, i consigli su modelli ed effort, gli strumenti di terzi, gli usi di Jev, gli otto strumenti pronti che lo usano e il workshop di Cole Medin.

### Cosa non ho potuto ricontrollare

- **Alcune voci di dettaglio dei settings.** Lo strumento di lettura tronca le pagine più lunghe. Di `autoCompactEnabled`, `worktree.bgIsolation`, `askUserQuestionTimeout`, `showClearContextOnPlanAccept` e `attribution` ho letto solo la riga dell'indice, non i valori ammessi. Per `attribution` la documentazione dice che le chiavi `commit` e `pr` cambiano o nascondono la firma: se con `false` la firma resta, prova la stringa vuota. Su `showClearContextOnPlanAccept` documentazione e changelog indicano default diversi: impostarla a `true` è comunque innocuo.
- **Gli script di esempio.** L'hook di stop sui test e il comando della status line seguono gli esempi ufficiali, con parti mie. Ne ho controllato la sintassi e li ho provati su input finti, fuori da Claude Code.
- **Quale review parte dentro `/implement` con il plugin.** Il nome `code-review` è sia della skill di Pocock sia di quella integrata.
- **Due dati su Jev.** La soglia a 0,7 e i 2-3 secondi a turno per la scelta della skill non compaiono nei due video riletti. Manca invece nel documento un uso che AI LABS mostra: la copertura dei test sulle regole di accesso.
- **Gli otto strumenti con Jev.** Li conosco solo dal video: comandi e repo sono mostrati a schermo, non detti. Nella trascrizione il nome "Jev Belay" e il comando di Jev SEO sono incerti. Il video non parla di Claude in Chrome: il suo strumento per il browser è Jev Browser.
- **Le repo di Graft, unlazy, Skill Spector, Agit e task-observer.** Non le ho lette e non ne ho l'indirizzo. Ho letto quelle di Chisle, Caliper, Reticle, Anti-Slop e delle regole di Karpathy. I numeri sui risparmi sono degli autori, e i video di AI LABS sono sponsorizzati.
- **Numeri su Jev e sulle alternative.** Vengono dal produttore, dagli autori delle repo o dai video: non li ho riprodotti.
- **Tool search degli MCP.** È attivo di default; non ho letto la sezione della documentazione con soglie e opzioni.

### Scelte di questo documento, non delle fonti

- **Il push lo fai tu.** È il guardrail di Pocock; l'esempio ufficiale per i team chiede invece conferma con una regola `ask`.
- **Leggere o scansionare le skills di terzi prima di installarle.** Nel video del 31 luglio la posizione attribuita a Boris Cherny è più permissiva.
- **Riservare i controlli scritti in anticipo ai loop non presidiati.**
- **`/retro` al posto del loop che riscrive da solo le proprie istruzioni.**
- **Niente agent teams.** Il video del 29 giugno li usa.
- **Non attivare `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`.** Il video del 5 ottobre la attiva.
- **Non spegnere in blocco le skills integrate.** Il video del 28 agosto lo consiglia per risparmiare contesto.
- **Tre soglie pratiche.** Sotto quale dimensione il flusso completo è eccessivo, la rete di sicurezza a 200k sulla compattazione, e il set minimo di hook.

### Limiti delle letture

- **Trascrizioni mediate.** Passano da un servizio esterno e da un riassunto automatico, video per video. Per il workshop di due ore di Cole Medin ho usato tre letture con domande diverse: una ha prodotto un finale che nella trascrizione non esiste, e le altre due l'hanno smentito.
- **AI LABS coperto solo da metà maggio.** Non ho esaminato i loro video da febbraio a metà maggio 2026. La scelta dei 20 è basata su titoli e descrizioni.
- **Le skills di AI LABS non le ho viste.** Sono nella loro community a pagamento; qui trovi i principi, non i file.
- **Un video di Pocock rilevante non letto.** La diretta del 3 ottobre con l'autore di pstack.
- **Il canale di Simone Rizzo non era leggibile.** Uso solo la sua repo.
- **Karpathy letto di seconda mano.** Il suo post originale non era raggiungibile: lo conosco dalla repo delle quattro regole.
- **Date mancanti.** Non ho rilevato la data di pubblicazione dei due video di Cole Medin.
- **Il playbook di Anthropic letto in sintesi.** L'ho consultato due volte con domande mirate, non riga per riga.
- **I consigli su modelli ed effort scadono.** Valgono per i modelli citati nei video e vanno rivisti a ogni rilascio.

I crediti vidIQ sono esauriti: 0 su 150 fino al 5 novembre. Dal 6 ottobre le trascrizioni vengono da youtubetotranscript.com, che non richiede crediti.

## Fonti

I link ai singoli video sono nelle tabelle della sezione precedente. Le altre pagine aperte:

- [mattpocock/skills su GitHub](https://github.com/mattpocock/skills): repo clonata alla v1.3.1; letti `plugin.json`, `CHANGELOG.md`, `CLAUDE.md` e i file delle skills; riclonata il 7 ottobre
- [AI Skills for Real Engineers](https://www.aihero.dev/skills): documentazione e changelog
- [Changelog v1.3](https://www.aihero.dev/skills/skills-changelog-v13-implement-spec-pr-retro-and-glossary-md), [v1.2](https://www.aihero.dev/skills/skills-changelog-v12-wait-what-writing-for-agents-claude-code-plugin-and-more), [v1.1](https://www.aihero.dev/skills/skills-changelog-v1-1-wayfinder-to-spec-to-tickets-grilling-improvements)
- [La skill /setup-matt-pocock-skills](https://www.aihero.dev/skills-setup-matt-pocock-skills), [/ask-matt](https://www.aihero.dev/skills-ask-matt), [/wayfinder](https://www.aihero.dev/skills-wayfinder) e [/handoff](https://www.aihero.dev/skills-handoff)
- [mattpocock/sandcastle](https://github.com/mattpocock/sandcastle): README
- Documentazione di Claude Code: [settings](https://code.claude.com/docs/en/settings-reference), [variabili d'ambiente](https://code.claude.com/docs/en/env-vars), [comandi](https://code.claude.com/docs/en/commands), [skills](https://code.claude.com/docs/en/skills), [memoria](https://code.claude.com/docs/en/memory), [goal](https://code.claude.com/docs/en/goal), [hooks](https://code.claude.com/docs/en/hooks-guide)
- [Changelog di Claude Code](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md), fino alla versione 2.1.289
- Repo degli strumenti citati: [Chisle](https://github.com/JayPokale/Chisle), [Caliper](https://github.com/edonadei/caliper), [Reticle](https://github.com/reticlehq/reticle), [Anti-Slop](https://github.com/dmmulroy/anti-slop), [regole di Karpathy](https://github.com/multica-ai/andrej-karpathy-skills)
- Canali [AI LABS](https://www.youtube.com/@AILABS-393/videos) e [Matt Pocock](https://www.youtube.com/@mattpocockuk/videos): elenchi, descrizioni e trascrizioni ottenuti tramite vidIQ

Aggiunte il 6 ottobre:

- [The AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook), Anthropic, 21 agosto 2026
- Documentazione di Claude Code: [MCP](https://code.claude.com/docs/en/mcp)
- Cole Medin: [coleam00/skills](https://github.com/coleam00/skills) con la cartella `hooks/`, [ai-native-starter-pack](https://github.com/coleam00/ai-native-starter-pack), [Archon](https://github.com/coleam00/Archon), [cole-medin-ai-coding](https://github.com/coleam00/cole-medin-ai-coding)
- Karpathy: [autoresearch](https://github.com/karpathy/autoresearch) e [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills), che è la stessa repo indicata sopra con l'indirizzo multica-ai
- Jev: [annuncio di TypeSafe](https://typesafe.ai/blog/introducing-system-one-models-and-jev), [jev-agent-hooks](https://github.com/onlyjq04/jev-agent-hooks), [jev-use](https://github.com/shitianfang/jev-use), [jev-ultrafast](https://github.com/browser-use/jev-ultrafast)
- Alternative open source a Jev: [Rizzo Flow](https://github.com/Rizzo-AI-Academy/rizzo-flow), [Open Alternative to Jev](https://github.com/ikermoel/open-alternative-jev), [SemIf](https://github.com/TheoLeeCJ/SemIf)
- Hook pronti: [karanb192/claude-code-hooks](https://github.com/karanb192/claude-code-hooks) e il [marketplace ufficiale dei plugin](https://github.com/anthropics/claude-plugins-official)
- Skills dello stack: [supabase/agent-skills](https://github.com/supabase/agent-skills), [greensock/gsap-skills](https://github.com/greensock/gsap-skills), [ibelick/ui-skills](https://github.com/ibelick/ui-skills)
- Trascrizioni dei video elencati sopra, tramite [youtubetotranscript.com](https://youtubetotranscript.com)

Aggiunte il 7 ottobre, dalla documentazione di Claude Code:

- Permessi e sandbox: [permessi](https://code.claude.com/docs/en/permissions), [modalità di permesso](https://code.claude.com/docs/en/permission-modes), [sandbox](https://code.claude.com/docs/en/sandboxing), [ambienti isolati](https://code.claude.com/docs/en/sandbox-environments)
- Settings: [file e precedenze](https://code.claude.com/docs/en/settings), [esempi](https://code.claude.com/docs/en/settings-example), [status line](https://code.claude.com/docs/en/statusline), [modelli ed effort](https://code.claude.com/docs/en/model-config), [terminale e notifiche](https://code.claude.com/docs/en/terminal-config)
- Sessioni e lavoro in parallelo: [sessioni](https://code.claude.com/docs/en/sessions), [messaggi tra sessioni](https://code.claude.com/docs/en/cross-session-messaging), [agent view](https://code.claude.com/docs/en/agent-view), [worktree](https://code.claude.com/docs/en/worktrees), [subagent](https://code.claude.com/docs/en/sub-agents), [confronto tra i modi](https://code.claude.com/docs/en/agents)
- Progetto: [Claude in Chrome](https://code.claude.com/docs/en/chrome), [codebase grandi](https://code.claude.com/docs/en/large-codebases), [cartella .claude](https://code.claude.com/docs/en/claude-directory), [strumenti](https://code.claude.com/docs/en/tools-reference), [installare plugin](https://code.claude.com/docs/en/plugins/install), [comandi dei plugin](https://code.claude.com/docs/en/plugins/cli-reference)
- CI e review: [uso da script](https://code.claude.com/docs/en/headless), [GitHub Actions](https://code.claude.com/docs/en/github-actions), [Code Review](https://code.claude.com/docs/en/code-review)

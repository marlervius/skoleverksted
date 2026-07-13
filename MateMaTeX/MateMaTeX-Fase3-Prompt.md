# MateMaTeX 2.0 — Fase 3: UX, Design og Frontend-polish

Du skal nå transformere MateMaTeX 2.0 fra funksjonell prototype til et visuelt slående, premium SaaS-produkt. All funksjonalitet fra Fase 1 (AI-motor) og Fase 2 (oppgavebank, editor, differensiering, eksport, samarbeid) er implementert. Nå skal det SE UT og FØLES som et produkt lærere ELSKER å bruke.

**Les gjennom hele den eksisterende frontend-koden før du begynner.** Du skal forbedre det som finnes — ikke reimplementere funksjonalitet.

---

## KONTEKST: EKSISTERENDE FRONTEND

```
frontend/src/
├── app/
│   ├── layout.tsx              # App shell med nav
│   ├── page.tsx                # Genereringswizard + pipeline-progress + resultat
│   ├── exercises/page.tsx      # Oppgavebank
│   ├── shared/[token]/page.tsx # Delt ressurs
│   └── globals.css             # Tailwind + noe custom
├── components/
│   ├── generation-wizard.tsx
│   ├── pipeline-progress.tsx
│   ├── result-view.tsx
│   ├── latex-editor.tsx
│   └── export-modal.tsx
└── lib/
    ├── store.ts                # Zustand
    └── api.ts                  # API-klient med SSE
```

**Stack:** Next.js 14 App Router, Tailwind CSS, shadcn/ui, Zustand, Framer Motion

---

## DESIGNVISJON

MateMaTeX skal ha en **"Scholarly Craft"**-estetikk: En blanding av akademisk presisjon og moderne verktøykvalitet. Tenk Notion møter en vakker matematikkbok — rent, rolig, men med distinkte detaljer som signaliserer at dette er laget for folk som bryr seg om kvalitet.

### Designprinsipper

1. **Ro, ikke kaos.** Lærere bruker dette etter en lang arbeidsdag. Interfacet skal føles som å åpne en velorganisert notatbok — ikke en overstimulerende dashboard.
2. **Matematikkens estetikk.** Bruk subtile referanser til matematisk notasjon og typografi: tynne linjer, presise grid, serif-accenter, geometriske detaljer.
3. **Progressiv kompleksitet.** Enkle oppgaver er enkle. Avanserte funksjoner avdekkes gradvis.
4. **Haptisk feedback.** Hver interaksjon skal føles responsiv: hover-states, klikk-animasjoner, transitions mellom steg.

---

## 3.1 — DESIGNSYSTEM

### Fargepalett

Definer et komplett fargesystem i `globals.css` som CSS-variabler:

```
Mørkt tema (default):
- Bakgrunn:        hsl(220, 20%, 8%)     — Dyp blåsvart, ikke helt svart
- Surface:         hsl(220, 18%, 12%)    — Kortbakgrunn, panels
- Surface elevated: hsl(220, 16%, 16%)   — Hover, modaler
- Border:          hsl(220, 14%, 20%)    — Subtile skillelinjer
- Text primary:    hsl(210, 20%, 92%)    — Nesten hvit, ikke pure white
- Text secondary:  hsl(210, 12%, 58%)    — Dempet for metadata
- Text muted:      hsl(210, 8%, 40%)     — Placeholders, disabled

Aksentfarger (basert på tcolorbox-fargene fra LaTeX-preamble):
- Blå (primær):    hsl(210, 70%, 55%)    — Hovedhandlinger, lenker
- Grønn:           hsl(150, 55%, 45%)    — Suksess, eksempler
- Lilla:           hsl(270, 50%, 55%)    — Oppgaver, badges
- Oransje:         hsl(30, 80%, 55%)     — Advarsler, hint, tips
- Turkis:          hsl(180, 50%, 45%)    — Løsninger
- Rød:             hsl(0, 65%, 55%)      — Feil, destruktive handlinger

Lyst tema:
- Bakgrunn:        hsl(40, 20%, 97%)     — Varm off-white, som godt papir
- Surface:         hsl(0, 0%, 100%)      — Ren hvit for kort
- Border:          hsl(220, 14%, 88%)
- Text primary:    hsl(220, 20%, 12%)
- (Aksentfarger justeres litt mørkere for kontrast)
```

### Typografi

Bruk Google Fonts. Velg noe med akademisk karakter men moderne lesbarhet:

- **Display/overskrifter:** `"Instrument Serif"` eller `"Playfair Display"` — Serif med karakter. Brukes for sidetitler, seksjonsoverskrifter, og tomme-state-meldinger.
- **Body/UI:** `"DM Sans"` eller `"Plus Jakarta Sans"` — Geometrisk sans-serif med god lesbarhet. Brukes for alt annet.
- **Kode/LaTeX:** `"JetBrains Mono"` — For LaTeX-editoren og kodeblokker.
- **Matematikk-accenter:** `"Latin Modern"` via KaTeX/MathJax for rendret matematikk i preview.

Typografisk skala (rem-basert):
```
text-xs:   0.75rem / 1rem line-height
text-sm:   0.875rem / 1.25rem
text-base: 1rem / 1.5rem
text-lg:   1.125rem / 1.75rem
text-xl:   1.25rem / 1.75rem
text-2xl:  1.5rem / 2rem
text-3xl:  1.875rem / 2.25rem
text-4xl:  2.25rem / 2.5rem    — Kun sidetitler
```

### Spacing og layout

- **Vertikal rytme:** Basert på 8px-grid. All spacing skal være multipler av 8 (8, 16, 24, 32, 48, 64, 96).
- **Maks innholdsbredde:** 1280px for hovedinnhold, 960px for lesefokuserte sider.
- **Sidebar:** 280px fast bredde, kollapserbar til 64px (kun ikoner).
- **Kortradius:** 12px konsekvent for alle kort og modaler.
- **Skygger (mørkt tema):** Bruk `ring` og subtile `border`-effekter i stedet for box-shadow (som er nesten usynlige på mørk bakgrunn).
- **Skygger (lyst tema):** Myke, laginndelte skygger: `0 1px 3px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.04)`.

---

## 3.2 — NAVIGASJON OG APP-SHELL

### Sidebar-navigasjon

Erstatt eventuell toppnavigasjon med en vertikal sidebar:

```
┌──────────────────────────────────────────────────────────┐
│ [M] MateMaTeX                  │                         │
│                                │                         │
│ ◇ Generer                      │    (Hovedinnhold)       │
│ ◇ Oppgavebank                  │                         │
│ ◇ Maler                        │                         │
│ ◇ Historikk                    │                         │
│                                │                         │
│ ─────────────                  │                         │
│ ◇ Skolens bank                 │                         │
│ ◇ Delt med meg                 │                         │
│                                │                         │
│ ─────────────                  │                         │
│                                │                         │
│                                │                         │
│ ◇ Innstillinger                │                         │
│ ◇ [Brukerprofil]               │                         │
└──────────────────────────────────────────────────────────┘
```

- Animert kollaps: `280px → 64px` med smooth transition. Ikoner alltid synlige, labels glir inn/ut.
- Aktiv side: Tydelig highlight med aksentfarge + subtil bakgrunn
- Hover-effekt: Bakgrunnsfargen fader inn (150ms ease)
- Mobilvisning (< 768px): Sidebar blir en bottom tab bar med 4-5 hovedikoner
- Logo: Stilisert "M" med matematisk notasjon-inspirert design (kan være en `<svg>`)
- Keyboard shortcut: `Cmd/Ctrl + B` toggler sidebar

### Breadcrumbs og kontekst

Vis sti øverst i hovedinnholdet: `Generer → Algebra → 8. trinn` — hjelper orientering.

---

## 3.3 — GENERERINGSFLYTEN (HOVEDOPPLEVELSEN)

Dette er kjernen av produktet. Den skal føles magisk.

### Steg 1: Wizard (input)

Redesign `generation-wizard.tsx` som en trinnvis flyt — IKKE et langt skjema:

**Steg 1a: Trinn** — Store, klikkbare kort i grid (2×5 layout):
```
┌─────────────┐  ┌─────────────┐
│   1.–4.     │  │   5.–7.     │
│  trinn      │  │  trinn      │
└─────────────┘  └─────────────┘
┌─────────────┐  ┌─────────────┐
│   8. trinn  │  │   9. trinn  │
└─────────────┘  └─────────────┘
       ...etc
```
- Hvert kort har en subtil illustrasjon eller ikon som representerer nivået
- Valgt kort: Hevet med aksentborder og check-ikon
- Animasjon: Kort stagger inn med 50ms delay mellom hvert

**Steg 1b: Emne** — Filtrert basert på valgt trinn. Vis som chips/tags gruppert etter kategori (Tall, Algebra, Geometri, etc.)

**Steg 1c: Type og innstillinger** — Oppgaveark, Fullt kapittel, Eksamen, Differensiert. Vis som horisontale kort med ikon + kort beskrivelse. Under: Valgfrie innstillinger som ekspanderer (språknivå, antall oppgaver, spesielle instruksjoner)

**Navigasjon:** Horisontale steg-indikatorer øverst (1 · 2 · 3) med progressbar mellom. "Tilbake" og "Neste" knapper med keyboard-navigasjon (piltaster).

**Overgang mellom steg:** Innhold glir horisontalt (Framer Motion `AnimatePresence` med `slideLeft`/`slideRight` variants). Myk, rask — 250ms.

### Steg 2: Pipeline-visualisering (generering pågår)

Redesign `pipeline-progress.tsx` til en visuell opplevelse:

**Layout:** Vertikal timeline med noder for hvert agent-steg:

```
    ● Pedagogen planlegger...          ✓ 2.3s
    │
    ● Forfatteren skriver...           ⟳ pågår
    │  "Genererer oppgave 4 av 10..."
    │
    ○ Matematikk-verifisering          — venter
    │
    ○ LaTeX-kompilering                — venter
    │
    ○ Redaktøren sjekker               — venter
```

- **Aktiv node:** Pulserende ring-animasjon (CSS `@keyframes pulse`), aksentfarge
- **Fullført node:** Grønn sjekk med fade-in, viser tidsbruk
- **Feilet → retry:** Rød node som blinker → gul "Retter..." → grønn ved suksess. Vis retry-nummer ("Forsøk 2/3")
- **Sanntids-detaljer:** Under aktiv node, vis streaming tekst fra agenten (fade in/out, maks 2 linjer synlig)
- **Estimert tid:** Vis progresjon som "~15 sekunder igjen" basert på historiske gjennomsnitt
- **Bakgrunn:** Subtilt animert gradient-mesh som skifter farge basert på aktiv agent (blå for pedagog, grønn for forfatter, lilla for verifikator)

### Steg 3: Resultat

Redesign `result-view.tsx`:

**Header:** Tittel + metadata (trinn, emne, type, genereringstid, tokenkostnad) i en kompakt bar.

**Hovedvisning:** Tabs: "Dokument" | "Rediger" | "Differensiering"
- **Dokument:** Full PDF-preview (react-pdf med sidenavigasjon, zoom, dark mode-invertert bakgrunn)
- **Rediger:** LaTeX-editoren (split-view)
- **Differensiering:** Tre kolonner side om side (responsivt → tabs på mobil)

**Handlingsbar (sticky bottom):**
```
[⬇ Last ned ▾]  [✏️ Rediger]  [🔀 Differensiér]  [🔗 Del]  [⭐ Favoritt]
```
- "Last ned"-dropdown: PDF, Word, PowerPoint, Print-optimalisert
- Alle knapper med ikoner + tekst, hover-animasjoner

**Overgang fra pipeline → resultat:** PDF-en "avdekkes" med en subtil blinds/reveal-animasjon fra toppen.

---

## 3.4 — OPPGAVEBANK-DESIGN

Redesign `exercises/page.tsx`:

### Søk og filtrering

**Søkefelt:** Stort, sentrert øverst med ikon. Rundet, med subtil inner shadow. Placeholder: "Søk i oppgaver... (f.eks. 'andregradsligning med diskriminant')"

**Filterbar:** Under søkefeltet, horisontalt scrollbar med chip-grupper:
- Trinn: `8.` `9.` `10.` `VG1 1T` `VG2 R1` ... (scrollbar ved overflow)
- Emne: `Algebra` `Geometri` `Funksjoner` ... (multi-select chips)
- Type: `Regneoppgave` `Flervalg` `Tekstoppgave` ...
- Vanskelighetsgrad: Kompakt slider (1–5) med tallvisning
- Aktive filtre: Vis som dismissable chips under filterbaren

### Visning

**Grid-modus (default):** Kort i 3-kolonne grid (2 på tablet, 1 på mobil):
```
┌─────────────────────────────────┐
│  [Algebra]  ●●●○○              │
│                                 │
│  Løs ligningen 2x + 5 = 13    │
│                                 │
│  8. trinn · Regneoppgave       │
│  ─────────────────────          │
│  [Lignende] [Variant] [⭐]     │
└─────────────────────────────────┘
```

- Hvert kort: Surface-bakgrunn, subtil border, 12px radius
- Hover: Hev kortet (translateY -2px), vis skygge, border lysner
- Vanskelighetsgrad: Fargede prikker (grønn → gul → oransje → rød → dyp rød)
- Emne-badge: Fargekodet chip (samme farger som tcolorbox-miljøene)
- Klikk: Ekspander kortet inline med full oppgavetekst, løsning (bak spoiler), hint
- Matematikk i kortene: Render med KaTeX for pen visning (ikke rå LaTeX-kode)

**Liste-modus:** Kompakt tabell med sorterbare kolonner. Mer info synlig per rad.

### "Bygg eksamen"-modus

Når aktivert (toggle-knapp øverst):
- Venstre: Oppgavebanken (filtrerbar som vanlig)
- Høyre: Droppable "Eksamens-builder" panel (sticky, 40% bredde)
- Dra oppgaver fra venstre til høyre med `@dnd-kit`
- I builder: Omorganiser rekkefølge, sett poengverdi per oppgave, legg til seksjonsoverskrifter
- "Generer eksamen"-knapp: Kompiler til PDF med forside, poengskjema, oppgavenummerering

---

## 3.5 — MIKROINTERAKSJONER OG ANIMASJONER

Implementer disse med Framer Motion (`motion` components) og CSS:

| Interaksjon | Animasjon |
|-------------|-----------|
| Sidelast | Staggered fade-in av innholdselementer (50ms delay) |
| Navigasjon | Innhold crossfader mellom sider (150ms) |
| Knapp-klikk | Scale 0.97 → 1.0 (100ms) |
| Knapp-hover | Bakgrunnsfarge fader inn (150ms ease) |
| Kort-hover | translateY(-2px) + border-color transition (200ms) |
| Modal åpne/lukke | Fade bakgrunn + slide-up innhold (200ms spring) |
| Toast-notifikasjoner | Slide inn fra høyre, auto-dismiss etter 4s |
| Toggle/switch | Spring-animert knapp med fargeskifte |
| Tab-bytte | Underline-indikator glir til aktiv tab (layout animation) |
| Sidebar kollaps | Width-animasjon med labels som fader ut/inn |
| Skeleton loading | Subtil shimmer-gradient animasjon |
| Favoritt-stjerne | Pop + rotate ved klikk (anticipation → overshoot → settle) |
| Wizard steg | Horizontal slide med opacity crossfade |

**Viktig:** Alle animasjoner skal respektere `prefers-reduced-motion`. Wrap i en conditional:
```tsx
const shouldAnimate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
```

---

## 3.6 — TOMME STATES OG ONBOARDING

Hver side trenger en gjennomtenkt tom-state for nye brukere:

**Oppgavebanken (tom):**
```
     📐

  Ingen oppgaver ennå

  Oppgaver du genererer lagres automatisk her.
  Generer ditt første arbeidsark for å komme i gang.

  [Generer nå →]
```

**Historikk (tom):**
```
     📝

  Ingen genereringer ennå

  Alt du lager dukker opp her, sortert etter dato.

  [Start din første generering →]
```

- Bruk display-fonten (serif) for overskriften
- Illustrasjon: Enkel SVG-ikon eller emoji, muted farge, 48px
- CTA-knapp med primæraksentfarge

### Første gangs bruk (onboarding)

Ved første innlogging, vis en kort wizard (3 steg, kan skippes):
1. "Hvilke trinn underviser du?" — Multi-select av trinn
2. "Hvilke emner fokuserer du på nå?" — Multi-select av emner
3. "Ferdig! Her er dashboardet ditt." — Kort animert intro

Lagre i brukerinnstillinger. Bruk til å forhåndsfiltrere wizard og oppgavebank.

---

## 3.7 — RESPONSIVT DESIGN

| Breakpoint | Layout |
|-----------|--------|
| ≥1280px (desktop) | Full sidebar + innhold |
| 1024–1279px (liten desktop) | Smalere sidebar (kollapset) + innhold |
| 768–1023px (tablet) | Sidebar som overlay + innhold, 2-kolonne grid |
| <768px (mobil) | Bottom tab bar, 1-kolonne, forenklet wizard |

**Spesifikke tilpasninger:**
- LaTeX-editor: På mobil → tabs i stedet for split-view (rediger/preview)
- Oppgavebank: 3 → 2 → 1 kolonner
- Pipeline-visualisering: Forenklet til en kompakt progress-bar på mobil
- Eksamen-builder: Fullskjerm-modus på mobil, ikke side-om-side

---

## 3.8 — MØRKT/LYST TEMA

- Tema-toggle i sidebar footer (sol/måne-ikon med rotasjonsanimasjon ved bytte)
- Bruk `class="dark"` på `<html>` og Tailwind `dark:` prefix
- Lagre preferanse i localStorage OG synk med brukerinnstillinger i DB
- Respekter `prefers-color-scheme` som default ved første besøk
- **Overgang:** Ved temabytte, legg på en 200ms `transition: background-color, color, border-color` på `*` for å unngå flash

---

## 3.9 — TASTATURNAVIGASJON OG TILGJENGELIGHET

| Shortcut | Handling |
|----------|---------|
| `Cmd/Ctrl + K` | Åpne global kommandopalett (à la Spotlight/VS Code) |
| `Cmd/Ctrl + B` | Toggle sidebar |
| `Cmd/Ctrl + N` | Ny generering |
| `Cmd/Ctrl + E` | Fokus søkefeltet i oppgavebanken |
| `Cmd/Ctrl + S` | Lagre (i editor-modus) |
| `Escape` | Lukk modal/overlay |
| `Tab` | Standard fokusnavigasjon med synlig fokusring |

**Kommandopalett (`components/command-palette.tsx`):**
- Åpnes med `Cmd+K`, overlay med søkefelt
- Søk i: Sider, handlinger ("Ny generering", "Oppgavebank"), nylige genereringer
- Navigér med piltaster, Enter for valg, Escape for lukk
- Implementer med `cmdk`-biblioteket (npm: `cmdk`)

**Tilgjengelighet:**
- Alle interaktive elementer har `aria-label`
- Fargekontrast ≥ 4.5:1 (WCAG AA)
- Fokus-synlighet: `ring-2 ring-offset-2 ring-blue-500` på focus-visible
- Skjermleser-vennlige live-regioner for pipeline-status (`aria-live="polite"`)

---

## 3.10 — YTELSESOPTIMALISERING

- **Fonter:** Bruk `next/font` for self-hosted Google Fonts med `display: swap`
- **Bilder/ikoner:** Bruk `lucide-react` for ikoner (tree-shakeable). Lazy-load tunge komponenter (Monaco Editor, react-pdf) med `next/dynamic`
- **Code splitting:** Sidene for exercises, editor, og shared-view er allerede lazy via App Router. Sørg for at Monaco-bundlen ikke lastes på hovedsiden.
- **Skeleton screens:** Implementer for: oppgavebank (3×3 grid av skjelett-kort), resultatvisning (PDF-placeholder), historikk
- **Lighthouse-mål:** Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 90

---

## NYE AVHENGIGHETER

```json
{
  "cmdk": "^1.0.0",
  "next-themes": "^0.3.0",
  "@next/font": "brukes allerede via next/font",
  "katex": "^0.16.0",
  "react-katex": "^3.0.0"
}
```

---

## ARBEIDSREKKEFØLGE

1. **Designsystem** (3.1) — Farger, typografi, spacing, CSS-variabler i `globals.css`. Alt annet bygger på dette.
2. **App-shell og navigasjon** (3.2) — Sidebar, layout, breadcrumbs. Rammeverket for alt innhold.
3. **Genereringsflyten** (3.3) — Wizard, pipeline-visualisering, resultatvisning. Kjerneopplevelsen.
4. **Oppgavebank-design** (3.4) — Kort, søk, filtrering, eksamen-builder.
5. **Mikrointeraksjoner** (3.5) — Framer Motion-animasjoner, hover-states, transitions.
6. **Resten** (3.6–3.10) — Tomme states, responsivt, tema, tastatur, ytelse.

---

*Begynn med 3.1 og 3.2: Implementer designsystemet i `globals.css` og Tailwind-config, deretter bygg den nye sidebar-navigasjonen med animert kollaps. Vis meg det komplette designsystemet og sidebar-komponenten.*

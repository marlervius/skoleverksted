// Scriptorium for VGS — læringsark-komponentbibliotek
// Implementerer DEL 2 av SPEC_laeringsark_redesign.
// Alle farger og mål er forpliktende — de matcher godkjent mockup.

// ── 2.1 Design-tokens ────────────────────────────────────────────────────────
// (Scriptorium = blå; oppgaver = lilla; kilde-badge = grønn)
#let blue-50   = rgb("#E6F1FB")
#let blue-600  = rgb("#185FA5")
#let blue-800  = rgb("#0C447C")
#let purple-50  = rgb("#EEEDFE")
#let purple-200 = rgb("#AFA9EC")
#let purple-600 = rgb("#534AB7")
#let purple-800 = rgb("#3C3489")
#let green-50  = rgb("#EAF3DE")
#let green-800 = rgb("#27500A")
#let red-50    = rgb("#FCEBEB")
#let red-800   = rgb("#791F1F")
#let amber-50  = rgb("#FAEEDA")
#let amber-800 = rgb("#633806")
#let gray-100  = rgb("#F1EFE8")
#let gray-300  = rgb("#B4B2A9")
#let gray-400  = rgb("#888780")
#let gray-600  = rgb("#5F5E5A")
#let ink       = rgb("#2C2C2A")

// Font med full latinsk dekning (vendored i backend/fonts, se compile_typst).
#let hovedfont = ("Source Sans 3", "Noto Sans", "Liberation Sans", "DejaVu Sans", "Arial")

// ── 2.2 Sideoppsett, topp- og bunntekst ──────────────────────────────────────
// Brukes som show-regel: #show: doc => laeringsark-oppsett(doc, fag: ..., tema: ...)
#let laeringsark-oppsett(doc, fag: "", tema: "") = {
  set text(font: hovedfont, size: 10.5pt, lang: "nb", fill: ink)
  set par(leading: 0.62em, justify: false)

  set page(
    paper: "a4",
    margin: (top: 20mm, bottom: 18mm, left: 18mm, right: 16mm),
    header: context if counter(page).get().first() > 1 {
      block(width: 100%)[
        #set text(size: 8pt)
        #grid(columns: (1fr, auto),
          text(fill: blue-600, weight: 500)[Scriptorium · #fag],
          text(fill: gray-400)[#tema])
        #v(2pt)
        #line(length: 100%, stroke: 0.4pt + gray-300)
      ]
    },
    footer: context block(width: 100%)[
      #line(length: 100%, stroke: 0.4pt + gray-300)
      #v(3pt)
      #set text(size: 8pt, fill: gray-400)
      #grid(columns: (1fr, auto),
        [Scriptorium for VGS · klasserom.ai],
        [Side #counter(page).display() av #counter(page).final().first()])
    ],
  )

  doc
}

// ── 2.3 Forside-topp: tittel, chips og kilde-badge ───────────────────────────
#let chip(txt, fill: blue-50, ink: blue-800) = box(
  fill: fill, radius: 8pt, inset: (x: 8pt, y: 3pt),
  text(size: 8.5pt, fill: ink, weight: 500)[#txt])

#let tittelblokk(tittel, niva, modus, fag: "", kilde: none) = {
  grid(columns: (1fr, auto),
    text(size: 9pt, fill: blue-600, weight: 500, tracking: 0.3pt)[Scriptorium · #fag],
    chip[#niva · #modus])
  v(4pt)
  text(size: 19pt, weight: 500)[#tittel]
  v(6pt)
  if kilde != none {
    box(fill: green-50, radius: 4pt, inset: (x: 8pt, y: 4pt))[
      #text(size: 8.5pt, fill: green-800)[✓ Kildeforankret: #kilde]]
  } else {
    box(fill: amber-50, radius: 4pt, inset: (x: 8pt, y: 4pt))[
      #text(size: 8.5pt, fill: amber-800)[Ikke kildeforankret — fakta hviler på modellens kunnskap]]
  }
  v(10pt)
}

// ── 2.4 Seksjonsoverskrift med fargestripe ───────────────────────────────────
#let seksjonsteller = counter("seksjon")
#let seksjonstittel(t) = {
  seksjonsteller.step()
  block(above: 1.5em, below: 0.7em, grid(
    columns: (3pt, auto), column-gutter: 8pt, align: horizon,
    // radius: 0 — ingen avrundede hjørner på ensidige aksenter
    rect(width: 3pt, height: 12pt, fill: blue-600, radius: 0pt),
    text(size: 12.5pt, weight: 500, fill: blue-800)[
      #context seksjonsteller.display() · #t]))
}

// ── 2.5 Margbegreper ─────────────────────────────────────────────────────────
#let begrepskolonne(begreper) = block(
  stroke: (left: 0.5pt + gray-300), inset: (left: 4mm))[
  #text(size: 7.5pt, fill: gray-400, tracking: 0.6pt, weight: 500)[BEGREPER]
  #v(2.5mm)
  #for b in begreper [
    #text(size: 8.5pt, weight: 500, fill: blue-600)[#b.term] \
    #text(size: 8.5pt, fill: gray-600)[#b.def]
    #v(2.5mm)
  ]
]

#let fagseksjon(tittel, begreper: (), body) = {
  seksjonstittel(tittel)
  if begreper.len() > 0 {
    grid(columns: (1fr, 44mm), column-gutter: 6mm,
         body, begrepskolonne(begreper))
  } else { body }
}

// Fallback når en seksjon har > 4 begreper (heuristikk i Python):
// begrepsboks i full bredde rett under seksjonstittelen.
#let begrepsboks(begreper) = block(
  fill: gray-100, radius: 4pt, inset: 9pt, width: 100%, below: 0.9em)[
  #text(size: 7.5pt, fill: gray-400, tracking: 0.6pt, weight: 500)[BEGREPER]
  #v(2mm)
  #for b in begreper [
    #text(size: 8.5pt, weight: 500, fill: blue-600)[#b.term]
    #text(size: 8.5pt, fill: gray-600)[— #b.def]
    #v(1.5mm)
  ]
]

// ── 2.6 K-markør (kildehenvisning) ──────────────────────────────────────────
#let K = h(0.5pt) + super(text(size: 6.5pt, fill: gray-300)[K])

#let k-legende(kilde: none) = block(above: 1em)[
  #text(size: 7.5pt, fill: gray-400)[
    K = påstanden bygger på kildematerialet#if kilde != none [ (#kilde)] og kan kontrolleres mot det.]
]

// ── 2.7 Oppgaveboks, svarlinjer og kausalkjede ───────────────────────────────
#let svarlinjer(n, compact: false) = for _ in range(n) {
  v(if compact { 10pt } else { 13pt })
  line(length: 100%, stroke: 0.5pt + purple-200)
}

// breakable: false er obligatorisk — instruks og svarlinjer skal aldri
// splittes over sidebryting. Nivået står i klartekst (ingen stjerne-legende).
#let oppgaveboks(nr, niva, tekst, linjer: 0, compact: false) = block(
  breakable: false, fill: purple-50, radius: 6pt,
  inset: if compact { 9pt } else { 11pt }, width: 100%,
  above: if compact { 0.6em } else { 1em },
  below: if compact { 0.6em } else { 1em })[
  #grid(columns: (1fr, auto),
    text(size: 10pt, weight: 500, fill: purple-800)[Oppgave #nr],
    text(size: 9pt, fill: purple-600)[
      #("★" * niva)#("☆" * (3 - niva)) #h(3pt)
      #if niva == 1 [Grunnleggende] else if niva == 2 [Middels] else [Avansert]])
  #v(if compact { 2.5pt } else { 4pt })
  #text(size: 9.5pt, fill: purple-600)[#tekst]
  #if linjer > 0 { svarlinjer(linjer, compact: compact) }
]

#let kjede(steg) = block(fill: gray-100, radius: 4pt, inset: 9pt,
  width: 100%, breakable: false)[
  #set text(size: 9pt, fill: gray-600)
  #steg.map(s => box(s)).join(text(fill: blue-600)[ → ])
]

// ── 2.8 Faktarapport — statusetiketter ───────────────────────────────────────
#let etikett(txt, fill, ink) = box(fill: fill, radius: 2pt,
  inset: (x: 4pt, y: 1.5pt),
  text(size: 7pt, weight: 500, fill: ink, tracking: 0.4pt)[#txt])

#let st-dekket  = etikett("DEKKET AV KILDEN", green-50, green-800)
#let st-strid   = etikett("I STRID MED KILDEN", red-50, red-800)
#let st-utenfor = etikett("UTENFOR KILDEN", blue-50, blue-800)
#let st-usikker = etikett("BØR PRESISERES", amber-50, amber-800)

// Konklusjonslinje øverst på faktarapportens forside (11pt weight 500).
#let konklusjonslinje(txt) = block(below: 1.2em)[
  #text(size: 11pt, weight: 500)[#txt]
]

// Topptekst-blokk for lærerveiledningen (egen PDF, kun for læreren).
#let faktarapport-topp(tema, fag: "") = {
  grid(columns: (1fr, auto),
    text(size: 9pt, fill: blue-600, weight: 500, tracking: 0.3pt)[Scriptorium · #fag],
    chip("Kun for læreren", fill: amber-50, ink: amber-800))
  v(4pt)
  text(size: 19pt, weight: 500)[Lærerveiledning: #tema]
  v(6pt)
  box(fill: amber-50, radius: 4pt, inset: (x: 8pt, y: 4pt))[
    #text(size: 8.5pt, fill: amber-800)[Faktasjekk og vurderingsstøtte — skal ikke deles ut til elever]]
  v(10pt)
}

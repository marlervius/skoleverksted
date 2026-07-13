"""
Material-type specific instructions for pedagogue and author agents.
"""

from __future__ import annotations


def pedagogue_material_instructions(material_type: str) -> str:
    """Extra planning rules per material type."""
    if material_type == "prøve":
        return """
TYPE: PRØVE/EKSAMEN
- Lag struktur: forside/tittel, instruksjoner (tid, hjelpemidler), oppgaver med poeng
- Del prøven i \\section*{Del 1 — uten hjelpemidler} og
  \\section*{Del 2 — med hjelpemidler}. Oppgi anbefalt tid for hver del.
- Del 1 skal teste grunnleggende regning, resonnement og ferdigheter som kan
  utføres uten digitale verktøy. Del 2 skal inneholde modellering, problemløsing
  og oppgaver der grafverktøy/CAS kan være relevant.
- Oppgaver nummerert; deloppgaver a), b), c)
- Ingen løsningsforslag i elevversjonen (løsninger i egen \\section*{Løsningsforslag} kun hvis løsninger er påkrevd)
- Inkluder poengskjema-tabell (booktabs) til slutt
- Varier vanskelighet: ca. 40% lett, 40% middels, 20% vanskelig
"""
    if material_type == "differensiert":
        return """
TYPE: DIFFERENSIERT ARBEIDSARK
- Planlegg én felles introduksjon, deretter tre nivåer: Grunnleggende, Standard, Avansert
- Standard-nivå er hovedinnholdet (ca. 70% av oppgavene)
- Grunnleggende: færre oppgaver, enklere tall, flere hint
- Avansert: utfordringsoppgaver og sammensatte problemer
"""
    if material_type == "kapittel":
        return """
TYPE: KAPITTEL (lærebok-kapittel — teoritungt!)
Et kapittel skal ligne en ordentlig lærebok-del, IKKE et arbeidsark. Teorien er
hovedsaken; oppgavene kommer til slutt. Planlegg GRUNDIG og OMFATTENDE.

KRAV TIL STRUKTUR:
- Innledning/motivasjon: hvorfor er temaet nyttig, hva skal eleven lære, kobling
  til det eleven kan fra før.
- 4–7 teoriseksjoner som bygger logisk fra grunnleggende til avansert. Del gjerne
  hver hovedteknikk/begrep i egen seksjon.
- For HVER seksjon, spesifiser:
  * Læringsmål og nøkkelbegreper
  * Definisjon(er) og/eller regel/setning som skal presenteres
  * Intuisjon/forklaring og (der det passer) en kort begrunnelse/utledning av regelen
  * MINST 2 gjennomregnede eksempler per teknikk/regel, med stigende vanskelighet
  * Vanlige feil / typiske misforståelser eleven bør unngå
  * Illustrasjonsbehov (TikZ/PGFPlots) markert NØDVENDIG/valgfri
- En tabell over standard­resultater/formler der det er relevant (f.eks. tabell over
  kjente integraler/deriverte).
- Oppsummering til slutt: de viktigste formlene og metodene samlet.
- Oppgaveseksjon HELT til slutt (teori FØR oppgaver), med stigende vanskelighet.

OMFANG: Et VG1/R1/R2-kapittel skal være rikt og detaljert. Hver hovedteknikk
fortjener egen seksjon med forklarende tekst, ikke bare en boks. Planlegg nok
innhold til flere sider teori.

STRENGE REGLER:
- Dekk ALLE deltemaer fra pensum-sjekklisten (hver med egen seksjon)
- ALDRI bland inn andre hovedkapitler (f.eks. vektorer i funksjonskapittel)
- Planlegg minst 2 eksempler og 1 graf per hovedseksjon
- Inkluder minst én utforsk-aktivitet og analyse/drøfting
"""
    return ""


def author_material_instructions(material_type: str, include_solutions: bool) -> str:
    """Extra authoring rules per material type."""
    if material_type == "prøve":
        sol = (
            "Inkluder \\section*{Løsningsforslag} på slutten med komplette løsninger."
            if include_solutions
            else "IKKE inkluder løsningsforslag — kun elevprøve."
        )
        return f"""
PRØVE-MODUS:
- Start med \\title, tid (f.eks. 90 min), og korte instruksjoner
- Bruk alltid \\section*{{Del 1 — uten hjelpemidler}} og
  \\section*{{Del 2 — med hjelpemidler}}, med tydelig tids- og hjelpemiddelinformasjon.
- Fordel oppgavene og poengene mellom delene, og oppgi delsummer.
- Oppgaver i \\begin{{taskbox}}{{Oppgave N}} med poeng i tittelen, f.eks. {{Oppgave 1 (4 poeng)}}
- Avslutt med poengskjema-tabell (booktabs): Oppgave | Poeng | Oppnådd
- {sol}
"""
    if material_type == "differensiert":
        return """
DIFFERENSIERT MODUS:
- Etter tittel: \\section*{{Grunnleggende}}, deretter \\section*{{Standard}}, deretter \\section*{{Avansert}}
- Standard-seksjonen inneholder hovedoppgavene (taskbox)
- Grunnleggende: enklere tall og Tips-bokser; Avansert: utfordringer
"""
    if material_type == "kapittel":
        return """
KAPITTEL-MODUS (lærebok-kapittel — skriv UTFYLLENDE teori!):
Dette er det viktigste: et kapittel skal være TEORITUNGT og grundig, som en ekte
lærebok-del. IKKE bare lister med definisjoner og bokser — skriv FORKLARENDE TEKST.

LÆREBOK-STRUKTUR (som norske lærebøker):
1. Rett etter \\maketitle: \\begin{{laeringsmaal}} med 3–5 konkrete mål
   ("...lærer du å ...").
2. Innledning (løpende tekst) som motiverer temaet, gjerne med et hverdagsnært
   eksempel, og en \\begin{{husk}}-boks som aktiverer forkunnskaper.
3. Bruk \\section{{...}} for hver hovedteknikk/begrep, og \\subsection{{...}} ved behov.
   Et fullverdig kapittel har typisk 4–7 seksjoner.
4. For HVER teknikk/regel:
   * Skriv først forklarende brødtekst (intuisjon — hvorfor virker dette?).
   * Begreper i \\begin{{definisjon}}; formler/regneregler i \\begin{{regel}}[title={...}]
     (rød boks — det eleven skal huske); beviste resultater i \\begin{{setning}}.
   * Der det er naturlig: vis en kort begrunnelse/utledning av formelen.
   * Gi MINST 2 fullt gjennomregnede \\begin{{eksempel}}[title={...}] med align* og
     \\forklaring{{...}} på hvert steg — ikke bare svaret.
   * Legg inn \\begin{{vanligfeil}} med en typisk misforståelse (vis den gale
     utregningen og forklar hvorfor den er feil).
5. Inkluder en formel-/resultattabell (booktabs) der det passer (f.eks. standardintegraler).
6. Gjerne en \\begin{{utforsk}}-aktivitet der eleven undersøker et mønster selv (LK20).
7. Avslutt teoridelen med \\begin{{oppsummering}} som samler de viktigste formlene
   og metodene (gjerne som kompakt liste eller tabell).
8. LEGG oppgaveseksjonen (\\section{{Oppgaver}} med taskbox) HELT til slutt, etter
   all teori, med stigende vanskelighet.
- Bruk rikelig med figurer (PGFPlots/TikZ) for å illustrere begreper.

VIKTIG: Skriv langt og grundig. Et tynt kapittel med bare noen få bokser er feil —
mål på flere sider sammenhengende teori med mange eksempler før oppgavene.

PENSUM: Følg pensum-sjekklisten i prompten — hvert deltema får egen \\section.
Fjern alt innhold som ikke hører til temaet (f.eks. vektorer i funksjonskapittel).
"""
    if material_type == "arbeidsark":
        return """
ARBEIDSARK-MODUS:
- Kort teoridel først: \\begin{husk} for forkunnskaper, \\begin{regel} for formelen
  som arbeidsarket øver på, og ETT gjennomregnet \\begin{eksempel} med \\forklaring{...}.
- Deretter oppgavene i taskbox med stigende vanskelighet.
- Legg \\MMAsvarlinjer eller \\MMArutefelt etter oppgavene så eleven kan skrive.
"""
    return ""

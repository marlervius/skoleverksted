"""
LK20 Curriculum Data - Emnebibliotek og kompetansemål for norsk matematikk.
Basert på Kunnskapsløftet 2020 (LK20).
Utvidet med flere emner og kompetansemål.
"""

# Emnebibliotek organisert etter klassetrinn
TOPIC_LIBRARY = {
    "1.-4. trinn": {
        "Tall og tallforståelse": [
            "Tallene 0-100",
            "Tallene 0-1000",
            "Tallene 0-10 000",
            "Tiervenner",
            "Partall og oddetall",
            "Plassverdisystemet (enere, tiere, hundrere)",
            "Tallinja",
            "Sammenligne og ordne tall",
            "Avrunding av tall",
        ],
        "Regning": [
            "Addisjon med tierovergang",
            "Subtraksjon med tierovergang",
            "Multiplikasjon (gangetabellen 1-10)",
            "Enkel divisjon",
            "Divisjon med rest",
            "Hoderegning",
            "Regnerekkefølge",
            "Regnestrategier",
            "Likhetstegnet og likninger",
        ],
        "Brøk": [
            "Halve og hele",
            "Enkle brøker (1/2, 1/4, 1/3)",
            "Brøk som del av en mengde",
            "Sammenligne enkle brøker",
        ],
        "Måling": [
            "Lengde (mm, cm, m, km)",
            "Vekt (gram, kg)",
            "Volum (dl, liter)",
            "Tid og klokka (analog og digital)",
            "Penger og kroner",
            "Temperatur",
            "Omgjøring mellom enheter",
        ],
        "Geometri": [
            "Geometriske figurer (trekant, firkant, sirkel)",
            "Tredimensjonale figurer (kube, kule, sylinder)",
            "Symmetri",
            "Mønster og rekkefølge",
            "Speiling",
            "Retninger (høyre, venstre, opp, ned)",
        ],
        "Statistikk": [
            "Telle og sortere",
            "Enkle tabeller",
            "Søylediagram",
            "Piktogram",
        ],
    },
    "5.-7. trinn": {
        "Tall og algebra": [
            "Store tall og desimaltall",
            "Negative tall",
            "Primtall og sammensatte tall",
            "Faktorisering",
            "Potenser (kvadrattall, kubikktall)",
            "Regning med parenteser",
            "Regnerekkefølge (PEMDAS)",
            "Enkle likninger",
            "Variabler og uttrykk",
            "Tallmønster og figurtall",
        ],
        "Brøk, desimaltall og prosent": [
            "Brøkregning (addisjon og subtraksjon)",
            "Brøkregning (multiplikasjon)",
            "Desimaltall",
            "Prosent",
            "Omgjøring mellom brøk, desimal og prosent",
            "Finne prosenten av et tall",
            "Sammenligne brøker med ulik nevner",
        ],
        "Forhold og proporsjonalitet": [
            "Forholdstall",
            "Skala og målestokk",
            "Proporsjonale størrelser",
            "Pris per enhet",
        ],
        "Geometri": [
            "Vinkler (spisse, rette, stumpe)",
            "Vinkelmåling med gradskive",
            "Areal av trekanter",
            "Areal av firkanter",
            "Areal av sammensatte figurer",
            "Omkrets",
            "Volum av prisme",
            "Volum av terning",
            "Koordinatsystemet",
            "Konstruksjon med passer og linjal",
            "Formlikhet",
        ],
        "Statistikk og sannsynlighet": [
            "Gjennomsnitt",
            "Median",
            "Typetall",
            "Variasjonsbredde",
            "Diagrammer (søyle, linje, sektor)",
            "Tabeller og frekvens",
            "Enkel sannsynlighet",
            "Kombinatorikk (telle muligheter)",
        ],
    },
    "8. trinn": {
        "Tall og algebra": [
            "Regning med potenser",
            "Potensregler",
            "Kvadratrot",
            "Bokstavregning",
            "Forenkling av uttrykk",
            "Faktorisering av uttrykk",
            "Likninger med én ukjent",
            "Ulikheter",
            "Formler og formelregning",
        ],
        "Brøk, desimaltall og prosent": [
            "Brøkregning alle regnearter",
            "Prosentregning",
            "Promille",
            "Vekstfaktor",
            "Prosentvis økning og reduksjon",
            "Rabatt og påslag",
        ],
        "Geometri": [
            "Pytagoras' setning",
            "Pytagoras' setning - anvendelser",
            "Areal og omkrets av sirkler",
            "Areal og omkrets av sammensatte figurer",
            "Volum av prismer og sylindre",
            "Overflate av prismer",
            "Formlikhet og kongruens",
            "Målestokk",
        ],
        "Funksjoner": [
            "Koordinatsystemet",
            "Lineære sammenhenger",
            "Tabell, graf og formel",
            "Proporsjonale og omvendt proporsjonale størrelser",
            "Praktiske funksjoner",
        ],
        "Statistikk og sannsynlighet": [
            "Sentralmål (gjennomsnitt, median, typetall)",
            "Spredningsmål (variasjonsbredde)",
            "Enkel sannsynlighetsregning",
            "Relativ frekvens",
            "Presentasjon av data",
        ],
    },
    "9. trinn": {
        "Tall og algebra": [
            "Potenser med negative eksponenter",
            "Standardform (vitenskapelig notasjon)",
            "Faktorisering av algebraiske uttrykk",
            "Likninger og ulikheter",
            "Ligningssett (to ukjente)",
            "Grafisk løsning av likningssett",
            "Innsettingsmetoden",
            "Addisjonsmetoden",
        ],
        "Økonomi": [
            "Renter og lån",
            "Rentesrente",
            "Budsjett og regnskap",
            "Prosentvis endring",
            "Vekstfaktor og eksponentiell vekst",
            "Nedbetaling av lån",
            "Sparing",
        ],
        "Geometri": [
            "Pytagoras anvendelser i praktiske oppgaver",
            "Areal av sammensatte figurer",
            "Setninger om trekanter",
            "Konstruksjon med passer og linjal",
            "Geometriske steder",
            "Innskrevne og omskrevne sirkler",
        ],
        "Funksjoner": [
            "Lineære funksjoner",
            "Stigningstall og konstantledd",
            "Skjæringspunkt mellom linjer",
            "Praktiske problemer med funksjoner",
            "Tolkning av grafer",
            "Lineær regresjon",
        ],
        "Statistikk og sannsynlighet": [
            "Statistisk analyse",
            "Kombinatorikk",
            "Sannsynlighetsberegning",
            "Valgtre",
            "Betinget sannsynlighet",
        ],
    },
    "10. trinn": {
        "Tall og algebra": [
            "Rasjonale og irrasjonale tall",
            "Potensregler",
            "Faktorisering av andregradsuttrykk",
            "Konjugatsetningen",
            "Kvadratsetningene",
            "Andregradslikninger",
            "Abc-formelen (løsningsformelen)",
            "Formler og formelregning",
        ],
        "Funksjoner": [
            "Lineære funksjoner - repetisjon",
            "Andregradsfunksjoner (parabler)",
            "Toppunkt og bunnpunkt",
            "Nullpunkter til andregradsfunksjoner",
            "Eksponentialfunksjoner",
            "Praktisk modellering",
            "Regresjon",
        ],
        "Geometri": [
            "Trigonometri i rettvinklede trekanter",
            "Sinus, cosinus og tangens",
            "Finne ukjente sider",
            "Finne ukjente vinkler",
            "Målestokk og formlikhet",
            "Volum av kjegle",
            "Volum av sylinder",
            "Volum av kule",
            "Overflate av sylinder og kule",
        ],
        "Sannsynlighet og statistikk": [
            "Sannsynlighetsmodeller",
            "Kombinatorikk",
            "Ordnet og uordnet utvalg",
            "Kritisk vurdering av statistikk",
            "Histogram og boksplott",
        ],
        "Eksamensoppgaver": [
            "Del 1 oppgaver (uten hjelpemidler)",
            "Del 2 oppgaver (med hjelpemidler)",
            "Problemløsningsoppgaver",
            "Modelleringsoppgaver",
        ],
    },
    "VG1 1T": {
        "Algebra": [
            "Regneregler og parenteser",
            "Potenser og røtter",
            "Rasjonale uttrykk",
            "Brøkregning med variabler",
            "Faktorisering",
            "Likninger og ulikheter",
            "Formelregning",
            "Andregradslikninger",
            "Faktorisering av andregradsuttrykk",
        ],
        "Funksjoner": [
            "Lineære funksjoner",
            "Andregradsfunksjoner",
            "Polynomfunksjoner",
            "Rasjonale funksjoner",
            "Eksponentialfunksjoner",
            "Logaritmer",
            "Logaritmeregler",
            "Eksponentiallikninger",
        ],
        "Geometri": [
            "Trigonometri (sinus, cosinus, tangens)",
            "Sinussetningen",
            "Cosinussetningen",
            "Arealsetningen",
            "Vektorer i planet",
            "Vektorregning",
            "Skalarprodukt",
            "Analytisk geometri",
        ],
        "Sannsynlighet": [
            "Kombinatorikk",
            "Permutasjoner",
            "Kombinasjoner",
            "Sannsynlighetsberegning",
            "Ordnet og uordnet utvalg",
            "Med og uten tilbakelegging",
        ],
    },
    "VG1 1P": {
        "Tall og algebra": [
            "Prosentregning",
            "Vekstfaktor",
            "Praktisk bruk av formler",
            "Likninger",
            "Formelregning",
        ],
        "Økonomi": [
            "Budsjett og regnskap",
            "Lån og sparing",
            "Renter og avdrag",
            "Annuitetslån og serielån",
            "Skatteberegning",
            "Personlig økonomi",
            "Valuta",
        ],
        "Funksjoner": [
            "Lineære modeller",
            "Praktiske funksjoner",
            "Grafisk framstilling",
            "Tolkning av grafer",
            "Regresjon med digitale verktøy",
        ],
        "Geometri": [
            "Måling og beregning",
            "Praktisk trigonometri",
            "Areal og volum",
            "Målestokk",
        ],
        "Statistikk": [
            "Dataanalyse",
            "Sentralmål og spredningsmål",
            "Kritisk vurdering",
            "Presentasjon av data",
            "Utvalg og populasjon",
        ],
    },
    "VG2 2P": {
        "Tall og algebra": [
            "Prosentregning i ulike sammenhenger",
            "Vekstfaktor og prosentvis endring",
            "Budsjett og regnskap",
            "Lån, renter og sparing",
            "Indeksregulering",
            "Valutaberegninger",
        ],
        "Funksjoner og modeller": [
            "Lineære modeller i praksis",
            "Eksponentiell vekst og nedbryting",
            "Modellering med regresjon",
            "Tolke og bruke grafiske fremstillinger",
            "Digitale verktøy for modellering",
        ],
        "Statistikk": [
            "Sentralmål og spredningsmål",
            "Normalfordelingen",
            "Standardavvik og varians",
            "Korrelasjon og regresjon",
            "Statistiske undersøkelser",
            "Feilkilder i statistikk",
        ],
        "Sannsynlighet": [
            "Betinget sannsynlighet",
            "Uavhengige og avhengige hendelser",
            "Sannsynlighetstre og krysstabell",
            "Simulering med digitale verktøy",
        ],
        "Geometri": [
            "Trigonometri i praktiske oppgaver",
            "Arealberegning av sammensatte figurer",
            "Volumberegning",
            "Målestokk og kart",
        ],
    },
    "VG2 R1": {
        "Algebra": [
            "Polynomdivisjon",
            "Faktorisering av polynomer",
            "Nullpunkter til polynomer",
            "Rasjonale uttrykk",
            "Eksponential- og logaritmefunksjoner",
            "Likninger med logaritmer",
            "Eksponentiallikninger",
        ],
        "Funksjoner": [
            "Polynomfunksjoner og egenskaper",
            "Rasjonale funksjoner og asymptoter",
            "Sammensetning av funksjoner",
            "Kontinuitet",
            "Grenseverdier",
            "Definisjon av grenseverdi",
        ],
        "Derivasjon": [
            "Definisjon av derivasjon",
            "Derivasjon fra definisjonen",
            "Derivasjonsregler",
            "Produktregelen",
            "Kvotientregelen",
            "Kjerneregelen",
            "Implisitt derivasjon",
            "Drøfting av funksjoner",
            "Ekstremalpunkter",
            "Vendepunkter",
            "Optimering",
        ],
        "Geometri": [
            "Vektorer i rommet",
            "Skalarprodukt i rommet",
            "Vektorprodukt",
            "Parametriske kurver",
            "Linjer i rommet",
            "Planet i rommet",
        ],
        "Kombinatorikk og sannsynlighet": [
            "Kombinatorikk - repetisjon",
            "Sannsynlighetsmodeller",
            "Binomisk sannsynlighetsmodell",
            "Binomialfordelingen",
            "Forventningsverdi og standardavvik",
        ],
    },
    "VG3 R2": {
        "Funksjoner og derivasjon": [
            "Trigonometriske funksjoner",
            "Derivasjon av trigonometriske funksjoner",
            "Logaritme- og eksponentialfunksjoner",
            "Derivasjon av ln og e^x",
            "Anvendelser av derivasjon",
            "Relaterte rater",
            "Linearisering",
        ],
        "Integralregning": [
            "Ubestemte integraler",
            "Integrasjonsregler",
            "Integrasjon ved substitusjon",
            "Delvis integrasjon",
            "Integrasjon av rasjonale funksjoner",
            "Bestemte integraler",
            "Areal under kurver",
            "Areal mellom kurver",
            "Volum av omdreiningslegemer",
        ],
        "Differensiallikninger": [
            "Separable differensiallikninger",
            "Lineære førsteordens differensiallikninger",
            "Lineære andreordens differensiallikninger",
            "Modellering med differensiallikninger",
            "Vekstmodeller",
        ],
        "Rekker": [
            "Aritmetiske rekker",
            "Geometriske rekker",
            "Uendelige geometriske rekker",
            "Konvergens og divergens",
            "Teleskoprekker",
            "Taylorrekker (introduksjon)",
        ],
    },
}

# LK20 Kompetansemål (utvidet med flere trinn)
COMPETENCY_GOALS = {
    "1.-4. trinn": [
        "Telle til 100, dele opp og bygge mengder opp til 10, sette sammen og dele opp tiergrupper",
        "Utvikle, bruke og samtale om varierte regnestrategier for addisjon og subtraksjon",
        "Utforske og beskrive strukturer og mønster i lek og spill",
        "Bruke ulike måleenheter for lengde og masse i praktiske situasjoner",
        "Utforske, lage og beskrive geometriske mønster med og uten digitale verktøy",
        "Samle, sortere og forklare data og lage enkle fremstillinger",
    ],
    "5.-7. trinn": [
        "Utforske og beskrive primtall, faktorisering og bruke det til å finne fellesnevner",
        "Sammenligne, ordne og regne med negative tall",
        "Beskrive plassering og forflytning i et koordinatsystem",
        "Utforske og bruke strategier for regning med desimaltall, brøk og prosent",
        "Utforske og argumentere for formler for omkrets, areal og volum",
        "Samle inn, sortere, presentere og lese av data og vurdere om fremstillingene er hensiktsmessige",
    ],
    "8. trinn": [
        "Utforske og beskrive strukturer og forandringer i geometriske mønster",
        "Beskrive og generalisere mønster med bokstaver og andre symboler",
        "Utforske og øve på strategier for regning med brøk, desimaltall og prosent",
        "Utforske sammenhengen mellom brøk, desimaltall og prosent",
        "Lage og programmere algoritmer med bruk av variabler og vilkår",
        "Utforske Pytagoras' setning og bruke den til å beregne lengder",
        "Utforske og argumentere for formler for areal og volum",
        "Samle inn, sortere og vurdere data og presentere med og uten digitale verktøy",
    ],
    "9. trinn": [
        "Behandle og faktorisere algebraiske uttrykk, og bruke dette i likninger og ulikheter",
        "Modellere situasjoner knyttet til reelle datasett og vurdere modellene",
        "Utforske og beskrive ulike representasjoner av funksjoner",
        "Utforske strategier for å løse likninger og likningssett",
        "Lage og bruke budsjett og regnskap med inntekt, utgifter og sparing",
        "Beregne og vurdere renter ved lån og sparing",
        "Bruke formlikhet og trigonometri til å beregne lengder og vinkler",
        "Planlegge, gjennomføre og presentere statistiske undersøkelser",
    ],
    "10. trinn": [
        "Utforske matematiske egenskaper og sammenhenger ved å bruke programmering",
        "Behandle og faktorisere enkle algebraiske uttrykk, og regne med formler",
        "Løse likninger og ulikheter av første og andre grad",
        "Utforske og beskrive egenskaper ved ulike funksjonstyper",
        "Analysere og presentere datasett med relevante statistiske mål",
        "Bruke trigonometri til å beregne lengder og vinkler i praktiske oppgaver",
        "Beregne overflate og volum av sylinder, kjegle og kule",
        "Vurdere og drøfte sannsynligheter ved hjelp av simuleringer",
    ],
    "VG1 1T": [
        "Omforme og forenkle sammensatte uttrykk, løse likninger og ulikheter",
        "Utforske, analysere og drøfte polynomfunksjoner og rasjonale funksjoner",
        "Utforske, forstå og bruke eksponentialfunksjoner og logaritmer",
        "Bruke trigonometri til beregninger og problemløsning",
        "Bruke vektorer til å beskrive bevegelse, beregne lengder og finne vinkler",
        "Kombinatorikk og sannsynlighetsberegning med ordnet og uordnet utvalg",
    ],
    "VG1 1P": [
        "Planlegge, gjennomføre og presentere selvstendig arbeid knyttet til økonomi",
        "Bruke funksjonsbegrepet i praktiske sammenhenger og gjøre rede for lineære modeller",
        "Analysere og presentere et datamateriale og drøfte ulike dataframstillinger",
        "Gjøre rede for og bruke formler i praktiske situasjoner",
        "Bruke trigonometri til beregninger i praktiske sammenhenger",
    ],
    "VG2 2P": [
        "Bruke prosent, prosentpoeng og vekstfaktor i ulike sammenhenger",
        "Planlegge, gjennomføre og presentere selvstendig arbeid knyttet til personlig økonomi",
        "Lage, tolke og drøfte funksjoner som modellerer praktiske situasjoner",
        "Gjennomføre statistiske undersøkelser og drøfte resultater kritisk",
        "Beregne og tolke sentralmål, spredningsmål og korrelasjon",
        "Bruke normalfordelingen til å beregne sannsynligheter",
    ],
    "VG2 R1": [
        "Finne grenseverdier og drøfte kontinuitet til funksjoner",
        "Derivere og drøfte polynomfunksjoner, rasjonale funksjoner og eksponentialfunksjoner",
        "Løse likninger med eksponential- og logaritmefunksjoner analytisk og grafisk",
        "Bruke derivasjon til å løse praktiske optimeringsproblemer",
        "Gjøre rede for vektorer i rommet og regne med skalarproduktet",
        "Gjøre rede for binomisk sannsynlighetsmodell og bruke den til beregninger",
    ],
    "VG3 R2": [
        "Derivere og integrere trigonometriske funksjoner",
        "Bruke ulike teknikker for integrasjon av funksjoner",
        "Beregne areal mellom kurver og volum av omdreiningslegemer",
        "Løse separable og lineære differensiallikninger analytisk",
        "Gjøre rede for uendelige rekker og bestemme konvergens",
        "Modellere praktiske situasjoner med differensiallikninger",
    ],
}

# Oppgavetyper
EXERCISE_TYPES = {
    "standard": {
        "name": "📝 Regneoppgaver",
        "description": "Klassiske oppgaver med beregninger",
        "instruction": "Lag tradisjonelle regneoppgaver med tydelig oppgavetekst og krav om utregning. Vis mellomregninger i løsningsforslaget."
    },
    "multiple_choice": {
        "name": "🔘 Flervalg",
        "description": "Oppgaver med svaralternativer A, B, C, D",
        "instruction": "Lag flervalgsoppgaver med 4 svaralternativer (A, B, C, D). Kun ett svar er riktig. Bruk \\begin{enumerate}[label=\\Alph*)] for alternativene. Inkluder distraktorer som tester vanlige feil."
    },
    "fill_blank": {
        "name": "📋 Utfylling",
        "description": "Fyll inn manglende tall/uttrykk",
        "instruction": "Lag utfyllingsoppgaver der eleven må fylle inn manglende tall eller uttrykk. Bruk \\underline{\\hspace{2cm}} for blanke felt. Oppgavene skal teste forståelse av konsepter."
    },
    "word_problem": {
        "name": "📖 Tekstoppgaver",
        "description": "Praktiske problemstillinger",
        "instruction": "Lag praktiske tekstoppgaver med hverdagslige situasjoner som krever matematisk modellering. Bruk norske navn og realistiske tall. Oppgavene skal kreve at eleven setter opp og løser likninger eller beregninger."
    },
    "true_false": {
        "name": "✓✗ Sant/Usant",
        "description": "Vurder om påstander er sanne",
        "instruction": "Lag sant/usant-påstander der eleven må avgjøre om matematiske utsagn er korrekte. Inkluder både sanne og usanne påstander. Krever begrunnelse i løsningsforslaget."
    },
    "matching": {
        "name": "🔗 Kobling",
        "description": "Match uttrykk med svar",
        "instruction": "Lag koblingsoppgaver der eleven må matche matematiske uttrykk i venstre kolonne med riktige svar i høyre kolonne. Bruk tabeller for oversiktlig layout."
    },
    "proof": {
        "name": "📐 Bevisoppgaver",
        "description": "Matematiske bevis og resonnementer",
        "instruction": "Lag oppgaver der eleven må bevise matematiske sammenhenger eller resonnere seg frem til løsningen. Krev tydelig argumentasjon og logisk oppbygging."
    },
    "graphical": {
        "name": "📊 Grafiske oppgaver",
        "description": "Tegne, lese av eller tolke grafer",
        "instruction": "Lag oppgaver som involverer grafer og figurer. Eleven kan bli bedt om å tegne grafer, lese av verdier, eller tolke grafiske fremstillinger. Inkluder koordinatsystem eller figur i oppgaven."
    },
    "open_ended": {
        "name": "💭 Åpne oppgaver",
        "description": "Utforskende oppgaver med flere løsninger",
        "instruction": "Lag åpne oppgaver der eleven kan utforske og finne flere mulige løsninger. Oppgavene skal stimulere til matematisk tenkning og kreativitet."
    },
}

# Grensebetingelser per trinn - definerer hva som ER og IKKE ER passende
# Brukes for å sikre at generert innhold matcher valgt klassetrinn
GRADE_BOUNDARIES = {
    "1.-4. trinn": {
        "description": "Barnetrinnet - konkret, lekbasert matematikk",
        "cognitive_level": "Konkret-operasjonelt",
        "allowed_concepts": [
            "Addisjon og subtraksjon opp til 1000",
            "Multiplikasjon (gangetabellen 1-10)",
            "Enkel divisjon med og uten rest",
            "Brøker som del av helhet (1/2, 1/4, 1/3)",
            "Geometriske grunnformer",
            "Klokka og tid",
            "Penger og kroner",
            "Lengde, vekt og volum (enkle enheter)",
        ],
        "forbidden_concepts": [
            "Negative tall",
            "Desimaltall med mer enn én desimal",
            "Algebra og variabler",
            "Koordinatsystem",
            "Prosent",
            "Brøkregning (addisjon/subtraksjon av brøker)",
            "Vinkelmåling",
        ],
        "number_complexity": {
            "max_value": 10000,
            "allow_negative": False,
            "allow_decimals": False,
            "allow_fractions": True,
            "fraction_types": ["enkel"],  # 1/2, 1/4, 3/4
        },
        "example_exercises": [
            "23 + 45 = ?",
            "8 × 7 = ?",
            "Del sirkelen i 4 like deler. Fargelegg 3/4.",
            "Klokka er halv tre. Tegn viserne.",
            "Marie har 50 kr. Hun kjøper en is til 25 kr. Hvor mye har hun igjen?",
        ],
        "too_hard_examples": [
            "Løs likningen x + 5 = 12",  # Algebra
            "Regn ut 25% av 80",  # Prosent
            "Finn arealet når lengden er 5,5 cm",  # Desimaltall
        ],
        "difficulty_definitions": {
            "lett": "Ensifrede tall, direkte operasjon, visuell støtte",
            "middels": "Tosifrede tall, tierovergang, enkel tekstoppgave",
            "vanskelig": "Tresifrede tall, flere operasjoner, praktisk kontekst",
        },
    },
    "5.-7. trinn": {
        "description": "Mellomtrinnet - overgang til abstrakt tenkning",
        "cognitive_level": "Konkret til formell-operasjonelt",
        "allowed_concepts": [
            "Negative tall på tallinja",
            "Desimaltall",
            "Brøkregning (addisjon, subtraksjon, multiplikasjon)",
            "Prosent (finne prosent av tall)",
            "Enkle likninger (x + 5 = 12)",
            "Koordinatsystem (første kvadrant)",
            "Vinkler og vinkelmåling",
            "Areal og omkrets av enkle figurer",
            "Gjennomsnitt, median, typetall",
        ],
        "forbidden_concepts": [
            "Potenser med negative eksponenter",
            "Andregradsuttrykk",
            "Pytagoras' setning",
            "Funksjoner som begrep",
            "Ligningssett",
            "Sannsynlighetsregning med multiplikasjon",
            "Rentesrente",
        ],
        "number_complexity": {
            "max_value": 1000000,
            "allow_negative": True,
            "allow_decimals": True,
            "max_decimal_places": 2,
            "allow_fractions": True,
        },
        "example_exercises": [
            "Regn ut 3/4 + 1/2",
            "Finn 25% av 80 kr",
            "Hva er gjennomsnittet av 12, 15, 18 og 23?",
            "Finn arealet av et rektangel med lengde 8 cm og bredde 5 cm",
            "Plasser punktet (3, 4) i koordinatsystemet",
        ],
        "too_easy_examples": [
            "5 + 3 = ?",  # For enkelt
            "Tegn en trekant",  # For enkelt
        ],
        "too_hard_examples": [
            "Løs likningen 2x + 3 = x - 4",  # Ukjent på begge sider
            "Bruk Pytagoras til å finne hypotenusen",  # 8. trinn
            "Finn stigningstallet til funksjonen",  # 8. trinn
        ],
        "difficulty_definitions": {
            "lett": "Én operasjon, pene tall, direkte anvendelse av formel",
            "middels": "To operasjoner, brøker/desimaler, enkel tekstoppgave",
            "vanskelig": "Flere steg, kombinere konsepter, problemløsning",
        },
    },
    "8. trinn": {
        "description": "Starten på ungdomstrinnet - algebra og funksjoner introduseres",
        "cognitive_level": "Formell-operasjonelt",
        "allowed_concepts": [
            "Potenser og potensregler",
            "Kvadratrot",
            "Bokstavregning og forenkling",
            "Likninger med én ukjent (også med ukjent på begge sider)",
            "Pytagoras' setning",
            "Areal og omkrets av sirkler",
            "Volum av prismer og sylindre",
            "Koordinatsystem med alle fire kvadranter",
            "Lineære sammenhenger (tabell, graf, formel)",
            "Prosentvis økning og reduksjon",
        ],
        "forbidden_concepts": [
            "Ligningssett med to ukjente",
            "Standardform (vitenskapelig notasjon)",
            "Rentesrente-formelen",
            "Trigonometri (sin, cos, tan)",
            "Andregradslikninger",
            "Faktorisering av andregradsuttrykk",
            "Eksponentialfunksjoner",
            "Andregradsformelen",
        ],
        "number_complexity": {
            "max_value": 10000000,
            "allow_negative": True,
            "allow_decimals": True,
            "max_decimal_places": 3,
            "allow_fractions": True,
            "allow_roots": True,
            "allow_powers": True,
            "max_power": 3,
        },
        "example_exercises": [
            "Løs likningen 3x + 7 = 2x - 5",
            "Forenkle uttrykket 4a + 3b - 2a + 5b",
            "En rettvinklet trekant har kateter 3 cm og 4 cm. Finn hypotenusen.",
            "Finn arealet av en sirkel med radius 5 cm",
            "Les av koordinatene til punktene A, B og C i koordinatsystemet",
            "En vare koster 400 kr. Den settes ned 20%. Hva er ny pris?",
        ],
        "too_easy_examples": [
            "Regn ut 3 × 7",  # Barnetrinn
            "Hva er 50% av 100?",  # For direkte
        ],
        "too_hard_examples": [
            "Løs likningssettet x + y = 5 og 2x - y = 4",  # 9. trinn
            "Finn sin(30°)",  # 10. trinn
            "Løs x² - 5x + 6 = 0",  # 10. trinn
            "Beregn renter og rentes rente over 3 år",  # 9. trinn
        ],
        "difficulty_definitions": {
            "lett": "Direkte anvendelse av én formel/regel, positive heltall",
            "middels": "Kombinere to konsepter, negative tall eller desimaler",
            "vanskelig": "Flerstegsproblem, praktisk kontekst, krever resonnement",
        },
    },
    "9. trinn": {
        "description": "Ungdomstrinnet - økonomi, ligningssett og dypere funksjonsforståelse",
        "cognitive_level": "Formell-operasjonelt",
        "allowed_concepts": [
            "Potenser med negative eksponenter",
            "Standardform (vitenskapelig notasjon)",
            "Faktorisering av algebraiske uttrykk",
            "Ligningssett med to ukjente",
            "Grafisk løsning av likningssett",
            "Innsettingsmetoden og addisjonsmetoden",
            "Lineære funksjoner (stigningstall, konstantledd)",
            "Rentesrente og vekstfaktor",
            "Budsjett og regnskap",
            "Kombinatorikk og valgtre",
        ],
        "forbidden_concepts": [
            "Andregradslikninger",
            "Andregradsformelen (abc-formelen)",
            "Andregradsfunksjoner (parabler)",
            "Trigonometri (sin, cos, tan)",
            "Eksponentialfunksjoner (som funksjonstype)",
            "Faktorisering av andregradsuttrykk",
            "Toppunkt/bunnpunkt",
        ],
        "number_complexity": {
            "max_value": 100000000,
            "allow_negative": True,
            "allow_decimals": True,
            "max_decimal_places": 4,
            "allow_scientific_notation": True,
            "allow_growth_factors": True,
        },
        "example_exercises": [
            "Løs likningssettet: x + y = 10 og 2x - y = 5",
            "Skriv 0,00045 på standardform",
            "Du setter 10 000 kr i banken med 3% rente. Hvor mye har du etter 5 år?",
            "Finn stigningstallet og konstantleddet til linjen gjennom (0, 3) og (2, 7)",
            "Faktoriser uttrykket 6x + 9",
        ],
        "too_easy_examples": [
            "Løs x + 5 = 12",  # 8. trinn
            "Finn arealet av en sirkel",  # 8. trinn (direkte)
        ],
        "too_hard_examples": [
            "Løs x² - 4x - 5 = 0",  # 10. trinn
            "Finn nullpunktene til f(x) = x² - 4",  # 10. trinn
            "Beregn sin(45°)",  # 10. trinn
        ],
        "difficulty_definitions": {
            "lett": "Standard ligningssett, enkle vekstfaktorer",
            "middels": "Praktisk økonomioppgave, tolke lineære funksjoner",
            "vanskelig": "Modellering med funksjoner, sammensatt økonomiproblem",
        },
    },
    "10. trinn": {
        "description": "Avslutning av ungdomstrinnet - andregradsuttrykk og trigonometri",
        "cognitive_level": "Formell-operasjonelt, forberedelse til VGS",
        "allowed_concepts": [
            "Rasjonale og irrasjonale tall",
            "Faktorisering av andregradsuttrykk",
            "Konjugatsetningen og kvadratsetningene",
            "Andregradslikninger og abc-formelen",
            "Andregradsfunksjoner (parabler)",
            "Toppunkt og bunnpunkt",
            "Nullpunkter til andregradsfunksjoner",
            "Trigonometri i rettvinklede trekanter (sin, cos, tan)",
            "Eksponentialfunksjoner (enkel)",
            "Volum av kjegle, sylinder og kule",
            "Histogram og boksplott",
        ],
        "forbidden_concepts": [
            "Sinussetningen og cosinussetningen",
            "Radianer",
            "Logaritmer",
            "Derivasjon",
            "Polynomer av grad høyere enn 2",
            "Vektorer",
            "Binomisk sannsynlighet",
            "Kontinuitet og grenseverdier",
        ],
        "number_complexity": {
            "max_value": 1000000000,
            "allow_negative": True,
            "allow_decimals": True,
            "allow_irrational": True,
            "allow_quadratic_solutions": True,
        },
        "example_exercises": [
            "Løs andregradslikningen x² - 5x + 6 = 0",
            "Faktoriser x² - 9 ved hjelp av konjugatsetningen",
            "Finn toppunktet til f(x) = -x² + 4x - 3",
            "En stige på 5 m står mot en vegg. Bunnen er 3 m fra veggen. Hvor høyt opp når stigen?",
            "Finn vinkelen A i en rettvinklet trekant der motstående katet er 4 og hosliggende er 3",
            "Finn volumet av en kule med radius 6 cm",
        ],
        "too_easy_examples": [
            "Løs 3x + 2 = 11",  # 8. trinn
            "Finn arealet av et rektangel",  # Mellomtrinn
        ],
        "too_hard_examples": [
            "Bruk sinussetningen til å finne siden a",  # VG1
            "Derivér f(x) = x³ - 2x",  # VG2
            "Løs ln(x) = 2",  # VG1
        ],
        "difficulty_definitions": {
            "lett": "Faktorisering med pene tall, direkte trigonometri",
            "middels": "Abc-formelen med heltallssvar, finne toppunkt",
            "vanskelig": "Praktisk modellering, kombinere trigonometri og Pytagoras",
        },
    },
    "VG1 1T": {
        "description": "Teoretisk matematikk VG1 - dypere algebra, logaritmer, vektorer",
        "cognitive_level": "Abstrakt, formelt",
        "allowed_concepts": [
            "Polynomfunksjoner",
            "Rasjonale funksjoner",
            "Eksponentialfunksjoner og logaritmer",
            "Logaritmeregler",
            "Eksponentiallikninger",
            "Sinussetningen og cosinussetningen",
            "Arealsetningen",
            "Vektorer i planet",
            "Skalarprodukt",
            "Kombinatorikk (permutasjoner, kombinasjoner)",
        ],
        "forbidden_concepts": [
            "Derivasjon",
            "Grenseverdier og kontinuitet",
            "Integrasjon",
            "Vektorer i rommet",
            "Differensiallikninger",
            "Binomialfordelingen (avansert)",
            "Taylorrekker",
        ],
        "example_exercises": [
            "Løs likningen 2^x = 16",
            "Forenkle lg(100) + lg(10)",
            "Finn alle sidene i en trekant der a = 5, B = 40° og C = 60°",
            "Gitt vektorene a = [3, 4] og b = [1, 2]. Finn a · b",
            "På hvor mange måter kan 5 personer stille seg i kø?",
        ],
        "too_easy_examples": [
            "Løs x² - 4 = 0",  # 10. trinn
            "Finn sin(30°)",  # 10. trinn (direkte oppslag)
        ],
        "too_hard_examples": [
            "Finn f'(x) når f(x) = x³",  # R1
            "Beregn ∫x² dx",  # R2
        ],
        "difficulty_definitions": {
            "lett": "Standard logaritmeregning, enkel vektorregning",
            "middels": "Sinussetningen med ukjent vinkel, sammensatt eksponentiallikning",
            "vanskelig": "Modellering med vektorer, bevis med trigonometri",
        },
    },
    "VG1 1P": {
        "description": "Praktisk matematikk VG1 - økonomi, statistikk, praktiske anvendelser",
        "cognitive_level": "Anvendt, praktisk",
        "allowed_concepts": [
            "Prosentregning og vekstfaktor",
            "Lån, renter og avdrag",
            "Annuitetslån og serielån",
            "Budsjett og regnskap",
            "Lineære modeller i praksis",
            "Regresjon med digitale verktøy",
            "Statistisk analyse",
            "Praktisk trigonometri",
        ],
        "forbidden_concepts": [
            "Logaritmer",
            "Polynomfunksjoner av høy grad",
            "Vektorer",
            "Derivasjon",
            "Formelle bevis",
            "Kombinatorikk (permutasjoner/kombinasjoner)",
        ],
        "example_exercises": [
            "Du tar opp et lån på 200 000 kr med 5% rente. Hva er månedlig annuitet over 10 år?",
            "Lag et budsjett for en student med inntekt 10 000 kr/mnd",
            "En stige på 6 m lener mot en vegg og danner 70° med bakken. Hvor høyt når den?",
            "Analyser dette datasettet og finn gjennomsnitt, median og standardavvik",
        ],
        "difficulty_definitions": {
            "lett": "Direkte prosentregning, enkel renteutregning",
            "middels": "Sammenligne låntyper, tolke statistikk",
            "vanskelig": "Helhetlig økonomianalyse, kritisk vurdering av data",
        },
    },
    "VG2 2P": {
        "description": "Praktisk matematikk VG2 - økonomi, statistikk, modellering",
        "cognitive_level": "Anvendt, praktisk, hverdagsrelatert",
        "allowed_concepts": [
            "Prosentregning og vekstfaktor",
            "Lån, renter, sparing, budsjett",
            "Lineære og eksponentielle modeller",
            "Regresjon",
            "Sentralmål og spredningsmål",
            "Normalfordelingen",
            "Korrelasjon",
            "Betinget sannsynlighet",
            "Trigonometri i praktiske sammenhenger",
        ],
        "forbidden_concepts": [
            "Derivasjon",
            "Integrasjon",
            "Vektorer i rommet",
            "Komplekse tall",
            "Formelle bevis",
            "Abstrakt algebra",
        ],
        "example_exercises": [
            "Du låner 200 000 kr til 4,5 % rente. Hva er månedlig terminbeløp over 5 år?",
            "En by hadde 25 000 innbyggere i 2020 og vokser med 1,8 % per år. Lag en modell.",
            "Finn gjennomsnitt, median og standardavvik for datasettet: 12, 15, 18, 22, 25, 28",
            "En vare kostet 450 kr. Prisen øker med 12 %. Hva er ny pris?",
            "Bruk normalfordelingen: Høyden til elever er normalfordelt med μ=170 og σ=8. Finn P(X > 180).",
        ],
        "too_hard_examples": [
            "Derivér f(x) = x³ - 3x",
            "Finn grenseverdien lim (x→0) sin(x)/x",
            "Beregn vektorproduktet",
        ],
        "difficulty_definitions": {
            "lett": "Enkel prosentregning, lese av diagram, finne gjennomsnitt",
            "middels": "Vekstfaktor over tid, normalfordeling, regresjon",
            "vanskelig": "Sammenligne lånetilbud, kritisk vurdering av statistikk, modellering",
        },
    },
    "VG2 R1": {
        "description": "Realfagsmatematikk 1 - derivasjon, vektorer i rommet, grenseverdier",
        "cognitive_level": "Avansert abstrakt",
        "allowed_concepts": [
            "Grenseverdier",
            "Kontinuitet",
            "Derivasjon fra definisjonen",
            "Derivasjonsregler (produkt, kvotient, kjerne)",
            "Drøfting av funksjoner",
            "Ekstremalpunkter og vendepunkter",
            "Optimering",
            "Vektorer i rommet",
            "Vektorprodukt",
            "Linjer og plan i rommet",
            "Binomialfordelingen",
        ],
        "forbidden_concepts": [
            "Integrasjon",
            "Differensiallikninger",
            "Taylorrekker",
            "Partielle deriverte",
            "Multivariabel kalkulus",
        ],
        "example_exercises": [
            "Derivér f(x) = x³ - 3x² + 2x",
            "Finn ekstremalpunktene til f(x) = x³ - 6x² + 9x + 1",
            "Finn likningen for tangenten til f(x) = x² i punktet (2, 4)",
            "Finn vektorproduktet av a = [1, 2, 3] og b = [4, 5, 6]",
            "En boks uten lokk skal ha volum 500 cm³. Finn dimensjonene som gir minst materialbruk",
        ],
        "difficulty_definitions": {
            "lett": "Standard derivasjon, finne ekstremalpunkt",
            "middels": "Kjerneregelen, drøfting av rasjonal funksjon",
            "vanskelig": "Optimeringsproblem med modellering, kompleks vektoroppgave",
        },
    },
    "VG3 R2": {
        "description": "Realfagsmatematikk 2 - integrasjon, differensiallikninger, rekker",
        "cognitive_level": "Høyt abstrakt, universitetsforberedende",
        "allowed_concepts": [
            "Integrasjon (alle teknikker)",
            "Substitusjon og delvis integrasjon",
            "Areal mellom kurver",
            "Volum av omdreiningslegemer",
            "Separable differensiallikninger",
            "Lineære differensiallikninger",
            "Aritmetiske og geometriske rekker",
            "Konvergens og divergens",
            "Trigonometriske funksjoner (derivasjon/integrasjon)",
        ],
        "forbidden_concepts": [
            "Partielle differensiallikninger",
            "Fourierrekker",
            "Komplekse tall (avansert)",
            "Lineær algebra (matriser)",
        ],
        "example_exercises": [
            "Beregn ∫(2x + 1)³ dx ved substitusjon",
            "Finn arealet mellom y = x² og y = x",
            "Løs differensiallikningen dy/dx = 2xy",
            "Finn summen av den uendelige rekken 1 + 1/2 + 1/4 + 1/8 + ...",
            "Finn volumet når området mellom y = √x og x-aksen fra x=0 til x=4 roteres om x-aksen",
        ],
        "difficulty_definitions": {
            "lett": "Standard integrasjon, enkel separabel diff.likn.",
            "middels": "Delvis integrasjon, areal mellom kurver",
            "vanskelig": "Volum av omdreiningslegeme, modellering med diff.likn.",
        },
    },
}


def get_grade_boundaries(grade: str) -> dict:
    """
    Get the boundary constraints for a specific grade level.
    
    Args:
        grade: The grade level string (e.g., "8. trinn", "VG1 1T")
    
    Returns:
        Dictionary with allowed/forbidden concepts, examples, etc.
    """
    # Normalize grade name
    grade_lower = grade.lower()
    
    for key in GRADE_BOUNDARIES.keys():
        if grade_lower in key.lower() or key.lower() in grade_lower:
            return GRADE_BOUNDARIES[key]
    
    # Try partial matching
    for key in GRADE_BOUNDARIES.keys():
        key_parts = key.lower().replace(".", "").split()
        grade_parts = grade_lower.replace(".", "").split()
        if any(part in grade_parts for part in key_parts):
            return GRADE_BOUNDARIES[key]
    
    return {}


def format_boundaries_for_prompt(grade: str) -> str:
    """
    Format grade boundaries as a string suitable for inclusion in agent prompts.
    
    Args:
        grade: The grade level string
    
    Returns:
        Formatted string with constraints and examples
    """
    boundaries = get_grade_boundaries(grade)
    
    if not boundaries:
        return ""
    
    lines = [
        f"=== KRAV FOR {grade.upper()} ===",
        f"Nivå: {boundaries.get('description', '')}",
        "",
        "TILLATTE KONSEPTER:",
    ]
    
    for concept in boundaries.get("allowed_concepts", []):
        lines.append(f"  ✓ {concept}")
    
    lines.append("")
    lines.append("FORBUDTE KONSEPTER (for avansert for dette trinnet):")
    
    for concept in boundaries.get("forbidden_concepts", []):
        lines.append(f"  ✗ {concept}")
    
    lines.append("")
    lines.append("EKSEMPLER PÅ PASSENDE OPPGAVER:")
    
    for example in boundaries.get("example_exercises", []):
        lines.append(f"  • {example}")
    
    if boundaries.get("too_hard_examples"):
        lines.append("")
        lines.append("FOR VANSKELIG - UNNGÅ DETTE:")
        for example in boundaries.get("too_hard_examples", []):
            lines.append(f"  ✗ {example}")
    
    if boundaries.get("difficulty_definitions"):
        lines.append("")
        lines.append("VANSKELIGHETSGRADERING FOR DETTE TRINNET:")
        for level, desc in boundaries.get("difficulty_definitions", {}).items():
            lines.append(f"  {level.capitalize()}: {desc}")
    
    return "\n".join(lines)


# Tidsestimater for ulike materialtyper (minutter)
TIME_ESTIMATES = {
    "arbeidsark": {
        "base": 15,
        "per_exercise": 3,
        "theory_multiplier": 1.0,
        "examples_multiplier": 1.2,
    },
    "kapittel": {
        "base": 45,
        "per_exercise": 5,
        "theory_multiplier": 1.5,
        "examples_multiplier": 1.3,
    },
    "prøve": {
        "base": 20,
        "per_exercise": 4,
        "theory_multiplier": 1.0,
        "examples_multiplier": 1.0,
    },
    "lekseark": {
        "base": 10,
        "per_exercise": 2,
        "theory_multiplier": 1.0,
        "examples_multiplier": 1.1,
    },
}


def get_topics_for_grade(grade: str) -> dict:
    """Get topics organized by category for a specific grade level."""
    # Normalize grade name
    grade_key = grade
    for key in TOPIC_LIBRARY.keys():
        if grade.lower() in key.lower() or key.lower() in grade.lower():
            grade_key = key
            break
    
    return TOPIC_LIBRARY.get(grade_key, {})


def get_all_topics_flat(grade: str) -> list:
    """Get a flat list of all topics for a grade."""
    topics = get_topics_for_grade(grade)
    flat_list = []
    for category, topic_list in topics.items():
        flat_list.extend(topic_list)
    return flat_list


def get_competency_goals(grade: str) -> list:
    """Get competency goals for a specific grade level."""
    # Normalize grade name
    grade_key = grade
    for key in COMPETENCY_GOALS.keys():
        if grade.lower() in key.lower() or key.lower() in grade.lower():
            grade_key = key
            break
    
    return COMPETENCY_GOALS.get(grade_key, [])


def get_exercise_types() -> dict:
    """Get all available exercise types."""
    return EXERCISE_TYPES


def estimate_generation_time(
    material_type: str,
    num_exercises: int = 10,
    include_theory: bool = True,
    include_examples: bool = True,
    include_graphs: bool = True
) -> tuple[int, int]:
    """
    Estimate generation time in minutes.
    
    Args:
        material_type: Type of material (arbeidsark, kapittel, etc.)
        num_exercises: Number of exercises to generate.
        include_theory: Whether theory is included.
        include_examples: Whether examples are included.
        include_graphs: Whether graphs are included.
    
    Returns:
        Tuple of (min_minutes, max_minutes).
    """
    estimates = TIME_ESTIMATES.get(material_type, TIME_ESTIMATES["arbeidsark"])
    
    base = estimates["base"]
    exercise_time = estimates["per_exercise"] * num_exercises
    
    total = base + exercise_time
    
    if include_theory:
        total *= estimates["theory_multiplier"]
    if include_examples:
        total *= estimates["examples_multiplier"]
    if include_graphs:
        total *= 1.2  # Graphs add complexity
    
    # Add some variance
    min_time = int(total * 0.7)
    max_time = int(total * 1.3)
    
    return (max(2, min_time), max(3, max_time))


def search_topics(query: str, grade: str = None) -> list[dict]:
    """
    Search for topics matching a query.
    
    Args:
        query: Search query string.
        grade: Optional grade to filter by.
    
    Returns:
        List of matching topics with their grade and category.
    """
    results = []
    query_lower = query.lower()
    
    grades_to_search = [grade] if grade else TOPIC_LIBRARY.keys()
    
    for g in grades_to_search:
        if g not in TOPIC_LIBRARY:
            continue
        
        for category, topics in TOPIC_LIBRARY[g].items():
            for topic in topics:
                if query_lower in topic.lower() or query_lower in category.lower():
                    results.append({
                        "topic": topic,
                        "category": category,
                        "grade": g,
                    })
    
    return results


def get_related_topics(topic: str, grade: str) -> list[str]:
    """
    Get topics related to the given topic within the same grade.
    
    Args:
        topic: The topic to find related topics for.
        grade: The grade level.
    
    Returns:
        List of related topic names.
    """
    topics_by_category = get_topics_for_grade(grade)
    
    # Find which category the topic belongs to
    topic_category = None
    for category, topics in topics_by_category.items():
        if topic in topics:
            topic_category = category
            break
    
    if not topic_category:
        return []
    
    # Return other topics in the same category
    return [t for t in topics_by_category[topic_category] if t != topic]

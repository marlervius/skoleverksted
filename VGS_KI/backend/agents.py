import os
import re
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

if __package__:
    from .tools import WikimediaImageSearchTool
    from .text_pipeline import find_english_leaks
    from .laeringsark_renderer import (
        coerce_structured_lesson, coerce_structured_rapport,
        collect_text_fields, structured_to_plain_text,
    )
else:
    from tools import WikimediaImageSearchTool
    from text_pipeline import find_english_leaks
    from laeringsark_renderer import (
        coerce_structured_lesson, coerce_structured_rapport,
        collect_text_fields, structured_to_plain_text,
    )

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Configure Google Generative AI SDK directly
google_api_key = os.getenv("GOOGLE_API_KEY")
model_name = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash")

# Validate required environment variables at startup
if not google_api_key:
    raise RuntimeError(
        "GOOGLE_API_KEY environment variable is not set. "
        "Please set it in your .env file or environment. "
        "Get your API key from https://aistudio.google.com/apikey"
    )

logger.info(f"Using model: {model_name}")
logger.info(f"API key configured (ending in ...{google_api_key[-4:]})")

# Configure the genai library with API key
genai.configure(api_key=google_api_key)

# Set environment variables for LiteLLM fallback
os.environ["GEMINI_API_KEY"] = google_api_key
os.environ["GOOGLE_API_KEY"] = google_api_key

# Use CrewAI's LLM with explicit lowercase model name
llm = LLM(
    model=f"gemini/{model_name.lower()}",
    api_key=google_api_key,
    temperature=0.7,
)

# Instantiate the Wikimedia image search tool
wikimedia_search_tool = WikimediaImageSearchTool()


# ── Subject classification ────────────────────────────────────────────────────
# Used to tailor prompts (narrative style, level requirements) to the subject
# family instead of applying history-flavoured guidance to every subject.

def _classify_subject(subject: str) -> str:
    """Map a subject name to a broad category for prompt tailoring.

    Returns one of: 'history', 'science', 'math', 'social', 'language',
    'religion', 'pe', 'arts', 'other'.
    """
    s = (subject or "").strip().lower()
    mapping = {
        "historie": "history",
        "naturfag": "science", "biologi": "science", "fysikk": "science",
        "kjemi": "science", "geofag": "science", "teknologi og forskningslære": "science",
        "matematikk": "math", "matte": "math",
        "samfunnsfag": "social", "samfunnskunnskap": "social", "geografi": "social",
        "sosiologi og sosialantropologi": "social", "politikk og menneskerettigheter": "social",
        "sosialkunnskap": "social", "rettslære": "social", "økonomi": "social",
        "norsk": "language", "engelsk": "language", "spansk": "language",
        "tysk": "language", "fransk": "language", "fremmedspråk": "language",
        "religion": "religion", "religion og etikk": "religion", "krle": "religion",
        "kroppsøving": "pe",
        "kunst": "arts", "musikk": "arts", "kunst og håndverk": "arts",
        "design og håndverk": "arts",
    }
    return mapping.get(s, "other")


def _narrative_guidelines_no(category: str) -> str:
    """Subject-appropriate Norwegian narrative writing guidelines."""
    if category == "history":
        return """

    ═══ NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv som de beste populærhistorikerne: Yuval Noah Harari, Simon Schama, Mary Beard.
    Kombiner faglig presisjon med narrativ kraft.

    1. ÅPNINGSKROKER — Hvert avsnitt må starte med noe som vekker nysgjerrighet:
       - Spørsmål: «Hva skjer med et samfunn der halvparten av menneskene plutselig dør?»
       - Konkret scene: «I 1347 la et handelsskip til kai i Messina. Mannskapet var døende.»
       - Paradoks: «Det katolske Frankrike kjempet på protestantenes side – for maktpolitikk veide tyngre enn tro.»
       ALDRI start med «I denne perioden...» eller «X var en...».
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes:
       «**Føydalismen** (et system der makt var knyttet til jord og lojalitetsbånd) dominerte Europa.»
    3. KAUSALKJEDER — Vis HVORFOR ting skjedde. Bruk eksplisitte piler:
       «Krig ble dyrere → kongen trengte faste **skatter** → skatter krevde et **byråkrati** → makten ble **sentralisert**.»
    4. MENNESKELIGE AKTØRER MED MOTIVER — Abstrakte prosesser drives av mennesker med interesser.
    5. KONTRASTPAR — Bruk før/etter-kontraster for å gjøre abstrakte endringer konkrete.
    6. ÉN MODERNE PARALLELL — Inkluder nøyaktig ÉN sammenligning med elevens verden (ikke overdriv).
    7. VARIER SETNINGSRYTME — Korte setninger for effekt, lengre for sammenhenger. Aldri over 30 ord.
    """
    if category == "science":
        return """

    ═══ FAGLIG-NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv som de beste vitenskapsformidlerne: presist, men levende og konkret.

    1. ÅPNINGSKROKER — Start hvert avsnitt med et fenomen, en observasjon eller et spørsmål:
       «Hvorfor er himmelen blå?» «Et glass vann ser stille ut – men molekylene farer av gårde i hundrevis av meter i sekundet.»
       ALDRI start med «X er en...» eller en tørr definisjon.
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes:
       «**Fotosyntese** (prosessen der planter lager kjemisk energi fra lys).»
    3. MEKANISME OG ÅRSAK–VIRKNING — Forklar HVORDAN og HVORFOR, ikke bare HVA. Bruk piler:
       «Mer CO₂ i atmosfæren → mer varmestråling fanges → global temperatur stiger.»
    4. ANALOGIER OG HVERDAGSEKSEMPLER — Knytt minst ÉN abstrakt idé til noe elevene kjenner.
    5. HVORDAN VI VET DET — Vis kort hvordan kunnskapen er bygd (eksperiment, måling, modell).
    6. ÉN RELEVANT ANVENDELSE — Koble til teknologi, helse, miljø eller dagligliv.
    7. VARIER SETNINGSRYTME — Korte setninger for poeng, lengre for sammenhenger. Aldri over 30 ord.
    """
    if category == "math":
        return """

    ═══ FAGLIG-NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv matematikk som meningsfull problemløsning – ikke regler å pugge.

    1. MOTIVASJON FØRST — Start med et problem eller spørsmål begrepet løser:
       «Hvordan kan vi finne høyden på et fjell uten å klatre det?»
       ALDRI start med en definisjon uten kontekst.
    2. FAGBEGREPER OG NOTASJON — Sett ALLE fagbegreper i **bold** ved første bruk og forklar:
       «**Pytagoras' setning** (a² + b² = c² i rettvinklede trekanter).» Forklar symboler i ord.
    3. BYGG INTUISJON FØR FORMALISME — Forklar idéen med ord og bilde før den formelle regelen.
    4. VIST RESONNEMENT — Vis utregning steg for steg med begrunnelse for hvert steg, ikke bare svaret.
    5. GJENNOMREGNET EKSEMPEL — Inkluder minst ÉT konkret eksempel med tall.
    6. ÉN ANVENDELSE — Vis hvor matematikken brukes i virkeligheten (økonomi, teknologi, natur).
    7. VANLIGE FEIL — Påpek minst ÉN typisk misforståelse elevene bør unngå.
    """
    if category == "social":
        return """

    ═══ NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv som en god samfunnsformidler: konkret, analytisk og nær elevens virkelighet.

    1. ÅPNINGSKROKER — Start med en sak, et dilemma eller et talleksempel:
       «Hvorfor blir noen land rike på olje mens andre forblir fattige?»
       ALDRI start med «X er en...».
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes.
    3. ÅRSAK–VIRKNING — Bruk eksplisitte piler og vis sammenhenger mellom samfunnsforhold.
    4. AKTØRER OG INTERESSER — Vis hvilke grupper og aktører som påvirker og påvirkes.
    5. FLERE PERSPEKTIVER — Presenter minst to syn på et omstridt spørsmål, uten å ta parti.
    6. ÉN AKTUELL KOBLING — Knytt til en aktuell hendelse eller elevens hverdag.
    7. VARIER SETNINGSRYTME — Korte setninger for poeng, lengre for sammenhenger. Aldri over 30 ord.
    """
    if category == "religion":
        return """

    ═══ NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv respektfullt og analytisk om livssyn, etikk og religion – beskriv, ikke forkynn.

    1. ÅPNINGSKROKER — Start med et etisk dilemma, en fortelling eller et spørsmål:
       «Kan en handling være rett i én kultur og gal i en annen?»
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes.
    3. INNENFRA OG UTENFRA — Vis både hvordan tilhengere selv forstår noe, og et analytisk utenfraperspektiv.
    4. FLERE PERSPEKTIVER — Presenter ulike livssyn/retninger saklig og likeverdig.
    5. ETISK RESONNEMENT — Vis hvordan ulike etiske teorier ville vurdert et konkret spørsmål.
    6. ÉN KOBLING til elevens egen samtid eller hverdag.
    7. VARIER SETNINGSRYTME — Aldri over 30 ord i én setning.
    """
    if category == "language":  # norsk (engelsk bruker engelsk variant)
        return """

    ═══ NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv engasjerende om språk, tekst og litteratur – og vis, ikke bare fortell.

    1. ÅPNINGSKROKER — Start med et sitat, en tekst eller et spørsmål om språk:
       «Hvorfor husker vi en god åpningssetning i årevis?»
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes
       (f.eks. **metafor**, **sjanger**, **retoriske appellformer**).
    3. VIS MED TEKSTEKSEMPLER — Illustrer hvert virkemiddel med et kort eksempel eller sitat.
    4. FORM SKAPER MENING — Vis hvordan virkemiddel → effekt (hva gjør grepet med leseren?).
    5. KONTEKST — Knytt teksten til tid, kultur og formål.
    6. ÉN KOBLING til elevens egen språkbruk eller medievirkelighet.
    7. VARIER SETNINGSRYTME — Korte setninger for effekt, lengre for sammenhenger. Aldri over 30 ord.
    """
    # General fallback (arts, pe, other)
    return """

    ═══ NARRATIV SKRIVEFORM (OBLIGATORISK) ═══
    Skriv levende og presist, slik at eleven får lyst til å lese videre.

    1. ÅPNINGSKROKER — Start hvert avsnitt med et spørsmål, en konkret scene eller et eksempel.
       ALDRI start med «X er en...».
    2. FAGBEGREPER — Sett ALLE fagbegreper i **bold** ved første bruk og forklar i parentes.
    3. FORKLAR HVORFOR OG HVORDAN — ikke bare hva. Bruk eksplisitte piler ved sammenhenger.
    4. KONKRETE EKSEMPLER OG ANALOGIER — knytt abstrakte idéer til noe elevene kjenner.
    5. FLERE PERSPEKTIVER — der det er relevant, vis ulike måter å se saken på.
    6. ÉN KOBLING til elevens egen verden.
    7. VARIER SETNINGSRYTME — Korte setninger for poeng, lengre for sammenhenger. Aldri over 30 ord.
    """


def _level_guidelines_no(category: str, level: str) -> str:
    """Subject-appropriate Norwegian VG2/VG3 depth requirements."""
    if level == "VG3":
        if category == "history":
            return """

    ═══ VG3-KRAV (OBLIGATORISK) ═══
    Dette er VG3-nivå. Teksten MÅ inneholde et historiografisk/faghistorisk lag:
    1. HISTORIOGRAFISK DEBATT — Inkluder minst ÉT tilfelle der historikere er uenige.
    2. METODISK BEVISSTHET — Vis at historisk kunnskap er fortolket («tolkning», «kildegrunnlag»).
    3. STRUKTURELLE vs. INDIVIDUELLE FORKLARINGER — Presenter begge.
    4. KRITISK AVSTAND — Avslutt minst én seksjon med et åpent spørsmål til eleven.
    """
        if category == "science":
            return """

    ═══ VG3-KRAV (OBLIGATORISK) ═══
    Dette er VG3-nivå. Teksten MÅ gå dypere enn beskrivelse:
    1. MEKANISME PÅ DYBDEN — Forklar de underliggende prosessene, ikke bare resultatet.
    2. MODELLER OG GYLDIGHET — Vis at modeller er forenklinger med gyldighetsområde og begrensninger.
    3. KVANTITATIV SAMMENHENG — Inkluder minst ÉN sammenheng uttrykt med tall, formel eller graf.
    4. USIKKERHET OG METODE — Vis hvordan kunnskapen er etablert, og hvor det fortsatt er usikkerhet.
    """
        if category == "math":
            return """

    ═══ VG3-KRAV (OBLIGATORISK) ═══
    Dette er VG3-nivå. Teksten MÅ vise matematisk modenhet:
    1. BEGRUNNELSE/BEVIS — Vis HVORFOR en regel gjelder, ikke bare hvordan den brukes.
    2. GENERALISERING — Gå fra konkrete eksempler til den generelle sammenhengen.
    3. SAMMENHENGER — Koble temaet til andre matematiske begreper eleven kjenner.
    4. ANVENDELSE OG MODELLERING — Vis hvordan matematikken modellerer et virkelig problem.
    """
        if category in ("social", "religion"):
            return """

    ═══ VG3-KRAV (OBLIGATORISK) ═══
    Dette er VG3-nivå. Teksten MÅ vise analytisk dybde:
    1. TEORI/PERSPEKTIV — Bruk minst ÉN faglig teori eller modell til å analysere temaet.
    2. FLERE FORKLARINGER — Presenter konkurrerende forklaringer og vei dem mot hverandre.
    3. KILDE- OG KRITISK BEVISSTHET — Vis at kunnskap er fortolket og avhengig av perspektiv.
    4. KRITISK AVSTAND — Avslutt minst én seksjon med et åpent, drøftende spørsmål.
    """
        return """

    ═══ VG3-KRAV (OBLIGATORISK) ═══
    Dette er VG3-nivå. Teksten MÅ gå i dybden:
    1. ANALYSE OG BEGRUNNELSE — Forklar HVORFOR, ikke bare HVA.
    2. FLERE PERSPEKTIVER — Presenter og vei ulike syn mot hverandre.
    3. SAMMENHENGER — Koble temaet til bredere faglige sammenhenger.
    4. KRITISK AVSTAND — Avslutt minst én seksjon med et åpent, drøftende spørsmål.
    """
    if level == "VG2":
        if category == "math":
            return """

    ═══ VG2-KRAV (OBLIGATORISK) ═══
    Dette er VG2-nivå. Teksten skal gå dypere enn VG1:
    1. RESONNEMENT — Vis fremgangsmåten steg for steg med begrunnelse, ikke bare svar.
    2. SAMMENHENGER — Koble begrepet til beslektede begreper eleven allerede kjenner.
    3. FLERE EKSEMPLER — Inkluder minst to gjennomregnede eksempler med ulik vanskegrad.
    4. FAGBEGREPER — Bruk og forklar minst 6 fagbegreper/notasjoner presist.
    """
        if category == "science":
            return """

    ═══ VG2-KRAV (OBLIGATORISK) ═══
    Dette er VG2-nivå. Teksten skal gå dypere enn VG1:
    1. ANALYSE — Forklar mekanismen bak fenomenet, ikke bare at det skjer.
    2. SAMMENHENGER — Inkluder minst to eksplisitte årsak→virkning-kjeder (A → B → C).
    3. NYANSERING — Vis minst ÉN sammenheng som er mer kompleks enn den enkle forklaringen.
    4. FAGBEGREPER — Bruk og forklar minst 6-8 fagbegreper presist.
    """
        return """

    ═══ VG2-KRAV (OBLIGATORISK) ═══
    Dette er VG2-nivå. Teksten skal gå dypere enn VG1:
    1. ANALYSE — Ikke bare beskriv hva som skjedde; forklar HVORFOR og HVILKE KONSEKVENSER.
       Inkluder minst to eksplisitte årsak→virkning-kjeder (A → B → C).
    2. SAMMENHENGER — Koble temaet til bredere faglige prosesser utover det umiddelbare.
    3. NYANSERING — Unngå svart/hvitt. Vis minst ÉT tilfelle der virkeligheten er mer kompleks.
    4. FAGBEGREPER — Bruk og forklar minst 6-8 fagbegreper presist.
    """
    return ""


# Agent 1: The VGS Content Creator (with image search capability)
content_creator = Agent(
    role="Expert teacher for Norwegian Upper Secondary School (Videregående skole - VGS)",
    goal="""Write a factual, educational text about a given topic in a specific subject, 
    strictly adapted to the Norwegian VGS curriculum and competence goals (kompetansemål). 
    Every sentence must be grammatically complete. You are strictly forbidden from leaving 
    trailing commas or empty placeholders like 'oppfinnelser som ,'. 
    The text should be informative, accurate, and appropriate for students aged 16-19.
    
    ADDITIONALLY: Find ONE relevant, high-quality image from Wikimedia Commons that 
    illustrates the topic. Use the wikimedia_image_search tool to search for an appropriate image.""",
    backstory="""You are an experienced teacher in the Norwegian Upper Secondary School (VGS). 
    You have deep knowledge of the LK20 (Læreplanverket for Kunnskapsløftet 2020) curriculum 
    and understand how to create engaging content that covers specific competence goals.
    
    STRICT RULES FOR CONTENT GENERATION:
    1. NO PLACEHOLDERS: Never use phrases like 'oppfinnelser som ,' or 'for eksempel .'. If you start an enumeration, you MUST complete it with specific names (e.g., 'Spinning Jenny', 'The Flying Shuttle').
    2. SENTENCE INTEGRITY: Every sentence must have a subject and a finite verb. Avoid fragmented sentences.
    3. SPECIFICITY OVER GENERALITY: Instead of saying 'many factors', name the factors (e.g., 'tilgang på kull, kapital og arbeidskraft').
    4. PROOFREADING SIMULATION: Before finalizing the text, verify that no commas are left trailing and that all technical terms are followed by their intended description.
    5. HEADINGS FORMAT: Use Markdown headings for subheadings with **bold** text. Put each heading on its OWN LINE:
       - Use ### **Heading text** for subheadings (e.g., "### **Skyvefaktorer**")
       - NEVER put headings inline with text (wrong: "Skyvefaktorer: Dette er...")
       - ALWAYS put a blank line after the heading before the paragraph
       - This ensures proper bold formatting in the PDF output

    ═══ FACTUAL INTEGRITY (this overrides the "be specific" rule above) ═══
    Teachers must be able to trust this text. Accuracy ALWAYS outranks impressive-sounding detail.
    When you must choose between a precise-looking detail and being correct, choose correct.
    6. NEVER INVENT FALSE PRECISION: Do not fabricate exact dates, statistics, percentages, named
       studies/reports, or quotations that you are not genuinely confident are correct. A fabricated
       "67 %" or "in 1847" that looks authoritative is far more damaging than an honest approximation.
    7. CALIBRATE TO YOUR CONFIDENCE: When unsure of an exact figure, use an honest hedge that is still
       informative — "rundt 1850" / "in the mid-1800s", "flere hundre tusen" / "several hundred thousand",
       "et stort flertall" / "a large majority". This is NOT the same as being vague: state well-established
       facts confidently and specifically; only soften the genuinely uncertain ones.
    8. NO FABRICATED ATTRIBUTION: Never invent a named person, a specific book/study title, or a direct
       quotation. If you cannot attribute something accurately, describe it generally instead
       (e.g. "samtidige kilder beskriver..." rather than a made-up name and year).
    9. Specificity rule (3 above) means: name facts you ARE sure of. It is NEVER a licence to invent
       plausible-sounding specifics to fill a gap.

    You know how to adapt content for different levels of VGS, from vocational programs (yrkesfag) 
    to academic specialization (studieforberedende).
    
    IMPORTANT: Write in the language specified in the task description. 
    For Norwegian subjects, write in Norwegian (Bokmål).
    For English subjects, write in English.
    
    CRITICAL - IMAGE SEARCH (you MUST do this):
    After writing the text, you MUST use the wikimedia_image_search tool to find a relevant image.
    This is NOT optional. Every lesson MUST have an image.
    
    IMAGE SEARCH STRATEGY:
    1. Use SIMPLE English keywords: 2-4 words maximum. Example: "Industrial Revolution factory"
    2. Do NOT use complex queries. BAD: "diagram of earth's axial tilt showing seasons". GOOD: "Earth axis tilt"
    3. If the first search returns no results, try DIFFERENT simpler keywords
    4. You MUST try at LEAST 2 different searches before giving up
    5. Use the 'Image URL' or 'Thumbnail' URL from the tool's response
    
    SEARCH EXAMPLES:
    - Topic "Den industrielle revolusjonen" → search "Industrial Revolution factory"
    - Topic "Fotosyntese" → search "photosynthesis diagram"
    - Topic "Andre verdenskrig" → search "World War II Europe"
    - Topic "Jordas rotasjon" → search "Earth rotation"
    
    At the VERY END of your output, on its own line, write:
    IMAGE_URL: <paste the URL from the tool here>
    
    Only write IMAGE_URL: none if you tried 2+ searches and found nothing.""",
    tools=[wikimedia_search_tool],
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


# Agent 2: The Pedagogical Developer
pedagogical_developer = Agent(
    role="Curriculum developer and worksheet creator for Upper Secondary School (VGS)",
    goal="""Create a comprehensive worksheet based on an educational text, 
    designed to reinforce learning and check understanding of competence goals for VGS students.
    Ensure that all tasks are complete and pedagogically sound.
    
    IMPORTANT: Start your response DIRECTLY with the worksheet sections (a, b, c). 
    Do NOT repeat or include the original educational text in your response. 
    Do NOT include introductory phrases like "Her er arbeidsarket" or "Here is the worksheet". 
    Focus ONLY on the learning activities.""",
    backstory="""You are a skilled curriculum developer with expertise in creating 
    educational materials for Norwegian Upper Secondary School (VGS). You understand 
    pedagogical principles for teenagers and young adults, and know how to create 
    varied tasks that challenge students at different levels.
    
    STRICT RULES FOR QUESTION QUALITY:
    1. COMPLETE QUESTIONS: Every question MUST have:
       - A clear question text (not just a number)
       - For multiple choice: 3-4 complete answer options
       - Example WRONG: "1. ?" or "a)" 
       - Example CORRECT: "1. Hva var hovedårsaken til...? a) Første alternativ b) Andre alternativ"
    2. NO FRAGMENTS: Never leave a question half-written or without options.
    3. CLARITY: Instructions must be crystal clear.
    4. LANGUAGE CONSISTENCY: If language simplification is requested, apply it to ALL questions
       and instructions - not just the main text. The worksheet language MUST match the 
       complexity level of the main educational text.
    5. BOLD SECTION HEADINGS: All section headings (a, b, c, etc.) MUST be formatted with **bold**.
       Example: **a) Fagbegreper** or **b) Forståelse og analyse**. This ensures proper PDF formatting.
    
    You always structure your worksheets with clear sections that progress from 
    basic understanding to critical thinking and application of knowledge.
    
    IMPORTANT: Write in the language specified in the task description.
    For Norwegian subjects, write in Norwegian (Bokmål).
    For English subjects, write in English.
    
    NOTE: Do NOT include any IMAGE_URL in your output. Focus only on creating the worksheet.""",
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


# Agent 3: The Exercise Creator
# (defined below)

# ── Agent 4: Differensieringsagent ────────────────────────────────────────────
differentiation_agent = Agent(
    role="Expert in differentiated instruction for Norwegian Upper Secondary School",
    goal="""Take a standard educational text and produce two adapted versions:
    1. STØTTE (support) — simplified language, shorter sentences, more scaffolding
    2. FORDYPNING (extension) — deeper analysis, more nuance, critical thinking demands

    Both versions must cover the same factual content as the original.
    STØTTE should be accessible to struggling learners without losing academic substance.
    FORDYPNING should challenge advanced learners with synthesis and evaluation.""",
    backstory="""You are a specialist in differentiated instruction (tilpasset opplæring)
    as required by Norwegian law (opplæringslova §1-3). You know exactly how to adapt
    the same academic content for different learning needs while keeping the curriculum goals intact.

    STØTTE rules:
    - Max 15 words per sentence
    - Active voice only
    - Every key term explained in parentheses again (even if already explained in standard)
    - Add signal words: «Først», «Deretter», «Fordi», «Dette betyr at»
    - Break complex paragraphs into bullet points where helpful
    - 20-30% shorter than original

    FORDYPNING rules:
    - Introduce 2-3 additional nuances or perspectives not in the standard text
    - Include at least one historiographical or methodological reflection
    - Add a critical question at the end: «Noen historikere mener... Men andre hevder...»
    - Reference primary source types that could be used to investigate the topic
    - 20-30% longer than original

    CRITICAL: Return ONLY valid JSON with exactly this structure:
    {"stoette": "...", "fordypning": "..."}
    No explanations, no markdown, just pure JSON.""",
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

# ── Agent 5: Prøveagent ───────────────────────────────────────────────────────
prove_agent = Agent(
    role="Expert exam and assessment designer for Norwegian Upper Secondary School (VGS)",
    goal="""Create complete, fair, and pedagogically sound exams/tests (prøver) for VGS students.
    Tests must have clear point distribution, varied question types, and a complete answer key (fasit).""",
    backstory="""You are an experienced exam designer who has created hundreds of VGS assessments
    aligned with LK20 competency goals and Udir's assessment guidelines (vurderingsforskriften).

    You know that a good VGS exam has three parts:
    - Del A (Flervalg): Tests factual recall (Bloom 1-2). 4-5 questions × 2 points = 8-10p
    - Del B (Kortsvarsoppgaver): Tests understanding and application (Bloom 2-4). 3-4 questions × 5-8p
    - Del C (Langsvarsoppgave): Tests analysis/evaluation/creation (Bloom 4-6). 1-2 questions × 10-15p

    STRICT RULES:
    1. Every multiple-choice question has EXACTLY 4 options (a, b, c, d). Only ONE is correct.
    2. Every question has a point value clearly marked: (2p), (5p), etc.
    3. The answer key lists correct answers with brief justifications.
    4. Total points are stated on the cover page.
    5. Time allocation is shown: typically 90 minutes for a standard test.
    6. Questions progress from easy (Del A) to complex (Del C).
    7. All questions are directly based on the provided educational text.
    8. FACTUAL INTEGRITY: Both questions and the answer key (fasit) must stay faithful to the
       provided text. Do NOT introduce dates, figures or named facts that are not supported by it,
       and never fabricate false precision. A wrong fasit destroys the teacher's trust — when the
       text does not settle a detail, do not invent one in the answer key.

    Output format: Return ONLY valid JSON — no markdown, no explanations.
    CRITICAL: The JSON must have exactly this structure:
    {
      "tittel": "Prøve: [topic]",
      "fag": "[subject]",
      "trinn": "[level]",
      "tid": "90 minutter",
      "total_poeng": [number],
      "del_a": {
        "tittel": "Del A – Flervalgsoppgaver",
        "instruksjon": "Sett ring rundt riktig svar.",
        "poeng_per_sporsmal": 2,
        "sporsmal": [
          {
            "nr": 1,
            "tekst": "...",
            "alternativer": {"a": "...", "b": "...", "c": "...", "d": "..."},
            "riktig": "a"
          }
        ]
      },
      "del_b": {
        "tittel": "Del B – Kortsvarsoppgaver",
        "instruksjon": "Svar med 3-5 setninger.",
        "sporsmal": [
          {"nr": 6, "tekst": "...", "poeng": 6, "fasit": "..."}
        ]
      },
      "del_c": {
        "tittel": "Del C – Langsvarsoppgave",
        "instruksjon": "Skriv et sammenhengende svar.",
        "sporsmal": [
          {"nr": 9, "tekst": "...", "poeng": 15, "fasit": "...", "vurderingskriterier": "..."}
        ]
      }
    }""",
    llm=llm,
    verbose=True,
    allow_delegation=False,
)

# Agent 3: The Exercise Creator
language_exercise_creator = Agent(
    role="Expert in subject-specific tasks and exercises for VGS",
    goal="""Analyze educational texts and create targeted exercises that help 
    VGS students develop both subject knowledge and relevant skills (writing, analysis, calculation).
    All exercises and answer options must be complete and logically consistent.
    For 'fill-in-the-blank' sentences, you MUST ensure that the sentence continues with at least 
    two words after the blank, unless the blank is intentionally at the very end of the sentence. 
    This provides necessary context for the student.""",
    backstory="""You are an expert in creating varied exercises for all subjects in 
    Norwegian Upper Secondary School (VGS).
    
    STRICT RULES:
    1. NO FRAGMENTS: All sentences in exercises must be complete.
    2. CONTEXTUAL BLANKS: Never leave a 'fill-in-the-blank' sentence hanging. Example: instead of '...to build [blank]', write '...to build [blank] and other infrastructure.'
    3. VALID OPTIONS: In multiple choice or matching tasks, every option must have a corresponding value. Never leave an option like 'A. ' or '1. '.
    4. PEDAGOGICAL PRECISION: Ensure that the tasks actually test the intended knowledge.
    
    Your expertise covers:
    - SUBJECT TERMINOLOGY: Identifying and practicing key terms
    - ANALYSIS: Creating tasks that require students to compare, reflect, and conclude
    - PRACTICAL APPLICATION: Creating tasks that relate the theory to real-world or vocational scenarios
    
    QUALITY CONTROL - YOU MUST:
    ✓ ONLY use content and concepts from the educational text provided
    ✓ Choose tasks relevant to the VGS competence goals
    ✓ NOT invent random content unless it relates to the subject matter
    ✓ Read the text carefully and select the most relevant points
    
    IMPORTANT: Respond in the SAME LANGUAGE as the task description.
    If the task is in Norwegian, respond in Norwegian.
    If the task is in English, respond in English.
    
    CRITICAL: You MUST return the answer as a valid JSON object. No explanations, 
    no markdown code blocks, just pure JSON.""",
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


def extract_json_object(text: str) -> dict | None:
    """Best-effort extraction of a single JSON object from agent output.

    Tries, in order: the whole text, a ```json code block, and the widest
    {...} span. Returns None when nothing parses.
    """
    if not text or not text.strip():
        return None
    candidates = [text.strip()]
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if m:
        candidates.append(m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


# ── DEL 3: structured output contract for the writer agent ───────────────────

STRUCTURED_OUTPUT_RULES_NO = """
    ═══ OUTPUTFORMAT (OBLIGATORISK): STRUKTURERT JSON ═══
    Returner fagteksten som ETT gyldig JSON-objekt — IKKE markdown, IKKE løpende tekst:
    {
      "tittel": "Dokumenttittel",
      "ingress": "1-2 setninger som vekker interesse (kan utelates)",
      "seksjoner": [
        {
          "tittel": "Seksjonstittel",
          "avsnitt": ["Første avsnitt ...", "Andre avsnitt ..."],
          "begreper": [
            {"term": "Maktbalanse", "def": "Ingen enkeltstat er sterk nok til å dominere de andre."}
          ],
          "kjeder": [
            {"steg": ["Tysk samling", "Fransk nederlag", "Endret maktbalanse"]}
          ]
        }
      ],
      "verk": ["eventuelle engelske bok-/verktitler du nevner i teksten"]
    }

    REGLER (disse OVERSTYRER tidligere formateringsinstruksjoner):
    - Begrepsdefinisjoner skal IKKE stå i parentes i brødteksten — kun i "begreper"-listen.
      I brødteksten brukes begrepet naturlig; første forekomst kan stå i kursiv: *begrep*.
    - "def" maks 12 ord (margkolonnen er smal).
    - Maks 4 begreper per seksjon.
    - Kausalkjeder (A fører til B fører til C) leveres KUN i "kjeder" — aldri som tekst
      med piler eller backticks i avsnittene.
    - Ingen markdown i feltene (ingen **, ##, `). Eneste unntak: *kursiv* for begreper.
    - ALDRI bruk emoji.
    - Bruk kun vanlig bindestrek (-) og tankestrek (–) — aldri spesialtegn-varianter.
    - [K]-markører beholdes inne i avsnitt-strengene, rett etter punktum.
    - Eventuelt primærkildesitat legges som eget avsnitt som starter med «PRIMÆRKILDE:».
    - ETTER JSON-objektet (utenfor det): IMAGE_URL-linjen som beskrevet.
"""

STRUCTURED_OUTPUT_RULES_EN = """
    ═══ OUTPUT FORMAT (MANDATORY): STRUCTURED JSON ═══
    Return the educational text as ONE valid JSON object — NOT markdown, NOT running text:
    {
      "tittel": "Document title",
      "ingress": "1-2 engaging opening sentences (optional)",
      "seksjoner": [
        {
          "tittel": "Section title",
          "avsnitt": ["First paragraph ...", "Second paragraph ..."],
          "begreper": [
            {"term": "Balance of power", "def": "No single state is strong enough to dominate the others."}
          ],
          "kjeder": [
            {"steg": ["German unification", "French defeat", "Shifted balance of power"]}
          ]
        }
      ],
      "verk": ["any book/work titles you mention in the text"]
    }

    RULES (these OVERRIDE earlier formatting instructions):
    - Term definitions must NOT appear in parentheses in the body text — only in "begreper".
      Use the term naturally in the body; the first occurrence may be italic: *term*.
    - "def" max 12 words (the margin column is narrow).
    - Max 4 terms per section.
    - Causal chains go ONLY in "kjeder" — never as arrow/backtick text in paragraphs.
    - No markdown in the fields (no **, ##, `). Only exception: *italics* for terms.
    - NEVER use emoji.
    - Use only the plain hyphen (-) and en-dash (–) — never special dash variants.
    - Keep [K] markers inside the paragraph strings, right after the full stop.
    - An optional primary-source quote goes in its own paragraph starting with "PRIMARY SOURCE:".
    - AFTER the JSON object (outside it): the IMAGE_URL line as described.
"""


def extract_image_url(text: str) -> tuple[str, str | None]:
    """
    Extract the IMAGE_URL from the agent's output.
    
    Handles multiple formats the agent might use:
    - IMAGE_URL: https://...
    - Image URL: https://...
    - **IMAGE_URL:** https://...
    - IMAGE_URL: <https://...>
    - Standalone Wikimedia URLs at end of text
    
    Args:
        text: The raw output from the content creator agent
        
    Returns:
        Tuple of (cleaned_text, image_url or None)
    """
    url = None
    
    # Pattern 1: Explicit IMAGE_URL marker (most common)
    patterns = [
        r'IMAGE[_\s]*URL\s*:\s*<?(["\']?)(https?://[^\s\n>"\']+)\1>?',
        r'Image\s*URL\s*:\s*<?(["\']?)(https?://[^\s\n>"\']+)\1>?',
        r'Bilde[_\s]*URL\s*:\s*<?(["\']?)(https?://[^\s\n>"\']+)\1>?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            url = match.group(2).strip().rstrip('.')
            break
    
    # Pattern 2: If no explicit marker, look for Wikimedia/Wikipedia image URLs at the end
    if not url:
        wiki_pattern = r'(https?://(?:upload\.wikimedia\.org|commons\.wikimedia\.org)/[^\s\n>"\']+\.(?:jpg|jpeg|png|webp|svg)(?:/[^\s\n>"\']*)?)'
        matches = re.findall(wiki_pattern, text, re.IGNORECASE)
        if matches:
            # Take the last Wikimedia URL (most likely the chosen one)
            url = matches[-1].strip().rstrip('.')
    
    # Clean the text - remove all IMAGE_URL lines and trailing wiki URLs
    cleaned_text = text
    cleaned_text = re.sub(r'\n*\**\s*IMAGE[_\s]*URL\s*:?\s*.*', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\n*\**\s*Image\s*URL\s*:?\s*.*', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\n*\**\s*Bilde[_\s]*URL\s*:?\s*.*', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r'\n*USE THIS URL[^\n]*', '', cleaned_text, flags=re.IGNORECASE)
    cleaned_text = cleaned_text.strip()
    
    # Validate URL
    if url:
        url = url.strip('.,;:!?')
        if url.startswith('http') and ('wikimedia' in url or 'wikipedia' in url):
            logger.info(f"Extracted image URL: {url[:80]}...")
            return cleaned_text, url
        elif url.startswith('http'):
            logger.info(f"Extracted non-wiki image URL: {url[:80]}...")
            return cleaned_text, url

    # Check for "none" indicator
    if re.search(r'IMAGE[_\s]*URL\s*:\s*none', text, re.IGNORECASE):
        logger.info("Agent explicitly reported no image found")
        return cleaned_text, None

    logger.warning("Could not extract image URL from agent output")
    return cleaned_text, None


def extract_language_exercises(text: str) -> dict:
    """
    Extract JSON language exercises from the agent's output.
    
    Args:
        text: The raw output from the language exercise creator agent
        
    Returns:
        dict containing grammar_tasks, vocabulary_tasks, and syntax_tasks
    """
    default_result = {
        "grammar_tasks": [],
        "vocabulary_tasks": [],
        "syntax_tasks": []
    }
    
    if not text:
        return default_result
    
    # Try to find JSON in the response
    # First, try to parse the entire text as JSON
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict):
            return {
                "grammar_tasks": result.get("grammar_tasks", []),
                "vocabulary_tasks": result.get("vocabulary_tasks", []),
                "syntax_tasks": result.get("syntax_tasks", [])
            }
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    json_pattern = r'```(?:json)?\s*(\{[\s\S]*?\})\s*```'
    match = re.search(json_pattern, text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return {
                    "grammar_tasks": result.get("grammar_tasks", []),
                    "vocabulary_tasks": result.get("vocabulary_tasks", []),
                    "syntax_tasks": result.get("syntax_tasks", [])
                }
        except json.JSONDecodeError:
            pass
    
    # Try to find a JSON object anywhere in the text
    brace_pattern = r'\{[\s\S]*"grammar_tasks"[\s\S]*\}'
    match = re.search(brace_pattern, text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return {
                    "grammar_tasks": result.get("grammar_tasks", []),
                    "vocabulary_tasks": result.get("vocabulary_tasks", []),
                    "syntax_tasks": result.get("syntax_tasks", [])
                }
        except json.JSONDecodeError:
            pass
    
    # If all parsing fails, return default
    logger.warning(f"Could not parse language exercises JSON. Raw output (first 200 chars): {text[:200]!r}")
    return default_result


def _rapport_to_plain_text(rapport: dict) -> str:
    """Readable plain-text version of a structured fact report (UI + docx)."""
    status_labels = {
        "dekket": "DEKKET AV KILDEN",
        "strid": "I STRID MED KILDEN",
        "utenfor": "UTENFOR KILDEN",
        "usikker": "BØR PRESISERES",
    }
    lines: list[str] = []
    if rapport.get("konklusjon"):
        lines += [rapport["konklusjon"], ""]
    if rapport.get("punkter"):
        lines.append("FAKTAPÅSTANDER")
        for p in rapport["punkter"]:
            label = status_labels.get(p["status"], p["status"].upper())
            entry = f"[{label}] {p['pastand']}"
            if p.get("kommentar"):
                entry += f" — {p['kommentar']}"
            lines.append(entry)
        lines.append("")
    for key, heading in [("kausalitet", "KAUSALNARRATIV SOM OVERFORENKLER"),
                         ("perspektiver", "UTELATTE PERSPEKTIVER"),
                         ("ikke_dekket", "HVA TEKSTEN IKKE DEKKER"),
                         ("kilder", "KILDER FOR VERIFISERING")]:
        items = rapport.get(key) or []
        if items:
            lines.append(heading)
            lines.extend(f"- {item}" for item in items)
            lines.append("")
    return "\n".join(lines).strip()


def _retry_english_fix(payload, leak_words: list[str]):
    """One deterministic-triggered retry that asks a proofreader to replace
    specific English words with Norwegian (spec 1.3). Returns the corrected
    payload (same type as input: dict for structured JSON, str for plain
    text), or None when the retry failed or broke the contract."""
    is_json = isinstance(payload, dict)
    text = json.dumps(payload, ensure_ascii=False, indent=2) if is_json else str(payload)
    words = ", ".join(f"«{w}»" for w in leak_words)

    fixer = Agent(
        role="Norsk språkvasker",
        goal="Erstatte engelske ord som har sneket seg inn i norsk fagtekst.",
        backstory="""Du er korrekturleser med ett eneste oppdrag: finne angitte engelske
        ord i en norsk tekst og erstatte dem med korrekt norsk i konteksten. Du endrer
        ingenting annet. Hvis et angitt ord faktisk er korrekt norsk i sin sammenheng
        (f.eks. «is» som frossen vann), lar du det stå.""",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    contract = (
        "Teksten er et JSON-objekt: returner NØYAKTIG samme JSON-struktur med kun disse "
        "ordene rettet i tekstfeltene. KUN JSON-objektet i svaret."
        if is_json else
        "Returner KUN den korrigerte teksten — ingen forklaringer."
    )
    task = Task(
        description=f"""I den norske teksten under har disse engelske ordene sneket seg inn:
        {words}

        Erstatt hvert av dem med korrekt norsk i konteksten (f.eks. «these» → «disse»,
        «to» (engelsk prep.) → «til», «with» → «med»). Endre INGENTING annet.
        {contract}

        TEKST:
        ═══════════════════════════════════════════
        {text}
        ═══════════════════════════════════════════""",
        expected_output="Den korrigerte teksten i samme format som input.",
        agent=fixer,
    )
    try:
        Crew(agents=[fixer], tasks=[task], process=Process.sequential, verbose=False).kickoff()
        raw = task.output.raw if task.output else ""
        if not raw.strip():
            return None
        if is_json:
            return coerce_structured_lesson(extract_json_object(raw))
        fixed_text = raw.strip()
        # Sanity: must still be substantially the same document
        if len(fixed_text) < len(text) * 0.6:
            return None
        return fixed_text
    except Exception as e:
        logger.warning(f"English-leak retry failed: {e}")
        return None


def generate_lesson_content(topic: str, subject: str, level: str, language_level: str = None, options: dict[str, bool] = None, description: str = None, source_text: str = None, basis_text: str = None, interest: str = None, progress_callback=None) -> dict:
    """
    Generate complete lesson content using the AI agents.
    
    Args:
        topic: The specific topic to write about (e.g., "Resirkulering")
        subject: The subject area (e.g., "Samfunnsfag", "Naturfag", "Norsk")
        level: VGS level (VG1, VG2, VG3, Yrkesfag)
        language_level: Optional language simplification level (B1, B2) for students with 
                       Norwegian as second language. When set, the academic content 
                       stays at VGS level, but the language is simplified.
        options: Dictionary of modular options (deep_dive, grammar_tasks, etc.)
        description: Optional detailed instructions/requirements from the teacher
    
    Returns:
        dict containing the educational text, worksheet content, language exercises, and optional image URL
    """
    # Set default options if None — must match frontend constants.ts DEFAULT_OPTIONS
    default_options = {
        "deep_dive": False,
        "lang_tekst": False,
        "grammar_tasks": True,
        "vocabulary_tasks": True,
        "comprehension_tasks": True,
        "discussion_tasks": True,
        "teacher_key": False,
        # Advanced modules
        "role_play": False,
        "image_description": False,
        "writing_frame": False,
        "cultural_comparison": False,
        "real_case": False,
        # Quality assurance — both default to True per skill specification
        "faktarapport": True,
        "korrektur": True,
        # Editorial revision pass on the main text before dependent tasks run
        "revision": True,
        "differensiering": False,
        # Adaptation axes
        "reading_friendly": False,
    }
    if options:
        default_options.update(options)
    options = default_options

    # Determine output language based on subject (needed early for language focus)
    is_english_subject = subject.lower() == "engelsk"
    is_history_subject = subject.lower() == "historie"
    subject_category = _classify_subject(subject)
    
    # Build language simplification instructions if language_level is set
    # This is for students with Norwegian as a second language
    language_simplification = ""
    language_simplification_worksheet = ""
    
    if language_level and language_level in ["B1", "B2"]:
        if language_level == "B1":
            if is_english_subject:
                language_simplification = """
    
    🌍 LANGUAGE ADAPTATION FOR MULTILINGUAL STUDENTS (B1 level):
    The academic content MUST remain at upper secondary level, but the LANGUAGE should be simplified.
    
    ═══ SENTENCE STRUCTURE ═══
    ✓ Maximum 15-20 words per sentence
    ✓ One main idea per sentence
    ✓ Subject-verb-object order (avoid inversions)
    ✓ Active voice: "The steam engine powered factories" NOT "Factories were powered by the steam engine"
    
    ═══ VOCABULARY ═══
    ✓ Use high-frequency words when possible
    ✓ ALWAYS explain subject-specific terms in parentheses at first use:
      - "urbanization (when people move from villages to cities)"
      - "capitalism (an economic system where individuals own businesses)"
    ✓ Avoid idioms and cultural expressions that may confuse
    ✓ Repeat key terms - do NOT replace them with pronouns like "it", "this", "they"
    
    ═══ TEXT STRUCTURE ═══
    ✓ Short paragraphs (3-4 sentences maximum)
    ✓ Clear topic sentence at the start of each paragraph
    ✓ Use signal words: "First,", "Second,", "However,", "Because of this,", "In conclusion,"
    ✓ Use bullet points or numbered lists for complex information
    
    ═══ EXAMPLES ═══
    BEFORE (too complex): "The multifaceted ramifications of industrialization precipitated unprecedented demographic shifts."
    AFTER (B1 adapted): "The Industrial Revolution changed society in many ways. One big change was urbanization (when people move from villages to cities). Many people left farms to work in factories."
    
    ⚠️ CRITICAL: The FACTS and ACADEMIC DEPTH must stay at VGS level. Only the LANGUAGE is simplified."""
                language_simplification_worksheet = """
    
    🌍 WORKSHEET ADAPTATION FOR B1 LEARNERS - CRITICAL:
    ═══ QUESTION DESIGN ═══
    - One question = one task (avoid multi-part questions)
    - Use simple question words: "What", "Why", "How" 
    - Provide clear examples of expected answer format
    - For multiple choice: keep all options similar in length and structure
    - Maximum 15 words per question
    
    ═══ INSTRUCTIONS ═══
    - Start with action verbs: "Write...", "Choose...", "Explain..."
    - Explain difficult words in parentheses
    - Use numbered steps for complex tasks
    
    ═══ SUPPORT ═══
    - Include sentence starters for open questions: "The main cause was... because..."
    - Provide word banks for fill-in exercises when helpful
    
    ⚠️ CRITICAL: The worksheet questions MUST be as simple as the main text.
    If the main text uses B1 language, the questions MUST also use B1 language.
    Do NOT write complex questions for a simplified text!"""
            else:
                language_simplification = """
    
    🌍 SPRÅKTILPASNING FOR FLERSPRÅKLIGE ELEVER (B1-nivå):
    Det faglige innholdet skal være på VGS-nivå, men SPRÅKET skal forenkles.
    
    ═══ SETNINGSSTRUKTUR ═══
    ✓ Maks 15-20 ord per setning
    ✓ Én hovedidé per setning
    ✓ Bruk rett ordstilling (subjekt-verbal-objekt), unngå inversjon
    ✓ Aktiv form: "Dampmaskinen drev fabrikkene" IKKE "Fabrikkene ble drevet av dampmaskinen"
    
    ═══ ORDVALG ═══
    ✓ Bruk vanlige, høyfrekvente ord når mulig
    ✓ ALLTID forklar fagbegreper i parentes ved første bruk:
      - "urbanisering (at folk flytter fra landsbygda til byer)"
      - "kapitalisme (et økonomisk system der privatpersoner eier bedrifter)"
    ✓ Unngå idiomer og kulturspesifikke uttrykk som kan forvirre
    ✓ Gjenta nøkkelord - IKKE erstatt dem med "det", "dette", "de"
    
    ═══ TEKSTSTRUKTUR ═══
    ✓ Korte avsnitt (maks 3-4 setninger)
    ✓ Tydelig temasetning først i hvert avsnitt
    ✓ Bruk signalord: "For det første,", "Deretter,", "Men,", "Derfor,", "Til slutt,"
    ✓ Bruk punktlister eller nummererte lister for kompleks informasjon
    
    ═══ EKSEMPEL ═══
    FØR (for komplekst): "De mangesidige konsekvensene av industrialiseringen forårsaket en enestående demografisk transformasjon."
    ETTER (B1-tilpasset): "Den industrielle revolusjonen endret samfunnet på mange måter. En stor endring var urbanisering (at folk flyttet fra landsbygda til byer). Mange forlot gårdene for å jobbe i fabrikker."
    
    ⚠️ VIKTIG: FAKTA og FAGLIG DYBDE skal være på VGS-nivå. Kun SPRÅKET forenkles."""
                language_simplification_worksheet = """
    
    🌍 ARBEIDSARK-TILPASNING FOR B1-ELEVER - KRITISK:
    ═══ SPØRSMÅLSDESIGN ═══
    - Ett spørsmål = én oppgave (unngå flerdelte spørsmål)
    - Bruk enkle spørreord: "Hva", "Hvorfor", "Hvordan"
    - Gi tydelige eksempler på forventet svarformat
    - For flervalg: hold alle alternativene like lange og med lik struktur
    - Maks 15 ord per spørsmål
    
    ═══ INSTRUKSJONER ═══
    - Start med handlingsverb: "Skriv...", "Velg...", "Forklar..."
    - Forklar vanskelige ord i parentes
    - Bruk nummererte steg for komplekse oppgaver
    
    ═══ STØTTE ═══
    - Inkluder setningsstartere for åpne spørsmål: "Hovedårsaken var... fordi..."
    - Gi ordbanker for fyll-inn-oppgaver når det er nyttig
    
    ⚠️ KRITISK: Arbeidsark-spørsmålene MÅ være like enkle som hovedteksten.
    Hvis hovedteksten bruker B1-språk, MÅ spørsmålene også bruke B1-språk.
    IKKE skriv komplekse spørsmål for en forenklet tekst!"""
        
        elif language_level == "B2":
            if is_english_subject:
                language_simplification = """
    
    🌍 LANGUAGE ADAPTATION FOR MULTILINGUAL STUDENTS (B2 level):
    The academic content MUST remain at upper secondary level. The language should be clear but can include more complexity than B1.
    
    ═══ SENTENCE STRUCTURE ═══
    ✓ Sentences can be longer (up to 25 words), but keep structure clear
    ✓ Can use some subordinate clauses, but avoid nesting multiple clauses
    ✓ Mix simple and complex sentences for natural flow
    ✓ Passive voice is acceptable when appropriate for academic register
    
    ═══ VOCABULARY ═══
    ✓ Subject-specific terminology should be explained briefly at first use:
      - "industrialization (the shift from farming to factory-based production)"
    ✓ Can use more varied vocabulary, but avoid archaic or highly literary words
    ✓ Avoid idioms and expressions that require cultural knowledge
    ✓ Key terms can be referenced with pronouns after being clearly established
    
    ═══ TEXT STRUCTURE ═══
    ✓ Paragraphs can be slightly longer (4-5 sentences)
    ✓ Use transition words to show logical connections
    ✓ Can include more nuanced argumentation
    ✓ Cause-effect relationships should be explicitly stated
    
    ⚠️ CRITICAL: Full VGS academic depth. Language is accessible but not overly simplified."""
                language_simplification_worksheet = """
    
    🌍 WORKSHEET ADAPTATION FOR B2 LEARNERS:
    - Questions can be more complex, but remain clear
    - Explain specialized terminology at first use
    - Can include analysis and comparison tasks
    - Provide sentence starters for longer written responses"""
            else:
                language_simplification = """
    
    🌍 SPRÅKTILPASNING FOR FLERSPRÅKLIGE ELEVER (B2-nivå):
    Det faglige innholdet skal være på VGS-nivå. Språket skal være tydelig, men kan inkludere mer kompleksitet enn B1.
    
    ═══ SETNINGSSTRUKTUR ═══
    ✓ Setninger kan være lengre (opptil 25 ord), men hold strukturen klar
    ✓ Kan bruke noen leddsetninger, men unngå å nøste flere inni hverandre
    ✓ Bland enkle og komplekse setninger for naturlig flyt
    ✓ Passiv form er akseptabelt når det passer akademisk stil
    
    ═══ ORDVALG ═══
    ✓ Fagbegreper bør forklares kort ved første bruk:
      - "industrialisering (overgangen fra jordbruk til fabrikkbasert produksjon)"
    ✓ Kan bruke mer variert ordforråd, men unngå gammeldagse eller svært litterære ord
    ✓ Unngå idiomer og uttrykk som krever kulturell forkunnskap
    ✓ Nøkkelord kan refereres med pronomen etter at de er tydelig etablert
    
    ═══ TEKSTSTRUKTUR ═══
    ✓ Avsnitt kan være litt lengre (4-5 setninger)
    ✓ Bruk overgangsord for å vise logiske sammenhenger
    ✓ Kan inkludere mer nyansert argumentasjon
    ✓ Årsak-virkning-sammenhenger bør uttrykkes eksplisitt
    
    ⚠️ VIKTIG: Full VGS faglig dybde. Språket er tilgjengelig, men ikke overforenklet."""
                language_simplification_worksheet = """
    
    🌍 ARBEIDSARK-TILPASNING FOR B2-ELEVER:
    - Spørsmål kan være mer komplekse, men fortsatt tydelige
    - Forklar fagterminologi ved første bruk
    - Kan inkludere analyse- og sammenligningsoppgaver
    - Gi setningsstartere for lengre skriftlige svar"""
    
    # Determine language exercise focus based on level and subject
    language_focus = ""
    language_focus_norwegian = ""
    language_focus_english = ""
    
    if options["grammar_tasks"] or options["vocabulary_tasks"]:
        # Norwegian VGS focus
        language_focus_norwegian = """
        FOKUS FOR VGS (videregående skole):
        
        1. FAGBEGREPER (Begrepsforståelse) - type: "begreps_sjekk":
           - Finn sentrale fagbegreper i teksten
           - Lag oppgaver der eleven må forklare eller koble begreper til definisjoner
        
        2. ANALYSE OG REFLEKSJON:
           - Lag oppgaver som krever at eleven bruker informasjonen i teksten til å drøfte en problemstilling
        
        3. FAGLIG FORMULERING - type: "faglig_skriving":
           - Oppgaver som trener eleven i å skrive presist om faget
        """
        language_focus_english = """
        FOCUS FOR VGS (Upper Secondary School):
        
        1. SUBJECT TERMINOLOGY - type: "terminology_check":
           - Identify key subject-specific terms in the text
           - Create tasks where students explain or match terms to definitions
        
        2. ANALYSIS AND REFLECTION:
           - Create tasks that require students to use information from the text to discuss an issue
        
        3. ACADEMIC WRITING - type: "academic_writing":
           - Tasks that train students to write precisely about the subject
        """
        
        language_focus = language_focus_english if is_english_subject else language_focus_norwegian
    
    # Task 1: Create the educational text AND find an image
    output_language = "English" if is_english_subject else "Norwegian (Bokmål)"
    output_language_short = "engelsk" if is_english_subject else "norsk (bokmål)"
    
    if options.get("lang_tekst", False):
        word_count = "1500-2000 words with thorough coverage of all aspects, historical context, causal chains, multiple perspectives, and in-depth analysis" if is_english_subject else "1500-2000 ord med grundig dekning av alle aspekter, historisk kontekst, kausalkjeder, flere perspektiver og dybdeanalyse"
    elif options.get("deep_dive", False):
        word_count = "about 1000 words with extra facts, analysis and details" if is_english_subject else "ca. 1000 ord med ekstra fakta, dybdeinformasjon, analyse og detaljer"
    else:
        word_count = "400-600 words" if is_english_subject else "400-600 ord"

    # Build teacher description block if provided
    teacher_instructions_en = ""
    teacher_instructions_no = ""
    if description and description.strip():
        teacher_instructions_en = f"""

    ═══════════════════════════════════════════════════════════
    📋 DETAILED TEACHER INSTRUCTIONS (HIGH PRIORITY - follow carefully):
    {description.strip()}
    ═══════════════════════════════════════════════════════════
    The above instructions override general defaults. Adapt the text specifically to these requirements."""
        teacher_instructions_no = f"""

    ═══════════════════════════════════════════════════════════
    📋 DETALJERTE LÆRERBESKRIVELSE (HØY PRIORITET - følg nøye):
    {description.strip()}
    ═══════════════════════════════════════════════════════════
    Instruksjonene over overstyrer generelle standarder. Tilpass teksten spesifikt til disse kravene."""

    # Build source text block if provided (for fact-grounding)
    source_text_en = ""
    source_text_no = ""
    if source_text and source_text.strip():
        source_text_en = f"""

    ═══════════════════════════════════════════════════════════
    📖 SOURCE MATERIAL FOR FACT-GROUNDING (USE AS PRIMARY BASIS):
    The teacher has provided the following source material. Base the educational text primarily
    on this source. Stay close to the facts, dates, names and claims in the source.
    Add pedagogical structure, narrative power, and term explanations — but do NOT invent
    facts that contradict or go beyond this source without clear pedagogical reason.

    INLINE CITATION (important): After a sentence whose specific facts (dates, numbers, names,
    claims) come directly from the source material below, append the marker [K] immediately after
    the full stop. Use it on the KEY factual claims — not on every sentence, and not on your own
    pedagogical framing or general background. This lets the teacher instantly see which statements
    can be checked against their source.
    ---
    {source_text.strip()[:4000]}
    ---
    ═══════════════════════════════════════════════════════════"""
        source_text_no = f"""

    ═══════════════════════════════════════════════════════════
    📖 KILDEMATERIALE FOR FAKTAFORANKRING (BRUK SOM PRIMÆRGRUNNLAG):
    Læreren har lastet opp følgende kildemateriale. Basér fagteksten primært på denne kilden.
    Hold deg nær faktaene, årstallene, navnene og påstandene i kilden.
    Legg til pedagogisk struktur, narrativ kraft og begrepsforklaringer — men IKKE finn opp
    fakta som motsier eller går langt utover kilden uten klar pedagogisk grunn.

    INLINE-SITERING (viktig): Etter en setning der de spesifikke faktaene (årstall, tall, navn,
    påstander) kommer direkte fra kildematerialet under, skal du sette inn markøren [K] rett etter
    punktum. Bruk den på de SENTRALE faktapåstandene — ikke på hver setning, og ikke på din egen
    pedagogiske innramming eller generelle bakgrunn. Slik ser læreren umiddelbart hvilke utsagn som
    kan kontrolleres mot kilden.
    ---
    {source_text.strip()[:4000]}
    ---
    ═══════════════════════════════════════════════════════════"""

    # ── Level-specific guidelines (subject-aware) ────────────────────────────
    level_guidelines_no = _level_guidelines_no(subject_category, level)
    # English subject is a language subject — use language-appropriate depth,
    # not the history-flavoured historiography requirements.
    level_guidelines_en = ""
    if level == "VG3":
        level_guidelines_en = """

    ═══ VG3 REQUIREMENTS (MANDATORY) ═══
    This is VG3 level. The text MUST show analytical depth:
    1. CLOSE ANALYSIS — Analyse texts/sources, showing how form and language create meaning.
    2. MULTIPLE PERSPECTIVES — Present and weigh more than one interpretation or viewpoint.
    3. CONTEXT & CRITICAL AWARENESS — Connect the topic to cultural, social and historical context.
    4. CRITICAL DISTANCE — End at least one section with an open, reflective question.
    """
    elif level == "VG2":
        level_guidelines_en = """

    ═══ VG2 REQUIREMENTS (MANDATORY) ═══
    This is VG2 level. The text should go deeper than VG1:
    1. ANALYSIS — Don't just describe; explain WHY and with WHAT EFFECT (use cause→effect reasoning).
    2. CONNECTIONS — Link the topic to broader cultural and social processes.
    3. NUANCE — Avoid black/white. Present at least ONE case where reality is more complex.
    4. TERMINOLOGY — Use and explain at least 6-8 subject-specific terms.
    """

    # ── Primary source for history ────────────────────────────────────────────
    primary_source_no = ""
    primary_source_en = ""
    if is_history_subject:
        primary_source_no = """

    ═══ PRIMÆRKILDE (for historiefaget) ═══
    Inkluder ETT primærkildeeksempel — men KUN hvis du kan gjengi en EKTE, VERIFISERBAR kilde
    nøyaktig (et velkjent, dokumentert sitat du er trygg på ordlyden av).
    Plasser det naturlig etter det mest relevante avsnittet.

    ⛔ ABSOLUTT FORBUDT: Dikt ALDRI opp et sitat, og skriv ALDRI «autentisk-klingende» tekst
    i hermetegn. Et oppdiktet kildesitat ødelegger lærerens tillit til hele dokumentet.
    Det er alltid bedre å beskrive kildetypen enn å fabrikkere et sitat.

    HVIS du er trygg på et eksakt, ekte sitat — legg det som eget avsnitt i denne formen:

    PRIMÆRKILDE: Kildetype, opphavsperson og år — f.eks. «Utdrag fra Erklæringen om
    menneskets rettigheter, 1789». «Det eksakte, autentiske sitatet — kun ord du faktisk
    vet stammer fra kilden.»

    HVIS du IKKE er trygg på et eksakt sitat — beskriv kildetypen i stedet (UTEN hermetegn),
    som eget avsnitt:

    OM KILDENE: Fra denne perioden finnes kildetyper som brev, dagbøker, offentlige
    erklæringer og avisartikler som typisk belyser sentrale poenger. Autentiske eksempler
    kan finnes hos f.eks. Nasjonalbiblioteket.

    KRAV:
    - Ved ekte sitat: oppgi alltid hvem, når og i hvilken situasjon.
    - Ved tvil: velg beskrivelsen. Aldri presenter konstruert tekst som et autentisk sitat.
    """
        primary_source_en = """

    ═══ PRIMARY SOURCE (for History) ═══
    Include ONE primary source example — but ONLY if you can reproduce a REAL, VERIFIABLE source
    accurately (a well-known, documented quotation whose wording you are confident about).
    Place it naturally after the most relevant paragraph.

    ⛔ STRICTLY FORBIDDEN: NEVER invent a quotation, and NEVER write "authentic-sounding" text
    inside quotation marks. A fabricated source quote destroys the teacher's trust in the whole document.
    It is always better to describe the source type than to fabricate a quote.

    IF you are confident about an exact, real quotation — add it as its own paragraph in this form:

    PRIMARY SOURCE: Source type, author and year — e.g. «Extract from the Declaration of
    the Rights of Man, 1789». «The exact, authentic quotation — only words you actually
    know come from the source.»

    IF you are NOT confident about an exact quotation — describe the source type instead
    (NO quotation marks), as its own paragraph:

    ABOUT THE SOURCES: From this period there exist source types such as letters, diaries,
    official declarations and newspaper articles that typically illuminate the central
    points. Authentic examples can be found in the relevant archives.

    REQUIREMENTS:
    - For a real quote: always state who, when, and in what situation.
    - When in doubt: choose the description. Never present constructed text as an authentic quotation.
    """

    # ── Narrative writing guidelines (subject-aware) ──────────────────────────
    narrative_guidelines_no = _narrative_guidelines_no(subject_category)
    # English subject = language subject; use a language-oriented narrative style.
    narrative_guidelines_en = """

    ═══ NARRATIVE WRITING GUIDELINES (MANDATORY) ═══
    Write engagingly about language, texts and culture — and show, don't just tell.

    1. OPENING HOOKS — Every section must start with something that creates curiosity:
       a question, a quotation, or a concrete scene. NEVER start with "X is a..." or "In this text...".
    2. KEY TERMS — Bold ALL subject-specific terms at first use and explain in parentheses immediately
       (e.g. **metaphor**, **genre**, **rhetorical appeals**). Then use the term freely.
    3. SHOW WITH TEXT EXAMPLES — Illustrate each concept or device with a short example or quotation.
    4. FORM CREATES MEANING — Show how a device → its effect (what does it do to the reader?).
    5. CONTEXT — Connect texts to their time, culture and purpose.
    6. ONE CONNECTION — Relate to the students' own language use or media reality (use exactly once).
    7. VARY SENTENCE RHYTHM — Short sentences for effect, longer ones to explain connections. Never exceed 30 words.
    """

    # ── Adaptation axes: interest-based personalisation + reading-friendly mode ──
    # These adapt HOW the text speaks to the student, never the facts themselves.
    interest_block_no = ""
    interest_block_en = ""
    if interest and interest.strip():
        interest_clean = interest.strip()[:200]
        interest_block_no = f"""

    ═══ INTERESSEBASERT TILPASNING ═══
    Eleven(e) er interessert i: {interest_clean}.
    Bruk DETTE til å skape gjenkjennelse: velg eksempler, analogier og innganger som knytter
    fagstoffet til disse interessene (f.eks. en analogi hentet fra elevens interessefelt for å
    forklare et fagbegrep). Vev det inn naturlig 2-4 steder — ikke påklistret, og ALDRI på
    bekostning av faglig presisjon. Faktaene og det faglige nivået skal være helt uendret;
    kun eksemplene og inngangene tilpasses."""
        interest_block_en = f"""

    ═══ INTEREST-BASED PERSONALISATION ═══
    The student(s) are interested in: {interest_clean}.
    Use THIS to create relevance: choose examples, analogies and entry points that connect the
    material to these interests (e.g. an analogy drawn from the student's interest to explain a
    concept). Weave it in naturally in 2-4 places — never forced, and NEVER at the expense of
    academic accuracy. The facts and academic level stay exactly the same; only the examples and
    entry points are adapted."""

    reading_block_no = ""
    reading_block_en = ""
    if options.get("reading_friendly", False):
        reading_block_no = """

    ═══ LESEVENNLIG MODUS (for elever med lese-/skrivevansker) ═══
    Behold VGS-faglig nivå, men gjør teksten lettere å avkode:
    ✓ Korte avsnitt (3-4 setninger), god luft mellom avsnitt.
    ✓ Korte til middels setninger — én hovedidé per setning, unngå lange innskutte bisetninger.
    ✓ Konkret, tydelig språk; unngå unødvendig lange/sjeldne ord når et enklere finnes.
    ✓ Tydelig struktur med deloverskrifter og punktlister der det hjelper lesbarheten.
    ✓ Forklar fagbegreper kort ved første bruk.
    Dette er IKKE språkforenkling til andrespråksnivå — faginnholdet er fullverdig VGS, kun
    presentasjonen gjøres mer lesbar."""
        reading_block_en = """

    ═══ READING-FRIENDLY MODE (for students with reading/writing difficulties) ═══
    Keep full VGS academic level, but make the text easier to decode:
    ✓ Short paragraphs (3-4 sentences) with clear spacing between them.
    ✓ Short to medium sentences — one main idea each, avoid long embedded clauses.
    ✓ Concrete, clear language; avoid unnecessarily long/rare words when a simpler one exists.
    ✓ Clear structure with subheadings and bullet lists where they aid readability.
    ✓ Briefly explain subject terms at first use.
    This is NOT second-language simplification — the academic content is full VGS level, only the
    presentation is made more readable."""

    if is_english_subject:
        create_text_task = Task(
            description=f"""Write an educational text about the topic "{topic}" for the subject "English" in Upper Secondary School (VGS).
            {teacher_instructions_en}
            {source_text_en}
            {interest_block_en}
            {reading_block_en}

            Requirements:
            - The text MUST be written in English
            - Length: {word_count}
            - The text should be factual, informative, and cover relevant competence goals (kompetansemål) from the LK20 curriculum
            - Use academic language appropriate for VGS students (16-19 years old)
            - Divide the text into clear sections with subheadings
            {language_simplification}
            {level_guidelines_en}
            {primary_source_en}
            {narrative_guidelines_en}
            {STRUCTURED_OUTPUT_RULES_EN}

            MANDATORY - IMAGE SEARCH (do NOT skip this):
            After writing the text, use the wikimedia_image_search tool to find one relevant image.

            Search strategy:
            - Use 2-4 simple English words: e.g., "{topic} photo" or "{topic} illustration"
            - If first search fails, try simpler/different keywords
            - You MUST try at least 2 searches before giving up
            - Use the URL from the tool's response (prefer the Thumbnail URL)

            At the END of your response, on its own line, write:
            IMAGE_URL: <the URL here>

            Only write IMAGE_URL: none after trying 2+ searches.""",
            expected_output=f"""One valid JSON object (tittel/ingress/seksjoner/begreper/kjeder/verk)
            containing a well-written educational text in English about {topic} for VGS,
            followed by IMAGE_URL: <url> on the last line after the JSON.""",
            agent=content_creator,
        )
    else:
        create_text_task = Task(
            description=f"""Skriv en pedagogisk tekst om temaet "{topic}" innenfor faget "{subject}" for videregående skole (VGS).
            {teacher_instructions_no}
            {source_text_no}
            {interest_block_no}
            {reading_block_no}

            Krav til teksten:
            - Teksten skal være på norsk (bokmål)
            - Lengde: {word_count}
            - Teksten skal være faktabasert, informativ og dekke relevante kompetansemål fra LK20-læreplanen
            - Bruk et fagspråk som er passende for VGS-elever (16-19 år)
            - Del teksten inn i tydelige avsnitt med deloverskrifter
            {language_simplification}
            {level_guidelines_no}
            {primary_source_no}
            {narrative_guidelines_no}
            {STRUCTURED_OUTPUT_RULES_NO}

            OBLIGATORISK - BILDESØK (IKKE hopp over dette):
            Etter at du har skrevet teksten, BRUK wikimedia_image_search verktøyet for å finne ett relevant bilde.

            Søkestrategi:
            - Bruk 2-4 enkle engelske ord: f.eks. "{topic} photo" eller "{topic} illustration"
            - Hvis første søk feiler, prøv enklere/andre nøkkelord
            - Du MÅ prøve minst 2 søk før du gir opp
            - Bruk URL-en fra verktøyets svar (foretrekk Thumbnail-URL-en)

            På SLUTTEN av svaret ditt, på en egen linje, skriv:
            IMAGE_URL: <URL-en her>

            Skriv kun IMAGE_URL: none etter å ha prøvd 2+ søk.""",
            expected_output=f"""Ett gyldig JSON-objekt (tittel/ingress/seksjoner/begreper/kjeder/verk)
            med en velskrevet, pedagogisk fagtekst på norsk om {topic} for VGS,
            etterfulgt av IMAGE_URL: <url> på siste linje etter JSON-en.""",
            agent=content_creator,
        )
    
    tasks = [create_text_task]
    agents = [content_creator]

    # Task 2: Create the worksheet
    has_basic_tasks = options["comprehension_tasks"] or options["discussion_tasks"] or options["vocabulary_tasks"]
    has_advanced_tasks = options["role_play"] or options["image_description"] or options["writing_frame"] or options["cultural_comparison"] or options["real_case"]
    
    if has_basic_tasks or has_advanced_tasks:
        sections = []
        section_letter = ord('a')
        
        if is_english_subject:
            # LEARNING GOALS section (always first)
            sections.append(f"""{chr(section_letter)}) LEARNING GOALS
                Write 2-4 concrete learning goals that the student should achieve after completing this worksheet.
                Start with: "After this lesson, you should be able to:"
                Use action verbs from Bloom's taxonomy:
                - Level 1-2: "explain", "describe", "identify"
                - Level 3-4: "apply", "compare", "analyze"
                - Level 5-6: "evaluate", "discuss", "create"
                Format: numbered list, e.g. "1. Explain what urbanization means and its causes"
                """)
            section_letter += 1
            
            # PRE-READING section (always second)
            sections.append(f"""{chr(section_letter)}) BEFORE YOU READ (Prior Knowledge Activation)
                Create 2-3 short questions or prompts that activate the student's prior knowledge about the topic.
                These should be quick, low-threshold tasks that everyone can answer. Examples:
                - "What do you already know about X? Write down 3 things."
                - "Look at the title. What do you think this text is about?"
                - "Have you heard about X before? Where?"
                Label this section clearly: "Before you read"
                """)
            section_letter += 1
            
            # English worksheet sections
            if options["vocabulary_tasks"]:
                sections.append(f"""{chr(section_letter)}) SUBJECT TERMINOLOGY
                - Select 5-7 key terms from the text
                - Provide a clear explanation for each term
                - Format: "Term: explanation" """)
                section_letter += 1
            
            if options["comprehension_tasks"]:
                sections.append(f"""{chr(section_letter)}) COMPREHENSION AND ANALYSIS (Bloom's Taxonomy progression)
                Create 4-5 complete questions that follow Bloom's Taxonomy from low to high:
                
                QUESTION 1 (REMEMBER ★): A factual recall question. "What is / Name / List..."
                QUESTION 2 (UNDERSTAND ★): A comprehension question. "Explain in your own words / Describe..."
                QUESTION 3 (APPLY ★★): An application question. "Use the concept X to describe / Give an example of..."
                QUESTION 4 (ANALYZE ★★★): An analysis question. "Compare X and Y / What are the differences between..."
                QUESTION 5 (EVALUATE ★★★): An evaluation/creation question. "Discuss whether... / What would happen if..."
                
                DIFFICULTY STARS - MANDATORY:
                - Mark each question with ★ (basic - all students), ★★ (intermediate), or ★★★ (advanced)
                - Put the stars AFTER the question number: "1. ★ What is...?"
                
                For multiple choice: include 3 complete options (a, b, c) with full text.
                Mark the correct answer with * at the end of the option.""")
                section_letter += 1
                
            if options["discussion_tasks"]:
                if level == "VG3":
                    sections.append(f"""{chr(section_letter)}) DISCUSSION AND REFLECTION ★★★ (VG3 scaffolded)
                Create 2 discussion questions. Each question MUST have four parts:

                1. THE QUESTION: An open, challenging question about the topic (Bloom 5-6)
                2. CONCEPTUAL TOOLKIT: "Useful concepts: [list 4-6 key terms the student needs to answer]"
                3. STRUCTURE GUIDE: "How to structure your answer:
                   → Introduction: State your position
                   → Argument 1: [hint towards a relevant perspective]
                   → Argument 2 / Counter-argument: [hint towards the opposing view]
                   → Conclusion: Summarise and nuance"
                4. SENTENCE STARTER: "You could begin with: '[a concrete sentence starter to help the student]'"

                Example format:
                «Discuss whether [X] was an inevitable consequence of [Y], or whether individual choices were decisive.
                Useful concepts: structural explanation, agency, historical determinism, causality, counterfactual.
                How to structure: → Intro: take a position → Arg 1: structural factors → Arg 2: individual choices → Conclusion: nuance.
                You could begin with: "The question of [X] can be approached from two perspectives: the structural and the individual..."»""")
                else:
                    sections.append(f"""{chr(section_letter)}) DISCUSSION AND REFLECTION ★★★
                - Create 2 open-ended questions that invite critical thinking
                - Questions should connect the topic to broader societal or vocational contexts
                - For each question: include 2-3 useful subject terms the student will need
                - Mark these as ★★★ (advanced level)""")
                section_letter += 1
            
            # Advanced modules in English
            if options["role_play"]:
                sections.append(f"""{chr(section_letter)}) CASE STUDY / ROLE PLAY
                - Create a short scenario or dialogue situation
                - The situation should relate to the topic "{topic}" in a professional or academic context
                - Write 4-6 lines total or describe the task for the students""")
                section_letter += 1
            
            if options["image_description"]:
                sections.append(f"""{chr(section_letter)}) VISUAL ANALYSIS
                - Create 3-4 questions for analyzing the image
                - Questions should help students connect the visual elements to the subject matter""")
                section_letter += 1
            
            if options["writing_frame"]:
                sections.append(f"""{chr(section_letter)}) ACADEMIC WRITING FRAME
                - Create a structured writing frame with sentence starters for an analytical paragraph
                - The frame should help students structure their arguments about the topic""")
                section_letter += 1
            
            if options["cultural_comparison"]:
                sections.append(f"""{chr(section_letter)}) GLOBAL PERSPECTIVE
                - Create 2-3 questions comparing the topic in a global or historical context
                - Relate to the competence goals in the curriculum""")
                section_letter += 1
            
            if options["real_case"]:
                sections.append(f"""{chr(section_letter)}) PROFESSIONAL COMMUNICATION
                - Create a practical task where the student writes a professional text (report, formal email, analysis)
                - The task should relate to the topic "{topic}" """)
                section_letter += 1
        else:
            # LÆRINGSMÅL section (alltid først)
            sections.append(f"""{chr(section_letter)}) LÆRINGSMÅL
                Skriv 2-4 konkrete læringsmål som eleven skal oppnå etter å ha jobbet med dette arbeidsarket.
                Start med: "Etter denne leksjonen skal du kunne:"
                Bruk handlingsverb fra Blooms taksonomi:
                - Nivå 1-2: "forklare", "beskrive", "identifisere"
                - Nivå 3-4: "anvende", "sammenligne", "analysere"
                - Nivå 5-6: "vurdere", "drøfte", "utvikle"
                Format: nummerert liste, f.eks. "1. Forklare hva urbanisering betyr og hvilke årsaker det har"
                """)
            section_letter += 1
            
            # FØR DU LESER section (alltid andre)
            sections.append(f"""{chr(section_letter)}) FØR DU LESER (Aktivering av forkunnskap)
                Lag 2-3 korte spørsmål eller oppfordringer som aktiverer elevens forkunnskap om temaet.
                Dette skal være raske, lavterskelsoppgaver som alle kan svare på. Eksempler:
                - "Hva vet du allerede om X? Skriv ned 3 ting."
                - "Se på tittelen. Hva tror du teksten handler om?"
                - "Har du hørt om X før? Hvor?"
                Merk denne seksjonen tydelig: "Før du leser"
                """)
            section_letter += 1
            
            # Norwegian worksheet sections
            if options["vocabulary_tasks"]:
                sections.append(f"""{chr(section_letter)}) FAGBEGREPER
                - Velg 5-7 sentrale fagbegreper fra teksten
                - Gi en klar forklaring av hvert begrep
                - Format: "Begrep: forklaring" """)
                section_letter += 1
            
            if options["comprehension_tasks"]:
                sections.append(f"""{chr(section_letter)}) FORSTÅELSE OG ANALYSE (Blooms taksonomi-progresjon)
                Lag 4-5 komplette spørsmål som følger Blooms taksonomi fra lavt til høyt:
                
                SPØRSMÅL 1 (HUSKE ★): Et faktaspørsmål. "Hva er / Nevn / List opp..."
                SPØRSMÅL 2 (FORSTÅ ★): Et forståelsesspørsmål. "Forklar med egne ord / Beskriv..."
                SPØRSMÅL 3 (ANVENDE ★★): Et anvendelsesspørsmål. "Bruk begrepet X til å beskrive / Gi et eksempel på..."
                SPØRSMÅL 4 (ANALYSERE ★★★): Et analysespørsmål. "Sammenlign X og Y / Hva er forskjellene mellom..."
                SPØRSMÅL 5 (VURDERE ★★★): Et vurderings-/drøftingsspørsmål. "Drøft om... / Hva ville skjedd hvis..."
                
                VANSKELIGHETSSTJERNER - OBLIGATORISK:
                - Merk hvert spørsmål med ★ (grunnleggende - alle elever), ★★ (middels), eller ★★★ (avansert)
                - Sett stjernene ETTER spørsmålsnummeret: "1. ★ Hva er...?"
                
                For flervalg: inkluder 3 komplette alternativer (a, b, c) med full tekst.
                Marker riktig svar med * på slutten av alternativet.""")
                section_letter += 1
                
            if options["discussion_tasks"]:
                if level == "VG3":
                    sections.append(f"""{chr(section_letter)}) DRØFTING OG REFLEKSJON ★★★ (VG3-nivå med stillas)
                Lag 2 drøftingsspørsmål. Hvert spørsmål MÅ ha fire deler:

                1. SPØRSMÅLET: Et åpent, utfordrende spørsmål om temaet (Bloom 5-6)
                2. BEGREPSAPPARAT: «Nyttige begreper: [list 4-6 relevante fagbegreper eleven trenger for å svare]»
                3. STRUKTURHJELP: «Slik kan du strukturere svaret:
                   → Innledning: Presenter standpunktet ditt
                   → Argument 1: [hint til relevant perspektiv]
                   → Argument 2 / Motargument: [hint til motperspektiv]
                   → Konklusjon: Oppsummer og nyansér»
                4. SETNINGSSTARTER: «Du kan begynne med: "[en konkret setningsstarter som hjelper eleven i gang]"»

                Eksempel på format:
                «Drøft om [X] var en uunngåelig konsekvens av [Y], eller om enkeltpersoners valg var avgjørende.
                Nyttige begreper: strukturell forklaring, aktørperspektiv, historisk determinisme, kausalitet, kontrafaktisk.
                Slik kan du strukturere svaret: → Innledning: ta standpunkt → Argument 1: strukturelle faktorer → Argument 2: individuelle valg → Konklusjon: nyansér.
                Du kan begynne med: "Spørsmålet om [X] kan belyses fra to perspektiver: det strukturelle og det individuelle..."»""")
                else:
                    sections.append(f"""{chr(section_letter)}) DRØFTING OG REFLEKSJON ★★★
                - Lag 2 åpne spørsmål som inviterer til kritisk tenkning
                - Spørsmålene skal koble temaet til samfunnsmessige eller yrkesfaglige sammenhenger
                - For hvert spørsmål: inkluder 2-3 nyttige fagbegreper eleven trenger
                - Merk disse som ★★★ (avansert nivå)""")
                section_letter += 1
            
            # Advanced modules in Norwegian
            if options["role_play"]:
                sections.append(f"""{chr(section_letter)}) CASE / ROLLESPILL
                - Lag en kort case eller dialogsituasjon
                - Situasjonen skal være relatert til temaet "{topic}" i en profesjonell eller akademisk sammenheng
                - Skriv 4-6 replikker totalt eller beskriv oppgaven for elevene""")
                section_letter += 1
            
            if options["image_description"]:
                sections.append(f"""{chr(section_letter)}) VISUELL ANALYSE
                - Lag 3-4 spørsmål for analyse av bildet
                - Spørsmålene skal hjelpe eleven å koble visuelle elementer til fagstoffet""")
                section_letter += 1
            
            if options["writing_frame"]:
                sections.append(f"""{chr(section_letter)}) FAGLIG SKRIVERAMME
                - Lag en strukturert skriveramme med setningsstartere for et drøftende avsnitt
                - Rammen skal hjelpe eleven å strukturere faglige argumenter""")
                section_letter += 1
            
            if options["cultural_comparison"]:
                sections.append(f"""{chr(section_letter)}) SAMFUNNSPERSPEKTIV
                - Lag 2-3 spørsmål som setter temaet inn i en større samfunnsmessig eller historisk sammenheng
                - Relater til kompetansemålene i læreplanen""")
                section_letter += 1
            
            if options["real_case"]:
                sections.append(f"""{chr(section_letter)}) YRKESFAGLIG KOMMUNIKASJON
                - Lag en praktisk oppgave der eleven skal skrive en fagtekst (rapport, formell e-post, analyse)
                - Oppgaven skal være relatert til temaet "{topic}" """)
                section_letter += 1
            
        teacher_key_instruction = ""
        if options["teacher_key"]:
            if is_english_subject:
                teacher_key_instruction = "\nIMPORTANT: Also create an 'ANSWER KEY' at the very end for all questions you have created."
            else:
                teacher_key_instruction = "\nVIKTIG: Lag også en 'FASIT' (answer key) helt til slutt for alle spørsmålene du har laget."

        sections_text = "\n\n".join(sections)
        
        if is_english_subject:
            create_worksheet_task = Task(
                description=f"""Based on the text you have received (ignore the IMAGE_URL line), 
                create a worksheet for VGS students with the following sections:

                {sections_text}

                All content MUST be written in English and follow the VGS curriculum (LK20).
                {teacher_key_instruction}
                {language_simplification_worksheet}
                
                Do NOT include any IMAGE_URL in your response.""",
                expected_output="""A complete worksheet with the requested sections, written in English for VGS students.""",
                agent=pedagogical_developer,
                context=[create_text_task],
            )
        else:
            create_worksheet_task = Task(
                description=f"""Basert på teksten du har mottatt (ignorer IMAGE_URL linjen), 
                lag et arbeidsark for VGS-elever med følgende seksjoner:

                {sections_text}

                Alt innhold skal være på norsk (bokmål) og følge VGS-læreplanen (LK20).
                {teacher_key_instruction}
                {language_simplification_worksheet}
                
                IKKE inkluder noen IMAGE_URL i ditt svar.""",
                expected_output="""Et komplett arbeidsark for VGS-elever med de forespurte seksjonene.""",
                agent=pedagogical_developer,
                context=[create_text_task],
            )
        tasks.append(create_worksheet_task)
        agents.append(pedagogical_developer)
    else:
        create_worksheet_task = None
    
    # Task 3: Create language exercises (VGS approach)
    if options["grammar_tasks"] or options["vocabulary_tasks"]:
        if is_english_subject:
            # English language exercises
            create_language_exercises_task = Task(
                description=f"""You have received an educational text about "{topic}" for VGS. 
                Analyze the text carefully and create exercises that are 100% based on the content.
                
                TOPIC: {topic}
                
                {language_focus}
                {language_simplification_worksheet}
                
                ⚠️ QUALITY CONTROL - VERY IMPORTANT:
                - ALL terms and concepts MUST come DIRECTLY from the text you received
                - Focus on academic and subject-specific vocabulary
                
                RETURN a valid JSON object with this EXACT structure:
                {{
                    "grammar_tasks": [
                        {{
                            "type": "terminology_check" | "academic_writing",
                            "instruction": "Instruction in English for the student",
                            "items": ["exercise from text 1", "exercise from text 2", ...]
                        }}
                    ],
                    "vocabulary_tasks": [
                        {{
                            "type": "fill_in" | "match_terms",
                            "instruction": "Instruction in English for the student",
                            "items": ["sentence with ___ from text", ...]
                        }}
                    ],
                    "syntax_tasks": [
                        {{
                            "type": "analysis" | "reflection",
                            "instruction": "Instruction in English for the student",
                            "items": ["analytical question 1", "analytical question 2", ...]
                        }}
                    ]
                }}
                
                CRITICAL: Return ONLY JSON. No explanations, no markdown code blocks, just pure JSON.""",
                expected_output="""A valid JSON object with VGS-appropriate exercises.""",
                agent=language_exercise_creator,
                context=[create_text_task],
            )
        else:
            # Norwegian language exercises
            create_language_exercises_task = Task(
                description=f"""Du har mottatt en pedagogisk tekst om "{topic}" for VGS. 
                Analyser teksten grundig og lag oppgaver som er 100% basert på innholdet i teksten.
                
                TEMA: {topic}
                
                {language_focus}
                {language_simplification_worksheet}
                
                ⚠️ KVALITETSKONTROLL - SVÆRT VIKTIG:
                - ALLE begreper og konsepter MÅ komme DIREKTE fra teksten du har mottatt
                - Fokusér på fagspråk og akademisk ordforråd
                
                RETURNER et gyldig JSON-objekt med denne EKSAKTE strukturen:
                {{
                    "grammar_tasks": [
                        {{
                            "type": "begreps_sjekk" | "faglig_skriving",
                            "instruction": "Instruksjon på norsk til eleven",
                            "items": ["oppgave fra teksten 1", "oppgave fra teksten 2", ...]
                        }}
                    ],
                    "vocabulary_tasks": [
                        {{
                            "type": "fyll_inn" | "koble_begreper",
                            "instruction": "Instruksjon på norsk til eleven",
                            "items": ["setning med ___ fra teksten", ...]
                        }}
                    ],
                    "syntax_tasks": [
                        {{
                            "type": "analyse" | "refleksjon",
                            "instruction": "Instruksjon på norsk til eleven",
                            "items": ["analytisk spørsmål 1", "analytisk spørsmål 2", ...]
                        }}
                    ]
                }}
                
                KRITISK: Returner BARE JSON. Ingen forklaringer, ingen markdown-kodeblokker, bare ren JSON.""",
                expected_output="""Et gyldig JSON-objekt med VGS-tilpassede oppgaver.""",
                agent=language_exercise_creator,
                context=[create_text_task],
            )
        tasks.append(create_language_exercises_task)
        agents.append(language_exercise_creator)
    else:
        create_language_exercises_task = None

    # ── Task: Differensiering (optional) ─────────────────────────────────────
    differensiering_task = None
    if options.get("differensiering", False):
        if is_english_subject:
            diff_desc = f"""Based on the educational text about "{topic}", create two adapted versions.
            The text will be provided as context from the previous task.

            Return ONLY valid JSON with this exact structure (no markdown, no explanations):
            {{"stoette": "... the full simplified text ...", "fordypning": "... the full extended text ..."}}

            STØTTE rules: max 15 words/sentence, active voice, re-explain all key terms,
            use signal words (First, Then, Because, This means), break into bullets where helpful,
            20-30% shorter than original.

            FORDYPNING rules: add 2-3 extra nuances not in original, include historiographical
            reflection, add a critical closing question comparing perspectives,
            reference relevant primary source types, 20-30% longer than original."""
        else:
            diff_desc = f"""Basert på fagteksten om "{topic}", lag to tilpassede versjoner.
            Teksten er tilgjengelig som kontekst fra forrige oppgave.

            Returner KUN gyldig JSON med denne eksakte strukturen (ingen markdown, ingen forklaringer):
            {{"stoette": "... full forenklet tekst ...", "fordypning": "... full utvidet tekst ..."}}

            STØTTE-regler: maks 15 ord/setning, aktiv form, forklar alle fagbegreper på nytt i parentes,
            bruk signalord (Først, Deretter, Fordi, Dette betyr at), del opp i punktlister der det hjelper,
            20-30% kortere enn originalen.

            FORDYPNING-regler: legg til 2-3 ekstra nyanser som ikke er i originalen, inkluder
            historiografisk eller metodisk refleksjon, avslutt med et kritisk spørsmål som sammenstiller
            ulike perspektiver, referer til relevante primærkildetyper, 20-30% lengre enn originalen."""

        differensiering_task = Task(
            description=diff_desc,
            expected_output='{"stoette": "...", "fordypning": "..."}',
            agent=differentiation_agent,
            context=[create_text_task],
        )
        tasks.append(differensiering_task)
        agents.append(differentiation_agent)

    # ── Task: Faktarapport (optional, only if requested) ─────────────────────
    faktarapport_task = None
    if options.get("faktarapport", False):
        faktarapport_agent = Agent(
            role="Faglig kvalitetssikrer og faktasjekker for VGS-undervisningsmateriell",
            goal="""Les den ferdig genererte fagteksten og lag en kort, ærlig faktarapport til læreren.
            Rapporten skal gi læreren nøyaktig nok informasjon til å kvalitetssikre teksten på 2-3 minutter.""",
            backstory="""Du er en erfaren fagredaktør som hjelper lærere å kvalitetssikre AI-generert innhold.
            Du er tydelig og ærlig om hva som er sikkert, hva som bør sjekkes, og hva som er forenklinger.
            Du vet at læreren stoler på deg og bruker rapporten som et faglig sikkerhetsnett.""",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )

        # ── Source grounding: if the teacher pasted source material, the fact report
        #    can actually cross-check claims against it (something an LLM CAN do
        #    reliably), instead of judging its own memory (which it cannot).
        has_source = bool(source_text and source_text.strip())
        source_excerpt = source_text.strip()[:4000] if has_source else ""

        if has_source:
            source_check_no = f"""

            ═══ KILDEKRYSSJEKK (læreren har lastet opp kildemateriale) ═══
            Kildematerialet nedenfor er det du FAKTISK kan verifisere mot. Sammenlign fagtekstens
            påstander mot denne kilden, og sett "status" på hvert punkt slik:
            "dekket"  — påstanden støttes direkte av kildematerialet
            "strid"   — påstanden motsier kilden (DETTE ER VIKTIGST Å FLAGGE)
            "utenfor" — påstanden finnes ikke i kilden og bygger på modellkunnskap; må verifiseres separat
            "usikker" — bør presiseres eller verifiseres av læreren

            KILDEMATERIALE:
            {source_excerpt}
            """
            source_check_en = f"""

            ═══ SOURCE CROSS-CHECK (the teacher uploaded source material) ═══
            The source material below is what you can ACTUALLY verify against. Compare the text's
            claims to this source, and set "status" on each item as follows:
            "dekket"  — directly supported by the source material
            "strid"   — the claim conflicts with the source (MOST IMPORTANT TO FLAG)
            "utenfor" — not present in the source, relies on model knowledge; verify separately
            "usikker" — should be clarified or verified by the teacher

            SOURCE MATERIAL:
            {source_excerpt}
            """
        else:
            source_check_no = """

            ═══ ÆRLIGHET OM GRUNNLAGET ═══
            Læreren har IKKE lastet opp kildemateriale. Du kan derfor ikke kryssjekke fakta mot en
            faktisk kilde — alt bygger på modellens hukommelse, som kan inneholde feil. Bruk derfor
            kun statusene "utenfor" (bygger på modellkunnskap, men udiskutabel konsensus) og
            "usikker" (spesifikke årstall, tall og navn som bør verifiseres). Nevn i "konklusjon"
            at læreren kan lime inn kildemateriale for å få kryssjekk mot en faktisk kilde.
            """
            source_check_en = """

            ═══ HONESTY ABOUT THE BASIS ═══
            The teacher has NOT uploaded any source material. You therefore cannot cross-check facts
            against an actual source — everything rests on the model's memory, which can be wrong.
            Therefore use only the statuses "utenfor" (model knowledge, but indisputable consensus)
            and "usikker" (specific years, numbers and names that should be verified). Mention in
            "konklusjon" that the teacher can paste source material to enable real cross-checking.
            """

        if is_english_subject:
            faktarapport_desc = f"""You are a sceptical academic reviewer. Read the educational text about "{topic}" for {subject} (VGS level {level}) and produce a FACT REPORT for the teacher.

            Your job is to be ACTIVELY CRITICAL — not to validate the text, but to find its weak points.
            Think like a historian who has just read a simplistic popular account and wants to flag what a student might mislearn.
            {source_check_en}

            Return ONE valid JSON object with EXACTLY this structure (no markdown, no explanations):
            {{
              "konklusjon": "One sentence verdict for the teacher, e.g. 'Safe to use; 2 claims should be clarified orally.'",
              "punkter": [
                {{"status": "dekket" | "strid" | "utenfor" | "usikker",
                  "pastand": "the specific claim from the text (year, number, name, event)",
                  "kommentar": "short justification / what to check"}}
              ],
              "kausalitet": ["each place the text implies 'X caused Y' while reality is more complex — quote the sentence and explain (missing intermediate steps, ignored structural factors, 'great man' explanations, correlation vs causation). THIS IS THE MOST IMPORTANT LIST."],
              "perspektiver": ["important groups, regions or viewpoints absent from the text"],
              "ikke_dekket": ["topics omitted to keep the text manageable"],
              "kilder": ["2-3 reliable sources for cross-checking"],
              "verk": ["English work titles quoted in the report, e.g. 'The Sleepwalkers'"]
            }}

            Rules:
            - "status" is ALWAYS one of the four enum strings — never a symbol or emoji.
            - NEVER use emoji anywhere. No markdown in any field.
            - List ALL specific years, numbers, names and events in "punkter".
            - Keep the whole report under 500 words. Be direct and specific."""
        else:
            faktarapport_desc = f"""Du er en kritisk faglig reviewer. Les fagteksten om "{topic}" for {subject} ({level}) og lag en FAKTARAPPORT til læreren.

            Din jobb er å være AKTIVT KRITISK — ikke validere teksten, men finne dens svake punkter.
            Tenk som en historiker som nettopp har lest en forenklende populærfremstilling og vil advare om hva en elev kan misforstå.
            {source_check_no}

            Returner ETT gyldig JSON-objekt med NØYAKTIG denne strukturen (ingen markdown, ingen forklaringer):
            {{
              "konklusjon": "Én setnings dom til læreren, f.eks. 'Trygt å bruke; 2 påstander bør presiseres muntlig.'",
              "punkter": [
                {{"status": "dekket" | "strid" | "utenfor" | "usikker",
                  "pastand": "den spesifikke påstanden fra teksten (årstall, tall, navn, hendelse)",
                  "kommentar": "kort begrunnelse / hva som bør sjekkes"}}
              ],
              "kausalitet": ["hvert sted teksten antyder 'X førte til Y' når virkeligheten er mer kompleks — sitér setningen og forklar (manglende mellomledd, ignorerte strukturelle faktorer, 'great man'-forklaringer, korrelasjon vs. kausalitet). DETTE ER VIKTIGSTE LISTE."],
              "perspektiver": ["viktige grupper, regioner eller synsvinkler som mangler i teksten"],
              "ikke_dekket": ["temaer som er utelatt for å holde lengden nede"],
              "kilder": ["2-3 anerkjente kilder læreren kan sjekke mot"],
              "verk": ["engelske verktitler du siterer i rapporten, f.eks. 'The Sleepwalkers'"]
            }}

            Regler:
            - "status" er ALLTID én av de fire enum-strengene — aldri et symbol eller emoji.
            - ALDRI bruk emoji noe sted. Ingen markdown i feltene.
            - List ALLE spesifikke årstall, tall, navn og hendelser i "punkter".
            - Hold hele rapporten under 500 ord. Vær direkte og konkret."""

        faktarapport_task = Task(
            description=faktarapport_desc,
            expected_output='Ett gyldig JSON-objekt med konklusjon, punkter (status-enum), kausalitet, perspektiver, ikke_dekket, kilder og verk.' if not is_english_subject else 'One valid JSON object with konklusjon, punkter (status enums), kausalitet, perspektiver, ikke_dekket, kilder and verk.',
            agent=faktarapport_agent,
            context=[create_text_task],
        )
        tasks.append(faktarapport_task)
        agents.append(faktarapport_agent)

    # ── Task: Korrekturpasning (optional) ────────────────────────────────────
    korrektur_task = None
    if options.get("korrektur", True) and not is_english_subject:
        korrektur_agent = Agent(
            role="Norsk korrekturleser og språkekspert for VGS-undervisningsmateriell",
            goal="""Les den genererte fagteksten og korriger kun faktiske språkfeil.
            Returner den korrigerte teksten og ingenting annet — ingen forklaringer, ingen kommentarer.""",
            backstory="""Du er en erfaren korrekturleser med ekspertise i norsk bokmål.

            Du ser etter og retter:
            1. KONGRUENSFEIL (kjønnskongruens og tallkongruens):
               - Feil: «en stor mann og hans venn var trøtt» → Rett: «en stor mann og hans venn var trøtte»
               - Feil: «et stor hus» → Rett: «et stort hus»
               - Feil: «den nye loven gjelder for alle borger» → Rett: «borgere»
            2. PLEONASMER (overflødige dobbeltord):
               - Feil: «fremtidig prognose» → Rett: «prognose»
               - Feil: «hvit hvetemel» → Rett: «hvetemel»
               - Feil: «ny innovasjon» → Rett: «innovasjon»
            3. MANGLENDE TEGNSETTING i lister og kausalkjeder
            4. ÅPENBARE SKRIVEFEIL og orddoblinger

            Du gjør IKKE:
            - Omskriver setninger som er stilistisk fine
            - Legger til nytt innhold eller fjerner faglige poenger
            - Endrer overskrifter, fagbegreper eller formateringssymboler (★, →, **)
            - Inkluderer IMAGE_URL-linjer i output

            KRITISK: Returner KUN den korrigerte teksten.
            Ingen innledning, ingen avslutning, ingen kommentarer om hva du har endret.""",
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )

        korrektur_task = Task(
            description=f"""Les fagteksten du har mottatt om "{topic}" og korriger språkfeil.

            RET kun:
            - Kongruensfeil (kjønns- og tallkongruens)
            - Pleonasmer
            - Manglende tegnsetting
            - Åpenbare skrivefeil og orddoblinger

            IKKE rett stilistiske valg, ikke endre faglig innhold, ikke inkluder IMAGE_URL.

            Returner KUN den korrigerte teksten — ingen forklaringer.""",
            expected_output="Den korrigerte fagteksten uten forklaringer eller kommentarer.",
            agent=korrektur_agent,
            context=[create_text_task],
        )
        tasks.append(korrektur_task)
        agents.append(korrektur_agent)

    # ── Two-phase execution: text first (sequential), then all dependents in parallel ──
    # Phase 1: generate the main text + image URL — skipped if basis_text is provided.
    if basis_text:
        raw_text_output = basis_text
        if progress_callback:
            progress_callback("Hopper over fagtekst-generering (bruker eksisterende)...")
    else:
        if progress_callback:
            progress_callback("Genererer fagtekst og søker etter bilde...")
        text_crew = Crew(
            agents=[content_creator],
            tasks=[create_text_task],
            process=Process.sequential,
            verbose=True,
        )
        text_crew.kickoff()
        raw_text_output = create_text_task.output.raw if create_text_task.output else ""

    # ── DEL 3: parse the writer's structured JSON (data contract) ────────────
    # The writer now delivers {"tittel", "seksjoner": [...], ...}. When parsing
    # succeeds, the new margin-term layout is used; otherwise we fall back to
    # the legacy free-text flow so a malformed JSON never blocks generation.
    _text_wo_url, _ = extract_image_url(raw_text_output)
    structured = coerce_structured_lesson(extract_json_object(_text_wo_url))
    if structured:
        logger.info("Structured lesson JSON parsed (%d seksjoner)", len(structured["seksjoner"]))
    elif not basis_text:
        logger.warning("Writer output was not valid structured JSON — using legacy text flow")

    # ── Phase 1.5: pedagogical revision pass ──
    # A critic/editor reviews the draft and returns an improved version before
    # the dependent tasks (worksheet, exercises, fact report) are built on it.
    # Skipped when reusing an existing text (basis_text) since that text has
    # already been through the pipeline once.
    if options.get("revision", True) and not basis_text and raw_text_output.strip():
        if progress_callback:
            progress_callback("Kvalitetsrevisjon: redaktør gjennomgår og forbedrer teksten...")
        draft_text, draft_image_url = extract_image_url(raw_text_output)
        if structured:
            # Revise inside the JSON contract: same schema, better prose.
            draft_text = json.dumps(structured, ensure_ascii=False, indent=2)

        if structured:
            schema_rules = (
                """
            JSON-KONTRAKT (ABSOLUTT): Utkastet er et JSON-objekt. Returner NØYAKTIG samme
            JSON-struktur (tittel/ingress/seksjoner/avsnitt/begreper/kjeder/verk) der du kun
            har forbedret språket i tekstfeltene. Ingen markdown, ingen emoji, ingen nye felter.
            Returner KUN JSON-objektet."""
                if not is_english_subject else
                """
            JSON CONTRACT (ABSOLUTE): The draft is a JSON object. Return EXACTLY the same
            JSON structure (tittel/ingress/seksjoner/avsnitt/begreper/kjeder/verk) where you
            have only improved the wording of the text fields. No markdown, no emoji, no new
            fields. Return ONLY the JSON object."""
            )
        else:
            schema_rules = ""

        if is_english_subject:
            revision_desc = f"""You are revising a draft educational text for Norwegian upper
            secondary school (level: {level}, subject: {subject}, topic: {topic}).

            DRAFT TEXT:
            ═══════════════════════════════════════════
            {draft_text}
            ═══════════════════════════════════════════

            First, silently evaluate the draft against these criteria:
            1. ENGAGEMENT — Does the opening hook the reader? Are examples concrete and vivid?
            2. PRECISION — Are explanations exact, or vague and hand-wavy?
            3. STRUCTURE — Does each section flow logically? Are paragraphs focused?
            4. LEVEL — Is the language and depth right for {level}{f" with language adaptation {language_level}" if language_level else ""}?
            5. CLARITY — Are difficult terms explained at first use?

            Then output an IMPROVED version of the full text that fixes the weaknesses you found.

            STRICT RULES:
            - Do NOT add any new factual claims, numbers, dates, names or quotes that are
              not in the draft. You may sharpen, restructure and clarify — never invent.
            - Keep ALL section headings and the overall format exactly as in the draft.
            - Keep all [K] citation markers attached to the same claims they mark.
            - Keep roughly the same total length (±15%).
            - Do NOT include any IMAGE_URL line.
            - Output ONLY the revised text — no critique, no commentary, no preamble.
            {schema_rules}"""
        else:
            revision_desc = f"""Du reviderer et utkast til en fagtekst for videregående skole
            (nivå: {level}, fag: {subject}, tema: {topic}).

            UTKAST:
            ═══════════════════════════════════════════
            {draft_text}
            ═══════════════════════════════════════════

            Vurder først utkastet stille mot disse kriteriene:
            1. ENGASJEMENT — Fanger åpningen leseren? Er eksemplene konkrete og levende?
            2. PRESISJON — Er forklaringene eksakte, eller vage og omtrentlige?
            3. STRUKTUR — Flyter hver seksjon logisk? Er avsnittene fokuserte?
            4. NIVÅ — Passer språk og dybde for {level}{f" med språktilpasning {language_level}" if language_level else ""}?
            5. KLARHET — Forklares vanskelige begreper ved første bruk?

            Skriv deretter en FORBEDRET versjon av hele teksten som retter svakhetene du fant.

            ABSOLUTTE REGLER:
            - IKKE legg til nye faktapåstander, tall, årstall, navn eller sitater som ikke
              finnes i utkastet. Du kan skjerpe, omstrukturere og klargjøre — aldri dikte.
            - Behold ALLE overskrifter og formatet nøyaktig som i utkastet.
            - Behold alle [K]-markører knyttet til de samme påstandene de markerer.
            - Behold omtrent samme totale lengde (±15 %).
            - IKKE ta med noen IMAGE_URL-linje.
            - Returner KUN den reviderte teksten — ingen kritikk, kommentarer eller innledning.
            {schema_rules}"""

        reviser_agent = Agent(
            role="Fagbokredaktør og pedagogisk kvalitetssikrer" if not is_english_subject
            else "Textbook editor and pedagogical quality reviewer",
            goal="Forbedre utkast til fagtekster: skarpere, klarere og mer engasjerende — uten å endre fakta."
            if not is_english_subject
            else "Improve draft educational texts: sharper, clearer, more engaging — without changing facts.",
            backstory="""Du er en erfaren redaktør i et læremiddelforlag. Du har lest tusenvis av
            fagtekster og vet nøyaktig hva som skiller en middels tekst fra en utmerket en:
            konkrete eksempler i stedet for generelle påstander, presise formuleringer i stedet
            for fyllord, og en rød tråd leseren kan følge. Du respekterer forfatterens faktagrunnlag
            fullstendig — din jobb er form, ikke innhold. Du finner alltid noe å forbedre, men du
            ødelegger aldri det som fungerer.""",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        revise_task = Task(
            description=revision_desc,
            expected_output="Den fullstendige reviderte fagteksten, uten kommentarer.",
            agent=reviser_agent,
        )
        try:
            revision_crew = Crew(
                agents=[reviser_agent],
                tasks=[revise_task],
                process=Process.sequential,
                verbose=False,
            )
            revision_crew.kickoff()
            revised_raw = revise_task.output.raw if revise_task.output else ""
            if structured:
                # JSON-in/JSON-out: only accept a revision that still honours
                # the data contract; otherwise keep the parsed draft.
                revised_structured = coerce_structured_lesson(extract_json_object(revised_raw))
                if revised_structured and len(revised_structured["seksjoner"]) >= max(
                        1, len(structured["seksjoner"]) - 1):
                    structured = revised_structured
                    logger.info("Revision pass applied to structured JSON")
                else:
                    logger.warning("Revision output broke the JSON contract — keeping draft")
            else:
                revised_text, _ = extract_image_url(revised_raw)
                # Sanity check: the revision must be a substantial text, not a refusal
                # or a truncated fragment. Otherwise keep the original draft.
                if len(revised_text.strip()) > max(300, int(len(draft_text) * 0.6)):
                    raw_text_output = revised_text.strip()
                    if draft_image_url:
                        raw_text_output += f"\n\nIMAGE_URL: {draft_image_url}"
                    logger.info(
                        "Revision pass applied (draft %d chars -> revised %d chars)",
                        len(draft_text), len(revised_text),
                    )
                else:
                    logger.warning(
                        "Revision output too short (%d chars vs draft %d) — keeping draft",
                        len(revised_text.strip()), len(draft_text),
                    )
        except Exception as e:
            logger.warning(f"Revision pass failed — keeping draft: {e}")

    if progress_callback:
        progress_callback("Lager arbeidsark, oppgaver og kvalitetssjekk parallelt...")

    # Phase 2: fan out independent dependent tasks. Each runs in its own Crew.
    # We embed the source text directly in each task description so context= is
    # not needed across separate Crews.
    # Downstream agents (worksheet, exercises, fact report) always get clean
    # prose — never raw JSON — so their prompts behave as before.
    if structured:
        text_for_context = structured_to_plain_text(structured)
    else:
        text_for_context = raw_text_output

    # The proofreader corrects the actual deliverable: the JSON when the
    # structured contract is in play, otherwise the plain text.
    if structured:
        korrektur_context = json.dumps(structured, ensure_ascii=False, indent=2)
        korrektur_json_note = (
            "\n\nNB: Teksten under er et JSON-objekt. Returner NØYAKTIG samme JSON-struktur "
            "der du kun har rettet språkfeil i tekstfeltene (tittel, ingress, avsnitt, term, "
            "def, steg). Ingen markdown, ingen forklaringer — KUN JSON-objektet."
        )
    else:
        korrektur_context = raw_text_output
        korrektur_json_note = ""

    def _inject_basis_text(task: Task, context_text: str, extra_note: str = "") -> Task:
        """Append the generated fagtekst to the task description so that the
        sub-crew can read it without a CrewAI cross-Crew context reference."""
        original_desc = task.description or ""
        if "BASIS-TEKST FRA FAGTEKSTEN" in original_desc:
            return task  # already injected
        injection = (
            f"{extra_note}"
            "\n\n═══ BASIS-TEKST FRA FAGTEKSTEN (bruk denne som primært grunnlag) ═══\n"
            f"{context_text}\n"
            "═══════════════════════════════════════════════════════════════════"
        )
        task.description = original_desc + injection
        # Sub-crew is single-task; clear context to avoid CrewAI lookup errors
        task.context = []
        return task

    def _run_subtask(agent: Agent, task: Task, context_text: str, extra_note: str = "") -> str:
        """Run a single agent subtask.

        Raises on failure so the caller can distinguish a genuine error from a
        successful-but-empty result, instead of silently dropping the section.
        """
        sub_crew = Crew(
            agents=[agent],
            tasks=[_inject_basis_text(task, context_text, extra_note)],
            process=Process.sequential,
            verbose=False,
        )
        sub_crew.kickoff()
        return task.output.raw if task.output else ""

    # Human-friendly labels for surfacing failures to the user.
    _subtask_labels = {
        "worksheet": "arbeidsark",
        "language_exercises": "fagoppgaver",
        "differensiering": "differensiering",
        "faktarapport": "faktarapport",
        "korrektur": "korrektur",
    }

    parallel_specs = []  # list of (key, agent, task, context_text, extra_note)
    if create_worksheet_task is not None:
        parallel_specs.append(("worksheet", pedagogical_developer, create_worksheet_task,
                               text_for_context, ""))
    if create_language_exercises_task is not None:
        parallel_specs.append(("language_exercises", language_exercise_creator,
                               create_language_exercises_task, text_for_context, ""))
    if differensiering_task is not None:
        parallel_specs.append(("differensiering", differentiation_agent, differensiering_task,
                               text_for_context, ""))
    if faktarapport_task is not None:
        # The faktarapport agent was created inline above; reuse it.
        parallel_specs.append(("faktarapport", faktarapport_task.agent, faktarapport_task,
                               text_for_context, ""))
    if korrektur_task is not None:
        parallel_specs.append(("korrektur", korrektur_task.agent, korrektur_task,
                               korrektur_context, korrektur_json_note))

    parallel_outputs: dict[str, str] = {}
    warnings: list[str] = []
    if parallel_specs:
        import concurrent.futures as _cf
        max_workers = min(len(parallel_specs), 5)
        with _cf.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="agent") as ex:
            futures = {
                ex.submit(_run_subtask, agent, task, context_text, extra_note): key
                for key, agent, task, context_text, extra_note in parallel_specs
            }
            for fut in _cf.as_completed(futures):
                key = futures[fut]
                label = _subtask_labels.get(key, key)
                try:
                    output = fut.result() or ""
                except Exception as e:
                    logger.warning(f"Parallel task {key} raised: {e}", exc_info=True)
                    output = ""
                parallel_outputs[key] = output
                # Surface sections that ran but produced nothing usable, so the
                # result is never silently missing a part the user asked for.
                if not output.strip():
                    msg = f"Kunne ikke generere {label} – seksjonen utelates."
                    warnings.append(msg)
                    logger.warning("Subtask %r produced empty output", key)
                    if progress_callback:
                        progress_callback(f"⚠ {msg}")

    if progress_callback:
        progress_callback("Analyserer og strukturerer innhold...")

    worksheet_output = parallel_outputs.get("worksheet", "")
    language_exercises_output = parallel_outputs.get("language_exercises", "")
    faktarapport_output = parallel_outputs.get("faktarapport", "")
    differensiering_output = parallel_outputs.get("differensiering", "")
    korrektur_output = parallel_outputs.get("korrektur", "")

    # Parse the text to extract the image URL (always from original text)
    text_output, image_url = extract_image_url(raw_text_output)

    # Use korrektur output as final text if the proofreader ran and returned content
    if korrektur_output and korrektur_output.strip():
        if structured:
            corrected_structured = coerce_structured_lesson(extract_json_object(korrektur_output))
            if corrected_structured and len(corrected_structured["seksjoner"]) >= max(
                    1, len(structured["seksjoner"]) - 1):
                structured = corrected_structured
                logger.info("Using korrektur-corrected structured JSON as final output")
            else:
                logger.warning("Korrektur output broke the JSON contract — keeping uncorrected JSON")
        else:
            corrected, _ = extract_image_url(korrektur_output)
            if len(corrected.strip()) > 100:  # sanity-check: non-empty meaningful output
                text_output = corrected
                logger.info("Using korrektur-corrected text as final text output")

    # ── Faktarapport: parse the structured JSON (status enums + konklusjon) ──
    faktarapport_structured = None
    if faktarapport_output and faktarapport_output.strip():
        faktarapport_structured = coerce_structured_rapport(
            extract_json_object(faktarapport_output))
        if faktarapport_structured:
            # Plain-text rendering for the UI text view and .docx export.
            faktarapport_output = _rapport_to_plain_text(faktarapport_structured)
        else:
            logger.warning("Faktarapport output was not valid JSON — using raw text")

    # ── DEL 1.3: deterministic English-leak check after korrektur ────────────
    # LLM proofreading alone does not reliably catch "These kildene" /
    # "I kontrast to dette". One retry with the exact words; then flag.
    if not is_english_subject:
        verk_whitelist = tuple(structured.get("verk", []) if structured else [])
        check_text = collect_text_fields(structured) if structured else text_output
        leaks = find_english_leaks(check_text, verk_whitelist)
        if leaks:
            leak_words = sorted({w.lower() for w in leaks})
            logger.warning("English leaks detected after korrektur: %s — retrying once", leak_words)
            if progress_callback:
                progress_callback("Språkvask: retter engelske ord som slapp gjennom...")
            fixed = _retry_english_fix(
                structured if structured else text_output,
                leak_words,
            )
            if fixed is not None:
                if structured:
                    structured = fixed
                    check_text = collect_text_fields(structured)
                else:
                    text_output = fixed
                    check_text = text_output
            remaining = find_english_leaks(check_text, verk_whitelist)
            if remaining:
                remaining_words = sorted({w.lower() for w in remaining})
                msg = f"Mulige engelske ord i teksten: {', '.join(remaining_words[:6])} — kontroller før utskrift."
                warnings.append(msg)
                logger.warning("English leaks remain after retry: %s", remaining_words)

    # When the structured contract is in play, the canonical plain text is
    # derived from the (corrected) JSON so UI/docx/regenerate stay in sync.
    if structured:
        text_output = structured_to_plain_text(structured)

    # Parse the language exercises JSON
    language_exercises = extract_language_exercises(language_exercises_output) if language_exercises_output else None

    # Parse differensiering JSON
    differensiering = None
    if differensiering_output:
        differensiering = _parse_differensiering(differensiering_output)

    # Whether this output was grounded in teacher-provided source material.
    source_grounded = bool(source_text and source_text.strip())

    return {
        "topic": topic,
        "subject": subject,
        "level": level,
        "text": text_output,
        "structured": structured,
        "worksheet": worksheet_output,
        "language_exercises": language_exercises,
        "image_url": image_url,
        "faktarapport": faktarapport_output,
        "faktarapport_structured": faktarapport_structured,
        "verk": list(structured.get("verk", [])) if structured else [],
        "differensiering": differensiering,
        "warnings": warnings,
        "source_grounded": source_grounded,
    }


def _parse_differensiering(text: str) -> dict | None:
    """Parse the JSON output from the differentiation agent."""
    if not text:
        return None
    import re as _re
    # Try direct parse
    try:
        result = json.loads(text.strip())
        if isinstance(result, dict) and "stoette" in result and "fordypning" in result:
            return result
    except json.JSONDecodeError:
        pass
    # Try markdown code block
    match = _re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict) and "stoette" in result:
                return result
        except json.JSONDecodeError:
            pass
    # Try any JSON object
    match = _re.search(r'\{[\s\S]*"stoette"[\s\S]*\}', text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict) and "stoette" in result:
                return result
        except json.JSONDecodeError:
            pass
    logger.warning(f"Kunne ikke parse differensiering JSON: {text[:200]!r}")
    return None


# ── Prøvegenerator ────────────────────────────────────────────────────────────

def generate_prove_content(
    topic: str,
    subject: str,
    level: str,
    description: str = None,
    language_level: str = None,
    source_text: str = None,
    progress_callback=None,
) -> dict:
    """
    Generer en komplett prøve (test/exam) for et gitt tema og fag.

    Returns:
        dict med prove_json (strukturert JSON), text (fagtekst brukt som grunnlag),
        image_url, og topic/subject/level metadata.
    """
    import re as _re

    is_english_subject = subject.lower() == "engelsk"

    teacher_instructions = ""
    if description and description.strip():
        if is_english_subject:
            teacher_instructions = f"""
    ═══════════════════════════════════════════════════════════
    📋 TEACHER INSTRUCTIONS (HIGH PRIORITY):
    {description.strip()}
    ═══════════════════════════════════════════════════════════"""
        else:
            teacher_instructions = f"""
    ═══════════════════════════════════════════════════════════
    📋 LÆRERBESKRIVELSE (HØY PRIORITET):
    {description.strip()}
    ═══════════════════════════════════════════════════════════"""

    # Optional source grounding — the exam (and its answer key) inherits the
    # teacher's source material via the underlying educational text.
    prove_source_en = ""
    prove_source_no = ""
    if source_text and source_text.strip():
        prove_source_en = f"""

    ═══ SOURCE MATERIAL FOR FACT-GROUNDING (USE AS PRIMARY BASIS) ═══
    The teacher provided this source material. Base the text primarily on it; stay close to its
    facts, dates, names and claims. Do NOT invent facts that contradict or go beyond the source.
    ---
    {source_text.strip()[:4000]}
    ---"""
        prove_source_no = f"""

    ═══ KILDEMATERIALE FOR FAKTAFORANKRING (BRUK SOM PRIMÆRGRUNNLAG) ═══
    Læreren har lagt ved dette kildematerialet. Basér teksten primært på det; hold deg nær
    faktaene, årstallene, navnene og påstandene i kilden. IKKE finn opp fakta som motsier
    eller går langt utover kilden.
    ---
    {source_text.strip()[:4000]}
    ---"""

    # Step 1: Generate educational text (same as normal, needed for exam questions)
    if is_english_subject:
        text_task = Task(
            description=f"""Write a concise educational text about "{topic}" for {subject} VGS ({level}).
            {teacher_instructions}
            {prove_source_en}
            Length: 400-600 words. Factual, competency-goal aligned, clear sections.
            At the END write: IMAGE_URL: none""",
            expected_output=f"Educational text about {topic} followed by IMAGE_URL: none",
            agent=content_creator,
        )
    else:
        text_task = Task(
            description=f"""Skriv en kortfattet fagtekst om "{topic}" for {subject} VGS ({level}).
            {teacher_instructions}
            {prove_source_no}
            Lengde: 400-600 ord. Faktabasert, kompetansemål-tilpasset, tydelige avsnitt.
            På SLUTTEN skriv: IMAGE_URL: none""",
            expected_output=f"Fagtekst om {topic} etterfulgt av IMAGE_URL: none",
            agent=content_creator,
        )

    # Step 2: Generate the exam
    if is_english_subject:
        prove_task_desc = f"""Based on the educational text about "{topic}" ({subject}, {level}),
        create a complete exam (prøve). {teacher_instructions}

        Requirements:
        - Del A: 4-5 multiple choice questions × 2p each
        - Del B: 3-4 short answer questions × 5-8p each
        - Del C: 1 extended response question × 12-15p
        - Include a complete answer key (fasit) for all questions
        - Vurderingskriterier for Del C

        Return ONLY valid JSON matching the specified structure. No markdown, no explanations."""
    else:
        prove_task_desc = f"""Basert på fagteksten om "{topic}" ({subject}, {level}),
        lag en komplett prøve. {teacher_instructions}

        Krav:
        - Del A: 4-5 flervalgsoppgaver × 2p hver
        - Del B: 3-4 kortsvarsoppgaver × 5-8p hver
        - Del C: 1 langsvarsoppgave × 12-15p
        - Inkluder komplett fasit for alle spørsmål
        - Vurderingskriterier for Del C

        Returner KUN gyldig JSON som matcher den spesifiserte strukturen. Ingen markdown, ingen forklaringer."""

    prove_task = Task(
        description=prove_task_desc,
        expected_output="Valid JSON object representing the complete exam structure.",
        agent=prove_agent,
        context=[text_task],
    )

    crew = Crew(
        agents=[content_creator, prove_agent],
        tasks=[text_task, prove_task],
        process=Process.sequential,
        verbose=True,
    )

    if progress_callback:
        progress_callback("Genererer fagtekst som grunnlag for prøven...")
    result = crew.kickoff()
    if progress_callback:
        progress_callback("Lager prøvespørsmål, fasit og vurderingskriterier...")

    raw_text = text_task.output.raw if text_task.output else ""
    raw_prove = prove_task.output.raw if prove_task.output else ""

    text_output, image_url = extract_image_url(raw_text)

    # Parse prove JSON
    prove_json = _parse_prove_json(raw_prove)

    return {
        "topic": topic,
        "subject": subject,
        "level": level,
        "text": text_output,
        "prove_json": prove_json,
        "image_url": image_url,
    }


def _parse_prove_json(text: str) -> dict | None:
    """Parse JSON output from the prove agent."""
    import re as _re
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = _re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Find the outermost { ... }
    match = _re.search(r'\{[\s\S]*"del_a"[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning(f"Kunne ikke parse prøve JSON: {text[:300]!r}")
    return None


# ── Agent 6: Sekvensplanlegger ────────────────────────────────────────────────
sequence_agent = Agent(
    role="Expert curriculum designer and pedagogical sequence planner for Norwegian VGS",
    goal="""Design a complete, pedagogically sound teaching sequence (sekvensplan / læringsløp)
    for a given topic, subject and school level. The sequence must be grounded in LK20 competency
    goals and follow proven didactic models (BSED, 5E, spiral curriculum).
    Return structured JSON only.""",
    backstory="""You are a senior curriculum consultant for Udir (Utdanningsdirektoratet) with 20+
    years of experience designing teaching sequences for Norwegian Upper Secondary School.

    You understand:
    - LK20 competency goals and their progression across VG1/VG2/VG3
    - Bloom's taxonomy — lessons should progress from Recall → Understanding → Application → Analysis
    - Formative assessment (underveisvurdering) woven into every lesson
    - Balanced methods: direct instruction, cooperative learning, inquiry, project work
    - Differentiation within the sequence so all students can participate
    - The Norwegian grading scale (1–6) and vurderingsforskriften

    STRICT OUTPUT RULES:
    1. Return ONLY valid JSON — no markdown, no explanations, no code fences.
    2. Every lesson must have a clear tittel, specific laeringsmaal (list), aktiviteter object
       with intro/hoved/avslutning strings, vurdering string, and ressurser list.
    3. Bloom level increases across weeks — start with recall, end with evaluation/creation.
    4. Include one formativ vurdering checkpoint per week.
    5. The avsluttende_vurdering must describe a summative assessment task.
    6. FACTUAL INTEGRITY: Do NOT fabricate exact LK20 competency-goal codes or invent verbatim
       curriculum wording you are not sure of — paraphrase the goal honestly if uncertain. Likewise,
       do not invent specific named resources (book titles, URLs, articles); describe the resource
       TYPE instead (e.g. "en kort dokumentar om temaet", "lærebokas kapittel om ...") when unsure.

    JSON structure MUST be exactly:
    {
      "tittel": "Sekvensplan: [topic]",
      "fag": "[subject]",
      "trinn": "[level]",
      "antall_uker": [number],
      "kompetansemaal": ["Kompetansemål 1 fra LK20...", "..."],
      "uker": [
        {
          "uke_nr": 1,
          "uke_tema": "...",
          "timer": [
            {
              "time_nr": 1,
              "tittel": "...",
              "varighet": "90 min",
              "bloom_niva": "Huske / Forstå",
              "laeringsmaal": ["Eleven kan ...", "Eleven kan ..."],
              "aktiviteter": {
                "intro": "... (ca X min)",
                "hoved": "... (ca X min)",
                "avslutning": "... (ca X min)"
              },
              "vurdering": "Formativ: ...",
              "ressurser": ["...", "..."],
              "differensiering": "Støtte: ... / Fordypning: ..."
            }
          ],
          "ukes_vurdering": "Formativ checkpoint for uke [N]: ..."
        }
      ],
      "avsluttende_vurdering": "...",
      "ressursliste": ["...", "..."]
    }""",
    llm=llm,
    verbose=True,
    allow_delegation=False,
)


def generate_sequence_content(
    topic: str,
    subject: str,
    level: str,
    antall_uker: int = 3,
    timer_per_uke: int = 2,
    description: str = None,
    grep_goals: list[str] = None,
    progress_callback=None,
) -> dict:
    """
    Generer en komplett sekvensplan (læringsløp) for et gitt tema, fag og trinn.

    Args:
        topic:           Emne/tema for sekvensen
        subject:         Fag (f.eks. "Historie", "Naturfag")
        level:           Trinn (f.eks. "VG1", "VG2")
        antall_uker:     Antall undervisningsuker (2–6)
        timer_per_uke:   Timer per uke (1–3)
        description:     Valgfri lærerbeskrivelse
        grep_goals:      Valgfri liste med LK20-kompetansemålkoder
        progress_callback: Kalles med fremdriftsmeldinger

    Returns:
        dict med sequence_json, topic, subject, level
    """
    is_english_subject = subject.lower() == "engelsk"

    def push(msg: str):
        if progress_callback:
            progress_callback(msg)

    teacher_instructions = ""
    if description and description.strip():
        teacher_instructions = f"""
═══════════════════════════════════════════════════════════
📋 LÆRERBESKRIVELSE (HØY PRIORITET):
{description.strip()}
═══════════════════════════════════════════════════════════"""

    grep_text = ""
    if grep_goals:
        grep_text = f"""
Disse LK20-kompetansemålene SKAL dekkes i sekvensen:
{chr(10).join(f'- {g}' for g in grep_goals)}"""

    total_timer = antall_uker * timer_per_uke

    if is_english_subject:
        task_desc = f"""Design a complete teaching sequence for "{topic}" in {subject} VGS ({level}).
        {teacher_instructions}
        {grep_text}

        Sequence parameters:
        - Number of weeks: {antall_uker}
        - Lessons per week: {timer_per_uke}
        - Total lessons: {total_timer}

        REQUIREMENTS:
        1. Cover all specified competency goals across the {antall_uker} weeks
        2. Lessons must escalate in Bloom's taxonomy level (recall → evaluation)
        3. Include formative assessment in every lesson and a summative at the end
        4. Each lesson must have specific learning goals ("The student can...")
        5. Activities must include intro (hook), main activity, and closing/reflection
        6. Include differentiation hints for both support and challenge levels

        Return ONLY valid JSON matching the required structure exactly."""

        expected = f"JSON sequence plan for {topic} with {antall_uker} weeks × {timer_per_uke} lessons"
    else:
        task_desc = f"""Design en komplett sekvensplan for "{topic}" i {subject} VGS ({level}).
        {teacher_instructions}
        {grep_text}

        Sekvensparametere:
        - Antall uker: {antall_uker}
        - Timer per uke: {timer_per_uke}
        - Totalt antall timer: {total_timer}

        KRAV:
        1. Dekk alle oppgitte kompetansemål fordelt over {antall_uker} uker
        2. Timene skal eskalere i Blooms taksonomi (huske → vurdere)
        3. Inkluder formativ vurdering i hver time og en summativ vurdering til slutt
        4. Hver time skal ha konkrete læringsmål ("Eleven kan...")
        5. Aktiviteter skal ha intro (hook), hoveddel og avslutning/refleksjon
        6. Inkluder differensieringstips for støtte- og fordypningsnivå

        Returner KUN gyldig JSON som matcher den påkrevde strukturen nøyaktig."""

        expected = f"JSON-sekvensplan for {topic} med {antall_uker} uker × {timer_per_uke} timer"

    push("Planlegger undervisningssekvens...")

    sequence_task = Task(
        description=task_desc,
        expected_output=expected,
        agent=sequence_agent,
    )

    crew = Crew(
        agents=[sequence_agent],
        tasks=[sequence_task],
        process=Process.sequential,
        verbose=True,
    )

    push("Genererer læringsløp og kompetansemål...")
    result = crew.kickoff()

    raw = str(result.raw) if hasattr(result, "raw") else str(result)
    seq_json = _parse_sequence_json(raw) or {}

    push("Sekvensplan klar — kompilerer PDF...")

    return {
        "topic": topic,
        "subject": subject,
        "level": level,
        "antall_uker": antall_uker,
        "timer_per_uke": timer_per_uke,
        "sequence_json": seq_json,
    }


def _parse_sequence_json(text: str) -> dict | None:
    """Parse JSON output from the sequence agent with fallback strategies."""
    import re as _re
    if not text:
        return None
    # Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Markdown code block
    match = _re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Find outermost { ... } containing "uker"
    match = _re.search(r'\{[\s\S]*?"uker"[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning(f"Kunne ikke parse sekvens JSON: {text[:300]!r}")
    return None


# For testing purposes
if __name__ == "__main__":
    # Test the agents with a sample topic
    result = generate_lesson_content(
        topic="Kildesortering og resirkulering",
        subject="Samfunnsfag",
        level="A2"
    )
    logger.info("GENERATED LESSON CONTENT")
    logger.info(f"Topic: {result['topic']}, Subject: {result['subject']}, Level: {result['level']}")
    logger.info(f"Image URL: {result['image_url']}")
    logger.debug(f"Text: {result['text']}")
    logger.debug(f"Worksheet: {result['worksheet']}")

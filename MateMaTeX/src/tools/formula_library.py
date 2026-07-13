"""
Formula Library for MateMaTeX.
Quick access to common mathematical formulas organized by category.
"""

from typing import Optional
from dataclasses import dataclass


@dataclass
class Formula:
    """Represents a mathematical formula."""
    name: str
    latex: str
    description: str
    category: str
    grade_level: str  # e.g., "8-10", "VG1", "VG2-VG3"
    keywords: list[str]


# Formula library organized by category
FORMULA_LIBRARY = {
    "Algebra": [
        Formula(
            name="Kvadratsetning 1",
            latex=r"(a + b)^2 = a^2 + 2ab + b^2",
            description="Første kvadratsetning",
            category="Algebra",
            grade_level="10-VG1",
            keywords=["kvadrat", "potens", "faktorisering"]
        ),
        Formula(
            name="Kvadratsetning 2",
            latex=r"(a - b)^2 = a^2 - 2ab + b^2",
            description="Andre kvadratsetning",
            category="Algebra",
            grade_level="10-VG1",
            keywords=["kvadrat", "potens", "faktorisering"]
        ),
        Formula(
            name="Konjugatsetningen",
            latex=r"(a + b)(a - b) = a^2 - b^2",
            description="Konjugatsetningen (tredje kvadratsetning)",
            category="Algebra",
            grade_level="10-VG1",
            keywords=["konjugat", "faktorisering", "differanse"]
        ),
        Formula(
            name="ABC-formelen",
            latex=r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
            description="Løsningsformel for andregradslikninger ax² + bx + c = 0",
            category="Algebra",
            grade_level="10-VG1",
            keywords=["andregradslikning", "nullpunkt", "løsning"]
        ),
        Formula(
            name="Potensregler",
            latex=r"a^m \cdot a^n = a^{m+n}, \quad \frac{a^m}{a^n} = a^{m-n}, \quad (a^m)^n = a^{mn}",
            description="Grunnleggende potensregler",
            category="Algebra",
            grade_level="8-VG1",
            keywords=["potens", "eksponent", "regler"]
        ),
        Formula(
            name="Logaritmeregler",
            latex=r"\log(ab) = \log a + \log b, \quad \log\frac{a}{b} = \log a - \log b, \quad \log a^n = n \log a",
            description="Grunnleggende logaritmeregler",
            category="Algebra",
            grade_level="VG1-VG2",
            keywords=["logaritme", "log", "regler"]
        ),
    ],
    
    "Geometri": [
        Formula(
            name="Pytagoras' setning",
            latex=r"a^2 + b^2 = c^2",
            description="For rettvinklet trekant der c er hypotenusen",
            category="Geometri",
            grade_level="8-10",
            keywords=["pytagoras", "trekant", "hypotenus", "katet"]
        ),
        Formula(
            name="Areal av trekant",
            latex=r"A = \frac{1}{2} \cdot g \cdot h",
            description="Areal = halve grunnlinje ganger høyde",
            category="Geometri",
            grade_level="5-10",
            keywords=["areal", "trekant", "grunnlinje", "høyde"]
        ),
        Formula(
            name="Areal av sirkel",
            latex=r"A = \pi r^2",
            description="Areal av sirkel med radius r",
            category="Geometri",
            grade_level="8-10",
            keywords=["areal", "sirkel", "radius", "pi"]
        ),
        Formula(
            name="Omkrets av sirkel",
            latex=r"O = 2\pi r = \pi d",
            description="Omkrets av sirkel",
            category="Geometri",
            grade_level="8-10",
            keywords=["omkrets", "sirkel", "diameter", "radius"]
        ),
        Formula(
            name="Volum av sylinder",
            latex=r"V = \pi r^2 h",
            description="Volum av sylinder med radius r og høyde h",
            category="Geometri",
            grade_level="8-10",
            keywords=["volum", "sylinder", "radius", "høyde"]
        ),
        Formula(
            name="Volum av kule",
            latex=r"V = \frac{4}{3}\pi r^3",
            description="Volum av kule med radius r",
            category="Geometri",
            grade_level="10",
            keywords=["volum", "kule", "sfære", "radius"]
        ),
        Formula(
            name="Volum av kjegle",
            latex=r"V = \frac{1}{3}\pi r^2 h",
            description="Volum av kjegle med radius r og høyde h",
            category="Geometri",
            grade_level="10",
            keywords=["volum", "kjegle", "radius", "høyde"]
        ),
        Formula(
            name="Overflate av kule",
            latex=r"A = 4\pi r^2",
            description="Overflate av kule med radius r",
            category="Geometri",
            grade_level="10",
            keywords=["overflate", "kule", "sfære", "areal"]
        ),
    ],
    
    "Trigonometri": [
        Formula(
            name="Sinus",
            latex=r"\sin v = \frac{\text{motstående katet}}{\text{hypotenus}}",
            description="Definisjon av sinus i rettvinklet trekant",
            category="Trigonometri",
            grade_level="10-VG1",
            keywords=["sinus", "sin", "trekant", "vinkel"]
        ),
        Formula(
            name="Cosinus",
            latex=r"\cos v = \frac{\text{hosliggende katet}}{\text{hypotenus}}",
            description="Definisjon av cosinus i rettvinklet trekant",
            category="Trigonometri",
            grade_level="10-VG1",
            keywords=["cosinus", "cos", "trekant", "vinkel"]
        ),
        Formula(
            name="Tangens",
            latex=r"\tan v = \frac{\text{motstående katet}}{\text{hosliggende katet}} = \frac{\sin v}{\cos v}",
            description="Definisjon av tangens",
            category="Trigonometri",
            grade_level="10-VG1",
            keywords=["tangens", "tan", "trekant", "vinkel"]
        ),
        Formula(
            name="Sinussetningen",
            latex=r"\frac{a}{\sin A} = \frac{b}{\sin B} = \frac{c}{\sin C}",
            description="For vilkårlige trekanter",
            category="Trigonometri",
            grade_level="VG1",
            keywords=["sinus", "setning", "trekant"]
        ),
        Formula(
            name="Cosinussetningen",
            latex=r"c^2 = a^2 + b^2 - 2ab\cos C",
            description="For vilkårlige trekanter",
            category="Trigonometri",
            grade_level="VG1",
            keywords=["cosinus", "setning", "trekant"]
        ),
        Formula(
            name="Arealsetningen",
            latex=r"A = \frac{1}{2}ab\sin C",
            description="Areal av trekant gitt to sider og mellomliggende vinkel",
            category="Trigonometri",
            grade_level="VG1",
            keywords=["areal", "trekant", "sinus", "vinkel"]
        ),
    ],
    
    "Funksjoner": [
        Formula(
            name="Lineær funksjon",
            latex=r"f(x) = ax + b",
            description="a = stigningstall, b = konstantledd",
            category="Funksjoner",
            grade_level="8-10",
            keywords=["lineær", "funksjon", "stigningstall", "rett linje"]
        ),
        Formula(
            name="Stigningstall",
            latex=r"a = \frac{y_2 - y_1}{x_2 - x_1} = \frac{\Delta y}{\Delta x}",
            description="Stigningstall mellom to punkter",
            category="Funksjoner",
            grade_level="8-10",
            keywords=["stigningstall", "lineær", "punkt"]
        ),
        Formula(
            name="Andregradsfunksjon",
            latex=r"f(x) = ax^2 + bx + c",
            description="Parabel, a ≠ 0",
            category="Funksjoner",
            grade_level="10-VG1",
            keywords=["andregrads", "parabel", "funksjon"]
        ),
        Formula(
            name="Toppunkt/bunnpunkt",
            latex=r"x_t = -\frac{b}{2a}, \quad y_t = f(x_t)",
            description="Ekstremalpunkt for andregradsfunksjon",
            category="Funksjoner",
            grade_level="10-VG1",
            keywords=["toppunkt", "bunnpunkt", "parabel", "ekstremal"]
        ),
        Formula(
            name="Eksponentialfunksjon",
            latex=r"f(x) = a \cdot b^x",
            description="a = startverdi, b = vekstfaktor",
            category="Funksjoner",
            grade_level="10-VG1",
            keywords=["eksponentiell", "vekst", "forfall"]
        ),
    ],
    
    "Derivasjon": [
        Formula(
            name="Derivasjonsdefinisjon",
            latex=r"f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}",
            description="Definisjonen av den deriverte",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["derivasjon", "definisjon", "grenseverdi"]
        ),
        Formula(
            name="Potensfunksjoner",
            latex=r"\frac{d}{dx}(x^n) = nx^{n-1}",
            description="Derivasjon av potensfunksjoner",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["derivasjon", "potens", "regel"]
        ),
        Formula(
            name="Produktregelen",
            latex=r"(f \cdot g)' = f' \cdot g + f \cdot g'",
            description="Derivasjon av produkt",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["produktregel", "derivasjon"]
        ),
        Formula(
            name="Kvotientregelen",
            latex=r"\left(\frac{f}{g}\right)' = \frac{f' \cdot g - f \cdot g'}{g^2}",
            description="Derivasjon av kvotient",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["kvotientregel", "derivasjon", "brøk"]
        ),
        Formula(
            name="Kjerneregelen",
            latex=r"(f(g(x)))' = f'(g(x)) \cdot g'(x)",
            description="Derivasjon av sammensatte funksjoner",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["kjerneregel", "sammensatt", "derivasjon"]
        ),
        Formula(
            name="Derivert av e^x",
            latex=r"\frac{d}{dx}(e^x) = e^x, \quad \frac{d}{dx}(e^{kx}) = k \cdot e^{kx}",
            description="Derivasjon av eksponentialfunksjoner",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["eksponentiell", "e", "derivasjon"]
        ),
        Formula(
            name="Derivert av ln",
            latex=r"\frac{d}{dx}(\ln x) = \frac{1}{x}",
            description="Derivasjon av naturlig logaritme",
            category="Derivasjon",
            grade_level="VG2",
            keywords=["ln", "logaritme", "derivasjon"]
        ),
    ],
    
    "Integrasjon": [
        Formula(
            name="Potensregel",
            latex=r"\int x^n \, dx = \frac{x^{n+1}}{n+1} + C, \quad n \neq -1",
            description="Integrasjon av potensfunksjoner",
            category="Integrasjon",
            grade_level="VG3",
            keywords=["integral", "potens", "regel"]
        ),
        Formula(
            name="Eksponentialfunksjon",
            latex=r"\int e^{kx} \, dx = \frac{1}{k}e^{kx} + C",
            description="Integrasjon av e^kx",
            category="Integrasjon",
            grade_level="VG3",
            keywords=["integral", "eksponentiell", "e"]
        ),
        Formula(
            name="Bestemt integral",
            latex=r"\int_a^b f(x) \, dx = F(b) - F(a)",
            description="Fundamentalteoremet i kalkulus",
            category="Integrasjon",
            grade_level="VG3",
            keywords=["bestemt", "integral", "areal"]
        ),
        Formula(
            name="Areal mellom kurver",
            latex=r"A = \int_a^b |f(x) - g(x)| \, dx",
            description="Areal mellom to kurver",
            category="Integrasjon",
            grade_level="VG3",
            keywords=["areal", "kurve", "integral"]
        ),
    ],
    
    "Sannsynlighet": [
        Formula(
            name="Klassisk sannsynlighet",
            latex=r"P(A) = \frac{\text{gunstige utfall}}{\text{mulige utfall}}",
            description="Grunnleggende sannsynlighetsformel",
            category="Sannsynlighet",
            grade_level="8-10",
            keywords=["sannsynlighet", "utfall", "gunstig"]
        ),
        Formula(
            name="Komplementsetningen",
            latex=r"P(A') = 1 - P(A)",
            description="Sannsynlighet for komplementet",
            category="Sannsynlighet",
            grade_level="8-10",
            keywords=["komplement", "sannsynlighet"]
        ),
        Formula(
            name="Addisjonssetningen",
            latex=r"P(A \cup B) = P(A) + P(B) - P(A \cap B)",
            description="Sannsynlighet for A eller B",
            category="Sannsynlighet",
            grade_level="VG1",
            keywords=["addisjon", "union", "sannsynlighet"]
        ),
        Formula(
            name="Binomialfordelingen",
            latex=r"P(X = k) = \binom{n}{k} p^k (1-p)^{n-k}",
            description="Sannsynlighet for k suksesser i n forsøk",
            category="Sannsynlighet",
            grade_level="VG2",
            keywords=["binomial", "fordeling", "sannsynlighet"]
        ),
        Formula(
            name="Forventningsverdi",
            latex=r"E(X) = \mu = \sum x_i \cdot P(x_i)",
            description="Forventet verdi for diskret variabel",
            category="Sannsynlighet",
            grade_level="VG2",
            keywords=["forventning", "gjennomsnitt", "mu"]
        ),
    ],
    
    "Økonomi": [
        Formula(
            name="Vekstfaktor",
            latex=r"\text{Ny verdi} = \text{Gammel verdi} \cdot (1 + r)^n",
            description="r = rente/vekst som desimaltall, n = antall perioder",
            category="Økonomi",
            grade_level="9-VG1",
            keywords=["vekst", "rente", "eksponentiell"]
        ),
        Formula(
            name="Prosentvis endring",
            latex=r"\text{Endring} = \frac{\text{Ny} - \text{Gammel}}{\text{Gammel}} \cdot 100\%",
            description="Beregne prosentvis endring",
            category="Økonomi",
            grade_level="8-10",
            keywords=["prosent", "endring", "økning", "reduksjon"]
        ),
        Formula(
            name="Annuitet",
            latex=r"A = L \cdot \frac{r(1+r)^n}{(1+r)^n - 1}",
            description="Årlig betaling for annuitetslån",
            category="Økonomi",
            grade_level="VG1",
            keywords=["annuitet", "lån", "betaling", "rente"]
        ),
    ],
}


def get_all_formulas() -> list[Formula]:
    """Get all formulas as a flat list."""
    formulas = []
    for category_formulas in FORMULA_LIBRARY.values():
        formulas.extend(category_formulas)
    return formulas


def get_formulas_by_category(category: str) -> list[Formula]:
    """Get formulas for a specific category."""
    return FORMULA_LIBRARY.get(category, [])


def get_categories() -> list[str]:
    """Get all available categories."""
    return list(FORMULA_LIBRARY.keys())


def search_formulas(query: str, grade_filter: Optional[str] = None) -> list[Formula]:
    """
    Search formulas by name, description, or keywords.
    
    Args:
        query: Search query.
        grade_filter: Optional grade level filter (e.g., "10", "VG1").
    
    Returns:
        List of matching formulas.
    """
    query_lower = query.lower()
    results = []
    
    for formula in get_all_formulas():
        # Check if query matches
        matches = (
            query_lower in formula.name.lower() or
            query_lower in formula.description.lower() or
            any(query_lower in kw.lower() for kw in formula.keywords)
        )
        
        if not matches:
            continue
        
        # Apply grade filter if specified
        if grade_filter:
            if grade_filter.lower() not in formula.grade_level.lower():
                continue
        
        results.append(formula)
    
    return results


def get_formula_latex_block(formula: Formula, include_description: bool = True) -> str:
    """
    Get a LaTeX block for inserting a formula.
    
    Args:
        formula: The formula to format.
        include_description: Whether to include the description.
    
    Returns:
        LaTeX code block.
    """
    if include_description:
        return f"""\\textbf{{{formula.name}}}

\\begin{{equation}}
{formula.latex}
\\end{{equation}}

\\textit{{{formula.description}}}
"""
    else:
        return f"""\\begin{{equation}}
{formula.latex}
\\end{{equation}}
"""


def get_formula_for_topic(topic: str, num_formulas: int = 3) -> list[Formula]:
    """
    Get relevant formulas for a given topic.
    
    Args:
        topic: The math topic.
        num_formulas: Maximum number of formulas to return.
    
    Returns:
        List of relevant formulas.
    """
    topic_lower = topic.lower()
    
    # Score formulas by relevance
    scored = []
    for formula in get_all_formulas():
        score = 0
        
        # Check name
        if topic_lower in formula.name.lower():
            score += 3
        
        # Check keywords
        for kw in formula.keywords:
            if kw.lower() in topic_lower or topic_lower in kw.lower():
                score += 2
        
        # Check category
        if topic_lower in formula.category.lower():
            score += 1
        
        # Check description
        if topic_lower in formula.description.lower():
            score += 1
        
        if score > 0:
            scored.append((score, formula))
    
    # Sort by score and return top results
    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:num_formulas]]

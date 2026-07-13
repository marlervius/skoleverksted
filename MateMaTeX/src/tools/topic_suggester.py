"""
Topic Suggester for MateMaTeX.
Uses AI to suggest relevant math topics based on grade level and context.
"""

import os
from typing import Optional

# Pre-defined topic suggestions by grade (fallback when AI is not available)
TOPIC_SUGGESTIONS = {
    "1.-4. trinn": [
        {"topic": "Tallene 0-100", "description": "Telle, lese og skrive tall", "difficulty": "lett"},
        {"topic": "Addisjon med tierovergang", "description": "Legge sammen med å låne", "difficulty": "middels"},
        {"topic": "Gangetabellen", "description": "Multiplikasjon 1-10", "difficulty": "middels"},
        {"topic": "Klokka", "description": "Lese analog og digital klokke", "difficulty": "lett"},
        {"topic": "Geometriske figurer", "description": "Trekant, firkant, sirkel", "difficulty": "lett"},
        {"topic": "Måling med linjal", "description": "Lengde i cm og m", "difficulty": "lett"},
    ],
    "5.-7. trinn": [
        {"topic": "Brøkregning", "description": "Addisjon og subtraksjon av brøker", "difficulty": "middels"},
        {"topic": "Desimaltall", "description": "Regning med desimaltall", "difficulty": "middels"},
        {"topic": "Prosent", "description": "Finne prosenten av et tall", "difficulty": "middels"},
        {"topic": "Areal og omkrets", "description": "Beregne areal av figurer", "difficulty": "middels"},
        {"topic": "Koordinatsystemet", "description": "Plotte punkter og lese av", "difficulty": "lett"},
        {"topic": "Statistikk", "description": "Gjennomsnitt, median og typetall", "difficulty": "middels"},
    ],
    "8. trinn": [
        {"topic": "Bokstavregning", "description": "Algebra med variabler", "difficulty": "middels"},
        {"topic": "Likninger med én ukjent", "description": "Løse enkle likninger", "difficulty": "middels"},
        {"topic": "Pytagoras' setning", "description": "Beregne sider i rettvinklet trekant", "difficulty": "middels"},
        {"topic": "Prosentregning", "description": "Rabatt, påslag og vekstfaktor", "difficulty": "middels"},
        {"topic": "Potenser", "description": "Regning med potenser", "difficulty": "middels"},
        {"topic": "Sannsynlighet", "description": "Enkel sannsynlighetsregning", "difficulty": "lett"},
    ],
    "9. trinn": [
        {"topic": "Likningssett", "description": "To likninger med to ukjente", "difficulty": "vanskelig"},
        {"topic": "Lineære funksjoner", "description": "Stigningstall og konstantledd", "difficulty": "middels"},
        {"topic": "Renter og lån", "description": "Rentesrente og annuitet", "difficulty": "middels"},
        {"topic": "Geometri med Pytagoras", "description": "Praktiske anvendelser", "difficulty": "middels"},
        {"topic": "Faktorisering", "description": "Faktorisere algebraiske uttrykk", "difficulty": "vanskelig"},
        {"topic": "Statistisk analyse", "description": "Analysere datasett", "difficulty": "middels"},
    ],
    "10. trinn": [
        {"topic": "Andregradslikninger", "description": "Løse med abc-formelen", "difficulty": "vanskelig"},
        {"topic": "Andregradsfunksjoner", "description": "Parabler og nullpunkter", "difficulty": "vanskelig"},
        {"topic": "Trigonometri", "description": "Sinus, cosinus og tangens", "difficulty": "vanskelig"},
        {"topic": "Eksponentialfunksjoner", "description": "Vekst og forfall", "difficulty": "middels"},
        {"topic": "Volum av kjegle og kule", "description": "Beregne romfigurer", "difficulty": "middels"},
        {"topic": "Eksamensoppgaver", "description": "Blandet repetisjon", "difficulty": "vanskelig"},
    ],
    "VG1 1T": [
        {"topic": "Polynomfunksjoner", "description": "Nullpunkter og faktorisering", "difficulty": "vanskelig"},
        {"topic": "Logaritmer", "description": "Logaritmeregler og likninger", "difficulty": "vanskelig"},
        {"topic": "Vektorer i planet", "description": "Vektorregning og skalarprodukt", "difficulty": "vanskelig"},
        {"topic": "Trigonometri", "description": "Sinussetningen og cosinussetningen", "difficulty": "vanskelig"},
        {"topic": "Kombinatorikk", "description": "Permutasjoner og kombinasjoner", "difficulty": "middels"},
        {"topic": "Eksponentiallikninger", "description": "Løse med logaritmer", "difficulty": "vanskelig"},
    ],
    "VG1 1P": [
        {"topic": "Personlig økonomi", "description": "Budsjett og regnskap", "difficulty": "lett"},
        {"topic": "Lån og sparing", "description": "Annuitetslån og serielån", "difficulty": "middels"},
        {"topic": "Lineære modeller", "description": "Praktiske funksjoner", "difficulty": "middels"},
        {"topic": "Statistikk", "description": "Dataanalyse og presentasjon", "difficulty": "middels"},
        {"topic": "Praktisk trigonometri", "description": "Måling og beregning", "difficulty": "middels"},
        {"topic": "Prosentregning", "description": "Vekstfaktor og endring", "difficulty": "lett"},
    ],
    "VG2 R1": [
        {"topic": "Derivasjon", "description": "Derivasjonsregler og drøfting", "difficulty": "vanskelig"},
        {"topic": "Polynomer", "description": "Polynomdivisjon og nullpunkter", "difficulty": "vanskelig"},
        {"topic": "Kjerneregelen", "description": "Derivasjon av sammensatte funksjoner", "difficulty": "vanskelig"},
        {"topic": "Vektorer i rommet", "description": "3D-vektorer og vektorprodukt", "difficulty": "vanskelig"},
        {"topic": "Binomialfordelingen", "description": "Sannsynlighetsmodeller", "difficulty": "vanskelig"},
        {"topic": "Optimering", "description": "Maks og min med derivasjon", "difficulty": "vanskelig"},
    ],
    "VG3 R2": [
        {"topic": "Integrasjon", "description": "Integrasjonsteknikker", "difficulty": "vanskelig"},
        {"topic": "Differensiallikninger", "description": "Separable og lineære", "difficulty": "vanskelig"},
        {"topic": "Volum av omdreiningslegemer", "description": "Integrasjon i praksis", "difficulty": "vanskelig"},
        {"topic": "Rekker", "description": "Geometriske og aritmetiske rekker", "difficulty": "vanskelig"},
        {"topic": "Delvis integrasjon", "description": "Avansert integrasjon", "difficulty": "vanskelig"},
        {"topic": "Trigonometriske funksjoner", "description": "Derivasjon og integrasjon", "difficulty": "vanskelig"},
    ],
}


def get_topic_suggestions(
    grade: str,
    current_topic: str = "",
    num_suggestions: int = 6,
    use_ai: bool = False
) -> list[dict]:
    """
    Get topic suggestions for a grade level.
    
    Args:
        grade: The grade level.
        current_topic: Current topic (to avoid duplicates).
        num_suggestions: Number of suggestions to return.
        use_ai: Whether to use AI for suggestions (requires API key).
    
    Returns:
        List of topic suggestion dictionaries.
    """
    # Normalize grade
    grade_key = grade
    for key in TOPIC_SUGGESTIONS.keys():
        if grade.lower() in key.lower() or key.lower() in grade.lower():
            grade_key = key
            break
    
    suggestions = TOPIC_SUGGESTIONS.get(grade_key, TOPIC_SUGGESTIONS.get("10. trinn", []))
    
    # Filter out current topic
    if current_topic:
        suggestions = [s for s in suggestions if current_topic.lower() not in s["topic"].lower()]
    
    # If AI is requested and API key is available, enhance suggestions
    if use_ai and os.getenv("GOOGLE_API_KEY"):
        try:
            ai_suggestions = _get_ai_suggestions(grade, current_topic, num_suggestions)
            if ai_suggestions:
                return ai_suggestions[:num_suggestions]
        except Exception:
            pass  # Fall back to static suggestions
    
    return suggestions[:num_suggestions]


def _get_ai_suggestions(grade: str, current_topic: str, num_suggestions: int) -> list[dict]:
    """
    Get AI-powered topic suggestions.
    
    Args:
        grade: Grade level.
        current_topic: Current topic to avoid.
        num_suggestions: Number of suggestions.
    
    Returns:
        List of AI-generated suggestions.
    """
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return []
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("PRIMARY_MODEL", "gemini-2.0-flash"))
        
        prompt = f"""
Du er en norsk matematikklærer. Foreslå {num_suggestions} relevante matematikkemner 
for {grade} som passer til norsk læreplan (LK20).

{f'Unngå emner som ligner på: {current_topic}' if current_topic else ''}

Svar BARE med en JSON-liste i dette formatet:
[
  {{"topic": "Emnenavn", "description": "Kort beskrivelse", "difficulty": "lett|middels|vanskelig"}},
  ...
]

Ingen annen tekst, bare JSON.
"""
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up response
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        
        import json
        suggestions = json.loads(text)
        return suggestions
        
    except Exception:
        return []


def get_related_topics(topic: str, grade: str, num_related: int = 4) -> list[dict]:
    """
    Get topics related to the current topic.
    
    Args:
        topic: Current topic.
        grade: Grade level.
        num_related: Number of related topics to return.
    
    Returns:
        List of related topic dictionaries.
    """
    # Topic relationship map
    relationships = {
        "brøk": ["desimaltall", "prosent", "likninger"],
        "prosent": ["brøk", "desimaltall", "økonomi"],
        "likninger": ["algebra", "funksjoner", "ulikheter"],
        "funksjoner": ["lineære funksjoner", "andregradsfunksjoner", "grafer"],
        "geometri": ["areal", "volum", "trigonometri"],
        "trigonometri": ["pytagoras", "geometri", "vinkler"],
        "statistikk": ["sannsynlighet", "diagrammer", "gjennomsnitt"],
        "algebra": ["likninger", "faktorisering", "uttrykk"],
        "derivasjon": ["funksjoner", "optimering", "grenseverdier"],
        "integrasjon": ["areal", "volum", "differensiallikninger"],
    }
    
    related = []
    topic_lower = topic.lower()
    
    # Find matching relationships
    for key, values in relationships.items():
        if key in topic_lower:
            for v in values[:num_related]:
                related.append({
                    "topic": v.capitalize(),
                    "description": f"Relatert til {topic}",
                    "difficulty": "middels"
                })
    
    # If no specific relationships found, get general suggestions
    if not related:
        suggestions = get_topic_suggestions(grade, topic, num_related)
        related = suggestions[:num_related]
    
    return related[:num_related]


def get_prerequisite_topics(topic: str, grade: str) -> list[str]:
    """
    Get prerequisite topics that should be mastered before the current topic.
    
    Args:
        topic: Current topic.
        grade: Grade level.
    
    Returns:
        List of prerequisite topic names.
    """
    prerequisites = {
        "andregradslikninger": ["likninger", "faktorisering", "kvadratsetningene"],
        "trigonometri": ["pytagoras", "vinkler", "trekanter"],
        "derivasjon": ["funksjoner", "grenseverdier", "polynomer"],
        "integrasjon": ["derivasjon", "areal", "funksjoner"],
        "likningssett": ["likninger", "algebra", "koordinatsystemet"],
        "prosent": ["brøk", "desimaltall", "multiplikasjon"],
        "funksjoner": ["koordinatsystemet", "algebra", "grafer"],
    }
    
    topic_lower = topic.lower()
    
    for key, prereqs in prerequisites.items():
        if key in topic_lower:
            return prereqs
    
    return []

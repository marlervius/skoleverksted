#!/usr/bin/env python3
"""
Test script for generating a sample PDF without running the full server.
This allows quick iteration on PDF layout without API calls.

Usage:
    cd backend
    python test_pdf_generation.py
    
Output:
    test_output.pdf in current directory
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_service import create_lesson_pdf, format_language_exercises

# Sample content that mimics real AI output
SAMPLE_TEXT = """
Klimasoner er områder på jorden med lignende klima. Norge ligger i den tempererte sonen. 
Her er det fire årstider: vår, sommer, høst og vinter.

Den tempererte sonen har milde temperaturer. Det er ikke for varmt og ikke for kaldt. 
Mange mennesker bor i denne sonen fordi klimaet er behagelig.

Andre klimasoner inkluderer den tropiske sonen (nær ekvator) og den arktiske sonen (nær polene).
I den tropiske sonen er det varmt hele året. I den arktiske sonen er det kaldt og mye is.
"""

SAMPLE_WORKSHEET = """
a) VIKTIGE BEGREPER

Klimasone: Et område på jorden med lignende værforhold og temperaturer.
Temperert: Ikke for varmt og ikke for kaldt, behagelig temperatur.
Tropisk: Veldig varmt klima, nær ekvator.
Arktisk: Veldig kaldt klima, nær polene.
Årstider: Vår, sommer, høst og vinter.

b) LESEFORSTÅELSE

1. Hvor ligger Norge?
a) I den tropiske sonen
b) I den tempererte sonen *
c) I den arktiske sonen

2. Hvor mange årstider har Norge?
a) To årstider
b) Tre årstider
c) Fire årstider *

3. Hvordan er klimaet i den tempererte sonen?
a) Veldig varmt hele året
b) Veldig kaldt hele året
c) Mildt med fire årstider *

c) DISKUSJON

1. Hvilken klimasone kommer du fra? Hvordan er været der sammenlignet med Norge?

2. Hvilken årstid liker du best i Norge? Hvorfor?
"""

# Sample language exercises (simulating AI output)
SAMPLE_LANGUAGE_EXERCISES = {
    "grammar_tasks": [
        {
            "type": "ordklasser_sortering",
            "instruction": "Sorter ordene i riktig kategori (substantiv, verb eller adjektiv):",
            "items": [
                "Substantiv: klimasone, årstid, temperatur, mennesker",
                "Verb: ligger, bor, inkluderer",
                "Adjektiv: temperert, tropisk, arktisk, varm, kald"
            ]
        },
        {
            "type": "preposisjoner",
            "instruction": "Fyll inn riktig preposisjon (i, på, til, fra, med):",
            "items": [
                "Norge ligger ___ den tempererte sonen.",
                "Mange mennesker bor ___ denne sonen.",
                "Det er varmt hele året ___ den tropiske sonen."
            ]
        }
    ],
    "vocabulary_tasks": [
        {
            "type": "fyll_inn",
            "instruction": "Fyll inn det manglende ordet:",
            "items": [
                "Norge har fire ___: vår, sommer, høst og vinter.",
                "Den tempererte sonen har ___ temperaturer.",
                "I den arktiske sonen er det ___ og mye is."
            ]
        },
        {
            "type": "koble_ord",
            "instruction": "Koble begrepet med riktig definisjon:",
            "items": [
                "Klimasone: Et område med lignende vær",
                "Temperert: Mildt klima",
                "Tropisk: Varmt hele året",
                "Arktisk: Kaldt med is"
            ]
        },
        {
            "type": "staving",
            "instruction": "Fyll inn de manglende bokstavene:",
            "items": [
                "Klimas_ne (Klimasone)",
                "Temper_rt (Temperert)",
                "Tr_pisk (Tropisk)"
            ]
        }
    ],
    "syntax_tasks": [
        {
            "type": "stokk_setning",
            "instruction": "Sett ordene i riktig rekkefølge:",
            "items": [
                "ligger / Norge / den / i / sonen / tempererte",
                "varmt / er / Det / hele / året",
                "mennesker / Mange / i / bor / sonen / denne"
            ]
        }
    ]
}

def main():
    print("=" * 60)
    print("FOV PDF Generator - Test Script")
    print("=" * 60)
    
    options = {
        "deep_dive": False,
        "grammar_tasks": True,
        "vocabulary_tasks": True,
        "comprehension_tasks": True,
        "discussion_tasks": True,
        "teacher_key": False
    }
    
    print("\n📝 Generating PDF with sample content...")
    print(f"   Topic: Klimasoner")
    print(f"   Level: A2")
    print(f"   Options: {options}")
    
    try:
        pdf_bytes = create_lesson_pdf(
            content_text=SAMPLE_TEXT,
            worksheet_text=SAMPLE_WORKSHEET,
            topic="Klimasoner",
            level="A2",
            image_path=None,
            language_exercises=SAMPLE_LANGUAGE_EXERCISES,
            options=options
        )
        
        output_file = "test_output.pdf"
        with open(output_file, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"\n✅ PDF generated successfully!")
        print(f"   Output: {os.path.abspath(output_file)}")
        print(f"   Size: {len(pdf_bytes):,} bytes")
        
        # Try to open the PDF automatically
        import subprocess
        import platform
        
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(output_file)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", output_file])
            else:  # Linux
                subprocess.run(["xdg-open", output_file])
            print(f"\n📄 Opening PDF in default viewer...")
        except Exception as e:
            print(f"\n⚠️  Could not auto-open PDF: {e}")
            print(f"   Please open manually: {os.path.abspath(output_file)}")
            
    except Exception as e:
        print(f"\n❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

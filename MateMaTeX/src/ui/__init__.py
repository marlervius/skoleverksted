"""
UI module for MateMaTeX.
Contains styles, sidebar, configuration, and results components.
"""

from pathlib import Path
import hashlib

# Version for cache busting - increment when styles change
CSS_VERSION = "2.1.0"


def load_css() -> str:
    """Load the main CSS styles from file."""
    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def inject_styles():
    """Inject CSS styles into the Streamlit app with cache busting."""
    import streamlit as st
    
    css = load_css()
    if css:
        # Add version comment to force cache refresh
        css_hash = hashlib.md5(css.encode()).hexdigest()[:8]
        versioned_css = f"/* MateMaTeX CSS v{CSS_VERSION} hash:{css_hash} */\n{css}"
        st.markdown(f"<style>{versioned_css}</style>", unsafe_allow_html=True)

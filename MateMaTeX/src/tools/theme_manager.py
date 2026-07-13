"""
Theme Manager for MateMaTeX.
Provides light/dark theme switching functionality.
"""

from typing import Literal
from dataclasses import dataclass


ThemeMode = Literal["dark", "light", "auto"]


@dataclass
class ThemeColors:
    """Theme color scheme."""
    # Background colors
    bg_primary: str
    bg_secondary: str
    bg_card: str
    bg_hover: str
    
    # Text colors
    text_primary: str
    text_secondary: str
    text_muted: str
    
    # Accent colors
    accent_primary: str
    accent_secondary: str
    
    # Status colors
    success: str
    warning: str
    error: str
    info: str
    
    # Border colors
    border: str
    border_light: str


# Dark theme (refined - less intense amber)
DARK_THEME = ThemeColors(
    bg_primary="#0c0c14",
    bg_secondary="#10101a",
    bg_card="#16161f",
    bg_hover="#1c1c28",
    text_primary="#f1f5f9",
    text_secondary="#94a3b8",
    text_muted="#64748b",
    accent_primary="#f59e0b",
    accent_secondary="#d97706",
    success="#10b981",
    warning="#f59e0b",
    error="#f43f5e",
    info="#3b82f6",
    border="#2a2a3d",
    border_light="#3d3d52",
)

# Light theme
LIGHT_THEME = ThemeColors(
    bg_primary="#f8fafc",
    bg_secondary="#ffffff",
    bg_card="#ffffff",
    bg_hover="#f1f5f9",
    text_primary="#1e293b",
    text_secondary="#475569",
    text_muted="#64748b",
    accent_primary="#d97706",
    accent_secondary="#f59e0b",
    success="#059669",
    warning="#d97706",
    error="#dc2626",
    info="#2563eb",
    border="#e2e8f0",
    border_light="#cbd5e1",
)


def get_theme(mode: ThemeMode) -> ThemeColors:
    """Get theme colors for the specified mode."""
    if mode == "light":
        return LIGHT_THEME
    return DARK_THEME


def generate_theme_css(theme: ThemeColors) -> str:
    """Generate CSS variables for the theme."""
    return f"""
    <style>
        :root {{
            --bg-primary: {theme.bg_primary};
            --bg-secondary: {theme.bg_secondary};
            --bg-card: {theme.bg_card};
            --bg-hover: {theme.bg_hover};
            --text-primary: {theme.text_primary};
            --text-secondary: {theme.text_secondary};
            --text-muted: {theme.text_muted};
            --accent-primary: {theme.accent_primary};
            --accent-secondary: {theme.accent_secondary};
            --success: {theme.success};
            --warning: {theme.warning};
            --error: {theme.error};
            --info: {theme.info};
            --border: {theme.border};
            --border-light: {theme.border_light};
        }}
        
        /* Apply theme to Streamlit elements */
        .stApp {{
            background-color: var(--bg-primary) !important;
        }}
        
        .stApp > header {{
            background-color: var(--bg-secondary) !important;
        }}
        
        .stSidebar {{
            background-color: var(--bg-secondary) !important;
        }}
        
        .stSidebar > div {{
            background-color: var(--bg-secondary) !important;
        }}
        
        /* Text colors */
        .stApp, .stApp p, .stApp span, .stApp label {{
            color: var(--text-primary) !important;
        }}
        
        .stApp .stMarkdown {{
            color: var(--text-primary) !important;
        }}
        
        /* Card styling */
        .config-card {{
            background: var(--bg-card) !important;
            border-color: var(--border) !important;
        }}
        
        /* Primary action button only - template buttons styled in main CSS */
        button[data-testid="baseButton-primary"] {{
            background-color: var(--accent-primary) !important;
            color: var(--bg-primary) !important;
            border: none !important;
        }}
        
        button[data-testid="baseButton-primary"]:hover {{
            background-color: var(--accent-secondary) !important;
        }}
        
        /* Input styling */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div {{
            background-color: var(--bg-card) !important;
            color: var(--text-primary) !important;
            border-color: var(--border) !important;
        }}
        
        /* Expander styling */
        .streamlit-expanderHeader {{
            background-color: var(--bg-card) !important;
            color: var(--text-primary) !important;
        }}
        
        .streamlit-expanderContent {{
            background-color: var(--bg-secondary) !important;
        }}
        
        /* Checkbox styling */
        .stCheckbox > label {{
            color: var(--text-primary) !important;
        }}
        
        /* Slider styling */
        .stSlider > div > div > div {{
            background-color: var(--accent-primary) !important;
        }}
        
        /* Success/error messages */
        .stSuccess {{
            background-color: rgba(16, 185, 129, 0.1) !important;
            color: var(--success) !important;
        }}
        
        .stError {{
            background-color: rgba(239, 68, 68, 0.1) !important;
            color: var(--error) !important;
        }}
        
        .stWarning {{
            background-color: rgba(245, 158, 11, 0.1) !important;
            color: var(--warning) !important;
        }}
        
        .stInfo {{
            background-color: rgba(59, 130, 246, 0.1) !important;
            color: var(--info) !important;
        }}
    </style>
    """


def get_theme_toggle_html(current_mode: ThemeMode) -> str:
    """Generate HTML for theme toggle button."""
    is_dark = current_mode == "dark"
    icon = "🌙" if is_dark else "☀️"
    label = "Mørkt tema" if is_dark else "Lyst tema"
    
    return f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem;
        background: {'rgba(255,255,255,0.05)' if is_dark else 'rgba(0,0,0,0.05)'};
        border-radius: 8px;
        margin-bottom: 1rem;
    ">
        <span style="font-size: 1.25rem;">{icon}</span>
        <span style="color: {'#e2e8f0' if is_dark else '#475569'}; font-size: 0.85rem;">{label}</span>
    </div>
    """


def get_theme_switcher_styles() -> str:
    """Get CSS for theme switcher component."""
    return """
    <style>
        .theme-switcher {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            margin-bottom: 1rem;
        }
        
        .theme-toggle {
            position: relative;
            width: 50px;
            height: 26px;
            background: #374151;
            border-radius: 13px;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        
        .theme-toggle.light {
            background: #fbbf24;
        }
        
        .theme-toggle::after {
            content: '';
            position: absolute;
            top: 3px;
            left: 3px;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s ease;
        }
        
        .theme-toggle.light::after {
            transform: translateX(24px);
        }
        
        .theme-icons {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .theme-icon {
            font-size: 1rem;
            opacity: 0.5;
            transition: opacity 0.3s ease;
        }
        
        .theme-icon.active {
            opacity: 1;
        }
    </style>
    """

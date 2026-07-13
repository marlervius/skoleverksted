"""
GeoGebra Integration for MateMaTeX.
Embed interactive graphs and geometric constructions.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class GeoGebraGraph:
    """Represents a GeoGebra graph configuration."""
    id: str
    title: str
    width: int
    height: int
    commands: list[str]  # GeoGebra commands
    show_toolbar: bool
    show_menu: bool
    show_algebra_input: bool
    enable_right_click: bool
    enable_label_drags: bool


# Predefined graph templates
GRAPH_TEMPLATES = {
    "linear": {
        "title": "Lineær funksjon",
        "commands": [
            "f(x) = 2x + 1",
            "SetColor(f, \"#f0b429\")",
            "ShowLabel(f, true)",
        ],
        "description": "Graf av en lineær funksjon y = ax + b",
    },
    "quadratic": {
        "title": "Andregradsfunksjon",
        "commands": [
            "f(x) = x^2 - 2x - 3",
            "SetColor(f, \"#3b82f6\")",
            "ShowLabel(f, true)",
            "A = Root(f)",
            "B = Vertex(f)",
        ],
        "description": "Graf av en andregradsfunksjon med nullpunkter og toppunkt",
    },
    "trigonometric": {
        "title": "Trigonometriske funksjoner",
        "commands": [
            "f(x) = sin(x)",
            "g(x) = cos(x)",
            "SetColor(f, \"#f0b429\")",
            "SetColor(g, \"#3b82f6\")",
        ],
        "description": "Graf av sinus og cosinus",
    },
    "circle": {
        "title": "Sirkel",
        "commands": [
            "c = Circle((0,0), 3)",
            "SetColor(c, \"#10b981\")",
            "A = (3, 0)",
            "B = (0, 3)",
        ],
        "description": "Sirkel med sentrum i origo",
    },
    "triangle": {
        "title": "Trekant",
        "commands": [
            "A = (0, 0)",
            "B = (4, 0)",
            "C = (2, 3)",
            "poly1 = Polygon(A, B, C)",
            "SetColor(poly1, \"#8b5cf6\")",
        ],
        "description": "Trekant med hjørner A, B, C",
    },
    "pythagorean": {
        "title": "Pytagoras",
        "commands": [
            "A = (0, 0)",
            "B = (4, 0)",
            "C = (4, 3)",
            "poly1 = Polygon(A, B, C)",
            "a = Segment(A, B)",
            "b = Segment(B, C)",
            "c = Segment(A, C)",
            "SetCaption(a, \"a = 4\")",
            "SetCaption(b, \"b = 3\")",
            "SetCaption(c, \"c = 5\")",
        ],
        "description": "Rettvinklet trekant som illustrerer Pytagoras' setning",
    },
    "derivative": {
        "title": "Derivasjon",
        "commands": [
            "f(x) = x^3 - 3x",
            "f'(x) = Derivative(f)",
            "SetColor(f, \"#f0b429\")",
            "SetColor(f', \"#ef4444\")",
            "A = Point(f, 1)",
            "tangent = Tangent(A, f)",
        ],
        "description": "Funksjon med derivert og tangent",
    },
    "integral": {
        "title": "Integral",
        "commands": [
            "f(x) = x^2",
            "SetColor(f, \"#3b82f6\")",
            "a = Slider(0, 3, 0.1)",
            "Integral(f, 0, a)",
        ],
        "description": "Bestemt integral som areal under kurven",
    },
}


def get_geogebra_embed_html(
    commands: list[str],
    width: int = 600,
    height: int = 400,
    show_toolbar: bool = False,
    show_menu: bool = False,
    show_algebra_input: bool = False,
    enable_right_click: bool = True,
    material_id: Optional[str] = None
) -> str:
    """
    Generate HTML for embedding a GeoGebra applet.
    
    Args:
        commands: List of GeoGebra commands to execute.
        width: Width of the applet.
        height: Height of the applet.
        show_toolbar: Show the toolbar.
        show_menu: Show the menu bar.
        show_algebra_input: Show algebra input field.
        enable_right_click: Enable right-click menu.
        material_id: Optional GeoGebra material ID for embedding existing material.
    
    Returns:
        HTML string for embedding.
    """
    # Convert commands to JavaScript array
    commands_js = "[" + ", ".join([f'"{cmd}"' for cmd in commands]) + "]"
    
    # Generate unique ID
    import hashlib
    unique_id = hashlib.md5("".join(commands).encode()).hexdigest()[:8]
    
    if material_id:
        # Embed existing GeoGebra material
        return f"""
        <div style="
            border: 1px solid #374151;
            border-radius: 12px;
            overflow: hidden;
            margin: 1rem 0;
            background: white;
        ">
            <iframe 
                src="https://www.geogebra.org/material/iframe/id/{material_id}/width/{width}/height/{height}/border/888888/sfsb/true/smb/false/stb/false/stbh/false/ai/false/asb/false/sri/false/rc/false/ld/false/sdz/false/ctl/false"
                width="{width}"
                height="{height}"
                style="border: none;"
                allowfullscreen
            ></iframe>
        </div>
        """
    
    return f"""
    <div id="ggb-container-{unique_id}" style="
        border: 1px solid #374151;
        border-radius: 12px;
        overflow: hidden;
        margin: 1rem 0;
        background: white;
    ">
        <div id="ggb-element-{unique_id}" style="width: {width}px; height: {height}px;"></div>
    </div>
    
    <script src="https://www.geogebra.org/apps/deployggb.js"></script>
    <script>
    (function() {{
        var params = {{
            "appName": "graphing",
            "width": {width},
            "height": {height},
            "showToolBar": {str(show_toolbar).lower()},
            "showAlgebraInput": {str(show_algebra_input).lower()},
            "showMenuBar": {str(show_menu).lower()},
            "enableRightClick": {str(enable_right_click).lower()},
            "enableLabelDrags": true,
            "enableShiftDragZoom": true,
            "showResetIcon": true,
            "language": "nb",
            "country": "NO",
            "appletOnLoad": function(api) {{
                var commands = {commands_js};
                commands.forEach(function(cmd) {{
                    api.evalCommand(cmd);
                }});
            }}
        }};
        
        var applet = new GGBApplet(params, true);
        applet.inject('ggb-element-{unique_id}');
    }})();
    </script>
    """


def get_geogebra_link(commands: list[str]) -> str:
    """
    Generate a link to GeoGebra with pre-filled commands.
    
    Args:
        commands: List of GeoGebra commands.
    
    Returns:
        URL to GeoGebra.
    """
    # For simple cases, we can use the calculator link
    return "https://www.geogebra.org/graphing"


def create_graph_from_template(template_key: str) -> Optional[dict]:
    """
    Create a graph configuration from a template.
    
    Args:
        template_key: Key of the template to use.
    
    Returns:
        Graph configuration dictionary.
    """
    if template_key not in GRAPH_TEMPLATES:
        return None
    
    template = GRAPH_TEMPLATES[template_key]
    
    return {
        "title": template["title"],
        "commands": template["commands"],
        "description": template["description"],
    }


def parse_function_from_latex(latex: str) -> Optional[str]:
    """
    Parse a mathematical function from LaTeX and convert to GeoGebra syntax.
    
    Args:
        latex: LaTeX function definition.
    
    Returns:
        GeoGebra command string.
    """
    # Remove LaTeX formatting
    expr = latex.strip()
    
    # Common replacements
    replacements = [
        (r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)'),
        (r'\\sqrt\{([^}]+)\}', r'sqrt(\1)'),
        (r'\\sin', 'sin'),
        (r'\\cos', 'cos'),
        (r'\\tan', 'tan'),
        (r'\\ln', 'ln'),
        (r'\\log', 'log'),
        (r'\\pi', 'pi'),
        (r'\\cdot', '*'),
        (r'\^', '^'),
        (r'\\left\(', '('),
        (r'\\right\)', ')'),
    ]
    
    for pattern, replacement in replacements:
        expr = re.sub(pattern, replacement, expr)
    
    # Clean up remaining backslashes
    expr = re.sub(r'\\[a-zA-Z]+', '', expr)
    
    return expr


def extract_functions_from_content(latex_content: str) -> list[str]:
    """
    Extract mathematical functions from LaTeX content.
    
    Args:
        latex_content: Full LaTeX document content.
    
    Returns:
        List of GeoGebra commands for the functions.
    """
    functions = []
    
    # Pattern for function definitions like f(x) = ...
    function_pattern = r'([a-zA-Z])\s*\(\s*x\s*\)\s*=\s*([^$\n]+)'
    
    matches = re.finditer(function_pattern, latex_content)
    
    for match in matches:
        func_name = match.group(1)
        func_expr = match.group(2).strip()
        
        # Convert to GeoGebra syntax
        ggb_expr = parse_function_from_latex(func_expr)
        
        if ggb_expr:
            functions.append(f"{func_name}(x) = {ggb_expr}")
    
    return functions


def get_graph_latex_code(
    title: str,
    graph_id: str,
    width: int = 300,
    height: int = 200
) -> str:
    """
    Generate LaTeX code for including a GeoGebra graph reference.
    
    Args:
        title: Title of the graph.
        graph_id: GeoGebra material ID.
        width: Width in points.
        height: Height in points.
    
    Returns:
        LaTeX code string.
    """
    return f"""
\\begin{{figure}}[h]
    \\centering
    \\includegraphics[width={width}pt]{{geogebra_{graph_id}}}
    \\caption{{{title}}}
    \\label{{fig:ggb_{graph_id}}}
\\end{{figure}}
"""


def get_template_list() -> list[dict]:
    """Get list of available graph templates."""
    return [
        {
            "key": key,
            "title": template["title"],
            "description": template["description"],
        }
        for key, template in GRAPH_TEMPLATES.items()
    ]


def render_template_selector_html() -> str:
    """Render HTML for template selector."""
    options = ""
    for key, template in GRAPH_TEMPLATES.items():
        options += f"""
        <option value="{key}">{template['title']} - {template['description']}</option>
        """
    
    return f"""
    <div style="margin-bottom: 1rem;">
        <label style="color: #9090a0; font-size: 0.85rem; display: block; margin-bottom: 0.5rem;">
            Velg grafmal:
        </label>
        <select style="
            width: 100%;
            padding: 0.5rem;
            border-radius: 6px;
            border: 1px solid #374151;
            background: #1a1a2e;
            color: #e2e8f0;
        ">
            {options}
        </select>
    </div>
    """


# Common GeoGebra commands reference
GEOGEBRA_COMMAND_REFERENCE = {
    "functions": [
        {"command": "f(x) = x^2", "description": "Definer en funksjon"},
        {"command": "Derivative(f)", "description": "Derivert av f"},
        {"command": "Integral(f, a, b)", "description": "Bestemt integral"},
        {"command": "Root(f)", "description": "Nullpunkter"},
        {"command": "Extremum(f)", "description": "Ekstremalpunkter"},
        {"command": "Tangent(punkt, f)", "description": "Tangent i et punkt"},
    ],
    "geometry": [
        {"command": "Point(x, y)", "description": "Lag et punkt"},
        {"command": "Line(A, B)", "description": "Linje gjennom to punkter"},
        {"command": "Segment(A, B)", "description": "Linjestykke"},
        {"command": "Circle(sentrum, radius)", "description": "Sirkel"},
        {"command": "Polygon(A, B, C, ...)", "description": "Polygon"},
        {"command": "Perpendicular(punkt, linje)", "description": "Normal"},
    ],
    "transformations": [
        {"command": "Reflect(objekt, linje)", "description": "Speiling"},
        {"command": "Rotate(objekt, vinkel, punkt)", "description": "Rotasjon"},
        {"command": "Translate(objekt, vektor)", "description": "Translasjon"},
        {"command": "Dilate(objekt, faktor, punkt)", "description": "Forstørring"},
    ],
}

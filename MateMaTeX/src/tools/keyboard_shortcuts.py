"""
Keyboard Shortcuts for MateMaTeX.
Provides keyboard shortcut functionality for the Streamlit app.
"""


# Define keyboard shortcuts
SHORTCUTS = {
    "generate": {
        "key": "g",
        "modifiers": ["ctrl"],
        "description": "Generer innhold",
        "action": "generate",
    },
    "save_pdf": {
        "key": "s",
        "modifiers": ["ctrl"],
        "description": "Last ned PDF",
        "action": "save_pdf",
    },
    "edit": {
        "key": "e",
        "modifiers": ["ctrl"],
        "description": "Rediger LaTeX",
        "action": "edit",
    },
    "copy": {
        "key": "c",
        "modifiers": ["ctrl", "shift"],
        "description": "Kopier LaTeX",
        "action": "copy",
    },
    "new": {
        "key": "n",
        "modifiers": ["ctrl"],
        "description": "Ny generering",
        "action": "new",
    },
    "preview": {
        "key": "p",
        "modifiers": ["ctrl"],
        "description": "Forhåndsvis PDF",
        "action": "preview",
    },
    "favorite": {
        "key": "f",
        "modifiers": ["ctrl"],
        "description": "Legg til favoritt",
        "action": "favorite",
    },
    "help": {
        "key": "?",
        "modifiers": ["shift"],
        "description": "Vis hurtigtaster",
        "action": "help",
    },
}


def get_shortcut_js() -> str:
    """
    Generate JavaScript for keyboard shortcuts.
    
    Returns:
        JavaScript code as string.
    """
    return """
<script>
(function() {
    // Keyboard shortcut handler for MateMaTeX
    const shortcuts = {
        'ctrl+g': 'generate',
        'ctrl+s': 'save_pdf',
        'ctrl+e': 'edit',
        'ctrl+shift+c': 'copy',
        'ctrl+n': 'new',
        'ctrl+p': 'preview',
        'ctrl+f': 'favorite',
        'shift+?': 'help'
    };
    
    function getKeyCombo(e) {
        let combo = [];
        if (e.ctrlKey) combo.push('ctrl');
        if (e.shiftKey) combo.push('shift');
        if (e.altKey) combo.push('alt');
        combo.push(e.key.toLowerCase());
        return combo.join('+');
    }
    
    function triggerAction(action) {
        // Find and click the corresponding button
        const buttonSelectors = {
            'generate': '[data-testid="generate-button"], button:contains("Generer")',
            'save_pdf': '[data-testid="download-pdf"], button:contains("Last ned PDF")',
            'edit': '[data-testid="edit-button"], button:contains("Rediger")',
            'copy': '[data-testid="copy-button"], button:contains("Kopier")',
            'new': '[data-testid="new-button"], button:contains("Ny")',
            'preview': '[data-testid="preview-button"], button:contains("Forhåndsvis")',
            'favorite': '[data-testid="favorite-button"], button:contains("Favoritt")',
            'help': '[data-testid="help-button"]'
        };
        
        // Try to find button by text content
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent.toLowerCase();
            if (action === 'generate' && text.includes('generer')) {
                btn.click();
                return true;
            }
            if (action === 'save_pdf' && text.includes('pdf')) {
                btn.click();
                return true;
            }
            if (action === 'edit' && text.includes('rediger')) {
                btn.click();
                return true;
            }
            if (action === 'favorite' && text.includes('favoritt')) {
                btn.click();
                return true;
            }
        }
        
        // Show help modal for help action
        if (action === 'help') {
            showShortcutsHelp();
            return true;
        }
        
        return false;
    }
    
    function showShortcutsHelp() {
        // Create modal overlay
        const existing = document.getElementById('shortcuts-modal');
        if (existing) {
            existing.remove();
            return;
        }
        
        const modal = document.createElement('div');
        modal.id = 'shortcuts-modal';
        modal.innerHTML = `
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            " onclick="this.parentElement.remove()">
                <div style="
                    background: #1e293b;
                    border-radius: 16px;
                    padding: 2rem;
                    max-width: 400px;
                    color: white;
                    font-family: sans-serif;
                " onclick="event.stopPropagation()">
                    <h2 style="margin-top: 0; color: #f0b429;">⌨️ Hurtigtaster</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Ctrl+G</kbd></td><td>Generer innhold</td></tr>
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Ctrl+S</kbd></td><td>Last ned PDF</td></tr>
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Ctrl+E</kbd></td><td>Rediger LaTeX</td></tr>
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Ctrl+F</kbd></td><td>Legg til favoritt</td></tr>
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Ctrl+P</kbd></td><td>Forhåndsvis PDF</td></tr>
                        <tr><td style="padding: 0.5rem;"><kbd style="background: #374151; padding: 0.25rem 0.5rem; border-radius: 4px;">Shift+?</kbd></td><td>Vis denne hjelpen</td></tr>
                    </table>
                    <p style="text-align: center; margin-top: 1rem; color: #9ca3af; font-size: 0.875rem;">
                        Klikk utenfor eller trykk Escape for å lukke
                    </p>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Close on Escape
        const closeHandler = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', closeHandler);
            }
        };
        document.addEventListener('keydown', closeHandler);
    }
    
    // Main keyboard event listener
    document.addEventListener('keydown', function(e) {
        // Don't trigger if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        const combo = getKeyCombo(e);
        
        if (shortcuts[combo]) {
            e.preventDefault();
            triggerAction(shortcuts[combo]);
        }
    });
    
    console.log('MateMaTeX keyboard shortcuts loaded. Press Shift+? for help.');
})();
</script>
"""


def get_shortcuts_help_html() -> str:
    """
    Generate HTML help display for shortcuts.
    
    Returns:
        HTML string.
    """
    return """
<div style="
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border-radius: 12px;
    padding: 1.5rem;
    margin: 1rem 0;
">
    <h3 style="color: #f0b429; margin-top: 0;">⌨️ Hurtigtaster</h3>
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.75rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Ctrl+G</kbd>
            <span style="color: #e2e8f0;">Generer</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Ctrl+S</kbd>
            <span style="color: #e2e8f0;">Last ned PDF</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Ctrl+E</kbd>
            <span style="color: #e2e8f0;">Rediger</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Ctrl+F</kbd>
            <span style="color: #e2e8f0;">Favoritt</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Ctrl+P</kbd>
            <span style="color: #e2e8f0;">Forhåndsvis</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <kbd style="background: #374151; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-family: monospace;">Shift+?</kbd>
            <span style="color: #e2e8f0;">Hjelp</span>
        </div>
    </div>
</div>
"""


def get_shortcut_list() -> list[dict]:
    """
    Get list of shortcuts for display.
    
    Returns:
        List of shortcut dictionaries.
    """
    return [
        {"keys": "Ctrl+G", "action": "Generer innhold"},
        {"keys": "Ctrl+S", "action": "Last ned PDF"},
        {"keys": "Ctrl+E", "action": "Rediger LaTeX"},
        {"keys": "Ctrl+F", "action": "Legg til favoritt"},
        {"keys": "Ctrl+P", "action": "Forhåndsvis PDF"},
        {"keys": "Ctrl+N", "action": "Ny generering"},
        {"keys": "Shift+?", "action": "Vis hurtigtaster"},
    ]

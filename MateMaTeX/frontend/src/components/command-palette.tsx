"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Library,
  Clock,
  Settings,
  Search,
  LayoutTemplate,
  Share2,
} from "lucide-react";

interface CommandItem {
  id: string;
  label: string;
  category: string;
  icon: React.ReactNode;
  action: () => void;
}

const COMMANDS: CommandItem[] = [
  {
    id: "new-gen",
    label: "Ny generering",
    category: "Handlinger",
    icon: <Sparkles size={16} />,
    action: () => (window.location.href = "/"),
  },
  {
    id: "exercises",
    label: "Oppgavebank",
    category: "Navigasjon",
    icon: <Library size={16} />,
    action: () => (window.location.href = "/exercises"),
  },
  {
    id: "templates",
    label: "Maler",
    category: "Navigasjon",
    icon: <LayoutTemplate size={16} />,
    action: () => (window.location.href = "/templates"),
  },
  {
    id: "history",
    label: "Historikk",
    category: "Navigasjon",
    icon: <Clock size={16} />,
    action: () => (window.location.href = "/history"),
  },
  {
    id: "shared",
    label: "Delt med meg",
    category: "Navigasjon",
    icon: <Share2 size={16} />,
    action: () => (window.location.href = "/shared"),
  },
  {
    id: "settings",
    label: "Innstillinger",
    category: "Navigasjon",
    icon: <Settings size={16} />,
    action: () => (window.location.href = "/settings"),
  },
];

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = query
    ? COMMANDS.filter(
        (c) =>
          c.label.toLowerCase().includes(query.toLowerCase()) ||
          c.category.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS;

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action();
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, selectedIndex, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -20 }}
            transition={{ duration: 0.15 }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 z-50 w-full max-w-lg"
          >
            <div className="bg-surface border border-border rounded-xl shadow-soft-lg overflow-hidden">
              {/* Search */}
              <div className="flex items-center gap-3 px-4 border-b border-border">
                <Search size={16} className="text-text-muted flex-shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setSelectedIndex(0);
                  }}
                  placeholder="Søk i kommandoer..."
                  className="flex-1 py-3.5 bg-transparent text-sm outline-none placeholder:text-text-muted text-text-primary"
                />
                <kbd className="px-1.5 py-0.5 text-[10px] text-text-muted bg-surface-elevated rounded font-mono">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-64 overflow-y-auto py-2">
                {filtered.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-text-muted">
                    Ingen resultater for &ldquo;{query}&rdquo;
                  </div>
                ) : (
                  filtered.map((cmd, i) => (
                    <button
                      key={cmd.id}
                      onClick={() => {
                        cmd.action();
                        onClose();
                      }}
                      onMouseEnter={() => setSelectedIndex(i)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                        i === selectedIndex
                          ? "bg-accent-blue/10 text-accent-blue"
                          : "text-text-secondary hover:bg-surface-elevated"
                      }`}
                    >
                      <span className="flex-shrink-0 opacity-70">
                        {cmd.icon}
                      </span>
                      <span className="flex-1 text-left">{cmd.label}</span>
                      <span className="text-[10px] text-text-muted">
                        {cmd.category}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

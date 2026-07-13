"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Library,
  LayoutTemplate,
  Clock,
  Share2,
  Settings,
  User,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  PanelLeftClose,
  PanelLeft,
  Home,
  FolderKanban,
  PackagePlus,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const mainNav: NavItem[] = [
  { href: "/", label: "Oversikt", icon: <Home size={20} /> },
];

const commonSecondaryNav: NavItem[] = [
  { href: "/theme-pack", label: "Temapakke", icon: <PackagePlus size={20} /> },
  { href: "/projects", label: "Prosjekter", icon: <FolderKanban size={20} /> },
  { href: "/templates", label: "Maler", icon: <LayoutTemplate size={20} /> },
  { href: "/history", label: "Historikk", icon: <Clock size={20} /> },
  { href: "/shared", label: "Delt med meg", icon: <Share2 size={20} /> },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [isDark, setIsDark] = useState(true);
  const secondaryNav = pathname.startsWith("/matematikk") || pathname.startsWith("/exercises")
    ? [{ href: "/exercises", label: "Matteoppgaver", icon: <Library size={20} /> }, ...commonSecondaryNav]
    : commonSecondaryNav;

  // Init theme from DOM
  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  // Keyboard shortcut: Cmd/Ctrl + B
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        setCollapsed((c) => !c);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const toggleTheme = () => {
    const html = document.documentElement;
    html.classList.add("theme-transitioning");
    if (isDark) {
      html.classList.remove("dark");
      localStorage.setItem("theme", "light");
    } else {
      html.classList.add("dark");
      localStorage.setItem("theme", "dark");
    }
    setIsDark(!isDark);
    setTimeout(() => html.classList.remove("theme-transitioning"), 250);
  };

  const sidebarWidth = collapsed ? 64 : 280;

  return (
    <motion.aside
      animate={{ width: sidebarWidth }}
      transition={{ duration: 0.2, ease: "easeInOut" }}
      className="fixed left-0 top-0 bottom-0 z-40 flex flex-col border-r border-border bg-surface overflow-hidden"
      aria-label="Navigasjon"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-border flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent-blue/10 flex items-center justify-center flex-shrink-0">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path
              d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
              stroke="hsl(var(--accent-blue))"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="flex items-center gap-2 overflow-hidden whitespace-nowrap"
            >
              <span className="font-semibold tracking-tight text-text-primary">
                Skoleverksted
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-accent-blue/10 text-accent-blue font-medium">
                samler alt
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Main nav */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {mainNav.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={pathname === item.href}
            collapsed={collapsed}
          />
        ))}

        <div className="my-3 mx-2 border-t border-border" />

        {secondaryNav.map((item) => (
          <NavLink
            key={item.href}
            item={item}
            active={pathname === item.href}
            collapsed={collapsed}
          />
        ))}
      </nav>

      {/* Footer */}
      <div className="px-2 pb-3 space-y-1 flex-shrink-0 border-t border-border pt-3">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="nav-item w-full"
          aria-label={isDark ? "Bytt til lyst tema" : "Bytt til mørkt tema"}
        >
          <motion.div
            animate={{ rotate: isDark ? 0 : 180 }}
            transition={{ duration: 0.3 }}
            className="flex-shrink-0"
          >
            {isDark ? <Moon size={20} /> : <Sun size={20} />}
          </motion.div>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden whitespace-nowrap"
              >
                {isDark ? "Mørkt tema" : "Lyst tema"}
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        {/* Settings + privacy (grunnlov §2 / §9) */}
        <NavLink
          item={{
            href: "/personvern",
            label: "Personvern",
            icon: <User size={20} />,
          }}
          active={pathname === "/personvern"}
          collapsed={collapsed}
        />
        <NavLink
          item={{
            href: "/settings",
            label: "Innstillinger",
            icon: <Settings size={20} />,
          }}
          active={pathname === "/settings"}
          collapsed={collapsed}
        />

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="nav-item w-full"
          aria-label={collapsed ? "Utvid sidepanelet" : "Kollaps sidepanelet"}
        >
          <span className="flex-shrink-0">
            {collapsed ? <PanelLeft size={20} /> : <PanelLeftClose size={20} />}
          </span>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden whitespace-nowrap text-xs"
              >
                Kollaps (⌘B)
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  );
}

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <a
      href={item.href}
      className={`nav-item ${active ? "active" : ""}`}
      aria-current={active ? "page" : undefined}
      title={collapsed ? item.label : undefined}
    >
      <span className="flex-shrink-0">{item.icon}</span>
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            className="overflow-hidden whitespace-nowrap"
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>
    </a>
  );
}

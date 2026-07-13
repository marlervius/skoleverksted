"use client";

import Link from "next/link";
import { Shield, Calculator, Users } from "lucide-react";

/** Compact trust row for the generator landing page. */
export function TrustSignals() {
  return (
    <div className="flex flex-wrap justify-center gap-2 mb-8 max-w-2xl mx-auto">
      <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-border bg-surface-elevated/50 text-text-secondary">
        <Calculator size={13} className="text-accent-green" />
        SymPy-verifisert fasit
      </span>
      <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-border bg-surface-elevated/50 text-text-secondary">
        <Shield size={13} className="text-accent-blue" />
        Ingen elevdata
      </span>
      <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-border bg-surface-elevated/50 text-text-secondary">
        <Users size={13} className="text-accent-purple" />
        Lærer kontrollerer uverifiserbart
      </span>
      <Link
        href="/personvern#m1"
        className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border border-accent-green/30 bg-accent-green/5 text-accent-green hover:bg-accent-green/10 transition-colors"
      >
        M1 fasitdekning →
      </Link>
    </div>
  );
}

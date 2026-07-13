"use client";

import { motion } from "framer-motion";
import { Share2, ExternalLink } from "lucide-react";

export default function SharedPage() {
  return (
    <div className="max-w-content mx-auto">
      <div className="mb-8">
        <h1 className="font-display text-3xl mb-1">Delt med meg</h1>
        <p className="text-text-secondary text-sm">
          Genereringer og oppgavesett som andre har delt med deg
        </p>
      </div>

      {/* Empty state */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col items-center justify-center min-h-[50vh] text-center"
      >
        <Share2 size={48} className="text-text-muted opacity-20 mb-4" />
        <h2 className="font-display text-2xl mb-2">Ingenting delt ennå</h2>
        <p className="text-text-secondary text-sm mb-6 max-w-sm">
          Når noen deler en generering eller et oppgavesett med deg via en lenke,
          dukker det opp her.
        </p>
        <p className="text-xs text-text-muted flex items-center gap-1">
          <ExternalLink size={12} />
          Delte lenker åpnes direkte via /shared/[token]
        </p>
      </motion.div>
    </div>
  );
}

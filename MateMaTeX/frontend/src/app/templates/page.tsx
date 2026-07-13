"use client";

import Link from "next/link";
import { LayoutTemplate, CheckCircle2, ArrowRight } from "lucide-react";
import { materialTypeFromTemplate } from "@/lib/user-preferences";

const TEMPLATES = [
  {
    id: "worksheet",
    title: "Oppgaveark",
    description: "Kort teori + mange oppgaver + løsningsdel",
  },
  {
    id: "chapter",
    title: "Kapittel",
    description: "Teori, eksempler, progresjon og refleksjonsoppgaver",
  },
  {
    id: "exam",
    title: "Prøve",
    description: "Poengfordeling, nivådeling og vurderingsgrunnlag",
  },
];

export default function TemplatesPage() {
  return (
    <div className="max-w-content mx-auto">
      <div className="mb-6">
        <h1 className="font-display text-3xl mb-1">Maler</h1>
        <p className="text-text-secondary text-sm">
          Forhåndsvis standardstrukturer før du genererer nytt materiale.
        </p>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        {TEMPLATES.map((t) => (
          <div key={t.id} className="card flex flex-col">
            <div className="flex items-center gap-2 mb-2">
              <LayoutTemplate size={16} className="text-accent-blue" />
              <h2 className="text-sm font-semibold">{t.title}</h2>
            </div>
            <p className="text-xs text-text-secondary mb-3">{t.description}</p>
            <div className="space-y-1 text-xs text-text-secondary mb-4 flex-1">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 size={12} className="text-accent-green" />
                Typografi optimalisert for utskrift
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 size={12} className="text-accent-green" />
                Struktur tilpasset valgt materialetype
              </div>
            </div>
            <Link
              href={`/?template=${t.id}&materialType=${materialTypeFromTemplate(t.id)}`}
              className="btn-primary !py-2 text-xs inline-flex items-center justify-center gap-1.5"
            >
              Bruk mal
              <ArrowRight size={12} />
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

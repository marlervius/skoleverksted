import Link from "next/link";
import { M1CoverageCard } from "@/components/m1-coverage";

export const metadata = {
  title: "Personvern — Skoleverksted",
  description:
    "Hvordan Skoleverksted behandler lærerinput, lokale elevprofiler, kildetekst og generert innhold.",
};

export default function PersonvernPage() {
  return (
    <div className="max-w-2xl mx-auto prose prose-invert prose-sm">
      <h1 className="font-display text-3xl mb-2">Personvern</h1>
      <p className="text-text-secondary text-base not-prose mb-8">
        Skoleverksted er bygget etter{" "}
        <Link href="/" className="text-accent-blue hover:underline">
          produktets grunnlov
        </Link>
        : vi lager innhold for lærere og ber ikke om identifiserbare elevopplysninger.
      </p>

      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">Ikke legg inn identifiserbare elevdata</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          Skoleverksted trenger ikke elevnavn, besvarelser eller andre direkte identifikatorer.
          Fagmodulen kan lagre pseudonyme gruppeprofiler og interesser lokalt i nettleseren.
          Bruk derfor beskrivelser som «gruppe A» og aldri navn, fødselsdato eller helseopplysninger.
        </p>
        <p className="text-sm text-text-secondary leading-relaxed mt-3">
          Lokale utkast og profiler kan bli liggende på en delt maskin. Tøm nettleserdata etter bruk
          dersom enheten deles. Skoleinnlogging og sentral datastyring innføres først i en senere fase.
        </p>
      </section>

      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">Hva vi behandler</h2>
        <ul className="text-sm text-text-secondary space-y-2 list-disc pl-5">
          <li>
            <strong className="text-text-primary">Lærerens input</strong> — emne, trinn, kompetansemål og
            eventuelle notater og kildetekster du skriver inn for å styre genereringen. Dette sendes
            til AI-leverandøren (Google Gemini) når du starter generering.
          </li>
          <li>
            <strong className="text-text-primary">Generert innhold</strong> — LaTeX/PDF lagres midlertidig
            for nedlasting og kan caches for raskere gjentakelse av samme forespørsel.
          </li>
          <li><strong className="text-text-primary">Prosjekter, årsplaner og kompendier</strong> — planer, kapitteltekster, kildelister og godkjente dokumentfiler lagres i plattformdatabasen og det vedvarende fillageret til de arkiveres eller slettes.</li>
          <li>
            <strong className="text-text-primary">Tilgangsnøkkel</strong> — en signert, midlertidig nøkkel i
            nettleseren som viser at du har skrevet inn tilgangskoden. Piloten har ingen brukerkontoer og
            tar ikke imot betaling.
          </li>
        </ul>
      </section>

      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">Tilgang i pilotfasen</h2>
        <ul className="text-sm text-text-secondary space-y-2 list-disc pl-5">
          <li>
            Skoleverksted er i lukket pilot. Alle som har tilgangskoden bruker{" "}
            <strong className="text-text-primary">samme arbeidsområde</strong>: prosjekter, årsplaner,
            kompendier og jobbhistorikk er synlige for alle pilotbrukere. Legg derfor ikke inn noe du ikke vil
            dele med de andre i piloten.
          </li>
          <li>
            Når du logger inn, lagrer nettleseren en midlertidig tilgangsnøkkel (ikke selve koden) i opptil
            12 timer. På delte maskiner kan du bruke «Logg ut» under Innstillinger eller slå på privat økt.
          </li>
          <li>
            Personlige kontoer og skoleinnlogging kommer etter piloten. Generert innhold er et utkast som du
            alltid må kontrollere før det deles med elever.
          </li>
        </ul>
      </section>

      <M1CoverageCard />

      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">Verifisert fasit (SymPy)</h2>
        <p className="text-sm text-text-secondary leading-relaxed">
          Alt som kan verifiseres maskinelt, sjekkes med SymPy før levering. Oppgaver som ikke lar seg
          verifisere (f.eks. «vis at» eller modellering) merkes tydelig som «lærer kontroll anbefales» —
          vi later aldri som om de er automatisk kontrollert.
        </p>
      </section>

      <section className="card mb-6 not-prose">
        <h2 className="text-lg font-semibold mb-2">Det vi ikke gjør</h2>
        <ul className="text-sm text-text-secondary space-y-2 list-disc pl-5">
          <li>Retting eller vurdering av elevarbeid</li>
          <li>Elevinnlogging eller læringsplattform for elever</li>
          <li>Deling av elevdata med tredjeparter</li>
        </ul>
      </section>

      <p className="text-xs text-text-muted not-prose">
        Spørsmål? Kontakt Apexlab (Lervik KI-Tech ENK). Sist oppdatert oktober 2026.
      </p>
    </div>
  );
}

export function NorskPrivacy() {
  return (
    <article className="mx-auto max-w-2xl space-y-8 px-5 py-12 text-sm leading-7 text-stone-600 sm:px-8">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-accent-700">Norskverksted</p><h1 className="mt-3 font-display text-4xl text-accent-900">Personvern og tilgang</h1><p className="mt-4">Norskverksted hjelper lærere med å lage materiell til norskopplæringen. Bruk generelle beskrivelser av gruppen og undervisningen.</p></div>
      <section><h2 className="text-lg font-semibold text-stone-900">Ikke legg inn identifiserbare elevopplysninger</h2><p className="mt-2">Ikke skriv inn navn, fødselsdato, helseopplysninger eller andre opplysninger som kan identifisere deltakere. Dette gjelder også kildetekster og bilder du laster opp.</p></section>
      <section><h2 className="text-lg font-semibold text-stone-900">Hva som behandles</h2><p className="mt-2">Tema, fag, språknivå, instrukser og eventuell kildetekst sendes til KI-leverandøren Google Gemini når du starter generering. Generert innhold og filer behandles og lagres på serveren for kontroll og nedlasting. Bilder behandles når du velger en bildefunksjon.</p><p className="mt-2">Utkast og historikk lagres lokalt i nettleseren. På en delt maskin bør du tømme nettleserdata etter bruk. En nedlastet begrepstrener kan brukes uten nett. Eventuelle elevnotater i øvingsfilen sendes ikke til Norskverksted.</p></section>
      <section className="rounded-xl border border-accent-200 bg-white p-5">
        <h2 className="text-lg font-semibold text-stone-900">Tilgang under utprøving</h2>
        <p className="mt-2">Norskverksted er midlertidig åpent uten tilgangskode. Nye genereringer får egne, tilfeldige jobbadresser. Den som har en slik adresse kan åpne, godkjenne eller avbryte den aktuelle jobben. Behandle adressene som tilgangslenker og del dem bare med personer du vil gi tilgang.</p>
        <p className="mt-2">Tidligere materiale fra den lukkede piloten og de andre modulene i Skoleverksted krever fortsatt tilgangskode. Åpne genereringer kan ikke knyttes til private pilotprosjekter.</p>
        <p className="mt-2">Norskverksted bruker fortsatt samme backend som Skoleverksted. Piloten har ingen personlige kontoer og tar ikke imot betaling. Ikke legg inn fortrolige opplysninger.</p>
      </section>
      <section><h2 className="text-lg font-semibold text-stone-900">Kontroll før deling</h2><p className="mt-2">Generert innhold er utkast. Du må kontrollere og godkjenne materialet før det deles med deltakere. Endringer i innhold eller kilder krever ny kontroll og godkjenning før endelig eksport.</p></section>
      <p className="border-t border-stone-200 pt-5 text-xs">Ansvarlig: Apexlab / Lervik KI-Tech ENK. Sist oppdatert oktober 2026.</p>
    </article>
  );
}

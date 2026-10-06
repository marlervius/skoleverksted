# Sjekkliste før lærerpilot

Gjelder en lukket pilot med noen få navngitte lærere og én felles tilgangskode.
Dommen i [PILOT_GO_NO_GO.md](PILOT_GO_NO_GO.md) er fortsatt `REJECTED` til punkt 1
under er gjort. Hakene under er eierens handlinger; koden dekker resten.

## Må gjøres av eieren før første lærer inviteres

1. **Faglig sluttvurdering.** La en navngitt lærer vurdere én ferdig, godkjent fil
   fra hver modul (Fag, Norsk, Matematikk) på faglig korrekthet, kilder, språk,
   nivå og layout. Oppdater `PILOT_GO_NO_GO.md` med resultatet.
2. **Tilgangskode.** Sett `APP_PASSWORD` i Render til en lang, tilfeldig verdi
   (minst 12 tegn) som ikke brukes andre steder. Å endre den logger alle ut, så
   den er også bryteren hvis koden lekker. Del den bare med pilotlærerne.
3. **Smoke-hemmelighet.** Legg samme verdi inn som GitHub-hemmeligheten
   `SMOKE_ACCESS_CODE` så produksjonssmoken også dekker innlogget bruk. Oppdater
   den hver gang koden endres.
4. **Kostnadsgrense hos Google.** Sett budsjettvarsel og kvotebegrensning på
   `GOOGLE_API_KEY`-prosjektet. Kontroller at nøkkelen hører til en betalt tjeneste
   med vilkår som ikke bruker lærernes innhold til modelltrening.
5. **Backup.** Åpne disken `skoleverksted-data` i Render og bekreft at daglige
   snapshots er på og hvor lenge de beholdes. Øv én gjenoppretting til en kopi.
6. **Overvåking.** Legg en gratis ekstern sjekk (for eksempel UptimeRobot) på
   `https://skoleverksted-api.onrender.com/health/ready` med varsel til deg.
   GitHub-varsler om feilede kjøringer av «Production smoke» skal gå til e-post.
7. **Brief lærerne**: det er en pilot, alle ser hverandres prosjekter, ingen
   elevnavn eller identifiserbare opplysninger, og alt generert innhold er et
   utkast som kontrolleres før det deles. Dette står også på `/personvern`.

## Kontroll etter hver deploy

* «Production smoke» i GitHub Actions er grønn (readiness, sider, anonyme kall
  avvist, og innlogget sti hvis `SMOKE_ACCESS_CODE` er satt).
* Logg inn i nettleseren, åpne én modul og kontroller at et prosjekt kan lagres.

## Tilbakerulling og nødstopp

* **Kode lekket:** endre `APP_PASSWORD` i Render. Alle token er ugyldige umiddelbart.
* **Feil release:** Render → tjenesten → Events → Rollback til forrige deploy.
* **Stoppe alt:** sett `APP_PASSWORD` til en ny verdi du ikke deler.

## Kjente begrensninger i piloten

* Delt arbeidsområde: alle med koden ser og kan endre alt. Kontoer per lærer og
  skolepålogging er utsatt til etter piloten.
* Tokenet kan stå i `?access_token=` på nedlastinger og strømmer og dermed i
  serverlogger. Det utløper etter høyst 12 timer og avslører ikke koden.
* Innloggingsvernet ligger i minnet og nullstilles ved restart. Klientadresser
  kommer fra proxy-headere og kan forfalskes; den globale grensen er det som
  faktisk setter taket.
* Én Render-instans med SQLite på disk: ingen horisontal skalering, og en kort
  nedetid ved hver deploy.

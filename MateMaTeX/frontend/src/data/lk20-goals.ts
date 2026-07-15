/**
 * Utvalgte kompetansemål i matematikk (LK20-stil) gruppert etter klassetrinn.
 * Brukes til søk og valg i veiviseren — ikke en full offisiell kopi av læreplanen.
 */

export interface CompetencyGoal {
  code: string;
  text: string;
}

export const COMPETENCY_GOALS_BY_GRADE: Record<string, CompetencyGoal[]> = {
  "1.-4. trinn": [
    { code: "MAT01-01", text: "Telle, dele inn og gruppere mengder og utforske tallmønster" },
    { code: "MAT01-02", text: "Utforske og bruke addisjon og subtraksjon i praktiske situasjoner" },
    { code: "MAT01-03", text: "Utforske og beskrive enkle symmetrier og mønster i geometriske figurer" },
    { code: "MAT01-04", text: "Måle og sammenligne lengde, masse, volum og tid i praktiske aktiviteter" },
  ],
  "5.-7. trinn": [
    { code: "MAT05-01", text: "Utforske og bruke brøk, desimaltall og prosent i praktiske sammenhenger" },
    { code: "MAT05-02", text: "Løse likninger og ulikheter og bruke variabler i enkle uttrykk" },
    { code: "MAT05-03", text: "Utforske og argumentere for egenskaper ved to- og tredimensjonale figurer" },
    { code: "MAT05-04", text: "Samle, sortere og vurdere data og presentere med passende diagrammer" },
  ],
  "8. trinn": [
    { code: "MAT08-01", text: "Utforske og generalisere mønster med tall og algebraiske uttrykk" },
    { code: "MAT08-02", text: "Løse likninger og ulikheter og modellere praktiske problemer" },
    { code: "MAT08-03", text: "Utforske og bruke funksjoner til å beskrive sammenhenger" },
    { code: "MAT08-04", text: "Beregne og forklare areal og volum i sammensatte figurer" },
  ],
  "9. trinn": [
    { code: "MAT09-01", text: "Modellere situasjoner med lineære funksjoner og likningssett" },
    { code: "MAT09-02", text: "Bruke Pytagoras’ setning og trigonometri i måling og problemløsning" },
    { code: "MAT09-03", text: "Planlegge og gjennomføre statistiske undersøkelser og vurdere resultater" },
    { code: "MAT09-04", text: "Beregne og tolke sannsynlighet i enkle situasjoner" },
  ],
  "10. trinn": [
    { code: "MAT10-01", text: "Utforske, forstå og bruke polynomfunksjoner og rasjonale uttrykk" },
    { code: "MAT10-02", text: "Løse likninger og ulikheter analytisk og grafisk" },
    { code: "MAT10-03", text: "Modellere og analysere eksponentielle og logaritmiske sammenhenger" },
    { code: "MAT10-04", text: "Beregne sannsynlighet og bruke kombinatorikk i problemløsning" },
  ],
  "VG1 1T": [
    { code: "1T-01", text: "Manipulere algebraiske uttrykk, potenser og røtter" },
    { code: "1T-02", text: "Løse likninger, ulikheter og likningssett med flere ukjente" },
    { code: "1T-03", text: "Utforske, analysere og tegne ulike typer funksjoner" },
    { code: "1T-04", text: "Bruke derivasjon til å finne stigningstall og ekstremalpunkter" },
  ],
  "VG1 1P": [
    { code: "1P-01", text: "Beregne prosent, vekstfaktor og rente i praktiske økonomiske sammenhenger" },
    { code: "1P-02", text: "Modellere situasjoner med lineære og enkle eksponentialfunksjoner" },
    { code: "1P-03", text: "Samle og presentere data og vurdere trender og usikkerhet" },
    { code: "1P-04", text: "Løse problemer med areal, volum og enkel trigonometri" },
  ],
  "VG2 2P": [
    { code: "2P-01", text: "Modellere og analysere funksjoner i praktiske kontekster" },
    { code: "2P-02", text: "Bruke statistikk og sannsynlighet til å vurdere påstander" },
    { code: "2P-03", text: "Planlegge undersøkelser og tolke resultater kritisk" },
  ],
  "VG2 R1": [
    { code: "R1-01", text: "Beherske algebra med rasjonale og irrasjonale uttrykk" },
    { code: "R1-02", text: "Derivere og integrere polynom- og enkle sammensatte funksjoner" },
    { code: "R1-03", text: "Løse likninger og ulikheter med logaritmer og eksponentialfunksjoner" },
    { code: "R1-04", text: "Bruke vektorer i planet til geometri og fysikk" },
  ],
  "VG3 R2": [
    { code: "R2-01", text: "Integrere rasjonale og trigonometriske uttrykk" },
    { code: "R2-02", text: "Løse enkle differensiallikninger og modellere vekst" },
    { code: "R2-03", text: "Bruke vektorer i rommet til avstand, vinkel og plan" },
  ],
};

export function goalsForGrade(grade: string): CompetencyGoal[] {
  return COMPETENCY_GOALS_BY_GRADE[grade] ?? [];
}

export function searchGoals(grade: string, query: string): CompetencyGoal[] {
  const q = query.trim().toLowerCase();
  const list = goalsForGrade(grade);
  if (!q) return list;
  return list.filter(
    (g) =>
      g.code.toLowerCase().includes(q) || g.text.toLowerCase().includes(q)
  );
}

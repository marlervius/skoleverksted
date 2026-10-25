import { redirect } from "next/navigation";
import Norskverksted from "@/features/norsk/app/page";
import { isLanguageSite } from "@/lib/site-edition";

export const metadata = { title: "Lag læringsark — Norskverksted" };

export default function LanguageWorkspace() {
  if (!isLanguageSite()) redirect("/norsk");
  return <Norskverksted />;
}

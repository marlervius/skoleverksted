import PlatformHome from "@/components/platform-home";
import { NorskHome } from "@/components/norsk-home";
import { isLanguageSite } from "@/lib/site-edition";

export default function HomePage() {
  return isLanguageSite() ? <NorskHome /> : <PlatformHome />;
}

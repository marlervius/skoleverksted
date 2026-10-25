import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { isLanguageSite, languageRoute } from "@/lib/site-edition";

/** Select the standalone product's pages; backend access gates remain authoritative. */
export function middleware(request: NextRequest) {
  if (isLanguageSite()) {
    const route = languageRoute(request.nextUrl.pathname);
    if (route === "workspace") {
      const destination = request.nextUrl.clone();
      destination.pathname = "/verksted";
      return NextResponse.redirect(destination);
    }
    if (route === "missing") {
      return new NextResponse("Denne siden finnes ikke i Norskverksted.", {
        status: 404,
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      });
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|icon.svg).*)"],
};

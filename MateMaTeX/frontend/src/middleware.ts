import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * No auth middleware — app runs without Supabase or other IdP.
 * Add your own checks here if needed.
 */
export function middleware(_request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};

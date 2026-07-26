import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { join } from "path";

const SYMBOL_RE = /^[A-Z0-9]{2,12}$/;
const ALLOWED_FILES = ["profile", "reports", "dividends", "foreign-trading"] as const;
type FileName = (typeof ALLOWED_FILES)[number];

export async function GET(req: NextRequest) {
  const symbol = req.nextUrl.searchParams.get("symbol")?.toUpperCase()?.trim();
  const file = req.nextUrl.searchParams.get("file") as FileName | null;

  if (!symbol || !SYMBOL_RE.test(symbol)) {
    return NextResponse.json({ error: "Invalid symbol" }, { status: 400 });
  }
  if (!file || !ALLOWED_FILES.includes(file)) {
    return NextResponse.json(
      { error: `Invalid file. Allowed: ${ALLOWED_FILES.join(", ")}` },
      { status: 400 },
    );
  }

  const filePath = join(
    process.cwd(),
    "public",
    "stock-data",
    symbol,
    `${file}.json`,
  );

  try {
    const raw = await readFile(filePath, "utf-8");
    const data = JSON.parse(raw);
    return NextResponse.json(data, {
      headers: { "Cache-Control": "public, max-age=3600" },
    });
  } catch {
    return NextResponse.json({ error: "Not found", symbol, file }, { status: 404 });
  }
}

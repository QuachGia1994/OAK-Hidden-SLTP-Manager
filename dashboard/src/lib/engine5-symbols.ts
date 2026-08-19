import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const cwd = process.cwd();
const scopePath = [
  resolve(cwd, "engine5-symbols.json"),
  resolve(cwd, "dashboard", "engine5-symbols.json"),
].find(existsSync);

if (!scopePath) throw new Error("Engine5 symbol scope configuration is missing");

const engine5SymbolScope = JSON.parse(readFileSync(scopePath, "utf8")) as {
  active?: unknown[];
  temporarilyDisabled?: unknown[];
};

export const ENGINE5_ACTIVE_SYMBOLS = Object.freeze(
  (engine5SymbolScope.active || []).map((symbol) => String(symbol).trim().toUpperCase()).filter(Boolean),
);

const ACTIVE_SYMBOL_SET = new Set(ENGINE5_ACTIVE_SYMBOLS);

export function isActiveEngine5Symbol(symbol: string): boolean {
  return ACTIVE_SYMBOL_SET.has(String(symbol || "").trim().toUpperCase());
}

export function filterActiveEngine5Tables<T extends { base: string }>(tables: readonly T[]): T[] {
  return tables.filter((table) => isActiveEngine5Symbol(table.base));
}

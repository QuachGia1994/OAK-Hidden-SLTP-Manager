import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("./ctrader-vault.ts", import.meta.url), "utf8");
const statusSource = readFileSync(new URL("../app/api/ctrader/status/route.ts", import.meta.url), "utf8");

test("cTrader vault requires a dedicated encryption key", () => {
  const vaultMaterial = source.match(/function vaultMaterial\(\): string \{([\s\S]*?)\n\}/)?.[1] || "";
  assert.match(vaultMaterial, /process\.env\.OAK_CTRADER_VAULT_KEY/);
  assert.doesNotMatch(vaultMaterial, /DASHBOARD_API_KEY/);
  assert.match(vaultMaterial, /OAK_CTRADER_VAULT_KEY is required/);
});

test("legacy API-key ciphertext is read only for one-way migration", () => {
  assert.match(source, /function legacyVaultMaterial/);
  assert.match(source, /const record = decryptWithMaterial\(serialized, legacy\)/);
  assert.match(source, /await redis\.set\(VAULT_KEY, encrypt\(record\)\)/);
  assert.doesNotMatch(source, /createCipheriv\([^\n]*DASHBOARD_API_KEY/);
});

test("cTrader status exposes dedicated vault-key readiness without the key value", () => {
  assert.match(statusSource, /vaultKeyConfigured: Boolean\(process\.env\.OAK_CTRADER_VAULT_KEY\)/);
  assert.doesNotMatch(statusSource, /OAK_CTRADER_VAULT_KEY\s*[,}]/);
});

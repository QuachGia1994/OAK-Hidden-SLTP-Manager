export function isSignalEvidenceV3(ev) {
  if (!ev || typeof ev !== "object") return false;
  return ev.evidence_schema_version === 9 || ev.evidence_schema_version === 10;
}

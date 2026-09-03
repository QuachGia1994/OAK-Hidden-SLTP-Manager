import Image from "next/image";

export function OAKLoadingSplash({ label = "Loading local H1…" }: { label?: string }) {
  return (
    <div className="oak-loading-splash" role="status" aria-live="polite" aria-busy="true">
      <Image src="/oak-app-icon.png" alt="" width={104} height={104} priority className="oak-loading-logo" />
      <b>OAK GATEKEEPER</b>
      <span className="oak-loading-spinner" aria-hidden="true" />
      <small>{label}</small>
    </div>
  );
}

import { OAKLoadingSplash } from "@/components/OAKLoadingSplash";

export default function EngineLoading() {
  return (
    <div className="page-shell oak-loading-route" data-loading-scope="engine">
      <OAKLoadingSplash scope="engine" />
    </div>
  );
}

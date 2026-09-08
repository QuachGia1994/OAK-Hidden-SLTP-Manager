import { OAKLoadingSplash } from "@/components/OAKLoadingSplash";

export default function HistoryLoading() {
  return (
    <div className="page-shell oak-loading-route" data-loading-scope="history">
      <OAKLoadingSplash scope="history" />
    </div>
  );
}

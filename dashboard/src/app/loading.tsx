import { OAKLoadingSplash } from "@/components/OAKLoadingSplash";

export default function AppLoading() {
  return (
    <div className="page-shell oak-loading-route" data-loading-scope="app">
      <OAKLoadingSplash />
    </div>
  );
}

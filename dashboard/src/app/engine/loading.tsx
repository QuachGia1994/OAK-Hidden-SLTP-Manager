export default function EngineLoading() {
  return (
    <div className="page-shell">
      <div className="oak-engine-screen oak-engine-skeleton" aria-busy="true" aria-label="Loading Engine 5">
        <header className="oak-command-strip">
          <div className="oak-skeleton-copy"><span /><b /></div>
          <div className="oak-command-meta"><span /><span /><span /></div>
        </header>
        <section className="oak-skeleton-access"><span /><div><b /><i /></div></section>
        <div className="oak-skeleton-grid">
          <section><header /><div /></section>
          <section><header /><div /></section>
        </div>
      </div>
    </div>
  );
}

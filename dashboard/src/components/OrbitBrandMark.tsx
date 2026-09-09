export function OrbitBrandMark({ label = "H1", showGrid = false }: { label?: string; showGrid?: boolean }) {
  return (
    <div className="engine-core-visual" aria-hidden="true">
      {showGrid && <div className="engine-core-grid" />}
      <div className="engine-core-ring engine-core-ring-outer" />
      <div className="engine-core-ring engine-core-ring-mid" />
      <div className="engine-core-ring engine-core-ring-inner" />
      <div className="engine-core-orbit engine-core-orbit-horizontal"><span /><span /><span /></div>
      <div className="engine-core-orbit engine-core-orbit-vertical"><span /><span /></div>
      <div className="engine-core-orbit engine-core-orbit-diagonal"><span /><span /></div>
      <div className="engine-core-sphere">
        {[0, 1, 2, 3, 4, 5].map((meridian) => <span className="engine-core-meridian" key={meridian} />)}
        <span className="engine-core-equator" />
      </div>
      <div className="engine-core-center"><b>{label}</b></div>
    </div>
  );
}

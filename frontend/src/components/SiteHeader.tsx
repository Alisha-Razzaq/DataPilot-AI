interface SiteHeaderProps {
  filename?: string | null;
}

export function SiteHeader({ filename }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            DP
          </span>
          <div>
            <h1 className="brand-name">DataPilot</h1>
            <p className="brand-tagline">CSV analysis with Python as the source of truth</p>
          </div>
        </div>
        <p className="header-status">
          {filename ? (
            <>
              Current dataset <strong>{filename}</strong>
            </>
          ) : (
            "No dataset loaded"
          )}
        </p>
      </div>
    </header>
  );
}

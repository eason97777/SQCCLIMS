type TopbarProps = {
  title: string;
  eyebrow: string;
  onOpenMenu: () => void;
};

export function Topbar({ title, eyebrow, onOpenMenu }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <button
          className="drawer-trigger ghost-button"
          type="button"
          aria-label="打开导航"
          onClick={onOpenMenu}
        >
          ☰
        </button>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
        </div>
      </div>
    </header>
  );
}

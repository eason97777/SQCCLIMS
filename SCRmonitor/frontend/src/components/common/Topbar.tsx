import { useAuth } from "../../stores/authStore";

type TopbarProps = {
  title: string;
  eyebrow: string;
  onOpenMenu: () => void;
};

const ROLE_LABELS: Record<string, string> = {
  viewer: "查看者",
  operator: "操作员",
  admin: "管理员",
};

export function Topbar({ title, eyebrow, onOpenMenu }: TopbarProps) {
  const { authEnabled, authenticated, role, logout } = useAuth();
  const showAuth = authEnabled && authenticated;

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
      {showAuth ? (
        <div className="topbar-auth">
          <span className="topbar-role">
            {role ? ROLE_LABELS[role] ?? role : "已登录"}
          </span>
          <button
            className="ghost-button topbar-logout"
            type="button"
            onClick={logout}
          >
            退出登录
          </button>
        </div>
      ) : null}
    </header>
  );
}

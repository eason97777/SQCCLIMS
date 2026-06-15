import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../utils/constants";

type SidebarProps = {
  activePath: string;
  open: boolean;
  onClose: () => void;
};

export function Sidebar({ activePath, open, onClose }: SidebarProps) {
  return (
    <aside className={`sidebar${open ? " open" : ""}`} aria-hidden={!open}>
      <div className="brand">
        <div className="brand-mark">ST</div>
        <div>
          <h1>样品测试信息管理中心</h1>
          <span>Sample Test Center</span>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="主导航">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.path === "/"
              ? activePath === "/"
              : activePath.startsWith(item.path);

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className="nav-link-reset"
              onClick={onClose}
            >
              <button
                type="button"
                className={`nav-tab${isActive ? " active" : ""}`}
              >
                {item.label}
              </button>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}

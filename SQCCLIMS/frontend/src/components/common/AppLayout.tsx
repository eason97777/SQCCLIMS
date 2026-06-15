import { useState, type PropsWithChildren } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

type AppLayoutProps = PropsWithChildren<{
  activePath: string;
  title: string;
  eyebrow: string;
}>;

export function AppLayout({
  activePath,
  title,
  eyebrow,
  children,
}: AppLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className={`app-shell${drawerOpen ? " drawer-open" : ""}`}>
      <button
        className="drawer-backdrop"
        type="button"
        aria-label="关闭导航"
        onClick={() => setDrawerOpen(false)}
      />
      <Sidebar
        activePath={activePath}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
      <main className="workspace">
        <Topbar
          title={title}
          eyebrow={eyebrow}
          onOpenMenu={() => setDrawerOpen(true)}
        />
        {children}
      </main>
    </div>
  );
}

import { Outlet, useLocation } from "react-router-dom";
import { AppLayout } from "./components/common/AppLayout";
import { VIEW_META } from "./utils/constants";

export default function App() {
  const location = useLocation();
  const meta = VIEW_META[location.pathname] ?? VIEW_META["/"];

  return (
    <AppLayout
      activePath={location.pathname}
      title={meta.title}
      eyebrow={meta.eyebrow}
    >
      <Outlet />
    </AppLayout>
  );
}

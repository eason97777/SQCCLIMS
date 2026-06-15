import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { AuthProvider, useAuth } from "./stores/authStore";
import { Login } from "./components/auth/Login";
import "./styles.css";

function Root() {
  const { status, gated } = useAuth();

  if (status === "loading") {
    return null;
  }

  if (gated) {
    return <Login />;
  }

  return <RouterProvider router={router} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <Root />
    </AuthProvider>
  </React.StrictMode>,
);

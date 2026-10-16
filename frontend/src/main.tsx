import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthRoot } from "./AuthRoot";
import { applyTheme, storedTheme } from "./theme";
import "./styles.css";
import "./research-workspace.css";

applyTheme(storedTheme());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthRoot />
  </StrictMode>,
);

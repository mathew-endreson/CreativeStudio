import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Inter, bundled with the UI (no network): the fallback when the OS has no SF Pro
import "@fontsource-variable/inter";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

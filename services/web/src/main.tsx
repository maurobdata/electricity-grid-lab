import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";

import App from "@/App";
import "@/index.css";

// Auto-update rather than prompt. This is a lab: nobody wants a "new version available"
// dialog in the middle of a demo, and there is no user state to lose on reload.
registerSW({ immediate: true });

const container = document.getElementById("root");
if (!container) throw new Error("#root is missing from index.html");

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

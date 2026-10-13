import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { bootstrapLanguage, changeLanguage, initialProvisionalLanguage } from "./i18n";
import "./styles.css";
import "./shell.css";
import "./ui.css";

async function renderApp() {
  try {
    await bootstrapLanguage();
  } catch {
    try {
      await changeLanguage(initialProvisionalLanguage);
    } catch {
      // The initialized provisional locale remains safe when recovery fails.
    }
  }

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void renderApp();

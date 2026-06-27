import { createElement } from "react";
import { createRoot } from "react-dom/client";
import { client } from "client/api/truescrub.js";
import { AccoladesPage } from "client/pages/AccoladesPage.js";

declare global {
  interface Window {
    TrueScrubAPI: {
      client: typeof client;
    };
  }
}

window.TrueScrubAPI = {client};

createRoot(document.getElementById("react-root")!).render(
    createElement(AccoladesPage)
);

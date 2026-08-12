import {createElement} from "react";
import {createRoot} from "react-dom/client";
import {TrueScrubClient} from "client/TrueScrubClient.js";

const root = document.getElementById("react-root");
if (root) {
  createRoot(root).render(createElement(TrueScrubClient));
}

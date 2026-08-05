import React from "react";
import { createRoot } from "react-dom/client";
import Marquee from "./Marquee.jsx";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Marquee />
  </React.StrictMode>
);

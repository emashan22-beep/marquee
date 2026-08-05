import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // GitHub Pages serves from /<repo-name>/. Set this to "/marquee/" (or
  // whatever you name the repo). If you use a custom domain, set it to "/".
  base: "/marquee/",
});

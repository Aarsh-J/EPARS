import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5174 }, // 5174 so it can run next to the main EPARS UI on 5173
});

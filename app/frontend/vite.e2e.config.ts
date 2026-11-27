// Used only by app/e2e: `vite preview` of the built bundle, proxying /api to the fake-provider API.
import { defineConfig } from "vite";

const target = process.env.E2E_API_URL ?? "http://127.0.0.1:18765";

export default defineConfig({
  preview: {
    proxy: { "/api": target },
  },
});

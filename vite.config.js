import react from "@vitejs/plugin-react";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { defineConfig } from "vite";

import {
  parseMultipartFile,
  readRequestBody,
  renderGeneratedComponent,
  sendJson,
  toComponentName,
} from "./src/lib/server-utils.mjs";

function localApiPlugin() {
  return {
    name: "local-builder-api",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        try {
          if (request.method === "POST" && request.url === "/api/files") {
            const body = await readRequestBody(request, 50_000_000);
            const file = parseMultipartFile(body, request.headers["content-type"]);
            const outputDir = join(process.cwd(), "files");
            const outputPath = join(outputDir, file.filename);

            await mkdir(outputDir, { recursive: true });
            await writeFile(outputPath, file.data);

            sendJson(response, 200, { name: file.filename, path: `files/${file.filename}` });
            return;
          }

          if (request.method === "POST" && request.url === "/api/components") {
            const body = await readRequestBody(request);
            const component = JSON.parse(body.toString("utf8"));
            const componentName = toComponentName(component.name);
            const outputDir = join(process.cwd(), "src", "components", "generated");
            const outputPath = join(outputDir, `${componentName}.jsx`);

            await mkdir(outputDir, { recursive: true });
            await writeFile(outputPath, renderGeneratedComponent(component), "utf8");

            sendJson(response, 200, {
              componentName,
              path: `src/components/generated/${componentName}.jsx`,
            });
            return;
          }
        } catch (error) {
          sendJson(response, 500, { error: error.message || "Request failed" });
          return;
        }

        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), localApiPlugin()],
});

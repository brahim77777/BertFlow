import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

import {
  parseMultipartFile,
  readRequestBody,
  renderGeneratedComponent,
  sendJson,
  toComponentName,
} from "./src/lib/server-utils.mjs";

const root = process.cwd();
const port = Number(process.env.PORT || 5173);

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".jsx": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://${request.headers.host}`);

    if (request.method === "POST" && url.pathname === "/api/files") {
      const body = await readRequestBody(request, 50_000_000);
      const file = parseMultipartFile(body, request.headers["content-type"]);
      const outputDir = join(root, "files");
      const outputPath = join(outputDir, file.filename);

      await mkdir(outputDir, { recursive: true });
      await writeFile(outputPath, file.data);

      sendJson(response, 200, { name: file.filename, path: `files/${file.filename}` });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/components") {
      const body = await readRequestBody(request);
      const component = JSON.parse(body.toString("utf8"));
      const componentName = toComponentName(component.name);
      const outputDir = join(root, "src", "components", "generated");
      const outputPath = join(outputDir, `${componentName}.jsx`);

      await mkdir(outputDir, { recursive: true });
      await writeFile(outputPath, renderGeneratedComponent(component), "utf8");

      sendJson(response, 200, { componentName, path: `src/components/generated/${componentName}.jsx` });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/run") {
      const body = await readRequestBody(request);
      const payload = JSON.parse(body);

      console.log("\n--- Received Run Request ---");
      console.log(JSON.stringify(payload, null, 2));
      console.log("----------------------------\n");

      sendJson(response, 200, { status: "success", message: "Run request received", run_id: payload.run_id });
      return;
    }

    const pathname = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
    const safePath = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(root, safePath);
    const data = await readFile(filePath);

    response.writeHead(200, { "Content-Type": types[extname(filePath)] || "application/octet-stream" });
    response.end(data);
  } catch (error) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
});

server.listen(port, () => {
  console.log(`Component builder running at http://localhost:${port}`);
});

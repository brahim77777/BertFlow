import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

function toComponentName(name = "Component") {
  const cleaned = name
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join("");

  return cleaned && /^[A-Z]/.test(cleaned) ? cleaned : `Component${cleaned || ""}`;
}

function escapeText(value = "") {
  return String(value).replace(/\\/g, "\\\\").replace(/`/g, "\\`").replace(/\$/g, "\\$");
}

function safeFileName(name = "file") {
  const cleaned = String(name)
    .replace(/[/\\?%*:|"<>]/g, "-")
    .replace(/\s+/g, " ")
    .trim();

  return cleaned || "file";
}

function renderGeneratedComponent(component) {
  const componentName = toComponentName(component.name);
  const fields = JSON.stringify(component.fields || [], null, 2);
  const inputs = JSON.stringify(component.inputs || [], null, 2);
  const outputs = JSON.stringify(component.outputs || [], null, 2);

  // Note: we render it as a Svelte component
  return `<script>
  import { Handle, Position } from "@xyflow/svelte";

  export let data = {};

  const fields = ${fields};
  const inputs = ${inputs};
  const outputs = ${outputs};

  $: nodeFields = data.fields || fields;
  $: nodeInputs = data.inputs || inputs;
  $: nodeOutputs = data.outputs || outputs;
  $: label = data.label || \`${escapeText(component.name)}\`;
  $: description = data.description || \`${escapeText(component.description)}\`;
</script>

<article class="generated-component-node" title={description}>
  <header class="generated-component-header">
    <strong>{label}</strong>
    <span>{description}</span>
  </header>
  <div class="generated-component-body">
    <div class="generated-port-list">
      {#each nodeInputs as port (port.id)}
        <div class="generated-port-row" title={port.description}>
          <Handle type="target" id={port.id} position={Position.Left} />
          <span>{port.label}</span>
          <code>{port.type || "any"}</code>
        </div>
      {/each}
    </div>
    <div class="generated-field-list">
      {#each nodeFields as field (field.id)}
        <div class="generated-field-row" title={field.description}>
          <span>{field.label}</span>
          {#if field.type === "toggle" || field.type === "checkbox"}
            <span class="component-switch {field.value ? 'is-on' : ''}"></span>
          {:else if field.type === "file"}
            <span class="component-value">{field.value || "No file"}</span>
          {:else}
            <span class="component-value">{String(field.value ?? "")}</span>
          {/if}
        </div>
      {/each}
    </div>
    <div class="generated-port-list">
      {#each nodeOutputs as port (port.id)}
        <div class="generated-port-row is-output" title={port.description}>
          <code>{port.type || "any"}</code>
          <span>{port.label}</span>
          <Handle type="source" id={port.id} position={Position.Right} />
        </div>
      {/each}
    </div>
  </div>
</article>
`;
}

async function readRequestBody(request, maxLength = 1_000_000) {
  const chunks = [];
  let length = 0;

  for await (const chunk of request) {
    chunks.push(chunk);
    length += chunk.length;

    if (length > maxLength) {
      throw new Error("Request body is too large");
    }
  }

  return Buffer.concat(chunks, length);
}

function parseMultipartFile(body, contentType = "") {
  const boundaryMatch = contentType.match(/boundary=(?:"([^"]+)"|([^;]+))/i);

  if (!boundaryMatch) {
    throw new Error("Missing multipart boundary");
  }

  const boundaryValue = boundaryMatch[1] || boundaryMatch[2];
  const boundary = Buffer.from(`--${boundaryValue}`);
  const start = body.indexOf(boundary);

  if (start === -1) {
    throw new Error("Multipart boundary not found");
  }

  const headerStart = start + boundary.length + 2;
  const headerEnd = body.indexOf(Buffer.from("\r\n\r\n"), headerStart);

  if (headerEnd === -1) {
    throw new Error("Multipart headers not found");
  }

  const headers = body.subarray(headerStart, headerEnd).toString("utf8");
  const filenameMatch = headers.match(/filename="([^"]*)"/i);
  const filename = safeFileName(filenameMatch?.[1] || "file");
  const dataStart = headerEnd + 4;
  const nextBoundary = body.indexOf(Buffer.from(`\r\n--${boundaryValue}`), dataStart);

  if (nextBoundary === -1) {
    throw new Error("Multipart file boundary not found");
  }

  return {
    filename,
    data: body.subarray(dataStart, nextBoundary)
  };
}

function sendJson(response, statusCode, data) {
  response.statusCode = statusCode;
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.end(JSON.stringify(data));
}

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
            const outputPath = join(outputDir, `${componentName}.svelte`);

            await mkdir(outputDir, { recursive: true });
            await writeFile(outputPath, renderGeneratedComponent(component), "utf8");

            sendJson(response, 200, {
              componentName,
              path: `src/components/generated/${componentName}.svelte`
            });
            return;
          }
          
          if (request.method === "POST" && request.url === "/api/run") {
            const body = await readRequestBody(request);
            const payload = JSON.parse(body.toString("utf8"));
            
            console.log("\n--- Received Run Request ---");
            console.log(JSON.stringify(payload, null, 2));
            console.log("----------------------------\n");

            sendJson(response, 200, { status: "success", message: "Run request received", run_id: payload.run_id });
            return;
          }
        } catch (error) {
          sendJson(response, 500, { error: error.message || "Request failed" });
          return;
        }

        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [
    svelte(),
    localApiPlugin()
  ]
});

import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const root = process.cwd();
const port = Number(process.env.PORT || 5173);

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".jsx": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml"
};

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

  return `import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = ${fields};
const inputs = ${inputs};
const outputs = ${outputs};

function FieldValue({ field }) {
  if (field.type === "toggle" || field.type === "checkbox") {
    return <span className={\`component-switch \${field.value ? "is-on" : ""}\`} />;
  }

  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function ${componentName}({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || \`${escapeText(component.name)}\`;
  const description = data.description || \`${escapeText(component.description)}\`;

  return (
    <article className="generated-component-node" title={description}>
      <header className="generated-component-header">
        <strong>{label}</strong>
        <span>{description}</span>
      </header>
      <div className="generated-component-body">
        <div className="generated-port-list">
          {nodeInputs.map((port) => (
            <div className="generated-port-row" key={port.id} title={port.description}>
              <Handle type="target" id={port.id} position={Position.Left} />
              <span>{port.label}</span>
              <code>{port.type || "any"}</code>
            </div>
          ))}
        </div>
        <div className="generated-field-list">
          {nodeFields.map((field) => (
            <div className="generated-field-row" key={field.id} title={field.description}>
              <span>{field.label}</span>
              <FieldValue field={field} />
            </div>
          ))}
        </div>
        <div className="generated-port-list">
          {nodeOutputs.map((port) => (
            <div className="generated-port-row is-output" key={port.id} title={port.description}>
              <code>{port.type || "any"}</code>
              <span>{port.label}</span>
              <Handle type="source" id={port.id} position={Position.Right} />
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

export default memo(${componentName});
`;
}

async function readRequestBody(request) {
  let body = "";

  for await (const chunk of request) {
    body += chunk;
    if (body.length > 1_000_000) {
      throw new Error("Request body is too large");
    }
  }

  return body;
}

async function readRequestBuffer(request) {
  const chunks = [];
  let length = 0;

  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    chunks.push(buffer);
    length += buffer.length;

    if (length > 50_000_000) {
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

  const boundary = Buffer.from(`--${boundaryMatch[1] || boundaryMatch[2]}`);
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
  const nextBoundary = body.indexOf(Buffer.from(`\r\n--${boundaryMatch[1] || boundaryMatch[2]}`), dataStart);

  if (nextBoundary === -1) {
    throw new Error("Multipart file boundary not found");
  }

  return {
    filename,
    data: body.subarray(dataStart, nextBoundary)
  };
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url || "/", `http://${request.headers.host}`);

    if (request.method === "POST" && url.pathname === "/api/files") {
      const body = await readRequestBuffer(request);
      const file = parseMultipartFile(body, request.headers["content-type"]);
      const outputDir = join(root, "files");
      const outputPath = join(outputDir, file.filename);

      await mkdir(outputDir, { recursive: true });
      await writeFile(outputPath, file.data);

      response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({ name: file.filename, path: `files/${file.filename}` }));
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/components") {
      const body = await readRequestBody(request);
      const component = JSON.parse(body);
      const componentName = toComponentName(component.name);
      const outputDir = join(root, "src", "components", "generated");
      const outputPath = join(outputDir, `${componentName}.jsx`);

      await mkdir(outputDir, { recursive: true });
      await writeFile(outputPath, renderGeneratedComponent(component), "utf8");

      response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      response.end(JSON.stringify({ componentName, path: `src/components/generated/${componentName}.jsx` }));
      return;
    }

    const pathname = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
    const safePath = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
    const filePath = join(root, safePath);
    const data = await readFile(filePath);

    response.writeHead(200, {
      "Content-Type": types[extname(filePath)] || "application/octet-stream"
    });
    response.end(data);
  } catch (error) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
  }
});

server.listen(port, () => {
  console.log(`Component builder running at http://localhost:${port}`);
});

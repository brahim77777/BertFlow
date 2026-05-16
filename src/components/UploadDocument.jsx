import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    id: "file",
    label: "File",
    type: "file",
    value: "",
    description: "Select a document to upload and process",
  },
];

const inputs = [];

const outputs = [
  {
    id: "text",
    label: "Text",
    type: "string",
    description: "Extracted text content from the document",
  },
  {
    id: "filename",
    label: "Filename",
    type: "string",
    description: "Name of the uploaded file",
  },
  {
    id: "metadata",
    label: "Metadata",
    type: "json",
    description: "File metadata including size and any errors",
  },
];

function FieldValue({ field }) {
  if (field.type === "file") {
    return (
      <span className="component-value file-value">
        {field.value ? field.value.split("/").pop() || field.value : "No file"}
      </span>
    );
  }
  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function UploadDocument({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || "Upload Document";
  const description = data.description || "Upload a file and extract its text content";

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

export default memo(UploadDocument);

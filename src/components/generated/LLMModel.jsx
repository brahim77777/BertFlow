import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    "id": "field-91aca417-9701-4e3b-852e-bae0aad5d4ff",
    "label": "Text Field",
    "type": "text",
    "value": "",
    "description": "Configure the text value."
  },
  {
    "id": "field-8bbc71bf-aff9-453b-9cfb-3611d81f4261",
    "label": "Toggle Field",
    "type": "toggle",
    "value": true,
    "description": "Configure the toggle value."
  },
  {
    "id": "field-f7b964b5-7969-47f7-833d-c397399c43c3",
    "label": "Long Text Field",
    "type": "textarea",
    "value": "salut cocou",
    "description": "Configure the long text value."
  },
  {
    "id": "field-8cbbbf55-fc77-4a97-a985-f797ac5485ac",
    "label": "Select Field",
    "type": "select",
    "value": "Option A",
    "description": "Configure the select value."
  },
  {
    "id": "field-4dbda5b1-65fe-4c29-9d22-bf93fb02ea21",
    "label": "Checkbox Field",
    "type": "checkbox",
    "value": false,
    "description": "Configure the checkbox value."
  }
];
const inputs = [
  {
    "id": "port-2b881f65-79c5-484e-865d-7fb6bb0d8f06",
    "label": "Input 1",
    "description": "Input 1 connection point."
  }
];
const outputs = [
  {
    "id": "port-3c4384c8-48fb-4c82-a785-e570ff047fe6",
    "label": "docs",
    "description": "documents output"
  },
  {
    "id": "port-b6a6df83-841e-47c5-b061-a59a8ee6a23f",
    "label": "Output 2",
    "description": "Output 2 connection point."
  },
  {
    "id": "port-108b873c-7537-40ac-abf1-9684c0a9941f",
    "label": "Output 3",
    "description": "Output 3 connection point."
  }
];

function FieldValue({ field }) {
  if (field.type === "toggle" || field.type === "checkbox") {
    return <span className={`component-switch ${field.value ? "is-on" : ""}`} />;
  }

  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function LLMModel({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || `LLM model`;
  const description = data.description || `Document`;

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
              <span>{port.label}</span>
              <Handle type="source" id={port.id} position={Position.Right} />
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

export default memo(LLMModel);

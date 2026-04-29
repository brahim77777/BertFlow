import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    "id": "field-8399a2b2-3e29-43b3-8acd-93f3ce12b008",
    "label": "Text Field",
    "type": "text",
    "value": "salut mon ami",
    "description": "Configure the text value."
  },
  {
    "id": "field-17a9d7e4-d8a0-42c5-bf36-0d345ac6e362",
    "label": "Toggle Field",
    "type": "toggle",
    "value": true,
    "description": "Configure the toggle value."
  },
  {
    "id": "field-15a6c8eb-ebe4-4fc9-9ddf-92cf0782f9dd",
    "label": "Long Text Field",
    "type": "textarea",
    "value": "salut cocou",
    "description": "Configure the long text value."
  }
];
const inputs = [];
const outputs = [
  {
    "id": "port-2cbd012b-929a-4020-94b6-435f9ad13c76",
    "label": "Output 1",
    "description": "Output 1 connection point."
  },
  {
    "id": "port-84060c49-8eac-41f5-814a-3522f00ddf35",
    "label": "Output 2",
    "description": "Output 2 connection point."
  },
  {
    "id": "port-70bbd7a6-d259-4c79-a9f7-00f7c7fb01db",
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

function LLMModelCopy({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || `LLM model Copy`;
  const description = data.description || `llm model to fetch api`;

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

export default memo(LLMModelCopy);

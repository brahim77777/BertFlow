import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    "id": "field-eb2a42b3-6c0c-4323-a3f3-141c73dd7cb1",
    "label": "text",
    "type": "textarea",
    "value": "hi",
    "description": ""
  }
];
const inputs = [
  {
    "id": "port-8f82107c-7433-470b-84b2-2d434b60e031",
    "label": "Input 1",
    "type": "any",
    "description": "Input 1 connection point."
  }
];
const outputs = [
  {
    "id": "port-42cce41d-1672-40a7-ba75-eb495f8495ec",
    "label": "text",
    "type": "text",
    "description": "Output 1 connection point."
  }
];

function FieldValue({ field }) {
  if (field.type === "toggle" || field.type === "checkbox") {
    return <span className={`component-switch ${field.value ? "is-on" : ""}`} />;
  }

  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function B({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || `B`;
  const description = data.description || `Collects prompt settings and sends the configured prompt to the next node.`;

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

export default memo(B);

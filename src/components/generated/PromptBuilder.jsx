import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    "id": "field-model",
    "label": "Model Name",
    "type": "text",
    "value": "bert-base",
    "description": "The model identifier used by this component."
  },
  {
    "id": "field-temperature",
    "label": "Temperature",
    "type": "number",
    "value": 0.7,
    "description": "Controls how much variation the component should allow."
  },
  {
    "id": "field-cache",
    "label": "Use Cache",
    "type": "toggle",
    "value": true,
    "description": "Keeps repeated executions faster by caching compatible results."
  }
];
const inputs = [
  {
    "id": "port-context",
    "label": "Context",
    "type": "string",
    "description": "Text or metadata used as input context."
  }
];
const outputs = [
  {
    "id": "port-result",
    "label": "Result",
    "type": "string",
    "description": "The configured output value from this component."
  }
];

function FieldValue({ field }) {
  if (field.type === "toggle" || field.type === "checkbox") {
    return <span className={`component-switch ${field.value ? "is-on" : ""}`} />;
  }

  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function PromptBuilder({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || `Prompt Builder`;
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

export default memo(PromptBuilder);

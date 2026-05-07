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
  },
  {
    "id": "port-b76276c5-5d59-485a-b560-bd5fb548276d",
    "label": "Input 2",
    "type": "any",
    "description": "Input 2 connection point."
  },
  {
    "id": "port-b367855a-0082-4184-9b7d-08fbcc354f31",
    "label": "Input 3",
    "type": "any",
    "description": "Input 3 connection point."
  },
  {
    "id": "port-17be3688-d0ab-4f83-b1e3-832f15234c31",
    "label": "Input 4",
    "type": "any",
    "description": "Input 4 connection point."
  },
  {
    "id": "port-afb4b557-4da0-4fcf-969b-c9b929b24a55",
    "label": "Input 5",
    "type": "any",
    "description": "Input 5 connection point."
  },
  {
    "id": "port-8a4ba478-02fd-4920-89da-55b293ac0c1b",
    "label": "Input 6",
    "type": "any",
    "description": "Input 6 connection point."
  },
  {
    "id": "port-73f7aa59-d2af-454c-a9eb-460b2fc184dd",
    "label": "Input 7",
    "type": "any",
    "description": "Input 7 connection point."
  },
  {
    "id": "port-57d0f1b1-f3bd-4963-913d-abf7f2c3a0c7",
    "label": "Input 8",
    "type": "any",
    "description": "Input 8 connection point."
  },
  {
    "id": "port-aed13969-5adb-4e99-a921-b4b57c530ffe",
    "label": "Input 9",
    "type": "any",
    "description": "Input 9 connection point."
  },
  {
    "id": "port-81e8f75a-3d45-4264-8752-7268bf881c20",
    "label": "Input 10",
    "type": "any",
    "description": "Input 10 connection point."
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

  if (field.type === "file") {
    return <span className="component-value">{field.value || "No file"}</span>;
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

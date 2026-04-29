import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

const fields = [
  {
    "label": "Text",
    "description": "A text field",
    "value": "hello",
    "id": "field-a",
    "type": "text"
  }
];
const inputs = [
  {
    "label": "Input",
    "description": "Input port",
    "id": "in-a"
  }
];
const outputs = [
  {
    "label": "Output",
    "description": "Output port",
    "id": "out-a"
  }
];

function FieldValue({ field }) {
  if (field.type === "toggle" || field.type === "checkbox") {
    return <span className={`component-switch ${field.value ? "is-on" : ""}`} />;
  }

  return <span className="component-value">{String(field.value ?? "")}</span>;
}

function TestNode({ data = {} }) {
  const nodeFields = data.fields || fields;
  const nodeInputs = data.inputs || inputs;
  const nodeOutputs = data.outputs || outputs;
  const label = data.label || `Test Node`;
  const description = data.description || `Generated test component`;

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

export default memo(TestNode);

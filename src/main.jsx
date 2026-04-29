import Flow from "./flow.jsx";

import React, { memo, useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  addEdge,
  useEdgesState,
  useNodesState
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./styles.css";
import {
  Check,
  ChevronDown,
  Copy,
  Download,
  FileUp,
  FilePlus2,
  Info,
  Plus,
  Save,
  Trash2
} from "lucide-react";

const STORAGE_KEY = "bertlike.component-builder.components";

const fieldTypes = [
  { id: "text", label: "Text", defaultValue: "" },
  { id: "number", label: "Number", defaultValue: 0 },
  { id: "toggle", label: "Toggle", defaultValue: false },
  { id: "checkbox", label: "Checkbox", defaultValue: false },
  { id: "select", label: "Select", defaultValue: "Option A" },
  { id: "textarea", label: "Long Text", defaultValue: "" },
  { id: "file", label: "File", defaultValue: "" }
];

const makeId = (prefix) => `${prefix}-${crypto.randomUUID()}`;

const createComponent = (overrides = {}) => ({
  id: makeId("component"),
  name: "New Component",
  description: "Describe what this component does.",
  fields: [],
  inputs: [],
  outputs: [],
  savedAt: new Date().toISOString(),
  ...overrides
});

const starterComponent = createComponent({
  id: "component-starter",
  name: "Prompt Builder",
  description: "Collects prompt settings and sends the configured prompt to the next node.",
  fields: [
    {
      id: "field-model",
      label: "Model Name",
      type: "text",
      value: "bert-base",
      description: "The model identifier used by this component."
    },
    {
      id: "field-temperature",
      label: "Temperature",
      type: "number",
      value: 0.7,
      description: "Controls how much variation the component should allow."
    },
    {
      id: "field-cache",
      label: "Use Cache",
      type: "toggle",
      value: true,
      description: "Keeps repeated executions faster by caching compatible results."
    }
  ],
  inputs: [
    {
      id: "port-context",
      label: "Context",
      type: "string",
      description: "Text or metadata used as input context."
    }
  ],
  outputs: [
    {
      id: "port-result",
      label: "Result",
      type: "string",
      description: "The configured output value from this component."
    }
  ]
});

function loadComponents() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [starterComponent];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length ? parsed : [starterComponent];
  } catch {
    return [starterComponent];
  }
}

function Tooltip({ text }) {
  if (!text) return null;

  return (
    <span className="tooltip" tabIndex="0" aria-label={text}>
      <Info size={14} aria-hidden="true" />
      <span className="tooltip-panel">{text}</span>
    </span>
  );
}

function IconButton({ label, children, className = "", ...props }) {
  return (
    <button className={`icon-button ${className}`} type="button" aria-label={label} title={label} {...props}>
      {children}
    </button>
  );
}

function AddMenu({ label, options, onSelect, buttonClassName = "", className = "", align = "center" }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`add-menu ${className}`} data-align={align} onMouseLeave={() => setOpen(false)}>
      <IconButton label={label} className={buttonClassName} onClick={() => setOpen((value) => !value)}>
        <Plus size={22} />
      </IconButton>
      {open && (
        <div className="add-menu-panel" role="menu">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(option);
                setOpen(false);
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function FieldInput({ field, onChange }) {
  const [uploading, setUploading] = useState(false);

  const uploadFile = async (file) => {
    if (!file) return;

    setUploading(true);

    try {
      const body = new FormData();
      body.append("file", file);

      const response = await fetch("/api/files", {
        method: "POST",
        body
      });

      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const result = await response.json();
      onChange(result.name);
    } finally {
      setUploading(false);
    }
  };

  if (field.type === "number") {
    return (
      <input
        type="number"
        value={field.value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="field-control"
      />
    );
  }

  if (field.type === "toggle" || field.type === "checkbox") {
    return (
      <button
        type="button"
        className={`switch ${field.value ? "is-on" : ""}`}
        aria-pressed={field.value}
        onClick={() => onChange(!field.value)}
      >
        <span />
      </button>
    );
  }

  if (field.type === "select") {
    return (
      <label className="select-wrap">
        <select value={field.value} onChange={(event) => onChange(event.target.value)} className="field-control">
          <option>Option A</option>
          <option>Option B</option>
          <option>Option C</option>
        </select>
        <ChevronDown size={16} />
      </label>
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        type="textarea"
        value={field.value}
        onChange={(event) => onChange(event.target.value)}
        className="field-control area"
        rows="3"
      />
    );
  }
  if (field.type === "file") {
    return (
      <label className="file-control">
        <input
          type="file"
          onChange={(event) => uploadFile(event.target.files?.[0])}
        />
        <span>
          <FileUp size={15} />
          {uploading ? "Uploading..." : field.value || "Choose file"}
        </span>
      </label>
    );
  }


  return (
    <input
      type="text"
      value={field.value}
      onChange={(event) => onChange(event.target.value)}
      className="field-control"
    />
  );
}

const ComponentNode = memo(({ data }) => {
  const { component, onAddField, onAddPort, onUpdateField, onRemoveField } = data;

  return (
    <article className="builder-node">
      <header className="node-header">
        <div>
          <h2>{component.name}</h2>
          <p>{component.description}</p>
        </div>
        <Tooltip text={component.description} />
      </header>

      <div className="node-body">
        <section className="port-panel">
          <div className="node-section-title">Inputs</div>
          <div className="port-list">
            {component.inputs.map((port) => (
              <div className="port-row input" key={port.id}>
                <Handle type="target" id={port.id} position={Position.Left} />
                <span>{port.label}</span>
                <code>{port.type || "any"}</code>
                <Tooltip text={port.description} />
              </div>
            ))}
          </div>
          <IconButton label="Add input port" className="port-add port-add-menu" onClick={() => onAddPort("inputs")}>
            <Plus size={20} />
          </IconButton>
        </section>

        <section className="field-panel">
          <div className="node-section-title">Fields</div>
          <div className="field-list">
            {component.fields.map((field) => (
              <section className="field-row" key={field.id}>
                <div className="field-meta">
                  <span>{field.label}</span>
                  <Tooltip text={field.description} />
                </div>
                <FieldInput field={field} onChange={(value) => onUpdateField(field.id, { value })} />
                <IconButton label={`Remove ${field.label}`} className="ghost danger" onClick={() => onRemoveField(field.id)}>
                  <Trash2 size={15} />
                </IconButton>
              </section>
            ))}
          </div>
          <AddMenu
            label="Add field"
            className="field-add-menu"
            buttonClassName="field-add"
            options={fieldTypes}
            onSelect={(type) => onAddField(type)}
          />
        </section>

        <section className="port-panel">
          <div className="node-section-title">Outputs</div>
          <div className="port-list">
            {component.outputs.map((port) => (
              <div className="port-row output" key={port.id}>
                <code>{port.type || "any"}</code>
                <span>{port.label}</span>
                <Tooltip text={port.description} />
                <Handle type="source" id={port.id} position={Position.Right} />
              </div>
            ))}
          </div>
          <IconButton label="Add output port" className="port-add port-add-menu" onClick={() => onAddPort("outputs")}>
            <Plus size={20} />
          </IconButton>
        </section>
      </div>
    </article>
  );
});

function Inspector({ component, components, saveStatus, onSelect, onUpdate, onAddComponent, onDuplicate, onExport }) {
  return (
    <aside className="inspector">
      <div className="panel-title">
        <div>
          <span>Component</span>
          <h1>Dynamic Builder</h1>
        </div>
        <IconButton label="New component" onClick={onAddComponent}>
          <FilePlus2 size={19} />
        </IconButton>
      </div>

      <label className="control-group">
        <span>Saved components</span>
        <select value={component.id} onChange={(event) => onSelect(event.target.value)}>
          {components.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>

      <label className="control-group">
        <span>Label</span>
        <input value={component.name} onChange={(event) => onUpdate({ name: event.target.value })} />
      </label>

      <label className="control-group">
        <span>Description</span>
        <textarea
          rows="4"
          value={component.description}
          onChange={(event) => onUpdate({ description: event.target.value })}
        />
      </label>

      <div className="inspector-grid">
        <div>
          <strong>{component.inputs.length}</strong>
          <span>Inputs</span>
        </div>
        <div>
          <strong>{component.fields.length}</strong>
          <span>Fields</span>
        </div>
        <div>
          <strong>{component.outputs.length}</strong>
          <span>Outputs</span>
        </div>
      </div>

      <PortEditor title="Input Ports" ports={component.inputs} onChange={(ports) => onUpdate({ inputs: ports })} />
      <PortEditor title="Output Ports" ports={component.outputs} onChange={(ports) => onUpdate({ outputs: ports })} />
      <FieldEditor fields={component.fields} onChange={(fields) => onUpdate({ fields })} />

      <div className="panel-actions">
        <button type="button" onClick={onDuplicate}>
          <Copy size={16} />
          Duplicate
        </button>
        <button type="button" onClick={onExport}>
          <Download size={16} />
          Export JSON
        </button>
      </div>

      <div className="save-state">
        <Save size={15} />
        {saveStatus}
      </div>
    </aside>
  );
}

function PortEditor({ title, ports, onChange }) {
  const updatePort = (id, patch) => {
    onChange(ports.map((port) => (port.id === id ? { ...port, ...patch } : port)));
  };

  const removePort = (id) => {
    onChange(ports.filter((port) => port.id !== id));
  };

  return (
    <section className="editor-section">
      <h3>{title}</h3>
      {ports.map((port) => (
        <div className="editor-row" key={port.id}>
          <input value={port.label} onChange={(event) => updatePort(port.id, { label: event.target.value })} />
          <input
            value={port.type || ""}
            placeholder="Type, e.g. List[string]"
            onChange={(event) => updatePort(port.id, { type: event.target.value })}
          />
          <input
            value={port.description}
            placeholder="Tooltip description"
            onChange={(event) => updatePort(port.id, { description: event.target.value })}
          />
          <IconButton label={`Remove ${port.label}`} className="ghost danger" onClick={() => removePort(port.id)}>
            <Trash2 size={15} />
          </IconButton>
        </div>
      ))}
    </section>
  );
}

function FieldEditor({ fields, onChange }) {
  const updateField = (id, patch) => {
    onChange(fields.map((field) => (field.id === id ? { ...field, ...patch } : field)));
  };

  return (
    <section className="editor-section">
      <h3>Field Details</h3>
      {fields.map((field) => (
        <div className="editor-row field-editor" key={field.id}>
          <input value={field.label} onChange={(event) => updateField(field.id, { label: event.target.value })} />
          <select value={field.type} onChange={(event) => updateField(field.id, { type: event.target.value })}>
            {fieldTypes.map((type) => (
              <option key={type.id} value={type.id}>
                {type.label}
              </option>
            ))}
          </select>
          <input
            value={field.description}
            placeholder="Tooltip description"
            onChange={(event) => updateField(field.id, { description: event.target.value })}
          />
        </div>
      ))}
    </section>
  );
}

function App() {
  const [components, setComponents] = useState(loadComponents);
  const [selectedId, setSelectedId] = useState(components[0].id);
  const [saveStatus, setSaveStatus] = useState("Saved in browser");
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const selected = components.find((component) => component.id === selectedId) || components[0];

  const updateComponent = useCallback((patch) => {
    setComponents((items) =>
      items.map((item) =>
        item.id === selectedId ? { ...item, ...patch, savedAt: new Date().toISOString() } : item
      )
    );
  }, [selectedId]);

  const addField = useCallback((type) => {
    updateComponent({
      fields: [
        ...selected.fields,
        {
          id: makeId("field"),
          label: `${type.label} Field`,
          type: type.id,
          value: type.defaultValue,
          description: `Configure the ${type.label.toLowerCase()} value.`
        }
      ]
    });
  }, [selected, updateComponent]);

  const addPort = useCallback((side) => {
    const label = side === "inputs" ? `Input ${selected.inputs.length + 1}` : `Output ${selected.outputs.length + 1}`;
    updateComponent({
      [side]: [
        ...selected[side],
        {
          id: makeId("port"),
          label,
          type: "any",
          description: `${label} connection point.`
        }
      ]
    });
  }, [selected, updateComponent]);

  const updateField = useCallback((fieldId, patch) => {
    updateComponent({
      fields: selected.fields.map((field) => (field.id === fieldId ? { ...field, ...patch } : field))
    });
  }, [selected.fields, updateComponent]);

  const removeField = useCallback((fieldId) => {
    updateComponent({ fields: selected.fields.filter((field) => field.id !== fieldId) });
  }, [selected.fields, updateComponent]);

  const nodeTypes = useMemo(() => ({ componentNode: ComponentNode }), []);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);

  useEffect(() => {
    setNodes((current) => {
      const position = current[0]?.position || { x: 420, y: 90 };
      return [
        {
          id: selected.id,
          type: "componentNode",
          position,
          data: {
            component: selected,
            onAddField: addField,
            onAddPort: addPort,
            onUpdateField: updateField,
            onRemoveField: removeField
          }
        }
      ];
    });
  }, [addField, addPort, removeField, selected, setNodes, updateField]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(components));
  }, [components]);

  useEffect(() => {
    if (!selected) return;

    setSaveStatus("Saving component file...");
    const timeout = window.setTimeout(async () => {
      try {
        const response = await fetch("/api/components", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(selected)
        });

        if (!response.ok) {
          throw new Error("Save failed");
        }

        const result = await response.json();
        setSaveStatus(`Saved to ${result.path}`);
      } catch {
        setSaveStatus("Browser saved only; start the local server to write JSX");
      }
    }, 450);

    return () => window.clearTimeout(timeout);
  }, [selected]);

  const addComponent = () => {
    const component = createComponent();
    setComponents((items) => [...items, component]);
    setSelectedId(component.id);
    setEdges([]);
  };

  const duplicateComponent = () => {
    const copy = createComponent({
      ...selected,
      id: makeId("component"),
      name: `${selected.name} Copy`,
      fields: selected.fields.map((field) => ({ ...field, id: makeId("field") })),
      inputs: selected.inputs.map((port) => ({ ...port, id: makeId("port") })),
      outputs: selected.outputs.map((port) => ({ ...port, id: makeId("port") }))
    });
    setComponents((items) => [...items, copy]);
    setSelectedId(copy.id);
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selected.name.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "component"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="app-shell">
      <Inspector
        component={selected}
        components={components}
        saveStatus={saveStatus}
        onSelect={setSelectedId}
        onUpdate={updateComponent}
        onAddComponent={addComponent}
        onDuplicate={duplicateComponent}
        onExport={exportJson}
      />

      <section className="flow-shell">
        <div className="topbar">
          <div>
            <span>React Flow canvas</span>
            <strong>{selected.name}</strong>
          </div>
          <div className="status-pill">
            <Check size={15} />
            Components save automatically
          </div>
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={(params) => setEdges((items) => addEdge(params, items))}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.45}
          maxZoom={1.5}
        >
          <MiniMap pannable zoomable />
          <Controls />
          <Background gap={22} size={1.2} color="#cbd5e1" />
        </ReactFlow>
      </section>
    </main>
  );
}

function Root() {
  const [mode, setMode] = useState("builder");

  return (
    <>
      <div className="mode-switch">
        <button onClick={() => setMode("builder")}>Builder</button>
        <button onClick={() => setMode("flow")}>Flow</button>
      </div>

      {mode === "builder" ? <App /> : <Flow />}
    </>
  );
}

createRoot(document.getElementById("root")).render(<Root />);

import { memo, useCallback, useMemo, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges
} from "@xyflow/react";

const STORAGE_KEY = "bertlike.component-builder.components";

function makeId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

function cloneComponent(component) {
  return typeof structuredClone === "function"
    ? structuredClone(component)
    : JSON.parse(JSON.stringify(component));
}

function loadSavedComponents() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = JSON.parse(raw || "[]");

    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function stopFlowInteraction(event) {
  event.stopPropagation();
}

function FlowFieldInput({ field, onChange }) {
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

  const controlProps = {
    className: "flow-field-control nodrag nopan",
    onPointerDown: stopFlowInteraction,
    onMouseDown: stopFlowInteraction,
    onClick: stopFlowInteraction
  };

  if (field.type === "number") {
    return (
      <input
        {...controlProps}
        type="number"
        value={field.value ?? 0}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    );
  }

  if (field.type === "toggle" || field.type === "checkbox") {
    return (
      <button
        type="button"
        className={`switch nodrag nopan ${field.value ? "is-on" : ""}`}
        aria-pressed={Boolean(field.value)}
        onPointerDown={stopFlowInteraction}
        onMouseDown={stopFlowInteraction}
        onClick={(event) => {
          stopFlowInteraction(event);
          onChange(!field.value);
        }}
      >
        <span />
      </button>
    );
  }

  if (field.type === "select") {
    return (
      <select
        {...controlProps}
        value={field.value ?? "Option A"}
        onChange={(event) => onChange(event.target.value)}
      >
        <option>Option A</option>
        <option>Option B</option>
        <option>Option C</option>
      </select>
    );
  }

  if (field.type === "textarea") {
    return (
      <textarea
        {...controlProps}
        value={field.value ?? ""}
        rows="3"
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  if (field.type === "file") {
    return (
      <label
        className="file-control flow-file-control nodrag nopan"
        onPointerDown={stopFlowInteraction}
        onMouseDown={stopFlowInteraction}
        onClick={stopFlowInteraction}
      >
        <input type="file" onChange={(event) => uploadFile(event.target.files?.[0])} />
        <span>{uploading ? "Uploading..." : field.value || "Choose file"}</span>
      </label>
    );
  }

  return (
    <input
      {...controlProps}
      type="text"
      value={field.value ?? ""}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

const SavedComponentNode = memo(({ id, data }) => {
  const component = data.component;
  const fields = component.fields || [];
  const inputs = component.inputs || [];
  const outputs = component.outputs || [];

  return (
    <article className="generated-component-node" title={component.description}>
      <header className="generated-component-header">
        <strong>{component.name}</strong>
        <span>{component.description}</span>
      </header>

      <div className="generated-component-body">
        <div className="generated-port-list">
          {inputs.map((port) => (
            <div className="generated-port-row" key={port.id} title={port.description}>
              <Handle type="target" id={port.id} position={Position.Left} />
              <span>{port.label}</span>
              <code>{port.type || "any"}</code>
            </div>
          ))}
        </div>

        <div className="generated-field-list">
          {fields.map((field) => (
            <div className="generated-field-row flow-field-row" key={field.id} title={field.description}>
              <span>{field.label}</span>
              <FlowFieldInput
                field={field}
                onChange={(value) => data.onFieldChange(id, field.id, value)}
              />
            </div>
          ))}
        </div>

        <div className="generated-port-list">
          {outputs.map((port) => (
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
});

export default function Flow() {
  const [savedComponents, setSavedComponents] = useState(loadSavedComponents);
  const [selectedComponentId, setSelectedComponentId] = useState(savedComponents[0]?.id || "");
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  const updateNodeField = useCallback((nodeId, fieldId, value) => {
    setNodes((currentNodes) =>
      currentNodes.map((node) => {
        if (node.id !== nodeId) return node;

        return {
          ...node,
          data: {
            ...node.data,
            component: {
              ...node.data.component,
              fields: (node.data.component.fields || []).map((field) =>
                field.id === fieldId ? { ...field, value } : field
              )
            }
          }
        };
      })
    );
  }, []);

  const nodeTypes = useMemo(
    () => ({
      savedComponent: SavedComponentNode
    }),
    []
  );

  const selectedComponent = savedComponents.find((component) => component.id === selectedComponentId);

  const refreshSavedComponents = useCallback(() => {
    const nextComponents = loadSavedComponents();
    setSavedComponents(nextComponents);
    setSelectedComponentId((currentId) => {
      if (nextComponents.some((component) => component.id === currentId)) {
        return currentId;
      }

      return nextComponents[0]?.id || "";
    });
  }, []);

  const addSelectedComponent = useCallback(() => {
    if (!selectedComponent) return;

    setNodes((currentNodes) => [
      ...currentNodes,
      {
        id: makeId("flow-node"),
        type: "savedComponent",
        position: {
          x: 120 + currentNodes.length * 38,
          y: 120 + currentNodes.length * 28
        },
        data: {
          component: cloneComponent(selectedComponent),
          onFieldChange: updateNodeField
        }
      }
    ]);
  }, [selectedComponent, updateNodeField]);

  const onNodesChange = useCallback((changes) => {
    setNodes((currentNodes) => applyNodeChanges(changes, currentNodes));
  }, []);

  const onEdgesChange = useCallback((changes) => {
    setEdges((currentEdges) => applyEdgeChanges(changes, currentEdges));
  }, []);

  const onConnect = useCallback((params) => {
    setEdges((currentEdges) => addEdge(params, currentEdges));
  }, []);

  return (
    <main className="flow-page">
      <div className="flow-toolbar">
        <div>
          <span>Flow canvas</span>
          <strong>Build a pipeline from saved components</strong>
        </div>

        <div className="flow-library">
          <select
            value={selectedComponentId}
            onChange={(event) => setSelectedComponentId(event.target.value)}
            disabled={!savedComponents.length}
          >
            {savedComponents.length ? (
              savedComponents.map((component) => (
                <option key={component.id} value={component.id}>
                  {component.name}
                </option>
              ))
            ) : (
              <option>No saved components</option>
            )}
          </select>
          <button type="button" onClick={refreshSavedComponents}>
            Refresh
          </button>
          <button type="button" onClick={addSelectedComponent} disabled={!selectedComponent}>
            Add Component
          </button>
        </div>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
        minZoom={0.35}
        maxZoom={1.4}
      >
        <MiniMap pannable zoomable />
        <Controls />
        <Background gap={22} size={1.2} color="#cbd5e1" />
      </ReactFlow>
    </main>
  );
}

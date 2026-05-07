import { memo, useCallback, useMemo, useRef, useState } from "react";
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
const BACKEND_WS_URL = import.meta.env.VITE_BACKEND_WS_URL || "ws://127.0.0.1:8765/ws";

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

function toContractName(value, fallback = "value") {
  const cleaned = String(value || fallback)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9&]+/g, "_")
    .replace(/^_+|_+$/g, "");

  return cleaned || fallback;
}

function buildPortNameMap(ports = [], fallback) {
  const seen = new Map();
  const names = new Map();

  ports.forEach((port, index) => {
    const base = toContractName(port.label || port.id, `${fallback}_${index + 1}`);
    const count = (seen.get(base) || 0) + 1;
    seen.set(base, count);
    names.set(port.id, count === 1 ? base : `${base}_${count}`);
  });

  return names;
}

function getComponentContract(component) {
  return {
    nodeType: toContractName(component.name, "node"),
    inputs: buildPortNameMap(component.inputs || [], "input"),
    outputs: buildPortNameMap(component.outputs || [], "output")
  };
}

function normalizePortType(type) {
  const value = String(type || "any").trim().toLowerCase().replace(/\s+/g, "");
  const aliases = {
    str: "string",
    text: "string",
    file: "string",
    bool: "boolean",
    toggle: "boolean",
    checkbox: "boolean",
    integer: "int"
  };

  return aliases[value] || value || "any";
}

function arePortTypesCompatible(sourceType, targetType) {
  const source = normalizePortType(sourceType);
  const target = normalizePortType(targetType);

  return (
    source === "any" ||
    target === "any" ||
    source === target ||
    (target === "number" && (source === "int" || source === "float")) ||
    (target === "float" && (source === "int" || source === "number"))
  );
}

function summarizeRunMessage(message) {
  if (message.type === "run_accepted") {
    return `Run accepted: ${message.run_id}`;
  }

  if (message.type === "run_rejected") {
    return `Run rejected: ${(message.errors || []).join("; ")}`;
  }

  if (message.type === "run_finished") {
    return `Run ${message.state?.status || "finished"}`;
  }

  if (message.type === "execution_state") {
    const label = message.node_id ? `${message.event} (${message.node_id.slice(0, 12)})` : message.event;
    return `${label}: ${message.state?.status || "running"}`;
  }

  if (message.type === "error") {
    return `Backend error: ${message.message}`;
  }

  return "Backend connected";
}

/* ── Memoized individual field input ─────────────────────────── */
const FlowFieldInput = memo(({ field, onChange }) => {
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
});

/* ── Memoized single field row ───────────────────────────────── */
const FlowFieldRow = memo(({ field, nodeId, onFieldChange }) => {
  const handleChange = useCallback(
    (value) => onFieldChange(nodeId, field.id, value),
    [onFieldChange, nodeId, field.id]
  );

  return (
    <div className="generated-field-row flow-field-row" title={field.description}>
      <span>{field.label}</span>
      <FlowFieldInput field={field} onChange={handleChange} />
    </div>
  );
});

/* ── Memoized port rows ──────────────────────────────────────── */
const InputPortRow = memo(({ port }) => (
  <div className="generated-port-row" title={port.description}>
    <Handle type="target" id={port.id} position={Position.Left} />
    <span>{port.label}</span>
    <code>{port.type || "any"}</code>
  </div>
));

const OutputPortRow = memo(({ port }) => (
  <div className="generated-port-row is-output" title={port.description}>
    <code>{port.type || "any"}</code>
    <span>{port.label}</span>
    <Handle type="source" id={port.id} position={Position.Right} />
  </div>
));

/* ── The main node component ─────────────────────────────────── */
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
            <InputPortRow key={port.id} port={port} />
          ))}
        </div>

        <div className="generated-field-list">
          {fields.map((field) => (
            <FlowFieldRow
              key={field.id}
              field={field}
              nodeId={id}
              onFieldChange={data.onFieldChange}
            />
          ))}
        </div>

        <div className="generated-port-list">
          {outputs.map((port) => (
            <OutputPortRow key={port.id} port={port} />
          ))}
        </div>
      </div>
    </article>
  );
});

/* ── Memoized toolbar to avoid re-render on every node/edge change */
const FlowToolbar = memo(({ savedComponents, selectedComponentId, onSelectComponent, onRefresh, onAdd, hasSelected, onRun, isRunning, runStatus }) => (
  <div className="flow-toolbar">
    <div>
      <span>Flow canvas</span>
      <strong>Build a pipeline from saved components</strong>
      <small className="flow-run-status">{runStatus}</small>
    </div>

    <div className="flow-library">
      <select
        value={selectedComponentId}
        onChange={(event) => onSelectComponent(event.target.value)}
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
      <button type="button" onClick={onRefresh}>
        Refresh
      </button>
      <button type="button" onClick={onAdd} disabled={!hasSelected}>
        Add Component
      </button>
      <button type="button" className="run-button" onClick={onRun} disabled={isRunning} style={{ background: '#3b82f6', color: 'white', fontWeight: 'bold' }}>
        {isRunning ? "Running..." : "Run Flow"}
      </button>
    </div>
  </div>
));

/* ── Default edge options (stable ref) ───────────────────────── */
const defaultEdgeOptions = { animated: false, zIndex: 50 };

export default function Flow() {
  const [savedComponents, setSavedComponents] = useState(loadSavedComponents);
  const [selectedComponentId, setSelectedComponentId] = useState(savedComponents[0]?.id || "");
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [runStatus, setRunStatus] = useState("Backend idle");
  const [isRunning, setIsRunning] = useState(false);

  // Keep a ref to current nodes/edges so runFlow never causes re-renders
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const edgesRef = useRef(edges);
  edgesRef.current = edges;

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
    const currentNodes = nodesRef.current;
    const sourceNode = currentNodes.find((node) => node.id === params.source);
    const targetNode = currentNodes.find((node) => node.id === params.target);
    const sourcePort = sourceNode?.data.component.outputs?.find((port) => port.id === params.sourceHandle);
    const targetPort = targetNode?.data.component.inputs?.find((port) => port.id === params.targetHandle);

    if (sourcePort && targetPort && !arePortTypesCompatible(sourcePort.type, targetPort.type)) {
      setRunStatus(`Cannot connect ${sourcePort.type || "any"} to ${targetPort.type || "any"}`);
      return;
    }

    setEdges((currentEdges) => {
      const filtered = currentEdges.filter(e => !(e.target === params.target && e.targetHandle === params.targetHandle));
      return addEdge(params, filtered);
    });
  }, []);

  const runFlow = useCallback(async () => {
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;

    if (!currentNodes.length) {
      setRunStatus("Add at least one node before running.");
      return;
    }

    const runPayload = {
      run_id: makeId("run"),
      flow_id: "flow_abc123", // Static for now
      schema_version: 1,
      flow_revision: 1,
      created_at: new Date().toISOString(),
      execution_config: {
        timeout_seconds: Number(import.meta.env.VITE_EXECUTION_TIMEOUT_SECONDS || 120),
        on_node_failure: import.meta.env.VITE_EXECUTION_ON_NODE_FAILURE || "halt",
        max_retries: Number(import.meta.env.VITE_EXECUTION_MAX_RETRIES || 0)
      },
      nodes: currentNodes.reduce((acc, node) => {
        const comp = node.data.component;
        const contract = getComponentContract(comp);
        const args = {};
        let cache = false;
        
        if (comp.fields) {
          comp.fields.forEach(f => {
            const labelLower = f.label.toLowerCase();
            if (labelLower === "use cache" || f.id === "field-cache") {
              cache = Boolean(f.value);
            } else {
              const argName = toContractName(f.label, "arg");
              args[argName] = f.value;
            }
          });
        }

        acc[node.id] = {
          node_type: contract.nodeType,
          args,
          config: { cache }
        };
        return acc;
      }, {}),
      edges: currentEdges.map(edge => {
        const sourceNode = currentNodes.find(n => n.id === edge.source);
        const targetNode = currentNodes.find(n => n.id === edge.target);
        
        let fromPortName = edge.sourceHandle;
        if (sourceNode) {
           const contract = getComponentContract(sourceNode.data.component);
           fromPortName = contract.outputs.get(edge.sourceHandle) || fromPortName;
        }

        let toPortName = edge.targetHandle;
        if (targetNode) {
           const contract = getComponentContract(targetNode.data.component);
           toPortName = contract.inputs.get(edge.targetHandle) || toPortName;
        }

        return {
          id: edge.id,
          from: edge.source,
          from_port: fromPortName,
          to: edge.target,
          to_port: toPortName
        };
      })
    };

    console.log("Run Payload:", JSON.stringify(runPayload, null, 2));
    setIsRunning(true);
    setRunStatus("Connecting to backend...");

    try {
      await new Promise((resolve, reject) => {
        const socket = new WebSocket(BACKEND_WS_URL);
        let settled = false;

        const finish = (callback, value) => {
          if (settled) return;
          settled = true;
          socket.close(1000, "run complete");
          callback(value);
        };

        socket.addEventListener("open", () => {
          socket.send(JSON.stringify({ type: "run", payload: runPayload }));
        });

        socket.addEventListener("message", (event) => {
          const message = JSON.parse(event.data);
          console.log("Backend Message:", message);
          setRunStatus(summarizeRunMessage(message));

          if (message.type === "run_rejected" || message.type === "error") {
            finish(reject, new Error(summarizeRunMessage(message)));
          }

          if (message.type === "run_finished") {
            finish(resolve, message);
          }
        });

        socket.addEventListener("error", () => {
          finish(reject, new Error(`Could not connect to backend at ${BACKEND_WS_URL}`));
        });

        socket.addEventListener("close", () => {
          if (!settled) {
            finish(reject, new Error("Backend connection closed before the run finished"));
          }
        });
      });
    } catch (error) {
      console.error("Error running flow:", error);
      setRunStatus(error.message || "Failed to run flow");
    } finally {
      setIsRunning(false);
    }
  }, []); // No deps — reads from refs

  return (
    <main className="flow-page">
      <FlowToolbar
        savedComponents={savedComponents}
        selectedComponentId={selectedComponentId}
        onSelectComponent={setSelectedComponentId}
        onRefresh={refreshSavedComponents}
        onAdd={addSelectedComponent}
        hasSelected={!!selectedComponent}
        onRun={runFlow}
        isRunning={isRunning}
        runStatus={runStatus}
      />

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onlyRenderVisibleElements
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
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

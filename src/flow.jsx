import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
} from "@xyflow/react";

const STORAGE_KEY = "bertlike.component-builder.components";
const BACKEND_WS_URL =
  import.meta.env.VITE_BACKEND_WS_URL || "ws://127.0.0.1:8765";

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

const BACKEND_TYPE_TO_FIELD = {
  string: "text",
  number: "number",
  integer: "number",
  boolean: "toggle",
  file: "file",
};

function backendTypeToComponent(bt) {
  const inputs = Object.entries(bt.ports?.inputs || {}).map(([name, def]) => ({
    id: `in-${name}`,
    label: name,
    type: def.type || "any",
    description: def.required ? `${def.type} (required)` : `${def.type}`,
  }));
  const outputs = Object.entries(bt.ports?.outputs || {}).map(
    ([name, def]) => ({
      id: `out-${name}`,
      label: name,
      type: def.type || "any",
      description: `Output: ${def.type}`,
    }),
  );
  const fields = Object.entries(bt.args_schema || {}).map(([name, def]) => {
    const fieldType = BACKEND_TYPE_TO_FIELD[def.type] || "text";
    return {
      id: `field-${name}`,
      label: name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      type: fieldType,
      value:
        def.default ??
        (fieldType === "number" ? 0 : fieldType === "toggle" ? false : ""),
      description: `Type: ${def.type}${def.default !== undefined ? `, default: ${def.default}` : ""}`,
    };
  });

  return {
    id: makeId("backend-comp"),
    name: bt.label || bt.node_type,
    description: bt.description || bt.node_type,
    fields,
    inputs,
    outputs,
    savedAt: new Date().toISOString(),
    _backendRef: bt.node_type,
    _backendDef: bt,
  };
}

function toContractName(value, fallback = "value") {
  const cleaned = String(value || fallback)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9&]+/g, "_")
    .replace(/^_+|_+$/g, "");
  return cleaned || fallback;
}

function normalizePortType(type) {
  const value = String(type || "any")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
  const aliases = {
    str: "string",
    text: "string",
    file: "string",
    bool: "boolean",
    toggle: "boolean",
    checkbox: "boolean",
    integer: "int",
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
    (target === "float" && (source === "int" || source === "number")) ||
    (target === "number" && source === "integer")
  );
}

function summarizeMessage(message) {
  if (message.type === "node_types")
    return `Backend ready: ${message.node_types?.length || 0} node types`;
  if (message.type === "run_accepted") return `Run accepted: ${message.run_id}`;
  if (message.type === "run_rejected")
    return `Run rejected: ${(message.errors || []).join("; ")}`;
  if (message.type === "run_finished")
    return `Run ${message.state?.status || "finished"}`;
  if (message.type === "error") return `Backend error: ${message.message}`;
  if (message.type === "stream_chunk") return `Streaming: ${message.node_id} → ${message.port}`;
  return `Message: ${message.type}`;
}

const FlowFieldInput = memo(({ field, onChange }) => {
  const [uploading, setUploading] = useState(false);

  const uploadFile = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/files", { method: "POST", body });
      if (!response.ok) throw new Error("Upload failed");
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
    onClick: stopFlowInteraction,
  };

  if (field.type === "number") {
    return (
      <input
        {...controlProps}
        type="number"
        value={field.value ?? 0}
        onChange={(e) => onChange(Number(e.target.value))}
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
        onClick={(e) => {
          stopFlowInteraction(e);
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
        onChange={(e) => onChange(e.target.value)}
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
        onChange={(e) => onChange(e.target.value)}
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
        <input type="file" onChange={(e) => uploadFile(e.target.files?.[0])} />
        <span>{uploading ? "Uploading..." : field.value || "Choose file"}</span>
      </label>
    );
  }
  return (
    <input
      {...controlProps}
      type="text"
      value={field.value ?? ""}
      onChange={(e) => onChange(e.target.value)}
    />
  );
});

const FlowFieldRow = memo(({ field, nodeId, onFieldChange }) => {
  const handleChange = useCallback(
    (value) => onFieldChange(nodeId, field.id, value),
    [onFieldChange, nodeId, field.id],
  );
  return (
    <div
      className="generated-field-row flow-field-row"
      title={field.description}
    >
      <span>{field.label}</span>
      <FlowFieldInput field={field} onChange={handleChange} />
    </div>
  );
});

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

function previewLines(value, maxLines = 15) {
  if (value === null || value === undefined) return ["null"];
  const str =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const lines = str.split("\n");
  if (lines.length <= maxLines) return lines;
  return [
    ...lines.slice(0, maxLines),
    `\n… (${lines.length - maxLines} more lines)`,
  ];
}

const SavedComponentNode = memo(({ id, data }) => {
  const component = data.component;
  const fields = component.fields || [];
  const inputs = component.inputs || [];
  const outputs = component.outputs || [];
  const status = data.nodeStatus;
  const nodeOutputs = data.nodeOutputs;
  const icon = component._backendDef?.ui_config?.icon;
  const [showPreview, setShowPreview] = useState(false);

  const hasOutputs =
    (status === "completed" || status === "streaming") &&
    nodeOutputs &&
    Object.keys(nodeOutputs).length > 0;

  return (
    <article
      className={`generated-component-node${status ? ` status-${status}` : ""}`}
      title={component.description}
    >
      <header className="generated-component-header">
        {icon && (
          <img
            src={`/src/assets/icons/${icon}.png`}
            alt=""
            className="node-logo"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
        )}
        <div>
          <strong>{component.name}</strong>
          <span>{component.description}</span>
        </div>
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
      {status === "streaming" && nodeOutputs && (
        <div className="streaming-preview">
          {Object.entries(nodeOutputs).map(([key, val]) => (
            <div key={key}>
              <code>{key}</code>
              <pre>{val}</pre>
            </div>
          ))}
        </div>
      )}
      {hasOutputs && (
        <>
          <button
            className="output-preview-btn nodrag nopan"
            onClick={(e) => {
              e.stopPropagation();
              setShowPreview(true);
            }}
            title="Preview outputs"
          >
            Preview
          </button>
          {showPreview && (
            <div
              className="output-modal-backdrop"
              onClick={() => setShowPreview(false)}
            >
              <div
                className="output-modal-panel"
                onClick={(e) => e.stopPropagation()}
              >
                <header className="output-modal-header">
                  <strong>{component.name} — Outputs{status === "streaming" ? " (streaming…)" : ""}</strong>
                  <button
                    className="output-modal-close nodrag nopan"
                    onClick={() => setShowPreview(false)}
                  >
                    ✕
                  </button>
                </header>
                <div className="output-modal-body">
                  {Object.entries(nodeOutputs).length === 0 && (
                    <p className="output-modal-empty">No outputs</p>
                  )}
                  {Object.entries(nodeOutputs).map(([key, val]) => (
                    <div className="output-entry" key={key}>
                      <code className="output-entry-key">{key}</code>
                      <pre className="output-entry-value">
                        {previewLines(val, 15).map((line, i) => (
                          <span key={i}>{line}</span>
                        ))}
                      </pre>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </article>
  );
});

const FlowToolbar = memo(
  ({
    components,
    selectedId,
    onSelect,
    onRefresh,
    onAdd,
    onFetchBackend,
    hasSelected,
    onRun,
    isRunning,
    status,
  }) => (
    <div className="flow-toolbar">
      <div>
        <span>Flow canvas</span>
        <strong>Build a pipeline</strong>
        <small className="flow-run-status">{status}</small>
      </div>
      <div className="flow-library">
        <select
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          disabled={!components.length}
        >
          {components.length ? (
            components.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c._backendRef ? " ⚡" : ""}
              </option>
            ))
          ) : (
            <option>No components loaded</option>
          )}
        </select>
        <button type="button" onClick={onRefresh}>
          Refresh Local
        </button>
        <button type="button" onClick={onFetchBackend}>
          Fetch from Backend
        </button>
        <button type="button" onClick={onAdd} disabled={!hasSelected}>
          Add
        </button>
        <button
          type="button"
          className="run-button"
          onClick={onRun}
          disabled={isRunning}
          style={{ background: "#3b82f6", color: "white", fontWeight: "bold" }}
        >
          {isRunning ? "Running..." : "Run Flow"}
        </button>
      </div>
    </div>
  ),
);

const defaultEdgeOptions = { animated: false, zIndex: 50 };

export default function Flow() {
  const [allComponents, setAllComponents] = useState(() => {
    const local = loadSavedComponents();
    return local.length ? local : [];
  });
  const [selectedId, setSelectedId] = useState(allComponents[0]?.id || "");
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [status, setStatus] = useState("Backend idle");
  const [isRunning, setIsRunning] = useState(false);
  const wsRef = useRef(null);

  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const edgesRef = useRef(edges);
  edgesRef.current = edges;

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, "unmount");
        wsRef.current = null;
      }
    };
  }, []);

  const updateNodeField = useCallback((nodeId, fieldId, value) => {
    setNodes((current) =>
      current.map((node) => {
        if (node.id !== nodeId) return node;
        return {
          ...node,
          data: {
            ...node.data,
            component: {
              ...node.data.component,
              fields: (node.data.component.fields || []).map((f) =>
                f.id === fieldId ? { ...f, value } : f,
              ),
            },
          },
        };
      }),
    );
  }, []);

  const nodeTypes = useMemo(() => ({ savedComponent: SavedComponentNode }), []);

  const selected = allComponents.find((c) => c.id === selectedId);

  const mergeBackendComponents = useCallback((backendTypes) => {
    const local = loadSavedComponents();
    const backend = (backendTypes || []).map(backendTypeToComponent);
    const merged = [...backend];
    for (const lc of local) {
      if (!merged.some((m) => m.name === lc.name && !m._backendRef)) {
        merged.push(lc);
      }
    }
    setAllComponents(merged);
    setSelectedId((cur) =>
      merged.some((c) => c.id === cur) ? cur : merged[0]?.id || "",
    );
  }, []);

  const fetchFromBackend = useCallback(() => {
    setStatus("Connecting to backend...");
    const socket = new WebSocket(BACKEND_WS_URL);
    const timeout = setTimeout(() => {
      socket.close(1000, "timeout");
      setStatus("Backend connection timed out");
    }, 5000);

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ type: "get_node_types" }));
    });

    socket.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "node_types") {
        clearTimeout(timeout);
        mergeBackendComponents(msg.node_types);
        setStatus(`Backend ready: ${msg.node_types.length} node types`);
        socket.close(1000, "done");
      } else if (msg.type === "pong") {
      }
    });

    socket.addEventListener("error", () => {
      clearTimeout(timeout);
      setStatus("Cannot reach backend");
    });

    socket.addEventListener("close", () => {
      clearTimeout(timeout);
    });
  }, [mergeBackendComponents]);

  const refreshSavedComponents = useCallback(() => {
    const local = loadSavedComponents();
    setAllComponents((prev) => {
      const noBackend = prev.filter((c) => c._backendRef);
      const merged = [...noBackend];
      for (const lc of local) {
        if (!merged.some((m) => m.name === lc.name && m.id === lc.id)) {
          merged.push(lc);
        }
      }
      return merged;
    });
    setSelectedId((cur) => {
      const updated = loadSavedComponents();
      if (updated.some((c) => c.id === cur)) return cur;
      return updated[0]?.id || "";
    });
  }, []);

  function makePortMap(component) {
    const inputs = {};
    for (const p of component.inputs || []) {
      inputs[p.id] = p.label;
    }
    const outputs = {};
    for (const p of component.outputs || []) {
      outputs[p.id] = p.label;
    }
    return { inputs, outputs };
  }

  const addSelectedComponent = useCallback(() => {
    if (!selected) return;
    const comp = cloneComponent(selected);
    setNodes((current) => [
      ...current,
      {
        id: makeId("flow-node"),
        type: "savedComponent",
        dragHandle: ".generated-component-header",
        position: {
          x: 120 + current.length * 38,
          y: 120 + current.length * 28,
        },
        data: {
          component: comp,
          onFieldChange: updateNodeField,
          _nodeType: selected._backendRef || null,
          _portMap: makePortMap(comp),
        },
      },
    ]);
  }, [selected, updateNodeField]);

  const onNodesChange = useCallback((changes) => {
    setNodes((current) => applyNodeChanges(changes, current));
  }, []);

  const onEdgesChange = useCallback((changes) => {
    setEdges((current) => applyEdgeChanges(changes, current));
  }, []);

  const onConnect = useCallback((params) => {
    const current = nodesRef.current;
    const src = current.find((n) => n.id === params.source);
    const tgt = current.find((n) => n.id === params.target);
    const srcPort = src?.data.component.outputs?.find(
      (p) => p.id === params.sourceHandle,
    );
    const tgtPort = tgt?.data.component.inputs?.find(
      (p) => p.id === params.targetHandle,
    );
    if (
      srcPort &&
      tgtPort &&
      !arePortTypesCompatible(srcPort.type, tgtPort.type)
    ) {
      setStatus(`Type mismatch: ${srcPort.type} → ${tgtPort.type}`);
      return;
    }
    setEdges((current) => {
      const filtered = current.filter(
        (e) =>
          !(
            e.target === params.target && e.targetHandle === params.targetHandle
          ),
      );
      return addEdge(params, filtered);
    });
  }, []);

  const runFlow = useCallback(async () => {
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    if (!currentNodes.length) {
      setStatus("Add at least one node first");
      return;
    }

    const runPayload = {
      run_id: makeId("run"),
      flow_id: "flow_abc123",
      schema_version: 1,
      flow_revision: 1,
      created_at: new Date().toISOString(),
      execution_config: {
        timeout_seconds: Number(
          import.meta.env.VITE_EXECUTION_TIMEOUT_SECONDS || 120,
        ),
        on_node_failure:
          import.meta.env.VITE_EXECUTION_ON_NODE_FAILURE || "halt",
        max_retries: Number(import.meta.env.VITE_EXECUTION_MAX_RETRIES || 0),
      },
      nodes: currentNodes.reduce((acc, node) => {
        const comp = node.data.component;
        const nodeType =
          node.data._nodeType || toContractName(comp.name, "node");
        const args = {};
        let cache = false;

        if (comp.fields) {
          comp.fields.forEach((f) => {
            const lower = f.label.toLowerCase();
            if (lower === "use cache" || f.id === "field-cache") {
              cache = Boolean(f.value);
            } else {
              let value = f.value;
              const schema = comp._backendDef?.args_schema;
              if (schema) {
                const key = Object.keys(schema).find(
                  (k) => f.id === `field-${k}`,
                );
                if (key) {
                  const t = schema[key].type;
                  if (t === "integer" || t === "number") value = Number(value);
                  if (t === "boolean") value = Boolean(value);
                }
              }
              args[toContractName(f.label, "arg")] = value;
            }
          });
        }

        acc[node.id] = { node_type: nodeType, args, config: { cache } };
        return acc;
      }, {}),
      edges: currentEdges.map((edge) => {
        const src = currentNodes.find((n) => n.id === edge.source);
        const tgt = currentNodes.find((n) => n.id === edge.target);
        const srcMap = src?.data?._portMap?.outputs || {};
        const tgtMap = tgt?.data?._portMap?.inputs || {};
        return {
          id: edge.id,
          from: edge.source,
          from_port: srcMap[edge.sourceHandle] || edge.sourceHandle,
          to: edge.target,
          to_port: tgtMap[edge.targetHandle] || edge.targetHandle,
        };
      }),
    };

    setIsRunning(true);
    setStatus("Connecting to backend...");

    let resultMsg = null;
    try {
      resultMsg = await new Promise((resolve, reject) => {
        const socket = new WebSocket(BACKEND_WS_URL);
        let settled = false;
        const finish = (cb, val) => {
          if (settled) return;
          settled = true;
          socket.close(1000, "done");
          cb(val);
        };

        socket.addEventListener("open", () => {
          console.log("payload: ", runPayload);
          socket.send(JSON.stringify({ type: "run", payload: runPayload }));
        });

        socket.addEventListener("message", (event) => {
          const msg = JSON.parse(event.data);
          console.log("Backend:", msg);
          setStatus(summarizeMessage(msg));
          if (msg.type === "run_accepted") {
            setNodes((current) =>
              current.map((node) => ({
                ...node,
                data: { ...node.data, nodeStatus: "pending" },
              })),
            );
          }
          if (msg.type === "node_status") {
            setNodes((current) =>
              current.map((node) =>
                node.id === msg.node_id
                  ? { ...node, data: { ...node.data, nodeStatus: msg.status } }
                  : node,
              ),
            );
          }
          if (msg.type === "stream_chunk") {
            setNodes((current) =>
              current.map((node) => {
                if (node.id !== msg.node_id) return node;
                const outputs = { ...(node.data.nodeOutputs || {}) };
                outputs[msg.port] = (outputs[msg.port] || "") + msg.data;
                return { ...node, data: { ...node.data, nodeOutputs: outputs, nodeStatus: "streaming" } };
              }),
            );
          }
          if (msg.type === "run_rejected" || msg.type === "error") {
            setNodes((current) =>
              current.map((node) => ({
                ...node,
                data: { ...node.data, nodeStatus: null },
              })),
            );
            finish(reject, new Error(summarizeMessage(msg)));
          }
          if (msg.type === "run_finished") {
            finish(resolve, msg);
          }
        });

        socket.addEventListener("error", () => {
          finish(reject, new Error(`Cannot connect to ${BACKEND_WS_URL}`));
        });

        socket.addEventListener("close", () => {
          if (!settled)
            finish(reject, new Error("Connection closed before run finished"));
        });
      });
    } catch (err) {
      console.error("Run error:", err);
      setStatus(err.message || "Run failed");
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          data: { ...node.data, nodeStatus: null },
        })),
      );
      setIsRunning(false);
      return;
    }

    if (resultMsg?.state?.status === "completed") {
      console.log("═ BERTFLOW RUN RESULTS ═══════════════════════════");
      console.log(`run_id: ${resultMsg.run_id}`);
      console.log(`status: ${resultMsg.state.status}`);

      const refsToResolve = [];
      for (const [nid, ns] of Object.entries(resultMsg.state.node_states)) {
        console.log(
          `── Node: ${nid} (${ns.status})${ns.cached ? " [cached]" : ""}`,
        );
        for (const [key, val] of Object.entries(ns.outputs || {})) {
          const preview =
            typeof val === "string"
              ? val.slice(0, 120)
              : JSON.stringify(val).slice(0, 120);
          const isRef = typeof val === "string" && val.startsWith("store://");
          console.log(
            `  ${key} => ${isRef ? "REF: " + val : "INLINE: " + preview}`,
          );
          if (isRef) refsToResolve.push(val);
        }
      }

      if (refsToResolve.length > 0) {
        console.log(
          `── Resolving ${refsToResolve.length} ref(s) from backend...`,
        );
        try {
          const resolved = await new Promise((resolve, reject) => {
            const socket = new WebSocket(BACKEND_WS_URL);
            let settled = false;
            const finish = (cb, val) => {
              if (settled) return;
              settled = true;
              socket.close(1000, "done");
              cb(val);
            };
            socket.addEventListener("open", () => {
              socket.send(
                JSON.stringify({ type: "resolve_refs", refs: refsToResolve }),
              );
            });
            socket.addEventListener("message", (event) => {
              const msg = JSON.parse(event.data);
              if (msg.type === "refs_resolved") finish(resolve, msg.values);
            });
            socket.addEventListener("error", () =>
              finish(reject, new Error("Failed to resolve refs")),
            );
            socket.addEventListener("close", () => {
              if (!settled) finish(resolve, {});
            });
          });

          for (const ns of Object.values(resultMsg.state.node_states)) {
            for (const [key, val] of Object.entries(ns.outputs || {})) {
              if (typeof val === "string" && resolved[val] !== undefined) {
                ns.outputs[key] = resolved[val];
              }
            }
          }

          console.log("── Resolved values:");
          for (const [nid, ns] of Object.entries(resultMsg.state.node_states)) {
            for (const [key, val] of Object.entries(ns.outputs || {})) {
              const preview =
                typeof val === "string"
                  ? val.slice(0, 200)
                  : JSON.stringify(val).slice(0, 200);
              console.log(`  ${nid}.${key} = ${preview}`);
            }
          }
        } catch (e) {
          console.log("── Ref resolution failed:", e);
        }
      }

      console.log("══════════════════════════════════════════════════");
      const counts = Object.values(resultMsg.state.node_states)
        .map((ns) => `${ns.node_id?.slice(0, 8) || "?"}:${ns.status}`)
        .join(", ");
      setStatus(`Run completed — ${counts}`);
    } else {
      setStatus(resultMsg?.state?.error || "Run failed");
    }
    if (resultMsg?.state?.node_states) {
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          data: {
            ...node.data,
            nodeStatus: resultMsg.state.node_states[node.id]?.status || null,
            nodeOutputs: resultMsg.state.node_states[node.id]?.outputs || null,
          },
        })),
      );
    }
    setIsRunning(false);
  }, []);

  return (
    <main className="flow-page">
      <FlowToolbar
        components={allComponents}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onRefresh={refreshSavedComponents}
        onFetchBackend={fetchFromBackend}
        onAdd={addSelectedComponent}
        hasSelected={!!selected}
        onRun={runFlow}
        isRunning={isRunning}
        status={status}
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

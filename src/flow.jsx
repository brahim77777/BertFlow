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
    mode: def.mode || "data",
    description: def.required ? `${def.type} (required)` : `${def.type}`,
  }));
  const outputs = Object.entries(bt.ports?.outputs || {}).map(
    ([name, def]) => ({
      id: `out-${name}`,
      label: name,
      type: def.type || "any",
      mode: def.mode || "data",
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

// ── Port type → color ────────────────────────────────────────────
// Single source of truth for the color used by a port's type badge and its
// connection handle. To support new types later, add an entry here (keyed by
// the *normalized* type from normalizePortType); anything unknown falls back to
// PORT_TYPE_DEFAULT_COLOR, so the UI degrades gracefully as the type system grows.
const PORT_TYPE_COLORS = {
  string: "#38bdf8", // sky
  int: "#34d399", // emerald
  number: "#34d399",
  float: "#34d399",
  boolean: "#f472b6", // pink
  array: "#fbbf24", // amber
  object: "#a78bfa", // violet
  json: "#c084fc", // light violet
  any: "#94a3b8", // slate
};
const PORT_TYPE_DEFAULT_COLOR = "#94a3b8";
const EXTENSION_PORT_COLOR = "#f59e0b";

function portColor(port) {
  if (port?.mode === "extension") return EXTENSION_PORT_COLOR;
  return PORT_TYPE_COLORS[normalizePortType(port?.type)] || PORT_TYPE_DEFAULT_COLOR;
}

// Distinct types present across the loaded components — drives the canvas legend.
function collectPortTypes(components) {
  const seen = new Map();
  for (const c of components || []) {
    for (const p of [...(c.inputs || []), ...(c.outputs || [])]) {
      if (p.mode === "extension") continue;
      const t = normalizePortType(p.type);
      if (!seen.has(t)) seen.set(t, PORT_TYPE_COLORS[t] || PORT_TYPE_DEFAULT_COLOR);
    }
  }
  return [...seen.entries()];
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

const ExpandableFieldInput = memo(({ field, onChange }) => {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(field.value ?? "");

  const openModal = (e) => {
    stopFlowInteraction(e);
    setDraft(field.value ?? "");
    setOpen(true);
  };

  const save = () => {
    onChange(draft);
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        className="expandable-field-trigger nodrag nopan"
        onPointerDown={stopFlowInteraction}
        onMouseDown={stopFlowInteraction}
        onClick={openModal}
        aria-label={`Edit ${field.label}`}
        title="Click to expand editor"
      >
        {(field.value || "").slice(0, 60) || "Click to edit template…"}
        <span className="expand-icon" aria-hidden="true">⤢</span>
      </button>
      {open && (
        <div
          className="template-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={`Edit ${field.label}`}
          onClick={() => setOpen(false)}
        >
          <div className="template-modal-panel" onClick={(e) => e.stopPropagation()}>
            <header className="template-modal-header">
              <strong>{field.label}</strong>
              <div className="template-modal-actions">
                <button className="template-modal-save nodrag nopan" onClick={save}>Save</button>
                <button className="template-modal-close nodrag nopan" onClick={() => setOpen(false)} aria-label="Close editor">✕</button>
              </div>
            </header>
            <textarea
              className="template-modal-textarea nodrag nopan"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onPointerDown={stopFlowInteraction}
              onMouseDown={stopFlowInteraction}
              autoFocus
              spellCheck={false}
            />
            <footer className="template-modal-footer">
              <span>Placeholders: <code>{'{context}'}</code> <code>{'{query}'}</code> <code>{'{history_block}'}</code></span>
            </footer>
          </div>
        </div>
      )}
    </>
  );
});

const FlowFieldRow = memo(({ field, nodeId, onFieldChange, nodeType }) => {
  const handleChange = useCallback(
    (value) => onFieldChange(nodeId, field.id, value),
    [onFieldChange, nodeId, field.id],
  );

  const isPromptTemplate = nodeType === "prompt_template" && field.type === "text";

  return (
    <div
      className="generated-field-row flow-field-row"
      title={field.description}
    >
      <span>{field.label}</span>
      {isPromptTemplate
        ? <ExpandableFieldInput field={field} onChange={handleChange} />
        : <FlowFieldInput field={field} onChange={handleChange} />
      }
    </div>
  );
});

const InputPortRow = memo(({ port }) => {
  const color = portColor(port);
  return (
    <div
      className={`generated-port-row${port.mode === "extension" ? " is-extension" : ""}`}
      title={port.description}
      style={{ "--port-color": color }}
    >
      <Handle
        type="target"
        id={port.id}
        position={Position.Left}
        style={{ background: color, boxShadow: `0 0 0 1px ${color}, 0 0 8px ${color}66` }}
      />
      <span className="port-label">{port.label}</span>
      <code className="port-type">{port.type || "any"}</code>
    </div>
  );
});

const OutputPortRow = memo(({ port }) => {
  const color = portColor(port);
  return (
    <div
      className={`generated-port-row is-output${port.mode === "extension" ? " is-extension" : ""}`}
      title={port.description}
      style={{ "--port-color": color }}
    >
      <code className="port-type">{port.type || "any"}</code>
      <span className="port-label">{port.label}</span>
      <Handle
        type="source"
        id={port.id}
        position={Position.Right}
        style={{ background: color, boxShadow: `0 0 0 1px ${color}, 0 0 8px ${color}66` }}
      />
    </div>
  );
});

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

const CopyButton = memo(({ value }) => {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(
    (e) => {
      e.stopPropagation();
      navigator.clipboard?.writeText(String(value ?? "")).then(
        () => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        },
        () => {},
      );
    },
    [value],
  );
  return (
    <button
      type="button"
      className="copy-btn nodrag nopan"
      onClick={copy}
      aria-label="Copy value to clipboard"
      title="Copy"
    >
      {copied ? "Copied ✓" : "Copy"}
    </button>
  );
});

const SavedComponentNode = memo(({ id, data }) => {
  const component = data.component;
  const fields = component.fields || [];
  const inputs = component.inputs || [];
  const outputs = component.outputs || [];
  const status = data.nodeStatus;
  const nodeOutputs = data.nodeOutputs;
  const icon = component._backendDef?.ui_config?.icon;
  const [showPreview, setShowPreview] = useState(false);

  const duration = data.nodeDuration;

  const hasOutputs =
    (status === "completed" || status === "streaming") &&
    nodeOutputs &&
    Object.keys(nodeOutputs).length > 0;
  const failed = status === "failed";
  const canPreview = hasOutputs || failed;

  useEffect(() => {
    if (!showPreview) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") setShowPreview(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [showPreview]);

  return (
    <article
      className={`generated-component-node${status ? ` status-${status}` : ""}`}
      title={component.description}
    >
      {status && status !== "pending" && (
        <div
          className="node-runtime-badge"
          title={data.nodeError || undefined}
        >
          {status === "running"
            ? "Running..."
            : status === "streaming"
              ? "Streaming..."
              : status === "failed"
                ? "Failed"
                : status === "skipped"
                  ? "Skipped"
                  : duration !== null && duration !== undefined
                    ? `${duration}s`
                    : "Completed"}
        </div>
      )}
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
        {component._backendDef?.category !== "storage" && (
          <button
            type="button"
            className={`switch cache-toggle nodrag nopan ${data.cacheEnabled ? "is-on" : ""}`}
            aria-pressed={Boolean(data.cacheEnabled)}
            aria-label="Toggle result caching"
            onPointerDown={stopFlowInteraction}
            onMouseDown={stopFlowInteraction}
            onClick={(e) => {
              stopFlowInteraction(e);
              data.onCacheToggle?.(id);
            }}
            title={data.cacheEnabled ? "Caching enabled — results will be reused" : "Caching disabled — will re-execute"}
          >
            <span />
          </button>
        )}
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
              nodeType={component._backendRef}
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
      {canPreview && (
        <>
          <button
            className={`node-preview-btn nodrag nopan${failed && !hasOutputs ? " is-error" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              setShowPreview(true);
            }}
            aria-label={
              failed && !hasOutputs
                ? `View error for ${component.name}`
                : `Preview output of ${component.name}`
            }
          >
            <span aria-hidden="true">{failed && !hasOutputs ? "⚠" : "⤢"}</span>
            {failed && !hasOutputs ? "View error" : "Preview output"}
          </button>
          {showPreview && (
            <div
              className="output-modal-backdrop"
              role="dialog"
              aria-modal="true"
              aria-label={`${component.name} ${failed && !hasOutputs ? "error" : "output"}`}
              onClick={() => setShowPreview(false)}
            >
              <div
                className="output-modal-panel"
                onClick={(e) => e.stopPropagation()}
              >
                <header className="output-modal-header">
                  <strong>
                    {component.name} — {failed && !hasOutputs ? "Error" : "Output"}
                    {status === "streaming" ? " (streaming…)" : ""}
                  </strong>
                  <button
                    className="output-modal-close nodrag nopan"
                    onClick={() => setShowPreview(false)}
                    aria-label="Close"
                    autoFocus
                  >
                    ✕
                  </button>
                </header>
                <div className="output-modal-body">
                  {failed && (
                    <div className="output-error">
                      <span className="output-error-icon" aria-hidden="true">⚠</span>
                      <span className="output-error-msg">
                        {data.nodeError || "This node failed without a message."}
                      </span>
                    </div>
                  )}
                  {hasOutputs &&
                    Object.entries(nodeOutputs).map(([key, val]) => (
                      <div className="output-entry" key={key}>
                        <div className="output-entry-head">
                          <code className="output-entry-key">{key}</code>
                          <CopyButton
                            value={typeof val === "string" ? val : JSON.stringify(val, null, 2)}
                          />
                        </div>
                        <pre className="output-entry-value">
                          {previewLines(val, 40).join("\n")}
                        </pre>
                      </div>
                    ))}
                  {!failed && !hasOutputs && (
                    <p className="output-modal-empty">No outputs</p>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </article>
  );
});

const FlowToolbar = memo(({ nodeCount, edgeCount, onRun, isRunning, status }) => (
  <div className="flow-toolbar">
    <div className="flow-toolbar-info">
      <span>Flow canvas</span>
      <strong>Build a pipeline</strong>
      <small className="flow-run-status">{status}</small>
    </div>
    <div className="flow-toolbar-actions">
      <div className="flow-stat-chips">
        <span className="flow-chip">{nodeCount} {nodeCount === 1 ? "node" : "nodes"}</span>
        <span className="flow-chip">{edgeCount} {edgeCount === 1 ? "edge" : "edges"}</span>
      </div>
      <button
        type="button"
        className="run-button"
        onClick={onRun}
        disabled={isRunning || nodeCount === 0}
        title={nodeCount === 0 ? "Add a node first" : "Run flow (Ctrl/⌘ + Enter)"}
      >
        {isRunning
          ? <span className="run-spinner" aria-hidden="true" />
          : <span className="run-glyph" aria-hidden="true">▶</span>}
        {isRunning ? "Running…" : "Run Flow"}
      </button>
    </div>
  </div>
));

function groupByCategory(components) {
  const groups = new Map();
  for (const c of components || []) {
    const cat = c._backendDef?.category || (c._backendRef ? "general" : "local");
    if (!groups.has(cat)) groups.set(cat, []);
    groups.get(cat).push(c);
  }
  return [...groups.entries()].sort((a, b) => {
    if (a[0] === "local") return 1;
    if (b[0] === "local") return -1;
    return a[0].localeCompare(b[0]);
  });
}

const PortLegend = memo(({ types }) => {
  if (!types.length) return null;
  return (
    <div className="port-legend">
      <span className="port-legend-title">Port types</span>
      <div className="port-legend-items">
        {types.map(([t, color]) => (
          <span className="port-legend-item" key={t}>
            <span className="port-legend-dot" style={{ background: color }} />
            {t}
          </span>
        ))}
        <span className="port-legend-item">
          <span className="port-legend-dot" style={{ background: EXTENSION_PORT_COLOR }} />
          extension
        </span>
      </div>
    </div>
  );
});

const FlowPalette = memo(({ components, onAdd, onFetchBackend, onRefresh, legendTypes }) => {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return components;
    return components.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.description || "").toLowerCase().includes(q),
    );
  }, [components, query]);
  const groups = useMemo(() => groupByCategory(filtered), [filtered]);

  const onDragStart = (e, comp) => {
    e.dataTransfer.setData("application/bertflow-node", comp.id);
    e.dataTransfer.effectAllowed = "move";
  };

  return (
    <aside className="flow-palette">
      <header className="palette-header">
        <span>Node Library</span>
        <strong>BertFlow</strong>
      </header>
      <div className="palette-actions">
        <button type="button" className="palette-fetch" onClick={onFetchBackend}>
          ⚡ Fetch from Backend
        </button>
        <button type="button" onClick={onRefresh}>Refresh Local</button>
      </div>
      <input
        className="palette-search nodrag"
        type="search"
        placeholder="Search nodes…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search nodes"
      />
      <div className="palette-list">
        {groups.length === 0 && (
          <p className="palette-empty">
            {components.length
              ? "No nodes match your search."
              : 'No nodes loaded yet. Click "Fetch from Backend" to discover node types.'}
          </p>
        )}
        {groups.map(([cat, items]) => (
          <section className="palette-group" key={cat}>
            <h3>{cat}</h3>
            {items.map((c) => (
              <button
                type="button"
                key={c.id}
                className="palette-item"
                draggable
                onDragStart={(e) => onDragStart(e, c)}
                onClick={() => onAdd(c)}
                title={c.description}
                aria-label={`Add ${c.name}`}
              >
                <span
                  className="palette-item-dot"
                  style={{ background: c._backendDef?.ui_config?.color || "var(--accent)" }}
                />
                <span className="palette-item-name">{c.name}</span>
                {c._backendRef && (
                  <span className="palette-item-badge" title="Backend node">⚡</span>
                )}
              </button>
            ))}
          </section>
        ))}
      </div>
      <PortLegend types={legendTypes} />
    </aside>
  );
});

const ToastStack = memo(({ toasts, onDismiss }) => (
  <div className="toast-stack" role="status" aria-live="polite">
    {toasts.map((t) => (
      <div className={`toast toast-${t.kind}`} key={t.id}>
        <span className="toast-icon" aria-hidden="true">
          {t.kind === "success" ? "✓" : t.kind === "error" ? "✕" : t.kind === "warning" ? "!" : "i"}
        </span>
        <span className="toast-msg">{t.message}</span>
        <button
          type="button"
          className="toast-close"
          onClick={() => onDismiss(t.id)}
          aria-label="Dismiss notification"
        >
          ✕
        </button>
      </div>
    ))}
  </div>
));

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
  const allComponentsRef = useRef(allComponents);
  allComponentsRef.current = allComponents;
  const rfInstance = useRef(null);

  const [toasts, setToasts] = useState([]);
  const toastIdRef = useRef(0);
  const pushToast = useCallback((message, kind = "info", ttl = 4500) => {
    const id = ++toastIdRef.current;
    setToasts((cur) => [...cur, { id, message, kind }]);
    if (ttl) {
      setTimeout(
        () => setToasts((cur) => cur.filter((t) => t.id !== id)),
        ttl,
      );
    }
  }, []);
  const dismissToast = useCallback((id) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
  }, []);

  const legendTypes = useMemo(
    () => collectPortTypes(allComponents),
    [allComponents],
  );

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

  const toggleNodeCache = useCallback((nodeId) => {
    setNodes((current) =>
      current.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, cacheEnabled: !node.data.cacheEnabled } }
          : node,
      ),
    );
  }, []);

  const nodeTypes = useMemo(() => ({ savedComponent: SavedComponentNode }), []);

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
      pushToast("Backend connection timed out", "error");
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
        pushToast(`Loaded ${msg.node_types.length} node types from backend`, "success");
        socket.close(1000, "done");
      } else if (msg.type === "pong") {
      }
    });

    socket.addEventListener("error", () => {
      clearTimeout(timeout);
      setStatus("Cannot reach backend");
      pushToast("Cannot reach backend — is it running?", "error");
    });

    socket.addEventListener("close", () => {
      clearTimeout(timeout);
    });
  }, [mergeBackendComponents, pushToast]);

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

  const addComponent = useCallback(
    (component, position) => {
      if (!component) return;
      const comp = cloneComponent(component);
      setNodes((current) => {
        const pos =
          position || {
            x: 160 + current.length * 36,
            y: 140 + current.length * 26,
          };
        return [
          ...current,
          {
            id: makeId("flow-node"),
            type: "savedComponent",
            dragHandle: ".generated-component-header",
            position: pos,
            data: {
              component: comp,
              onFieldChange: updateNodeField,
              onCacheToggle: toggleNodeCache,
              cacheEnabled: false,
              _nodeType: component._backendRef || null,
              _portMap: makePortMap(comp),
            },
          },
        ];
      });
      pushToast(`Added “${comp.name}”`, "info", 2200);
    },
    [updateNodeField, toggleNodeCache, pushToast],
  );

  const addFromPalette = useCallback(
    (component) => {
      let position;
      if (rfInstance.current?.screenToFlowPosition) {
        position = rfInstance.current.screenToFlowPosition({
          x: window.innerWidth / 2,
          y: window.innerHeight / 2,
        });
      }
      addComponent(component, position);
    },
    [addComponent],
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const id = event.dataTransfer.getData("application/bertflow-node");
      if (!id) return;
      const comp = allComponentsRef.current.find((c) => c.id === id);
      if (!comp) return;
      let position;
      if (rfInstance.current?.screenToFlowPosition) {
        position = rfInstance.current.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });
      }
      addComponent(comp, position);
    },
    [addComponent],
  );

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

    let mode = tgtPort?.mode === "extension" || srcPort?.mode === "extension" ? "extension" : "data";

    if (mode === "data" && tgt?.data._backendDef) {
      const backendInputs = tgt.data._backendDef.ports?.inputs || {};
      for (const [name, def] of Object.entries(backendInputs)) {
        const handleId = `in-${name}`;
        if (params.targetHandle === handleId && def.mode === "extension") {
          mode = "extension";
          break;
        }
      }
    }

    if (
      srcPort && tgtPort &&
      srcPort.mode !== "extension" && tgtPort.mode !== "extension" &&
      !arePortTypesCompatible(srcPort.type, tgtPort.type)
    ) {
      const msg = `Type mismatch: ${srcPort.type} → ${tgtPort.type}`;
      setStatus(msg);
      pushToast(msg, "warning");
      return;
    }
    setEdges((current) => {
      let base = current;
      if (mode !== "extension") {
        base = current.filter(
          (e) =>
            !(
              e.target === params.target && e.targetHandle === params.targetHandle
            ),
        );
      }
      return addEdge({
        ...params,
        mode,
        className: mode === "extension" ? "extension-edge" : "",
      }, base);
    });
  }, [pushToast]);

  const runFlow = useCallback(async () => {
    const currentNodes = nodesRef.current;
    const currentEdges = edgesRef.current;
    if (!currentNodes.length) {
      setStatus("Add at least one node first");
      pushToast("Add at least one node before running", "warning");
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

        if (comp.fields) {
          comp.fields.forEach((f) => {
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
          });
        }

        acc[node.id] = { node_type: nodeType, args, config: { cache: node.data.cacheEnabled || false } };
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
          mode: edge.mode || "data",
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
                data: { ...node.data, nodeStatus: "pending", nodeDuration: null, nodeError: null },
              })),
            );
          }
          if (msg.type === "node_status") {
            setNodes((current) =>
              current.map((node) =>
                node.id === msg.node_id
                  ? {
                      ...node,
                      data: {
                        ...node.data,
                        nodeStatus: msg.status,
                        nodeDuration: msg.duration !== undefined ? msg.duration : node.data.nodeDuration,
                        nodeError: msg.error ?? null,
                      },
                    }
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
                data: { ...node.data, nodeStatus: null, nodeDuration: null },
              })),
            );
            pushToast(summarizeMessage(msg), "error", 7000);
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
      pushToast(err.message || "Run failed", "error", 7000);
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
      const states = Object.values(resultMsg.state.node_states);
      const done = states.filter((ns) => ns.status === "completed").length;
      const cached = states.filter((ns) => ns.cached).length;
      const summary = `Run completed — ${done}/${states.length} nodes${cached ? `, ${cached} cached` : ""}`;
      setStatus(summary);
      pushToast(summary, "success");
    } else {
      const errMsg = resultMsg?.state?.error || "Run failed";
      setStatus(errMsg);
      pushToast(errMsg, "error", 7000);
    }
    if (resultMsg?.state?.node_states) {
      setNodes((current) =>
        current.map((node) => ({
          ...node,
          data: {
            ...node.data,
            nodeStatus: resultMsg.state.node_states[node.id]?.status || null,
            nodeOutputs: resultMsg.state.node_states[node.id]?.outputs || null,
            nodeDuration: resultMsg.state.node_states[node.id]?.duration || null,
            nodeError: resultMsg.state.node_states[node.id]?.error || null,
          },
        })),
      );
    }
    setIsRunning(false);
  }, [pushToast]);

  // Keyboard shortcuts: Ctrl/⌘+Enter runs the flow (unless typing in a field).
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target?.tagName || "").toLowerCase();
      const typing =
        tag === "input" || tag === "textarea" || e.target?.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !typing) {
        e.preventDefault();
        if (!isRunning) runFlow();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [runFlow, isRunning]);

  return (
    <div className="app-shell">
      <FlowPalette
        components={allComponents}
        onAdd={addFromPalette}
        onFetchBackend={fetchFromBackend}
        onRefresh={refreshSavedComponents}
        legendTypes={legendTypes}
      />
      <div className="flow-canvas" onDrop={onDrop} onDragOver={onDragOver}>
        <FlowToolbar
          nodeCount={nodes.length}
          edgeCount={edges.length}
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
          onInit={(inst) => {
            rfInstance.current = inst;
          }}
          deleteKeyCode={["Delete"]}
          fitView
          minZoom={0.35}
          maxZoom={1.4}
        >
          <MiniMap pannable zoomable />
          <Controls />
          <Background gap={22} size={1.2} color="#2a2a3a" />
        </ReactFlow>
        {nodes.length === 0 && (
          <div className="canvas-empty">
            <div className="canvas-empty-card">
              <div className="canvas-empty-icon" aria-hidden="true">⌗</div>
              <h2>Start building your pipeline</h2>
              <p>
                Drag a node from the <strong>library</strong> on the left onto the
                canvas — or click one to drop it in the center. Connect ports, then
                press <kbd>Run Flow</kbd> (<kbd>Ctrl/⌘</kbd> + <kbd>Enter</kbd>).
              </p>
              <p className="canvas-empty-hint">
                Library empty? Click <strong>Fetch from Backend</strong>.
              </p>
            </div>
          </div>
        )}
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
      </div>
    </div>
  );
}

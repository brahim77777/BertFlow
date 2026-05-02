<script>
  import { SvelteFlow, Background, Controls, MiniMap } from "@xyflow/svelte";
  import { writable } from "svelte/store";
  import SavedComponentNode from "./SavedComponentNode.svelte";
  import { components } from "./componentsStore.js";

  let selectedComponentId = $components[0]?.id || "";

  // Dedicated store for this canvas instances
  const nodes = writable([]);
  const edges = writable([]);

  const nodeTypes = { savedComponent: SavedComponentNode };

  function makeId(prefix) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  function cloneComponent(component) {
    return typeof structuredClone === "function"
      ? structuredClone(component)
      : JSON.parse(JSON.stringify(component));
  }

  function refreshSavedComponents() {
    components.set(JSON.parse(localStorage.getItem("bertlike.component-builder.components") || "[]"));
    if (!$components.some((c) => c.id === selectedComponentId)) {
      selectedComponentId = $components[0]?.id || "";
    }
  }

  $: selectedComponent = $components.find((c) => c.id === selectedComponentId);

  function updateNodeField(nodeId, fieldId, value) {
    $nodes = $nodes.map((node) => {
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
    });
  }

  function addSelectedComponent() {
    if (!selectedComponent) return;

    const newNode = {
      id: makeId("flow-node"),
      type: "savedComponent",
      position: {
        x: 120 + $nodes.length * 38,
        y: 120 + $nodes.length * 28
      },
      data: {
        id: "", // will be set dynamically in map but let's pass it
        component: cloneComponent(selectedComponent),
        onFieldChange: updateNodeField
      }
    };
    // inject its own id
    newNode.data.id = newNode.id;
    
    $nodes = [...$nodes, newNode];
  }

  async function runFlow() {
    const runPayload = {
      run_id: makeId("run"),
      flow_id: "flow_abc123",
      schema_version: 1,
      flow_revision: 1,
      created_at: new Date().toISOString(),
      execution_config: {
        timeout_seconds: 120,
        on_node_failure: "halt",
        max_retries: 0
      },
      nodes: $nodes.reduce((acc, node) => {
        const comp = node.data.component;
        const args = {};
        let cache = false;
        
        if (comp.fields) {
          comp.fields.forEach(f => {
            const labelLower = f.label.toLowerCase();
            if (labelLower === "use cache" || f.id === "field-cache") {
              cache = Boolean(f.value);
            } else {
              const argName = labelLower.replace(/\s+/g, "_");
              args[argName] = f.value;
            }
          });
        }

        acc[node.id] = {
          node_type: comp.name.toLowerCase().replace(/\s+/g, "_"),
          args,
          config: { cache }
        };
        return acc;
      }, {}),
      edges: $edges.map(edge => {
        const sourceNode = $nodes.find(n => n.id === edge.source);
        const targetNode = $nodes.find(n => n.id === edge.target);
        
        let fromPortName = edge.sourceHandle;
        if (sourceNode) {
           const port = sourceNode.data.component.outputs?.find(p => p.id === edge.sourceHandle);
           if (port) fromPortName = port.label.toLowerCase().replace(/\s+/g, "_");
        }

        let toPortName = edge.targetHandle;
        if (targetNode) {
           const port = targetNode.data.component.inputs?.find(p => p.id === edge.targetHandle);
           if (port) toPortName = port.label.toLowerCase().replace(/\s+/g, "_");
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

    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(runPayload)
      });
      if (!response.ok) {
        throw new Error("Failed to run flow");
      }
      const result = await response.json();
      console.log("Run Result:", result);
      alert("Flow run successfully! Check console for details.");
    } catch (error) {
      console.error("Error running flow:", error);
      alert("Failed to run flow. Check console for errors.");
    }
  }

  function handleConnect(params) {
    $edges = $edges.filter(e => !(e.target === params.target && e.targetHandle === params.targetHandle));
    $edges = [...$edges, { ...params, zIndex: 50, id: `e${params.source}-${params.target}` }];
  }
</script>

<main class="flow-page">
  <div class="flow-toolbar">
    <div>
      <span>Flow canvas</span>
      <strong>Build a pipeline from saved components</strong>
    </div>

    <div class="flow-library">
      <select
        bind:value={selectedComponentId}
        disabled={!$components.length}
      >
        {#if $components.length}
          {#each $components as component}
            <option value={component.id}>
              {component.name}
            </option>
          {/each}
        {:else}
          <option>No saved components</option>
        {/if}
      </select>
      <button type="button" on:click={refreshSavedComponents}>
        Refresh
      </button>
      <button type="button" on:click={addSelectedComponent} disabled={!selectedComponent}>
        Add Component
      </button>
      <button type="button" class="run-button" on:click={runFlow} style="background: #3b82f6; color: white; font-weight: bold;">
        Run Flow
      </button>
    </div>
  </div>

  <SvelteFlow
    {nodes}
    {edges}
    {nodeTypes}
    on:connect={handleConnect}
    fitView
    minZoom={0.35}
    maxZoom={1.4}
  >
    <MiniMap pannable zoomable />
    <Controls />
    <Background gap={22} size={1.2} color="#cbd5e1" />
  </SvelteFlow>
</main>

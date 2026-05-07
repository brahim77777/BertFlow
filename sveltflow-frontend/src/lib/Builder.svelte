<script>
  import { SvelteFlow, Background, Controls, MiniMap } from "@xyflow/svelte";
  import { writable } from "svelte/store";
  import Inspector from "./Inspector.svelte";
  import ComponentNode from "./ComponentNode.svelte";
  import { components, createComponent } from "./componentsStore.js";
  import { Check } from "lucide-svelte";
  
  let selectedId = $components[0].id;
  let saveStatus = "Saved in browser";
  
  // Re-export nodes/edges state
  const nodes = writable([]);
  const edges = writable([]);
  
  const nodeTypes = { componentNode: ComponentNode };

  $: selected = $components.find(c => c.id === selectedId) || $components[0];
  
  function makeId(prefix) {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  function updateComponent(patch) {
    $components = $components.map((item) =>
      item.id === selectedId ? { ...item, ...patch, savedAt: new Date().toISOString() } : item
    );
  }

  function addField(type) {
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
  }

  function addPort(side) {
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
  }

  function updateField(fieldId, patch) {
    updateComponent({
      fields: selected.fields.map((field) => (field.id === fieldId ? { ...field, ...patch } : field))
    });
  }

  function removeField(fieldId) {
    updateComponent({ fields: selected.fields.filter((field) => field.id !== fieldId) });
  }

  $: {
    if (selected) {
      $nodes = [
        {
          id: selected.id,
          type: "componentNode",
          position: { x: 420, y: 90 },
          data: {
            component: selected,
            onAddField: addField,
            onAddPort: addPort,
            onUpdateField: updateField,
            onRemoveField: removeField
          }
        }
      ];
    }
  }

  let saveTimeout;
  $: {
    if (selected) {
      saveStatus = "Saving component file...";
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(async () => {
        try {
          const response = await fetch("/api/components", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(selected)
          });
          if (!response.ok) throw new Error("Save failed");
          const result = await response.json();
          saveStatus = `Saved to ${result.path}`;
        } catch {
          saveStatus = "Browser saved only; start the local server to write files";
        }
      }, 450);
    }
  }

  function addComponent() {
    const component = createComponent();
    $components = [...$components, component];
    selectedId = component.id;
    $edges = [];
  }

  function duplicateComponent() {
    const copy = createComponent({
      ...selected,
      id: makeId("component"),
      name: `${selected.name} Copy`,
      fields: selected.fields.map((field) => ({ ...field, id: makeId("field") })),
      inputs: selected.inputs.map((port) => ({ ...port, id: makeId("port") })),
      outputs: selected.outputs.map((port) => ({ ...port, id: makeId("port") }))
    });
    $components = [...$components, copy];
    selectedId = copy.id;
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(selected, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selected.name.toLowerCase().replace(/[^a-z0-9]+/g, "-") || "component"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
</script>

<main class="app-shell">
  <Inspector
    component={selected}
    components={$components}
    {saveStatus}
    onSelect={(id) => selectedId = id}
    onUpdate={updateComponent}
    onAddComponent={addComponent}
    onDuplicate={duplicateComponent}
    onExport={exportJson}
  />

  <section class="flow-shell">
    <div class="topbar">
      <div>
        <span>Svelte Flow canvas</span>
        <strong>{selected.name}</strong>
      </div>
      <div class="status-pill">
        <Check size={15} />
        Components save automatically
      </div>
    </div>
    <SvelteFlow
      {nodes}
      {edges}
      onlyRenderVisibleElements
      {nodeTypes}
      fitView
      minZoom={0.45}
      maxZoom={1.5}
    >
      <MiniMap pannable zoomable />
      <Controls />
      <Background gap={22} size={1.2} color="#cbd5e1" />
    </SvelteFlow>
  </section>
</main>

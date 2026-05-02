<script>
  import { FilePlus2, Copy, Download, Save, Trash2, Plus, Info, ChevronDown, FileUp } from "lucide-svelte";

  export let component;
  export let components = [];
  export let saveStatus = "Saved in browser";

  export let onSelect = (id) => {};
  export let onUpdate = (patch) => {};
  export let onAddComponent = () => {};
  export let onDuplicate = () => {};
  export let onExport = () => {};

  const fieldTypes = [
    { id: "text", label: "Text", defaultValue: "" },
    { id: "number", label: "Number", defaultValue: 0 },
    { id: "toggle", label: "Toggle", defaultValue: false },
    { id: "checkbox", label: "Checkbox", defaultValue: false },
    { id: "select", label: "Select", defaultValue: "Option A" },
    { id: "textarea", label: "Long Text", defaultValue: "" },
    { id: "file", label: "File", defaultValue: "" }
  ];

  function updatePort(side, id, patch) {
    const ports = component[side].map((port) => (port.id === id ? { ...port, ...patch } : port));
    onUpdate({ [side]: ports });
  }

  function removePort(side, id) {
    const ports = component[side].filter((port) => port.id !== id);
    onUpdate({ [side]: ports });
  }

  function updateField(id, patch) {
    const fields = component.fields.map((field) => (field.id === id ? { ...field, ...patch } : field));
    onUpdate({ fields });
  }
</script>

<aside class="inspector">
  <div class="panel-title">
    <div>
      <span>Component</span>
      <h1>Dynamic Builder</h1>
    </div>
    <button class="icon-button" aria-label="New component" title="New component" on:click={onAddComponent}>
      <FilePlus2 size={19} />
    </button>
  </div>

  <label class="control-group">
    <span>Saved components</span>
    <select value={component.id} on:change={(e) => onSelect(e.target.value)}>
      {#each components as item}
        <option value={item.id}>{item.name}</option>
      {/each}
    </select>
  </label>

  <label class="control-group">
    <span>Label</span>
    <input value={component.name} on:input={(e) => onUpdate({ name: e.target.value })} />
  </label>

  <label class="control-group">
    <span>Description</span>
    <textarea
      rows="4"
      value={component.description}
      on:input={(e) => onUpdate({ description: e.target.value })}
    ></textarea>
  </label>

  <div class="inspector-grid">
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

  <section class="editor-section">
    <h3>Input Ports</h3>
    {#each component.inputs as port (port.id)}
      <div class="editor-row">
        <input value={port.label} on:input={(e) => updatePort('inputs', port.id, { label: e.target.value })} />
        <input
          value={port.type || ""}
          placeholder="Type, e.g. List[string]"
          on:input={(e) => updatePort('inputs', port.id, { type: e.target.value })}
        />
        <input
          value={port.description}
          placeholder="Tooltip description"
          on:input={(e) => updatePort('inputs', port.id, { description: e.target.value })}
        />
        <button class="icon-button ghost danger" title="Remove {port.label}" on:click={() => removePort('inputs', port.id)}>
          <Trash2 size={15} />
        </button>
      </div>
    {/each}
  </section>

  <section class="editor-section">
    <h3>Output Ports</h3>
    {#each component.outputs as port (port.id)}
      <div class="editor-row">
        <input value={port.label} on:input={(e) => updatePort('outputs', port.id, { label: e.target.value })} />
        <input
          value={port.type || ""}
          placeholder="Type, e.g. List[string]"
          on:input={(e) => updatePort('outputs', port.id, { type: e.target.value })}
        />
        <input
          value={port.description}
          placeholder="Tooltip description"
          on:input={(e) => updatePort('outputs', port.id, { description: e.target.value })}
        />
        <button class="icon-button ghost danger" title="Remove {port.label}" on:click={() => removePort('outputs', port.id)}>
          <Trash2 size={15} />
        </button>
      </div>
    {/each}
  </section>

  <section class="editor-section">
    <h3>Field Details</h3>
    {#each component.fields as field (field.id)}
      <div class="editor-row field-editor">
        <input value={field.label} on:input={(e) => updateField(field.id, { label: e.target.value })} />
        <select value={field.type} on:change={(e) => updateField(field.id, { type: e.target.value })}>
          {#each fieldTypes as type}
            <option value={type.id}>{type.label}</option>
          {/each}
        </select>
        <input
          value={field.description}
          placeholder="Tooltip description"
          on:input={(e) => updateField(field.id, { description: e.target.value })}
        />
      </div>
    {/each}
  </section>

  <div class="panel-actions">
    <button type="button" on:click={onDuplicate}>
      <Copy size={16} />
      Duplicate
    </button>
    <button type="button" on:click={onExport}>
      <Download size={16} />
      Export JSON
    </button>
  </div>

  <div class="save-state">
    <Save size={15} />
    {saveStatus}
  </div>
</aside>

<script>
  import { Handle, Position } from "@xyflow/svelte";
  import { Plus, Trash2, Info, ChevronDown, FileUp } from "lucide-svelte";
  import { writable } from "svelte/store";
  import { setContext } from 'svelte';

  export let data = {};
  
  $: component = data.component;

  const fieldTypes = [
    { id: "text", label: "Text", defaultValue: "" },
    { id: "number", label: "Number", defaultValue: 0 },
    { id: "toggle", label: "Toggle", defaultValue: false },
    { id: "checkbox", label: "Checkbox", defaultValue: false },
    { id: "select", label: "Select", defaultValue: "Option A" },
    { id: "textarea", label: "Long Text", defaultValue: "" },
    { id: "file", label: "File", defaultValue: "" }
  ];

  let uploading = false;

  async function uploadFile(file, onChange) {
    if (!file) return;
    uploading = true;
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/files", { method: "POST", body });
      if (!response.ok) throw new Error("Upload failed");
      const result = await response.json();
      onChange(result.name);
    } finally {
      uploading = false;
    }
  }
</script>

<article class="builder-node">
  <header class="node-header">
    <div>
      <h2>{component.name}</h2>
      <p>{component.description}</p>
    </div>
    {#if component.description}
      <span class="tooltip" tabindex="0" aria-label={component.description}>
        <Info size={14} aria-hidden="true" />
        <span class="tooltip-panel">{component.description}</span>
      </span>
    {/if}
  </header>

  <div class="node-body">
    <section class="port-panel">
      <div class="node-section-title">Inputs</div>
      <div class="port-list">
        {#each component.inputs as port (port.id)}
          <div class="port-row input">
            <Handle type="target" id={port.id} position={Position.Left} />
            <span>{port.label}</span>
            <code>{port.type || "any"}</code>
            {#if port.description}
              <span class="tooltip" tabindex="0" aria-label={port.description}>
                <Info size={14} aria-hidden="true" />
                <span class="tooltip-panel">{port.description}</span>
              </span>
            {/if}
          </div>
        {/each}
      </div>
      <button class="icon-button port-add port-add-menu" title="Add input port" on:click={() => data.onAddPort("inputs")}>
        <Plus size={20} />
      </button>
    </section>

    <section class="field-panel">
      <div class="node-section-title">Fields</div>
      <div class="field-list">
        {#each component.fields as field (field.id)}
          <section class="field-row">
            <div class="field-meta">
              <span>{field.label}</span>
              {#if field.description}
                <span class="tooltip" tabindex="0" aria-label={field.description}>
                  <Info size={14} aria-hidden="true" />
                  <span class="tooltip-panel">{field.description}</span>
                </span>
              {/if}
            </div>
            
            {#if field.type === "number"}
              <input
                type="number"
                value={field.value}
                on:input={(e) => data.onUpdateField(field.id, { value: Number(e.target.value) })}
                class="field-control"
              />
            {:else if field.type === "toggle" || field.type === "checkbox"}
              <button
                type="button"
                class="switch {field.value ? 'is-on' : ''}"
                aria-pressed={field.value}
                on:click={() => data.onUpdateField(field.id, { value: !field.value })}
              >
                <span></span>
              </button>
            {:else if field.type === "select"}
              <label class="select-wrap">
                <select value={field.value} on:change={(e) => data.onUpdateField(field.id, { value: e.target.value })} class="field-control">
                  <option>Option A</option>
                  <option>Option B</option>
                  <option>Option C</option>
                </select>
                <ChevronDown size={16} />
              </label>
            {:else if field.type === "textarea"}
              <textarea
                value={field.value}
                on:input={(e) => data.onUpdateField(field.id, { value: e.target.value })}
                class="field-control area"
                rows="3"
              ></textarea>
            {:else if field.type === "file"}
              <label class="file-control">
                <input
                  type="file"
                  on:change={(e) => uploadFile(e.target.files[0], (v) => data.onUpdateField(field.id, { value: v }))}
                />
                <span>
                  <FileUp size={15} />
                  {uploading ? "Uploading..." : field.value || "Choose file"}
                </span>
              </label>
            {:else}
              <input
                type="text"
                value={field.value}
                on:input={(e) => data.onUpdateField(field.id, { value: e.target.value })}
                class="field-control"
              />
            {/if}

            <button class="icon-button ghost danger" title="Remove {field.label}" on:click={() => data.onRemoveField(field.id)}>
              <Trash2 size={15} />
            </button>
          </section>
        {/each}
      </div>

      <div class="add-menu field-add-menu" data-align="center">
        <select class="icon-button field-add" style="appearance: none; text-align: center; font-size: 14px;" on:change={(e) => {
          if (e.target.value) {
            const type = fieldTypes.find(t => t.id === e.target.value);
            data.onAddField(type);
            e.target.value = "";
          }
        }}>
          <option value="">+ Add field</option>
          {#each fieldTypes as type}
            <option value={type.id}>{type.label}</option>
          {/each}
        </select>
      </div>
    </section>

    <section class="port-panel">
      <div class="node-section-title">Outputs</div>
      <div class="port-list">
        {#each component.outputs as port (port.id)}
          <div class="port-row output">
            <code>{port.type || "any"}</code>
            <span>{port.label}</span>
            {#if port.description}
              <span class="tooltip" tabindex="0" aria-label={port.description}>
                <Info size={14} aria-hidden="true" />
                <span class="tooltip-panel">{port.description}</span>
              </span>
            {/if}
            <Handle type="source" id={port.id} position={Position.Right} />
          </div>
        {/each}
      </div>
      <button class="icon-button port-add port-add-menu" title="Add output port" on:click={() => data.onAddPort("outputs")}>
        <Plus size={20} />
      </button>
    </section>
  </div>
</article>

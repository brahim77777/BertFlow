<script>
  import { Handle, Position } from "@xyflow/svelte";

  export let data = {};
  
  $: component = data.component;
  $: inputs = component.inputs || [];
  $: outputs = component.outputs || [];
  $: fields = component.fields || [];

  let uploading = false;

  async function uploadFile(fieldId, file) {
    if (!file) return;
    uploading = true;
    try {
      const body = new FormData();
      body.append("file", file);
      const response = await fetch("/api/files", { method: "POST", body });
      if (!response.ok) throw new Error("Upload failed");
      const result = await response.json();
      data.onFieldChange(data.id, fieldId, result.name);
    } finally {
      uploading = false;
    }
  }
</script>

<article class="generated-component-node" title={component.description}>
  <header class="generated-component-header">
    <strong>{component.name}</strong>
    <span>{component.description}</span>
  </header>

  <div class="generated-component-body">
    <div class="generated-port-list">
      {#each inputs as port (port.id)}
        <div class="generated-port-row" title={port.description}>
          <Handle type="target" id={port.id} position={Position.Left} />
          <span>{port.label}</span>
          <code>{port.type || "any"}</code>
        </div>
      {/each}
    </div>

    <div class="generated-field-list">
      {#each fields as field (field.id)}
        <div class="generated-field-row flow-field-row" title={field.description}>
          <span>{field.label}</span>
          
          {#if field.type === "number"}
            <input
              class="flow-field-control nodrag nopan"
              type="number"
              value={field.value ?? 0}
              on:input={(e) => data.onFieldChange(data.id, field.id, Number(e.target.value))}
            />
          {:else if field.type === "toggle" || field.type === "checkbox"}
            <button
              type="button"
              class="switch nodrag nopan {field.value ? 'is-on' : ''}"
              aria-pressed={Boolean(field.value)}
              on:click={(e) => {
                e.stopPropagation();
                data.onFieldChange(data.id, field.id, !field.value);
              }}
            >
              <span></span>
            </button>
          {:else if field.type === "select"}
            <select
              class="flow-field-control nodrag nopan"
              value={field.value ?? "Option A"}
              on:change={(e) => data.onFieldChange(data.id, field.id, e.target.value)}
            >
              <option>Option A</option>
              <option>Option B</option>
              <option>Option C</option>
            </select>
          {:else if field.type === "textarea"}
            <textarea
              class="flow-field-control nodrag nopan"
              value={field.value ?? ""}
              rows="3"
              on:input={(e) => data.onFieldChange(data.id, field.id, e.target.value)}
            ></textarea>
          {:else if field.type === "file"}
            <label class="file-control flow-file-control nodrag nopan" on:click|stopPropagation>
              <input type="file" on:change={(e) => uploadFile(field.id, e.target.files[0])} />
              <span>{uploading ? "Uploading..." : field.value || "Choose file"}</span>
            </label>
          {:else}
            <input
              class="flow-field-control nodrag nopan"
              type="text"
              value={field.value ?? ""}
              on:input={(e) => data.onFieldChange(data.id, field.id, e.target.value)}
            />
          {/if}
        </div>
      {/each}
    </div>

    <div class="generated-port-list">
      {#each outputs as port (port.id)}
        <div class="generated-port-row is-output" title={port.description}>
          <code>{port.type || "any"}</code>
          <span>{port.label}</span>
          <Handle type="source" id={port.id} position={Position.Right} />
        </div>
      {/each}
    </div>
  </div>
</article>

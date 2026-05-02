<script>
  import { Handle, Position } from "@xyflow/svelte";

  export let data = {};

  const fields = [
  {
    "id": "field-ca3d29bc-bf6a-44c0-8fd0-69fd199b66d2",
    "label": "File",
    "type": "file",
    "value": "",
    "description": "Configure the file value."
  },
  {
    "id": "field-6e3f9037-dfeb-4ea0-9a06-c5d3fbba7d66",
    "label": "Cach results",
    "type": "toggle",
    "value": true,
    "description": "wehter to cach results or no"
  },
  {
    "id": "field-337545ca-5e3e-4705-8e04-21547c16084c",
    "label": "Number Field",
    "type": "number",
    "value": 8,
    "description": "Configure the number value."
  },
  {
    "id": "field-19f2091d-24ed-4fca-a8e9-e1dd650ec578",
    "label": "Checkbox Field",
    "type": "checkbox",
    "value": false,
    "description": "Configure the checkbox value."
  }
];
  const inputs = [
  {
    "id": "port-15fd6b21-0750-45c7-94f8-9ed54f33d495",
    "label": "Input 2",
    "type": "string",
    "description": "Input 2 connection point."
  },
  {
    "id": "port-e2036135-0fbe-4da5-b08f-76a965c8aab9",
    "label": "Input 2",
    "type": "any",
    "description": "Input 2 connection point."
  },
  {
    "id": "port-810375a9-ada5-4916-96f6-b5f636ab7d10",
    "label": "Input 3",
    "type": "any",
    "description": "Input 3 connection point."
  }
];
  const outputs = [
  {
    "id": "port-2a378414-05f9-4d57-930c-1cde12a6b59f",
    "label": "text",
    "type": "string",
    "description": "pdf after convertion to text"
  },
  {
    "id": "port-af2d83cb-fe1d-45c6-9f16-c5d3e520672c",
    "label": "Output 2",
    "type": "any",
    "description": "Output 2 connection point."
  },
  {
    "id": "port-44aa5cbf-938d-42a9-9afa-bdcf8d9a2f76",
    "label": "Output 3",
    "type": "any",
    "description": "Output 3 connection point."
  }
];

  $: nodeFields = data.fields || fields;
  $: nodeInputs = data.inputs || inputs;
  $: nodeOutputs = data.outputs || outputs;
  $: label = data.label || `Document Upload`;
  $: description = data.description || `upload documents here.`;
</script>

<article class="generated-component-node" title={description}>
  <header class="generated-component-header">
    <strong>{label}</strong>
    <span>{description}</span>
  </header>
  <div class="generated-component-body">
    <div class="generated-port-list">
      {#each nodeInputs as port (port.id)}
        <div class="generated-port-row" title={port.description}>
          <Handle type="target" id={port.id} position={Position.Left} />
          <span>{port.label}</span>
          <code>{port.type || "any"}</code>
        </div>
      {/each}
    </div>
    <div class="generated-field-list">
      {#each nodeFields as field (field.id)}
        <div class="generated-field-row" title={field.description}>
          <span>{field.label}</span>
          {#if field.type === "toggle" || field.type === "checkbox"}
            <span class="component-switch {field.value ? 'is-on' : ''}"></span>
          {:else if field.type === "file"}
            <span class="component-value">{field.value || "No file"}</span>
          {:else}
            <span class="component-value">{String(field.value ?? "")}</span>
          {/if}
        </div>
      {/each}
    </div>
    <div class="generated-port-list">
      {#each nodeOutputs as port (port.id)}
        <div class="generated-port-row is-output" title={port.description}>
          <code>{port.type || "any"}</code>
          <span>{port.label}</span>
          <Handle type="source" id={port.id} position={Position.Right} />
        </div>
      {/each}
    </div>
  </div>
</article>

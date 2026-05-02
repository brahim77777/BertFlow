<script>
  import Builder from "./lib/Builder.svelte";
  import FlowCanvas from "./lib/FlowCanvas.svelte";

  let mode = "builder";
</script>

<div class="mode-switch">
  <button on:click={() => mode = "builder"}>Builder</button>
  <button on:click={() => mode = "flow"}>Flow</button>
</div>

{#if mode === "builder"}
  <Builder />
{:else}
  <FlowCanvas />
{/if}

<style>
  .mode-switch {
    position: absolute;
    bottom: 20px;
    left: 20px;
    z-index: 50;
    display: flex;
    gap: 8px;
    background: white;
    padding: 8px;
    border-radius: 8px;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  }
  .mode-switch button {
    padding: 6px 12px;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    background: #f9fafb;
    font-weight: 500;
  }
  .mode-switch button:hover {
    background: #f3f4f6;
  }
</style>

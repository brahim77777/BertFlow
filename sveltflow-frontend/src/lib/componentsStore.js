import { writable } from "svelte/store";

const STORAGE_KEY = "bertlike.component-builder.components";

function makeId(prefix) {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function createComponent(overrides = {}) {
  return {
    id: makeId("component"),
    name: "New Component",
    description: "Describe what this component does.",
    fields: [],
    inputs: [],
    outputs: [],
    savedAt: new Date().toISOString(),
    ...overrides
  };
}

const starterComponent = createComponent({
  id: "component-starter",
  name: "Prompt Builder",
  description: "Collects prompt settings and sends the configured prompt to the next node.",
  fields: [
    {
      id: "field-model",
      label: "Model Name",
      type: "text",
      value: "bert-base",
      description: "The model identifier used by this component."
    },
    {
      id: "field-temperature",
      label: "Temperature",
      type: "number",
      value: 0.7,
      description: "Controls how much variation the component should allow."
    },
    {
      id: "field-cache",
      label: "Use Cache",
      type: "toggle",
      value: true,
      description: "Keeps repeated executions faster by caching compatible results."
    }
  ],
  inputs: [
    {
      id: "port-context",
      label: "Context",
      type: "string",
      description: "Text or metadata used as input context."
    }
  ],
  outputs: [
    {
      id: "port-result",
      label: "Result",
      type: "string",
      description: "The configured output value from this component."
    }
  ]
});

function loadComponents() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [starterComponent];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length ? parsed : [starterComponent];
  } catch {
    return [starterComponent];
  }
}

export const components = writable(loadComponents());

components.subscribe(value => {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  }
});

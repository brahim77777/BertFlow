# Graph Report - .  (2026-04-29)

## Corpus Check
- Corpus is ~19,016 words - fits in a single context window. You may not need a graph.

## Summary
- 98 nodes · 88 edges · 9 communities detected
- Extraction: 89% EXTRACTED · 8% INFERRED · 3% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]

## God Nodes (most connected - your core abstractions)
1. `Saved Component Schema` - 6 edges
2. `Dynamic Component Builder App` - 5 edges
3. `POST /api/files Endpoint` - 4 edges
4. `renderGeneratedComponent()` - 3 edges
5. `renderGeneratedComponent()` - 3 edges
6. `POST /api/components Endpoint` - 3 edges
7. `Vite Local Builder API Plugin` - 3 edges
8. `Saved Component Flow Canvas` - 3 edges
9. `Component Builder Feature Description` - 3 edges
10. `toComponentName()` - 2 edges

## Surprising Connections (you probably didn't know these)
- `Missing Untitled Design Image Artifact` --conceptually_related_to--> `Dynamic Component Builder App`  [AMBIGUOUS]
  files/Untitled design.jpg → src/main.jsx
- `Missing upload-check.txt Artifact` --references--> `POST /api/files Endpoint`  [AMBIGUOUS]
  files/upload-check.txt → server.mjs
- `Missing 2410.08801v1 PDF Artifact` --conceptually_related_to--> `Document Upload Generated Node`  [AMBIGUOUS]
  files/2410.08801v1.pdf → src/components/generated/DocumentUpload.jsx
- `Vite Local Builder API Plugin` --semantically_similar_to--> `Local HTTP Component Builder Server`  [INFERRED] [semantically similar]
  vite.config.js → server.mjs
- `Generated Component Renderer` --shares_data_with--> `Saved Component Schema`  [INFERRED]
  server.mjs → src/main.jsx

## Hyperedges (group relationships)
- **Component Generation Flow** — main_component_builder_app, main_component_autosave, server_component_generation_endpoint, server_generated_component_renderer, generated_test_node [EXTRACTED 0.91]
- **File Upload Flow** — main_file_field_upload_control, flow_file_field_upload_control, server_file_upload_endpoint, generated_document_upload_node [EXTRACTED 0.88]
- **Saved Component Runtime Flow** — main_component_schema, flow_pipeline_canvas, flow_saved_component_node, generated_document_node, generated_llm_model_node, generated_output_node [INFERRED 0.84]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.17
Nodes (2): createComponent(), makeId()

### Community 1 - "Community 1"
Cohesion: 0.2
Nodes (10): Flow File Field Upload Control, Component Autosave to JSX, Builder File Field Upload Control, Component Builder Feature Description, POST /api/components Endpoint, Component Name Normalizer, POST /api/files Endpoint, Generated Component Renderer (+2 more)

### Community 2 - "Community 2"
Cohesion: 0.31
Nodes (5): escapeText(), parseMultipartFile(), renderGeneratedComponent(), safeFileName(), toComponentName()

### Community 3 - "Community 3"
Cohesion: 0.36
Nodes (5): escapeText(), parseMultipartFile(), renderGeneratedComponent(), safeFileName(), toComponentName()

### Community 4 - "Community 4"
Cohesion: 0.32
Nodes (8): Saved Component Flow Canvas, Saved Component Node Runtime, Empty Generated Component Nodes, Test Node Generated Component, React Root HTML Entry, Dynamic Component Builder App, Saved Component Schema, Missing Untitled Design Image Artifact

### Community 7 - "Community 7"
Cohesion: 0.5
Nodes (4): Bun Dev Launcher, Local HTTP Component Builder Server, Vite Generated Component Renderer, Vite Local Builder API Plugin

### Community 16 - "Community 16"
Cohesion: 0.67
Nodes (3): Document Generated Node, LLM Model Copy Generated Node, LLM Model Generated Node

### Community 17 - "Community 17"
Cohesion: 0.67
Nodes (3): Missing 2410.08801v1 PDF Artifact, Document Upload Generated Node, Output Generated Node

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (2): Python Virtualenv In-Process Activation, PowerShell Virtualenv Activation Script

## Ambiguous Edges - Review These
- `POST /api/files Endpoint` → `Missing upload-check.txt Artifact`  [AMBIGUOUS]
  files/upload-check.txt · relation: references
- `Dynamic Component Builder App` → `Missing Untitled Design Image Artifact`  [AMBIGUOUS]
  files/Untitled design.jpg · relation: conceptually_related_to
- `Document Upload Generated Node` → `Missing 2410.08801v1 PDF Artifact`  [AMBIGUOUS]
  files/2410.08801v1.pdf · relation: conceptually_related_to

## Knowledge Gaps
- **17 isolated node(s):** `Bun Dev Launcher`, `Local HTTP Component Builder Server`, `Component Name Normalizer`, `Safe File Name Sanitizer`, `Vite Generated Component Renderer` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 0`** (13 nodes): `AddMenu()`, `App()`, `createComponent()`, `FieldEditor()`, `FieldInput()`, `IconButton()`, `Inspector()`, `main.jsx`, `loadComponents()`, `makeId()`, `PortEditor()`, `Root()`, `Tooltip()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `Python Virtualenv In-Process Activation`, `PowerShell Virtualenv Activation Script`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
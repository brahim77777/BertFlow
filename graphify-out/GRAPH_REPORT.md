# Graph Report - ./src  (2026-05-12)

## Corpus Check
- Corpus is ~7,600 words - fits in a single context window. You may not need a graph.

## Summary
- 120 nodes · 112 edges · 15 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Main UI Builder|Main UI Builder]]
- [[_COMMUNITY_Flow Engine|Flow Engine]]
- [[_COMMUNITY_Server Utilities|Server Utilities]]
- [[_COMMUNITY_Brahim Component|Brahim Component]]
- [[_COMMUNITY_BrahimYoucefDemo Component|BrahimYoucefDemo Component]]
- [[_COMMUNITY_Document Component|Document Component]]
- [[_COMMUNITY_DocumentUpload Component|DocumentUpload Component]]
- [[_COMMUNITY_LLMModel Component|LLMModel Component]]
- [[_COMMUNITY_LLMModelCopy Component|LLMModelCopy Component]]
- [[_COMMUNITY_NewComponent Component|NewComponent Component]]
- [[_COMMUNITY_Ou Component|Ou Component]]
- [[_COMMUNITY_Output Component|Output Component]]
- [[_COMMUNITY_PromptBuilder Component|PromptBuilder Component]]
- [[_COMMUNITY_TestNode Component|TestNode Component]]
- [[_COMMUNITY_Username Component|Username Component]]

## God Nodes (most connected - your core abstractions)
1. `renderGeneratedComponent()` - 3 edges
2. `makeId()` - 2 edges
3. `backendTypeToComponent()` - 2 edges
4. `normalizePortType()` - 2 edges
5. `arePortTypesCompatible()` - 2 edges
6. `makeId()` - 2 edges
7. `createComponent()` - 2 edges
8. `toComponentName()` - 2 edges
9. `escapeText()` - 2 edges
10. `safeFileName()` - 2 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities (15 total, 0 thin omitted)

### Community 0 - "Main UI Builder"
Cohesion: 0.1
Nodes (12): BuilderFieldRow, BuilderInputPort, BuilderOutputPort, ComponentNode, createComponent(), defaultEdgeOptions, FieldInput, fieldTypes (+4 more)

### Community 1 - "Flow Engine"
Cohesion: 0.12
Nodes (12): arePortTypesCompatible(), BACKEND_TYPE_TO_FIELD, backendTypeToComponent(), defaultEdgeOptions, FlowFieldInput, FlowFieldRow, FlowToolbar, InputPortRow (+4 more)

### Community 2 - "Server Utilities"
Cohesion: 0.36
Nodes (5): escapeText(), parseMultipartFile(), renderGeneratedComponent(), safeFileName(), toComponentName()

### Community 3 - "Brahim Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 4 - "BrahimYoucefDemo Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 5 - "Document Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 6 - "DocumentUpload Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 7 - "LLMModel Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 8 - "LLMModelCopy Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 9 - "NewComponent Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 10 - "Ou Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 11 - "Output Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 12 - "PromptBuilder Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 13 - "TestNode Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

### Community 14 - "Username Component"
Cohesion: 0.33
Nodes (3): fields, inputs, outputs

## Knowledge Gaps
- **54 isolated node(s):** `BACKEND_TYPE_TO_FIELD`, `FlowFieldInput`, `FlowFieldRow`, `InputPortRow`, `OutputPortRow` (+49 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `BACKEND_TYPE_TO_FIELD`, `FlowFieldInput`, `FlowFieldRow` to the rest of the system?**
  _54 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Main UI Builder` be split into smaller, more focused modules?**
  _Cohesion score 0.1 - nodes in this community are weakly interconnected._
- **Should `Flow Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.12 - nodes in this community are weakly interconnected._
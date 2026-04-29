# BertLike Component Builder

A Bun + Vite React Flow prototype for creating dynamic node components.

## Run

```powershell
.\run-dev.ps1
```

or:

```powershell
bun run dev
```

Then open:

```text
http://localhost:5173
```

Install dependencies first if this is a fresh checkout:

```powershell
bun install
```

## What It Does

- Create, duplicate, and select saved components.
- Auto-save component definitions to `localStorage`.
- While the Vite dev server is running, auto-write the selected component to `src/components/generated/<ComponentName>.jsx`.
- Edit the component label and description.
- Add dynamic fields: text, number, toggle, checkbox, select, and long text.
- Add file fields. The field value stores only the uploaded filename, and the file is written to the local `files/` folder.
- Add labeled input and output ports.
- Set a free-form type string on each port, such as `int`, `string`, or `List[string]`.
- Edit field and port descriptions, shown as hover tooltips.
- Export the selected component as JSON.

Generated components are React Flow node components that import `Handle` and `Position` from `@xyflow/react`.
=======
# BertFlow
A langflow alternative.
>>>>>>> 1151a34f8bf9e3f599cfc0beb024accf9a0322ba

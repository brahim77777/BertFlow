# Plan de Présentation — BertFlow

---

## 1. Architecture Générale

BertFlow est une application interactive de création et d'exécution de pipelines de données. Elle repose sur trois couches :

- **Frontend React** (Vite + `@xyflow/react`) — deux modes : *Builder* (création de composants) et *Flow* (assemblage et exécution de pipelines).
- **Backend Python** (WebSocket asynchrone via `websockets`) — validation, ordonnancement et exécution des graphes.
- **Serveur HTTP Node.js** (`server.mjs`) — persistance des composants builder sous forme de fichiers JSX et upload de fichiers.

La communication frontend ↔ backend s'effectue exclusivement par WebSocket (JSON). Le serveur HTTP est utilisé uniquement pour l'API REST du Builder (`POST /api/components`, `POST /api/files`).

```
Builder (main.jsx) ──HTTP──> server.mjs (JSX + fichiers)
Flow (flow.jsx)    ──WS────> backend/ws_server.py (exécution)
                    ──HTTP──> server.mjs (upload fichiers)
```

---

## 2. Backend

### `backend/__init__.py`

Fichier vide. Marque `backend` comme un package Python.

---

### `backend/__main__.py`

Point d'entrée du serveur. Utilise `argparse` pour deux options :

- `--host` (défaut `127.0.0.1`)
- `--port` (défaut `8765`)
- `--reload` (active l'auto-reload via `watchfiles`)

Si `--reload` est présent, `watchfiles.run_process()` surveille le répertoire parent (`backend/`) et redémarre le serveur à chaque modification. Sans `--reload`, `asyncio.run(run_server(...))` est appelé directement.

```python
watchfiles.run_process(
    __file__.rsplit("/", 1)[0],  # = backend/
    target=run_server,
    args=(args.host, args.port),
)
```

---

### `backend/ws_server.py`

Cœur du serveur WebSocket. Trois fonctions principales :

#### `build_registry()`

Délègue à `NodeRegistry.discover()` qui importe automatiquement tous les fichiers Python dans `backend/nodes/`.

#### `handle_message(text, registry, executor, send_fn, store)`

Distribue les messages JSON entrants selon leur champ `type` :

| `type` reçu | Réponse | Détails |
|---|---|---|
| `"ping"` | `{"type": "pong"}` | Keepalive simple |
| `"get_node_types"` | `{"type": "node_types", "node_types": [...]}` | Retourne les schémas via `registry.get_types()` |
| `"run"` | `run_accepted` ou `run_rejected` puis `run_finished` | Valide, exécute, retourne l'état final |
| `"resolve_refs"` | `{"type": "refs_resolved", "values": {...}}` | Résout les refs `store://` pour le client |
| Autre | `{"type": "error", "message": "..."}` | Erreur `unknown_type` |

**Déroulement d'un `run` :**
1. Extraction du `payload` → `RunRequest.from_dict()`. En cas d'échec, `run_rejected` est envoyé.
2. `validate_run_request(request, registry)` — validation en 6 étapes (voir §5). En cas d'échec, `GraphValidationError` → `run_rejected`.
3. Envoi de `run_accepted` avec `run_id`, `n_nodes`, `n_edges`.
4. `executor.execute(request)` — exécution asynchrone.
5. Envoi de `run_finished` avec l'état complet (`status`, `node_states`, `error` optionnel).
6. Si une exception non gérée survient pendant l'exécution, `run_finished` est tout de même envoyé avec `status: "failed"`.

**Messages malformés :** tout `JSONDecodeError` → `parse_error`.

#### `ws_handler(websocket)`

Gère le cycle de vie d'une connexion WebSocket :

```python
registry = build_registry()
store = InMemoryResultStore()
cache = InMemoryExecutionCache()
executor = AsyncGraphExecutor(registry, store, cache)
```

Envoie automatiquement `{"type": "node_types", "node_types": registry.get_types()}` dès la connexion (pas besoin d'attendre une requête `get_node_types`). Puis écoute les messages entrants en boucle asynchrone.

#### `run_server(host, port)`

Initialise le serveur `websockets.asyncio.server.serve(ws_handler, host, port)` et maintient le loop ouvert avec `asyncio.get_running_loop().create_future()`.

---

### `backend/core/errors.py`

Hiérarchie d'exceptions :

```
BackendError (Exception)
├── RunRequestError       — requête invalide
├── GraphValidationError  — échec de validation du graphe (cycle, type mismatch, etc.)
└── NodeExecutionError    — échec d'exécution d'un nœud (après retries épuisées)
```

---

### `backend/core/types.py`

#### `normalize_type(raw: str) -> str`

Normalise un nom de type en :
1. Minuscule, stripping, suppression des espaces.
2. Gestion des génériques : `List[string]` → `list[string]`.
3. Application des alias :

| Alias | Normalisé |
|---|---|
| `str`, `text`, `file` | `string` |
| `bool`, `toggle`, `checkbox` | `boolean` |
| `integer` | `int` |

```python
_ALIASES = {
    "str": "string", "text": "string", "file": "string",
    "bool": "boolean", "toggle": "boolean", "checkbox": "boolean",
    "integer": "int",
}
```

#### `are_types_compatible(source: str, target: str) -> bool`

Compare deux types après normalisation. Compatible si :
- `source == "any"` ou `target == "any"` (compatibilité universelle).
- Les types normalisés sont égaux.
- La paire existe dans `_COMPATIBILITY` :

```python
_COMPATIBILITY = {
    ("int", "number"): True,
    ("number", "int"): True,
    ("float", "number"): True,
    ("number", "float"): True,
    ("int", "float"): True,
    ("float", "int"): True,
}
```

---

### `backend/core/models.py`

Toutes les dataclasses du domaine :

#### `ExecutionConfig`
- `timeout_seconds: int = 120` — timeout global de l'exécution.
- `on_node_failure: str = "halt"` — `"halt"` ou `"skip"`.
- `max_retries: int = 0` — nombre de tentatives supplémentaires après la première.
- `from_dict(d)` avec valeurs par défaut via `d.get()`.

#### `NodeConfig`
- `cache: bool = False` — active ou désactive le cache pour ce nœud.

#### `NodeInstance`
- `node_type: str`, `args: dict`, `config: NodeConfig`.
- `from_dict(d)` extrait `d["node_type"]` (obligatoire), `d.get("args", {})`, `d.get("config", {})`.

#### `Edge`
- `id: str`, `source: str`, `source_port: str`, `target: str`, `target_port: str`, `source_type: str = ""`, `target_type: str = ""`.
- `from_dict(d)` mappe `from` → `source`, `from_port` → `source_port`, `to` → `target`, `to_port` → `target_port`. Les types sont normalisés via `normalize_type()`.

#### `RunRequest`
- Contient `run_id`, `flow_id`, `schema_version`, `flow_revision`, `execution_config`, `nodes: dict[str, NodeInstance]`, `edges: list[Edge]`, `user_id`, `created_at`, `metadata`.
- `from_dict(d)` construit chaque `NodeInstance` et `Edge` depuis le dictionnaire.

#### `NodeState`
- État d'un nœud pendant l'exécution : `node_id`, `node_type`, `status` (pending/running/completed/failed), `outputs`, `error`, `cached`, `started_at`, `finished_at`.

#### `ExecutionState`
- État global : `run_id`, `status` (pending/running/completed/failed), `node_states: dict[str, NodeState]`, `error`.

#### `PortDefinition`
- `name: str`, `type: str`, `required: bool = False`, `default: Any = None`.

#### `ArgDefinition`
- `name: str`, `type: str`, `default: Any = None`.

#### `NodeTypeSchema`
- Schéma complet d'un type de nœud : `node_type`, `label`, `category`, `version`, `description`, `ui_config`, `inputs`, `outputs`, `args_schema`.
- `to_dict()` transforme en dictionnaire avec structure :
  ```python
  {
      "node_type": "...", "version": "...", "label": "...",
      "description": "...", "category": "...", "ui_config": {...},
      "ports": {
          "inputs": {"port_name": {"type": "...", "required": bool, "default": ...}},
          "outputs": {"port_name": {"type": "..."}},
      },
      "args_schema": {"arg_name": {"type": "...", "default": ...}},
  }
  ```

#### `GraphPlan`
- Résultat de la validation : `nodes`, `edges`, `connected_components: list[list[str]]`, `topological_order: list[str]`.

---

### `backend/core/registry.py`

#### `RegisteredNode`

Wrapper autour d'une classe de nœud décorée par `@register_node`. À l'initialisation :
- Lit les attributs de classe : `node_type`, `label`, `description`, `category`, `version`, `ui_config`.
- Construit les ports (`inputs`, `outputs`) et `args_schema` via `_build_ports()` et `_build_args()`.
- `to_schema()` → `NodeTypeSchema`.
- `run(args, inputs, context)` délègue à `cls.run()`.

#### `register_node(cls)`

Décorateur qui enregistre la classe dans le dictionnaire global `_registry[node_type] = RegisteredNode(cls)`.

```python
_registry: dict[str, RegisteredNode] = {}
```

#### `NodeRegistry`

- `discover(nodes_path=None)` : méthode de classe principale.
  1. Détermine le chemin (`backend/nodes/` par défaut).
  2. Ajoute le répertoire parent à `sys.path` si nécessaire.
  3. Itère sur tous les fichiers `.py` (sauf ceux commençant par `_`).
  4. `importlib.import_module(f"backend.nodes.{fname[:-3]}")` — l'import déclenche les décorateurs `@register_node`.
  5. Copie le dictionnaire global `_registry` dans l'instance.
  6. Retourne le registry.

- `get(node_type)` → `RegisteredNode | None`.
- `get_types()` → `list[dict]` (appelle `to_schema().to_dict()` pour chaque nœud).
- `__contains__` / `__len__`.

---

### `backend/core/validator.py`

#### `validate_run_request(request, registry) -> GraphPlan`

Validation en 6 étapes séquentielles. Chaque étape lève `GraphValidationError` en cas d'échec.

**Étape 1 — Existence des nœuds dans le registre + injection des args par défaut :**
```python
if not nodes:
    raise GraphValidationError("Run request must contain at least one node")
```
Pour chaque `(nid, node)` :
- `node.node_type not in registry` → erreur avec liste des types connus.
- Injection des valeurs par défaut : tout `arg_name` présent dans `reg.args_schema` mais absent de `node.args` reçoit `reg.args_schema[arg_name].default`.

**Étape 2 — IDs d'arêtes uniques :**
```python
if edge.id in seen_edge_ids:
    raise GraphValidationError(f"Duplicate edge id '{edge.id}'")
```

**Étape 3 — Nœuds source et target existent :**
```python
if edge.source not in nodes → erreur
if edge.target not in nodes → erreur
```

**Étape 4 — Ports source et target existent sur les nœuds enregistrés :**
- `edge.source_port` doit exister dans `src_reg.outputs` (si `src_reg` non-null).
- `edge.target_port` doit exister dans `tgt_reg.inputs` (si `tgt_reg` non-null).
- Message d'erreur avec la liste des ports valides.

**Étape 5 — Compatibilité des types :**
```python
if not are_types_compatible(edge.source_type, edge.target_type):
    raise GraphValidationError(...)
```

**Étape 6 — Un seul edge entrant par port cible :**
```python
key = (edge.target, edge.target_port)
if key in target_inputs:
    raise GraphValidationError(...)
```

**Tri topologique (Kahn) :**
- Construction de l'adjacence et des degrés entrants.
- File d'attente initiale : tous les nœuds avec `in_degree == 0`.
- Itération : pop, ajout à `topo`, décrémentation des voisins, ajout si `in_degree == 0`.
- Si `len(topo) != len(nodes)` → cycle détecté.

**Composantes connexes (BFS) :**
- Parcourt tous les nœuds non visités.
- Pour chaque nœud de départ, BFS bidirectionnel (source et target) pour collecter la composante.
- Chaque composante est une `list[str]` de nœuds.

Retourne `GraphPlan(nodes, edges, connected_components, topological_order)`.

---

### `backend/core/executor.py`

#### `AsyncGraphExecutor`

Ordonnanceur par vagues parallèles basé sur l'algorithme de Kahn.

##### `__init__(self, registry, store, cache)`

Stocke les références. Si `store` ou `cache` sont `None`, crée des instances par défaut.

##### `execute(self, request) -> ExecutionState`

1. **Initialisation** : crée `ExecutionState` et les `NodeState` pour chaque nœud (tous à `status="pending"`).
2. **Construction du graphe** : `adj[nid] = list of (target_node, source_port, target_port)`. Calcul des `in_deg`.
3. **File ready** : nœuds avec `in_deg == 0`.
4. **Boucle principale** (sous `asyncio.timeout(timeout_seconds)`) :

```python
async with asyncio.timeout(timeout):
    while ready or pending > 0:
        wave = list(ready)
        ready.clear()
        # Exécution parallèle de la vague
        tasks = [self._run_node(request, nid, ...) for nid in wave]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Propagation des résultats
        for nid, result in zip(wave, results):
            if isinstance(result, Exception):
                # Gestion d'échec
                if fail_mode == "halt": return state
                elif fail_mode == "skip": pass
            else:
                node_states[nid].status = "completed"
                node_states[nid].outputs = store.build_outputs(...)
        # Nouvelle vague
        for edge in edges:
            if node state source == "completed" and target == "pending":
                node_inputs[target][target_port] = outputs[source_port]
                in_deg[target] -= 1
                if in_deg[target] == 0: ready.append(target)
```

**Cas particulier « vague vide » :** si `ready` est vide mais `pending > 0`, les nœuds restants sont marqués `failed` avec le message `"Dependency not satisfied (possible cycle or disconnected)"`.

**Timeouts :** `asyncio.timeout()` lève `TimeoutError` après `timeout_seconds` → `state.status = "failed"`.

**Mode d'échec :**
- `"halt"` : retour immédiat dès le premier nœud en échec.
- `"skip"` : le nœud échoué est ignoré, les autres continuent.

##### `_run_node(self, request, nid, ...) -> dict | None`

1. Marque le nœud `"running"`, enregistre `started_at`.
2. Récupère `args` et `inputs`.
3. **Cache check** : si `node.config.cache == True`, appelle `self._cache.get(node_type, args, inputs)`. Si hit, retourne le résultat avec `cached=True`.
4. **Boucle de retry** : `for attempt in range(max_retries + 1)` :
   - `await reg.run(args, inputs, nid)`.
   - En cas de succès : enregistre `finished_at`, met en cache si `cache == True`, retourne le résultat.
   - En cas d'exception : log warning, `await asyncio.sleep(0.1 * (attempt + 1))`.
5. Après épuisement des retries : lève `NodeExecutionError`.

---

### `backend/core/result_store.py`

#### `InMemoryResultStore`

Stockage intermédiaire des sorties de nœuds.

- `_data: dict[str, dict[str, Any]]` = `{run_id: {node_id: outputs}}`.
- `put(run_id, node_id, outputs)` : stocke.
- `get(run_id, node_id)` : récupère.
- `resolve(ref)` : parse la ref `store://run_id/node_id/port` et retourne la valeur.
- `ref(run_id, node_id, port)` : génère `f"store://{run_id}/{node_id}/{port}"`.
- `build_outputs(run_id, node_id, result)` :
  1. `self.put(run_id, node_id, result)`.
  2. Pour chaque `(port_name, value)`, si `should_inline(value)` → valeur inline, sinon → ref `store://...`.

#### `InMemoryExecutionCache`

Cache d'exécution basé sur SHA-256.

- `_cache: dict[str, dict]` = `{sha256_hash: outputs}`.
- `_key(node_type, args, inputs)` :
  1. `json.dumps([node_type, args, inputs], sort_keys=True, default=str)`.
  2. `hashlib.sha256(raw.encode()).hexdigest()`.
- `get(node_type, args, inputs)` : retourne le résultat si la clé existe.
- `put(node_type, args, inputs, outputs)` : stocke.

#### `should_inline(value) -> bool`

Décide si une valeur est stockée inline ou par référence :

| Type | Condition |
|---|---|
| `None`, `bool`, `int`, `float` | Toujours inline |
| `str` | Inline si `len(value) < 1024` |
| Autre (dict, list, etc.) | Inline si `len(json.dumps(value, default=str)) < 1024` |

Le seuil est défini par `HYBRID_THRESHOLD = 1024` (1 Ko).

#### `parse_ref(ref) -> tuple | None`

Parse `store://run_id/node_id` ou `store://run_id/node_id/port`. Retourne `(run_id, node_id, port)` ou `None`.

---

### `backend/core/logging.py`

Logger unique `bertflow` avec un `StreamHandler` vers `stderr`. Format :

```
HH:MM:SS [LEVEL] message
```

Niveau par défaut : `INFO`.

---

### `backend/nodes/__init__.py`

Importe `backend.nodes.builtin` pour déclencher les décorateurs `@register_node`.

```python
from backend.nodes import builtin  # noqa: F401
```

---

### `backend/nodes/builtin.py`

Trois nœuds enregistrés via `@register_node` :

#### `PromptBuilder`
- `node_type = "prompt_builder"`, catégorie `"llm"`.
- 1 input : `context` (string, optionnel).
- 1 output : `result` (string).
- Args : `model_name` (string, défaut `"bert-base"`), `temperature` (number, défaut `0.7`), `use_cache` (boolean, défaut `True`).
- `run()` : retourne une concaténation formatée.

#### `BrahimYoucefDemo`
- `node_type = "brahim_&_youcef_demo"`, catégorie `"demo"`.
- 2 inputs : `input_1`, `input_2` (string, optionnels).
- 2 outputs : `text` (string), `metadata` (json).
- Args : `file` (string), `cach_results` (boolean), `number_field` (integer), `checkbox_field` (boolean).
- `run()` : retourne un texte combiné et un dict metadata.

#### `OutputNode`
- `node_type = "output"`, catégorie `"io"`.
- 1 input : `text` (string, optionnel).
- 0 outputs.
- `run()` : retourne `{}`.

---

### `backend/nodes/raw_text.py`

#### `RawText`
- `node_type = "raw_text"`, catégorie `"demo"`.
- 0 inputs, 1 output `text` (string).
- Args : `text` (string, défaut `"None"`).
- `run()` : `args.get("text").split(" ")` → retourne une liste de mots.

---

### `backend/nodes/print_text.py`

#### `PrintText`
- `node_type = "print_text"`, catégorie `"demo"`.
- 1 input : `text` (string).
- 0 outputs.
- Args : `screen` (text, défaut `""`).
- `run()` : passe `inputs.get("text")` en sortie sur `screen` (passthrough display).

---

## 3. Frontend

### `src/main.jsx`

Composant principal du **mode Builder**.

#### Structures de données

```javascript
const STORAGE_KEY = "bertlike.component-builder.components";
const MODE_KEY = "bertflow.mode";
```

Un composant builder est un objet :

```javascript
{
  id: "component-<uuid>",
  name: "New Component",
  description: "...",
  fields: [{ id, label, type, value, description }],
  inputs: [{ id, label, type, description }],
  outputs: [{ id, label, type, description }],
  savedAt: ISO string
}
```

Types de champs disponibles : `text`, `number`, `toggle`, `checkbox`, `select`, `textarea`, `file`.

#### `loadComponents()`

Charge depuis `localStorage`. Si vide ou invalide, retourne un `starterComponent` (Prompt Builder avec 3 fields, 1 input, 1 output).

#### Composants d'interface

- **`Tooltip`** — info icon avec panel flottant.
- **`IconButton`** — bouton carré avec icône.
- **`AddMenu`** — dropdown avec options, trois alignements (`center`, `left`, `right`).
- **`FieldInput`** — rendu conditionnel selon le type de champ : `number` → `<input type="number">`, `toggle`/`checkbox` → `<button class="switch">`, `select` → `<select>`, `textarea` → `<textarea>`, `file` → upload via `FormData` vers `POST /api/files`, défaut → `<input type="text">`.
- **`BuilderInputPort` / `BuilderOutputPort`** — rendus memoized avec `Handle` (target à gauche, source à droite).
- **`BuilderFieldRow`** — ligne de champ avec label, `FieldInput`, bouton supprimer.
- **`ComponentNode`** — nœud ReactFlow complet : header (nom, description), inputs, fields, outputs.
- **`Inspector`** — panneau latéral :
  - Sélection de composant parmi la liste.
  - Édition du nom, description.
  - Compteurs (inputs, fields, outputs).
  - `PortEditor` (édition nom, type, description + suppression).
  - `FieldEditor` (édition label, type, description).
  - Boutons Duplicate et Export JSON.
  - Statut de sauvegarde.
- **`PortEditor`** — pour chaque port : input label, input type, input description, bouton supprimer.
- **`FieldEditor`** — pour chaque champ : input label, select type, input description.

#### Logique principale (`App`)

- `useState` : `components`, `selectedId`, `saveStatus`, `edges`.
- `updateComponent(patch)` : fusionne le patch dans le composant sélectionné, met à jour `savedAt`.
- `addField(type)` : ajoute un champ avec l'ID, label, type et valeur par défaut.
- `addPort(side)` : ajoute un port input ou output avec type `"any"`.
- `updateField(fieldId, patch)` / `removeField(fieldId)`.
- **Auto-save localStorage** : `useEffect` qui écrit `JSON.stringify(components)` dans `localStorage` à chaque changement.
- **Debounced save serveur** : `useEffect` avec `setTimeout(450ms)` pour `POST /api/components`. Statut affiché : `"Saved to ..."` ou message d'erreur.
- `addComponent()` : ajoute un composant vierge via `createComponent()`.
- `duplicateComponent()` : clone le composant sélectionné avec nouveaux IDs.
- `exportJson()` : télécharge le composant en JSON.
- `onConnect` : filtre les edges en double (même target + targetHandle).

#### Mode switch (`Root`)

Persistance du mode (`"builder"` / `"flow"`) via `location.hash` + `localStorage`. La valeur initiale est lue depuis le hash, puis localStorage.

```jsx
{mode === "builder" ? <App /> : <Flow />}
```

---

### `src/flow.jsx`

Composant principal du **mode Flow**.

#### Connexion WebSocket

URL : `import.meta.env.VITE_BACKEND_WS_URL || "ws://127.0.0.1:8765"`.

#### Structures de données

- `BACKEND_TYPE_TO_FIELD` : mapping `{string → "text", number → "number", integer → "number", boolean → "toggle"}`.

#### `backendTypeToComponent(bt)`

Convertit un `NodeTypeSchema` backend en composant local :
- `inputs` : chaque entrée `ports.inputs` → `{id: "in-<name>", label, type, description}`.
- `outputs` : chaque entrée `ports.outputs` → `{id: "out-<name>", label, type, description}`.
- `fields` : chaque entrée `args_schema` → `{id: "field-<name>", label, type: BACKEND_TYPE_TO_FIELD[def.type] || "text", value: def.default ?? (type==="number"?0 : type==="toggle"?false : ""), description}`.
- Marqueur : `_backendRef: bt.node_type`, `_backendDef: bt`.

#### `normalizePortType(type)`

Même logique que `normalize_type()` côté backend : alias `str→string`, `text→string`, etc.

#### `arePortTypesCompatible(sourceType, targetType)`

Versions frontend de la compatibilité :
```javascript
source === "any" || target === "any" ||
source === target ||
(target === "number" && (source === "int" || source === "float")) ||
(target === "float" && (source === "int" || source === "number")) ||
(target === "number" && source === "integer")
```

#### `summarizeMessage(msg)`

Génère un texte de statut lisible pour chaque type de message WebSocket.

#### Composants d'interface

- **`FlowFieldInput`** — comme `FieldInput` mais avec classes `nodrag nopan` et `stopPropagation` pour ne pas interférer avec ReactFlow.
- **`FlowFieldRow`** — label + `FlowFieldInput`.
- **`InputPortRow` / `OutputPortRow`** — port avec `Handle` (target gauche, source droite), label, type.
- **`SavedComponentNode`** — nœud ReactFlow : header (nom, description), inputs, fields, outputs. Composant memoized.
- **`FlowToolbar`** — barre d'outils : sélecteur de composants (avec `⚡` pour les nœuds backend), boutons Refresh Local, Fetch from Backend, Add, Run Flow.

#### Logique principale (`Flow`)

- **`allComponents`** : fusion des composants locaux et backend.
- **`mergeBackendComponents(backendTypes)`** :
  1. Convertit chaque type backend via `backendTypeToComponent`.
  2. Ajoute les composants locaux (sans doublon de nom).
- **`fetchFromBackend()`** :
  1. Ouvre WebSocket + timeout 5s.
  2. Envoie `{type: "get_node_types"}`.
  3. Réception `node_types` → `mergeBackendComponents` + fermeture.
- **`refreshSavedComponents()`** : recharge depuis `localStorage` et fusionne.
- **`addSelectedComponent()`** : clone le composant sélectionné et l'ajoute au canvas avec position décalée (`x: 120 + i*38, y: 120 + i*28`).
- **`onConnect`** : vérifie la compatibilité des types via `arePortTypesCompatible`. Si incompatible, statut message. Filtre les edges dupliqués.
- **`runFlow()`** — construction du payload puis exécution :

**Construction du payload `RunRequest` :**
```javascript
{
  run_id: "run-<uuid>",
  flow_id: "flow_abc123",
  schema_version: 1,
  flow_revision: 1,
  created_at: new Date().toISOString(),
  execution_config: { timeout_seconds, on_node_failure, max_retries }  // depuis env vars
}
```

**Nœuds** : pour chaque nœud du canvas :
- `node_type` = `_nodeType` (backendl ref) ou `toContractName(component.name)`.
- `args` = tous les champs sauf si `lower === "use cache" || field.id === "field-cache"`.
- `config.cache` = valeur du champ cache.
```javascript
acc[node.id] = { node_type, args, config: { cache } }
```

**Edges** : mapping des handles ReactFlow vers les noms de ports :
```javascript
{
  id: edge.id,
  from: edge.source,
  from_port: srcMap[edge.sourceHandle] || edge.sourceHandle,
  to: edge.target,
  to_port: tgtMap[edge.targetHandle] || edge.targetHandle,
}
```

**Exécution WebSocket :**
1. Nouveau WebSocket.
2. Envoi `{type: "run", payload: runPayload}`.
3. Attente des messages : `run_accepted` (info), `run_rejected` (rejet), `run_finished` (résultat).
4. En cas d'erreur de connexion ou fermeture prématurée → Promise reject.
5. Après `run_finished` : affichage console des résultats.

**Resolution des refs :**
1. Parcourt les `node_states` du résultat.
2. Pour chaque output commençant par `"store://"`, collecte dans `refsToResolve`.
3. Ouvre un second WebSocket, envoie `{type: "resolve_refs", refs: [...]}`.
4. Reçoit `{type: "refs_resolved", values: {...}}`.
5. Remplace les refs par les valeurs résolues dans `node_states`.
6. Affiche les valeurs résolues dans la console.

---

### `src/lib/server-utils.mjs`

Utilitaires côté serveur Node.js :

#### `toComponentName(name)`
Nettoie un nom pour en faire un identifiant JavaScript valide (PascalCase). Si le résultat ne commence pas par une majuscule, préfixe `Component`.

#### `escapeText(value)`
Échappe les backticks, backslashes et `$` pour les templates littéraux JSX générés.

#### `safeFileName(name)`
Remplace les caractères interdits dans les noms de fichiers (`/ \ ? % * : | " < >`) par des tirets.

#### `renderGeneratedComponent(component)`
Génère un fichier JSX complet :
- Importe React, `Handle`, `Position` depuis `@xyflow/react`.
- `FieldValue` : rendu du champ (toggle → switch, sinon texte).
- Composant principal : header, inputs avec handles, fields, outputs avec handles.
- Export `memo(ComponentName)`.

#### `readRequestBody(request, maxLength = 1_000_000)`
Lit le corps d'une requête HTTP en chunks. Limite à 1 Mo par défaut.

#### `parseMultipartFile(body, contentType)`
Parse un upload multipart :
1. Extrait le `boundary` du `Content-Type`.
2. Cherche `--boundary` dans le body.
3. Extrait les headers (dont `filename`).
4. Cherche `\r\n--boundary` suivant.
5. Retourne `{filename, data: Buffer}`.

#### `sendJson(response, statusCode, data)`
Envoie une réponse JSON avec le code status et les headers appropriés.

---

### `src/styles.css`

Single CSS file (~880 lignes) avec :

- Variables CSS pour thème clair.
- Layout : `app-shell` (grid 2 colonnes), `flow-page` (full viewport).
- Styles des composants : `builder-node` (720px), `generated-component-node` (520px), ports, fields, switches, tooltips.
- `AddMenu` avec dropdown positionné.
- Media queries pour responsive (breakpoints 1120px, 980px, 660px).

---

### `src/components/generated/`

Dossier contenant les fichiers JSX générés automatiquement par le Builder via `POST /api/components`. Exemples : `PromptBuilder.jsx`, `Output.jsx`, `BrahimYoucefDemo.jsx`, `DocumentUpload.jsx`, etc. Chaque fichier est un composant React avec ports et fields, exporté via `export default memo(ComponentName)`.

---

## 4. Contrats de Communication WebSocket

### Connexion initiale (auto-send)

Dès qu'un client se connecte, le serveur envoie automatiquement :

```json
{
  "type": "node_types",
  "node_types": [
    {
      "node_type": "prompt_builder",
      "version": "1.0.0",
      "label": "Prompt Builder",
      "description": "Collects prompt settings...",
      "category": "llm",
      "ui_config": {"icon": "bot", "color": "#4A90D9", "category_order": 1},
      "ports": {
        "inputs": {"context": {"type": "string", "required": false, "default": null}},
        "outputs": {"result": {"type": "string"}}
      },
      "args_schema": {
        "model_name": {"type": "string", "default": "bert-base"},
        "temperature": {"type": "number", "default": 0.7},
        "use_cache": {"type": "boolean", "default": true}
      }
    }
  ]
}
```

### Requête → Réponse

| Requête | Réponse |
|---|---|
| `{"type": "get_node_types"}` | `{"type": "node_types", "node_types": [...]}` |
| `{"type": "ping"}` | `{"type": "pong"}` |
| `{"type": "run", "payload": {...}}` | `{"type": "run_accepted", "run_id": "...", "n_nodes": N, "n_edges": M}` puis `{"type": "run_finished", "run_id": "...", "state": {...}}` **ou** `{"type": "run_rejected", "run_id": "...", "errors": [...]}` |
| `{"type": "resolve_refs", "refs": ["store://...", ...]}` | `{"type": "refs_resolved", "values": {"store://...": ..., ...}}` |

### Réponse `run_finished`

```json
{
  "type": "run_finished",
  "run_id": "run-<uuid>",
  "state": {
    "status": "completed",
    "node_states": {
      "<node_id>": {
        "status": "completed",
        "outputs": {
          "result": "Valeur inline",
          "large_data": "store://run-xxx/<node_id>/large_data"
        },
        "cached": false,
        "error": null
      }
    }
  }
}
```

En cas d'échec global : `state.status = "failed"`, `state.error = "message"`.

### Erreurs

| Situation | Réponse |
|---|---|
| JSON invalide | `{"type": "parse_error", "message": "Invalid JSON: ..."}` |
| Type de message inconnu | `{"type": "error", "message": "Unknown message type '...'"}` |
| Erreur interne | `{"type": "error", "message": "Internal server error: ..."}` |

---

## 5. Détails d'Implémentation Importants

### Cache d'exécution

- Activé par `node.config.cache = True` dans le `RunRequest`.
- Clé de cache = `SHA-256( json.dumps([node_type, args, inputs], sort_keys=True) )`.
- Arguments normalisés par `sort_keys=True` pour garantir la reproductibilité.
- Vérifié au début de `_run_node()` : si hit, le nœud est marqué `cached=True` et le résultat est retourné immédiatement sans exécution.
- Stocké dans le dictionnaire `InMemoryExecutionCache._cache` (volatile, perdu au redémarrage).
- Mis en cache immédiatement après une exécution réussie.

### Stockage hybride inline/ref

- Seuil : `HYBRID_THRESHOLD = 1024` octets.
- Les valeurs `None`, `bool`, `int`, `float` sont **toujours** inline (pas de overhead de résolution).
- Les chaînes de moins de 1024 caractères sont inline.
- Les objets JSON sérialisables de moins de 1024 octets sont inline.
- Les valeurs dépassant le seuil sont stockées sous forme de référence : `store://<run_id>/<node_id>/<port>`.
- Les refs sont résolues côté client via un second appel WebSocket `resolve_refs`.
- `build_outputs()` applique cette logique port par port.

### Exécution parallèle par vagues (Kahn Wave)

- Basée sur l'algorithme de Kahn pour le tri topologique.
- L'exécuteur calcule les degrés entrants de chaque nœud.
- **Vague** = ensemble des nœuds avec `in_degree == 0` à un instant donné.
- Tous les nœuds d'une vague sont exécutés **en parallèle** via `asyncio.gather()`.
- Une fois une vague terminée, les sorties sont propagées aux nœuds aval, leurs `in_degree` décrémentés.
- Nouvelle vague = nœuds dont `in_degree` vient de passer à 0.
- Si aucune vague n'est prête mais qu'il reste des nœuds en attente → échec (dépendance non satisfaite, probablement un cycle ou un graphe déconnecté).
- Le timeout global (`asyncio.timeout()`) couvre l'ensemble de l'exécution.

### Validation en 6 étapes (ordre strict)

1. **Existence des nœuds** + injection des valeurs par défaut des `args_schema`.
2. **Unicité des IDs d'arêtes**.
3. **Existence des nœuds source et target** dans la requête.
4. **Existence des ports** sur les nœuds enregistrés.
5. **Compatibilité des types** entre `source_type` et `target_type`.
6. **Unicité des edges entrants** par port cible.

Ensuite :

- **Tri topologique (Kahn)** : détection de cycles.
- **BFS des composantes connexes** : identification des sous-graphes isolés.

### Auto-découverte des nœuds

- `NodeRegistry.discover()` utilise le système de modules Python.
- Parcourt `backend/nodes/`, importe tous les fichiers `.py` (sauf `__init__.py`).
- Chaque import déclenche les décorateurs `@register_node` qui peuplent le dictionnaire global `_registry`.
- `discover()` copie `_registry` dans l'instance.
- L'ordre d'import est alphabétique (`sorted(os.listdir(...))`).

### Logique de retry (backoff exponentiel)

- `max_retries` est configurable par `RunRequest.execution_config.max_retries` (défaut 0).
- La boucle exécute `max_retries + 1` tentatives (la première + les retries).
- Délai entre les tentatives : `asyncio.sleep(0.1 * (attempt + 1))` → 0.1s, 0.2s, 0.3s, ...
- Après épuisement : `NodeExecutionError` avec le nombre total de tentatives et la dernière erreur.
- En mode `"halt"`, l'exécution s'arrête immédiatement. En mode `"skip"`, le nœud est marqué `failed` mais les autres continuent.

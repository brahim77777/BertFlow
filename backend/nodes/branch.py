from backend.core.registry import register_node


@register_node
class FlowBranch:
    node_type = "flow-branch"
    label = "branch output"
    category = "demo"
    inputs = {"text": {"type": "List[str]"}}
    outputs = {"branch1": {"type": "string"}, "branch2": {"type": "string"}}
    args_schema = {"screen": {"type": "text", "default": ""}}

    @staticmethod
    async def run(args, inputs, context):

        return {"branch1": inputs.get("text", "default 1"), "branch2": inputs.get("text", "default 2")}

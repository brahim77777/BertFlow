from backend.core.registry import register_node


@register_node
class PrintText:
    node_type = "print_text"
    label = "print value recieved"
    category = "demo"
    inputs = {"text": {"type": "string"}}
    outputs = {}
    args_schema = {"screen": {"type": "text", "default": ""}}

    @staticmethod
    async def run(args, inputs, context):
        screen = inputs.get("text")
        return {"screen": screen}

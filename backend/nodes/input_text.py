from backend.core.registry import register_node


@register_node
class InputText:
    node_type = "input_text"
    label = "input text"
    category = "demo"
    inputs = {}
    outputs = {"text": {"type": "string"}}
    args_schema = {"input": {"type": "text", "default": ""}}

    @staticmethod
    async def run(args, inputs, context):
        input_text = args.get("input")
        return {"text": input_text}

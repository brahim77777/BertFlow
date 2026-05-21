from backend.core.registry import register_node


@register_node
class RawText:
    node_type = "raw_text"
    label = "Raw Text"
    category = "demo"
    inputs = {}
    outputs = {"text": {"type": "text"}, "len": {"type": "int"}}
    args_schema = {"text": {"type": "string", "default": ""}}

    @staticmethod
    async def run(args, inputs, context):
        raw = args.get("text", "")
        if not raw:
            raise ValueError("text argument is empty")
        text = raw 
        return {"text": text, "len": len(text)}

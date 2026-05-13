from backend.core.registry import register_node


@register_node
class RawText:
    node_type = "raw_text"
    label = "Raw Text"
    category = "demo"
    inputs = {}
    outputs = {"text": {"type": "List[str]"}, "len":{"type":"int", "default":0}}
    args_schema = {"text": {"type": "string", "default": "None"}}

    @staticmethod
    async def run(args, inputs, context):
        text = args.get("text").split(" ")
        
        return {"text": text, "len": len(text)}

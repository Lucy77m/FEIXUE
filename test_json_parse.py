import json

# Simulate what happens when LLM produces float
json_from_llm = '{"pid": 1234.5, "address": "0x7fff0000", "size": 256}'
parsed = json.loads(json_from_llm)
print(f"JSON-parsed arguments: {parsed}")
print(f"Type of pid: {type(parsed['pid'])}")
print(f"Value of pid: {parsed['pid']}")

# Now pass to int()
pid_converted = int(parsed['pid'])
print(f"\nint({parsed['pid']}) -> {pid_converted}")
print(f"Original pid: {1234.5}")
print(f"Converted pid: {pid_converted}")
print(f"Data loss: {1234.5} != {pid_converted}")

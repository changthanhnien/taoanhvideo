import json

d = json.load(open('debug_getModels.json', 'r', encoding='utf-8'))
mc = d['result']['data']['json']['result']['modelConfig']

print("=== imageModels ===")
imgs = mc.get('imageModels', [])
print(f"Type: {type(imgs)}, Count: {len(imgs)}")
for m in imgs:
    if isinstance(m, dict):
        print(f"  {m.get('displayName', '?')} | key={m.get('key', '?')} | type={m.get('type', '?')}")
        print(f"    keys: {list(m.keys())}")
    else:
        print(f"  {m}")

print("\n=== videoModels ===")
vids = mc.get('videoModels', [])
print(f"Type: {type(vids)}, Count: {len(vids)}")
for m in vids:
    if isinstance(m, dict):
        print(f"  {m.get('displayName', '?')} | key={m.get('key', '?')} | type={m.get('type', '?')}")
        print(f"    keys: {list(m.keys())}")
    else:
        print(f"  {m}")

print("\n=== audioModels ===")
auds = mc.get('audioModels', [])
print(f"Type: {type(auds)}, Count: {len(auds)}")
for m in auds:
    if isinstance(m, dict):
        print(f"  {m.get('displayName', '?')} | key={m.get('key', '?')}")
    else:
        print(f"  {m}")

print("\n=== tierDefaults ===")
td = mc.get('tierDefaults', {})
print(json.dumps(td, ensure_ascii=False, indent=2)[:500])

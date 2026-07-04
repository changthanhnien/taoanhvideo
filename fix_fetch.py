with open('services/flow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace credentials: "omit" with "include" in the fetch call
if 'credentials: "omit"' in content:
    content = content.replace('credentials: "omit"', 'credentials: "include"')
    with open('services/flow_client.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed fetch credentials!")
else:
    print("Could not find credentials: 'omit'")

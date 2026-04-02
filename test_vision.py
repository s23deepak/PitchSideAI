import base64
import requests
import json
import sys

files = ["test_images/var.jpg", "test_images/formation.png", "test_images/direct free kick.jpg"]
for file in files:
    with open(file, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    
    try:
        res = requests.post("http://localhost:8080/api/v1/frame/analyze", json={"frame_b64": b64, "sport": "soccer"})
        if res.status_code == 200:
            data = res.json()
            analysis = data.get("analysis", {})
            print(f"File: {file}")
            print(f"  Status: {data.get('status')}")
            print(f"  Label:  {analysis.get('tactical_label')}")
            print(f"  Obs:    {analysis.get('key_observation')}")
            print("-" * 40)
        else:
            print(f"File: {file} -> HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"Error testing {file}: {e}")

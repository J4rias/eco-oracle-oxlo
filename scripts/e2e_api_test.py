import httpx
import json
import time
import subprocess
import sys
from pathlib import Path

def main():
    print("🚀 Starting local FastAPI server (uvicorn)...")
    server_process = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", "8000"])
    
    # Wait for the server to initialize (3 seconds)
    time.sleep(3)
    
    print("\n📦 Sending the test polygon to the server (POST /api/v1/compliance/analyze)...")
    
    url = "http://localhost:8000/api/v1/compliance/analyze"
    geojson_path = Path("tests/fixtures/sample_farm.geojson")
    
    if not geojson_path.exists():
        print(f"❌ File not found: {geojson_path}")
        server_process.terminate()
        return

    # Emulated audit metadata (Coffee)
    metadata = {
        "crop_type": "Coffee",
        "harvest_date": "2024-05-15",
        "invoice_id": "INV-E2E-TEST",
        "reported_tons": 12.5
    }
    
    try:
        with open(geojson_path, "rb") as f:
            files = {"geojson_file": ("sample_farm.geojson", f, "application/geo+json")}
            data = {"metadata": json.dumps(metadata)}
            
            with httpx.Client(timeout=120) as client:
                response = client.post(url, data=data, files=files)
                
        print(f"\n✅ HTTP Response Status Code: {response.status_code}")
        print("\n📄 Compliance Report (JSON):\n")
        print(json.dumps(response.json(), indent=4, ensure_ascii=False))
        
    except httpx.ReadTimeout:
        print("\n❌ Error: The analyzer took too long. This sometimes happens when the Oxlo API takes time to load the DeepSeek model.")
    except Exception as e:
        print(f"\n❌ An error occurred while sending the request: {e}")
        
    finally:
        print("\n🛑 Shutting down local server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    main()

import json
import requests
import os
import time

BASE_URL = "http://localhost:8000/api/v1/compliance/analyze"
EXAMPLES_DIR = "examples"

USE_CASES = [
    {
        "name": "CASE 1: PASS (Coffee, Colombia)",
        "geojson": "coffee_pass_colombia.geojson",
        "metadata": {
            "crop_type": "Coffee",
            "harvest_date": "2026-03-15",
            "invoice_id": "INV-COF-2026-001",
            "reported_tons": 12.5
        },
        "expected_verdict": "PASS"
    },
    {
        "name": "CASE 2: REVIEW (Cocoa, Ivory Coast)",
        "geojson": "cocoa_review_ivory_coast.geojson",
        "metadata": {
            "crop_type": "Cocoa",
            "harvest_date": "2026-02-10",
            "invoice_id": "INV-COC-2026-089",
            "reported_tons": 45.0
        },
        "expected_verdict": "REQUIRES_HUMAN_REVIEW"
    },
    {
        "name": "CASE 3: FAIL (Palm Oil, Indonesia)",
        "geojson": "palm_fail_indonesia.geojson",
        "metadata": {
            "crop_type": "Palm Oil",
            "harvest_date": "2026-01-20",
            "invoice_id": "INV-PALM-2026-X12",
            "reported_tons": 150.0
        },
        "expected_verdict": "FAIL"
    },
    {
        "name": "CASE 4: REJECTED (Urban Bogota)",
        "geojson": "urban_rejected_bogota.geojson",
        "metadata": {
            "crop_type": "Other",
            "harvest_date": "2026-03-01",
            "invoice_id": "INV-URBAN-BOGOTA",
            "reported_tons": 10.0
        },
        "expected_verdict": "REJECTED_URBAN_AREA"
    }
]

def run_test():
    print("=" * 80)
    print("ECOORACLE USE CASE VERIFICATION TEST")
    print("=" * 80)
    print(f"Target API: {BASE_URL}")
    print("-" * 80)

    results = []

    for case in USE_CASES:
        print(f"\n🚀 Running {case['name']}...")
        
        geojson_path = os.path.join(EXAMPLES_DIR, case['geojson'])
        if not os.path.exists(geojson_path):
            print(f"❌ Error: {geojson_path} not found!")
            results.append((case['name'], "MISSING FILE", "FAIL"))
            continue

        with open(geojson_path, 'rb') as f:
            files = {'geojson_file': (case['geojson'], f, 'application/json')}
            data = {'metadata': json.dumps(case['metadata'])}
            
            try:
                # SSE response
                response = requests.post(BASE_URL, files=files, data=data, stream=True, timeout=180)
                
                final_verdict = None
                
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data: '):
                            event_data = json.loads(decoded_line[6:])
                            
                            # Log progress
                            if event_data.get('type') == 'node_start':
                                print(f"  • Node: {event_data.get('node')}")
                            
                            if event_data.get('type') == 'final':
                                final_verdict = event_data.get('data', {}).get('report', {}).get('verdict')
                                break
                            
                            if event_data.get('type') == 'error':
                                print(f"  ❌ Backend Error: {event_data.get('detail')}")
                                break

                if final_verdict == case['expected_verdict']:
                    print(f"✅ SUCCESS: Got {final_verdict}")
                    results.append((case['name'], final_verdict, "OK"))
                else:
                    print(f"❌ FAILED: Expected {case['expected_verdict']}, got {final_verdict}")
                    results.append((case['name'], final_verdict, "WRONG VERDICT"))

            except Exception as e:
                print(f"💥 Exception: {str(e)}")
                results.append((case['name'], "CRASH", "FAIL"))

    print("\n" + "=" * 80)
    print(f"{'USE CASE':<40} | {'ACTUAL':<20} | {'STATUS':<10}")
    print("-" * 80)
    for name, actual, status in results:
        print(f"{name:<40} | {str(actual):<20} | {status:<10}")
    print("=" * 80)

if __name__ == "__main__":
    run_test()

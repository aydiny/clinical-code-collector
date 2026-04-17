import requests

def test_opencodelists_api():
    org = "nhs-drug-refsets"
    codelist_id = "sglt2idrug_cod"
    
    api_url = f"https://www.opencodelists.org/api/v1/codelist/{org}/{codelist_id}/"
    print(f"🌍 1. Pinging OpenCodelists API: {api_url}")
    
    try:
        # Step 1: Get the JSON metadata
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        latest_version = data["versions"][0]["id"]
        print(f"✅ 2. Success! Latest version hash detected: {latest_version}")
        
        # Step 2: Construct the CSV URL
        download_url = f"https://www.opencodelists.org/codelist/{org}/{codelist_id}/{latest_version}/download.csv"
        print(f"🔗 3. Constructed CSV URL: {download_url}")
        
        # Step 3: Actually download the CSV to prove data flows
        print("\n📄 4. Fetching the actual CSV data...")
        csv_response = requests.get(download_url, timeout=10)
        csv_response.raise_for_status()
        
        lines = csv_response.text.splitlines()
        print(f"✅ Downloaded {len(lines)} rows! Here are the first 3:")
        for i, line in enumerate(lines[:3]):
            print(f"  Row {i}: {line}")
            
    except Exception as e:
        print(f"\n❌ API Test Failed: {e}")

if __name__ == "__main__":
    test_opencodelists_api()
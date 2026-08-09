import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    print("--- 1. Testing Health Endpoint ---")
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_extract_metadata():
    print("\n--- 2. Testing Full Metadata Extraction Endpoint ---")
    test_url = "https://github.com"
    
    # Initial request (live fetch)
    response = client.get(f"/api/v1/extract?url={test_url}")
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    print("Extracted Data (Initial Fetch):")
    print(f" - Final URL: {data['final_url']}")
    print(f" - Title: {data['metadata']['title']}")
    print(f" - Description: {data['metadata']['description']}")
    print(f" - Favicon: {data['metadata']['favicon']}")
    print(f" - Social Links Found: {data['social_links']}")
    print(f" - Technologies Detected: {data['detected_technologies']}")
    print(f" - RSS Feeds Found: {data['rss_feeds']}")
    print(f" - Security Score: {data['security_score_percentage']}%")
    print(f" - Execution Time: {data['execution_time_ms']} ms")
    
    # Second request (memory cache hit)
    response_cached = client.get(f"/api/v1/extract?url={test_url}")
    assert response_cached.status_code == 200
    data_cached = response_cached.json()
    print(f" - Cache Hit Time: {data_cached['execution_time_ms']} ms")
    assert data_cached['execution_time_ms'] < 5.0

def test_field_filtering():
    print("\n--- 3. Testing Dynamic Fields Filtering ---")
    test_url = "https://github.com"
    response = client.get(f"/api/v1/extract?url={test_url}&fields=metadata,contacts")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "contacts" in data
    assert "social_links" not in data
    print(" [Fields Filter OK] Selected keys only: metadata, contacts")

def test_sub_endpoints():
    print("\n--- 4. Testing Specialized Sub-Endpoints ---")
    test_url = "https://github.com"

    # Link Preview
    res_lp = client.get(f"/api/v1/link-preview?url={test_url}")
    assert res_lp.status_code == 200
    data_lp = res_lp.json()
    assert "title" in data_lp
    assert "og_image" in data_lp
    print(f" [Link Preview OK] Title: {data_lp['title'][:40]}... (Time: {data_lp['execution_time_ms']} ms)")

    # Contacts
    res_c = client.get(f"/api/v1/contacts?url={test_url}")
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert "emails" in data_c
    assert "social_links" in data_c
    print(f" [Contacts OK] Socials found: {sum(1 for v in data_c['social_links'].values() if v)}")

    # Tech Stack
    res_ts = client.get(f"/api/v1/tech-stack?url={test_url}")
    assert res_ts.status_code == 200
    data_ts = res_ts.json()
    assert "detected_technologies" in data_ts
    print(f" [Tech Stack OK] Technologies: {data_ts['detected_technologies']}")

    # Schema JSON-LD
    res_sc = client.get(f"/api/v1/schema?url={test_url}")
    assert res_sc.status_code == 200
    data_sc = res_sc.json()
    assert "json_ld_schemas" in data_sc
    print(f" [Schema.org JSON-LD OK] Schemas count: {data_sc['json_ld_count']}")

    # Security Headers Audit
    res_sec = client.get(f"/api/v1/security?url={test_url}")
    assert res_sec.status_code == 200
    data_sec = res_sec.json()
    assert "security_headers" in data_sec
    print(f" [Security Audit OK] Score: {data_sec['security_score_percentage']}%")

if __name__ == "__main__":
    try:
        test_health()
        test_extract_metadata()
        test_field_filtering()
        test_sub_endpoints()
        print("\n[OK] ALL TESTS PASSED SUCCESSFULLY")
    except Exception as e:
        print(f"\n[ERROR] Test suite failed: {e}")
        sys.exit(1)

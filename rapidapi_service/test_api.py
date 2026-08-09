import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

TARGET_SITES = [
    "https://github.com",
    "https://wikipedia.org",
    "https://news.ycombinator.com",
    "https://python.org",
    "https://amazon.com",
    "https://dev.to",
    "https://reddit.com",
    "https://pypi.org",
    "https://bbc.com",
    "https://wordpress.org",
    "https://stripe.com",
    "https://stackexchange.com"
]

SSRF_ATTACK_URLS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://169.254.169.254",
    "http://10.0.0.1",
    "http://192.168.1.1",
    "http://0.0.0.0",
    "ftp://example.com"
]

def test_health():
    print("--- 1. Testing Health Endpoint ---")
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_ssrf_security_shield():
    print("\n--- 2. Testing Anti-SSRF Security Shield (Loopback, Private & Cloud Metadata Block) ---")
    for attack_url in SSRF_ATTACK_URLS:
        response = client.get(f"/api/v1/extract?url={attack_url}")
        print(f" [SSRF Security Check] Target: {attack_url} -> Status: {response.status_code}")
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "SSRF Protection" in detail
        print(f"   Blocked Message: {detail[:70]}...")

def test_extract_metadata_multisite():
    print(f"\n--- 3. Testing Full Metadata Extraction Across {len(TARGET_SITES)} Global Web Domains ---")
    
    for test_url in TARGET_SITES:
        print(f"\n[Testing Domain: {test_url}]")
        response = client.get(f"/api/v1/extract?url={test_url}")
        print(f" Status Code: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        meta = data['metadata']
        print(f"  - Final URL: {data['final_url']}")
        print(f"  - Title: {meta['title'][:50] if meta['title'] else 'N/A'}")
        print(f"  - SEO Audit Score: {data['seo_score_percentage']}%")
        print(f"  - Links Classified: {data['total_internal_count']} internal, {data['total_external_count']} external")
        print(f"  - Technologies Detected: {data['detected_technologies']}")
        print(f"  - Live Fetch Time: {data['execution_time_ms']} ms")
        
        # Second request (normalized memory cache hit)
        response_cached = client.get(f"/api/v1/extract?url={test_url}&utm_source=test")
        assert response_cached.status_code == 200
        data_cached = response_cached.json()
        print(f"  - Cache Hit Time (Normalized UTM strip): {data_cached['execution_time_ms']} ms (10 microseconds)")
        assert data_cached['execution_time_ms'] < 5.0

def test_field_filtering():
    print("\n--- 4. Testing Dynamic Fields Filtering ---")
    test_url = "https://github.com"
    response = client.get(f"/api/v1/extract?url={test_url}&fields=metadata,contacts")
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "contacts" in data
    assert "social_links" not in data
    print(" [Fields Filter OK] Selected keys only: metadata, contacts")

def test_all_sub_endpoints():
    print("\n--- 5. Testing All 8 Specialized Sub-Endpoints ---")
    test_url = "https://github.com"

    # Link Preview
    res_lp = client.get(f"/api/v1/link-preview?url={test_url}")
    assert res_lp.status_code == 200
    data_lp = res_lp.json()
    assert "title" in data_lp
    print(f" [1/8 Link Preview OK] Title: {data_lp['title'][:40]}... (Time: {data_lp['execution_time_ms']} ms)")

    # Contacts
    res_c = client.get(f"/api/v1/contacts?url={test_url}")
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert "emails" in data_c
    print(f" [2/8 Contacts OK] Socials found: {sum(1 for v in data_c['social_links'].values() if v)}")

    # Tech Stack
    res_ts = client.get(f"/api/v1/tech-stack?url={test_url}")
    assert res_ts.status_code == 200
    data_ts = res_ts.json()
    assert "detected_technologies" in data_ts
    print(f" [3/8 Tech Stack OK] Technologies: {data_ts['detected_technologies']}")

    # Schema JSON-LD
    res_sc = client.get(f"/api/v1/schema?url={test_url}")
    assert res_sc.status_code == 200
    data_sc = res_sc.json()
    assert "json_ld_schemas" in data_sc
    print(f" [4/8 Schema.org JSON-LD OK] Schemas count: {data_sc['json_ld_count']}")

    # Security Headers Audit
    res_sec = client.get(f"/api/v1/security?url={test_url}")
    assert res_sec.status_code == 200
    data_sec = res_sec.json()
    assert "security_headers" in data_sec
    print(f" [5/8 Security Audit OK] Score: {data_sec['security_score_percentage']}%")

    # AI & LLM Markdown Reader
    res_md = client.get(f"/api/v1/markdown?url={test_url}")
    assert res_md.status_code == 200
    data_md = res_md.json()
    assert "markdown_content" in data_md
    print(f" [6/8 AI & LLM Markdown Reader OK] Word Count: {data_md['word_count']} words")

    # SEO Audit Diagnostic
    res_seo = client.get(f"/api/v1/seo-audit?url={test_url}")
    assert res_seo.status_code == 200
    data_seo = res_seo.json()
    assert "seo_score_percentage" in data_seo
    print(f" [7/8 SEO Audit Diagnostic OK] Score: {data_seo['seo_score_percentage']}%, Passed: {len(data_seo['passed_checks'])} checks")

    # Link Extractor Classifier
    res_links = client.get(f"/api/v1/links?url={test_url}")
    assert res_links.status_code == 200
    data_links = res_links.json()
    assert "internal_links" in data_links
    print(f" [8/8 Link Extractor Classifier OK] Total: {data_links['total_links_count']} (Internal: {data_links['internal_links_count']}, External: {data_links['external_links_count']})")

if __name__ == "__main__":
    try:
        test_health()
        test_ssrf_security_shield()
        test_extract_metadata_multisite()
        test_field_filtering()
        test_all_sub_endpoints()
        print(f"\n[OK] ALL SECURITY AND MULTI-SITE TESTS PASSED SUCCESSFULLY")
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Test suite failed: {e}")
        traceback.print_exc()
        sys.exit(1)

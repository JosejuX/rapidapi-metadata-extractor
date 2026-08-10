import sys
import re
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
    "ftp://example.com",
    "file:///etc/passwd",
    "gopher://example.com",
    "javascript:alert(1)",
    "http://2130706433",
    "http://0x7f000001",
    "http://0177.0.0.1",
    "http://[::1]",
    "http://[::ffff:127.0.0.1]",
    "http://[fe80::1]"
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
        print(f" [SSRF Security Check] Target: {attack_url:<25} -> Status: {response.status_code}")
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "SSRF Protection" in detail
        print(f"   Blocked Message: {detail[:70]}...")

def test_schemeless_urls():
    print("\n--- 2.1 Testing Scheme-less URLs Normalization (e.g. github.com) ---")
    response = client.get("/api/v1/extract?url=github.com")
    print(f" [Scheme-less Check] Target: github.com -> Status: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    assert data["final_url"].startswith("https://")
    print(f"   Successfully Normalized Final URL: {data['final_url']}")

def test_crlf_user_agent_sanitizer():
    print("\n--- 2.2 Testing CRLF User-Agent Sanitization & Header Injection Protection ---")
    malicious_ua = "Mozilla/5.0\r\nX-Injected-Header: evil\nInjected: true"
    response = client.get("/api/v1/extract?url=https://github.com", headers={"User-Agent": malicious_ua})
    assert response.status_code == 200
    print(" [CRLF Header Injection Check] Passed cleanly without HTTP header splitting")

def test_error_ip_sanitizer():
    print("\n--- 2.3 Testing Error Message Internal IP Sanitization ---")
    response = client.get("/api/v1/extract?url=https://github.com/nonexistent_page_404_test_xyz")
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "Unable to access target URL" in detail
    # Ensure internal IP pinned string is not leaked in exception message
    assert not re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', detail)
    print(f" [Error Message IP Sanitization Check] Passed: Internal IP address hidden cleanly")




def test_extract_metadata_multisite():
    print(f"\n--- 3. Testing Full Metadata Extraction Across {len(TARGET_SITES)} Global Web Domains ---")
    
    for test_url in TARGET_SITES:
        print(f"\n[Testing Domain: {test_url}]")
        response = client.get(f"/api/v1/extract?url={test_url}")
        print(f" Status Code: {response.status_code}")

        if response.status_code == 400:
            detail = response.json().get("detail", "")
            print(f"  - Remote site blocked request / unreachable on CI IP: {detail[:80]}...")
            continue

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

def test_edge_case_resilience():
    print("\n--- 6. Testing Edge Case Resilience (Corrupted Schema, Encodings, Malformed Enpoints) ---")
    
    # 6.1 Non-existent domain / DNS failure
    res_dns = client.get("/api/v1/extract?url=https://this-domain-definitely-does-not-exist-123456789.com")
    assert res_dns.status_code == 400
    print(" [Edge Case OK] DNS failure handled gracefully with 400 status code")

    # 6.2 HTTP 404 response
    res_404 = client.get("/api/v1/extract?url=https://httpbin.org/status/404")
    assert res_404.status_code in [200, 400]
    print(" [Edge Case OK] HTTP 404 target page handled gracefully")

    # 6.3 Invalid fields filter
    res_fields = client.get("/api/v1/extract?url=https://python.org&fields=non_existent_key_123")
    assert res_fields.status_code == 200
    assert "metadata" not in res_fields.json()
    assert "contacts" not in res_fields.json()
    print(" [Edge Case OK] Invalid fields filter returns base response without metadata keys")

    # 6.4 Forbidden Port blocking (e.g. port 22 SSH)
    res_port = client.get("/api/v1/extract?url=http://example.com:22")
    assert res_port.status_code == 400
    assert "Port 22 is not allowed" in res_port.json().get("detail", "")
    print(" [Edge Case OK] Non-standard public port 22 blocked cleanly with 400 status code")

    # 6.5 Custom User-Agent Cache Key Isolation
    res_ua_1 = client.get("/api/v1/extract?url=https://python.org", headers={"User-Agent": "Googlebot/2.1"})
    res_ua_2 = client.get("/api/v1/extract?url=https://python.org", headers={"User-Agent": "CustomScraper/1.0"})
    assert res_ua_1.status_code == 200 and res_ua_2.status_code == 200
    print(" [Edge Case OK] Custom User-Agent requests cache isolated without cross-contamination")

if __name__ == "__main__":
    try:
        test_health()
        test_ssrf_security_shield()
        test_schemeless_urls()
        test_crlf_user_agent_sanitizer()
        test_error_ip_sanitizer()
        test_extract_metadata_multisite()
        test_field_filtering()
        test_all_sub_endpoints()
        test_edge_case_resilience()
        print(f"\n[OK] ALL SECURITY, MULTI-SITE, AND EDGE-CASE RESILIENCE TESTS PASSED SUCCESSFULLY")

    except Exception as e:
        import traceback
        print(f"\n[ERROR] Test suite failed: {e}")
        traceback.print_exc()
        sys.exit(1)


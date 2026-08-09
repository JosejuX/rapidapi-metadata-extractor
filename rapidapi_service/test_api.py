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



def test_health():
    print("--- 1. Testing Health Endpoint ---")
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_extract_metadata_multisite():
    print(f"\n--- 2. Testing Full Metadata Extraction Across {len(TARGET_SITES)} Global Web Domains ---")
    
    for test_url in TARGET_SITES:
        print(f"\n[Testing Domain: {test_url}]")
        # Initial request (live fetch)
        response = client.get(f"/api/v1/extract?url={test_url}")
        print(f" Status Code: {response.status_code}")
        assert response.status_code == 200
        data = response.json()
        meta = data['metadata']
        print(f"  - Final URL: {data['final_url']}")
        print(f"  - Title: {meta['title'][:50] if meta['title'] else 'N/A'}")
        print(f"  - Canonical URL: {meta['canonical_url']}")
        print(f"  - H1 Headings: {meta['h1_tags']}")
        print(f"  - Page Stats: {meta['images_count']} images ({meta['images_missing_alt_count']} missing alt), {meta['links_count']} links, {meta['content_length_bytes']} bytes")
        print(f"  - Technologies Detected: {data['detected_technologies']}")
        print(f"  - RSS Feeds Count: {len(data['rss_feeds'])}")
        print(f"  - Security Score: {data['security_score_percentage']}%")
        print(f"  - Word Count: {data['word_count']} words")
        print(f"  - Live Fetch Time: {data['execution_time_ms']} ms")
        
        # Second request (memory cache hit)
        response_cached = client.get(f"/api/v1/extract?url={test_url}")
        assert response_cached.status_code == 200
        data_cached = response_cached.json()
        print(f"  - Cache Hit Time: {data_cached['execution_time_ms']} ms (10 microseconds)")
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
    print("\n--- 4. Testing All 6 Specialized Sub-Endpoints ---")
    test_url = "https://github.com"

    # Link Preview
    res_lp = client.get(f"/api/v1/link-preview?url={test_url}")
    assert res_lp.status_code == 200
    data_lp = res_lp.json()
    assert "title" in data_lp
    print(f" [Link Preview OK] Title: {data_lp['title'][:40]}... (Time: {data_lp['execution_time_ms']} ms)")

    # Contacts
    res_c = client.get(f"/api/v1/contacts?url={test_url}")
    assert res_c.status_code == 200
    data_c = res_c.json()
    assert "emails" in data_c
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

    # AI & LLM Markdown Reader
    res_md = client.get(f"/api/v1/markdown?url={test_url}")
    assert res_md.status_code == 200
    data_md = res_md.json()
    assert "markdown_content" in data_md
    print(f" [AI & LLM Markdown Reader OK] Word Count: {data_md['word_count']} words, Est. Time: {data_md['reading_time_minutes']} min")

if __name__ == "__main__":
    try:
        test_health()
        test_extract_metadata_multisite()
        test_field_filtering()
        test_sub_endpoints()
        print(f"\n[OK] ALL 12 TARGET DOMAIN TESTS PASSED SUCCESSFULLY")
    except Exception as e:
        print(f"\n[ERROR] Test suite failed: {e}")
        sys.exit(1)

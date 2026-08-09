import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    print("--- 1. Probando Endpoint de Health ---")
    response = client.get("/health")
    print(f"Status Code: {response.status_code}")
    print(f"Respuesta: {response.json()}")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_extract_metadata():
    print("\n--- 2. Probando Endpoint de Extracción de Metadatos ---")
    test_url = "https://github.com"
    
    # Primera petición (Fetch real)
    response = client.get(f"/api/v1/extract?url={test_url}")
    print(f"Status Code: {response.status_code}")
    assert response.status_code == 200
    data = response.json()
    print("Resultado extraído (Petición Inicial):")
    print(f" - Título: {data['metadata']['title']}")
    print(f" - Descripción: {data['metadata']['description']}")
    print(f" - Favicon: {data['metadata']['favicon']}")
    print(f" - Redes encontradas: {data['social_links']}")
    print(f" - Tecnologías detectadas: {data['detected_technologies']}")
    print(f" - Tiempo de ejecución: {data['execution_time_ms']} ms")
    
    # Segunda petición (Caché hit)
    response_cached = client.get(f"/api/v1/extract?url={test_url}")
    assert response_cached.status_code == 200
    data_cached = response_cached.json()
    print(f" - Tiempo en Caché: {data_cached['execution_time_ms']} ms")
    assert data_cached['execution_time_ms'] < 5.0

if __name__ == "__main__":
    try:
        test_health()
        test_extract_metadata()
        print("\n[OK] TODAS LAS PRUEBAS PASADAS CON EXITO")
    except Exception as e:
        print(f"\n[ERROR] Error durante las pruebas: {e}")
        sys.exit(1)

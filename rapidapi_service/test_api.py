import sys
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    print("--- 1. Probando Endpoint de Health ---")
    response = client.get("/")
    print(f"Status Code: {response.status_code}")
    print(f"Respuesta: {response.json()}")
    assert response.status_code == 200

def test_extract_metadata():
    print("\n--- 2. Probando Endpoint de Extracción de Metadatos ---")
    test_url = "https://github.com"
    response = client.get(f"/api/v1/extract?url={test_url}")
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print("Resultado extraído:")
    print(f" - Título: {data['metadata']['title']}")
    print(f" - Descripción: {data['metadata']['description']}")
    print(f" - Favicon: {data['metadata']['favicon']}")
    print(f" - Redes encontradas: {data['social_links']}")
    print(f" - Tecnologías detectadas: {data['detected_technologies']}")
    print(f" - Tiempo de ejecución: {data['execution_time_ms']} ms")
    assert response.status_code == 200

if __name__ == "__main__":
    try:
        test_health()
        test_extract_metadata()
        print("\n[OK] TODAS LAS PRUEBAS PASADAS CON EXITO")
    except Exception as e:
        print(f"\n[ERROR] Error durante las pruebas: {e}")
        sys.exit(1)


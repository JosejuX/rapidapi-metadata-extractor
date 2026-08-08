# 🚀 Guía de Despliegue y Monetización en RapidAPI

Esta guía te explica paso a paso cómo desplegar tu servicio **Web Metadata & Contact Extractor API** a coste $0 y conectarlo a **RapidAPI** para empezar a generar ingresos pasivos.

---

## PASO 1: Ejecutar la API Localmente (Prueba)

Puedes probar la API en tu ordenador o móvil inmediatamente:

```bash
cd c:\Users\Juanj\Desktop\ZTE_Bot_Telegram\rapidapi_service
python -m pip install -r requirements.txt
python test_api.py
```

Para arrancar el servidor web interactivo:
```bash
python -m uvicorn main:app --reload --port 8000
```
Abre en tu navegador: `http://localhost:8000/docs` para ver la documentación interactiva Swagger automatizada.

---

## PASO 2: Alojamiento Gratuito 24/7 (Elegir una opción)

Para que RapidAPI pueda conectarse a tu API, necesitas una URL pública HTTPS que esté activa 24/7.

### Opción A: En tu móvil Android (Termux)
Si usas Termux en tu móvil:
1. Copia la carpeta `rapidapi_service` a Termux.
2. Instala dependencias: `pip install -r requirements.txt`.
3. Arranca el servidor: `uvicorn main:app --host 0.0.0.0 --port 8000`.
4. Usa un túnel gratuito como **Cloudflare Tunnel (`cloudflared`)** o **ngrok** para obtener una URL pública HTTPS:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   *(Cloudflare te dará una URL tipo `https://tu-subdominio.trycloudflare.com`)*.

### Opción B: En la nube 100% gratis (Render.com / Fly.io) - RECOMENDADO
No depende de tu batería ni de tu WiFi:
1. Crea una cuenta gratuita en **[Render.com](https://render.com)**.
2. Subes esta carpeta a un repositorio privado de GitHub.
3. En Render, crea un **Web Service**, conecta el repositorio y configura:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Render te dará una URL gratis tipo `https://mi-api-metadata.onrender.com`.

---

## PASO 3: Publicar y Monetizar en RapidAPI.com

1. **Crear cuenta de Desarrollador**:
   - Registrate en **[RapidAPI.com](https://rapidapi.com)**.
   - Ve a **My APIs** -> **Add New API**.

2. **Configurar los datos de tu API**:
   - **API Name**: `Web Metadata, Social & Contact Extractor`
   - **Category**: `Data / SEO`
   - **Base URL**: Pon la URL pública de tu servidor (ej: `https://mi-api-metadata.onrender.com`).

3. **Configurar la Seguridad (Crucial para que nadie se salte el pago)**:
   - En RapidAPI, activa el parámetro **Secret Header**. RapidAPI te dará un token tipo `sec_abc123...`.
   - En tu servidor, define la variable de entorno `RAPIDAPI_PROXY_SECRET=sec_abc123...`.
   - A partir de ese momento, tu API rechazará cualquier petición que no provenga de un cliente que haya pagado en RapidAPI.

4. **Configurar los Planes de Precios (Planes de Monetización)**:
   En la pestaña **Monetization** de RapidAPI, define tus tarifas:
   - **BASIC (Gratis)**: 100 peticiones / mes (para atraer desarrolladores).
   - **PRO ($9 / mes)**: 2.000 peticiones / mes.
   - **ULTRA ($29 / mes)**: 10.000 peticiones / mes.
   - **MEGA ($79 / mes)**: 50.000 peticiones / mes.

5. **¡Publicar!**:
   Haz clic en **Publish to Hub**.

---

## 💰 ¿Cómo recibes tus ingresos?

RapidAPI cobra a los usuarios mediante tarjeta de crédito y te transfiere las ganancias automáticamente a tu cuenta de **PayPal** o **Cuenta Bancaria (Stripe/Payouts)** al final de cada mes.

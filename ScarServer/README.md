# Scar Client - Sistema HWID & Discord Bot

Este sistema te permite gestionar licencias por HWID (Hardware ID) para **Scar Client** de manera totalmente automática mediante un Bot de Discord y una API en la nube gratuita (Railway).

---

## 📁 Estructura

- **`main.py`**: API REST construida con FastAPI y base de datos SQLite (`scar.db`).
- **`bot.py`**: Bot de Discord con Slash Commands (`/whitelist`, `/unwhitelist`, `/check`, `/delete_hwid`, `/list_users`).
- **`scar_auth.ini`**: Archivo de configuración que acompaña a `Scar.exe` para apuntar a tu servidor.
- **`Dockerfile` & `Dockerfile.bot`**: Archivos listos para desplegar en [Railway.app](https://railway.app/).

---

## 🚀 Despliegue Gratuito en Railway.app

1. **Crear cuenta**: Regístrate gratis en [Railway.app](https://railway.app/).
2. **Subir repositorio**: Sube la carpeta `ScarServer` a un repositorio de GitHub (puedes crearlo privado).
3. **Desplegar la API (`main.py`)**:
   - En Railway: **New Project** -> **Deploy from GitHub repo**.
   - Agrega las Variables de Entorno:
     - `ADMIN_SECRET`: Una clave secreta para comunicar el bot con el API (ej: `MiClaveUltraSecreta2026`).
     - `PORT`: `8000`
   - En **Settings** -> **Networking** -> **Generate Domain**: obtendrás una URL como `https://scar-api-production.up.railway.app`.
4. **Desplegar el Bot (`bot.py`)**:
   - En el mismo proyecto de Railway, agrega otro servicio desde el mismo repo.
   - En Configuración de Build/Deploy, usa el Dockerfile `Dockerfile.bot` o configura el comando de inicio: `python bot.py`.
   - Variables de Entorno del Bot:
     - `DISCORD_TOKEN`: El token de tu bot de Discord (creado en [Discord Developer Portal](https://discord.com/developers/applications)).
     - `API_URL`: La URL pública de tu API de Railway (ej: `https://scar-api-production.up.railway.app`).
     - `ADMIN_SECRET`: La misma clave secreta que pusiste en la API.
     - `ADMIN_ROLE_NAME`: Nombre del rol en tu servidor de Discord que podrá usar los comandos (por defecto: `Scar Admin`).

---

## 🤖 Comandos del Bot de Discord

Todos los comandos son Slash Commands (`/`):

| Comando | Descripción |
|---|---|
| `/whitelist <hwid> [discord_id] [username] [expires]` | Registra o reactiva el HWID de un usuario con fecha opcional. |
| `/unwhitelist <hwid>` | Revoca inmediatamente el acceso de un HWID. |
| `/check <hwid>` | Consulta si un HWID está permitido y la razón. |
| `/delete_hwid <hwid>` | Borra por completo el HWID de la base de datos. |
| `/list_users` | Muestra la lista de usuarios y su estado. |

---

## ⚙️ Configuración del Inyector (`scar_auth.ini`)

En la misma carpeta donde esté `Scar.exe`, pon el archivo `scar_auth.ini`:

```ini
[Auth]
; Tu dominio de Railway sin "https://"
host=scar-api-production.up.railway.app
port=443
https=1
bypass=0
```

> **Nota para desarrollo/pruebas:**
> Si quieres probar el cliente en tu PC sin tener el servidor encendido, pon `bypass=1` en `scar_auth.ini`.

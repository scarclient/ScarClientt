"""
Scar Client - Discord Bot
Commands:
  /whitelist <discord_id> [username] [expires]  - Add/whitelist a user
  /unwhitelist <discord_id>                     - Revoke access
  /check <discord_id>                           - Check a user's status
  /reset <hwid>                                 - Delete a HWID entry
  /list                                         - List all users

Environment variables required:
  DISCORD_TOKEN    - Your bot token
  API_URL          - Your Railway API URL (e.g. https://scar-api.up.railway.app)
  ADMIN_SECRET     - Same secret as in the API
  ADMIN_ROLE_NAME  - Discord role name allowed to use bot commands (default: "Scar Admin")
"""

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
from typing import Optional

# --- Config ---
TOKEN        = os.environ.get("DISCORD_TOKEN", "")
API_URL      = os.environ.get("API_URL", "https://scarclientt-production.up.railway.app").rstrip("/")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "changeme_scar_secret_2024")
ADMIN_ROLE   = os.environ.get("ADMIN_ROLE_NAME", "Scar Admin")

# --- Bot setup ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def admin_headers():
    return {"x-admin-secret": ADMIN_SECRET, "Content-Type": "application/json"}

def has_admin_role(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    # Permitir a cualquier administrador del servidor o a quien tenga el rol
    if interaction.user.guild_permissions.administrator:
        return True
    return any(r.name == ADMIN_ROLE for r in interaction.user.roles)

# ---------------------------------------------------------------------------
# /whitelist
# ---------------------------------------------------------------------------
@tree.command(name="whitelist", description="Add or re-whitelist a user by HWID")
@app_commands.describe(
    hwid="Hardware ID of the user (they can see it in the injector)",
    discord_id="Discord user ID (optional)",
    username="Username label (optional)",
    expires="Expiry date ISO format: 2025-12-31T23:59:59 (optional, leave blank = never)"
)
async def cmd_whitelist(
    interaction: discord.Interaction,
    hwid: str,
    discord_id: Optional[str] = None,
    username: Optional[str] = None,
    expires: Optional[str] = None
):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        # Try add first, if exists → patch to re-whitelist
        payload = {"hwid": hwid, "discord_id": discord_id, "username": username, "expires_at": expires}
        async with session.post(f"{API_URL}/admin/users", json=payload, headers=admin_headers()) as r:
            if r.status == 200:
                await interaction.followup.send(f"✅ **{username or hwid}** agregado y whitelisted.", ephemeral=True)
                return
            data = await r.json()
            if data.get("detail") == "HWID already exists":
                # Re-whitelist
                patch = {"whitelisted": True}
                if username: patch["username"] = username
                if expires: patch["expires_at"] = expires
                async with session.patch(f"{API_URL}/admin/users/{hwid}", json=patch, headers=admin_headers()) as r2:
                    if r2.status == 200:
                        await interaction.followup.send(f"✅ **{username or hwid}** re-whitelisted.", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ Error al actualizar.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error: {data}", ephemeral=True)

# ---------------------------------------------------------------------------
# /unwhitelist
# ---------------------------------------------------------------------------
@tree.command(name="unwhitelist", description="Revocar acceso a un usuario (por HWID)")
@app_commands.describe(hwid="Hardware ID del usuario")
async def cmd_unwhitelist(interaction: discord.Interaction, hwid: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.patch(
            f"{API_URL}/admin/users/{hwid}",
            json={"whitelisted": False},
            headers=admin_headers()
        ) as r:
            if r.status == 200:
                await interaction.followup.send(f"🚫 Acceso revocado para `{hwid}`.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ No encontrado o error.", ephemeral=True)

# ---------------------------------------------------------------------------
# /check
# ---------------------------------------------------------------------------
@tree.command(name="check", description="Verificar el estado de un HWID")
@app_commands.describe(hwid="Hardware ID a verificar")
async def cmd_check(interaction: discord.Interaction, hwid: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{API_URL}/check", json={"hwid": hwid}) as r:
            data = await r.json()
            status = "✅ PERMITIDO" if data.get("allowed") else "❌ BLOQUEADO"
            reason = data.get("reason", "")
            await interaction.followup.send(f"**{status}**\n`{hwid}`\n> {reason}", ephemeral=True)

# ---------------------------------------------------------------------------
# /delete_hwid
# ---------------------------------------------------------------------------
@tree.command(name="delete_hwid", description="Eliminar completamente un HWID de la base de datos")
@app_commands.describe(hwid="Hardware ID a eliminar")
async def cmd_delete(interaction: discord.Interaction, hwid: str):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{API_URL}/admin/users/{hwid}", headers=admin_headers()) as r:
            if r.status == 200:
                await interaction.followup.send(f"🗑️ HWID `{hwid}` eliminado.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ No encontrado.", ephemeral=True)

# ---------------------------------------------------------------------------
# /list
# ---------------------------------------------------------------------------
@tree.command(name="list_users", description="Listar todos los usuarios registrados")
async def cmd_list(interaction: discord.Interaction):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/admin/users", headers=admin_headers()) as r:
            users = await r.json()

    if not users:
        await interaction.followup.send("📋 No hay usuarios registrados.", ephemeral=True)
        return

    lines = ["```"]
    lines.append(f"{'ID':<4} {'Username':<18} {'Status':<10} {'Expires':<20} HWID")
    lines.append("-" * 75)
    for u in users[:20]:  # max 20 to avoid message limit
        status = "✅" if u["whitelisted"] else "❌"
        exp = u["expires_at"][:10] if u["expires_at"] else "Never"
        name = (u["username"] or "unknown")[:16]
        hwid_short = u["hwid"][:20] + "..."
        lines.append(f"{u['id']:<4} {name:<18} {status:<10} {exp:<20} {hwid_short}")
    lines.append("```")
    if len(users) > 20:
        lines.append(f"*...y {len(users)-20} más*")

    await interaction.followup.send("\n".join(lines), ephemeral=True)

# ---------------------------------------------------------------------------
# Bot ready
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Scar Bot online como {bot.user} | {len(tree.get_commands())} comandos sincronizados")

if __name__ == "__main__":
    bot.run(TOKEN)

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
from datetime import datetime, timedelta

# --- Config ---
TOKEN        = os.environ.get("DISCORD_TOKEN", "")
API_URL      = os.environ.get("API_URL", "https://scarclientt-production.up.railway.app").rstrip("/")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "changeme_scar_secret_2024")
ADMIN_ROLE   = os.environ.get("ADMIN_ROLE_NAME", "Scar Admin")

# --- Bot setup ---
intents = discord.Intents.default()
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

def parse_duration(dur: Optional[str]) -> Optional[str]:
    if not dur:
        return None
    dur = dur.strip().lower()
    if dur in ["perm", "permanente", "lifetime", "infinito", "none", "0"]:
        return None
    
    now = datetime.utcnow()
    try:
        if dur.endswith("d"):
            days = int(dur[:-1])
            return (now + timedelta(days=days)).isoformat()
        elif dur.endswith("h"):
            hours = int(dur[:-1])
            return (now + timedelta(hours=hours)).isoformat()
        elif dur.endswith("m"):
            months = int(dur[:-1])
            return (now + timedelta(days=months * 30)).isoformat()
        elif dur.isdigit():
            days = int(dur)
            return (now + timedelta(days=days)).isoformat()
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# /whitelist
# ---------------------------------------------------------------------------
@tree.command(name="whitelist", description="Dar acceso a un usuario por HWID")
@app_commands.describe(
    hwid="HWID del usuario (el inyector se lo copia automáticamente al portapapeles)",
    duracion="Ej: 5d (5 días), 30d (30 días), 12h, permanente (vacío = permanente)",
    usuario="Nombre o tag de la persona (ej: @Juan)"
)
async def cmd_whitelist(
    interaction: discord.Interaction,
    hwid: str,
    duracion: Optional[str] = None,
    usuario: Optional[str] = None
):
    if not has_admin_role(interaction):
        await interaction.response.send_message("❌ No tienes permisos.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    clean_hwid = hwid.strip()
    expires_iso = parse_duration(duracion)
    dur_label = duracion if duracion else "Permanente (Sin límite)"
    if expires_iso:
        dur_label += f" (Expira: {expires_iso[:10]})"

    async with aiohttp.ClientSession() as session:
        payload = {"hwid": clean_hwid, "username": usuario, "expires_at": expires_iso}
        async with session.post(f"{API_URL}/admin/users", json=payload, headers=admin_headers()) as r:
            if r.status == 200:
                embed = discord.Embed(title="🛡️ Licencia Scar Client Activada", color=0x9b59b6)
                embed.add_field(name="Usuario", value=usuario or "Sin nombre", inline=True)
                embed.add_field(name="Duración", value=dur_label, inline=True)
                embed.add_field(name="HWID", value=f"`{clean_hwid[:28]}...`", inline=False)
                embed.set_footer(text="Scar Client Authentication System")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            data = await r.json()
            if data.get("detail") == "HWID already exists":
                patch = {"whitelisted": True}
                if usuario: patch["username"] = usuario
                patch["expires_at"] = expires_iso
                async with session.patch(f"{API_URL}/admin/users/{clean_hwid}", json=patch, headers=admin_headers()) as r2:
                    if r2.status == 200:
                        embed = discord.Embed(title="🔄 Licencia Scar Client Renovada", color=0x2ecc71)
                        embed.add_field(name="Usuario", value=usuario or "Sin nombre", inline=True)
                        embed.add_field(name="Nueva Duración", value=dur_label, inline=True)
                        embed.add_field(name="HWID", value=f"`{clean_hwid[:28]}...`", inline=False)
                        embed.set_footer(text="Scar Client Authentication System")
                        await interaction.followup.send(embed=embed, ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ Error al renovar usuario.", ephemeral=True)
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
# Bot ready & Instant Guild Sync
# ---------------------------------------------------------------------------
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def cmd_manual_sync(ctx):
    tree.copy_global_to(guild=ctx.guild)
    synced = await tree.sync(guild=ctx.guild)
    await ctx.send(f"✅ {len(synced)} comandos sincronizados instantáneamente en este servidor!")

@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        except Exception as e:
            print(f"Error syncing guild {guild.id}: {e}")
    await tree.sync()
    print(f"✅ Scar Bot online como {bot.user} | {len(tree.get_commands())} comandos sincronizados")

if __name__ == "__main__":
    bot.run(TOKEN)

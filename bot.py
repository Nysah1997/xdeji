#!/usr/bin/env python3

# Auto-instalación de dependencias si no están disponibles
try:
    import discord
except ImportError:
    print("📦 discord.py no encontrado. Instalando automáticamente...")
    import subprocess
    import sys
    
    # Intentar instalar discord.py
    install_methods = [
        [sys.executable, "-m", "pip", "install", "discord.py"],
        [sys.executable, "-m", "pip", "install", "--user", "discord.py"],
        ["pip3", "install", "discord.py"],
        [sys.executable, "-m", "pip", "install", "--break-system-packages", "discord.py"],
    ]
    
    installed = False
    for method in install_methods:
        try:
            result = subprocess.run(method, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ discord.py instalado con: {' '.join(method)}")
                installed = True
                break
        except:
            continue
    
    if not installed:
        print("❌ No se pudo instalar discord.py automáticamente")
        print("🔧 Instala manualmente con: pip install discord.py")
        exit(1)
    
    # Intentar importar después de la instalación
    try:
        import discord
        print("✅ discord.py importado correctamente")
    except ImportError:
        print("❌ Error: discord.py instalado pero no se puede importar")
        print("🔧 Reinicia el bot o instala manualmente")
        exit(1)

from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import asyncio
import pytz

from time_tracker import TimeTracker

# Configuración del bot
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True  # Necesario para acceder a información de miembros y roles
intents.message_content = True  # Para evitar warnings

bot = commands.Bot(command_prefix='!', intents=intents)
time_tracker = TimeTracker()


# Rol especial para tiempo ilimitado (se carga desde config.json)
UNLIMITED_TIME_ROLE_ID = None

# Variables para IDs de canales de notificación
NOTIFICATION_CHANNEL_ID = 1387194559318196416
PAUSE_NOTIFICATION_CHANNEL_ID = 1387194620961751070
CANCELLATION_NOTIFICATION_CHANNEL_ID = 1387194756211146792
ATTENDANCE_NOTIFICATION_CHANNEL_ID = 1387194412966350878

# Cargar configuración completa desde config.json
config = {}
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Cargar IDs de roles
    role_ids = config.get('role_ids', {})
    UNLIMITED_TIME_ROLE_ID = role_ids.get('unlimited_time_role_id')
    if UNLIMITED_TIME_ROLE_ID:
        print(f"✅ Rol de tiempo ilimitado cargado desde config: ID {UNLIMITED_TIME_ROLE_ID}")

    # Cargar IDs de canales de notificación desde config
    notification_channels = config.get('notification_channels', {})
    NOTIFICATION_CHANNEL_ID = notification_channels.get('milestones', 1387194559318196416)
    PAUSE_NOTIFICATION_CHANNEL_ID = notification_channels.get('pauses', 1387194620961751070)
    CANCELLATION_NOTIFICATION_CHANNEL_ID = notification_channels.get('cancellations', 1387194756211146792)
    ATTENDANCE_NOTIFICATION_CHANNEL_ID = notification_channels.get('attendances', 1387194412966350878)

    print(f"✅ Configuración cargada desde config.json:")
    print(f"  - Milestones: {NOTIFICATION_CHANNEL_ID}")
    print(f"  - Pausas: {PAUSE_NOTIFICATION_CHANNEL_ID}")
    print(f"  - Cancelaciones: {CANCELLATION_NOTIFICATION_CHANNEL_ID}")
    print(f"  - Asistencias: {ATTENDANCE_NOTIFICATION_CHANNEL_ID}")

except Exception as e:
    print(f"⚠️ No se pudo cargar configuración: {e}")
    config = {}
    # Valores por defecto si no se puede cargar config
    NOTIFICATION_CHANNEL_ID = 1385005232685318281
    PAUSE_NOTIFICATION_CHANNEL_ID = 1385005232685318282
    CANCELLATION_NOTIFICATION_CHANNEL_ID = 1385005232685318284
    ATTENDANCE_NOTIFICATION_CHANNEL_ID = 1390478447901675660

# Task para verificar milestones periódicamente
milestone_check_task = None

# Sistema de pre-registro con horario Colombia
colombia_tz = pytz.timezone('America/Bogota')
daily_preregistration_task = None

# Configuración de hora de inicio automático (puedes cambiar estos valores)
AUTO_START_HOUR = 20      # Hora en formato 24h (17 = 5 PM)
AUTO_START_MINUTE = 16    # Minuto (0-59)

# AUTO-LIGADO: Los cargos altos auto-ligan tiempos al usar /iniciar_tiempo
# (ya no se basa en hora específica)


@bot.event
async def on_ready():
    print(f'{bot.user} se ha conectado a Discord!')

    # Verificar que el canal de notificaciones existe
    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel:
        if hasattr(channel, 'name'):
            print(f'Canal de notificaciones encontrado: {channel.name} (ID: {channel.id})')
        else:
            print(f'Canal de notificaciones encontrado (ID: {channel.id})')
    else:
        print(f'⚠️ Canal de notificaciones no encontrado con ID: {NOTIFICATION_CHANNEL_ID}')

    try:
        # Sincronización global primero
        print("🔄 Sincronizando comandos globalmente...")
        synced_global = await bot.tree.sync()
        print(f'✅ Sincronizados {len(synced_global)} comando(s) slash globalmente')

        # Sincronización específica del guild si hay guilds
        if bot.guilds:
            for guild in bot.guilds:
                try:
                    print(f"🔄 Sincronizando comandos en {guild.name} (ID: {guild.id})...")
                    synced_guild = await bot.tree.sync(guild=guild)
                    print(f'✅ Sincronizados {len(synced_guild)} comando(s) en {guild.name}')
                except Exception as guild_error:
                    print(f'⚠️ Error sincronizando en {guild.name}: {guild_error}')

        # Listar todos los comandos registrados
        commands = [cmd.name for cmd in bot.tree.get_commands()]
        print(f'📋 Comandos registrados ({len(commands)}): {", ".join(commands)}')

        # Verificar comandos importantes
        important_commands = ["iniciar_tiempo", "ver_tiempos", "mi_tiempo", "reiniciar_todos_tiempos", "limpiar_base_datos", "paga_recluta", "paga_medios", "paga_gold", "paga_cargos"]
        for cmd in important_commands:
            if cmd in commands:
                print(f"✅ Comando {cmd} registrado correctamente")
            else:
                print(f"❌ Comando {cmd} no encontrado")

        print("💡 Si los comandos no aparecen inmediatamente:")
        print("   • Espera 1-5 minutos para que Discord los propague")
        print("   • Reinicia tu cliente de Discord")
        print("   • Verifica que el bot tenga permisos de 'applications.commands'")

    except Exception as e:
        print(f'❌ Error al sincronizar comandos: {e}')
        print("🔧 Intentando sincronización de emergencia...")
        try:
            # Intentar sincronización de emergencia sin guild específico
            emergency_sync = await bot.tree.sync()
            print(f'🆘 Sincronización de emergencia: {len(emergency_sync)} comandos')
        except Exception as emergency_error:
            print(f'❌ Falló sincronización de emergencia: {emergency_error}')

    # Iniciar task de verificación de milestones se hará después de definir la función

# @bot.event
# async def on_voice_state_update(member, before, after):
#     """Función deshabilitada - el seguimiento de tiempo ahora es solo manual"""
#     pass

def is_admin():
    """Decorator para verificar si el usuario tiene permisos - AHORA PERMITE A TODOS LOS USUARIOS"""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            # PERMITIR A TODOS LOS USUARIOS - Solo verificar que esté en un servidor
            if not hasattr(interaction, 'guild') or not interaction.guild:
                print(f"❌ Usuario {interaction.user.display_name} sin guild")
                return False

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                print(f"❌ No se pudo obtener member para {interaction.user.display_name}")
                return False

            # PERMITIR A TODOS - Solo verificar que no sea un bot
            if member.bot:
                print(f"❌ {interaction.user.display_name} es un bot")
                return False

            print(f"✅ {interaction.user.display_name} puede usar comandos (acceso abierto)")
            return True

        except Exception as e:
            print(f"Error en verificación de permisos para {interaction.user.display_name}: {e}")
            return False

    return discord.app_commands.check(predicate)

def load_config():
    """Cargar configuración desde config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error cargando configuración: {e}")
        return {}

def has_command_permission_role(member: discord.Member) -> bool:
    """Verificar si el usuario tiene el rol autorizado para usar comandos"""
    try:
        config = load_config()
        role_ids = config.get('role_ids', {})
        command_role_id = role_ids.get('command_permission_role_id')

        if command_role_id is None:
            return False

        for role in member.roles:
            if role.id == command_role_id:
                return True
        return False
    except Exception as e:
        print(f"Error en has_command_permission_role: {e}")
        return False

def can_use_mi_tiempo(member: discord.Member) -> bool:
    """Verificar si el usuario tiene el rol autorizado para usar /mi_tiempo"""
    config = load_config()
    role_ids = config.get('role_ids', {})
    mi_tiempo_role_id = role_ids.get('mi_tiempo_role_id')

    if mi_tiempo_role_id is None:
        return False

    for role in member.roles:
        if role.id == mi_tiempo_role_id:
            return True

    return False

def has_unlimited_time_role(member: discord.Member) -> bool:
    """Verificar si el usuario tiene el rol de tiempo ilimitado"""
    if UNLIMITED_TIME_ROLE_ID is None:
        return False

    for role in member.roles:
        if role.id == UNLIMITED_TIME_ROLE_ID:
            return True
    return False

def has_attendance_role(member: discord.Member) -> bool:
    """Verificar si el usuario tiene un rol que puede obtener asistencias"""
    role_type = get_user_role_type(member)
    return role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]

def calculate_credits(total_seconds: float, role_type: str = "normal") -> int:
    """Calcular créditos basado en el tiempo total y el rol"""
    try:
        # Validar entrada
        if not isinstance(total_seconds, (int, float)) or total_seconds < 0:
            return 0

        total_hours = total_seconds / 3600

        # Los cargos altos y superiores NO reciben créditos por tiempo completado
        # Solo reciben créditos por asistencias
        if role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]:
            return 0  # No créditos por tiempo - solo por asistencias

        if role_type == "gold":
          if total_hours >= 2.0:
              return 12  # 2 horas = 12 créditos
          elif total_hours >= 1.0:
              return 6  # 1 hora = 6 créditos
          else:
              return 0  # Menos de 1 hora = 0 créditos
        elif role_type == "medios":
          if total_hours >= 2.0:
              return 10  # 2 horas = 10 créditos
          elif total_hours >= 1.0:
              return 5  # 1 hora = 5 créditos
          else:
              return 0  # Menos de 1 hora = 0 créditos
        else:
          # Lógica para usuarios sin rol específico (normal)
          if total_hours >= 2.0:
              return 8  # 2 horas = 8 créditos
          elif total_hours >= 1.0:
              return 4  # 1 hora = 4 créditos
          else:
              return 0  # Menos de 1 hora = 0 créditos

    except Exception as e:
        print(f"Error calculando créditos: {e}")
        return 0

def calculate_credits_from_time(member: discord.Member, time_minutes: int) -> int:
    """Calcular créditos basándose en el tiempo - sistema sin rol únicamente"""
    try:
        # Sin rol: Hasta 1 hora por 3 créditos
        max_time_minutes = 1 * 60  # 60 minutos
        credits_per_session = 3

        # Limitar el tiempo al máximo permitido
        effective_time = min(time_minutes, max_time_minutes)

        # Calcular créditos proporcionales
        if effective_time > 0:
            credits = int((effective_time / max_time_minutes) * credits_per_session)
            return max(1, credits)  # Mínimo 1 crédito

        return 0
    except Exception as e:
        print(f"Error calculando créditos: {e}")
        return 0

@bot.tree.command(name="iniciar_tiempo", description="Pre-registrar usuario para inicio automático a las 5 PM Colombia")
@discord.app_commands.describe(usuario="El usuario para pre-registrar o iniciar inmediatamente")
@is_admin()
async def iniciar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    if usuario.bot:
        await interaction.response.send_message("❌ No se puede rastrear el tiempo de bots.")
        return

    # Obtener hora actual en Colombia
    colombia_now = datetime.now(colombia_tz)
    current_hour = colombia_now.hour
    current_minute = colombia_now.minute

    # Verificar si el usuario tiene el rol de tiempo ilimitado
    has_unlimited_role = has_unlimited_time_role(usuario)

    # Verificar límites según el rol del usuario
    total_time = time_tracker.get_total_time(usuario.id)
    total_hours = total_time / 3600

    # Verificar el tipo de rol del usuario
    role_type = get_user_role_type(usuario)

    if role_type in ["gold", "medios"]:
        # Usuarios con rol Gold o Medios: límite de 2 horas
        if total_hours >= 2.0:
            formatted_time = time_tracker.format_time_human(total_time)
            await interaction.response.send_message(
                f"❌ {usuario.mention} ya ha alcanzado el límite máximo de 2 horas (Tiempo actual: {formatted_time}). "
                f"No se puede registrar más seguimiento."
            )
            return
    elif not has_unlimited_role:
        # Usuarios sin rol específico: límite de 2 horas
        if total_hours >= 2.0:
            formatted_time = time_tracker.format_time_human(total_time)
            await interaction.response.send_message(
                f"❌ {usuario.mention} ya ha alcanzado el límite máximo de 2 horas (Tiempo actual: {formatted_time}). "
                f"No se puede registrar más seguimiento."
            )
            return
    else:
        # Usuarios con rol especial: límite de 4 horas
        if total_hours >= 4.0:
            formatted_time = time_tracker.format_time_human(total_time)
            await interaction.response.send_message(
                f"❌ {usuario.mention} ya ha alcanzado el límite máximo de 4 horas (Tiempo actual: {formatted_time}). "
                f"No se puede registrar más seguimiento."
            )
            return

    # Verificar si el usuario tiene tiempo pausado
    user_data = time_tracker.get_user_data(usuario.id)
    if user_data and user_data.get('is_paused', False):
        await interaction.response.send_message(
            f"⚠️ {usuario.mention} tiene tiempo pausado. Usa `/despausar_tiempo` para continuar el tiempo."
        )
        return

    # Si es la hora configurada o después, iniciar inmediatamente
    if current_hour > AUTO_START_HOUR or (current_hour == AUTO_START_HOUR and current_minute >= AUTO_START_MINUTE):
        success = time_tracker.start_tracking(usuario.id, usuario.display_name)
        if success:
            # Registrar quién inició el tiempo para asistencias
            time_tracker.set_time_initiator(usuario.id, interaction.user.id, interaction.user.display_name)
            
            # AUTO-LIGADO: Si el ejecutor tiene cargo alto, auto-ligar automáticamente
            executor = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
            can_auto_link = executor and has_attendance_role(executor)
            
            auto_linked = False
            if can_auto_link:
                # Auto-ligar el tiempo
                link_success = time_tracker.link_time_to_user(usuario.id, interaction.user.id, interaction.user.display_name)
                if link_success:
                    auto_linked = True
                    # Enviar notificación de ligado automático
                    await send_auto_link_notification(interaction.user, usuario, colombia_now.strftime('%H:%M'))
            
            response_message = (f"⏰ **INICIO INMEDIATO** - Son las {colombia_now.strftime('%H:%M')} (Colombia)\n"
                              f"El tiempo de {usuario.mention} ha sido iniciado por {interaction.user.mention}")
            
            if auto_linked:
                response_message += f"\n🔗 **TIEMPO AUTO-LIGADO** - Cargo alto detectado"
            elif not can_auto_link:
                role_info = get_role_info(executor) if executor else ""
                response_message += f"\n💡 **Nota:**{role_info} no puede auto-ligar tiempos (requiere cargo alto)"
            
            await interaction.response.send_message(response_message)
        else:
            await interaction.response.send_message(f"⚠️ El tiempo de {usuario.mention} ya está activo")
    else:
        # Antes de la hora configurada: PRE-REGISTRAR
        success = time_tracker.preregister_user(usuario.id, usuario.display_name, interaction.user.id, interaction.user.display_name)
        if success:
            next_start_time = colombia_now.replace(hour=AUTO_START_HOUR, minute=AUTO_START_MINUTE, second=0, microsecond=0)
            time_until_start = next_start_time - colombia_now
            
            hours_left = int(time_until_start.total_seconds() // 3600)
            minutes_left = int((time_until_start.total_seconds() % 3600) // 60)
            
            time_left_str = ""
            if hours_left > 0:
                time_left_str = f"{hours_left} hora{'s' if hours_left != 1 else ''}"
            if minutes_left > 0:
                if time_left_str:
                    time_left_str += f" y {minutes_left} minuto{'s' if minutes_left != 1 else ''}"
                else:
                    time_left_str = f"{minutes_left} minuto{'s' if minutes_left != 1 else ''}"
            
            start_time_formatted = f"{AUTO_START_HOUR:02d}:{AUTO_START_MINUTE:02d}"
            await interaction.response.send_message(
                f"📝 El tiempo de {usuario.mention} ha sido registrado por {interaction.user.mention}\n"              
            )
        else:
            await interaction.response.send_message(f"⚠️ {usuario.mention} ya está pre-registrado o tiene tiempo activo")

@bot.tree.command(name="pausar_tiempo", description="Pausar el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario para quien pausar el tiempo")
@is_admin()
async def pausar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    # Obtener datos antes de pausar para mostrar tiempo de sesión actual
    user_data = time_tracker.get_user_data(usuario.id)
    total_time_before = time_tracker.get_total_time(usuario.id)

    success = time_tracker.pause_tracking(usuario.id)
    if success:
        # Obtener tiempo total después de pausar (incluye la sesión que se acaba de pausar)
        total_time_after = time_tracker.get_total_time(usuario.id)
        session_time = total_time_after - total_time_before

        # Obtener número de pausas
        pause_count = time_tracker.get_pause_count(usuario.id)

        formatted_total_time = time_tracker.format_time_human(total_time_after)
        formatted_session_time = time_tracker.format_time_human(session_time) if session_time > 0 else "0 Segundos"

        # Verificar si alcanzó 3 pausas para cancelación automática
        if pause_count >= 3:
            # Cancelar automáticamente el tiempo del usuario
            time_tracker.cancel_user_tracking(usuario.id)

            # Respuesta del comando simple para el admin
            await interaction.response.send_message(
                f"⏸️ El tiempo de {usuario.mention} ha sido pausado\n"
                f"🚫 **{usuario.mention} lleva {pause_count} pausas - Tiempo cancelado automáticamente por exceder el límite**"
            )

            # Enviar notificación de cancelación automática
            await send_auto_cancellation_notification(usuario.display_name, formatted_total_time, interaction.user.mention, pause_count)
        else:
            # Respuesta del comando simple para el admin
            await interaction.response.send_message(
                f"⏸️ El tiempo de {usuario.mention} ha sido pausado"
            )

            # Enviar notificación de pausa al canal específico con conteo de pausas
            await send_pause_notification(usuario.display_name, total_time_after, interaction.user.mention, formatted_session_time, pause_count)

    else:
        await interaction.response.send_message(f"⚠️ No hay tiempo activo para {usuario.mention}")

@bot.tree.command(name="despausar_tiempo", description="Despausar el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario para quien despausar el tiempo")
@is_admin()
async def despausar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    # Obtener duración pausada antes de despausar
    paused_duration = time_tracker.get_paused_duration(usuario.id)

    success = time_tracker.resume_tracking(usuario.id)
    if success:
        # Obtener tiempo total después de despausar
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_paused_duration = time_tracker.format_time_human(paused_duration) if paused_duration > 0 else "0 Segundos"

        # Respuesta del comando (efímera para el admin)
        await interaction.response.send_message(
            f"▶️ El tiempo de {usuario.mention} ha sido despausado\n"
            f"**Tiempo pausado:** {formatted_paused_duration}\n"
            f"**Despausado por:** {interaction.user.mention}",

        )

        # Enviar notificación de despausa al canal específico
        await send_unpause_notification(usuario.display_name, total_time, interaction.user.mention, formatted_paused_duration)
    else:
        await interaction.response.send_message(f"⚠️ No se puede despausar - {usuario.mention} no tiene tiempo pausado")

@bot.tree.command(name="sumar_minutos", description="Sumar minutos al tiempo de un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que sumar tiempo",
    minutos="Cantidad de minutos a sumar"
)
@is_admin()
async def sumar_minutos(interaction: discord.Interaction, usuario: discord.Member, minutos: int):
    if minutos <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva")
        return

    success = time_tracker.add_minutes(usuario.id, usuario.display_name, minutos)
    if success:
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_time = time_tracker.format_time_human(total_time)
        await interaction.response.send_message(
            f"✅ Sumados {minutos} minutos a {usuario.mention} por {interaction.user.mention}\n"
            f"⏱️ Tiempo total: {formatted_time}"
        )
        # Verificar milestone después de sumar tiempo
        await check_time_milestone(usuario.id, usuario.display_name)
    else:
        await interaction.response.send_message(f"❌ Error al sumar tiempo para {usuario.mention}")

@bot.tree.command(name="restar_minutos", description="Restar minutos del tiempo de un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que restar tiempo",
    minutos="Cantidad de minutos a restar"
)
@is_admin()
async def restar_minutos(interaction: discord.Interaction, usuario: discord.Member, minutos: int):
    if minutos <= 0:
        await interaction.response.send_message("❌ La cantidad de minutos debe ser positiva")
        return

    success = time_tracker.subtract_minutes(usuario.id, minutos)
    if success:
        total_time = time_tracker.get_total_time(usuario.id)
        formatted_time = time_tracker.format_time_human(total_time)
        await interaction.response.send_message(
            f"➖ Restados {minutos} minutos de {usuario.mention} por {interaction.user.mention}\n"
            f"⏱️ Tiempo total: {formatted_time}"
        )
    else:
        await interaction.response.send_message(f"❌ Error al restar tiempo para {usuario.mention}")

# Clase para manejar la paginación
class TimesView(discord.ui.View):
    def __init__(self, sorted_users, guild, max_per_page=25):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.sorted_users = sorted_users
        self.guild = guild
        self.max_per_page = max_per_page
        self.current_page = 0
        self.total_pages = (len(sorted_users) + max_per_page - 1) // max_per_page

        # Deshabilitar botones si solo hay una página
        if self.total_pages <= 1:
            self.clear_items()

    def get_embed(self):
        """Crear embed para la página actual"""
        start_idx = self.current_page * self.max_per_page
        end_idx = min(start_idx + self.max_per_page, len(self.sorted_users))

        current_users = self.sorted_users[start_idx:end_idx]
        user_list = []

        for _, user_id, data in current_users:
            try:
                user_id_int = int(user_id)
                member = self.guild.get_member(user_id_int) if self.guild else None

                if member:
                        user_mention = member.mention
                        role_type = get_user_role_type(member)
                else:
                        user_name = data.get('name', f'Usuario {user_id}')
                        user_mention = f"**{user_name}** `(ID: {user_id})`"
                        # Usuario no está en el servidor, asumir rol normal
                        role_type = "normal"

                # Obtener tiempo total
                total_time = time_tracker.get_total_time(user_id_int)
                formatted_time = time_tracker.format_time_human(total_time)

                # Determinar estado
                status = "🔴 Inactivo"
                if data.get('is_active', False):
                    status = "🟢 Activo"
                elif data.get('is_paused', False):
                    total_hours = total_time / 3600
                    has_special_role = has_unlimited_time_role(member) if member else False
                    if data.get("milestone_completed", False) or (has_special_role and total_hours >= 4.0) or (not has_special_role and total_hours >= 2.0):
                        status = "✅ Terminado"
                    else:
                        status = "⏸️ Pausado"

                # Calcular créditos
                credits = calculate_credits(total_time, role_type)
                credit_info = f" 💰 {credits} Créditos" if credits > 0 else ""
                role_info = get_role_info(member) if member else ""
                user_list.append(f"📌 {user_mention}{role_info} - ⏱️ {formatted_time}{credit_info} {status}")

            except Exception as e:
                print(f"Error procesando usuario {user_id}: {e}")
                continue

        embed = discord.Embed(
            title="⏰ Tiempos Registrados",
            description="\n".join(user_list) if user_list else "No hay usuarios en esta página",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} • Total: {len(self.sorted_users)} usuarios")
        return embed

    @discord.ui.button(label='◀️ Anterior', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1

        # Actualizar estado de botones
        self.update_buttons()

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='▶️ Siguiente', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1

        # Actualizar estado de botones
        self.update_buttons()

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='📄 Ir a página', style=discord.ButtonStyle.primary)
    async def go_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PageModal(self)
        await interaction.response.send_modal(modal)

    def update_buttons(self):
        """Actualizar estado de los botones según la página actual"""
        # Botón anterior
        self.children[0].disabled = (self.current_page == 0)
        # Botón siguiente  
        self.children[1].disabled = (self.current_page >= self.total_pages - 1)

    async def on_timeout(self):
        """Deshabilitar botones cuando expire el timeout"""
        for item in self.children:
            item.disabled = True

# Modal para ir a una página específica
class PageModal(discord.ui.Modal, title='Ir a Página'):
    def __init__(self, view):
        super().__init__()
        self.view = view

    page_number = discord.ui.TextInput(
        label='Número de página',
        placeholder=f'Ingresa un número entre 1 y {999}',
        required=True,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value)
            if 1 <= page <= self.view.total_pages:
                self.view.current_page = page - 1
                self.view.update_buttons()
                embed = self.view.get_embed()
                await interaction.response.edit_message(embed=embed, view=self.view)
            else:
                await interaction.response.send_message(
                    f"❌ Página inválida. Debe estar entre 1 y {self.view.total_pages}", 
                    ephemeral=True
                )
        except ValueError:
            await interaction.response.send_message("❌ Por favor ingresa un número válido", ephemeral=True)

@bot.tree.command(name="ver_tiempos", description="Ver todos los tiempos registrados y pre-registros")
@is_admin()
async def ver_tiempos(interaction: discord.Interaction):
    # Responder inmediatamente para evitar timeout
    try:
        await interaction.response.defer(ephemeral=False)
    except Exception as e:
        print(f"Error al defer la interacción: {e}")
        try:
            await interaction.response.send_message("🔄 Procesando tiempos...", ephemeral=False)
        except Exception:
            return

    try:
        # Obtener usuarios con timeout
        tracked_users = await asyncio.wait_for(
            asyncio.to_thread(time_tracker.get_all_tracked_users),
            timeout=5.0
        )

        # Obtener pre-registros
        preregistered_users = time_tracker.get_preregistered_users()

        # Si no hay ningún dato
        if not tracked_users and not preregistered_users:
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("📊 No hay usuarios con tiempo registrado ni pre-registros", ephemeral=False)
                else:
                    await interaction.followup.send("📊 No hay usuarios con tiempo registrado ni pre-registros")
            except Exception as e:
                print(f"Error enviando mensaje de sin usuarios: {e}")
            return

        # Crear embed principal
        embed = discord.Embed(
            title="⏰ Tiempos y Pre-Registros",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Procesar usuarios con tiempo registrado
        if tracked_users:
            # Ordenar usuarios alfabéticamente por nombre
            sorted_users = []
            for user_id, data in tracked_users.items():
                user_name = data.get('name', f'Usuario {user_id}')
                sorted_users.append((user_name.lower(), user_id, data))

            sorted_users.sort(key=lambda x: x[0])

            user_list = []
            for _, user_id, data in sorted_users[:15]:  # Limitar a 15 para dejar espacio a pre-registros
                try:
                    user_id_int = int(user_id)
                    member = interaction.guild.get_member(user_id_int) if interaction.guild else None

                    if member:
                        user_mention = member.mention
                        role_type = get_user_role_type(member)
                    else:
                        user_name = data.get('name', f'Usuario {user_id}')
                        user_mention = f"**{user_name}** `(ID: {user_id})`"
                        role_type = "normal"

                    total_time = time_tracker.get_total_time(user_id_int)
                    formatted_time = time_tracker.format_time_human(total_time)

                    status = "🔴 Inactivo"
                    if data.get('is_active', False):
                        status = "🟢 Activo"
                    elif data.get('is_paused', False):
                        total_hours = total_time / 3600
                        has_special_role = has_unlimited_time_role(member) if member else False
                        if (data.get("milestone_completed", False) or 
                            (has_special_role and total_hours >= 4.0) or 
                            (not has_special_role and total_hours >= 2.0)):
                            status = "✅ Terminado"
                        else:
                            status = "⏸️ Pausado"

                    credits = calculate_credits(total_time, role_type)
                    credit_info = f" 💰 {credits} Créditos" if credits > 0 else ""
                    role_info = get_role_info(member) if member else ""

                    user_list.append(f"📌 {user_mention}{role_info} - ⏱️ {formatted_time}{credit_info} {status}")

                except Exception as e:
                    print(f"Error procesando usuario {user_id}: {e}")
                    continue

            if user_list:
                embed.add_field(
                    name=f"⏱️ Usuarios con Tiempo ({len(tracked_users)} total)",
                    value="\n".join(user_list),
                    inline=False
                )
                
                if len(tracked_users) > 15:
                    embed.add_field(
                        name="ℹ️ Nota",
                        value=f"Mostrando primeros 15 de {len(tracked_users)} usuarios",
                        inline=False
                    )

        # Procesar pre-registros
        if preregistered_users:
            colombia_now = datetime.now(colombia_tz)
            prereg_list = []
            
            for user_id_str, prereg_data in list(preregistered_users.items())[:10]:  # Limitar a 10
                try:
                    user_id = int(user_id_str)
                    user_name = prereg_data.get('name', f'Usuario {user_id}')
                    admin_name = prereg_data.get('registered_by_name', 'Admin')
                    registered_time = prereg_data.get('registered_at', '')
                    
                    # Intentar obtener el miembro del servidor
                    member = interaction.guild.get_member(user_id) if interaction.guild else None
                    if member:
                        user_reference = member.mention
                    else:
                        user_reference = f"**{user_name}**"
                    
                    # Formatear hora de registro
                    if registered_time:
                        try:
                            reg_dt = datetime.fromisoformat(registered_time.replace('Z', '+00:00'))
                            colombia_reg_time = reg_dt.astimezone(colombia_tz)
                            time_str = colombia_reg_time.strftime('%H:%M')
                        except:
                            time_str = "?"
                    else:
                        time_str = "?"
                    
                    prereg_list.append(f"📝 {user_reference} - Pre-reg. {time_str} por **{admin_name}**")
                    
                except Exception as e:
                    print(f"Error procesando pre-registro {user_id_str}: {e}")
                    continue
            
            if prereg_list:
                embed.add_field(
                    name=f"📝 Pre-Registrados ({len(preregistered_users)} total)",
                    value="\n".join(prereg_list),
                    inline=False
                )
                
                # Calcular tiempo hasta la hora configurada
                if colombia_now.hour < AUTO_START_HOUR or (colombia_now.hour == AUTO_START_HOUR and colombia_now.minute < AUTO_START_MINUTE):
                    next_start_time = colombia_now.replace(hour=AUTO_START_HOUR, minute=AUTO_START_MINUTE, second=0, microsecond=0)
                    time_until_start = next_start_time - colombia_now
                    
                    hours_left = int(time_until_start.total_seconds() // 3600)
                    minutes_left = int((time_until_start.total_seconds() % 3600) // 60)
                    
                    time_left_str = f"{hours_left:02d}:{minutes_left:02d}"
                    
                    start_time_formatted = f"{AUTO_START_HOUR:02d}:{AUTO_START_MINUTE:02d}"
                    embed.add_field(
                        name="⏰ Inicio Automático",
                        value=f"Pre-registros iniciarán a las **{start_time_formatted}** (Colombia)\n⏳ Tiempo restante: **{time_left_str}**",
                        inline=False
                    )

        # Información adicional
        total_count = len(tracked_users) + len(preregistered_users)
        embed.set_footer(text=f"Total: {total_count} usuarios • Hora Colombia: {datetime.now(colombia_tz).strftime('%H:%M')}")

        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.followup.send(embed=embed)

    except asyncio.TimeoutError:
        error_msg = "❌ Timeout al obtener usuarios. Intenta de nuevo."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=False)
            else:
                await interaction.followup.send(error_msg)
        except Exception as e:
            print(f"Error enviando mensaje de timeout: {e}")

    except Exception as e:
        print(f"Error general en ver_tiempos: {e}")
        import traceback
        traceback.print_exc()

        error_msg = "❌ Error interno del comando. Revisa los logs del servidor."
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=False)
            else:
                await interaction.followup.send(error_msg)
        except Exception as e2:
            print(f"No se pudo enviar mensaje de error final: {e2}")

@bot.tree.command(name="reiniciar_tiempo", description="Reiniciar el tiempo de un usuario a cero")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo se reiniciará")
@is_admin()
async def reiniciar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    success = time_tracker.reset_user_time(usuario.id)
    if success:
        await interaction.response.send_message(f"🔄 Tiempo reiniciado para {usuario.mention} por {interaction.user.mention}")
    else:
        await interaction.response.send_message(f"❌ No se encontró registro de tiempo para {usuario.mention}")

@bot.tree.command(name="reiniciar_todos_tiempos", description="Reiniciar todos los tiempos de todos los usuarios")
@is_admin()
async def reiniciar_todos_tiempos(interaction: discord.Interaction):
    usuarios_reiniciados = time_tracker.reset_all_user_times()
    if usuarios_reiniciados > 0:
        await interaction.response.send_message(f"🔄 Tiempos reiniciados para {usuarios_reiniciados} usuario(s)")
    else:
        await interaction.response.send_message("❌ No hay usuarios con tiempo registrado para reiniciar")

@bot.tree.command(name="limpiar_base_datos", description="ELIMINAR COMPLETAMENTE todos los usuarios registrados de la base de datos")
@is_admin()
async def limpiar_base_datos(interaction: discord.Interaction):
    # Obtener conteo actual de usuarios antes de limpiar
    tracked_users = time_tracker.get_all_tracked_users()
    user_count = len(tracked_users)

    if user_count == 0:
        await interaction.response.send_message("❌ No hay usuarios registrados en la base de datos")
        return

    # Crear embed de confirmación con información detallada
    embed = discord.Embed(
        title="⚠️ CONFIRMACIÓN REQUERIDA",
        description="Esta acción eliminará COMPLETAMENTE todos los datos de usuarios",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="📊 Datos que se eliminarán:",
        value=f"• {user_count} usuarios registrados\n"
              f"• Todo el historial de tiempo\n"
              f"• Sesiones activas\n"
              f"• Contadores de pausas\n"
              f"• Estados de notificaciones\n"
              f"• **TODOS los comandos de pago quedarán vacíos**",
        inline=False
    )
    embed.add_field(
        name="⚠️ ADVERTENCIA:",
        value="Esta acción NO se puede deshacer\n"
              "Los usuarios tendrán que registrarse de nuevo\n"
              "Afecta: `/paga_recluta`, `/paga_medios`, `/paga_gold`, `/paga_cargos`",
        inline=False
    )
    embed.add_field(
        name="💡 Diferencia con resetear asistencias:",
        value="• Este comando: Borra usuarios completos\n"
              "• `/resetear_asistencias`: Solo borra asistencias",
        inline=False
    )
    embed.add_field(
        name="🔄 Para continuar:",
        value="Usa el comando nuevamente con `confirmar: True`",
        inline=False
    )
    embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="limpiar_base_datos_confirmar", description="CONFIRMAR eliminación completa de la base de datos")
@discord.app_commands.describe(confirmar="Escribe 'SI' para confirmar la eliminación completa")
@is_admin()
async def limpiar_base_datos_confirmar(interaction: discord.Interaction, confirmar: str):
    if confirmar.upper() != "SI":
        await interaction.response.send_message("❌ Operación cancelada. Debes escribir 'SI' para confirmar")
        return

    # Obtener información antes de limpiar
    tracked_users = time_tracker.get_all_tracked_users()
    user_count = len(tracked_users)

    if user_count == 0:
        await interaction.response.send_message("❌ No hay usuarios registrados en la base de datos")
        return

    # Realizar la limpieza completa
    success = time_tracker.clear_all_data()

    if success:
        embed = discord.Embed(
            title="🗑️ BASE DE DATOS LIMPIADA",
            description="Todos los datos de usuarios han sido eliminados completamente",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📊 Datos eliminados:",
            value=f"• {user_count} usuarios registrados\n"
                  f"• Todo el historial de tiempo\n"
                  f"• Sesiones activas\n"
                  f"• Archivo user_times.json reiniciado",
            inline=False
        )
        embed.add_field(
            name="✅ Estado actual:",
            value="Base de datos completamente limpia\n"
                  "Sistema listo para nuevos registros",
            inline=False
        )
        embed.set_footer(text=f"Ejecutado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Error al limpiar la base de datos")

@bot.tree.command(name="cancelar_tiempo", description="Cancelar completamente el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo se cancelará por completo")
@is_admin()
async def cancelar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    # Obtener datos del usuario ANTES de usarlos
    user_data = time_tracker.get_user_data(usuario.id)
    total_time = time_tracker.get_total_time(usuario.id)
    user_id = usuario.id

    if user_data:
        formatted_time = time_tracker.format_time_human(total_time)
        success = time_tracker.cancel_user_tracking(user_id)
        if success:
            # NO limpiar información del iniciador aquí - se limpia automáticamente al cancelar
            await interaction.response.send_message(
                f"🗑️ El tiempo de {usuario.mention} ha sido cancelado"
            )
            # Enviar notificación al canal de cancelaciones con tiempo cancelado
            await send_cancellation_notification(usuario.display_name, interaction.user.mention, formatted_time)
        else:
            await interaction.response.send_message(f"❌ Error al cancelar el tiempo para {usuario.mention}")
    else:
        await interaction.response.send_message(f"❌ No se encontró registro de tiempo para {usuario.mention}")



async def send_auto_cancellation_notification(user_name: str, total_time: str, cancelled_by: str, pause_count: int):
    """Enviar notificación cuando un usuario es cancelado automáticamente por 3 pausas"""
    channel = bot.get_channel(CANCELLATION_NOTIFICATION_CHANNEL_ID)
    if channel:
        try:
            message = f"🚫 **CANCELACIÓN AUTOMÁTICA**\n**{user_name}** ha sido cancelado automáticamente por exceder el límite de pausas\n**Tiempo total perdido:** {total_time}\n**Pausas alcanzadas:** {pause_count}/3\n**Última pausa ejecutada por:** {cancelled_by}"
            await channel.send(message)
            print(f"✅ Notificación de cancelación automática enviada para {user_name}")
        except Exception as e:
            print(f"❌ Error enviando notificación de cancelación automática: {e}")
    else:
        print(f"❌ No se pudo encontrar el canal de cancelaciones con ID: {CANCELLATION_NOTIFICATION_CHANNEL_ID}")

async def send_cancellation_notification(user_name: str, cancelled_by: str, cancelled_time: str = ""):
    """Enviar notificación cuando un usuario es cancelado"""
    channel = bot.get_channel(CANCELLATION_NOTIFICATION_CHANNEL_ID)
    if channel:
        try:
            if cancelled_time:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado\n**Tiempo cancelado:** {cancelled_time}\n**Cancelado por:** {cancelled_by}"
            else:
                message = f"🗑️ El seguimiento de tiempo de **{user_name}** ha sido cancelado por {cancelled_by}"
            await channel.send(message)
            print(f"✅ Notificación de cancelación enviada para {user_name}")
        except Exception as e:
            print(f"❌ Error enviando notificación de cancelación: {e}")
    else:
        print(f"❌ No se pudo encontrar el canal de cancelaciones con ID: {CANCELLATION_NOTIFICATION_CHANNEL_ID}")

async def send_pause_notification(user_name: str, total_time: float, paused_by: str, session_time: str = "", pause_count: int = 0):
    """Enviar notificación cuando un usuario es pausado"""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            channel = bot.get_channel(PAUSE_NOTIFICATION_CHANNEL_ID)
            if not channel:
                print(f"❌ Canal de pausas no encontrado: {PAUSE_NOTIFICATION_CHANNEL_ID}")
                return

            formatted_total_time = time_tracker.format_time_human(total_time)
            pause_text = f"pausa" if pause_count == 1 else f"pausas"

            if session_time and session_time != "0 Segundos":
                message = f"⏸️ El tiempo de **{user_name}** ha sido pausado\n**Tiempo de sesión pausado:** {session_time}\n**Tiempo total acumulado:** {formatted_total_time}\n**Pausado por:** {paused_by}\n📊 **{user_name}** lleva {pause_count} {pause_text}"
            else:
                message = f"⏸️ El tiempo de **{user_name}** ha sido pausado por {paused_by}\n**Tiempo total acumulado:** {formatted_total_time}\n📊 **{user_name}** lleva {pause_count} {pause_text}"

            await asyncio.wait_for(channel.send(message), timeout=10.0)
            print(f"✅ Notificación de pausa enviada para {user_name}")
            return

        except asyncio.TimeoutError:
            print(f"⚠️ Timeout enviando notificación de pausa para {user_name} (intento {attempt + 1}/{max_retries})")
        except discord.HTTPException as e:
            print(f"⚠️ Error HTTP enviando notificación de pausa para {user_name}: {e}")
            if "50013" in str(e):  # No permissions
                return
        except Exception as e:
            print(f"⚠️ Error enviando notificación de pausa para {user_name} (intento {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Backoff exponencial

async def send_unpause_notification(user_name: str, total_time: float, unpaused_by: str, paused_duration: str = ""):
    """Enviar notificación cuando un usuario es despausado"""
    max_retries = 3

    channel_id = config.get("notification_channels", {}).get("unpause")
    if not channel_id:
        print("❌ Canal de despausas no configurado")
        return

    for attempt in range(max_retries):
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                print(f"❌ Canal de despausas no encontrado: {channel_id}")
                return

            formatted_total_time = time_tracker.format_time_human(total_time)

            if paused_duration:
                message = f"▶️ El tiempo de **{user_name}** ha sido despausado\n**Tiempo total acumulado:** {formatted_total_time}\n**Tiempo pausado:** {paused_duration}\n**Despausado por:** {unpaused_by}"
            else:
                message = f"▶️ **{user_name}** ha sido despausado por {unpaused_by}. Tiempo acumulado: {formatted_total_time}"

            await asyncio.wait_for(channel.send(message), timeout=10.0)
            print(f"✅ Notificación de despausa enviada para {user_name}")
            return

        except asyncio.TimeoutError:
            print(f"⚠️ Timeout enviando notificación de despausa para {user_name} (intento {attempt + 1}/{max_retries})")
        except discord.HTTPException as e:
            print(f"⚠️ Error HTTP enviando notificación de despausa para {user_name}: {e}")
            if "50013" in str(e):  # No permissions
                return
        except Exception as e:
            print(f"⚠️ Error enviando notificación de despausa para {user_name} (intento {attempt + 1}): {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Backoff exponencial

async def check_time_milestone(user_id: int, user_name: str):
    """Verificar si el usuario ha alcanzado milestones de tiempo y enviar notificaciones"""
    try:
        user_data = time_tracker.get_user_data(user_id)
        if not user_data:
            return

        # Verificar si el usuario está en el servidor con timeout
        guild = None
        member = None
        try:
            guild = bot.guilds[0] if bot.guilds else None
            if guild:
                member = guild.get_member(user_id)
        except Exception as e:
            print(f"⚠️ Error obteniendo miembro del servidor para {user_name}: {e}")

        # Para usuarios externos (comandos de prefijo), asumir sin rol especial
        has_unlimited_role = False
        is_external_user = user_data.get('is_external_user', False)

        if member:
            try:
                has_unlimited_role = has_unlimited_time_role(member)
            except Exception as e:
                print(f"⚠️ Error verificando rol especial para {user_name}: {e}")
                has_unlimited_role = False
        else:
            # Usuario externo (comando prefijo) - sin rol especial
            has_unlimited_role = False

        # Solo verificar si el usuario está activo o pausado (pero no completamente detenido)
        if not user_data.get('is_active', False):
            return

        # Calcular tiempo de la sesión actual
        if not user_data.get('last_start'):
            return

        try:
            session_start = datetime.fromisoformat(user_data['last_start'])
        except (ValueError, TypeError) as e:
            print(f"⚠️ Error parseando fecha de inicio para {user_name}: {e}")
            return

        # Si está pausado, calcular tiempo hasta la pausa
        if user_data.get('is_paused', False) and user_data.get('pause_start'):
            try:
                pause_start = datetime.fromisoformat(user_data['pause_start'])
                session_time = (pause_start - session_start).total_seconds()
            except (ValueError, TypeError) as e:
                print(f"⚠️ Error parseando fecha de pausa para {user_name}: {e}")
                return
        else:
            # Si está activo, calcular tiempo hasta ahora
            current_time = datetime.now()
            session_time = (current_time - session_start).total_seconds()

        # Solo proceder si la sesión actual ha alcanzado 1 hora
        if session_time < 3600:
            return

        total_time = time_tracker.get_total_time(user_id)

        # Asegurar que existe el campo notified_milestones
        if 'notified_milestones' not in user_data:
            user_data['notified_milestones'] = []
            try:
                time_tracker.save_data()
            except Exception as e:
                print(f"⚠️ Error guardando datos para {user_name}: {e}")

        notified_milestones = user_data.get('notified_milestones', [])

        # Calcular cuántas horas totales tiene el usuario
        total_hours = int(total_time // 3600)
        hour_milestone = total_hours * 3600

        # Verificar si hay milestones perdidos (usuario tiene tiempo acumulado pero sin notificaciones)
        missing_milestones = []
        for h in range(1, total_hours + 1):
            milestone = h * 3600
            if milestone not in notified_milestones:
                missing_milestones.append((milestone, h))

        # Si hay milestones perdidos, notificar el más reciente
        if missing_milestones:
            milestone_to_notify, hours_to_notify = missing_milestones[-1]

            # AGREGAR ASISTENCIA ANTES DE DETENER EL TRACKING
            if member:
                await add_attendance_for_milestone(member, hours_to_notify)

            # Marcar TODOS los milestones perdidos como notificados
            for milestone, _ in missing_milestones:
                if milestone not in notified_milestones:
                    notified_milestones.append(milestone)
            user_data['notified_milestones'] = notified_milestones

            try:
                time_tracker.save_data()
            except Exception as e:
                print(f"⚠️ Error guardando milestones para {user_name}: {e}")

            # Detener el seguimiento después de completar 1 hora de sesión
            try:
                time_tracker.stop_tracking(user_id)
            except Exception as e:
                print(f"⚠️ Error deteniendo tracking para {user_name}: {e}")

            # Enviar notificación con retry y timeout
            await send_milestone_notification(user_name, member, is_external_user, hours_to_notify, total_time)

            return

        # Verificar si ya se notificó este milestone específico
        elif hour_milestone not in notified_milestones:
            # AGREGAR ASISTENCIA ANTES DE DETENER EL TRACKING
            if member:
                await add_attendance_for_milestone(member, total_hours)

            # Marcar este milestone como notificado
            notified_milestones.append(hour_milestone)
            user_data['notified_milestones'] = notified_milestones

            try:
                time_tracker.save_data()
            except Exception as e:
                print(f"⚠️ Error guardando milestone para {user_name}: {e}")

            # Detener seguimiento para todos los usuarios
            try:
                time_tracker.stop_tracking(user_id)
                # Marcar como milestone completado para usuarios con rol especial
                if has_unlimited_role:
                    user_data_refresh = time_tracker.get_user_data(user_id)
                    if user_data_refresh:
                        user_data_refresh['milestone_completed'] = True
                        time_tracker.save_data()
            except Exception as e:
                print(f"⚠️ Error deteniendo tracking final para {user_name}: {e}")

            # Enviar notificación con retry y timeout
            await send_milestone_notification(user_name, member, is_external_user, total_hours, total_time)

    except Exception as e:
        print(f"❌ Error crítico en check_time_milestone para {user_name}: {e}")
        import traceback
        traceback.print_exc()

async def add_attendance_for_milestone(member: discord.Member, hours_completed: int):
    """Agregar asistencia cuando alguien completa milestone - considera tiempo ligado"""
    try:
        print(f"🔍 Verificando asistencia para milestone de {member.display_name} ({hours_completed} horas)")

        # Verificar si el tiempo está ligado
        linked_info = time_tracker.get_linked_user(member.id)
        if linked_info:
            # El tiempo está ligado - dar asistencia al usuario ligado
            admin_id = linked_info['admin_id']
            admin_name = linked_info['admin_name']
            print(f"🔗 Tiempo ligado encontrado: {admin_name} (ID: {admin_id})")
        else:
            # No está ligado - usar el iniciador original
            initiator_info = time_tracker.get_time_initiator(member.id)
            if not initiator_info:
                print(f"❌ No se encontró información del iniciador para {member.display_name}")
                return

            admin_id = initiator_info['admin_id']
            admin_name = initiator_info['admin_name']
            print(f"🔍 Iniciador encontrado: {admin_name} (ID: {admin_id})")

        # Verificar si el admin puede recibir asistencias
        if not time_tracker.can_receive_daily_attendance(admin_id):
            print(f"🚫 {admin_name} no puede recibir asistencias - NO se agregará asistencia")
            return

        # Obtener el miembro del servidor
        admin_member = None
        for guild in bot.guilds:
            admin_member = guild.get_member(admin_id)
            if admin_member:
                print(f"🔍 Miembro del servidor encontrado: {admin_member.display_name}")
                break

        if admin_member:
            if has_attendance_role(admin_member):
                # Agregar solo 1 asistencia por este milestone específico
                success = time_tracker.add_attendance(admin_id, admin_member.display_name, 1)
                if success:
                    # Enviar notificación de asistencia
                    attendance_info = time_tracker.get_attendance_info(admin_id)
                    await send_attendance_notification(admin_member, 1, member, attendance_info)
                    
                    link_status = "tiempo ligado" if linked_info else "tiempo iniciado"
                    print(f"✅ Asistencia agregada: {admin_member.display_name} (+1) por completar hora {hours_completed} de {member.display_name} ({link_status})")
                else:
                    print(f"⚠️ No se pudo agregar asistencia para {admin_member.display_name} (límites alcanzados)")
            else:
                role_info = get_role_info(admin_member)
                print(f"⚠️ {admin_member.display_name}{role_info} no tiene un rol que permita obtener asistencias (necesita Altos o superior)")
        else:
            print(f"⚠️ {admin_name} no está en el servidor para verificar rol de asistencia")

    except Exception as e:
        print(f"Error agregando asistencia: {e}")

async def send_attendance_notification(admin_member: discord.Member, hours_completed: int, user_member, attendance_info: dict):
    """Enviar notificación de asistencia agregada"""
    try:
        channel = bot.get_channel(ATTENDANCE_NOTIFICATION_CHANNEL_ID)
        if channel:
            attendances_text = "asistencia" if hours_completed == 1 else "asistencias"

            # Obtener el cargo del usuario
            cargo_info = get_cargo_info(admin_member)

            # Determinar referencia del usuario (puede ser member o nombre de usuario externo)
            if user_member and hasattr(user_member, 'mention'):
                user_reference = user_member.mention
            elif user_member and hasattr(user_member, 'display_name'):
                user_reference = f"**{user_member.display_name}**"
            else:
                user_reference = "**Usuario externo**"

            message = (f"📋 **ASISTENCIA REGISTRADA**\n"
                      f"{admin_member.mention} {cargo_info} ha recibido {hours_completed} {attendances_text} "
                      f"por completar tiempo de {user_reference}\n"
                      f"📊 **Asistencias:** Hoy: {attendance_info['daily']}/3 | Semana: {attendance_info['weekly']}/15 | Total: {attendance_info['total']}")

            await channel.send(message)
            print(f"✅ Asistencia registrada: {admin_member.display_name} (+{hours_completed})")
    except Exception as e:
        print(f"Error enviando notificación de asistencia: {e}")

async def send_milestone_notification(user_name: str, member, is_external_user: bool, hours: int, total_time: float):
    """Enviar notificación de milestone con sistema de retry ultra-robusto"""
    max_retries = 5  # Aumentado a 5 intentos
    base_delay = 1  # Delay inicial reducido
    max_timeout = 30  # Timeout máximo aumentado

    for attempt in range(max_retries):
        try:
            # Intentar obtener el canal con timeout
            channel = await asyncio.wait_for(
                asyncio.to_thread(bot.get_channel, NOTIFICATION_CHANNEL_ID),
                timeout=5.0
            )
            
            if not channel:
                print(f"❌ Canal de notificaciones no encontrado: {NOTIFICATION_CHANNEL_ID}")
                return

            formatted_time = time_tracker.format_time_human(total_time)

            # Decidir formato según si es usuario externo o de servidor
            if member and not is_external_user:
                user_reference = member.mention
            else:
                user_reference = f"**{user_name}**"

            if hours == 1:
                message = f"🎉 {user_reference} ha completado 1 Hora! Tiempo acumulado: {formatted_time} "
            else:
                message = f"🎉 {user_reference} ha completado {hours} Horas! Tiempo acumulado: {formatted_time} "

            # Timeout progresivo: aumenta con cada intento
            current_timeout = min(10 + (attempt * 5), max_timeout)
            
            # Enviar con timeout progresivo
            await asyncio.wait_for(channel.send(message), timeout=current_timeout)
            print(f"✅ Notificación enviada exitosamente: {user_name} completó {hours} hora(s) (intento {attempt + 1}, timeout: {current_timeout}s)")
            return

        except asyncio.TimeoutError:
            delay = base_delay * (2 ** attempt)  # Backoff exponencial más agresivo
            print(f"⚠️ Timeout ({current_timeout if 'current_timeout' in locals() else 'N/A'}s) enviando notificación para {user_name} (intento {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                print(f"🔄 Reintentando en {delay}s...")
                await asyncio.sleep(delay)
        except discord.HTTPException as e:
            if "50013" in str(e):  # No permissions
                print(f"❌ Sin permisos para enviar mensaje en canal {NOTIFICATION_CHANNEL_ID}")
                return
            elif "50035" in str(e):  # Invalid form body
                print(f"❌ Mensaje inválido para {user_name}: {e}")
                return
            print(f"⚠️ Error HTTP enviando notificación para {user_name} (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
        except discord.NotFound:
            print(f"❌ Canal de notificaciones no encontrado: {NOTIFICATION_CHANNEL_ID}")
            return
        except Exception as e:
            print(f"⚠️ Error inesperado enviando notificación para {user_name} (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

    # Si fallan todos los intentos, intentar una notificación de emergencia simplificada
    print(f"🚨 TODOS LOS INTENTOS FALLARON para {user_name}. Intentando notificación de emergencia...")
    try:
        channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if channel:
            emergency_message = f"⚠️ {user_reference if 'user_reference' in locals() else user_name} completó {hours}h - Notificación de emergencia"
            await asyncio.wait_for(channel.send(emergency_message), timeout=10.0)
            print(f"✅ Notificación de emergencia enviada para {user_name}")
            return
    except Exception as emergency_error:
        print(f"❌ Falló notificación de emergencia para {user_name}: {emergency_error}")

    print(f"❌ CRÍTICO: No se pudo enviar notificación para {user_name} después de {max_retries} intentos + emergencia")

async def daily_preregistration_monitor():
    """Monitorear pre-registros y activarlos automáticamente a la hora configurada Colombia"""
    print(f"🔄 Iniciando monitoreo de pre-registro diario ({AUTO_START_HOUR:02d}:{AUTO_START_MINUTE:02d} Colombia)")
    
    while True:
        try:
            # Verificar cada 30 segundos
            await asyncio.sleep(30)
            
            # Obtener hora actual en Colombia
            colombia_now = datetime.now(colombia_tz)
            current_hour = colombia_now.hour
            current_minute = colombia_now.minute
            
            # Verificar si es exactamente la hora configurada (con ventana de 1 minuto)
            if current_hour == AUTO_START_HOUR and current_minute == AUTO_START_MINUTE:
                print(f"🕐 ¡Son las {AUTO_START_HOUR:02d}:{AUTO_START_MINUTE:02d} en Colombia! Activando pre-registros...")
                
                # Activar todos los pre-registros
                activated_users = await activate_all_preregistrations()
                
                if activated_users > 0:
                    print(f"✅ {activated_users} usuario(s) pre-registrado(s) activado(s) automáticamente")
                    
                    # Enviar notificación al canal de asistencias
                    try:
                        channel = bot.get_channel(ATTENDANCE_NOTIFICATION_CHANNEL_ID)
                        if channel:
                            start_time_formatted = f"{AUTO_START_HOUR:02d}:{AUTO_START_MINUTE:02d}"
                    except Exception as e:
                        print(f"Error enviando notificación de activación: {e}")
                else:
                    print("ℹ️ No había usuarios pre-registrados para activar")
                
                # Esperar 2 minutos para evitar activaciones múltiples
                await asyncio.sleep(120)
            
            # También verificar si hay pre-registros expirados (después de la hora configurada sin activar)
            elif current_hour > AUTO_START_HOUR or (current_hour == AUTO_START_HOUR and current_minute > AUTO_START_MINUTE):
                # Limpiar pre-registros expirados (si quedó alguno)
                cleaned = time_tracker.clean_expired_preregistrations()
                if cleaned > 0:
                    print(f"🧹 {cleaned} pre-registro(s) expirado(s) limpiado(s)")
        
        except Exception as e:
            print(f"❌ Error en monitoreo de pre-registro: {e}")
            await asyncio.sleep(60)  # Esperar 1 minuto antes de continuar

async def activate_all_preregistrations():
    """Activar todos los usuarios pre-registrados"""
    try:
        preregistered_users = time_tracker.get_preregistered_users()
        activated_count = 0
        
        for user_id_str, prereg_data in preregistered_users.items():
            try:
                user_id = int(user_id_str)
                user_name = prereg_data.get('name', f'Usuario {user_id}')
                admin_id = prereg_data.get('registered_by_id')
                admin_name = prereg_data.get('registered_by_name', 'Admin')
                
                # Activar el tracking
                success = time_tracker.activate_preregistration(user_id)
                if success:
                    activated_count += 1
                    print(f"✅ Activado: {user_name} (registrado por {admin_name})")
                else:
                    print(f"⚠️ Error activando: {user_name}")
                    
            except Exception as e:
                print(f"Error activando usuario {user_id_str}: {e}")
        
        return activated_count
    
    except Exception as e:
        print(f"Error general activando pre-registros: {e}")
        return 0

async def check_missing_milestones():
    """Verificar y notificar milestones perdidos para todos los usuarios con procesamiento paralelo"""
    try:
        # Timeout para obtener usuarios
        tracked_users = await asyncio.wait_for(
            asyncio.to_thread(time_tracker.get_all_tracked_users),
            timeout=15.0  # Aumentado timeout inicial
        )

        # Procesar usuarios con limite aumentado para garantizar todas las confirmaciones
        max_users_per_cycle = 100  # Aumentado significativamente
        max_concurrent = 10  # Procesar hasta 10 usuarios en paralelo

        # Dividir usuarios en chunks para procesamiento paralelo
        user_items = list(tracked_users.items())[:max_users_per_cycle]
        
        async def process_user_chunk(chunk):
            """Procesar un chunk de usuarios en paralelo"""
            tasks = []
            for user_id_str, data in chunk:
                task = process_single_user_milestone(user_id_str, data)
                tasks.append(task)
            
            # Ejecutar tasks en paralelo con timeout global
            await asyncio.gather(*tasks, return_exceptions=True)

        # Dividir en chunks pequeños para procesamiento paralelo controlado
        chunk_size = max_concurrent
        for i in range(0, len(user_items), chunk_size):
            chunk = user_items[i:i + chunk_size]
            try:
                await asyncio.wait_for(process_user_chunk(chunk), timeout=30.0)
                # Pausa pequeña entre chunks
                await asyncio.sleep(0.2)
            except asyncio.TimeoutError:
                print(f"⚠️ Timeout procesando chunk {i//chunk_size + 1}")
                continue

    except asyncio.TimeoutError:
        print("⚠️ Timeout obteniendo usuarios tracked")
    except Exception as e:
        print(f"❌ Error verificando milestones perdidos: {e}")

async def process_single_user_milestone(user_id_str: str, data: dict):
    """Procesar milestone de un solo usuario con manejo robusto de errores"""
    try:
        user_id = int(user_id_str)
        user_name = data.get('name', f'Usuario {user_id}')

        # Timeout para obtener tiempo total
        total_time = await asyncio.wait_for(
            asyncio.to_thread(time_tracker.get_total_time, user_id),
            timeout=3.0
        )

        # Verificar si el usuario está en el servidor
        guild = None
        member = None
        try:
            guild = bot.guilds[0] if bot.guilds else None
            if guild:
                member = guild.get_member(user_id)
        except Exception as e:
            print(f"⚠️ Error obteniendo miembro para {user_name}: {e}")

        # Para usuarios externos, continuar con verificación
        has_unlimited_role = False
        is_external_user = data.get('is_external_user', False)

        if member:
            try:
                has_unlimited_role = has_unlimited_time_role(member)
            except Exception as e:
                print(f"⚠️ Error verificando rol para {user_name}: {e}")
                has_unlimited_role = False

        # Asegurar que existe el campo notified_milestones
        if 'notified_milestones' not in data:
            data['notified_milestones'] = []

        notified_milestones = data.get('notified_milestones', [])
        total_hours = int(total_time // 3600)

        # Verificar milestones perdidos
        missing_milestones = []
        for h in range(1, total_hours + 1):
            milestone = h * 3600
            if milestone not in notified_milestones:
                missing_milestones.append((milestone, h))

        # Notificar milestone más alto perdido
        if missing_milestones:
            milestone_to_notify, hours_to_notify = missing_milestones[-1]

            # AGREGAR ASISTENCIA ANTES DE DETENER TRACKING
            if member:
                await add_attendance_for_milestone(member, hours_to_notify)

            # Marcar todos los milestones perdidos como notificados
            for milestone, _ in missing_milestones:
                if milestone not in notified_milestones:
                    notified_milestones.append(milestone)
            data['notified_milestones'] = notified_milestones

            # Guardar datos con timeout corto
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(time_tracker.save_data),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                print(f"⚠️ Timeout guardando milestones para {user_name}")

            # Detener seguimiento
            if hours_to_notify >= 1:
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(time_tracker.stop_tracking, user_id),
                        timeout=2.0
                    )

                    # Marcar como milestone completado para usuarios con rol especial
                    if has_unlimited_role:
                        user_data = time_tracker.get_user_data(user_id)
                        if user_data:
                            user_data['milestone_completed'] = True
                            await asyncio.wait_for(
                                asyncio.to_thread(time_tracker.save_data),
                                timeout=2.0
                            )
                except asyncio.TimeoutError:
                    print(f"⚠️ Timeout deteniendo tracking para {user_name}")

            # Enviar notificación (esta función ya tiene su propio sistema de retry robusto)
            await send_milestone_notification(user_name, member, is_external_user, hours_to_notify, total_time)

            # Marcar procesado
            data['last_milestone_check'] = total_time
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(time_tracker.save_data),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                print(f"⚠️ Timeout guardando última verificación para {user_name}")

    except asyncio.TimeoutError:
        print(f"⚠️ Timeout procesando usuario {user_id_str}")
    except Exception as e:
        print(f"⚠️ Error procesando usuario {user_id_str}: {e}")



async def periodic_milestone_check():
    """Verificar milestones periódicamente para usuarios activos"""
    milestone_check_count = 0
    error_count = 0
    max_errors = 5

    while True:
        try:
            await asyncio.sleep(5)  # Verificar cada 5 segundos
            milestone_check_count += 1

            # Verificar milestones perdidos cada 12 ciclos (cada minuto)
            if milestone_check_count % 12 == 1:
                try:
                    await asyncio.wait_for(check_missing_milestones(), timeout=30.0)
                except asyncio.TimeoutError:
                    print("⚠️ Timeout en verificación de milestones perdidos")
                except Exception as e:
                    print(f"⚠️ Error en verificación de milestones perdidos: {e}")

            # Verificar usuarios activos para sesiones de 1 hora con procesamiento paralelo
            try:
                tracked_users = await asyncio.wait_for(
                    asyncio.to_thread(time_tracker.get_all_tracked_users),
                    timeout=15.0
                )

                # Filtrar solo usuarios activos
                active_users = [
                    (user_id_str, data) for user_id_str, data in tracked_users.items()
                    if data.get('is_active', False) and not data.get('is_paused', False)
                ]

                max_active_users = 80  # Aumentado significativamente
                active_users = active_users[:max_active_users]

                # Procesar usuarios activos en paralelo (chunks de 5)
                chunk_size = 5
                for i in range(0, len(active_users), chunk_size):
                    chunk = active_users[i:i + chunk_size]
                    
                    # Crear tasks para procesamiento paralelo
                    tasks = []
                    for user_id_str, data in chunk:
                        try:
                            user_id = int(user_id_str)
                            user_name = data.get('name', f'Usuario {user_id}')
                            
                            # Crear task con timeout individual
                            task = asyncio.wait_for(
                                check_time_milestone(user_id, user_name),
                                timeout=15.0
                            )
                            tasks.append(task)
                        except Exception as e:
                            print(f"⚠️ Error creando task para usuario {user_id_str}: {e}")

                    if tasks:
                        # Ejecutar chunk en paralelo
                        try:
                            await asyncio.gather(*tasks, return_exceptions=True)
                        except Exception as e:
                            print(f"⚠️ Error en procesamiento paralelo de chunk: {e}")
                        
                        # Pausa pequeña entre chunks
                        await asyncio.sleep(0.3)

                print(f"✅ Verificados {len(active_users)} usuarios activos en chunks paralelos")

            except asyncio.TimeoutError:
                print("⚠️ Timeout obteniendo usuarios activos")
            except Exception as e:
                print(f"⚠️ Error obteniendo usuarios activos: {e}")

            # Reset contador de errores si el ciclo fue exitoso
            error_count = 0

        except Exception as e:
            error_count += 1
            print(f"❌ Error en verificación periódica de milestones (#{error_count}): {e}")

            if error_count >= max_errors:
                print(f"🚨 Demasiados errores consecutivos ({error_count}). Pausando verificaciones por 60 segundos...")
                await asyncio.sleep(60)
                error_count = 0
            else:
                # Backoff exponencial en caso de errores
                sleep_time = min(10 * (2 ** error_count), 60)
                await asyncio.sleep(sleep_time)

# Iniciar la verificación periódica después de definir la función
async def start_periodic_checks():
    """Iniciar la verificación periódica de milestones y pre-registro"""
    global milestone_check_task, daily_preregistration_task
    if milestone_check_task is None:
        milestone_check_task = bot.loop.create_task(periodic_milestone_check())
        print('✅ Task de verificación de milestones iniciado')
    
    if daily_preregistration_task is None:
        daily_preregistration_task = bot.loop.create_task(daily_preregistration_monitor())
        print('✅ Task de pre-registro diario iniciado')



# Agregar la inicialización al final del archivo
@bot.event
async def on_connect():
    """Evento que se ejecuta cuando el bot se conecta"""
    await start_periodic_checks()

@bot.tree.command(name="saber_tiempo", description="Ver estadísticas detalladas de un usuario")
@discord.app_commands.describe(usuario="El usuario del que ver estadísticas")
@is_admin()
async def saber_tiempo_admin(interaction: discord.Interaction, usuario: discord.Member):
    user_data = time_tracker.get_user_data(usuario.id)

    if not user_data:
        await interaction.response.send_message(f"❌ No se encontraron datos para {usuario.mention}")
        return

    total_time = time_tracker.get_total_time(usuario.id)
    formatted_time = time_tracker.format_time_human(total_time)

    embed = discord.Embed(
        title=f"📊 Estadísticas de {usuario.display_name}",
        color=discord.Color.green(),
        timestamp=datetime.now()
    )

    embed.add_field(name="⏱️ Tiempo Total", value=formatted_time, inline=True)

    # Verificar si el usuario tiene rol especial
    has_special_role = has_unlimited_time_role(usuario)

    status = "🟢 Activo" if user_data.get('is_active', False) else "🔴 Inactivo"
    if user_data.get('is_paused', False):
        total_hours = total_time / 3600
        # Verificar si completó milestone y debe mostrar como "Terminado"
        if user_data.get("milestone_completed", False) or (has_special_role and total_hours >= 4.0) or (not has_special_role and total_hours >= 2.0):
            status = "✅ Terminado"
        else:
            status = "⏸️ Pausado"

    embed.add_field(name="📍 Estado", value=status, inline=True)

    # Mostrar tiempo pausado si está pausado
    if user_data.get('is_paused', False):
        paused_duration = time_tracker.get_paused_duration(usuario.id)
        formatted_paused_time = time_tracker.format_time_human(paused_duration) if paused_duration > 0 else "0 Segundos"
        embed.add_field(
            name=f"⏸️ Tiempo Pausado de {usuario.display_name}",
            value=formatted_paused_time,
            inline=False
        )

    # Mostrar contador de pausas
    pause_count = time_tracker.get_pause_count(usuario.id)
    if pause_count > 0:
        pause_text = "pausa" if pause_count == 1 else "pausas"
        embed.add_field(
            name="📊 Contador de Pausas",
            value=f"{pause_count} {pause_text} de 3 máximo",
            inline=True
        )

    embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
    embed.set_footer(text="Estadísticas actualizadas")

    await interaction.response.send_message(embed=embed)





def check_mi_tiempo_permission():
    """Decorator para verificar si el usuario puede usar /mi_tiempo"""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            if not hasattr(interaction, 'guild') or not interaction.guild:
                return False

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                return False

            # Verificar si tiene el rol autorizado para /mi_tiempo
            return can_use_mi_tiempo(member)

        except Exception as e:
            print(f"Error en verificación de permisos /mi_tiempo: {e}")
            return False

    return discord.app_commands.check(predicate)

# =================== SISTEMA DE ROLES ESPECÍFICOS ===================

# Definir los roles disponibles y sus niveles
ROLES_ESPECIFICOS = {
    "medios": {
        "nombre": "Medios",
        "nivel": 1,
        "emoji": "🥉"
    },
    "gold": {
        "nombre": "Gold",
        "nivel": 2,
        "emoji": "🏆"
    },
    "altos": {
        "nombre": "Altos",
        "nivel": 3,
        "emoji": "🥈"
    },
    "imperiales": {
        "nombre": "Imperiales",
        "nivel": 4,
        "emoji": "👑"
    },
    "nobleza": {
        "nombre": "Nobleza",
        "nivel": 5,
        "emoji": "🏰"
    },
    "monarquia": {
        "nombre": "Monarquía",
        "nivel": 6,
        "emoji": "👸"
    },
    "supremos": {
        "nombre": "Supremos",
        "nivel": 7,
        "emoji": "⭐"
    }
}

def get_user_role_type(member: discord.Member) -> str:
    """Determina el tipo de rol del usuario basándose en sus roles (retorna el de mayor jerarquía)"""
    # Definir jerarquía de roles (de mayor a menor)
    role_hierarchy = ["supremos", "monarquia", "nobleza", "imperiales", "altos", "gold", "medios"]
    
    # Buscar el rol de mayor jerarquía que tenga el usuario
    for role_type in role_hierarchy:
        for role in member.roles:
            role_name_lower = role.name.lower()
            if role_type in role_name_lower:
                return role_type
    
    return "normal"

def get_role_info(member: discord.Member) -> str:
    """Obtiene la información del rol de mayor jerarquía del usuario en Discord"""
    if member and member.roles:
        # Obtener todos los roles excepto @everyone y ordenarlos por posición (mayor posición = mayor jerarquía)
        user_roles = [role for role in member.roles if role.name != "@everyone"]
        if user_roles:
            # Ordenar por posición descendente para obtener el rol de mayor jerarquía
            highest_role = max(user_roles, key=lambda role: role.position)
            return f" ({highest_role.name})"
    return ""

def get_cargo_info(member: discord.Member) -> str:
    """Obtiene la información del cargo del usuario con formato 'Cargo Tipo:'"""
    if member:
        for role in member.roles:
            role_name_lower = role.name.lower()
            if "supremos" in role_name_lower:
                return "**Cargo Supremo:**"
            elif "monarquia" in role_name_lower:
                return "**Cargo Monarquía:**"
            elif "nobleza" in role_name_lower:
                return "**Cargo Nobleza:**"
            elif "imperiales" in role_name_lower:
                return "**Cargo Imperial:**"
            elif "altos" in role_name_lower:
                return "**Cargo Alto:**"
            elif "medios" in role_name_lower:
                return "**Cargo Medio:**"
    return "**Sin Cargo:**"

def has_attendance_role(member: discord.Member) -> bool:
    """Verificar si el usuario tiene un rol que puede obtener asistencias"""
    role_type = get_user_role_type(member)
    return role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]

@bot.tree.command(name="dar_cargo_medio", description="Asignar el rol Medios a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Medios a asignar")
@is_admin()
async def dar_cargo_medio(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "medios")

@bot.tree.command(name="dar_cargo_gold", description="Asignar el rol Gold a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Gold a asignar")
@is_admin()
async def dar_cargo_gold(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "gold")

@bot.tree.command(name="dar_cargo_alto", description="Asignar el rol Altos a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Altos a asignar")
@is_admin()
async def dar_cargo_alto(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "altos")

@bot.tree.command(name="dar_cargo_imperial", description="Asignar el rol Imperiales a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Imperiales a asignar")
@is_admin()
async def dar_cargo_imperial(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "imperiales")

@bot.tree.command(name="dar_cargo_nobleza", description="Asignar el rol Nobleza a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Nobleza a asignar")
@is_admin()
async def dar_cargo_nobleza(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "nobleza")

@bot.tree.command(name="dar_cargo_monarquia", description="Asignar el rol Monarquía a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Monarquía a asignar")
@is_admin()
async def dar_cargo_monarquia(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "monarquia")

@bot.tree.command(name="dar_cargo_supremo", description="Asignar el rol Supremos a un usuario")
@discord.app_commands.describe(usuario="El usuario al que asignar el rol", rol="El rol Supremos a asignar")
@is_admin()
async def dar_cargo_supremo(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    await asignar_rol_especifico(interaction, usuario, rol, "supremos")

async def asignar_rol_especifico(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role, tipo_rol: str):
    """Función auxiliar para asignar roles específicos"""
    try:
        # Verificar si el usuario es un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se pueden asignar roles a bots.", ephemeral=True)
            return

        # Verificar si el usuario ya tiene el rol
        if rol in usuario.roles:
            rol_info = ROLES_ESPECIFICOS[tipo_rol]
            await interaction.response.send_message(
                f"⚠️ {usuario.mention} ya tiene el rol {rol_info['emoji']} **{rol.name}**",
                ephemeral=True
            )
            return

        # Asignar el rol
        await usuario.add_roles(rol, reason=f"Rol asignado por {interaction.user.display_name}")

        # Respuesta de confirmación
        rol_info = ROLES_ESPECIFICOS[tipo_rol]
        embed = discord.Embed(
            title="✅ Rol Asignado",
            description=f"{rol_info['emoji']} **{rol.name}** ha sido asignado a {usuario.mention}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Usuario", value=usuario.mention, inline=True)
        embed.add_field(name="🎭 Rol", value=f"{rol_info['emoji']} {rol.name}", inline=True)
        embed.add_field(name="📊 Nivel", value=f"Nivel {rol_info['nivel']}", inline=True)
        embed.add_field(name="👮 Asignado por", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Tipo: {rol_info['nombre']}")

        await interaction.response.send_message(embed=embed)

        # Registrar en logs
        print(f"✅ Rol {rol_info['nombre']} ({rol.name}) asignado a {usuario.display_name} por {interaction.user.display_name}")

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ No tengo permisos para asignar este rol. Verifica que mi rol esté por encima del rol que intentas asignar.",
            ephemeral=True
        )
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"❌ Error al asignar el rol: {e}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al asignar el rol.",
            ephemeral=True
        )
        print(f"Error asignando rol {tipo_rol}: {e}")

@bot.tree.command(name="quitar_cargo", description="Quitar un rol específico de un usuario")
@discord.app_commands.describe(usuario="El usuario al que quitar el rol", rol="El rol a quitar")
@is_admin()
async def quitar_cargo(interaction: discord.Interaction, usuario: discord.Member, rol: discord.Role):
    """Comando para quitar roles específicos"""
    try:
        # Verificar si el usuario es un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se pueden quitar roles de bots.", ephemeral=True)
            return

        # Verificar si el usuario tiene el rol
        if rol not in usuario.roles:
            await interaction.response.send_message(
                f"⚠️ {usuario.mention} no tiene el rol **{rol.name}**",
                ephemeral=True
            )
            return

        # Quitar el rol
        await usuario.remove_roles(rol, reason=f"Rol removido por {interaction.user.display_name}")

        # Respuesta de confirmación
        embed = discord.Embed(
            title="✅ Rol Removido",
            description=f"**{rol.name}** ha sido removido de {usuario.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 Usuario", value=usuario.mention, inline=True)
        embed.add_field(name="🎭 Rol Removido", value=rol.name, inline=True)
        embed.add_field(name="👮 Removido por", value=interaction.user.mention, inline=False)

        await interaction.response.send_message(embed=embed)

        # Registrar en logs
        print(f"✅ Rol {rol.name} removido de {usuario.display_name} por {interaction.user.display_name}")

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ No tengo permisos para quitar este rol. Verifica que mi rol esté por encima del rol que intentas quitar.",
            ephemeral=True
        )
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"❌ Error al quitar el rol: {e}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al quitar el rol.",
            ephemeral=True
        )
        print(f"Error quitando rol: {e}")

@bot.tree.command(name="ver_roles_usuario", description="Ver todos los roles específicos de un usuario")
@discord.app_commands.describe(usuario="El usuario del que ver los roles")
@is_admin()
async def ver_roles_usuario(interaction: discord.Interaction, usuario: discord.Member):
    """Ver todos los roles específicos de un usuario"""
    try:
        # Obtener todos los roles del usuario
        user_roles = usuario.roles[1:]  # Excluir @everyone

        if not user_roles:
            await interaction.response.send_message(
                f"📋 {usuario.mention} no tiene roles asignados (excepto @everyone)",
                ephemeral=True
            )
            return

        # Separar roles específicos del sistema de otros roles
        roles_especificos = []
        otros_roles = []

        for role in user_roles:
            # Buscar si el rol coincide con alguno de nuestros tipos específicos
            es_especifico = False
            for tipo, info in ROLES_ESPECIFICOS.items():
                if info['nombre'].lower() in role.name.lower():
                    roles_especificos.append((role, info))
                    es_especifico = True
                    break

            if not es_especifico:
                otros_roles.append(role)

        # Crear embed
        embed = discord.Embed(
            title=f"🎭 Roles de {usuario.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)

        # Roles específicos del sistema
        if roles_especificos:
            roles_especificos.sort(key=lambda x: x[1]['nivel'], reverse=True)  # Ordenar por nivel
            roles_text = ""
            for role, info in roles_especificos:
                roles_text += f"{info['emoji']} **{role.name}** (Nivel {info['nivel']})\n"
            embed.add_field(name="⭐ Roles del Sistema", value=roles_text, inline=False)

        # Otros roles
        if otros_roles:
            otros_text = ""
            for role in otros_roles[:10]:  # Limitar a 10 roles para evitar overflow
                otros_text += f"• {role.name}\n"
            if len(otros_roles) > 10:
                otros_text += f"... y {len(otros_roles) - 10} más"
            embed.add_field(name="📋 Otros Roles", value=otros_text, inline=False)

        embed.add_field(name="📊 Total de Roles", value=str(len(user_roles)), inline=True)
        embed.set_footer(text="Información de roles")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error al obtener información de roles.",
            ephemeral=True
        )
        print(f"Error obteniendo roles de usuario: {e}")

@bot.tree.command(name="mis_asistencias", description="Ver tus propias asistencias")
async def mis_asistencias(interaction: discord.Interaction):
    """Ver tus propias asistencias"""
    try:
        # Cualquier usuario puede usar este comando
        member = interaction.guild.get_member(interaction.user.id)
        
        # Verificar si el usuario tiene rol de asistencia
        if not has_attendance_role(member):
            role_info = get_role_info(member)
            if role_info:
                await interaction.response.send_message(
                    f"❌ Tu rol{role_info} no permite obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ No tienes un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            return

        # Obtener información de asistencias
        attendance_info = time_tracker.get_attendance_info(interaction.user.id)
        role_info = get_role_info(member)

        # Crear embed
        embed = discord.Embed(
            title=f"📋 Tus Asistencias",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        embed.add_field(name="📅 Hoy", value=f"{attendance_info['daily']}/3", inline=True)
        embed.add_field(name="📆 Esta Semana", value=f"{attendance_info['weekly']}/15", inline=True)
        embed.add_field(name="📊 Total", value=f"{attendance_info['total']}", inline=True)

        # Información del rol
        embed.add_field(name="🎭 Rol", value=role_info.strip("()") if role_info else "Sin rol específico", inline=False)

        # Determinar créditos semanales según el rol
        role_type = get_user_role_type(member)
        weekly_credits = 0
        if role_type == "altos":
            weekly_credits = 43
        elif role_type == "imperiales":
            weekly_credits = 48
        elif role_type == "nobleza":
            weekly_credits = 54
        elif role_type == "monarquia":
            weekly_credits = 60
        elif role_type == "supremos":
            weekly_credits = 70

        # Calcular créditos ganados basado en las asistencias totales
        if weekly_credits > 0:
            # Calcular créditos basándose en todas las asistencias acumuladas
            # Cada 15 asistencias = créditos semanales completos
            complete_weeks = attendance_info['total'] // 15
            remaining_attendances = attendance_info['total'] % 15
            
            # Créditos de semanas completas + créditos proporcionales
            total_credits_earned = (complete_weeks * weekly_credits) + int((remaining_attendances / 15) * weekly_credits)

            # Calcular créditos de la semana actual - CORREGIDO
            if attendance_info['weekly'] >= 15:
                current_week_credits = weekly_credits
            else:
                current_week_credits = int((attendance_info['weekly'] / 15) * weekly_credits)

            embed.add_field(
                name="💰 Créditos Ganados",
                value=f"**Esta Semana:** {current_week_credits} Créditos ({attendance_info['weekly']}/15 asistencias)\n"
                      f"**Total Acumulado:** {total_credits_earned} Créditos",
                inline=False
            )

        # Información adicional
        if weekly_credits > 0:
            embed.add_field(
                name="ℹ️ Sistema de Asistencias",
                value="• 1 asistencia por cada hora completada\n"
                      "• 2 asistencias por 2 horas completadas\n"
                      "• Máximo 3 asistencias por día\n"
                      "• Máximo 15 asistencias por semana",
                inline=False
            )

            embed.add_field(
                name="💎 Potencial Semanal",
                value=f"Con 15 asistencias completas: **{weekly_credits} Créditos**\n"
                      f"Progreso: **{attendance_info['weekly']}/15** asistencias",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Sistema de Asistencias",
                value="• 1 asistencia por cada hora completada\n"
                      "• 2 asistencias por 2 horas completadas\n"
                      "• Máximo 3 asistencias por día\n"
                      "• Máximo 15 asistencias por semana\n"
                      "• Este cargo no recibe créditos por asistencias",
                inline=False
            )

        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        embed.set_footer(text="Consulta tus asistencias cuando quieras")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error al obtener asistencias del usuario.",
            ephemeral=True
        )
        print(f"Error en ver_asistencias: {e}")

@bot.tree.command(name="ver_asistencias_admin", description="Ver asistencias de cualquier usuario (solo administradores)")
@discord.app_commands.describe(usuario="El usuario del que ver las asistencias")
@is_admin()
async def ver_asistencias_admin(interaction: discord.Interaction, usuario: discord.Member):
    """Ver asistencias de un usuario (comando para administradores)"""
    try:
        # Verificar si el usuario tiene rol de asistencia
        if not has_attendance_role(usuario):
            role_info = get_role_info(usuario)
            if role_info:
                await interaction.response.send_message(
                    f"❌ {usuario.mention}{role_info} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {usuario.mention} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            return

        # Obtener información de asistencias
        attendance_info = time_tracker.get_attendance_info(usuario.id)
        role_info = get_role_info(usuario)

        # Crear embed
        embed = discord.Embed(
            title=f"📋 Asistencias de {usuario.display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        embed.add_field(name="📅 Hoy", value=f"{attendance_info['daily']}/3", inline=True)
        embed.add_field(name="📆 Esta Semana", value=f"{attendance_info['weekly']}/15", inline=True)
        embed.add_field(name="📊 Total", value=f"{attendance_info['total']}", inline=True)

        # Información del rol
        embed.add_field(name="🎭 Rol", value=role_info.strip("()") if role_info else "Sin rol específico", inline=False)

        # Determinar créditos semanales según el rol
        role_type = get_user_role_type(usuario)
        weekly_credits = 0
        if role_type == "altos":
            weekly_credits = 43
        elif role_type == "imperiales":
            weekly_credits = 48
        elif role_type == "nobleza":
            weekly_credits = 54
        elif role_type == "monarquia":
            weekly_credits = 60
        elif role_type == "supremos":
            weekly_credits = 70

        # Calcular créditos ganados basado en las asistencias totales
        if weekly_credits > 0:
            # Calcular créditos basándose en todas las asistencias acumuladas
            # Cada 15 asistencias = créditos semanales completos
            complete_weeks = attendance_info['total'] // 15
            remaining_attendances = attendance_info['total'] % 15
            
            # Créditos de semanas completas + créditos proporcionales
            total_credits_earned = (complete_weeks * weekly_credits) + int((remaining_attendances / 15) * weekly_credits)

            # Calcular créditos de la semana actual
            if attendance_info['weekly'] >= 15:
                current_week_credits = weekly_credits
            else:
                current_week_credits = int((attendance_info['weekly'] / 15) * weekly_credits)

            embed.add_field(
                name="💰 Créditos Ganados",
                value=f"**Esta Semana:** {current_week_credits} Créditos ({attendance_info['weekly']}/15 asistencias)\n"
                      f"**Total Acumulado:** {total_credits_earned} Créditos",
                inline=False
            )

        # Información adicional
        if weekly_credits > 0:
            embed.add_field(
                name="ℹ️ Sistema de Asistencias",
                value="• 1 asistencia por cada hora completada\n"
                      "• 2 asistencias por 2 horas completadas\n"
                      "• Máximo 3 asistencias por día\n"
                      "• Máximo 15 asistencias por semana",
                inline=False
            )

            embed.add_field(
                name="💎 Potencial Semanal",
                value=f"Con 15 asistencias completas: **{weekly_credits} Créditos**\n"
                      f"Progreso: **{attendance_info['weekly']}/15** asistencias",
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Sistema de Asistencias",
                value="• 1 asistencia por cada hora completada\n"
                      "• 2 asistencias por 2 horas completadas\n"
                      "• Máximo 3 asistencias por día\n"
                      "• Máximo 15 asistencias por semana\n"
                      "• Este cargo no recibe créditos por asistencias",
                inline=False
            )

        embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else usuario.default_avatar.url)
        embed.set_footer(text=f"Consultado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error al obtener asistencias del usuario.",
            ephemeral=True
        )
        print(f"Error en ver_asistencias_admin: {e}")

@bot.tree.command(name="sumar_asistencias", description="Sumar asistencias manualmente a un usuario")
@discord.app_commands.describe(
    usuario="El usuario al que sumar asistencias",
    cantidad="Cantidad de asistencias a sumar (máximo 15, ignora límites diarios/semanales)"
)
@is_admin()
async def sumar_asistencias(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    """Sumar asistencias manualmente a un usuario"""
    try:
        # Verificar que la cantidad esté entre 1 y 15
        if cantidad < 1 or cantidad > 15:
            await interaction.response.send_message("❌ La cantidad de asistencias debe ser entre 1 y 15", ephemeral=True)
            return

        # Verificar que no sea un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se pueden asignar asistencias a bots", ephemeral=True)
            return

        # Verificar si el usuario tiene rol de asistencia
        if not has_attendance_role(usuario):
            role_info = get_role_info(usuario)
            if role_info:
                await interaction.response.send_message(
                    f"❌ {usuario.mention}{role_info} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {usuario.mention} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            return

        # Agregar las asistencias (sin verificar límites)
        success = time_tracker.add_manual_attendance(usuario.id, usuario.display_name, cantidad)
        
        if success:
            # Obtener información actualizada
            new_attendance_info = time_tracker.get_attendance_info(usuario.id)
            role_info = get_role_info(usuario)
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="✅ Asistencias Agregadas",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="👤 Usuario", value=f"{usuario.mention}{role_info}", inline=False)
            embed.add_field(name="➕ Asistencias Agregadas", value=str(cantidad), inline=True)
            embed.add_field(name="👮 Agregado por", value=interaction.user.mention, inline=True)
            
            embed.add_field(
                name="📊 Estado Actual",
                value=f"📅 Hoy: {new_attendance_info['daily']} (sin cambios)\n"
                      f"📆 Esta semana: {new_attendance_info['weekly']} (+{cantidad} manual)\n"
                      f"📋 Total: {new_attendance_info['total']} (+{cantidad})",
                inline=False
            )
            
            # Información sobre créditos si aplica
            role_type = get_user_role_type(usuario)
            credits_per_attendance = 0
            if role_type == "altos":
                credits_per_attendance = 43 // 15  # 2.87 ≈ 2
            elif role_type == "imperiales":
                credits_per_attendance = 48 // 15  # 3.2 ≈ 3
            elif role_type == "nobleza":
                credits_per_attendance = 54 // 15  # 3.6 ≈ 3
            elif role_type == "supremos":
                credits_per_attendance = 70 // 15  # 4.67 ≈ 4
            
            if credits_per_attendance > 0:
                credits_earned = cantidad * credits_per_attendance
                embed.add_field(
                    name="💰 Créditos",
                    value=f"+{credits_earned} créditos ({credits_per_attendance} por asistencia)",
                    inline=True
                )
            
            # Mostrar nota explicativa
            embed.add_field(
                name="ℹ️ Nota",
                value="Las asistencias manuales solo afectan el contador semanal y total.\n"
                      "El contador diario permanece sin cambios.",
                inline=False
            )
            
            embed.set_footer(text="Asistencias manuales: solo semanal y total")
            
            await interaction.response.send_message(embed=embed)
            
            # Log
            print(f"✅ Asistencias agregadas manualmente: {usuario.display_name} (+{cantidad}) por {interaction.user.display_name}")
            
        else:
            await interaction.response.send_message(
                "❌ Error al agregar asistencias. Intenta de nuevo.",
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al agregar asistencias.",
            ephemeral=True
        )
        print(f"Error en sumar_asistencias: {e}")

@bot.tree.command(name="agregar_asistencias_diarias", description="Agregar asistencias diarias específicamente (máximo 3 por día)")
@discord.app_commands.describe(
    usuario="El usuario al que agregar asistencias diarias",
    cantidad="Cantidad de asistencias diarias a agregar (1-3)"
)
@is_admin()
async def agregar_asistencias_diarias(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    """Agregar asistencias diarias específicamente (suma a diarias, semanales y totales)"""
    try:
        # Verificar que la cantidad esté entre 1 y 3
        if cantidad < 1 or cantidad > 3:
            await interaction.response.send_message("❌ La cantidad de asistencias diarias debe ser entre 1 y 3", ephemeral=True)
            return

        # Verificar que no sea un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se pueden asignar asistencias a bots", ephemeral=True)
            return

        # Verificar si el usuario tiene rol de asistencia
        if not has_attendance_role(usuario):
            role_info = get_role_info(usuario)
            if role_info:
                await interaction.response.send_message(
                    f"❌ {usuario.mention}{role_info} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {usuario.mention} no tiene un rol que permita obtener asistencias.\n"
                    f"Solo los roles **Altos, Imperiales, Nobleza, Monarquía y Supremos** pueden obtener asistencias.",
                    ephemeral=True
                )
            return

        # Obtener estado actual para verificar límite diario
        current_daily = time_tracker.get_daily_attendance(usuario.id)
        if current_daily + cantidad > 3:
            available_slots = 3 - current_daily
            await interaction.response.send_message(
                f"❌ No se puede agregar {cantidad} asistencias diarias.\n"
                f"**{usuario.mention}** ya tiene {current_daily}/3 asistencias hoy.\n"
                f"Solo puedes agregar {available_slots} asistencia{'s' if available_slots != 1 else ''} más.",
                ephemeral=True
            )
            return

        # Agregar las asistencias diarias
        success = time_tracker.add_daily_manual_attendance(usuario.id, usuario.display_name, cantidad)
        
        if success:
            # Obtener información actualizada
            new_attendance_info = time_tracker.get_attendance_info(usuario.id)
            role_info = get_role_info(usuario)
            
            # Crear embed de confirmación
            embed = discord.Embed(
                title="✅ Asistencias Diarias Agregadas",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="👤 Usuario", value=f"{usuario.mention}{role_info}", inline=False)
            embed.add_field(name="➕ Asistencias Diarias Agregadas", value=str(cantidad), inline=True)
            embed.add_field(name="👮 Agregado por", value=interaction.user.mention, inline=True)
            
            embed.add_field(
                name="📊 Estado Actual",
                value=f"📅 Hoy: {new_attendance_info['daily']}/3 (+{cantidad})\n"
                      f"📆 Esta semana: {new_attendance_info['weekly']}/15 (+{cantidad})\n"
                      f"📋 Total: {new_attendance_info['total']} (+{cantidad})",
                inline=False
            )
            
            # Información sobre créditos si aplica
            role_type = get_user_role_type(usuario)
            credits_per_attendance = 0
            if role_type == "altos":
                credits_per_attendance = 43 // 15  # 2.87 ≈ 2
            elif role_type == "imperiales":
                credits_per_attendance = 48 // 15  # 3.2 ≈ 3
            elif role_type == "nobleza":
                credits_per_attendance = 54 // 15  # 3.6 ≈ 3
            elif role_type == "monarquia":
                credits_per_attendance = 60 // 15  # 4 créditos por asistencia
            elif role_type == "supremos":
                credits_per_attendance = 70 // 15  # 4.67 ≈ 4
            
            if credits_per_attendance > 0:
                credits_earned = cantidad * credits_per_attendance
                embed.add_field(
                    name="💰 Créditos",
                    value=f"+{credits_earned} créditos ({credits_per_attendance} por asistencia)",
                    inline=True
                )
            
            # Mostrar nota explicativa
            embed.add_field(
                name="ℹ️ Nota",
                value="Las asistencias diarias afectan TODOS los contadores:\n"
                      "• Contador diario: +{} hoy\n"
                      "• Contador semanal: +{}\n"
                      "• Contador total: +{}".format(cantidad, cantidad, cantidad),
                inline=False
            )
            
            embed.set_footer(text="Asistencias diarias: afecta diario, semanal y total")
            
            await interaction.response.send_message(embed=embed)
            
            # Log
            print(f"✅ Asistencias diarias agregadas: {usuario.display_name} (+{cantidad}) por {interaction.user.display_name}")
            
        else:
            await interaction.response.send_message(
                "❌ Error al agregar asistencias diarias. Verifica los límites.",
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al agregar asistencias diarias.",
            ephemeral=True
        )
        print(f"Error en agregar_asistencias_diarias: {e}")

@bot.tree.command(name="resetear_asistencias", description="RESETEAR TODAS las asistencias de todos los usuarios")
@is_admin()
async def resetear_asistencias(interaction: discord.Interaction):
    """Resetear todas las asistencias de todos los usuarios"""
    # Obtener conteo actual de usuarios con asistencias
    attendance_data = time_tracker.attendance_data
    user_count = len(attendance_data)

    if user_count == 0:
        await interaction.response.send_message("❌ No hay usuarios con asistencias registradas")
        return

    # Crear embed de confirmación con información detallada
    embed = discord.Embed(
        title="⚠️ CONFIRMACIÓN REQUERIDA",
        description="Esta acción reseteará TODAS las asistencias de TODOS los usuarios",
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="📊 Datos que se resetearán:",
        value=f"• {user_count} usuarios con asistencias\n"
              f"• Todas las asistencias diarias\n"
              f"• Todas las asistencias semanales\n"
              f"• Todos los totales acumulados\n"
              f"• Todo el historial de asistencias",
        inline=False
    )
    embed.add_field(
        name="⚠️ ADVERTENCIA:",
        value="Esta acción NO se puede deshacer\n"
              "Se perderá todo el historial de asistencias\n"
              "Los usuarios seguirán apareciendo en `/paga_cargos` pero sin créditos",
        inline=False
    )
    embed.add_field(
        name="💡 Diferencia con limpiar base de datos:",
        value="• Este comando: Solo borra asistencias\n"
              "• `/limpiar_base_datos`: Borra usuarios completos",
        inline=False
    )
    embed.add_field(
        name="🔄 Para continuar:",
        value="Usa el comando `/resetear_asistencias_confirmar` con `confirmar: 'SI'`",
        inline=False
    )
    embed.set_footer(text=f"Solicitado por {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="resetear_asistencias_confirmar", description="CONFIRMAR reseteo completo de todas las asistencias")
@discord.app_commands.describe(confirmar="Escribe 'SI' para confirmar el reseteo completo")
@is_admin()
async def resetear_asistencias_confirmar(interaction: discord.Interaction, confirmar: str):
    """Confirmar y ejecutar el reseteo de todas las asistencias"""
    if confirmar.upper() != "SI":
        await interaction.response.send_message("❌ Operación cancelada. Debes escribir 'SI' para confirmar")
        return

    # Obtener información antes de resetear
    attendance_data = time_tracker.attendance_data
    user_count = len(attendance_data)

    if user_count == 0:
        await interaction.response.send_message("❌ No hay usuarios con asistencias registradas")
        return

    # Realizar el reseteo completo
    success = time_tracker.reset_all_attendances()

    if success:
        embed = discord.Embed(
            title="🗑️ ASISTENCIAS RESETEADAS",
            description="Todas las asistencias han sido eliminadas completamente",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="📊 Datos eliminados:",
            value=f"• {user_count} usuarios con asistencias\n"
                  f"• Todas las asistencias diarias\n"
                  f"• Todas las asistencias semanales\n"
                  f"• Todos los totales acumulados\n"
                  f"• Archivo attendance_data.json reiniciado",
            inline=False
        )
        embed.add_field(
            name="✅ Estado actual:",
            value="Sistema de asistencias completamente limpio\n"
                  "Listo para nuevos registros de asistencias\n"
                  "**Nota:** `/paga_cargos` mostrará usuarios sin créditos",
            inline=False
        )
        embed.set_footer(text=f"Ejecutado por {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Error al resetear las asistencias")

@bot.tree.command(name="lista_roles_sistema", description="Ver información sobre todos los roles del sistema")
@is_admin()
async def lista_roles_sistema(interaction: discord.Interaction):
    """Mostrar información sobre los roles específicos del sistema"""
    try:
        embed = discord.Embed(
            title="🎭 Sistema de Roles Específicos",
            description="Información sobre los roles disponibles en el sistema",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        # Ordenar roles por nivel
        roles_ordenados = sorted(ROLES_ESPECIFICOS.items(), key=lambda x: x[1]['nivel'])

        roles_info = ""
        for tipo, info in roles_ordenados:
            roles_info += f"{info['emoji']} **{info['nombre']}** - Nivel {info['nivel']}\n"

        embed.add_field(name="📊 Jerarquía de Roles", value=roles_info, inline=False)

        embed.add_field(
            name="💡 Comandos Disponibles",
            value="• `/dar_cargo_medio` - Asignar rol Medios\n"
                  "• `/dar_cargo_gold` - Asignar rol Gold\n"
                  "• `/dar_cargo_alto` - Asignar rol Altos\n"
                  "• `/dar_cargo_imperial` - Asignar rol Imperiales\n"
                  "• `/dar_cargo_nobleza` - Asignar rol Nobleza\n"
                  "• `/dar_cargo_monarquia` - Asignar rol Monarquía\n"
                  "• `/dar_cargo_supremo` - Asignar rol Supremos\n"
                  "• `/quitar_cargo` - Quitar cualquier rol\n"
                  "• `/ver_roles_usuario` - Ver roles de un usuario\n"
                  "• `/mis_asistencias` - Ver tus propias asistencias\n"
                  "• `/mis_tiempos` - Ver usuarios a quienes has iniciado tiempo (cargos altos)\n"
                  "• `/sumar_asistencias` - Agregar asistencias (solo semanal/total)\n"
                  "• `/agregar_asistencias_diarias` - Agregar asistencias diarias (diario/semanal/total)\n"
                  "• `/ligar_tiempo` - Ligar tiempo de usuario (cargos altos)\n"
                  "• `/desligar_tiempo` - Desligar tiempo de usuario (cargos altos)\n"
                  "• `/resetear_asistencias` - Resetear todas las asistencias",
            inline=False
        )

        embed.add_field(
            name="📋 Sistema de Asistencias",
            value="**Roles con asistencias:** Altos, Imperiales, Nobleza, Monarquía, Supremos\n"
                  "• 1 asistencia por 1 hora completada\n"
                  "• 2 asistencias por 2 horas completadas\n"
                  "• Máximo 3 asistencias por día\n"
                  "• Máximo 15 asistencias por semana\n"
                  "• **Ligado de tiempo:** Los cargos altos pueden ligar tiempos activos",
            inline=False
        )

        embed.add_field(
            name="💰 Créditos por Asistencias Semanales",
            value="**Con 15 asistencias completas:**\n"
                  "🥈 **Altos:** 43 Créditos\n"
                  "👑 **Imperiales:** 48 Créditos\n"
                  "🏰 **Nobleza:** 54 Créditos\n"
                  "👸 **Monarquía:** 60 Créditos\n"
                  "⭐ **Supremos:** 70 Créditos",
            inline=False
        )

        embed.set_footer(text="Todos los comandos requieren permisos de administrador")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error al mostrar información del sistema de roles.",
            ephemeral=True
        )
        print(f"Error mostrando lista de roles: {e}")



@bot.tree.command(name="verificar_permisos", description="Verificar tus permisos actuales")
async def verificar_permisos(interaction: discord.Interaction):
    """Comando para que cualquier usuario verifique sus permisos"""
    try:
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        
        embed = discord.Embed(
            title="🔍 Verificación de Permisos",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Información básica del usuario
        embed.add_field(
            name="👤 Usuario",
            value=f"{interaction.user.mention}\n"
                  f"ID: {interaction.user.id}",
            inline=False
        )
        
        # Verificar permisos de administrador
        is_owner = interaction.guild.owner_id == interaction.user.id if interaction.guild else False
        is_admin = member.guild_permissions.administrator if member else False
        
        admin_status = "❌ No"
        if is_owner:
            admin_status = "✅ Sí (Dueño del servidor)"
        elif is_admin:
            admin_status = "✅ Sí (Administrador)"
        
        embed.add_field(
            name="👑 Permisos de Administrador",
            value=admin_status,
            inline=False
        )
        
        # Verificar rol de permisos de comandos
        config = load_config()
        role_ids = config.get('role_ids', {})
        command_role_id = role_ids.get('command_permission_role_id')
        
        if command_role_id and interaction.guild:
            role = interaction.guild.get_role(command_role_id)
            role_name = role.name if role else f"ID: {command_role_id}"
            
            has_role = member and has_command_permission_role(member)
            role_status = "✅ Sí" if has_role else "❌ No"
            
            embed.add_field(
                name="🎭 Rol de Comandos",
                value=f"**Rol requerido:** {role_name}\n"
                      f"**¿Lo tienes?** {role_status}",
                inline=False
            )
        else:
            embed.add_field(
                name="🎭 Rol de Comandos",
                value="❌ No configurado\n*(Solo administradores pueden usar comandos)*",
                inline=False
            )
        
        # Verificar acceso a comandos
        can_use_commands = is_owner or is_admin or (member and has_command_permission_role(member))
        command_access = "✅ Sí" if can_use_commands else "❌ No"
        
        embed.add_field(
            name="⚡ Acceso a Comandos",
            value=command_access,
            inline=True
        )
        
        # Verificar rol de /mi_tiempo
        mi_tiempo_role_id = role_ids.get('mi_tiempo_role_id')
        if mi_tiempo_role_id and interaction.guild:
            mi_tiempo_role = interaction.guild.get_role(mi_tiempo_role_id)
            mi_tiempo_role_name = mi_tiempo_role.name if mi_tiempo_role else f"ID: {mi_tiempo_role_id}"
            
            has_mi_tiempo = member and can_use_mi_tiempo(member)
            mi_tiempo_status = "✅ Sí" if has_mi_tiempo else "❌ No"
            
            embed.add_field(
                name="⏱️ Comando /mi_tiempo",
                value=f"**Rol requerido:** {mi_tiempo_role_name}\n"
                      f"**¿Lo tienes?** {mi_tiempo_status}",
                inline=False
            )
        
        # Listar roles actuales del usuario
        if member and member.roles:
            user_roles = [role.name for role in member.roles if role.name != "@everyone"]
            if user_roles:
                roles_text = ", ".join(user_roles[:10])  # Limitar a 10 roles
                if len(user_roles) > 10:
                    roles_text += f" y {len(user_roles) - 10} más"
                embed.add_field(
                    name="📝 Tus Roles Actuales",
                    value=roles_text,
                    inline=False
                )
        
        embed.set_footer(text="Verifica tus permisos cuando tengas dudas")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error verificando permisos: {e}",
            ephemeral=True
        )

# =================== COMANDOS DE PAGO POR ROLES ===================

class PaymentView(discord.ui.View):
    def __init__(self, filtered_users, role_name, guild, search_term=None):
        super().__init__(timeout=300)
        self.filtered_users = filtered_users
        self.role_name = role_name
        self.guild = guild
        self.search_term = search_term
        self.current_page = 0
        self.max_per_page = 15
        self.total_pages = (len(filtered_users) + self.max_per_page - 1) // self.max_per_page if filtered_users else 1

        # Deshabilitar botones si solo hay una página
        if self.total_pages <= 1:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.label in ['◀️ Anterior', '▶️ Siguiente']:
                    item.disabled = True

    def get_embed(self):
        """Crear embed para la página actual"""
        start_idx = self.current_page * self.max_per_page
        end_idx = min(start_idx + self.max_per_page, len(self.filtered_users))
        current_users = self.filtered_users[start_idx:end_idx]

        # Determinar emoji según el rol
        role_emoji = "👤"
        if "Medios" in self.role_name:
            role_emoji = "🥉"
        elif "Gold" in self.role_name:
            role_emoji = "🏆"
        elif "Cargos Altos" in self.role_name:
            role_emoji = "⭐"

        title = f"{role_emoji} Pago - {self.role_name}"
        if self.search_term:
            title += f" (Búsqueda: '{self.search_term}')"

        embed = discord.Embed(
            title=title,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )

        if not current_users:
            embed.description = f"No se encontraron usuarios para {self.role_name}"
            if self.search_term:
                embed.description += f" con el término '{self.search_term}'"
            embed.set_footer(text="No hay datos para mostrar")
            return embed

        user_list = []
        total_credits = 0

        for user_data in current_users:
            try:
                user_id = user_data['user_id']
                member = self.guild.get_member(user_id) if self.guild else None
                
                if member:
                    user_mention = member.mention
                else:
                    user_name = user_data.get('name', f'Usuario {user_id}')
                    user_mention = f"**{user_name}** `(ID: {user_id})`"

                total_time = user_data['total_time']
                formatted_time = time_tracker.format_time_human(total_time)
                credits = user_data['credits']
                total_credits += credits

                # Determinar estado
                data = user_data.get('data', {})
                status = "🔴 Inactivo"
                if data.get('is_active', False):
                    status = "🟢 Activo"
                elif data.get('is_paused', False):
                    total_hours = total_time / 3600
                    if (data.get("milestone_completed", False) or 
                        (user_data.get('has_special_role', False) and total_hours >= 4.0) or 
                        (not user_data.get('has_special_role', False) and total_hours >= 2.0)):
                        status = "✅ Terminado"
                    else:
                        status = "⏸️ Pausado"

                user_list.append(f"📌 {user_mention} - ⏱️ {formatted_time} - 💰 {credits} Créditos {status}")

            except Exception as e:
                print(f"Error procesando usuario en pago: {e}")
                continue

        embed.description = "\n".join(user_list)
        
        # Información del resumen
        embed.add_field(
            name="📊 Resumen de Página",
            value=f"Usuarios: {len(current_users)}\nCréditos en página: {total_credits}",
            inline=True
        )

        # Calcular totales generales
        total_users = len(self.filtered_users)
        total_all_credits = sum(user['credits'] for user in self.filtered_users)
        
        embed.add_field(
            name="🎯 Total General",
            value=f"Usuarios: {total_users}\nCréditos totales: {total_all_credits}",
            inline=True
        )

        embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} • {total_users} usuarios en total")
        return embed

    @discord.ui.button(label='◀️ Anterior', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='▶️ Siguiente', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='🔍 Buscar Usuario', style=discord.ButtonStyle.primary)
    async def search_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchUserModal(self)
        await interaction.response.send_modal(modal)

    def update_buttons(self):
        """Actualizar estado de los botones"""
        self.children[0].disabled = (self.current_page == 0)  # Anterior
        self.children[1].disabled = (self.current_page >= self.total_pages - 1)  # Siguiente

    async def on_timeout(self):
        """Deshabilitar botones cuando expire"""
        for item in self.children:
            item.disabled = True

class SearchUserModal(discord.ui.Modal, title='Buscar Usuario'):
    def __init__(self, payment_view):
        super().__init__()
        self.payment_view = payment_view

    search_term = discord.ui.TextInput(
        label='Nombre del usuario',
        placeholder='Escribe parte del nombre del usuario...',
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        search_term = self.search_term.value.lower().strip()
        
        # Filtrar usuarios que coincidan con el término de búsqueda
        matching_users = []
        for user_data in self.payment_view.filtered_users:
            user_name = user_data.get('name', '').lower()
            if search_term in user_name:
                matching_users.append(user_data)

        if not matching_users:
            await interaction.response.send_message(
                f"❌ No se encontraron usuarios con '{self.search_term.value}' en {self.payment_view.role_name}",
                ephemeral=True
            )
            return

        # Crear nueva vista con resultados filtrados
        new_view = PaymentView(matching_users, self.payment_view.role_name, self.payment_view.guild, search_term)
        embed = new_view.get_embed()
        
        await interaction.response.edit_message(embed=embed, view=new_view)

def get_users_by_role_filter(role_filter_func, role_name: str, interaction: discord.Interaction):
    """Función auxiliar para obtener usuarios filtrados por rol"""
    try:
        tracked_users = time_tracker.get_all_tracked_users()
        filtered_users = []

        for user_id_str, data in tracked_users.items():
            try:
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id) if interaction.guild else None
                
                # Aplicar filtro de rol
                if not role_filter_func(member, data):
                    continue

                total_time = time_tracker.get_total_time(user_id)
                
                # Solo incluir usuarios con tiempo > 0
                if total_time <= 0:
                    continue

                # Determinar tipo de rol para calcular créditos
                if member:
                    role_type = get_user_role_type(member)
                    has_special_role = has_unlimited_time_role(member)
                else:
                    role_type = "normal"
                    has_special_role = False

                # Calcular créditos
                credits = calculate_credits(total_time, role_type)

                user_info = {
                    'user_id': user_id,
                    'name': data.get('name', f'Usuario {user_id}'),
                    'total_time': total_time,
                    'credits': credits,
                    'role_type': role_type,
                    'has_special_role': has_special_role,
                    'data': data
                }
                
                filtered_users.append(user_info)

            except Exception as e:
                print(f"Error procesando usuario {user_id_str}: {e}")
                continue

        # Ordenar por nombre
        filtered_users.sort(key=lambda x: x['name'].lower())
        return filtered_users

    except Exception as e:
        print(f"Error en get_users_by_role_filter: {e}")
        return []

@bot.tree.command(name="paga_recluta", description="Ver usuarios sin rol específico con sus horas y créditos")
@is_admin()
async def paga_recluta(interaction: discord.Interaction):
    """Mostrar usuarios sin rol específico (normales) con sus créditos"""
    await interaction.response.defer()

    def filter_normal_users(member, data):
        """Filtrar usuarios sin rol específico"""
        if not member:
            return True  # Usuarios no en servidor se consideran normales
        
        role_type = get_user_role_type(member)
        return role_type == "normal"

    filtered_users = get_users_by_role_filter(filter_normal_users, "Reclutas (Sin Rol)", interaction)
    
    if not filtered_users:
        await interaction.followup.send("❌ No se encontraron reclutas con tiempo registrado")
        return

    view = PaymentView(filtered_users, "Reclutas (Sin Rol)", interaction.guild)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="paga_medios", description="Ver usuarios con rol Medios con sus horas y créditos")
@is_admin()
async def paga_medios(interaction: discord.Interaction):
    """Mostrar usuarios con rol Medios con sus créditos"""
    await interaction.response.defer()

    # Obtener ID del rol desde config.json
    config = load_config()
    role_ids = config.get('role_ids', {})
    medios_role_id = role_ids.get('medios_role_id', 1357521784395665525)

    def filter_medios_users(member, data):
        """Filtrar usuarios con rol Medios"""
        if not member:
            return False
        
        # Verificar por ID específico del rol
        for role in member.roles:
            if role.id == medios_role_id:
                return True
        
        # Verificar por nombre del rol como respaldo
        role_type = get_user_role_type(member)
        return role_type == "medios"

    filtered_users = get_users_by_role_filter(filter_medios_users, "Medios", interaction)
    
    if not filtered_users:
        await interaction.followup.send("❌ No se encontraron usuarios con rol Medios con tiempo registrado")
        return

    view = PaymentView(filtered_users, "Medios", interaction.guild)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="paga_gold", description="Ver usuarios con rol Gold con sus horas y créditos")
@is_admin()
async def paga_gold(interaction: discord.Interaction):
    """Mostrar usuarios con rol Gold con sus créditos"""
    await interaction.response.defer()

    # Obtener ID del rol desde config.json
    config = load_config()
    role_ids = config.get('role_ids', {})
    gold_role_id = role_ids.get('gold_role_id', 1387196609967816948)

    def filter_gold_users(member, data):
        """Filtrar usuarios con rol Gold"""
        if not member:
            return False
        
        # Verificar por ID específico del rol
        for role in member.roles:
            if role.id == gold_role_id:
                return True
        
        # Verificar por nombre del rol como respaldo
        role_type = get_user_role_type(member)
        return role_type == "gold"

    filtered_users = get_users_by_role_filter(filter_gold_users, "Gold", interaction)
    
    if not filtered_users:
        await interaction.followup.send("❌ No se encontraron usuarios con rol Gold con tiempo registrado")
        return

    view = PaymentView(filtered_users, "Gold", interaction.guild)
    embed = view.get_embed()
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="paga_cargos", description="Ver usuarios con cargos altos (Altos hasta Supremos) con sus créditos")
@is_admin()
async def paga_cargos(interaction: discord.Interaction):
    """Mostrar usuarios con cargos altos con sus asistencias y créditos"""
    await interaction.response.defer()

    def filter_high_rank_users(member, data):
        """Filtrar usuarios con cargos altos"""
        if not member:
            return False
        
        role_type = get_user_role_type(member)
        return role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]

    # Obtener usuarios con cargos altos
    try:
        tracked_users = time_tracker.get_all_tracked_users()
        filtered_users = []

        for user_id_str, data in tracked_users.items():
            try:
                user_id = int(user_id_str)
                member = interaction.guild.get_member(user_id) if interaction.guild else None
                
                # Aplicar filtro de rol
                if not filter_high_rank_users(member, data):
                    continue

                total_time = time_tracker.get_total_time(user_id)
                
                # Incluir usuarios con cargos altos aunque no tengan tiempo
                # porque reciben créditos por asistencias
                role_type = get_user_role_type(member)
                
                # Para cargos altos, los créditos vienen de asistencias, no de tiempo
                attendance_info = time_tracker.get_attendance_info(user_id)
                
                # Calcular créditos por asistencias según el rol
                weekly_credits = 0
                if role_type == "altos":
                    weekly_credits = 43
                elif role_type == "imperiales":
                    weekly_credits = 48
                elif role_type == "nobleza":
                    weekly_credits = 54
                elif role_type == "monarquia":
                    weekly_credits = 60
                elif role_type == "supremos":
                    weekly_credits = 70

                # Calcular créditos totales basado en asistencias
                if weekly_credits > 0:
                    complete_weeks = attendance_info['total'] // 15
                    remaining_attendances = attendance_info['total'] % 15
                    total_credits_earned = (complete_weeks * weekly_credits) + int((remaining_attendances / 15) * weekly_credits)
                else:
                    total_credits_earned = 0

                user_info = {
                    'user_id': user_id,
                    'name': data.get('name', f'Usuario {user_id}'),
                    'total_time': total_time,
                    'credits': total_credits_earned,
                    'role_type': role_type,
                    'has_special_role': has_unlimited_time_role(member),
                    'data': data,
                    'attendance_info': attendance_info,
                    'weekly_credits': weekly_credits
                }
                
                filtered_users.append(user_info)

            except Exception as e:
                print(f"Error procesando usuario de cargo alto {user_id_str}: {e}")
                continue

        # Ordenar por nombre
        filtered_users.sort(key=lambda x: x['name'].lower())

        if not filtered_users:
            await interaction.followup.send("❌ No se encontraron usuarios con cargos altos registrados")
            return

        # Usar vista especial para cargos altos
        view = HighRankPaymentView(filtered_users, "Cargos Altos", interaction.guild)
        embed = view.get_embed()
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        print(f"Error en paga_cargos: {e}")
        await interaction.followup.send("❌ Error al obtener información de cargos altos")

class HighRankPaymentView(PaymentView):
    """Vista especializada para cargos altos que muestra asistencias"""
    
    def get_embed(self):
        """Embed especializado para cargos altos con asistencias"""
        start_idx = self.current_page * self.max_per_page
        end_idx = min(start_idx + self.max_per_page, len(self.filtered_users))
        current_users = self.filtered_users[start_idx:end_idx]

        title = f"⭐ Pago - Cargos Altos"
        if self.search_term:
            title += f" (Búsqueda: '{self.search_term}')"

        embed = discord.Embed(
            title=title,
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )

        if not current_users:
            embed.description = f"No se encontraron usuarios con cargos altos"
            if self.search_term:
                embed.description += f" con el término '{self.search_term}'"
            embed.set_footer(text="No hay datos para mostrar")
            return embed

        user_list = []
        total_credits = 0
        total_attendances = 0

        for user_data in current_users:
            try:
                user_id = user_data['user_id']
                member = self.guild.get_member(user_id) if self.guild else None
                
                if member:
                    user_mention = member.mention
                    role_info = get_role_info(member)
                else:
                    user_name = user_data.get('name', f'Usuario {user_id}')
                    user_mention = f"**{user_name}** `(ID: {user_id})`"
                    role_info = f" ({user_data['role_type'].capitalize()})"

                total_time = user_data['total_time']
                formatted_time = time_tracker.format_time_human(total_time)
                credits = user_data['credits']
                attendance_info = user_data['attendance_info']
                
                total_credits += credits
                total_attendances += attendance_info['total']

                # Información de asistencias
                attendance_text = f"📋 {attendance_info['total']} Asist"
                
                user_list.append(f"📌 {user_mention}{role_info} - {attendance_text} - 💰 {credits} Créditos")

            except Exception as e:
                print(f"Error procesando usuario de cargo alto: {e}")
                continue

        embed.description = "\n".join(user_list)
        
        # Información del resumen
        embed.add_field(
            name="📊 Resumen de Página",
            value=f"Usuarios: {len(current_users)}\nAsistencias: {total_attendances}\nCréditos: {total_credits}",
            inline=True
        )

        # Calcular totales generales
        total_users = len(self.filtered_users)
        total_all_credits = sum(user['credits'] for user in self.filtered_users)
        total_all_attendances = sum(user['attendance_info']['total'] for user in self.filtered_users)
        
        embed.add_field(
            name="🎯 Total General",
            value=f"Usuarios: {total_users}\nAsistencias: {total_all_attendances}\nCréditos: {total_all_credits}",
            inline=True
        )

        embed.add_field(
            name="ℹ️ Sistema de Créditos",
            value="Los cargos altos reciben créditos por asistencias:\n"
                  "• Altos: 43 créditos/15 asistencias\n"
                  "• Imperiales: 48 créditos/15 asistencias\n"
                  "• Nobleza: 54 créditos/15 asistencias\n"
                  "• Monarquía: 60 créditos/15 asistencias\n"
                  "• Supremos: 70 créditos/15 asistencias",
            inline=False
        )

        embed.set_footer(text=f"Página {self.current_page + 1}/{self.total_pages} • {total_users} usuarios en total")
        return embed

@bot.tree.command(name="ligar_tiempo", description="Ligar el tiempo de un usuario para que las asistencias vayan a ti")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo será ligado a ti")
@is_admin()
async def ligar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    """Ligar el tiempo de un usuario a quien ejecuta el comando"""
    try:
        # Verificar que no sea un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se puede ligar el tiempo de bots", ephemeral=True)
            return

        # Verificar que no se ligue a sí mismo
        if usuario.id == interaction.user.id:
            await interaction.response.send_message("❌ No puedes ligar tu propio tiempo", ephemeral=True)
            return

        # Verificar que el usuario ejecutor tenga cargo alto
        executor = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if not executor or not has_attendance_role(executor):
            role_info = get_role_info(executor) if executor else ""
            await interaction.response.send_message(
                f"❌ Solo los cargos altos pueden ligar tiempos.\n"
                f"**Roles permitidos:** Altos, Imperiales, Nobleza, Monarquía, Supremos\n"
                f"**Tu rol actual:**{role_info if role_info else ' Sin cargo alto'}",
                ephemeral=True
            )
            return

        # Verificar que el usuario tenga tiempo registrado
        user_data = time_tracker.get_user_data(usuario.id)
        if not user_data:
            await interaction.response.send_message(
                f"❌ {usuario.mention} no tiene tiempo registrado",
                ephemeral=True
            )
            return

        # Verificar que el tiempo NO esté terminado
        total_time = time_tracker.get_total_time(usuario.id)
        total_hours = total_time / 3600
        has_special_role = has_unlimited_time_role(usuario)
        
        # Verificar si está terminado
        is_finished = False
        if user_data.get("milestone_completed", False):
            is_finished = True
        elif has_special_role and total_hours >= 4.0:
            is_finished = True
        elif not has_special_role and total_hours >= 2.0:
            is_finished = True

        if is_finished:
            formatted_time = time_tracker.format_time_human(total_time)
            await interaction.response.send_message(
                f"❌ No se puede ligar el tiempo de {usuario.mention} porque ya está **TERMINADO**\n"
                f"⏱️ Tiempo completado: {formatted_time}\n"
                f"💡 Solo se pueden ligar tiempos activos o pausados (no terminados)",
                ephemeral=True
            )
            return

        # Verificar que el tiempo esté activo
        if not user_data.get('is_active', False):
            await interaction.response.send_message(
                f"❌ {usuario.mention} no tiene tiempo activo para ligar\n"
                f"💡 Solo se pueden ligar tiempos que estén corriendo actualmente",
                ephemeral=True
            )
            return

        # Verificar si ya está ligado
        if time_tracker.is_time_linked(usuario.id):
            linked_info = time_tracker.get_linked_user(usuario.id)
            if linked_info:
                await interaction.response.send_message(
                    f"❌ El tiempo de {usuario.mention} ya está ligado a **{linked_info['admin_name']}**\n"
                    f"💡 Usa `/desligar_tiempo` primero para cambiar el ligado",
                    ephemeral=True
                )
                return

        # Intentar ligar el tiempo
        success = time_tracker.link_time_to_user(usuario.id, interaction.user.id, interaction.user.display_name)
        
        if success:
            # Respuesta del comando
            await interaction.response.send_message(
                f"🔗 {interaction.user.mention} ha ligado el tiempo de {usuario.mention}"
            )

            # Enviar notificación al canal de asistencias
            await send_link_notification(interaction.user, usuario, "ligado")

            print(f"✅ Tiempo ligado: {usuario.display_name} -> {interaction.user.display_name}")
        else:
            await interaction.response.send_message(
                f"❌ Error al ligar el tiempo de {usuario.mention}",
                ephemeral=True
            )

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al ligar tiempo. Intenta de nuevo.",
            ephemeral=True
        )
        print(f"Error en ligar_tiempo: {e}")

@bot.tree.command(name="desligar_tiempo", description="Desligar el tiempo de un usuario")
@discord.app_commands.describe(usuario="El usuario cuyo tiempo será desligado")
@is_admin()
async def desligar_tiempo(interaction: discord.Interaction, usuario: discord.Member):
    """Desligar el tiempo de un usuario"""
    try:
        # Verificar que no sea un bot
        if usuario.bot:
            await interaction.response.send_message("❌ No se puede desligar el tiempo de bots", ephemeral=True)
            return

        # Verificar que el usuario ejecutor tenga cargo alto
        executor = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        if not executor or not has_attendance_role(executor):
            role_info = get_role_info(executor) if executor else ""
            await interaction.response.send_message(
                f"❌ Solo los cargos altos pueden desligar tiempos.\n"
                f"**Roles permitidos:** Altos, Imperiales, Nobleza, Monarquía, Supremos\n"
                f"**Tu rol actual:**{role_info if role_info else ' Sin cargo alto'}",
                ephemeral=True
            )
            return

        # Verificar que el tiempo esté ligado
        if not time_tracker.is_time_linked(usuario.id):
            await interaction.response.send_message(
                f"❌ El tiempo de {usuario.mention} no está ligado",
                ephemeral=True
            )
            return

        # Intentar desligar el tiempo
        success = time_tracker.unlink_time(usuario.id)
        
        if success:
            # Respuesta del comando
            await interaction.response.send_message(
                f"🔓 {interaction.user.mention} ha desligado el tiempo de {usuario.mention}"
            )

            # Enviar notificación al canal de asistencias
            await send_link_notification(interaction.user, usuario, "desligado")

            print(f"✅ Tiempo desligado: {usuario.display_name} por {interaction.user.display_name}")
        else:
            await interaction.response.send_message(
                f"❌ Error al desligar el tiempo de {usuario.mention}",
                ephemeral=True
            )

    except Exception as e:
        await interaction.response.send_message(
            "❌ Error inesperado al desligar tiempo. Intenta de nuevo.",
            ephemeral=True
        )
        print(f"Error en desligar_tiempo: {e}")

async def send_link_notification(admin_member: discord.Member, user_member: discord.Member, action: str):
    """Enviar notificación de ligado/desligado al canal de asistencias"""
    try:
        channel = bot.get_channel(ATTENDANCE_NOTIFICATION_CHANNEL_ID)
        if channel:
            admin_role = get_role_info(admin_member)
            
            if action == "ligado":
                message = (f"🔗 **TIEMPO LIGADO**\n"
                          f"{admin_member.mention}{admin_role} ha **ligado** el tiempo de {user_member.mention}\n"
                          f"💡 Las asistencias de {user_member.mention} ahora irán para {admin_member.mention}")
            else:  # desligado
                message = (f"🔓 **TIEMPO DESLIGADO**\n"
                          f"{admin_member.mention}{admin_role} ha **desligado** el tiempo de {user_member.mention}\n"
                          f"💡 Las asistencias de {user_member.mention} vuelven a la normalidad")

            await channel.send(message)
            print(f"✅ Notificación de {action} enviada: {admin_member.display_name} -> {user_member.display_name}")
    except Exception as e:
        print(f"Error enviando notificación de {action}: {e}")

async def send_auto_link_notification(admin_member: discord.Member, user_member: discord.Member, current_time: str):
    """Enviar notificación de auto-ligado por cargo alto"""
    try:
        channel = bot.get_channel(ATTENDANCE_NOTIFICATION_CHANNEL_ID)
        if channel:
            admin_role = get_role_info(admin_member)
            
            message = (f"🔗 **TIEMPO AUTO-LIGADO** (Cargo Alto)\n"
                      f"{admin_member.mention}{admin_role} inició el tiempo de {user_member.mention} a las **{current_time}** (Colombia)\n"
                      f"⚡ **Auto-ligado activado:** Las asistencias de {user_member.mention} irán para {admin_member.mention}\n"
                      f"💡 Usa `/desligar_tiempo` si necesitas cambiar esto")

            await channel.send(message)
            print(f"✅ Notificación de auto-ligado enviada: {admin_member.display_name} -> {user_member.display_name} ({current_time} Colombia)")
    except Exception as e:
        print(f"Error enviando notificación de auto-ligado: {e}")

@bot.tree.command(name="diagnostico_bot", description="Verificar estado del bot y comandos")
@is_admin()
async def diagnostico_bot(interaction: discord.Interaction):
    """Comando para diagnosticar el estado del bot"""
    try:
        embed = discord.Embed(
            title="🔧 Diagnóstico del Bot",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Información básica del bot
        embed.add_field(
            name="🤖 Estado del Bot",
            value=f"✅ Conectado como {bot.user.name}\n"
                  f"📡 Latencia: {round(bot.latency * 1000)}ms\n"
                  f"🔗 Guilds conectados: {len(bot.guilds)}",
            inline=False
        )

        # Comandos registrados
        commands = [cmd.name for cmd in bot.tree.get_commands()]
        embed.add_field(
            name="📋 Comandos Registrados",
            value=f"Total: {len(commands)} comandos\n"
                  f"Principales: iniciar_tiempo, ver_tiempos, mi_tiempo",
            inline=False
        )

        # Información del servidor actual
        if interaction.guild:
            embed.add_field(
                name="🏠 Servidor Actual",
                value=f"Nombre: {interaction.guild.name}\n"
                      f"ID: {interaction.guild.id}\n"
                      f"Miembros: {interaction.guild.member_count}",
                inline=False
            )

        # Permisos del bot
        if interaction.guild:
            bot_member = interaction.guild.get_member(bot.user.id)
            if bot_member:
                perms = bot_member.guild_permissions
                embed.add_field(
                    name="🔐 Permisos Importantes",
                    value=f"Administrador: {'✅' if perms.administrator else '❌'}\n"
                          f"Usar comandos slash: {'✅' if perms.use_slash_commands else '❌'}\n"
                          f"Enviar mensajes: {'✅' if perms.send_messages else '❌'}",
                    inline=False
                )

        embed.add_field(
            name="💡 Solución a 'Integración desconocida'",
            value="1. Espera 1-5 minutos\n"
                  "2. Reinicia Discord\n"
                  "3. Verifica permisos del bot\n"
                  "4. Usa este comando para re-sincronizar",
            inline=False
        )

        await interaction.response.send_message(embed=embed)

        # Intentar re-sincronizar comandos
        try:
            synced = await bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(
                f"🔄 Re-sincronizados {len(synced)} comandos en este servidor",
                ephemeral=True
            )
        except Exception as sync_error:
            await interaction.followup.send(
                f"⚠️ Error re-sincronizando: {sync_error}",
                ephemeral=True
            )

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error en diagnóstico: {e}",
            ephemeral=True
        )

@bot.tree.command(name="mi_tiempo", description="Ver tu propio tiempo acumulado")
@check_mi_tiempo_permission()
async def mi_tiempo(interaction: discord.Interaction):
    # El decorator ya verificó los permisos, por lo que este código es seguro ejecutar
    member = interaction.guild.get_member(interaction.user.id)

    user_data = time_tracker.get_user_data(interaction.user.id)

    if not user_data:
        await interaction.response.send_message("❌ No tienes tiempo registrado aún")
        return

    total_time = time_tracker.get_total_time(interaction.user.id)
    formatted_time = time_tracker.format_time_human(total_time)

    embed = discord.Embed(
        title=f"⏱️ Tu Tiempo Acumulado",
        color=discord.Color.from_rgb(255, 215, 0),
        timestamp=datetime.now()
    )

    # Usar formato humano detallado para /mi_tiempo
    formatted_time = time_tracker.format_time_human(total_time)
    embed.add_field(name="⏱️ Tiempo Total", value=formatted_time, inline=True)

    # Verificar si el usuario tiene rol especial (ya tenemos el member object)
    has_special_role = has_unlimited_time_role(member)

    status = "🟢 Activo" if user_data.get('is_active', False) else "🔴 Inactivo"
    if user_data.get('is_paused', False):
        total_hours = total_time / 3600
        # Verificar si completó milestone y debe mostrar como "Terminado"
        if user_data.get("milestone_completed", False) or (has_special_role and total_hours >= 4.0) or (not has_special_role and total_hours >= 2.0):
            status = "✅ Terminado"
        else:
            status = "⏸️ Pausado"

    embed.add_field(name="📍 Estado", value=status, inline=True)

    # Calcular y mostrar créditos
    role_type = get_user_role_type(member)
    credits = calculate_credits(total_time, role_type)
    
    if role_type in ["altos", "imperiales", "nobleza", "monarquia", "supremos"]:
        # Para cargos altos y superiores, mostrar que ganan créditos por asistencias, no por tiempo
        embed.add_field(
            name="💰 Créditos por Tiempo", 
            value="No aplica - Ganas créditos por asistencias", 
            inline=True
        )
        embed.add_field(
            name="📋 Asistencias", 
            value="Usa `/mis_asistencias` para ver tus créditos", 
            inline=True
        )
    elif credits > 0:
        embed.add_field(name="💰 Créditos", value=f"{credits} créditos", inline=True)



    if user_data.get('last_start'):
        last_start = datetime.fromisoformat(user_data['last_start'])
        embed.add_field(
            name="🕐 Última Sesión Iniciada",
            value=last_start.strftime("%d/%m/%Y %H:%M:%S"),
            inline=False
        )

    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
    embed.set_footer(text="Consulta tu tiempo cuando quieras")

    await interaction.response.send_message(embed=embed)

def check_high_rank_permission():
    """Decorator para verificar si el usuario tiene cargo alto (Altos hasta Supremos)"""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            if not hasattr(interaction, 'guild') or not interaction.guild:
                return False

            member = interaction.guild.get_member(interaction.user.id)
            if not member:
                return False

            # Verificar si tiene cargo alto
            return has_attendance_role(member)

        except Exception as e:
            print(f"Error en verificación de permisos cargo alto: {e}")
            return False

    return discord.app_commands.check(predicate)

@bot.tree.command(name="mis_tiempos", description="Ver la lista de usuarios a quienes has iniciado tiempo (solo cargos altos)")
@check_high_rank_permission()
async def mis_tiempos(interaction: discord.Interaction):
    """Ver lista de usuarios a quienes el admin ha iniciado tiempo"""
    try:
        # Obtener usuarios iniciados por este admin
        initiated_users = time_tracker.get_users_initiated_by_admin(interaction.user.id)
        
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        role_info = get_role_info(member) if member else ""
        
        embed = discord.Embed(
            title="⏱️ Tus Tiempos Iniciados",
            description="Estos son los usuarios a quienes has iniciado tiempo:",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        if not initiated_users:
            embed.add_field(
                name="📝 Sin tiempos iniciados",
                value="No has iniciado tiempo a ningún usuario aún.\n"
                      "Usa `/iniciar_tiempo @usuario` para comenzar a rastrear tiempo.",
                inline=False
            )
        else:
            # Separar usuarios por estado
            active_users = []
            paused_users = []
            finished_users = []
            
            for user_info in initiated_users:
                total_hours = user_info['total_time'] / 3600
                formatted_time = time_tracker.format_time_human(user_info['total_time'])
                
                user_entry = f"📌 **{user_info['name']}** - ⏱️ {formatted_time}"
                
                if user_info['is_active']:
                    user_entry += " 🟢 Activo"
                    active_users.append(user_entry)
                elif user_info['is_paused']:
                    if user_info['milestone_completed'] or total_hours >= 2.0:
                        user_entry += " ✅ Terminado"
                        finished_users.append(user_entry)
                    else:
                        user_entry += " ⏸️ Pausado"
                        paused_users.append(user_entry)
                else:
                    user_entry += " ✅ Terminado"
                    finished_users.append(user_entry)
            
            # Mostrar usuarios activos
            if active_users:
                embed.add_field(
                    name="🟢 Usuarios Activos",
                    value="\n".join(active_users[:10]),  # Limitar a 10 para evitar overflow
                    inline=False
                )
            
            # Mostrar usuarios pausados
            if paused_users:
                embed.add_field(
                    name="⏸️ Usuarios Pausados",
                    value="\n".join(paused_users[:10]),
                    inline=False
                )
            
            # Mostrar usuarios terminados
            if finished_users:
                embed.add_field(
                    name="✅ Usuarios Terminados",
                    value="\n".join(finished_users[:10]),
                    inline=False
                )
            
            # Resumen
            total_count = len(initiated_users)
            embed.add_field(
                name="📊 Resumen",
                value=f"**Total usuarios:** {total_count}\n"
                      f"🟢 Activos: {len(active_users)}\n"
                      f"⏸️ Pausados: {len(paused_users)}\n"
                      f"✅ Terminados: {len(finished_users)}",
                inline=True
            )
            
            if total_count > 30:  # Si hay muchos usuarios, mostrar nota
                embed.add_field(
                    name="ℹ️ Nota",
                    value=f"Mostrando primeros 30 de {total_count} usuarios",
                    inline=True
                )
        
        embed.add_field(
            name="👤 Cargo",
            value=f"{interaction.user.display_name}{role_info}",
            inline=False
        )
        
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
        embed.set_footer(text="Solo cargos altos pueden ver esta información")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(
            "❌ Error al obtener la lista de tiempos iniciados.",
            ephemeral=True
        )
        print(f"Error en mis_tiempos: {e}")





# =================== COMANDOS ANTI AUSENTE ===================

def get_discord_token():
    """Obtener token de Discord de forma segura desde config.json o variables de entorno"""
    # Intentar obtener desde config.json primero
    if config and config.get('discord_bot_token'):
        token = config.get('discord_bot_token')
        if token and isinstance(token, str) and token.strip():
            print("✅ Token cargado desde config.json")
            return token.strip()

    # Si no está en config.json, intentar desde variables de entorno
    env_token = os.getenv('DISCORD_BOT_TOKEN')
    if env_token and isinstance(env_token, str) and env_token.strip():
        print("✅ Token cargado desde variables de entorno")
        return env_token.strip()

    # Si no se encuentra en ningún lado
    print("❌ Error: No se encontró el token de Discord")
    print("┌─ Configura tu token de Discord de una de estas formas:")
    print("│")
    print("│ OPCIÓN 1 (Recomendado): En config.json")
    print("│ Edita config.json y cambia:")
    print('│ "discord_bot_token": "tu_token_aqui"')
    print("│")
    print("│ OPCIÓN 2: Variable de entorno")
    print("│ export DISCORD_BOT_TOKEN='tu_token_aqui'")
    print("└─")
    return None

# Manejo global de errores para el bot
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    try:
        # Información para debugging
        command_name = interaction.command.name if interaction.command else 'desconocido'
        print(f"Error en comando /{command_name}: {type(error).__name__}")

        # Verificar si la interacción ya expiró antes de intentar responder
        if isinstance(error, discord.app_commands.CommandInvokeError):
            original_error = error.original if hasattr(error, 'original') else error

            # Si es un error de interacción expirada, no intentar responder
            if isinstance(original_error, discord.NotFound) and "10062" in str(original_error):
                print(f"⚠️ Interacción /{command_name} expirada (10062) - no respondiendo")
                return
            elif "Unknown interaction" in str(original_error):
                print(f"⚠️ Interacción /{command_name} desconocida - no respondiendo")
                return

        # Determinar mensaje de error apropiado
        if isinstance(error, discord.app_commands.CheckFailure):
            error_msg = "❌ No tienes permisos para usar este comando."
        elif isinstance(error, discord.app_commands.CommandInvokeError):
            error_msg = "❌ Error interno del comando. El administrador ha sido notificado."
        elif isinstance(error, discord.app_commands.TransformerError):
            error_msg = "❌ Error en los parámetros. Verifica los valores ingresados."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            error_msg = f"⏰ Comando en cooldown. Intenta de nuevo en {error.retry_after:.1f}s"
        else:
            error_msg = "❌ Error inesperado. Intenta de nuevo."

        # Intentar responder de forma muy segura
        try:
            # Solo intentar responder si la interacción no está completa
            if not interaction.response.is_done():
                await asyncio.wait_for(
                    interaction.response.send_message(error_msg, ephemeral=True),
                    timeout=2.0  # Timeout de 2 segundos
                )
            else:
                await asyncio.wait_for(
                    interaction.followup.send(error_msg, ephemeral=True),
                    timeout=2.0
                )
        except asyncio.TimeoutError:
            print(f"⚠️ Timeout respondiendo a error en /{command_name}")
        except discord.NotFound:
            print(f"⚠️ Interacción /{command_name} no encontrada al responder error")
        except discord.HTTPException as e:
            if "10062" not in str(e):  # No login str(e):  # No logear errores de interacción expirada
                print(f"⚠️ Error HTTP respondiendo a /{command_name}: {e}")
        except Exception as e:
            print(f"⚠️ Error inesperado respondiendo a /{command_name}: {e}")

    except Exception as e:
        print(f"❌ Error crítico en manejo global de errores: {e}")

# Manejo específico de errores para comandos con @is_admin()
@iniciar_tiempo.error
@pausar_tiempo.error
@despausar_tiempo.error
@sumar_minutos.error
@restar_minutos.error
@ver_tiempos.error
@reiniciar_tiempo.error
@reiniciar_todos_tiempos.error
@cancelar_tiempo.error
@saber_tiempo_admin.error
@dar_cargo_medio.error
@dar_cargo_alto.error
@dar_cargo_imperial.error
@dar_cargo_nobleza.error
@dar_cargo_monarquia.error
@dar_cargo_supremo.error
@quitar_cargo.error
@ver_roles_usuario.error
@lista_roles_sistema.error
async def admin_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    # Solo manejar errores de permisos específicamente, dejar que el manejo global se encargue del resto
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                # Obtener información del usuario para mensaje más específico
                config = load_config()
                command_role_id = config.get('command_permission_role_id')
                
                if command_role_id:
                    # Buscar el nombre del rol
                    role_name = "rol configurado"
                    if interaction.guild:
                        role = interaction.guild.get_role(command_role_id)
                        if role:
                            role_name = role.name
                    
                    message = (f"❌ **Sin permisos suficientes**\n\n"
                              f"Para usar este comando necesitas:\n"
                              f"• Ser **administrador** del servidor, O\n"
                              f"• Tener el rol **{role_name}**\n\n"
                              f"**Tu situación:**\n"
                              f"• No eres administrador\n"
                              f"• No tienes el rol requerido")
                else:
                    message = (f"❌ **Sin permisos suficientes**\n\n"
                              f"Para usar este comando necesitas:\n"
                              f"• Ser **administrador** del servidor\n\n"
                              f"*(No hay rol de permisos configurado)*")
                
                await interaction.response.send_message(message, ephemeral=True)
        except discord.NotFound:
            pass  # Interacción expirada, ignorar
        except Exception:
            pass  # Cualquier otro error, ignorar para evitar loops
    # Para otros errores, dejar que el manejo global se encargue

#Agrego manejador de error para el comando mi_tiempo
@mis_asistencias.error
async def mis_asistencias_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ No tienes permisos para usar este comando.",
                    ephemeral=True
                )
        except discord.NotFound:
            pass
        except Exception:
            pass

@mis_tiempos.error
async def mis_tiempos_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
                role_info = get_role_info(member) if member else ""
                await interaction.response.send_message(
                    f"❌ **Solo cargos altos pueden usar este comando**\n\n"
                    f"**Roles permitidos:** Altos, Imperiales, Nobleza, Monarquía, Supremos\n"
                    f"**Tu rol actual:**{role_info if role_info else ' Sin cargo alto'}\n\n"
                    f"💡 Este comando muestra los usuarios a quienes has iniciado tiempo.",
                    ephemeral=True
                )
        except discord.NotFound:
            pass
        except Exception:
            pass

@ver_asistencias_admin.error
@sumar_asistencias.error
@agregar_asistencias_diarias.error
@resetear_asistencias.error
@resetear_asistencias_confirmar.error
@ligar_tiempo.error
@desligar_tiempo.error
async def admin_asistencias_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ No tienes permisos de administrador para usar este comando.",
                    ephemeral=True
                )
        except discord.NotFound:
            pass
        except Exception:
            pass

@mi_tiempo.error
async def mi_tiempo_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ No tienes permisos para usar este comando.",
                    ephemeral=True
                )
        except discord.NotFound:
            pass  # Interacción expirada, ignorar
        except Exception:
            pass  # Cualquier otro error, ignorar para evitar loops
    # Para otros errores, dejar que el manejo global se encargue



if __name__ == "__main__":
    print("🤖 Iniciando Discord Time Tracker Bot...")
    print("📋 Cargando configuración...")

    # Obtener token de Discord
    token = get_discord_token()
    if not token:
        exit(1)

    print("🔗 Conectando a Discord...")
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Error: Token de Discord inválido")
        print("   Verifica que el token sea correcto en config.json")
        print("   O en las variables de entorno si usas esa opción")
    except KeyboardInterrupt:
        print("🛑 Bot detenido por el usuario")
    except Exception as e:
        print(f"❌ Error al iniciar el bot: {e}")
        print("   Revisa la configuración y vuelve a intentar")
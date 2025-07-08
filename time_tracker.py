
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

class TimeTracker:
    def __init__(self, data_file: str = "user_times.json"):
        self.data_file = data_file
        self.data = self.load_data()
        self.attendance_file = "attendance_data.json"
        self.attendance_data = self.load_attendance_data()
        self.preregistration_file = "preregistrations.json"
        self.preregistration_data = self.load_preregistration_data()

    def load_data(self) -> Dict[str, Any]:
        """Cargar datos desde el archivo JSON"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error cargando datos: {e}")
            return {}

    def save_data(self) -> None:
        """Guardar datos al archivo JSON"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando datos: {e}")

    def start_tracking(self, user_id: int, user_name: str) -> bool:
        """Iniciar seguimiento de tiempo para un usuario"""
        user_id_str = str(user_id)
        current_time = datetime.now().isoformat()

        if user_id_str not in self.data:
            self.data[user_id_str] = {
                'name': user_name,
                'total_time': 0,
                'sessions': [],
                'is_active': False,
                'is_paused': False,
                'pause_count': 0,
                'notified_milestones': [],
                'milestone_completed': False
            }

        user_data = self.data[user_id_str]

        # Si ya está activo, no hacer nada
        if user_data.get('is_active', False):
            return False

        # Si está pausado, no permitir iniciar nuevo tracking
        if user_data.get('is_paused', False):
            return False

        # Iniciar nueva sesión
        user_data['is_active'] = True
        user_data['is_paused'] = False
        user_data['last_start'] = current_time
        user_data['name'] = user_name  # Actualizar nombre

        self.save_data()
        return True

    def stop_tracking(self, user_id: int) -> bool:
        """Detener seguimiento de tiempo para un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]

        if not user_data.get('is_active', False):
            return False

        # Calcular tiempo de sesión
        if user_data.get('last_start'):
            session_start = datetime.fromisoformat(user_data['last_start'])
            session_time = (datetime.now() - session_start).total_seconds()
            
            # Añadir tiempo de sesión al total
            user_data['total_time'] = user_data.get('total_time', 0) + session_time

        # Marcar como inactivo
        user_data['is_active'] = False
        user_data['is_paused'] = False

        # Agregar sesión al historial
        if 'sessions' not in user_data:
            user_data['sessions'] = []

        session_record = {
            'start': user_data.get('last_start'),
            'end': datetime.now().isoformat(),
            'duration': session_time if user_data.get('last_start') else 0
        }
        user_data['sessions'].append(session_record)

        self.save_data()
        return True

    def pause_tracking(self, user_id: int) -> bool:
        """Pausar seguimiento de tiempo para un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]

        if not user_data.get('is_active', False):
            return False

        # Calcular tiempo de sesión actual y añadirlo al total
        if user_data.get('last_start'):
            session_start = datetime.fromisoformat(user_data['last_start'])
            session_time = (datetime.now() - session_start).total_seconds()
            user_data['total_time'] = user_data.get('total_time', 0) + session_time

        # Marcar como pausado
        user_data['is_active'] = False
        user_data['is_paused'] = True
        user_data['pause_start'] = datetime.now().isoformat()
        user_data['pause_count'] = user_data.get('pause_count', 0) + 1

        self.save_data()
        return True

    def resume_tracking(self, user_id: int) -> bool:
        """Reanudar seguimiento de tiempo para un usuario pausado"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]

        if not user_data.get('is_paused', False):
            return False

        # Reanudar seguimiento
        user_data['is_active'] = True
        user_data['is_paused'] = False
        user_data['last_start'] = datetime.now().isoformat()

        # Limpiar pause_start
        if 'pause_start' in user_data:
            del user_data['pause_start']

        self.save_data()
        return True

    def get_total_time(self, user_id: int) -> float:
        """Obtener tiempo total acumulado de un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return 0.0

        user_data = self.data[user_id_str]
        total_time = user_data.get('total_time', 0)

        # Si está activo, añadir tiempo de sesión actual
        if user_data.get('is_active', False) and user_data.get('last_start'):
            session_start = datetime.fromisoformat(user_data['last_start'])
            current_session_time = (datetime.now() - session_start).total_seconds()
            total_time += current_session_time

        return total_time

    def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Obtener datos completos de un usuario"""
        user_id_str = str(user_id)
        return self.data.get(user_id_str)

    def get_all_tracked_users(self) -> Dict[str, Any]:
        """Obtener todos los usuarios con seguimiento"""
        return self.data.copy()

    def reset_user_time(self, user_id: int) -> bool:
        """Reiniciar tiempo de un usuario a cero"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]
        user_data['total_time'] = 0
        user_data['is_active'] = False
        user_data['is_paused'] = False
        user_data['pause_count'] = 0
        user_data['sessions'] = []
        user_data['notified_milestones'] = []
        user_data['milestone_completed'] = False

        # Limpiar campos de seguimiento
        if 'last_start' in user_data:
            del user_data['last_start']
        if 'pause_start' in user_data:
            del user_data['pause_start']

        self.save_data()
        return True

    def reset_all_user_times(self) -> int:
        """Reiniciar todos los tiempos de usuarios"""
        count = 0
        for user_id_str in list(self.data.keys()):
            user_id = int(user_id_str)
            if self.reset_user_time(user_id):
                count += 1
        return count

    def cancel_user_tracking(self, user_id: int) -> bool:
        """Cancelar completamente el seguimiento de un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        # Eliminar completamente al usuario
        del self.data[user_id_str]
        self.save_data()
        return True

    def clear_all_data(self) -> bool:
        """Limpiar completamente todos los datos"""
        try:
            self.data = {}
            self.save_data()
            return True
        except Exception as e:
            print(f"Error limpiando datos: {e}")
            return False

    def add_minutes(self, user_id: int, user_name: str, minutes: int) -> bool:
        """Añadir minutos al tiempo de un usuario (solo si ya existe)"""
        user_id_str = str(user_id)

        # Solo permitir si el usuario ya existe
        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]
        user_data['total_time'] = user_data.get('total_time', 0) + (minutes * 60)
        user_data['name'] = user_name  # Actualizar nombre

        self.save_data()
        return True

    def subtract_minutes(self, user_id: int, minutes: int) -> bool:
        """Restar minutos del tiempo de un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return False

        user_data = self.data[user_id_str]
        current_time = user_data.get('total_time', 0)
        new_time = max(0, current_time - (minutes * 60))
        user_data['total_time'] = new_time

        self.save_data()
        return True

    def get_pause_count(self, user_id: int) -> int:
        """Obtener número de pausas de un usuario"""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            return 0
        return self.data[user_id_str].get('pause_count', 0)

    def get_paused_duration(self, user_id: int) -> float:
        """Obtener duración pausada actual de un usuario"""
        user_id_str = str(user_id)

        if user_id_str not in self.data:
            return 0.0

        user_data = self.data[user_id_str]

        if not user_data.get('is_paused', False) or not user_data.get('pause_start'):
            return 0.0

        pause_start = datetime.fromisoformat(user_data['pause_start'])
        return (datetime.now() - pause_start).total_seconds()

    def format_time_human(self, seconds: float) -> str:
        """Formatear tiempo en formato humano legible"""
        if seconds < 0:
            return "0 Segundos"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours} Hora{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} Minuto{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:  # Mostrar segundos si no hay otras partes
            parts.append(f"{secs} Segundo{'s' if secs != 1 else ''}")

        return ", ".join(parts)

    def load_attendance_data(self) -> Dict[str, Any]:
        """Cargar datos de asistencias desde archivo JSON"""
        try:
            if os.path.exists(self.attendance_file):
                with open(self.attendance_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error cargando datos de asistencias: {e}")
            return {}

    def save_attendance_data(self) -> None:
        """Guardar datos de asistencias al archivo JSON"""
        try:
            with open(self.attendance_file, 'w', encoding='utf-8') as f:
                json.dump(self.attendance_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando datos de asistencias: {e}")

    def add_manual_attendance(self, admin_id: int, admin_name: str, quantity: int) -> bool:
        """Agregar asistencias manualmente (para comando /sumar_asistencias) - hasta 15 asistencias sin límites"""
        admin_id_str = str(admin_id)
        
        # Verificar que la cantidad esté entre 1 y 15
        if quantity < 1 or quantity > 15:
            return False
        
        # Inicializar datos del admin si no existen
        if admin_id_str not in self.attendance_data:
            self.attendance_data[admin_id_str] = {
                'name': admin_name,
                'daily_attendance': {},
                'total_attendance': 0,
                'manual_weekly_attendance': 0  # Nuevo campo para asistencias manuales semanales
            }
        
        admin_data = self.attendance_data[admin_id_str]
        admin_data['name'] = admin_name  # Actualizar nombre
        
        # Inicializar campo manual semanal si no existe
        if 'manual_weekly_attendance' not in admin_data:
            admin_data['manual_weekly_attendance'] = 0
        
        # Solo agregar al total y al contador semanal manual (NO al diario)
        admin_data['manual_weekly_attendance'] += quantity
        admin_data['total_attendance'] = admin_data.get('total_attendance', 0) + quantity
        self.save_attendance_data()
        return True

    def add_daily_manual_attendance(self, admin_id: int, admin_name: str, quantity: int) -> bool:
        """Agregar asistencias diarias manualmente (para comando /agregar_asistencias_diarias) - máximo 3 por día"""
        admin_id_str = str(admin_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Verificar que la cantidad esté entre 1 y 3
        if quantity < 1 or quantity > 3:
            return False
        
        # Inicializar datos del admin si no existen
        if admin_id_str not in self.attendance_data:
            self.attendance_data[admin_id_str] = {
                'name': admin_name,
                'daily_attendance': {},
                'total_attendance': 0,
                'manual_weekly_attendance': 0
            }
        
        admin_data = self.attendance_data[admin_id_str]
        admin_data['name'] = admin_name  # Actualizar nombre
        
        # Inicializar día si no existe
        if today not in admin_data['daily_attendance']:
            admin_data['daily_attendance'][today] = 0
        
        # Verificar que no exceda 3 asistencias diarias
        if admin_data['daily_attendance'][today] + quantity > 3:
            return False
        
        # SOLO agregar a diarias y totales
        # NO agregar a manual_weekly_attendance porque get_weekly_attendance ya cuenta las diarias
        admin_data['daily_attendance'][today] += quantity
        admin_data['total_attendance'] = admin_data.get('total_attendance', 0) + quantity
        
        # Inicializar campo manual semanal si no existe (pero no sumar aquí)
        if 'manual_weekly_attendance' not in admin_data:
            admin_data['manual_weekly_attendance'] = 0
        
        self.save_attendance_data()
        return True

    def add_attendance(self, admin_id: int, admin_name: str, attendances_to_add: int = 1) -> bool:
        """Agregar asistencia para un administrador (por defecto 1 asistencia)"""
        admin_id_str = str(admin_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Inicializar datos del admin si no existen
        if admin_id_str not in self.attendance_data:
            self.attendance_data[admin_id_str] = {
                'name': admin_name,
                'daily_attendance': {},
                'total_attendance': 0
            }
        
        admin_data = self.attendance_data[admin_id_str]
        admin_data['name'] = admin_name  # Actualizar nombre
        
        # Inicializar día si no existe
        if today not in admin_data['daily_attendance']:
            admin_data['daily_attendance'][today] = 0
        
        # Verificar límite diario (máximo 3 por día)
        if admin_data['daily_attendance'][today] >= 3:
            return False
        
        # Verificar límite semanal (máximo 15 por semana)
        weekly_count = self.get_weekly_attendance(admin_id)
        if weekly_count >= 15:
            return False
        
        # Verificar que no exceda el límite diario
        if admin_data['daily_attendance'][today] + attendances_to_add > 3:
            attendances_to_add = 3 - admin_data['daily_attendance'][today]
        
        # Verificar que no exceda el límite semanal
        if weekly_count + attendances_to_add > 15:
            attendances_to_add = 15 - weekly_count
        
        if attendances_to_add > 0:
            admin_data['daily_attendance'][today] += attendances_to_add
            admin_data['total_attendance'] = admin_data.get('total_attendance', 0) + attendances_to_add
            self.save_attendance_data()
            return True
        
        return False

    def get_daily_attendance(self, admin_id: int) -> int:
        """Obtener asistencias del día actual"""
        admin_id_str = str(admin_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if admin_id_str not in self.attendance_data:
            return 0
        
        return self.attendance_data[admin_id_str]['daily_attendance'].get(today, 0)

    def get_weekly_attendance(self, admin_id: int) -> int:
        """Obtener asistencias de la semana actual"""
        admin_id_str = str(admin_id)
        
        if admin_id_str not in self.attendance_data:
            return 0
        
        admin_data = self.attendance_data[admin_id_str]
        
        # Calcular fechas de la semana actual (lunes a viernes)
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        
        weekly_count = 0
        for i in range(5):  # Solo 5 días: lunes a viernes
            date = (start_of_week + timedelta(days=i)).strftime("%Y-%m-%d")
            weekly_count += admin_data['daily_attendance'].get(date, 0)
        
        # Agregar asistencias manuales semanales
        weekly_count += admin_data.get('manual_weekly_attendance', 0)
        
        return weekly_count

    def get_total_attendance(self, admin_id: int) -> int:
        """Obtener total de asistencias"""
        admin_id_str = str(admin_id)
        
        if admin_id_str not in self.attendance_data:
            return 0
        
        return self.attendance_data[admin_id_str].get('total_attendance', 0)

    def get_attendance_info(self, admin_id: int) -> Dict[str, int]:
        """Obtener información completa de asistencias"""
        return {
            'daily': self.get_daily_attendance(admin_id),
            'weekly': self.get_weekly_attendance(admin_id),
            'total': self.get_total_attendance(admin_id)
        }

    def set_time_initiator(self, user_id: int, admin_id: int, admin_name: str) -> None:
        """Registrar quién inició el tiempo para un usuario"""
        user_id_str = str(user_id)
        if user_id_str in self.data:
            self.data[user_id_str]['time_initiator'] = {
                'admin_id': admin_id,
                'admin_name': admin_name,
                'timestamp': datetime.now().isoformat()
            }
            self.save_data()

    def get_time_initiator(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Obtener información de quién inició el tiempo para un usuario"""
        user_id_str = str(user_id)
        if user_id_str in self.data:
            return self.data[user_id_str].get('time_initiator')
        return None

    def clear_time_initiator(self, user_id: int) -> None:
        """Limpiar información del iniciador del tiempo"""
        user_id_str = str(user_id)
        if user_id_str in self.data and 'time_initiator' in self.data[user_id_str]:
            del self.data[user_id_str]['time_initiator']
            self.save_data()

    def reset_weekly_manual_attendances(self) -> None:
        """Resetear solo las asistencias manuales semanales (para nueva semana)"""
        for admin_id_str in self.attendance_data:
            self.attendance_data[admin_id_str]['manual_weekly_attendance'] = 0
        self.save_attendance_data()

    def link_time_to_user(self, user_id: int, admin_id: int, admin_name: str) -> bool:
        """Ligar el tiempo de un usuario a otro (para que reciba asistencias)"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            return False
        
        user_data = self.data[user_id_str]
        
        # Verificar que el usuario tenga tiempo activo
        if not user_data.get('is_active', False):
            return False
        
        # Establecer el ligado
        user_data['linked_to'] = {
            'admin_id': admin_id,
            'admin_name': admin_name,
            'linked_at': datetime.now().isoformat()
        }
        
        self.save_data()
        return True

    def unlink_time(self, user_id: int) -> bool:
        """Desligar el tiempo de un usuario"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            return False
        
        user_data = self.data[user_id_str]
        
        if 'linked_to' in user_data:
            del user_data['linked_to']
            self.save_data()
            return True
        
        return False

    def is_time_linked(self, user_id: int) -> bool:
        """Verificar si el tiempo de un usuario está ligado"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            return False
        
        return 'linked_to' in self.data[user_id_str]

    def get_linked_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Obtener información del usuario al que está ligado el tiempo"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            return None
        
        return self.data[user_id_str].get('linked_to')

    def can_receive_daily_attendance(self, user_id: int) -> bool:
        """Verificar si un usuario puede recibir asistencias diarias (siempre True ahora que no hay transferencias)"""
        return True

    def reset_all_attendances(self) -> bool:
        """Resetear completamente todas las asistencias de todos los usuarios"""
        try:
            self.attendance_data = {}
            self.save_attendance_data()
            return True
        except Exception as e:
            print(f"Error reseteando asistencias: {e}")
            return False

    def load_preregistration_data(self) -> Dict[str, Any]:
        """Cargar datos de pre-registros desde archivo JSON"""
        try:
            if os.path.exists(self.preregistration_file):
                with open(self.preregistration_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error cargando datos de pre-registros: {e}")
            return {}

    def save_preregistration_data(self) -> None:
        """Guardar datos de pre-registros al archivo JSON"""
        try:
            with open(self.preregistration_file, 'w', encoding='utf-8') as f:
                json.dump(self.preregistration_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando datos de pre-registros: {e}")

    def preregister_user(self, user_id: int, user_name: str, admin_id: int, admin_name: str) -> bool:
        """Pre-registrar un usuario para inicio automático a las 5 PM"""
        user_id_str = str(user_id)
        
        # Verificar si ya está pre-registrado
        if user_id_str in self.preregistration_data:
            return False
        
        # Verificar si ya tiene tiempo activo o pausado
        if user_id_str in self.data:
            user_data = self.data[user_id_str]
            if user_data.get('is_active', False) or user_data.get('is_paused', False):
                return False
        
        # Crear pre-registro
        self.preregistration_data[user_id_str] = {
            'name': user_name,
            'registered_by_id': admin_id,
            'registered_by_name': admin_name,
            'registered_at': datetime.now().isoformat()
        }
        
        self.save_preregistration_data()
        return True

    def get_preregistered_users(self) -> Dict[str, Any]:
        """Obtener todos los usuarios pre-registrados"""
        return self.preregistration_data.copy()

    def activate_preregistration(self, user_id: int) -> bool:
        """Activar un pre-registro (convertirlo en tiempo activo)"""
        user_id_str = str(user_id)
        
        # Verificar que esté pre-registrado
        if user_id_str not in self.preregistration_data:
            return False
        
        prereg_data = self.preregistration_data[user_id_str]
        user_name = prereg_data['name']
        admin_id = prereg_data['registered_by_id']
        admin_name = prereg_data['registered_by_name']
        
        # Iniciar el tracking normal
        success = self.start_tracking(user_id, user_name)
        if success:
            # Establecer información del iniciador
            self.set_time_initiator(user_id, admin_id, admin_name)
            
            # Remover del pre-registro
            del self.preregistration_data[user_id_str]
            self.save_preregistration_data()
            
            return True
        
        return False

    def clean_expired_preregistrations(self) -> int:
        """Limpiar pre-registros expirados (después de las 5 PM)"""
        cleaned_count = 0
        try:
            # Limpiar todos los pre-registros
            cleaned_count = len(self.preregistration_data)
            self.preregistration_data = {}
            self.save_preregistration_data()
        except Exception as e:
            print(f"Error limpiando pre-registros expirados: {e}")
        
        return cleaned_count

    def remove_preregistration(self, user_id: int) -> bool:
        """Remover un pre-registro específico"""
        user_id_str = str(user_id)
        if user_id_str in self.preregistration_data:
            del self.preregistration_data[user_id_str]
            self.save_preregistration_data()
            return True
        return False

    def get_users_initiated_by_admin(self, admin_id: int) -> list:
        """Obtener lista de usuarios que fueron iniciados por un admin específico"""
        initiated_users = []
        
        for user_id_str, user_data in self.data.items():
            # Verificar si el admin inició este tiempo
            initiator_info = user_data.get('time_initiator')
            if initiator_info and initiator_info.get('admin_id') == admin_id:
                user_id = int(user_id_str)
                total_time = self.get_total_time(user_id)
                
                initiated_users.append({
                    'user_id': user_id,
                    'name': user_data.get('name', f'Usuario {user_id}'),
                    'total_time': total_time,
                    'is_active': user_data.get('is_active', False),
                    'is_paused': user_data.get('is_paused', False),
                    'milestone_completed': user_data.get('milestone_completed', False),
                    'initiated_at': initiator_info.get('timestamp', '')
                })
        
        # Ordenar por nombre
        initiated_users.sort(key=lambda x: x['name'].lower())
        return initiated_users

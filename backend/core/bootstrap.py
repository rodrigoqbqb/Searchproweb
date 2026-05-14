import sys
import subprocess
import os

REQUIRED_PACKAGES = [
    "PyQt5", 
    "qtawesome", 
    "httpx", 
    "geopy", 
    "sqlalchemy", 
    "requests",
    "psutil" # Adicionado para monitoramento de performance
]

def install_dependencies():
    """Garante que todas as dependências industriais estejam instaladas."""
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.lower().replace('-', '_'))
        except ImportError:
            print(f"[*] Instalando dependência crítica: {pkg}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            except Exception as e:
                print(f"[X] Erro ao instalar {pkg}: {e}")

def get_memory_usage():
    """Retorna o percentual de uso de memória do sistema."""
    try:
        import psutil
        return psutil.virtual_memory().percent
    except:
        return 0

def get_recommended_threads():
    """Calcula o número ideal de threads baseado na saúde do sistema."""
    usage = get_memory_usage()
    if usage > 85: return 1  # Modo crítico
    if usage > 70: return 2  # Modo conservador
    return 5  # Modo Full Performance

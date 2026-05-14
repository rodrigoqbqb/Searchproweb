import time
import hashlib
from typing import Optional, Any

class MultiLayerCache:
    """Cache em memória para máxima performance."""
    
    def __init__(self):
        self._memory_cache = {}
        self._ttl = {
            "coords": 86400,    # 24h - CEP não muda
            "stores": 3600,     # 1h  - resultados podem mudar
            "categories": 604800  # 7 dias - mapa de categorias
        }
    
    def _make_key(self, prefix: str, key_val: str) -> str:
        return f"{prefix}:{hashlib.md5(str(key_val).encode()).hexdigest()}"
    
    async def get_or_fetch(
        self, 
        prefix: str, 
        key: str, 
        fetch_func,
        *args,
        ttl: Optional[int] = None
    ):
        cache_key = self._make_key(prefix, key)
        
        # Check memory cache
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if time.time() - cached["ts"] < (ttl or self._ttl.get(prefix, 3600)):
                return cached["data"]
        
        # Fetch fresh data
        data = await fetch_func(*args)
        
        # Store in cache (Apenas se houver resultados para evitar 'bloqueio' por falha temporária)
        if data or prefix != "stores":
            self._memory_cache[cache_key] = {
                "data": data,
                "ts": time.time()
            }
        
        return data


# Instância global
cache = MultiLayerCache()

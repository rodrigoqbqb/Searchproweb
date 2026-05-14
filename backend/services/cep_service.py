import httpx
import asyncio
import re
import time
import logging
from typing import Optional, List, Dict
from ..schemas.schemas import CoordsUser
from ..core.cache import cache
from .web_service import web_hunter
from .translator_service import translator
from .tag_discovery import tag_discovery

logging.basicConfig(filename='activity_log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "buscador-lojas"}
SEARCH_RADIUS = 5000   # metros
MAX_HUNT_TIME = 120    # segundos (2 minutos)


async def get_cep_from_ip() -> Optional[str]:
    services = ["http://ip-api.com/json", "https://ipapi.co/json/"]
    for url in services:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    cep = data.get("zip") or data.get("postal")
                    if cep:
                        cep_clean = re.sub(r"\D", "", str(cep))
                        if len(cep_clean) == 8:
                            return cep_clean
        except:
            pass
    return None


async def get_cords_from_cep(cep: str) -> Optional[CoordsUser]:
    async def _fetch(current_cep: str) -> Optional[CoordsUser]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"https://viacep.com.br/ws/{current_cep}/json/")
            if resp.status_code != 200 or resp.json().get("erro"):
                return None
            addr = resp.json()
            
        # Se for um CEP master, logradouro vem vazio. Protege contra string 'None'
        logra = addr.get('logradouro', '')
        loc = addr.get('localidade', '')
        uf = addr.get('uf', '')
        
        full_addr = f"{logra}, {loc}, {uf}, Brasil" if logra else f"{loc}, {uf}, Brasil"
        params = {"q": full_addr, "format": "json", "limit": 1}
        
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=HEADERS)
            if resp.status_code != 200 or not resp.json():
                return None
            data = resp.json()
            
        return CoordsUser(latitude=data[0]["lat"], longitude=data[0]["lon"])

    # Tentativa 1: CEP Original
    result = await cache.get_or_fetch("coords", cep, lambda: _fetch(cep))
    if result:
        return result
        
    # Tentativa 2: CEP Master (+/- cidade/bairro genérico final 000)
    cep_master_1 = cep[:-3] + "000"
    if cep_master_1 != cep:
        print(f"DEBUG: [CEP] Original {cep} falhou. Tentando Master {cep_master_1}...")
        result = await cache.get_or_fetch("coords", cep_master_1, lambda: _fetch(cep_master_1))
        if result:
            return result
            
    # Tentativa 3: CEP Master Amplo (final 0000)
    cep_master_2 = cep[:-4] + "0000"
    if cep_master_2 != cep_master_1:
        print(f"DEBUG: [CEP] Master {cep_master_1} falhou. Tentando Master Amplo {cep_master_2}...")
        result = await cache.get_or_fetch("coords", cep_master_2, lambda: _fetch(cep_master_2))
        if result:
            return result

    print(f"DEBUG: [CEP ERROR] Impossível encontrar coordenadas para o CEP {cep} e seus equivalentes Master.")
    return None


async def _osm_query(query: str) -> list:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(OVERPASS_URL, data=query, headers=HEADERS)
            if resp.status_code == 200:
                return resp.json().get("elements", [])
    except:
        pass
    return []


async def _search_by_tag(key: str, value: str, lat: float, lon: float) -> list:
    """Consulta OSM por etiqueta especifica (key=value)."""
    around = f"(around:{SEARCH_RADIUS},{lat},{lon})"
    q = (
        f'[out:json][timeout:20];('
        f'node["{key}"="{value}"]{around};'
        f'way["{key}"="{value}"]{around};'
        f'relation["{key}"="{value}"]{around};'
        f');out center;'
    )
    return await _osm_query(q)


async def _search_by_name(term: str, english: str, lat: float, lon: float) -> list:
    """Consulta OSM filtrando pelo nome do local (contem o termo)."""
    terms = list({term.lower(), english.lower()})
    terms = [t for t in terms if len(t) > 2]
    safe_regex = "|".join(re.escape(t) for t in terms)
    around = f"(around:{SEARCH_RADIUS},{lat},{lon})"
    print(f"DEBUG: [NOME] Buscando por nome: '{safe_regex}'")
    q = (
        f'[out:json][timeout:20];('
        f'node["name"~"{safe_regex}",i]{around};'
        f'way["name"~"{safe_regex}",i]{around};'
        f'relation["name"~"{safe_regex}",i]{around};'
        f');out center;'
    )
    return await _osm_query(q)


def _format_elements(elements: list) -> dict:
    """Formata elementos OSM em dicionario de stores."""
    stores = {}
    for el in elements:
        tags = el.get("tags", {})
        eid = el.get("id")
        name = (
            tags.get("name") or tags.get("brand") or
            tags.get("operator") or
            f"Local ({tags.get('amenity') or tags.get('shop') or tags.get('tourism') or '?'})"
        )
        addr = tags.get("addr:street", "Endereco via mapa")
        if tags.get("addr:housenumber"):
            addr += f", {tags['addr:housenumber']}"
        stores[eid] = {
            "id": eid, "name": name,
            "latitude": el.get("center", {}).get("lat") or el.get("lat"),
            "longitude": el.get("center", {}).get("lon") or el.get("lon"),
            "address": addr,
            "website": tags.get("website"),
            "phone": tags.get("phone"),
            "source": "OSM"
        }
    return stores


async def search_nearby_stores(latitude: float, longitude: float, search_term: str, cep: str = ""):
    async def _fetch():
        logging.info(f"Busca: '{search_term}' ({latitude}, {longitude})")
        lat, lon = latitude, longitude

        # Web Hunter em paralelo (resultados sao sempre relevantes pois buscam o termo)
        web_task = asyncio.create_task(web_hunter.search_web_fallback(search_term, cep))

        english = await translator.translate_to_english(search_term)
        all_elements = []
        start_time = time.time()

        # ================================================================
        # LOOP PRINCIPAL: Tenta etiquetas do banco, cacando novas se vazio
        # ================================================================
        hunt_round = 0
        while time.time() - start_time < MAX_HUNT_TIME:
            # 1. Busca etiquetas no banco
            candidates = await tag_discovery.get_candidates_from_db(search_term)

            if candidates:
                for k, v in candidates:
                    print(f"DEBUG: [BANCO] Tentando {k}={v}...")
                    els = await _search_by_tag(k, v, lat, lon)
                    if els:
                        all_elements = els
                        await tag_discovery.register_successful_tag(search_term, k, v)
                        print(f"DEBUG: [OK] {len(els)} resultados com {k}={v}")
                        break
                    else:
                        print(f"DEBUG: [ZERO] {k}={v} nao retornou resultados")

            if all_elements:
                break

            # 2. Sem resultado: busca por NOME (sempre relevante)
            name_els = await _search_by_name(search_term, english, lat, lon)
            if name_els:
                all_elements = name_els
                # Aprende a tag do primeiro resultado encontrado
                first_tags = name_els[0].get("tags", {})
                for tk in ["amenity", "shop", "cuisine", "tourism", "leisure", "historic"]:
                    if tk in first_tags:
                        await tag_discovery.register_successful_tag(search_term, tk, first_tags[tk])
                        break
                break

            # 3. Ainda vazio: cacada web por novas etiquetas OSM
            elapsed = time.time() - start_time
            remaining = MAX_HUNT_TIME - elapsed
            if remaining < 10:
                print(f"DEBUG: [TIMEOUT] 2 minutos atingidos sem resultado OSM.")
                break

            hunt_round += 1
            print(f"DEBUG: [HUNT #{hunt_round}] Cacando novas etiquetas (restam {remaining:.0f}s)...")
            new_candidates = await tag_discovery.hunt_and_store(search_term, lat, lon)

            if not new_candidates:
                # Sem etiquetas, sem nome: nao ha dados OSM para esse termo
                print(f"DEBUG: [SEM DADOS OSM] Nenhuma etiqueta ou nome encontrado. Usando apenas Web Hunter.")
                break

            # Testa as novas candidatas imediatamente
            for k, v in new_candidates:
                print(f"DEBUG: [NOVA TAG] Testando {k}={v}...")
                els = await _search_by_tag(k, v, lat, lon)
                if els:
                    all_elements = els
                    await tag_discovery.register_successful_tag(search_term, k, v)
                    print(f"DEBUG: [OK] {len(els)} resultados com nova etiqueta {k}={v}")
                    break
                else:
                    print(f"DEBUG: [ZERO] Nova etiqueta {k}={v} tambem sem resultado")

            if all_elements:
                break

        # ================================================================
        # RESULTADO FINAL: Mescla OSM + Web Hunter
        # Web Hunter eh relevante porque buscou especificamente o termo
        # ================================================================
        web_results = []
        try:
            web_results = await web_task
        except:
            pass

        stores = {}
        # Web Hunter primeiro (sempre relevante ao termo)
        for w in web_results:
            # Garante que web results tenham latitude/longitude (podem ser None)
            if "latitude" not in w:
                w["latitude"] = None
            if "longitude" not in w:
                w["longitude"] = None
            stores[w["id"]] = w

        # OSM depois (sobrescreve apenas se nao for resultado web)
        osm_stores = _format_elements(all_elements)
        for eid, store in osm_stores.items():
            if eid not in stores:
                stores[eid] = store

        return list(stores.values())

    cache_key = f"{latitude}|{longitude}|{search_term.lower()}"
    return await cache.get_or_fetch("stores", cache_key, _fetch)

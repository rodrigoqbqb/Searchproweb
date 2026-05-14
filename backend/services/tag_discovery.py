import httpx
import re
import asyncio
import logging
from .web_service import web_hunter
from ..core.vault import get_etiqueta, save_etiqueta
from .translator_service import translator

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
VALID_KEYS = {"amenity", "shop", "cuisine", "leisure", "tourism", "historic",
              "craft", "office", "healthcare", "sport", "natural", "place", "emergency"}


class TagDiscoveryService:
    """Cerebro Autonomo de Descoberta de Etiquetas.
    
    Estrategia:
    1. Banco de dados (etiquetas aprendidas)
    2. Overpass Raio Amplo (busca em 500km para descobrir tags reais do OSM)
    3. Busca web (OSM wiki/taginfo via Bing como ultimo recurso)
    """

    async def get_candidates_from_db(self, term: str) -> list:
        """Busca candidatas exclusivamente do banco de dados."""
        term_lower = term.lower().strip()
        cached = get_etiqueta(term_lower)
        if cached:
            return [(cached["key"], cached["value"])]
        return []

    async def hunt_and_store(self, term: str, lat: float = -15.0, lon: float = -47.0) -> list:
        """Descobre tags OSM reais usando Overpass em raio amplo, depois web."""
        term_lower = term.lower().strip()
        english = await translator.translate_to_english(term_lower)

        candidates = []

        # ── Etapa 1: Overpass Raio Amplo (500km) ──────────────────────────────
        # Busca o termo no raio de 500km para descobrir quais tags OSM usa
        terms = list(dict.fromkeys([re.escape(term_lower), re.escape(english.lower())]))
        regex = "|".join(t for t in terms if len(t) > 2)
        
        print(f"DEBUG: [OVERPASS WIDE] Buscando '{regex}' em raio de 500km para descobrir tags...")
        query = (
            f'[out:json][timeout:20];'
            f'('
            f'node["name"~"{regex}",i](around:500000,{lat},{lon});'
            f'way["name"~"{regex}",i](around:500000,{lat},{lon});'
            f');'
            f'out tags 5;'
        )
        try:
            async with httpx.AsyncClient(timeout=25, headers={"User-Agent": "buscador-lojas"}) as client:
                resp = await client.post(OVERPASS_URL, data=query)
                if resp.status_code == 200:
                    elements = resp.json().get("elements", [])
                    for el in elements:
                        tags = el.get("tags", {})
                        for k in VALID_KEYS:
                            if k in tags and tags[k]:
                                pair = (k, tags[k])
                                if pair not in candidates:
                                    candidates.append(pair)
                                    print(f"DEBUG: [OVERPASS WIDE RESULT] {k}={tags[k]}")
        except Exception as e:
            print(f"DEBUG: [OVERPASS WIDE ERROR] {e}")

        # ── Etapa 2: Busca Web (OSM wiki via Bing) ────────────────────────────
        if not candidates:
            print(f"DEBUG: [WEB HUNT] Buscando tags no wiki OSM para '{english}'...")
            candidates = await self._hunt_via_web(english)

        # ── Salva no banco ────────────────────────────────────────────────────
        if candidates:
            k, v = candidates[0]
            save_etiqueta(term_lower, k, v, fonte="Overpass Wide Discovery")
            print(f"DEBUG: [BANCO] Salvo: '{term_lower}' -> {k}={v} | {len(candidates)} candidatas")
        else:
            print(f"DEBUG: [SEM TAG] Nenhuma etiqueta OSM encontrada para '{term}'")

        return candidates

    async def _hunt_via_web(self, english: str) -> list:
        """Extrai tags OSM do texto de resultados web (OSM wiki, taginfo)."""
        candidates = []
        try:
            results = await web_hunter.search_web_fallback(
                f'{english} openstreetmap amenity shop tag wiki', "01001000"
            )
            context = " ".join([
                r.get("name", "") + " " + r.get("address", "")
                for r in results
            ]).lower()
            valid_pattern = r"amenity|shop|cuisine|leisure|tourism|historic|craft|office|healthcare"
            matches = re.findall(rf'({valid_pattern})=([a-z_]+)', context)
            for k, v in matches:
                if (k, v) not in candidates:
                    candidates.append((k, v))
                    print(f"DEBUG: [WEB RESULT] {k}={v}")
        except Exception as e:
            print(f"DEBUG: [WEB ERROR] {e}")
        return candidates

    async def register_successful_tag(self, term: str, key: str, value: str):
        """Registra no banco uma etiqueta que gerou resultados reais."""
        save_etiqueta(term.lower().strip(), key, value, fonte="Active Learning (Confirmed)")
        print(f"DEBUG: [CONFIRMADO] '{term}' -> {key}={value}")


tag_discovery = TagDiscoveryService()

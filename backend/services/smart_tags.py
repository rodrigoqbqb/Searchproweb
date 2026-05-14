# @CanalQb SearchPRO Web — Motor Semântico OSM
# Mapeia qualquer termo humano para tags válidas do OpenStreetMap
# Feito com Master Rules CanalQb v1.0

import unicodedata
import re
from typing import NamedTuple, List, Dict, Optional, Tuple

# ──────────────────────────────────────────────
# TIPOS
# ──────────────────────────────────────────────
class TagQuery(NamedTuple):
    key: str
    value: str
    extra_filter: str = ""   # ex: '["cuisine"~"pizza",i]'


# ──────────────────────────────────────────────
# NORMALIZADOR
# ──────────────────────────────────────────────
def normalize(text: str) -> str:
    """Remove acentos, lowercase, strip. 'Mecânica' → 'mecanica'"""
    if not text: return ""
    nfkd = unicodedata.normalize("NFKD", text.lower().strip())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ──────────────────────────────────────────────
# MAPA PRINCIPAL: termo normalizado → tags OSM
# ──────────────────────────────────────────────
TAG_MAP: Dict[str, List[TagQuery]] = {

    # ─── ALIMENTAÇÃO GERAL ───────────────────
    "mercado":        [TagQuery("shop","supermarket"), TagQuery("shop","convenience"),
                       TagQuery("shop","grocery"), TagQuery("amenity","marketplace")],
    "supermercado":   [TagQuery("shop","supermarket"), TagQuery("shop","grocery")],
    "minimercado":    [TagQuery("shop","convenience"), TagQuery("shop","grocery")],
    "mercearia":      [TagQuery("shop","convenience"), TagQuery("shop","grocery")],
    "emporio":        [TagQuery("shop","deli"), TagQuery("shop","convenience")],
    "hortifruti":     [TagQuery("shop","greengrocer"), TagQuery("shop","farm")],
    "quitanda":       [TagQuery("shop","greengrocer")],
    "acougue":        [TagQuery("shop","butcher")],
    "peixaria":       [TagQuery("shop","seafood")],
    "padaria":        [TagQuery("shop","bakery")],
    "confeitaria":    [TagQuery("shop","pastry"), TagQuery("shop","bakery")],
    "doceria":        [TagQuery("shop","confectionery"), TagQuery("shop","pastry")],
    "atacado":        [TagQuery("shop","wholesale")],
    "atacadao":       [TagQuery("shop","wholesale")],
    "feira":          [TagQuery("amenity","marketplace"), TagQuery("shop","farm")],

    # ─── RESTAURANTES / COMIDA ───────────────
    "restaurante":    [TagQuery("amenity","restaurant")],
    "lanchonete":     [TagQuery("amenity","fast_food"), TagQuery("amenity","snack_bar")],
    "lanche":         [TagQuery("amenity","fast_food"), TagQuery("amenity","snack_bar")],
    "fast food":      [TagQuery("amenity","fast_food")],
    "hamburguer":     [TagQuery("amenity","fast_food","[\"cuisine\"~\"burger\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"burger\",i]")],
    "pizza":          [TagQuery("amenity","restaurant","[\"cuisine\"~\"pizza\",i]"),
                       TagQuery("amenity","fast_food","[\"cuisine\"~\"pizza\",i]")],
    "pizzaria":       [TagQuery("amenity","restaurant","[\"cuisine\"~\"pizza\",i]"),
                       TagQuery("amenity","fast_food","[\"cuisine\"~\"pizza\",i]")],
    "churrascaria":   [TagQuery("amenity","restaurant","[\"cuisine\"~\"barbecue\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"steak_house\",i]")],
    "churrasco":      [TagQuery("amenity","restaurant","[\"cuisine\"~\"barbecue\",i]")],
    "japones":        [TagQuery("amenity","restaurant","[\"cuisine\"~\"japanese\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"sushi\",i]")],
    "sushi":          [TagQuery("amenity","restaurant","[\"cuisine\"~\"sushi\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"japanese\",i]")],
    "chines":         [TagQuery("amenity","restaurant","[\"cuisine\"~\"chinese\",i]")],
    "italiano":       [TagQuery("amenity","restaurant","[\"cuisine\"~\"italian\",i]")],
    "mexicano":       [TagQuery("amenity","restaurant","[\"cuisine\"~\"mexican\",i]")],
    "arabe":          [TagQuery("amenity","restaurant","[\"cuisine\"~\"arab\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"lebanese\",i]")],
    "turco":          [TagQuery("amenity","restaurant","[\"cuisine\"~\"turkish\",i]")],
    "indiano":        [TagQuery("amenity","restaurant","[\"cuisine\"~\"indian\",i]")],
    "thai":           [TagQuery("amenity","restaurant","[\"cuisine\"~\"thai\",i]")],
    "peruano":        [TagQuery("amenity","restaurant","[\"cuisine\"~\"peruvian\",i]")],
    "frutos do mar":  [TagQuery("amenity","restaurant","[\"cuisine\"~\"seafood\",i]")],
    "frango":         [TagQuery("amenity","fast_food","[\"cuisine\"~\"chicken\",i]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"chicken\",i]")],
    "vegano":         [TagQuery("amenity","restaurant","[\"diet:vegan\"=\"yes\"]"),
                       TagQuery("amenity","restaurant","[\"cuisine\"~\"vegan\",i]")],
    "vegetariano":    [TagQuery("amenity","restaurant","[\"diet:vegetarian\"=\"yes\"]")],
    "cafe":           [TagQuery("amenity","cafe")],
    "cafeteria":      [TagQuery("amenity","cafe")],
    "sorveteria":     [TagQuery("amenity","ice_cream"), TagQuery("shop","ice_cream")],
    "sorvete":        [TagQuery("amenity","ice_cream"), TagQuery("shop","ice_cream")],
    "acai":           [TagQuery("amenity","ice_cream","[\"name\"~\"acai\",i]"),
                       TagQuery("amenity","fast_food","[\"name\"~\"acai\",i]")],
    "bar":            [TagQuery("amenity","bar"), TagQuery("amenity","pub")],
    "boteco":         [TagQuery("amenity","bar"), TagQuery("amenity","pub")],
    "pub":            [TagQuery("amenity","pub"), TagQuery("amenity","bar")],
    "balada":         [TagQuery("amenity","nightclub")],
    "boate":          [TagQuery("amenity","nightclub")],

    # ─── AUTOMOTIVO / CARRO ──────────────────
    "carro":          [TagQuery("shop","car_repair"), TagQuery("shop","car"),
                       TagQuery("amenity","car_wash"), TagQuery("shop","tyres"),
                       TagQuery("shop","car_parts")],
    "automovel":      [TagQuery("shop","car"), TagQuery("shop","car_repair")],
    "mecanica":       [TagQuery("shop","car_repair")],
    "oficina":        [TagQuery("shop","car_repair"), TagQuery("craft","car_repair")],
    "concessionaria": [TagQuery("shop","car")],
    "autoparts":      [TagQuery("shop","car_parts")],
    "autopecas":      [TagQuery("shop","car_parts")],
    "pecas":          [TagQuery("shop","car_parts")],
    "borracharia":    [TagQuery("shop","tyres")],
    "pneu":           [TagQuery("shop","tyres")],
    "lava jato":      [TagQuery("amenity","car_wash")],
    "lavagem":        [TagQuery("amenity","car_wash")],
    "estacionamento": [TagQuery("amenity","parking")],
    "garagem":        [TagQuery("amenity","parking")],
    "posto":          [TagQuery("amenity","fuel")],
    "gasolina":       [TagQuery("amenity","fuel")],
    "combustivel":    [TagQuery("amenity","fuel")],
    "gnv":            [TagQuery("amenity","fuel","[\"fuel:cng\"=\"yes\"]")],
    "moto":           [TagQuery("shop","motorcycle"), TagQuery("shop","motorcycle_repair")],
    "motocicleta":    [TagQuery("shop","motorcycle"), TagQuery("shop","motorcycle_repair")],
    "bicicleta":      [TagQuery("shop","bicycle"), TagQuery("amenity","bicycle_rental")],
    "bike":           [TagQuery("shop","bicycle")],

    # ─── SAÚDE ───────────────────────────────
    "hospital":       [TagQuery("amenity","hospital")],
    "upa":            [TagQuery("amenity","clinic"), TagQuery("amenity","hospital")],
    "pronto socorro": [TagQuery("amenity","hospital"), TagQuery("amenity","clinic")],
    "clinica":        [TagQuery("amenity","clinic"), TagQuery("amenity","doctors")],
    "medico":         [TagQuery("amenity","doctors"), TagQuery("amenity","clinic")],
    "farmacia":       [TagQuery("amenity","pharmacy")],
    "drogaria":       [TagQuery("amenity","pharmacy")],
    "remedio":        [TagQuery("amenity","pharmacy")],
    "dentista":       [TagQuery("amenity","dentist")],
    "otica":          [TagQuery("shop","optician")],
    "academia":       [TagQuery("leisure","fitness_centre")],
    "ginastica":      [TagQuery("leisure","fitness_centre")],
    "veterinario":    [TagQuery("amenity","veterinary")],
    "pet":            [TagQuery("amenity","veterinary"), TagQuery("shop","pet")],
    "petshop":        [TagQuery("shop","pet")],

    # ─── TRANSPORTE ──────────────────────────
    "onibus":         [TagQuery("highway","bus_stop"), TagQuery("amenity","bus_station")],
    "ponto":          [TagQuery("highway","bus_stop")],
    "parada":         [TagQuery("highway","bus_stop")],
    "terminal":       [TagQuery("amenity","bus_station"), TagQuery("railway","station")],
    "metro":          [TagQuery("railway","station")],
    "trem":           [TagQuery("railway","station")],

    # ─── LAZER ───────────────────────────────
    "parque":         [TagQuery("leisure","park")],
    "praca":          [TagQuery("leisure","park")],
    "shopping":       [TagQuery("shop","mall")],
    "hotel":          [TagQuery("tourism","hotel")],
}

# ──────────────────────────────────────────────
# SINONIMOS: termo → termos canônicos no TAG_MAP
# ──────────────────────────────────────────────
SYNONYM_MAP: Dict[str, str] = {
    "super": "supermercado",
    "hipermercado": "supermercado",
    "armazem": "mercado",
    "carnes": "acougue",
    "pao": "padaria",
    "burger": "hamburguer",
    "japanese": "japones",
    "remédio": "farmacia",
    "cabelo": "salao",
    "combustível": "combustivel",
}


def resolve_term(raw: str) -> Tuple[str, List[TagQuery]]:
    """Resolve um termo bruto para (termo_canônico, lista_de_tags)."""
    key = normalize(raw)
    if key in TAG_MAP: return key, TAG_MAP[key]
    canonical = SYNONYM_MAP.get(key)
    if canonical and canonical in TAG_MAP: return canonical, TAG_MAP[canonical]
    return key, []


def build_overpass_query(
    tags: List[TagQuery],
    lat: float,
    lon: float,
    radius: int = 5000,
    timeout: int = 25,
    term_fallback: str = "",
) -> str:
    """Constrói uma query Overpass QL válida."""
    parts: List[str] = []
    around = f"(around:{radius},{lat},{lon})"

    for tq in tags:
        base_filter = f'["{tq.key}"="{tq.value}"]{tq.extra_filter}'
        for elem in ("node", "way", "relation"):
            parts.append(f'  {elem}{base_filter}{around};')

    if term_fallback:
        safe = term_fallback.replace('"', '\\"')
        for elem in ("node", "way", "relation"):
            parts.append(f'  {elem}["name"~"{safe}",i]{around};')

    if not parts: return ""

    body = "\n".join(parts)
    return (
        f'[out:json][timeout:{timeout}];\n'
        f'(\n'
        f'{body}\n'
        f');\n'
        f'out center;'
    )

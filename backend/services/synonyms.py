SYNONYM_MAP = {
    "mercado": ["supermercado", "minimercado", "hipermercado", "atacadão", "empório", "quitanda", "grocery", "market", "venda", "mercearia"],
    "farmacia": ["farmácia", "drogaria", "medicamento", "pharmacy", "drugstore"],
    "mecanica": ["mecânica", "oficina", "automecânica", "carro", "repair", "garage", "carros", "veiculos", "automotivo"],
    "carro": ["carros", "veiculos", "veículos", "automotivo", "oficina", "mecânica", "revisão", "concessionária", "revenda"],
    "carros": ["carro", "veiculos", "veículos", "automotivo", "oficina", "mecânica", "concessionária", "revenda"],
    "lanche": ["lanchonete", "lanche", "snack", "fast food", "burger", "hamburger"],
    "pizza": ["pizzaria", "pizza", "pizz"],
    "academia": ["ginástica", "musculação", "fitness", "crossfit", "gym"],
    "bar": ["bar", "boteco", "pub", "balada", "nightclub"],
    "hotel": ["hospede", "pousada", "hostel", "resort", "hotel"],
    "restaurante": ["restaurante", "resto", "comida", "jantar", "almoço", "restaurant", "food"],
    "onibus": ["ônibus", "ponto", "parada", "terminal", "rodoviária", "bus", "bus_stop", "bus_station", "abrigo"],

    "trem": ["metrô", "estação", "ferrovia", "train", "railway"],
    "emprego": ["vaga", "trabalho", "rh", "agência", "job", "recruitment", "employment_agency"],
    "turismo": ["agência de turismo", "passeio", "guia", "tourism", "travel_agency"],
    "geladeira": ["refrigerador", "eletrodoméstico", "eletrodomestico", "appliance", "conserto", "assistência técnica"],
    "farmácia": ["farmacia", "drogaria", "medicamento"],
    "padaria": ["padaria", "padarie", "pastel", "confeitaria", "doce"],
}

def expand_search_term(term: str) -> list[str]:
    """Expande termo de busca com sinônimos."""
    term_lower = term.lower().strip()
    variations = {term_lower}
    
    # Remove acentos para comparação básica se necessário, mas aqui usaremos direto
    for key, synonyms in SYNONYM_MAP.items():
        if term_lower == key or term_lower in synonyms:
            variations.add(key)
            for s in synonyms:
                variations.add(s)
            # Não paramos aqui para permitir que um termo seja sinônimo de múltiplos grupos
            
    return list(variations)

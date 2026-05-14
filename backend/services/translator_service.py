import httpx
import logging
from ..core.vault import get_translation, save_translation


class TranslatorService:
    """Serviço de Tradução Automática com Cache em Banco (Tecnologia Hunter)."""
    
    def __init__(self):
        self.api_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=pt&tl=en&dt=t&q={text}"

    async def translate_to_english(self, text: str) -> str:
        if not text: return ""
        text = text.lower().strip()
        
        # 1. Verifica Cache (Vault)
        cached = get_translation(text)
        if cached:
            return cached
            
        # 2. Tradução Online (Fallback)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = self.api_url.format(text=text)
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Formato Google: [[["translated", "original", ...]]]
                    result = resp.json()
                    translated = result[0][0][0]
                    
                    # Salva no Banco para futuras buscas
                    save_translation(text, translated)
                    return translated
        except Exception as e:
            logging.error(f"Erro na tradução: {e}")
            
        return text # Fallback: retorna o original se falhar

translator = TranslatorService()

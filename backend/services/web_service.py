import httpx
import asyncio
import re
import random
import html
import urllib.parse
from typing import List, Dict

class WebSearchService:
    """Web Hunter - Busca hibrida Google + Bing com parser robusto."""

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        ]

    async def search_web_fallback(self, term: str, cep: str) -> List[Dict]:
        location = await self._get_city_from_cep(cep) or cep

        # Busca principal: Bing (mais tolerante a automacao)
        results = await self._bing_search(term, location)

        # Fallback: DuckDuckGo HTML
        if not results:
            results = await self._ddg_search(term, location)

        return results[:15]

    async def _bing_search(self, term: str, location: str) -> List[Dict]:
        query = f'"{term}" "{location}"'
        url = f"https://www.bing.com/search?q={query}&count=15"
        results = []
        try:
            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
            }
            async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Parser robusto: extrai todos os links e titulos do HTML
                    # Bing usa estrutura: <li class="b_algo"><h2><a href="...">titulo</a></h2>
                    titles = re.findall(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>([^<]+)<', resp.text)
                    snippets = re.findall(r'class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>', resp.text, re.DOTALL)
                    
                    for i, (link, title) in enumerate(titles[:15]):
                        # Filtra links internos do Bing
                        if "bing.com" in link and "search" in link:
                            continue
                            
                        # Limpa URLs incompletas do Bing
                        if link.startswith("//"):
                            link = "https:" + link
                        elif link.startswith("/"):
                            link = "https://www.bing.com" + link
                            
                        title_clean = html.unescape(re.sub(r'<[^>]+>', '', title).strip())
                        snippet = ""
                        if i < len(snippets):
                            snippet = html.unescape(re.sub(r'<[^>]+>', '', snippets[i]).strip()[:120])
                        
                        results.append({
                            "id": f"bing_{hash(link)}",
                            "name": title_clean,
                            "address": snippet + "...",
                            "website": link,
                            "search_url": url,
                            "phone": self._extract_phone(snippet),
                            "source": "Web Hunter (Bing)"
                        })
        except Exception as e:
            print(f"DEBUG: [BING ERROR] {e}")
        return results

    async def _ddg_search(self, term: str, location: str) -> List[Dict]:
        query = f"{term} {location}"
        url = f"https://html.duckduckgo.com/html/?q={query}"
        results = []
        try:
            headers = {
                "User-Agent": random.choice(self.user_agents),
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
            async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    titles = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)<', resp.text)
                    snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', resp.text)
                    for i, (link, title) in enumerate(titles[:10]):
                        snippet = snippets[i] if i < len(snippets) else ""
                        title_clean = html.unescape(title.strip())
                        snippet_clean = html.unescape(snippet.strip()[:120])
                        
                        # Extrai a URL real de redirecionamentos do DuckDuckGo
                        parsed = urllib.parse.urlparse(link)
                        qs = urllib.parse.parse_qs(parsed.query)
                        real_link = qs.get("uddg", [link])[0]
                        
                        if real_link.startswith("//"):
                            real_link = "https:" + real_link
                            
                        results.append({
                            "id": f"ddg_{hash(real_link)}",
                            "name": title_clean,
                            "address": snippet_clean + "...",
                            "website": real_link,
                            "search_url": url,
                            "phone": self._extract_phone(snippet),
                            "source": "Web Hunter (DuckDuckGo)"
                        })
        except Exception as e:
            print(f"DEBUG: [DDG ERROR] {e}")
        return results

    async def _get_city_from_cep(self, cep: str) -> str:
        if not cep or len(re.sub(r'\D', '', cep)) != 8:
            return ""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"https://viacep.com.br/ws/{cep}/json/")
                data = r.json()
                if "localidade" in data:
                    return f"{data['localidade']} - {data['uf']}"
        except:
            pass
        return ""

    def _extract_phone(self, text: str) -> str:
        pattern = r"\(?\d{2}\)?\s?\d{4,5}[-\s]?\d{4}"
        match = re.search(pattern, text)
        return match.group(0) if match else ""


web_hunter = WebSearchService()

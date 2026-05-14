import httpx
import asyncio

async def test():
    query = """
    [out:json];
    (
        node["shop"="supermarket"](around:5000,-23.6757595,-46.4817585);
        way["shop"="supermarket"](around:5000,-23.6757595,-46.4817585);
        relation["shop"="supermarket"](around:5000,-23.6757595,-46.4817585);
    );
    out center;
    """
    headers = {"User-Agent": "buscador-lojas"}
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post("https://overpass-api.de/api/interpreter", data=query, headers=headers)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Encontrados: {len(data.get('elements', []))}")
            else:
                print(f"Corpo: {resp.text}")
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(test())

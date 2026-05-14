import sys
import io
import os
import json
import subprocess
import re
import time
import hashlib
import math
import psutil
import gc
import threading
import signal

# --- BOOTSTRAP: Auto-Installer ---
# Usando bip32utils (pure python) para evitar erros de compilacao no Windows
# Adicionado psutil para controle de memoria e performance
REQUIRED_PACKAGES = ["rich", "requests", "ddgs", "base58", "beautifulsoup4", "mnemonic", "bip32utils", "psutil", "cloudscraper", "lxml"]
BLOCKCHAIN_LOG = "verificacao_balanco.txt"
DATABASE_FILE = "hunter_vault.db"
import sqlite3

def install_dependencies():
    for pkg in REQUIRED_PACKAGES:
        try:
            import_name = pkg
            if pkg == "beautifulsoup4": import_name = "bs4"
            elif pkg == "mnemonic": import_name = "mnemonic"
            elif pkg == "bip32utils": import_name = "bip32utils"
            __import__(import_name)
        except ImportError:
            print(f"[!] Modulo '{pkg}' nao encontrado. Instalando automaticamente...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
                print(f"[+] '{pkg}' instalado com sucesso.")
            except Exception as e:
                print(f"[X] Erro ao instalar '{pkg}': {e}")
                sys.exit(1)

install_dependencies()
# --- END BOOTSTRAP ---

import requests
import cloudscraper
import concurrent.futures
import base58
import random
import re
import json
import os
import time
import hashlib
from ddgs import DDGS
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from mnemonic import Mnemonic
from bip32utils import BIP32Key
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text

# Fix for Windows Console UTF-8
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Global Config
CONFIG_FILE = "keyhunter_config.json"
LOG_FILE = "encontradas.txt"
PROCURAREM_FILE = "procurarem.txt"
NAOPROCURAREM_FILE = "naoprocurarem.txt"
CUSTOM_DORKS_FILE = "custom_dorks.txt"
ACTIVITY_LOG = "activity_log.txt"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"

DEFAULT_CONFIG = {
    "low_memory_mode": True,
    "max_threads": 3,  # Reduzido para economizar memoria
    "scan_limit_kb": 256,  # Reduzido para evitar sobrecarga
    "spider_depth": 1,
    "refresh_hz": 2,  # Reduzido para menos atualizações UI
    "memory_threshold": 70,  # % de memoria para alerta
    "temp_cleanup_interval": 50,  # Limpar cache a cada N URLs
    "adaptive_performance": True,  # Ajustar performance dinamicamente
    "verbose_mode": False,
    "infinite_loop": False,
    "search_offset": 0 # Quantos resultados pular para escavar fundo
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f: json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f: return json.load(f)
    except: return DEFAULT_CONFIG

# Global Log Queue para a UI
UI_LOGS = []

def bootstrap_files():
    """Garante que todos os arquivos TXT necessários existam."""
    vituais = [
        PROCURAREM_FILE, NAOPROCURAREM_FILE, 
        CUSTOM_DORKS_FILE, ACTIVITY_LOG
    ]
    for arquivo in vituais:
        if not os.path.exists(arquivo):
            try:
                with open(arquivo, "w", encoding='utf-8') as f:
                    if arquivo == CUSTOM_DORKS_FILE:
                        f.write("# Adicione dorks aqui, uma por linha:\n")
                    else:
                        # Formato original que o usuário usa
                        f.write(f'{os.path.basename(arquivo).split(".")[0].capitalize()} = ""')
                # verbose_log ainda não está disponível aqui, usamos print
                print(f"[*] Arquivo recriado: {arquivo}")
            except: pass

config = load_config()
UI_ACTIVE = False # Flag para silenciar logs externos
bootstrap_files() # Garantir arquivos vitais
console = Console()

def verbose_log(msg, level="INFO"):
    """Saves to activity_log.txt and updates UI_LOGS"""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    full_msg = f"[{timestamp}] [{level}] {msg}"
    
    # Save to file
    try:
        with open(ACTIVITY_LOG, "a", encoding='utf-8') as f:
            f.write(full_msg + "\n")
    except: pass
    
    # Print to console (apenas se a interface NÃO estiver ativa)
    if not UI_ACTIVE:
        color = "cyan" if level == "INFO" else "red" if level == "ERROR" else "yellow"
        if level == "ALERT": color = "bold white on red"
        console.print(f"[{color}]{full_msg}[/{color}]")
    
    # Estilo especial para Alertas na UI
    display_msg = full_msg
    if level == "ALERT":
        display_msg = f"[bold white on red] 🔥 !!! SALDO ENCONTRADO !!! 🔥 [/bold white on red]\n{full_msg}"
        # Tenta tocar um som simples de beep no Windows se possível
        try: import winsound; winsound.Beep(1000, 500); winsound.Beep(1500, 500)
        except: pass

    # Adicionar à fila da UI para o TextArea
    UI_LOGS.append(display_msg)
    if len(UI_LOGS) > 100: UI_LOGS.pop(0)

def site_permite(url):
    """Verifica robots.txt."""
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(base)
        rp.read()
        return rp.can_fetch("*", url)
    except: return True

def delay_humano():
    """Simula comportamento humano."""
    time.sleep(random.uniform(0.5, 2.0))

def discover_sitemaps(domain):
    """Tenta localizar sitemaps."""
    return [f"https://{domain}/sitemap.xml", f"https://{domain}/sitemap_index.xml"]

def load_site_list(filename):
    """Loads sites from a semicolon separated quoted string format"""
    if not os.path.exists(filename): return set()
    try:
        with open(filename, "r", encoding='utf-8') as f:
            content = f.read().strip()
            # Procurarem = "site1";"site2"
            parts = re.findall(r'"([^"]*)"', content)
            return set(parts)
    except: return set()

def save_site_list(filename, sites, var_name):
    """Saves sites to a semicolon separated quoted string format"""
    try:
        quoted = ";".join([f'"{s}"' for s in sorted(list(sites)) if s])
        with open(filename, "w", encoding='utf-8') as f:
            f.write(f'{var_name} = {quoted}')
    except Exception as e:
        verbose_log(f"Erro ao salvar lista {filename}: {e}", "ERROR")

# Global Targets
TARGET_STRING = "5bCRZhiS5sEGMpmcRZdpAhmWLRfMmutGmPHtjVob"

mnemo = Mnemonic("english")
BIP39_WORDS = set(mnemo.wordlist)

# Dorks Lists - EXPANDED v3.0
WIF_DORKS = [
    # Pastebin & Paste Sites
    'site:pastebin.com "5H" OR "5J" OR "5K" OR "L" OR "K" "private key"',
    'site:pastebin.com "bitcoin" "private key" "WIF"',
    'site:gist.github.com "5H" OR "5J" OR "5K" OR "L" OR "K" "private key"',
    'site:controlc.com "private key" "bitcoin" "5"',
    'site:jsfiddle.net "private key" "bitcoin" "WIF"',
    
    # Code Repositories
    'site:github.com "5H" OR "5J" OR "5K" OR "L" OR "K" "private key" extension:txt',
    'site:github.com "bitcoin" "private key" "wallet.dat"',
    'site:github.com "dump" "private" "keys" "bitcoin"',
    'site:gitlab.com "5H" OR "5J" "bitcoin" "private"',
    'site:bitbucket.org "private key" "bitcoin" "WIF"',
    'site:sourceforge.net "private key" "bitcoin" "WIF"',
    'site:codepen.io "bitcoin" "private key" "wallet"',
    'site:gitea.com "5H" OR "5J" "bitcoin" "private key"',
    'site:gitlab.com "bitcoin" "private key" "WIF"',
    'site:bitbucket.org "bitcoin" "private key" "wallet.dat"',
    'site:codeberg.org "private key" "bitcoin" "WIF"',
    
    # Forums & Communities
    'site:bitcointalk.org "5" OR "private key"',
    'site:reddit.com "private key" "bitcoin" "WIF"',
    'site:steemit.com "bitcoin" "private key" "wallet"',
    'site:discord.com "private key" "bitcoin" "5"',
    'site:telegram.com "private key" "bitcoin" "channel"',
    'site:4chan.org "private key" "bitcoin" "WIF"',
    'site:8chan.net "private key" "bitcoin" "wallet"',
    'site:2chan.org "bitcoin" "private key" "WIF"',
    'site:bitcoinnova.org "private key" "bitcoin" "WIF"',
    'site:coindesk.com "private key" "bitcoin" "WIF"',
    'site:cryptocompare.com "private key" "bitcoin" "WIF"',
    
    # Academic & Research
    'site:arxiv.org "bitcoin" "private key" "vulnerability"',
    'site:ieeexplore.ieee.org "bitcoin" "private key" "ECDSA"',
    'site:researchgate.net "bitcoin" "private key" "cryptography"',
    
    # Pastes & Leaks
    'site:justpaste.it "bitcoin" "private key"',
    'site:hastebin.com "5" "private key" "bitcoin"',
    'site:dpaste.com "bitcoin" "WIF" "private"',
    'site:paste.ee "bitcoin" "private key" "wallet"',
    'site:paste.org "bitcoin" "private key" "WIF"',
    'site:0bin.net "bitcoin" "private key" "WIF"',
    'site:rentry.org "bitcoin" "private key" "wallet"',
    'site:nopaste.net "bitcoin" "private key" "WIF"',
    'site:ix.io "bitcoin" "private key" "WIF"',
    'site:cl1p.net "bitcoin" "private key" "WIF"',
    'site:anypaste.in "bitcoin" "private key" "WIF"',
    
    # Blockchain Explorers
    'site:blockchain.com "private key" "vulnerability"',
    'site: etherscan.io "private key" "bitcoin" -ethereum',
    'site:bscscan.com "private key" "bitcoin" -bnb',
    'site:polygonscan.com "private key" "bitcoin" -polygon',
    'site:explorer.btc.com "private key" "bitcoin"',
    'site:sochain.com "private key" "bitcoin"',
    'site:blockchair.com "private key" "bitcoin"',
    'site:mempool.space "private key" "bitcoin"',
    'site:chain.so "private key" "bitcoin"',
    'site:blockstream.info "private key" "bitcoin"',
    
    # General Search
    'intext:"private key" AND "5" AND "WIF" -wallet -buy -sell',
    'intext:"bitcoin" "private key" "dump" "leak"',
    'intext:"WIF" "private key" "bitcoin" "github"',
    'intext:"5K" OR "5H" OR "5J" "bitcoin" "private"',
    'intext:"private key" "bitcoin" "exposed"',
    'intext:"bitcoin" "private key" "leaked"',
    'intext:"bitcoin" "private key" "vulnerable"',
    'intext:"bitcoin" "private key" "compromised"',
    
    # File Sharing
    'site:mediafire.com "private key" "bitcoin" "wallet"',
    'site:dropbox.com "bitcoin" "private key" "txt"',
    'site:drive.google.com "private key" "bitcoin" "WIF"',
    'site:mega.nz "private key" "bitcoin" "wallet"',
    'site:onedrive.live "private key" "bitcoin" "WIF"',
    'site:icloud.com "private key" "bitcoin" "wallet"',
    
    # Dark Web (Onion links indexed)
    'intext:"private key" "bitcoin" "onion" "WIF"',
    'intext:"bitcoin" "leaked" "private" "keys"',
    
    # Social Media
    'site:twitter.com "private key" "bitcoin" "WIF"',
    'site:facebook.com "bitcoin" "private key" "wallet"',
]

SEED_DORKS = [
    # Paste Sites
    'site:pastebin.com "seed phrase" OR "recovery phrase" "abandon"',
    'site:pastebin.com "12 words" "bitcoin" "mnemonic"',
    'site:pastebin.com "24 words" "seed" "bitcoin"',
    'site:controlc.com "seed phrase" OR "mnemonic" "bitcoin"',
    'site:justpaste.it "mnemonic" "12 words" "bitcoin"',
    
    # Code Repositories
    'site:github.com "mnemonic" "english" extension:js OR extension:py',
    'site:github.com "seed" "phrase" "bitcoin" "BIP39"',
    'site:github.com "recovery" "mnemonic" "12 words"',
    'site:gitlab.com "mnemonic" "seed" "bitcoin"',
    'site:bitbucket.org "mnemonic" "bitcoin" "phrase"',
    
    # Forums & Communities
    'site:bitcointalk.org "seed" "phrase" "mnemonic"',
    'site:reddit.com "12 words" "seed" "bitcoin"',
    'site:steemit.com "mnemonic" "seed" "bitcoin"',
    'site:discord.com "seed phrase" "mnemonic" "bitcoin"',
    
    # Academic & Research
    'site:arxiv.org "mnemonic" "BIP39" "bitcoin"',
    'site:ieeexplore.ieee.org "seed" "phrase" "cryptography"',
    
    # General Search
    'intext:"12 words" AND "seed" AND "bitcoin" -buy -sell',
    'intext:"24 words" "mnemonic" "bitcoin" "seed"',
    'intext:"BIP39" "mnemonic" "seed" "phrase"',
    'intext:"recovery phrase" "bitcoin" "12 words"',
    'intext:"mnemonic" "english" "bitcoin" "seed"',
    
    # Wallet Specific
    'intext:"metamask" "seed phrase" "12 words"',
    'intext:"trust wallet" "mnemonic" "12 words"',
    'intext:"ledger" "recovery" "phrase" "24 words"',
    'intext:"trezor" "mnemonic" "seed" "bitcoin"',
    
    # File Sharing
    'site:mediafire.com "mnemonic" "seed" "bitcoin"',
    'site:dropbox.com "seed phrase" "bitcoin" "txt"',
    'site:drive.google.com "mnemonic" "12 words" "bitcoin"',
    
    # Leaks & Dumps
    'intext:"leaked" "mnemonic" "seed" "bitcoin"',
    'intext:"dump" "seed" "phrase" "bitcoin"',
    'intext:"exposed" "mnemonic" "bitcoin" "wallet"',
    
    # Social Media
    'site:twitter.com "seed phrase" "mnemonic" "bitcoin"',
    'site:facebook.com "recovery" "phrase" "bitcoin"',
    
    # Advanced Cryptography
    'intext:"entropy" "mnemonic" "BIP39" "bitcoin"',
    'intext:"brainwallet" "seed" "phrase" "bitcoin"',
    'intext:"deterministic" "wallet" "seed" "bitcoin"',
]

# Additional specialized dorks for different attack vectors
BLOCKCHAIN_DORKS = [
    'site:blockchain.com "vulnerable" "address" "private key"',
    'site:etherscan.io "private key" "leaked" -ethereum',
    'site:bscscan.com "private key" "leaked" -bnb',
    'site:polygonscan.com "private key" "leaked" -polygon',
]

WALLET_DUMP_DORKS = [
    'site:github.com "wallet.dat" "bitcoin" "private"',
    'site:pastebin.com "wallet.dat" "bitcoin" "dump"',
    'intext:"wallet.dat" "bitcoin" "private" "leaked"',
    'intext:"keystore" "ethereum" "private" "bitcoin"',
    'intext:"backup" "wallet" "private" "seed"',
]

# Crypto-specific dorks
CRYPTO_VULN_DORKS = [
    'intext:"ECDSA" "private key" "bitcoin" "vulnerability"',
    'intext:"nonce reuse" "bitcoin" "private key"',
    'intext:"side channel" "bitcoin" "private key"',
    'intext:"fault injection" "bitcoin" "private key"',
    'intext:"timing attack" "bitcoin"']

# --- CRYPTO HELPERS: Address Generation (Legacy, SegWit, Taproot) ---
import hashlib
import threading

def hash160(data):
    return hashlib.new('ripemd160', hashlib.sha256(data).digest()).digest()

def bech32_encode(hrp, data):
    """Encoding para SegWit/Bech32."""
    CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    def poly_mod(values):
        GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
        chk = 1
        for v in values:
            b = chk >> 25
            chk = ((chk & 0x1ffffff) << 5) ^ v
            for i in range(5):
                chk ^= GEN[i] if ((b >> i) & 1) else 0
        return chk

    def hrp_expand(hrp):
        return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]

    def create_checksum(hrp, data):
        values = hrp_expand(hrp) + data
        polymod = poly_mod(values + [0, 0, 0, 0, 0, 0]) ^ 1
        return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]

    combined = data + create_checksum(hrp, data)
    return hrp + "1" + "".join([CHARSET[d] for d in combined])

def convert_to_addr(priv_hex, compressed=True):
    """Gera 4 tipos de endereços BTC a partir de HEX."""
    try:
        key = BIP32Key.fromEntropy(bytes.fromhex(priv_hex))
        pub = key.PublicKey()
        addr_legacy = key.Address()
        
        # P2SH-P2WPKH (3...)
        p2wpkh_script = b'\x00\x14' + hash160(pub)
        p2sh_hash = hash160(p2wpkh_script)
        addr_p2sh = base58.b58encode_check(b'\x05' + p2sh_hash).decode()
        
        # Native SegWit (bc1q...)
        def convertbits(data, frombits, tobits, pad=True):
            acc = 0; bits = 0; ret = []; maxv = (1 << tobits) - 1
            for value in data:
                acc = (acc << frombits) | value
                bits += frombits
                while bits >= tobits:
                    bits -= tobits
                    ret.append((acc >> bits) & maxv)
            if pad and bits: ret.append((acc << (tobits - bits)) & maxv)
            return ret

        addr_bech32 = bech32_encode("bc", [0] + convertbits(hash160(pub), 8, 5))
        addr_taproot = bech32_encode("bc", [1] + convertbits(pub[1:33], 8, 5))
        
        return {"legacy": addr_legacy, "p2sh": addr_p2sh, "bech32": addr_bech32, "taproot": addr_taproot}
    except: return None

def extract_hex(text):
    """Caçador de Hexadecimais (32 a 64 chars)."""
    return list(set(re.findall(r'\b([a-fA-F0-9]{32,64})\b', text)))

class BalanceChecker(threading.Thread):
    """Motor paralelo de verificação de balanço."""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True

    def check(self, address):
        try:
            # Usando API pública robusta
            url = f"https://blockchain.info/rawaddr/{address}"
            resp = requests.get(url, timeout=7)
            if resp.status_code == 200:
                bal = resp.json().get("final_balance", 0) / 100000000
                return f"{bal:.8f} BTC"
            return "Erro 429/API" if resp.status_code == 429 else "Erro"
        except: return "Offline"

    def run(self):
        while self.running and not _shutdown_event.is_set():
            try:
                conn = sqlite3.connect(DATABASE_FILE, timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                cursor = conn.cursor()
                cursor.execute("SELECT wif, addr_legacy FROM audit WHERE balance = 'Pendente' LIMIT 10")
                rows = cursor.fetchall()
                conn.close()
                
                for wif, addr in rows:
                    if _shutdown_event.is_set(): return  # Sai imediatamente
                    res = self.check(addr)
                    if res == "Limit":
                        _shutdown_event.wait(timeout=60); break
                    
                    conn = sqlite3.connect(DATABASE_FILE, timeout=30)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE audit SET balance = ? WHERE wif = ?", (f"Saldo: {res}", wif))
                    conn.commit()
                    conn.close()
                    
                    if "Saldo" in res and "0.00000000" not in res:
                        verbose_log(f"FORTUNA! {addr} = {res}", "ALERT")
                    _shutdown_event.wait(timeout=5)  # Substituir time.sleep para ser interrompível
            except: pass
            _shutdown_event.wait(timeout=10)

def get_key_metadata(priv_key_hex):
    """
    Calculates power of 2 and returns formatted metadata.
    """
    try:
        int_val = int(priv_key_hex, 16)
        if int_val == 0: return "2^0", "0"
        power = int_val.bit_length() - 1
        return f"2^{power}", str(int_val)
    except:
        return "?", "?"

def priv_to_wif(priv_key_bytes, compressed=True):
    """
    Converts raw private key bytes to WIF.
    """
    prefix = b'\x80' + priv_key_bytes
    if compressed:
        prefix += b'\x01'
    return base58.b58encode_check(prefix).decode('utf-8')

def derive_wifs_from_mnemonic(phrase):
    """
    Derives compressed and uncompressed WIFs from a BIP39 mnemonic.
    Uses standard path m/44'/0'/0'/0/0 (BIP44)
    """
    try:
        seed = Mnemonic.to_seed(phrase)
        root = BIP32Key.fromEntropy(seed)
        # Caminho m/44'/0'/0'/0/0 (Hierarquia padrao)
        child = root.ChildKey(44 + 0x80000000).ChildKey(0 + 0x80000000).ChildKey(0 + 0x80000000).ChildKey(0).ChildKey(0)
        priv_bytes = child.PrivateKey()
        
        wif_c = priv_to_wif(priv_bytes, True)
        wif_u = priv_to_wif(priv_bytes, False)
        return wif_c, wif_u, priv_bytes.hex()
    except:
        return None, None, None

def validate_wif(key):
    try:
        if len(key) not in (51, 52) or key[0] not in ("5", "K", "L"): return False, None
        decoded = base58.b58decode_check(key)
        if decoded[0] != 0x80: return False, None
        raw_priv = decoded[1:33]
        return True, raw_priv.hex()
    except: return False, None

def extract_wif(text):
    """Extrai chaves WIF de múltiplas moedas (BTC, LTC, DOGE, DASH, etc.)."""
    # Prefixos: 5, K, L (BTC), 9, c (Testnet), 6, T (LTC), 6, Q (DOGE), 7, X (DASH)
    pattern = r'\b([5679KLQXcT][1-9A-HJ-NP-Za-km-z]{50,51})\b'
    found = re.findall(pattern, text)
    valid = []
    for w in found:
        try:
            # O base58.b58decode_check valida o checksum independente do prefixo da moeda
            decoded = base58.b58decode_check(w)
            # Se decodificou com sucesso, o checksum é válido matematicamente
            priv_hex = decoded[1:33].hex()
            valid.append((w, priv_hex))
        except: continue
    return valid

def extract_mnemonics(text):
    words = re.findall(r'[a-z]+', text.lower())
    valid_found = []
    i = 0
    while i < len(words):
        if words[i] in BIP39_WORDS:
            for lengths in [24, 21, 18, 15, 12]:
                if i + lengths <= len(words):
                    potential = words[i:i+lengths]
                    if all(w in BIP39_WORDS for w in potential):
                        phrase = " ".join(potential)
                        if mnemo.check(phrase):
                            valid_found.append(phrase)
                            i += lengths - 1
                            break
        i += 1
    return valid_found

def cleanup_duplicates():
    """
    Enhanced deduplication of LOG_FILE based on WIF keys and source URLs.
    Preserves line breaks and updates stats with WIF list.
    """
    if not os.path.exists(LOG_FILE): 
        verbose_log(f"Arquivo {LOG_FILE} não encontrado. Nada para limpar.")
        return
        
    verbose_log(f"Iniciando limpeza avançada em {LOG_FILE}...", "INFO")
    try:
        seen_entries = set()  # WIF + URL
        seen_wifs = {}        # {WIF: Power}
        cleaned_lines = []
        duplicates_removed = 0
        
        # Read file. Handle giant line corruption if any.
        with open(LOG_FILE, "r", encoding='utf-8') as f:
            content = f.read()
            
        # Robust splitting: find all bracketed timestamps
        pattern = r'(\[\w{3} \w{3} \d{1,2} \d{2}:\d{2}:\d{2} \d{4}\])'
        parts = re.split(pattern, content)
        
        raw_records = []
        current_record = ""
        for p in parts:
            if not p: continue
            if re.match(pattern, p):
                if current_record: raw_records.append(current_record.strip())
                current_record = p
            else:
                current_record += p
        if current_record: raw_records.append(current_record.strip())
        
        total_records = len(raw_records)
        
        for line in raw_records:
            if not line: continue
            
            # parts = [Timestamp, Power, IntVal, WIF, URL ...]
            sections = line.split(" | ")
            if len(sections) >= 4:
                pwr = sections[1].strip()
                wif = sections[3].strip()
                url = sections[4].strip() if len(sections) > 4 else "unknown"
                
                entry_key = f"{wif}|{url}"
                if entry_key not in seen_entries:
                    seen_entries.add(entry_key)
                    seen_wifs[wif] = pwr
                    cleaned_lines.append(line)
                else:
                    duplicates_removed += 1
            else:
                cleaned_lines.append(line)
        
        # Salvar arquivo limpo com novas linhas garantidas
        with open(LOG_FILE, "w", encoding='utf-8', newline='\n') as f:
            for line in cleaned_lines:
                f.write(line + '\n')
            
        # Stats file with WIF list
        stats_file = LOG_FILE.replace('.txt', '_stats.txt')
        with open(stats_file, 'w', encoding='utf-8') as f_stats:
            f_stats.write(f"Limpeza realizada: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f_stats.write(f"Total original: {total_records}\n")
            f_stats.write(f"Duplicatas removidas: {duplicates_removed}\n")
            f_stats.write(f"WIFs únicos: {len(seen_wifs)}\n")
            f_stats.write("\n--- LISTA DE WIFS ENCONTRADOS ---\n")
            for w, p in sorted(seen_wifs.items(), key=lambda item: item[1], reverse=True):
                f_stats.write(f"{w} | {p}\n")
            
        verbose_log(f"Limpeza concluída. {len(seen_wifs)} WIFs únicos.")
        
    except Exception as e:
        verbose_log(f"Erro na limpeza avançada: {e}", "ERROR")

# Evento global para sinalizar encerramento a todas as threads
_shutdown_event = threading.Event()

def signal_handler(sig, frame):
    console.print("\n[bold red][!] Interrupção detectada! Encerrando...[/bold red]")
    _shutdown_event.set()
    os._exit(0)  # Mata TODAS as threads instantaneamente, sem esperar cleanup

signal.signal(signal.SIGINT, signal_handler)
try:
    signal.signal(signal.SIGBREAK, signal_handler) # Ctrl+Break no Windows
except AttributeError:
    pass

class MemoryManager:
    def __init__(self, threshold=70):
        self.threshold = threshold
        self.cleanup_counter = 0
        
    def get_memory_usage(self):
        try:
            return psutil.virtual_memory().percent
        except:
            return 0
            
    def check_memory(self):
        usage = self.get_memory_usage()
        if usage > self.threshold:
            console.print(f"[red][!] ALTA MEMÓRIA: {usage:.1f}%[/red]")
            return False
        return True
        
    def force_cleanup(self):
        gc.collect()
        self.cleanup_counter += 1
        console.print(f"[yellow][*] Limpando memória (#{self.cleanup_counter})[/yellow]")

class MultiHunter:
    def __init__(self, mode, cfg):
        self.mode = mode
        self.cfg = cfg
        self.stats = {"urls": 0, "hits": 0, "errors": 0, "queue": 0, "queries": 0}
        self.found = []
        self.seen_urls = set()
        self.memory_manager = MemoryManager(cfg.get("memory_threshold", 70))
        self.url_count = 0
        
        # Define o termo de busca para os modos Alvo e Custom
        if mode == 'Alvo Especifico':
            self.target_term = TARGET_STRING
        elif mode in ('PrivKeys', 'Mnemonic Seeds', 'Wallet Dumps', 'Vulnerabilidades', 'Blockchain', 'Auto Discovery'):
            self.target_term = None
        else:
            self.target_term = mode # Modo Customizado (Opção 8)
        
        # Interface
        self.table = Table(title="Resultados Encontrados", expand=True)
        self.table.add_column("Pwr", style="cyan")
        self.table.add_column("WIF Key", style="green")
        self.table.add_column("Origem", style="dim")
        
        self.performance_mode = "adaptive" if cfg.get("adaptive_performance", True) else "fixed"
        self.dork_queue = [] # Fila dinâmica
        
        # Configuração compatível com a versão estável do Cloudscraper
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # Tenta configurar interpretador e delay se a versão suportar como atributos
        try:
            self.scraper.interpreter = 'native'
            self.scraper.delay = 5
        except:
            pass
        
        # Nome dinâmico do log
        termo_seguro = re.sub(r'[\\/*?:"<>|]', "", mode).strip().replace(" ", "_")
        self.custom_log_file = f"encontrado_{termo_seguro}.txt"
        self.last_ui_update = 0 # Para controle de flickering
        self.cached_progress = (0, 0, "[dim]----------[/dim]") # Cache da barra de progresso
        self.last_file_read = 0

    def is_wif_already_logged(self, wif):
        """Verifica duplicata no Banco de Dados SQLite."""
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM audit WHERE wif = ?", (wif,))
            exists = cursor.fetchone() is not None
            conn.close()
            return exists
        except: return False

    def save_hit(self, wif_input, priv_hex, url, note=""):
        pwr, _ = get_key_metadata(priv_hex)
        domain = urlparse(url).netloc
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Gerar AMBOS: C e U via lógica robusta
            wifs = generate_wif_pair(priv_hex)
            
            conn = sqlite3.connect(DATABASE_FILE, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            
            for tag in ["C", "U"]:
                w = wifs[tag]
                is_comp = (tag == "C")
                addrs = convert_to_addr(priv_hex, compressed=is_comp)
                
                if addrs:
                    cursor.execute("""
                        INSERT OR IGNORE INTO audit 
                        (wif, addr_legacy, addr_p2sh, addr_bech32, addr_taproot) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (w, addrs['legacy'], addrs['p2sh'], addrs['bech32'], addrs['taproot']))
            
            conn.commit()
            conn.close()
            verbose_log(f"HIT! Salvo WIF C/U no Banco: {wifs['C'][:10]}...", "SUCCESS")
        except Exception as e:
            verbose_log(f"Erro ao salvar no Banco: {e}", "ERROR")

        # Salvar log texto auxiliar
        log_path = self.custom_log_file if hasattr(self, 'custom_log_file') and self.custom_log_file else LOG_FILE
        line = f"[{timestamp}] | {pwr} | {wif_input} | {url} {note}\n"
        try:
            with open(log_path, "a", encoding='utf-8') as f: f.write(line)
        except: pass
        
        self.found.append({"wif": wif_input, "url": url, "pwr": pwr})
        self.stats["hits"] += 1

    def adaptive_thread_count(self):
        """Ajusta dinamicamente o numero de threads baseado no uso de memoria"""
        if not self.cfg.get("adaptive_performance", True):
            return self.cfg.get("max_threads", 3)
        
        mem_usage = self.memory_manager.get_memory_usage()
        if mem_usage > 80:
            return 1  # Muito alta memoria - reduzir drasticamente
        elif mem_usage > 60:
            return 2  # Alta memoria - modo conservador
        elif mem_usage > 40:
            return 3  # Media memoria - normal
        else:
            return 4  # Baixa memoria - pode aumentar

    def scan_page(self, url, depth=0):
        if url in self.seen_urls: return []
        self.seen_urls.add(url)
        self.stats["urls"] += 1
        self.url_count += 1
        domain = urlparse(url).netloc
        
        # Ignorar se estiver na lista negra
        naoprocurarem = load_site_list(NAOPROCURAREM_FILE)
        if domain in naoprocurarem: return []

        # Ética e Resiliência (Bypass Cloudflare + Robots)
        if not site_permite(url): return []
        delay_humano()

        try:
            verbose_log(f"Scaneando: {url}", "INFO")
            r = self.scraper.get(url, timeout=15, stream=True)
            if r.status_code == 200:
                content_type = r.headers.get('Content-Type', '').lower()
                is_xml = 'xml' in content_type or url.endswith('.xml')
                
                text = ""
                limit = self.cfg.get("scan_limit_kb", 256) * 1024
                for chunk in r.iter_content(chunk_size=8192, decode_unicode=True):
                    if chunk: text += chunk
                    if len(text) >= limit: break
                
                if is_xml:
                    soup = BeautifulSoup(text, 'xml')
                    locs = [l.text for l in soup.find_all('loc') if l.text]
                    for loc in locs[:100]:
                        if loc not in self.seen_urls: self.dork_queue.append(f"DIRECT_URL:{loc}")
                    return []
                
                # --- EXTRAÇÃO (FORA DO BLOCO XML) ---
                soup = BeautifulSoup(text, 'html.parser')
                clean_text = soup.get_text()
                
                # Detectar Hexadecimais em qualquer lugar (Texto e URL)
                potential_hex = extract_hex(clean_text) + extract_hex(url)
                for h in potential_hex:
                    try:
                        # Tentar converter hex em WIF C e U
                        key = BIP32Key.fromEntropy(bytes.fromhex(h))
                        wif_c = key.WalletImportFormat()
                        # Derivar chave sem compressão
                        key_u = BIP32Key.fromEntropy(bytes.fromhex(h))
                        key_u.compressed = False
                        wif_u = key_u.WalletImportFormat()
                        
                        self.save_hit(wif_c, h, url, "(Hex Detected)")
                        self.save_hit(wif_u, h, url, "(Hex Detected - Uncompressed)")
                    except: pass

                # 2. Se for modo de Sementes, extrair Mnemonics
                if self.mode == 'Mnemonic Seeds':
                    mnemonics = extract_mnemonics(text)
                    for m in mnemonics:
                        wif_c, wif_u, priv_hex = derive_wifs_from_mnemonic(m)
                        if wif_c: self.save_hit(wif_c, priv_hex, url, f"(Seed: {m[:20]}...)")
                
                # 3. Caso contrário, extrair WIF (PrivKeys, Alvo, Custom, etc.)
                else:
                    hits = extract_wif(text)
                    for wif, priv in hits: self.save_hit(wif, priv, url)
                    
                    # Verificação de alvo específico (Opção 7 ou Termo Customizado)
                    if self.target_term and self.target_term.lower() in clean_text.lower():
                        verbose_log(f"Termo '{self.target_term}' encontrado em {url}", "SUCCESS")
                        self.save_hit("TARGET_FOUND", "0", url, f"(Termo: {self.target_term})")
                
                # Spidering
                links = []
                if depth < self.cfg.get("spider_depth", 1):
                    for a in soup.find_all('a', href=True):
                        u = urljoin(url, a['href'])
                        parsed_u = urlparse(u)
                        if parsed_u.scheme in ('http', 'https') and parsed_u.netloc == domain:
                            links.append(u)
                return list(set(links))
            else:
                self.stats["errors"] += 1
        except Exception as e:
            self.stats["errors"] += 1
        return []
    def process_single_dork(self, q, max_results):
        """Processa dork com Rotação Inteligente de Blocos."""
        is_direct = q.startswith("DIRECT_URL:")
        target = q.replace("DIRECT_URL:", "") if is_direct else q
        
        # 1. Recuperar último offset do banco para este 'bloco'
        current_offset = 0
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT last_offset FROM search_blocks WHERE dork = ?", (q,))
            row = cursor.fetchone()
            if row: current_offset = row[0]
            conn.close()
        except: pass

        try:
            if is_direct:
                self.scan_page(target, 0)
            else:
                time.sleep(random.uniform(0.1, 1.0))
                with DDGS() as ddgs:
                    limit = 100 if "site:" in q else max_results
                    total_to_fetch = limit + current_offset
                    results = list(ddgs.text(q, max_results=total_to_fetch))
                    
                    if len(results) > current_offset:
                        results = results[current_offset:]
                    
                    # 2. Atualizar offset no banco para a próxima pesquisa (Bloco seguinte)
                    new_offset = current_offset + len(results)
                    try:
                        conn = sqlite3.connect(DATABASE_FILE)
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO search_blocks (dork, last_offset) VALUES (?, ?)", (q, new_offset))
                        conn.commit()
                        conn.close()
                    except: pass

                    urls = [res['href'] for res in results]
                    current_threads = self.adaptive_thread_count()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=current_threads) as ex:
                        futures = {ex.submit(self.scan_page, u, 0): u for u in urls}
                        for f in concurrent.futures.as_completed(futures):
                            try:
                                depth1 = f.result()
                                if depth1: ex.map(lambda u: self.scan_page(u, 1), depth1[:10]) 
                            except: pass
        except Exception as e:
            err_str = str(e)
            # Erros de rede são esperados, logamos de forma concisa
            if "error sending request" in err_str.lower() or "connection" in err_str.lower() or "timeout" in err_str.lower():
                verbose_log(f"Rede indisponível para query: {q[:40]}...", "WARN")
            else:
                verbose_log(f"Falha na query {q[:30]}: {err_str[:80]}", "ERROR")

    def run(self, dorks_input, max_results=50):
        global UI_ACTIVE
        UI_ACTIVE = True 
        
        # Guardar dorks iniciais para o loop infinito
        initial_dorks = list(dorks_input)
        
        while True:
            self.dork_queue = list(initial_dorks)
            
            # Adicionar dorks customizadas se existirem
            if os.path.exists(CUSTOM_DORKS_FILE):
                try:
                    with open(CUSTOM_DORKS_FILE, 'r', encoding='utf-8') as f:
                        custom = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                        self.dork_queue.extend(custom)
                except: pass

            layout = make_layout()
            title_str = f"CanalQb - BITCOIN {'WIF' if self.mode=='wif' else 'SEED'} HUNTER v2.5"
            layout["header"].update(Panel(Text(title_str, style="bold cyan", justify="center"), border_style="blue"))
            
            with Live(layout, refresh_per_second=self.cfg.get("refresh_hz", 2), screen=False) as live:
                # Processar dorks em lotes de 3 para maior cobertura paralela
                while self.dork_queue:
                    batch = []
                    for _ in range(3):
                        if self.dork_queue: batch.append(self.dork_queue.pop(0))
                    
                    if not batch: break
                    
                    self.stats["queries"] += len(batch)
                    self.stats["queue"] = len(self.dork_queue)
                    
                    # Log dos termos atuais
                    batch_display = " | ".join([b.replace("DIRECT_URL:", "")[:30] for b in batch])
                    layout["footer"].update(Panel(Text(f"Lote Atual: {batch_display}", style="cyan"), title="Status"))

                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as dork_ex:
                        dork_futures = {dork_ex.submit(self.process_single_dork, d, max_results): d for d in batch}
                        for df in concurrent.futures.as_completed(dork_futures):
                            try: df.result()
                            except: pass
                            self.update_ui(layout, len(initial_dorks))
            
            if not self.cfg.get("infinite_loop", False):
                break
        
        cleanup_duplicates(self.custom_log_file)
        UI_ACTIVE = False # Desativa modo interface ao terminar

    def update_ui(self, layout, total_q):
        # Limitador de FPS para evitar flickering (máx 2 atualizações por segundo)
        now = time.time()
        if now - self.last_ui_update < 0.5:
            return
        self.last_ui_update = now

        s = self.stats
        mem_usage = self.memory_manager.get_memory_usage()
        
        # Calcular progresso do Banco de Dados SQLite (Cache de 5 seg)
        pct, total_verify, prog_bar = self.cached_progress
        if now - self.last_file_read > 5:
            try:
                conn = sqlite3.connect(DATABASE_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), SUM(CASE WHEN balance != 'Pendente' THEN 1 ELSE 0 END) FROM audit")
                total_verify, concluidos = cursor.fetchone()
                conn.close()
                
                if total_verify and total_verify > 0:
                    pct = (concluidos / total_verify) * 100
                    filled = int(pct / 10)
                    prog_bar = f"[{'█' * filled}{'-' * (10 - filled)}]"
                self.cached_progress = (pct or 0, total_verify or 0, prog_bar)
                self.last_file_read = now
            except: pass

        stats_txt = (f"Consultas: {s['queries']}\n"
                   f"URLs: {s['urls']}\n"
                   f"Hits: [green]{s['hits']}[/]\n"
                   f"Erros: [red]{s['errors']}[/]\n"
                   f"Memória: {mem_usage:.1f}%\n\n"
                   f"Verificação Blockchain:\n"
                   f"{prog_bar} {pct:.1f}%\n"
                   f"Total: {total_verify} chaves")
        
        layout["side"].update(Panel(stats_txt, title="Dashboard", border_style="magenta"))
        
        # Console de Status (TextArea com limite de 6 linhas)
        log_lines = [line for line in UI_LOGS if "[ERROR]" in line or "[SUCCESS]" in line or "[INFO]" in line]
        console_content = "\n".join(log_lines[-6:])
        
        main_content = Table.grid(expand=True)
        main_content.add_row(Panel(Text.from_markup(console_content), title="Console de Status", border_style="cyan", height=8))
        
        if self.found:
            self.table = Table(expand=True, box=None)
            self.table.add_column("Pwr", style="cyan", width=5)
            self.table.add_column("WIF", style="green")
            for h in self.found[-5:]:
                self.table.add_row(h["pwr"], h["wif"][:40] + "...")
            main_content.add_row(Panel(self.table, title="Últimos Hits", border_style="green"))
            
        layout["main"].update(main_content)

def make_layout() -> Layout:
    l = Layout()
    l.split_column(Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3))
    l["body"].split_row(Layout(name="main", ratio=2), Layout(name="side", ratio=1))
    return l

def settings():
    global config
    while True:
        console.clear()
        console.print("[bold cyan]=== CanalQb CONFIGURACOES v2.0 ===[/]\n")
        console.print(f"1. Threads: {config['max_threads']}")
        console.print(f"2. Limite Site (KB): {config['scan_limit_kb']}")
        console.print(f"3. Profundidade Spider: {config['spider_depth']}")
        console.print(f"4. Modo Verbose: [{'LIGADO' if config.get('verbose_mode') else 'DESLIGADO'}]")
        console.print(f"5. Loop Infinito: [{'LIGADO' if config.get('infinite_loop') else 'DESLIGADO'}]")
        console.print(f"6. Salto de Busca (Offset): {config.get('search_offset', 0)}")
        console.print("7. Salvar e Voltar")
        
        op = console.input("\nOpcao: ")
        if op == "1": config["max_threads"] = int(console.input("Valor: ") or config["max_threads"])
        elif op == "2": config["scan_limit_kb"] = int(console.input("Valor: ") or config["scan_limit_kb"])
        elif op == "3": config["spider_depth"] = int(console.input("Valor: ") or config["spider_depth"])
        elif op == "4": config["verbose_mode"] = not config.get("verbose_mode", False)
        elif op == "5": config["infinite_loop"] = not config.get("infinite_loop", False)
        elif op == "6":
            try:
                val = int(console.input("Tamanho do bloco de busca (ex: 1000): ") or 0)
                config["search_offset"] = max(0, val)
                console.print(f"[green]Bloco definido: {config['search_offset']} resultados por janela[/]")
            except ValueError:
                console.print("[red]Valor inválido. Use um número inteiro positivo.[/]")

        elif op == "7": 
            with open(CONFIG_FILE, "w") as f: json.dump(config, f, indent=4)
            break

def auto_discovery_mode():
    """Modo especial que usa a lista procurarem.txt para gerar dorks"""
    sites = load_site_list(PROCURAREM_FILE)
    if not sites:
        console.print("[yellow][!] A lista procurarem.txt está vazia. Adicione sites manualment ou use os outros buscadores primeiro.[/yellow]")
        time.sleep(2)
        return
        
    custom_dorks = []
    # Usar termos básicos + cada site da lista
    base_terms = ['"5H" OR "5J" OR "5K" OR "L" OR "K" "private key"', '"seed phrase" "12 words"']
    for s in sites:
        for t in base_terms:
            custom_dorks.append(f"site:{s} {t}")
            
    verbose_log(f"Iniciando Auto-Discovery com {len(sites)} sites e {len(custom_dorks)} queries.")
    MultiHunter('Auto Discovery', config).run(custom_dorks)

def generate_wif_pair(priv_hex):
    """Gera par WIF (Compressed e Uncompressed) de forma robusta."""
    def to_wif(hex_val, compressed=False, prefix="80"):
        payload = bytes.fromhex(prefix + hex_val)
        if compressed: payload += b'\x01'
        first_sha = hashlib.sha256(payload).digest()
        checksum = hashlib.sha256(first_sha).digest()[:4]
        return base58.b58encode(payload + checksum).decode()
    return {
        "C": to_wif(priv_hex, True, "80"),
        "U": to_wif(priv_hex, False, "80")
    }

if __name__ == "__main__":
    # 1. Inicializar arquivos e banco de dados
    bootstrap_files()

    # 2. Iniciar motor de verificação de balanço em segundo plano
    checker = BalanceChecker()
    checker.daemon = True  # Thread daemon: encerra automaticamente com o processo
    checker.start()

    while True:
        console.clear()
        console.print("[bold cyan]*** CanalQb - BITCOIN HUNTER MULTI-MODE v2.5 ***[/]\n")
        console.print("1. [bold green]Buscador de Chaves WIF[/] (PrivKeys)")
        console.print("2. [bold yellow]Buscador de Mnemonic Seeds[/] (12/24 Palavras)")
        console.print("3. [bold blue]Buscador de Wallet Dumps[/] (wallet.dat)")
        console.print("4. [bold magenta]Buscador de Vulnerabilidades[/] (Crypto)")
        console.print("5. [bold red]Buscador de Blockchain[/] (Explorers)")
        console.print("6. [bold white]Auto-Discovery (Lista TXT)[/]")
        console.print("7. [bold cyan]Buscar Alvo Específico[/] (Chave Global)")
        console.print("8. [bold yellow]Busca Customizada[/] (Termo livre)")
        console.print("9. Configurações")
        console.print("0. Sair")
        
        c = console.input("\nSua escolha: ")
        if c == "1": MultiHunter('PrivKeys', config).run(WIF_DORKS)
        elif c == "2": MultiHunter('Mnemonic Seeds', config).run(SEED_DORKS)
        elif c == "3": MultiHunter('Wallet Dumps', config).run(WALLET_DUMP_DORKS)
        elif c == "4": MultiHunter('Vulnerabilidades', config).run(CRYPTO_VULN_DORKS)
        elif c == "5": MultiHunter('Blockchain', config).run(BLOCKCHAIN_DORKS)
        elif c == "6": auto_discovery_mode()
        elif c == "7": 
            dorks = [f'"{TARGET_STRING}"']
            procurarem = load_site_list(PROCURAREM_FILE)
            for s in list(procurarem)[:20]: dorks.append(f'site:{s} "{TARGET_STRING}"')
            MultiHunter('Alvo Especifico', config).run(dorks)
        elif c == "8":
            term = console.input("\nDigite o termo de busca: ")
            if term:
                dorks = [term]
                procurarem = load_site_list(PROCURAREM_FILE)
                for s in list(procurarem)[:20]: dorks.append(f'site:{s} "{term}"')
                hunter = MultiHunter(term, config)
                hunter.run(dorks)
        elif c == "9": settings()
        elif c == "0": break
        console.input("\nEnter para voltar...")

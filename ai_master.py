# =============================================================================
#  ai_master.py — Narrativa generada por Ollama (modelo local, sin API key)
# =============================================================================

import threading
import urllib.request
import urllib.error
import json

# ── Configuración Ollama ──────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "llama3.2:1b"   # cambia a "llama3.2", "mistral", "gemma2" si usas otro

# ── Prompts del sistema ───────────────────────────────────────────────────────

SYSTEM_ES = """Eres el Dungeon Master de un juego de rol de texto. Tu trabajo es:
1. Narrar la historia de forma dramática, inmersiva y en ESPAÑOL
2. Responder a las acciones del jugador con consecuencias interesantes
3. Generar enemigos, tesoros y eventos sorpresa
4. Mantener la tensión y el drama
5. Ser creativo pero coherente con el mundo establecido

Reglas importantes:
- Respuestas CORTAS (máx 4 oraciones) — el jugador lee en pantalla pequeña
- Siempre termina describiendo qué opciones tiene el jugador (implícitas en los gestos)
- Cuando el jugador ataca, describe el combate vívidamente
- Cuando lanza dados, incorpora el resultado en la narrativa
- Si el jugador huye, describe las consecuencias
- Si usa magia, describe efectos espectaculares
- NUNCA respondas en inglés si el sistema está en español

Gestos disponibles para el jugador:
Puno cerrado = ATACAR | Mano abierta = DEFENDER | Indice arriba = LANZAR DADO
Pellizco = INVENTARIO | Dos dedos V = HUIR | Shaka = MAGIA"""

SYSTEM_EN = """You are the Dungeon Master of a text role-playing game. Your job is to:
1. Narrate the story dramatically and immersively in ENGLISH
2. Respond to player actions with interesting consequences
3. Generate enemies, treasures and surprise events
4. Maintain tension and drama
5. Be creative but consistent with the established world

Important rules:
- SHORT responses (max 4 sentences) — player reads on a small screen
- Always end by implying what options the player has
- When the player attacks, describe combat vividly
- When dice are rolled, incorporate the result into the narrative
- If the player flees, describe the consequences
- If magic is used, describe spectacular effects
- ALWAYS respond in English

Available gestures for the player:
Fist = ATTACK | Open hand = DEFEND | Index finger = ROLL DICE
Pinch = INVENTORY | Two fingers V = FLEE | Shaka = MAGIC"""


def _system_prompt(language: str) -> str:
    return SYSTEM_ES if language == "es" else SYSTEM_EN


# ── Textos de acciones ────────────────────────────────────────────────────────

ACTION_TEXTS = {
    "es": {
        "ATTACK":    lambda r, d, w: f"[ATAQUE con {w['name'] if w else 'puños'} | Dado: {r}/20 | Daño: {d}]",
        "DEFEND":    lambda r, b, s: f"[DEFENSA con {s['name'] if s else 'postura'} | Dado: {r}/20 | Bloqueado: {b}]",
        "DICE":      lambda r:       f"[DADO LANZADO: {r}/20]",
        "MAGIC":     lambda r, d, t: f"[MAGIA con {t['name'] if t else 'voluntad'} | Dado: {r}/20 | Daño magico: {d}]",
        "FLEE":      lambda r, s:    f"[HUIDA | Dado: {r}/20 | {'Escapo!' if s else 'Fallo el escape'}]",
        "INVENTORY": lambda items:   f"[INVENTARIO: {items}]",
        "NO_MANA":   "No tienes mana suficiente para lanzar un hechizo.",
        "DEAD":      "Has caido en combate. Tu aventura termina aqui...",
        "INTRO_PROMPT": lambda name, cls, setting: (
            f"El jugador se llama {name}, es un {cls}. "
            f"La ambientacion es: {setting}. "
            f"Comienza la aventura con una escena de apertura epica y presenta el primer desafio."
        ),
        "SETTINGS": [
            "Fantasia medieval oscura con dragones y mazmorras antiguas",
            "Sci-Fi espacial con alienígenas y naves estelares",
            "Horror gotico con mansiones encantadas y no-muertos",
            "Mundo post-apocaliptico con mutantes y ruinas",
            "Mundo submarino con criaturas abisales y civilizaciones perdidas",
        ],
    },
    "en": {
        "ATTACK":    lambda r, d, w: f"[ATTACK with {w['name'] if w else 'fists'} | Roll: {r}/20 | Damage: {d}]",
        "DEFEND":    lambda r, b, s: f"[DEFENSE with {s['name'] if s else 'stance'} | Roll: {r}/20 | Blocked: {b}]",
        "DICE":      lambda r:       f"[DICE ROLLED: {r}/20]",
        "MAGIC":     lambda r, d, t: f"[MAGIC with {t['name'] if t else 'willpower'} | Roll: {r}/20 | Magic damage: {d}]",
        "FLEE":      lambda r, s:    f"[FLEE | Roll: {r}/20 | {'Escaped!' if s else 'Failed to escape'}]",
        "INVENTORY": lambda items:   f"[INVENTORY: {items}]",
        "NO_MANA":   "You don't have enough mana to cast a spell.",
        "DEAD":      "You have fallen in battle. Your adventure ends here...",
        "INTRO_PROMPT": lambda name, cls, setting: (
            f"The player's name is {name}, they are a {cls}. "
            f"The setting is: {setting}. "
            f"Start the adventure with an epic opening scene and present the first challenge."
        ),
        "SETTINGS": [
            "Dark medieval fantasy with dragons and ancient dungeons",
            "Space sci-fi with aliens and starships",
            "Gothic horror with haunted mansions and undead",
            "Post-apocalyptic world with mutants and ruins",
            "Underwater world with abyssal creatures and lost civilizations",
        ],
    }
}


# ── Llamada a Ollama ──────────────────────────────────────────────────────────

def _call_ollama(messages: list) -> str:
    """Llama a la API local de Ollama y retorna el texto generado."""
    payload = json.dumps({
        "model":    MODEL,
        "messages": messages,
        "stream":   False,
        "options": {
            "temperature": 0.85,
            "num_predict": 200,   # equivale a max_tokens
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data    = payload,
        headers = {"Content-Type": "application/json"},
        method  = "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["message"]["content"].strip()
    except urllib.error.URLError as e:
        return (f"[Error: Ollama no esta corriendo. "
                f"Abre una terminal y ejecuta: ollama serve] ({e})")
    except Exception as e:
        return f"[Error inesperado: {e}]"


# ── Clase principal ───────────────────────────────────────────────────────────

class AIMaster:

    def __init__(self, language: str = "es"):
        self.language  = language
        self.last_text = ""
        self.is_typing = False

    def set_language(self, language: str):
        self.language = language

    def _async_call(self, messages: list, callback=None):
        """Llama a Ollama en un hilo separado para no bloquear la UI."""
        def run():
            self.is_typing = True
            text = _call_ollama(messages)
            self.is_typing = False
            self.last_text = text
            if callback:
                callback(text)
        threading.Thread(target=run, daemon=True).start()

    # ── Inicio del juego ──────────────────────────────────────────────────────

    def start_game(self, state, callback=None):
        import random
        texts   = ACTION_TEXTS[self.language]
        setting = random.choice(texts["SETTINGS"])
        state.setting = setting

        intro = texts["INTRO_PROMPT"](
            state.player_name, state.player_class, setting
        )
        messages = [
            {"role": "system", "content": _system_prompt(self.language)},
            {"role": "user",   "content": intro},
        ]
        self._async_call(messages, callback)

    # ── Acción del jugador ────────────────────────────────────────────────────

    def player_action(self, gesture: str, action_result: dict,
                      history: list, state, callback=None):
        texts = ACTION_TEXTS[self.language]

        # Construir descripción de la acción
        action_desc = ""
        if gesture == "ATTACK":
            r, d, w = action_result["roll"], action_result["damage"], action_result.get("weapon")
            action_desc = texts["ATTACK"](r, d, w)
        elif gesture == "DEFEND":
            r, b, s = action_result["roll"], action_result["blocked"], action_result.get("shield")
            action_desc = texts["DEFEND"](r, b, s)
        elif gesture == "DICE":
            action_desc = texts["DICE"](action_result["roll"])
        elif gesture == "MAGIC":
            if not action_result.get("success"):
                self.last_text = texts["NO_MANA"]
                if callback: callback(self.last_text)
                return
            r, d, t = action_result["roll"], action_result["damage"], action_result.get("tome")
            action_desc = texts["MAGIC"](r, d, t)
        elif gesture == "FLEE":
            r, s = action_result["roll"], action_result["success"]
            action_desc = texts["FLEE"](r, s)
        elif gesture == "INVENTORY":
            items = state.get_inventory_text()
            self.last_text = texts["INVENTORY"](items)
            if callback: callback(self.last_text)
            return

        # Estado actual
        status = state.get_status_summary()
        lang   = self.language
        full_msg = (f"{action_desc}\n[Estado: {status}]" if lang == "es"
                    else f"{action_desc}\n[Status: {status}]")

        # Construir historial para Ollama
        messages = [{"role": "system", "content": _system_prompt(self.language)}]
        messages += history[-12:]
        messages.append({"role": "user", "content": full_msg})

        self._async_call(messages, callback)
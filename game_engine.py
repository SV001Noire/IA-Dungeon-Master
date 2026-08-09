# =============================================================================
#  game_engine — Motor de estado del AI Dungeon Master
# =============================================================================

import random
from dataclasses import dataclass, field
from typing import List, Optional

# ── Constantes
MAX_HP        = 100
STARTING_HP   = 100
MAX_MANA      = 50
STARTING_MANA = 50
MANA_PER_TURN = 5

STARTING_INVENTORY = [
    {"name": "Espada corta",   "type": "weapon", "power": 8,  "emoji": "⚔️"},
    {"name": "Escudo de madera","type": "armor",  "power": 5,  "emoji": "🛡️"},
    {"name": "Poción de vida",  "type": "potion", "power": 30, "emoji": "🧪"},
    {"name": "Tomo arcano",     "type": "magic",  "power": 15, "emoji": "📖"},
]

DICE_SIDES = 20   # D20 clásico de D&D


@dataclass
class GameState:
    # Personaje
    player_name:  str = "Aventurero"
    player_class: str = "Guerrero"
    hp:           int = STARTING_HP
    max_hp:       int = MAX_HP
    mana:         int = STARTING_MANA
    max_mana:     int = MAX_MANA
    level:        int = 1
    xp:           int = 0

    # Juego
    turn:            int  = 0
    language:        str  = "es"     # "es" o "en"
    setting:         str  = ""       # generado por la IA al inicio
    alive:           bool = True
    in_combat:       bool = False
    show_inventory:  bool = False

    # Historia
    history:     List[dict] = field(default_factory=list)
    last_action: str        = ""
    last_result: str        = ""
    last_roll:   Optional[int] = None

    # Inventario
    inventory: List[dict] = field(default_factory=lambda: list(STARTING_INVENTORY))

    def __post_init__(self):
        self.inventory = [dict(i) for i in STARTING_INVENTORY]


class GameEngine:

    def __init__(self):
        self.state = GameState()

    def new_game(self, player_name: str, player_class: str, language: str):
        self.state = GameState(
            player_name  = player_name,
            player_class = player_class,
            language     = language,
        )

    # ── Acciones

    def roll_dice(self, sides: int = DICE_SIDES) -> int:
        result = random.randint(1, sides)
        self.state.last_roll = result
        return result

    def attack(self) -> dict:
        roll    = self.roll_dice()
        weapon  = self._get_item("weapon")
        power   = weapon["power"] if weapon else 5
        damage  = max(1, int(power * (roll / DICE_SIDES) * 1.5))
        self.state.turn += 1
        self.state.last_action = "ATTACK"
        return {"roll": roll, "damage": damage, "weapon": weapon}

    def defend(self) -> dict:
        roll     = self.roll_dice()
        shield   = self._get_item("armor")
        power    = shield["power"] if shield else 3
        blocked  = max(0, int(power * (roll / DICE_SIDES) * 2))
        self.state.turn += 1
        self.state.last_action = "DEFEND"
        return {"roll": roll, "blocked": blocked, "shield": shield}

    def use_magic(self) -> dict:
        cost = 10
        if self.state.mana < cost:
            return {"success": False, "reason": "no_mana"}
        roll  = self.roll_dice()
        tome  = self._get_item("magic")
        power = tome["power"] if tome else 10
        dmg   = max(1, int(power * (roll / DICE_SIDES) * 2))
        self.state.mana -= cost
        self.state.turn += 1
        self.state.last_action = "MAGIC"
        return {"success": True, "roll": roll, "damage": dmg, "tome": tome}

    def flee(self) -> dict:
        roll    = self.roll_dice()
        success = roll > 10
        self.state.turn += 1
        self.state.in_combat = not success
        self.state.last_action = "FLEE"
        return {"roll": roll, "success": success}

    def use_potion(self) -> dict:
        potion = self._get_item("potion")
        if not potion:
            return {"success": False}
        heal = potion["power"]
        self.state.hp = min(self.state.max_hp, self.state.hp + heal)
        self.state.inventory.remove(potion)
        return {"success": True, "heal": heal, "potion": potion}

    def take_damage(self, amount: int):
        self.state.hp = max(0, self.state.hp - amount)
        if self.state.hp == 0:
            self.state.alive = False

    def gain_xp(self, amount: int):
        self.state.xp += amount
        if self.state.xp >= self.state.level * 100:
            self.state.level  += 1
            self.state.max_hp += 10
            self.state.hp      = min(self.state.hp + 10, self.state.max_hp)
            self.state.max_mana += 5
            return True   # level up
        return False

    def restore_mana(self):
        self.state.mana = min(self.state.max_mana,
                              self.state.mana + MANA_PER_TURN)

    def add_to_history(self, role: str, content: str):
        self.state.history.append({"role": role, "content": content})
        # Mantener historial razonable para el contexto de la IA
        if len(self.state.history) > 20:
            self.state.history = self.state.history[-20:]

    # ── Helpers

    def _get_item(self, item_type: str):
        for item in self.state.inventory:
            if item["type"] == item_type:
                return item
        return None

    def get_status_summary(self) -> str:
        s = self.state
        lang = s.language
        if lang == "es":
            return (f"HP: {s.hp}/{s.max_hp} | Maná: {s.mana}/{s.max_mana} | "
                    f"Nivel: {s.level} | Turno: {s.turn}")
        else:
            return (f"HP: {s.hp}/{s.max_hp} | Mana: {s.mana}/{s.max_mana} | "
                    f"Level: {s.level} | Turn: {s.turn}")

    def get_inventory_text(self) -> str:
        if not self.state.inventory:
            return "— vacío —" if self.state.language == "es" else "— empty —"
        return "  ".join(
            f"{i['emoji']} {i['name']} (+{i['power']})"
            for i in self.state.inventory
        )

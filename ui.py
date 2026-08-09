# =============================================================================
# Overlay visual del AI Dungeon Master
# =============================================================================


import cv2
import numpy as np

# ── Colores BGR ───────────────────────────────────────────────────────────────
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (140, 140, 140)
DGRAY = (30, 30, 30)
GREEN = (60, 200, 80)
RED = (60, 60, 210)
GOLD = (30, 200, 215)
PURPLE = (200, 80, 180)
BLUE = (220, 140, 40)
ORANGE = (30, 140, 255)
CYAN = (230, 210, 50)

# Colores por gesto
GESTURE_COLORS = {
    "ATTACK": RED,
    "DEFEND": BLUE,
    "DICE": GOLD,
    "INVENTORY": GREEN,
    "FLEE": ORANGE,
    "MAGIC": PURPLE,
    None: GRAY,
}

GESTURE_EMOJIS = {
    "ATTACK": "ATACAR",
    "DEFEND": "DEFENDER",
    "DICE": "DADO",
    "INVENTORY": "INVENTARIO",
    "FLEE": "HUIR",
    "MAGIC": "MAGIA",
    None: "...",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _panel(frame, x1, y1, x2, y2, color=DGRAY, alpha=0.72):
    sub = frame[max(0, y1):min(frame.shape[0], y2),
          max(0, x1):min(frame.shape[1], x2)]
    if sub.size == 0: return
    rect = np.full_like(sub, color)
    cv2.addWeighted(rect, alpha, sub, 1 - alpha, 0, sub)
    frame[max(0, y1):min(frame.shape[0], y2),
    max(0, x1):min(frame.shape[1], x2)] = sub


def _text(frame, text, x, y, scale=0.6, color=WHITE,
          thickness=1, font=cv2.FONT_HERSHEY_SIMPLEX):
    cv2.putText(frame, text, (x, y), font, scale, BLACK,
                thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), font, scale, color,
                thickness, cv2.LINE_AA)


def _bar(frame, x, y, w, h, value, max_val, color, bg=(50, 50, 50)):
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg, -1)
    fill = int(w * max(0.0, min(1.0, value / max(1, max_val))))
    if fill > 0:
        cv2.rectangle(frame, (x, y), (x + fill, y + h), color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), GRAY, 1)


def _clean_text(text):
    """Reemplaza caracteres especiales que OpenCV no renderiza bien."""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
        '¿': '?', '¡': '!', '«': '"', '»': '"',
        '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
        '**': '', '*': '',  # quitar markdown bold que genera llama
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _wrap_text_lines(text, max_width_px, scale):
    """
    Convierte texto en lista de líneas que caben dentro de max_width_px.
    Usa medición real de píxeles con cv2.getTextSize.
    """
    text = _clean_text(text)
    font = cv2.FONT_HERSHEY_SIMPLEX
    thick = 1
    lines = []

    for paragraph in text.split('\n'):
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            (tw, _), _ = cv2.getTextSize(test, font, scale, thick)
            if tw <= max_width_px:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)

    return lines


def _draw_scrollable_text(frame, lines, x, y, panel_h,
                          scale, color, line_height, scroll_offset):
    """Dibuja líneas con scroll. Retorna (total, visible, scroll_offset)."""
    max_visible = max(1, (panel_h - 10) // line_height)
    total = len(lines)
    scroll_offset = max(0, min(scroll_offset, max(0, total - max_visible)))
    visible_lines = lines[scroll_offset: scroll_offset + max_visible]

    for i, line in enumerate(visible_lines):
        _text(frame, line, x, y + i * line_height, scale=scale, color=color)

    return total, max_visible, scroll_offset


# =============================================================================
class GameUI:
    # Dimensiones de paneles
    TOP_H = 80  # barra superior (stats)
    BOT_H = 260  # panel inferior (narrativa) — más alto para más texto
    SIDE_W = 260  # panel derecho (gestos)

    def __init__(self, fw, fh):
        self.fw = fw
        self.fh = fh
        self.scroll_offset = 0  # línea desde donde mostrar el texto
        self._last_lines = []  # cache de líneas para scroll

    # ── Frame de setup (antes de iniciar) ─────────────────────────────────────
    def draw_setup(self, frame, setup_state: dict):
        _panel(frame, 0, 0, self.fw, self.fh, (15, 15, 25), alpha=0.85)

        cy = self.fh // 2 - 80
        _text(frame, "AI DUNGEON MASTER", self.fw // 2 - 170, cy,
              scale=1.2, color=GOLD, thickness=3)

        step = setup_state.get("step", 0)
        lang = setup_state.get("language", "es")

        if step == 0:
            msg1 = "Elige idioma:" if lang == "es" else "Choose language:"
            msg2 = "[ E ] Espanol    [ N ] English"
        elif step == 1:
            msg1 = "Escribe tu nombre y presiona ENTER:" if lang == "es" else "Type your name and press ENTER:"
            msg2 = f"> {setup_state.get('input_buffer', '')}_"
        elif step == 2:
            msg1 = "Elige tu clase:" if lang == "es" else "Choose your class:"
            msg2 = "[ G ] Guerrero / Warrior    [ M ] Mago / Mage    [ A ] Arquero / Archer"
        elif step == 3:
            msg1 = "Generando mundo..." if lang == "es" else "Generating world..."
            msg2 = "Por favor espera..." if lang == "es" else "Please wait..."

        _text(frame, msg1, self.fw // 2 - 200, cy + 80, scale=0.65, color=WHITE)
        _text(frame, msg2, self.fw // 2 - 280, cy + 120, scale=0.60, color=CYAN)

    # ── Frame principal de juego ───────────────────────────────────────────────
    def draw_game(self, frame, state, gesture, conf, is_typing: bool,
                  narrative: str, flash_gesture: str = None):

        h, w = frame.shape[:2]

        # ── Barra superior — Stats ─────────────────────────────────────────────
        _panel(frame, 0, 0, w, self.TOP_H, (15, 15, 30), alpha=0.80)

        # HP bar
        _text(frame, "HP", 10, 28, scale=0.65, color=RED)
        _bar(frame, 48, 10, 150, 18, state.hp, state.max_hp, RED)
        _text(frame, f"{state.hp}/{state.max_hp}", 48, 50, scale=0.50, color=WHITE)

        # Mana bar
        _text(frame, "MP", 215, 28, scale=0.65, color=PURPLE)
        _bar(frame, 255, 10, 130, 18, state.mana, state.max_mana, PURPLE)
        _text(frame, f"{state.mana}/{state.max_mana}", 255, 50, scale=0.50, color=WHITE)

        # Nivel y turno
        _text(frame, f"Lv.{state.level}  XP:{state.xp}", 405, 28,
              scale=0.60, color=GOLD)
        _text(frame, f"Turno {state.turn}", 405, 55, scale=0.50, color=GRAY)

        # Nombre y clase
        _text(frame, f"{state.player_name} | {state.player_class}",
              w // 2 - 100, 38, scale=0.70, color=CYAN)

        # Dado
        if state.last_roll:
            roll_color = GOLD if state.last_roll >= 15 else (WHITE if state.last_roll >= 8 else RED)
            _text(frame, f"D20: {state.last_roll}", w - 150, 38,
                  scale=0.75, color=roll_color, thickness=2)

        # ── Panel derecho — Guía de gestos ────────────────────────────────────
        px = w - self.SIDE_W
        _panel(frame, px, self.TOP_H, w, h - self.BOT_H, (20, 15, 30), alpha=0.78)

        gestures_guide = [
            ("ATTACK", "Puno cerrado"),
            ("DEFEND", "Mano abierta"),
            ("DICE", "Indice arriba"),
            ("INVENTORY", "Pellizco"),
            ("FLEE", "Dos dedos V"),
            ("MAGIC", "Shaka"),
        ]
        gy = self.TOP_H + 26
        _text(frame, "GESTOS:", px + 12, gy, scale=0.65, color=GOLD)
        gy += 30
        for g_name, g_desc in gestures_guide:
            is_active = (gesture == g_name)
            color = GESTURE_COLORS[g_name] if is_active else GRAY
            prefix = ">> " if is_active else "   "
            _text(frame, f"{prefix}{g_name[:3]}  {g_desc}", px + 10, gy,
                  scale=0.48, color=color)
            gy += 26

        # Gesto actual grande
        if gesture:
            g_color = GESTURE_COLORS.get(gesture, GRAY)
            _text(frame, GESTURE_EMOJIS.get(gesture, ""), px + 12, gy + 30,
                  scale=0.85, color=g_color, thickness=2)
            # Barra de confianza
            _bar(frame, px + 10, gy + 48, self.SIDE_W - 20, 10, conf, 1.0, g_color)
            _text(frame, f"{int(conf * 100)}%", px + 12, gy + 72,
                  scale=0.45, color=WHITE)

        # ── Panel inferior — Narrativa ─────────────────────────────────────────
        bot_y = h - self.BOT_H
        panel_w = w - self.SIDE_W
        _panel(frame, 0, bot_y, panel_w, h, (15, 10, 25), alpha=0.82)

        # Título
        if is_typing:
            _text(frame, "Dungeon Master ...", 12, bot_y + 26,
                  scale=0.60, color=GOLD)
        else:
            _text(frame, "Dungeon Master:", 12, bot_y + 26,
                  scale=0.60, color=GOLD)

        # Separador
        cv2.line(frame, (12, bot_y + 36), (panel_w - 16, bot_y + 36),
                 (60, 50, 80), 1)

        # Texto narrativo con scroll
        if narrative:
            SCROLL_BAR_W = 10
            text_max_w = panel_w - 24 - SCROLL_BAR_W  # dejar espacio a barra
            line_h = 24
            text_scale = 0.48

            lines = _wrap_text_lines(narrative, text_max_w, text_scale)
            self._last_lines = lines

            total, visible, self.scroll_offset = _draw_scrollable_text(
                frame, lines,
                x=12,
                y=bot_y + 50,
                panel_h=self.BOT_H - 55,
                scale=text_scale,
                color=WHITE,
                line_height=line_h,
                scroll_offset=self.scroll_offset,
            )

            # Barra de scroll
            if total > visible:
                bar_x = panel_w - SCROLL_BAR_W - 4
                bar_top = bot_y + 50
                bar_bot = h - 28
                bar_h = max(1, bar_bot - bar_top)
                thumb_h = max(16, int(bar_h * visible / total))
                thumb_y = bar_top + int(
                    (bar_h - thumb_h) * self.scroll_offset / max(1, total - visible)
                )
                cv2.rectangle(frame, (bar_x, bar_top),
                              (bar_x + SCROLL_BAR_W, bar_bot), (40, 40, 60), -1)
                cv2.rectangle(frame, (bar_x, thumb_y),
                              (bar_x + SCROLL_BAR_W, thumb_y + thumb_h), GOLD, -1)

                # Flechas
                if self.scroll_offset > 0:
                    _text(frame, "^ W", bar_x - 28, bar_top + 12,
                          scale=0.35, color=GOLD)
                if self.scroll_offset < total - visible:
                    _text(frame, "v X", bar_x - 28, bar_bot - 4,
                          scale=0.35, color=GOLD)

        # Ayuda teclas
        _text(frame,
              "[W] Subir  [X] Bajar  [I] Inventario  [ESC] Salir  [R] Reiniciar",
              12, h - 8, scale=0.38, color=GRAY)

        # ── Flash de gesto confirmado ──────────────────────────────────────────
        if flash_gesture:
            overlay = frame.copy()
            fc = GESTURE_COLORS.get(flash_gesture, WHITE)
            cv2.rectangle(overlay, (0, 0), (w, h), fc, -1)
            cv2.addWeighted(overlay, 0.10, frame, 0.90, 0, frame)
            _text(frame, f">> {GESTURE_EMOJIS.get(flash_gesture, flash_gesture)} <<",
                  w // 2 - 100, h // 2, scale=1.2,
                  color=fc, thickness=3)

    # ── Game Over ─────────────────────────────────────────────────────────────
    def draw_game_over(self, frame, state):
        _panel(frame, 0, 0, self.fw, self.fh, BLACK, alpha=0.88)
        cy = self.fh // 2
        lang = state.language
        _text(frame, "GAME OVER" if lang == "en" else "FIN DEL JUEGO",
              self.fw // 2 - 130, cy - 40, scale=1.4, color=RED, thickness=3)
        _text(frame, f"Turno {state.turn} | Nivel {state.level}",
              self.fw // 2 - 90, cy + 10, scale=0.65, color=GOLD)
        msg = "Press R to restart" if lang == "en" else "Presiona R para reiniciar"
        _text(frame, msg, self.fw // 2 - 130, cy + 50, scale=0.6, color=WHITE)

    # ── Inventario ────────────────────────────────────────────────────────────
    def draw_inventory(self, frame, inventory, language):
        _panel(frame, 80, 80, self.fw - 80, self.fh - 80, (10, 10, 20), alpha=0.92)
        title = "INVENTARIO" if language == "es" else "INVENTORY"
        _text(frame, title, self.fw // 2 - 70, 120, scale=0.9, color=GOLD, thickness=2)

        if not inventory:
            msg = "Inventario vacío" if language == "es" else "Empty inventory"
            _text(frame, msg, self.fw // 2 - 80, self.fh // 2, scale=0.7, color=GRAY)
        else:
            for i, item in enumerate(inventory):
                y = 160 + i * 45
                color = {"weapon": RED, "armor": BLUE,
                         "potion": GREEN, "magic": PURPLE}.get(item["type"], WHITE)
                _text(frame, f"{item['emoji']}  {item['name']}", 120, y,
                      scale=0.65, color=color, thickness=1)
                _text(frame, f"+{item['power']}", 400, y, scale=0.55, color=GOLD)
                _text(frame, item["type"].upper(), 460, y, scale=0.38, color=GRAY)

        close = "[ I ] Cerrar" if language == "es" else "[ I ] Close"
        _text(frame, close, self.fw // 2 - 50, self.fh - 100, scale=0.5, color=GRAY)

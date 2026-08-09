# =============================================================================
#  main.py — AI Dungeon Master
#  Gestos de mano + OpenAI GPT → Juego de rol interactivo
# =============================================================================

import cv2
import mediapipe as mp
import time
import sys

from gestures import GestureDetector, GESTURE_NONE
from game_engine import GameEngine
from ai_master import AIMaster
from ui import GameUI

# ── Configuración ─────────────────────────────────────────────────────────────
CAMERA_INDEX = 0
FRAME_W = 1280
FRAME_H = 800

# ── MediaPipe ─────────────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
mp_styles = mp.solutions.drawing_styles

hands = mp_hands.Hands(
    max_num_hands=1,
    model_complexity=0,
    min_detection_confidence=0.65,
    min_tracking_confidence=0.60,
)


# ── Estado de la app ──────────────────────────────────────────────────────────

class App:
    PHASE_SETUP = "setup"
    PHASE_GAME = "game"
    PHASE_GAMEOVER = "gameover"

    def __init__(self):
        self.phase = self.PHASE_SETUP
        self.engine = GameEngine()
        self.detector = GestureDetector()
        self.ai = AIMaster("es")
        self.ui = None  # se inicializa con dimensiones reales

        # Setup wizard
        self.setup = {
            "step": 0,  # 0=idioma 1=nombre 2=clase 3=generando
            "language": "es",
            "input_buffer": "",
            "player_class": "Guerrero",
        }

        # Estado de juego
        self.narrative = ""
        self.flash_gesture = None
        self.flash_frames = 0
        self.last_gesture = None

    def on_narrative(self, text: str):
        """Callback cuando la IA termina de generar texto."""
        self.narrative = text
        # Añadir al historial de la IA
        self.engine.add_to_history("assistant", text)
        # Resetear scroll al llegar texto nuevo
        if self.ui:
            self.ui.scroll_offset = 0
        # Si estábamos en setup paso 3, pasar a juego
        if self.setup["step"] == 3:
            self.phase = self.PHASE_GAME

    def start_game(self):
        """Iniciar el juego con los datos del setup."""
        lang = self.setup["language"]
        name = self.setup["input_buffer"] or ("Aventurero" if lang == "es" else "Adventurer")
        cls = self.setup["player_class"]

        self.engine.new_game(name, cls, lang)
        self.ai.set_language(lang)
        self.narrative = "Generando mundo..." if lang == "es" else "Generating world..."
        self.setup["step"] = 3
        self.ai.start_game(self.engine.state, callback=self.on_narrative)

    def handle_gesture(self, gesture: str):
        """Procesar un gesto confirmado."""
        if self.phase != self.PHASE_GAME:
            return
        if self.ai.is_typing:
            return  # esperar a que la IA termine

        state = self.engine.state
        result = {}

        if gesture == "ATTACK":
            result = self.engine.attack()
        elif gesture == "DEFEND":
            result = self.engine.defend()
        elif gesture == "DICE":
            roll = self.engine.roll_dice()
            result = {"roll": roll}
        elif gesture == "MAGIC":
            result = self.engine.use_magic()
        elif gesture == "FLEE":
            result = self.engine.flee()
        elif gesture == "INVENTORY":
            state.show_inventory = not state.show_inventory
            result = {}

        # Flash visual
        self.flash_gesture = gesture
        self.flash_frames = 8

        # Restaurar maná cada turno
        self.engine.restore_mana()

        # Llamar a la IA (excepto inventario que es instantáneo)
        if gesture != "INVENTORY":
            # Añadir acción al historial
            action_label = {
                "ATTACK": "Atacar", "DEFEND": "Defender", "DICE": "Lanzar dado",
                "MAGIC": "Usar magia", "FLEE": "Huir",
            }.get(gesture, gesture)
            self.engine.add_to_history("user", f"[Acción: {action_label}]")

            self.ai.player_action(
                gesture, result, self.engine.state.history,
                self.engine, callback=self.on_narrative
            )

        # Chequear game over
        if not self.engine.state.alive:
            self.phase = self.PHASE_GAMEOVER


def main():
    print("=" * 55)
    print("  AI Dungeon Master")
    print("  Controles de teclado:")
    print("    E/N   → Idioma (Español/English) en setup")
    print("    ENTER → Confirmar nombre")
    print("    I     → Toggle inventario")
    print("    R     → Reiniciar juego")
    print("    ESC   → Salir")
    print("=" * 55)

    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

    if not cap.isOpened():
        print("ERROR: No se pudo abrir la cámara.")
        sys.exit(1)

    app = App()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            if app.ui is None:
                app.ui = GameUI(w, h)

            # ── MediaPipe ─────────────────────────────────────────────────────
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            stable_gesture = None
            current_gesture = GESTURE_NONE
            conf = 0.0

            if results.multi_hand_landmarks:
                hand_lm = results.multi_hand_landmarks[0]
                mp_draw.draw_landmarks(
                    frame, hand_lm, mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )
                stable_gesture, current_gesture, conf = app.detector.update(hand_lm)
            else:
                app.detector.no_hand_tick()

            # ── Procesar gesto estable ────────────────────────────────────────
            if stable_gesture and app.phase == App.PHASE_GAME:
                app.handle_gesture(stable_gesture)

            # ── Flash decremento ──────────────────────────────────────────────
            flash = None
            if app.flash_frames > 0:
                flash = app.flash_gesture
                app.flash_frames -= 1

            # ── Dibujar UI ────────────────────────────────────────────────────
            if app.phase == App.PHASE_SETUP:
                app.ui.draw_setup(frame, app.setup)

            elif app.phase == App.PHASE_GAME:
                s = app.engine.state
                if s.show_inventory:
                    # Dibujar juego de fondo + inventario encima
                    app.ui.draw_game(frame, s, current_gesture, conf,
                                     app.ai.is_typing, app.narrative, flash)
                    app.ui.draw_inventory(frame, s.inventory, s.language)
                else:
                    app.ui.draw_game(frame, s, current_gesture, conf,
                                     app.ai.is_typing, app.narrative, flash)

            elif app.phase == App.PHASE_GAMEOVER:
                app.ui.draw_game_over(frame, app.engine.state)

            cv2.imshow("AI Dungeon Master", frame)

            # ── Teclado ───────────────────────────────────────────────────────
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                break

            elif key == ord('r') or key == ord('R'):
                app = App()
                continue

            elif app.phase == App.PHASE_SETUP:
                step = app.setup["step"]

                if step == 0:  # Elegir idioma
                    if key == ord('e') or key == ord('E'):
                        app.setup["language"] = "es"
                        app.setup["step"] = 1
                    elif key == ord('n') or key == ord('N'):
                        app.setup["language"] = "en"
                        app.setup["step"] = 1

                elif step == 1:  # Escribir nombre
                    if key == 13:  # ENTER
                        if app.setup["input_buffer"]:
                            app.setup["step"] = 2
                    elif key == 8:  # BACKSPACE
                        app.setup["input_buffer"] = app.setup["input_buffer"][:-1]
                    elif 32 <= key <= 126 and len(app.setup["input_buffer"]) < 16:
                        app.setup["input_buffer"] += chr(key)

                elif step == 2:  # Elegir clase
                    lang = app.setup["language"]
                    if key == ord('g') or key == ord('G'):
                        app.setup["player_class"] = "Guerrero" if lang == "es" else "Warrior"
                        app.start_game()
                    elif key == ord('m') or key == ord('M'):
                        app.setup["player_class"] = "Mago" if lang == "es" else "Mage"
                        app.start_game()
                    elif key == ord('a') or key == ord('A'):
                        app.setup["player_class"] = "Arquero" if lang == "es" else "Archer"
                        app.start_game()

            elif app.phase == App.PHASE_GAME:
                if key == ord('i') or key == ord('I'):
                    app.engine.state.show_inventory = not app.engine.state.show_inventory
                elif key == 82 or key == ord('w') or key == ord('W'):  # ↑ o W
                    if app.ui:
                        app.ui.scroll_offset = max(0, app.ui.scroll_offset - 1)
                elif key == 84 or key == ord('x') or key == ord('X'):  # ↓ o X
                    if app.ui:
                        app.ui.scroll_offset += 1

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\nGracias por jugar AI Dungeon Master!")


if __name__ == "__main__":
    main()
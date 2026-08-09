# =============================================================================
#  Detección de gestos para AI Dungeon Master
#  6 gestos → 6 acciones de juego
# =============================================================================

import math

# ── Nombres de gestos
GESTURE_ATTACK    = "ATTACK"     # ✊ Puño cerrado
GESTURE_DEFEND    = "DEFEND"     # 🖐 Mano abierta
GESTURE_DICE      = "DICE"       # ☝️ Solo índice arriba
GESTURE_INVENTORY = "INVENTORY"  # 🤏 Pellizco pulgar-índice
GESTURE_FLEE      = "FLEE"       # ✌️ Dos dedos en V
GESTURE_MAGIC     = "MAGIC"      # 🤙 Pulgar + meñique (shaka)
GESTURE_NONE      = None

# Frames estables requeridos para confirmar un gesto
STABLE_FRAMES    = 6
COOLDOWN_FRAMES  = 25
NO_HAND_TOLERANCE = 10

# ── Helpers

def _dist(a, b):
    return math.sqrt((a.x - b.x)**2 + (a.y - b.y)**2 + (a.z - b.z)**2)

def _curl(lm, tip, pip, mcp, wrist_dist):
    """Qué tan cerrado está el dedo: 0.0 = abierto, 1.0 = cerrado."""
    d = _dist(lm[tip], lm[mcp]) / (wrist_dist + 1e-9)
    return max(0.0, min(1.0, 1.0 - d * 0.85))

def _extended(lm, tip, pip, wrist):
    """True si la punta del dedo está más lejos de la muñeca que el PIP."""
    return _dist(lm[tip], wrist) > _dist(lm[pip], wrist) * 0.9

def extract_gesture_features(hand_landmarks):
    lm     = hand_landmarks.landmark
    wrist  = lm[0]
    ref    = _dist(wrist, lm[9]) + 1e-9   # distancia de referencia

    # Extensión de dedos
    thumb  = _dist(lm[4], wrist) > _dist(lm[3], wrist) * 1.05
    index  = _extended(lm, 8,  7,  wrist)
    middle = _extended(lm, 12, 11, wrist)
    ring   = _extended(lm, 16, 15, wrist)
    pinky  = _extended(lm, 20, 19, wrist)

    # Curl de cada dedo
    ct = max(0.0, min(1.0, 1.0 - _dist(lm[4], lm[1]) / ref * 1.2))
    ci = _curl(lm, 8,  7,  5,  ref)
    cm = _curl(lm, 12, 11, 9,  ref)
    cr = _curl(lm, 16, 15, 13, ref)
    cp = _curl(lm, 20, 19, 17, ref)

    # Toques
    touch_ti = (_dist(lm[4], lm[8])  / ref) < 0.08
    touch_tm = (_dist(lm[4], lm[12]) / ref) < 0.08

    # Ángulo V entre índice y medio
    v1 = (lm[8].x  - wrist.x, lm[8].y  - wrist.y)
    v2 = (lm[12].x - wrist.x, lm[12].y - wrist.y)
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2) + 1e-9
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2) + 1e-9
    cos_a = max(-1.0, min(1.0, (v1[0]*v2[0] + v1[1]*v2[1]) / (mag1 * mag2)))
    v_angle = math.degrees(math.acos(cos_a))

    return {
        "fingers": [thumb, index, middle, ring, pinky],
        "curl":    [ct, ci, cm, cr, cp],
        "touch_ti": touch_ti,
        "touch_tm": touch_tm,
        "v_angle":  v_angle,
    }

def detect_gesture(features):
    """Retorna (gesto, confianza) a partir de los features."""
    thumb, index, middle, ring, pinky = features["fingers"]
    ct, ci, cm, cr, cp = features["curl"]
    touch_ti = features["touch_ti"]
    v_angle  = features["v_angle"]

    scores = {}

    # ── ✊ ATTACK — Puño cerrado
    s = 0
    if ci > 0.55: s += 2
    if cm > 0.55: s += 2
    if cr > 0.55: s += 2
    if cp > 0.55: s += 2
    if not index and not middle and not ring and not pinky: s += 2
    scores[GESTURE_ATTACK] = (s, 10)

    # ── 🖐 DEFEND — Mano completamente abierta
    s = 0
    if index:  s += 2
    if middle: s += 2
    if ring:   s += 2
    if pinky:  s += 2
    if thumb:  s += 1
    if ci < 0.30: s += 1
    if cm < 0.30: s += 1
    scores[GESTURE_DEFEND] = (s, 11)

    # ── ☝️ DICE (Tirar los dados) — Solo índice extendido
    s = 0
    if index:       s += 3
    if not middle:  s += 2
    if not ring:    s += 2
    if not pinky:   s += 2
    if cm > 0.55:   s += 1
    scores[GESTURE_DICE] = (s, 10)

    # ── 🤏 INVENTORY — Pellizco pulgar-índice
    s = 0
    if touch_ti:    s += 4
    if not middle:  s += 2
    if not ring:    s += 2
    if not pinky:   s += 2
    scores[GESTURE_INVENTORY] = (s, 10)

    # ── ✌️ FLEE (Huir) — Dos dedos en V
    s = 0
    if index:       s += 2
    if middle:      s += 2
    if not ring:    s += 2
    if not pinky:   s += 2
    if v_angle > 18: s += 3
    scores[GESTURE_FLEE] = (s, 11)

    # ── 🤙 MAGIC — Pulgar + meñique (seña de "chill")
    s = 0
    if thumb:       s += 2
    if pinky:       s += 2
    if not index:   s += 2
    if not middle:  s += 2
    if not ring:    s += 2
    if ci > 0.55:   s += 1
    if cm > 0.55:   s += 1
    scores[GESTURE_MAGIC] = (s, 12)

    # ── Elegir el mejor
    MIN_PCT = 0.72
    best, best_conf = GESTURE_NONE, 0.0

    for gesture, (pts, max_pts) in scores.items():
        pct = pts / max_pts if max_pts > 0 else 0.0
        if pct >= MIN_PCT and pct > best_conf:
            best      = gesture
            best_conf = pct

    conf = min(0.99, 0.50 + best_conf * 0.49) if best else 0.0
    return best, conf


# ── Estabilizador (igual que en el traductor)
class GestureDetector:

    def __init__(self):
        self._history        = []
        self._cooldown       = 0
        self._last_stable    = None
        self._no_hand_frames = 0
        self.current_gesture = GESTURE_NONE
        self.confidence      = 0.0

    def update(self, hand_landmarks):
        self._no_hand_frames = 0
        features = extract_gesture_features(hand_landmarks)
        gesture, conf = detect_gesture(features)

        self.current_gesture = gesture
        self.confidence      = conf

        self._history.append(gesture)
        if len(self._history) > STABLE_FRAMES:
            self._history.pop(0)

        stable = None
        if self._cooldown > 0:
            self._cooldown -= 1
        else:
            if (len(self._history) == STABLE_FRAMES
                    and gesture is not None
                    and gesture != self._last_stable):
                matches = sum(1 for g in self._history if g == gesture)
                if matches >= STABLE_FRAMES - 1:
                    stable            = gesture
                    self._last_stable = gesture
                    self._cooldown    = COOLDOWN_FRAMES

        return stable, gesture, conf

    def no_hand_tick(self):
        self._no_hand_frames += 1
        if self._no_hand_frames >= NO_HAND_TOLERANCE:
            self._history        = []
            self._last_stable    = None
            self._no_hand_frames = 0
        self.current_gesture = GESTURE_NONE
        self.confidence      = 0.0

    def reset(self):
        self._history        = []
        self._last_stable    = None
        self._cooldown       = 0
        self._no_hand_frames = 0
        self.current_gesture = GESTURE_NONE
        self.confidence      = 0.0

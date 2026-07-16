"""
Action planning — pure Python, no pygame dependency.

Public API:
  - can_reach_puck:  check if a player can physically reach the puck
  - simulate_action:    simulate one action and return a quality score
  - find_best_action: two-phase search (guided + random) for the best action
  - plan_action:     select the best player and action for a given puck position
"""

import logging
import math
import random
import copy

from .constants import (
    PlayerID,
    SCALE, WIDTH, GOAL_WIDTH,
    BOTTOM_GOAL_Y,
    TARGET_X_MIN, TARGET_X_MAX, TARGET_Y_MIN, TARGET_Y_MAX,
    TARGET_X_MIN_P2, TARGET_X_MAX_P2, TARGET_Y_MIN_P2, TARGET_Y_MAX_P2,
    TARGET_RIGHT_D_Z2_X,  TARGET_RIGHT_D_Z2_Y,
    TARGET_RIGHT_D_Z2_X_MIN, TARGET_RIGHT_D_Z2_X_MAX,
    TARGET_RIGHT_D_Z2_Y_MIN, TARGET_RIGHT_D_Z2_Y_MAX,
    YELLOW_BOX_TARGET_X,  YELLOW_BOX_TARGET_Y,
    YELLOW_BOX_TARGET_X_MIN, YELLOW_BOX_TARGET_X_MAX,
    YELLOW_BOX_TARGET_Y_MIN,  YELLOW_BOX_TARGET_Y_MAX,
    TARGET_LEFT_D_Z2_X,  TARGET_LEFT_D_Z2_Y,
    TARGET_LEFT_D_Z2_X_MIN, TARGET_LEFT_D_Z2_X_MAX,
    TARGET_LEFT_D_Z2_Y_MIN, TARGET_LEFT_D_Z2_Y_MAX,
    TARGET_LEFT_D_Z3_X,  TARGET_LEFT_D_Z3_Y,
    TARGET_LEFT_D_Z3_X_MIN, TARGET_LEFT_D_Z3_X_MAX,
    TARGET_LEFT_D_Z3_Y_MIN, TARGET_LEFT_D_Z3_Y_MAX,
    TARGET_RIGHT_WING_Z2_X,  TARGET_RIGHT_WING_Z2_Y,
    TARGET_RIGHT_WING_Z2_X_MIN, TARGET_RIGHT_WING_Z2_X_MAX,
    TARGET_RIGHT_WING_Z2_Y_MIN, TARGET_RIGHT_WING_Z2_Y_MAX,
    LEFT_WING_SEG_B_X_MID,
    LEFT_WING_Z1_TARGET_X, LEFT_WING_Z1_TARGET_Y,
    LEFT_WING_Z3_TARGET_X, LEFT_WING_Z3_TARGET_Y,
    PLAYER_DIAMETER, STICK_LENGTH, PUCK_DIAMETER,
    RIGHT_WING_ZONE1_MAX_Y, RIGHT_WING_ZONE2_MAX_Y,
    RIGHT_D_ZONE_MID_Y,
    LEFT_D_ZONE1_MAX_Y, LEFT_D_ZONE2_MAX_Y,
    max_y_right_wing, right_wing_x,
    center_x,
)
from .entities import players, CurvedPlayer, Puck

log = logging.getLogger(__name__)


# ============================================================
#  Target zone lookup table
#
#  Each entry: (center_x, center_y, x_min, x_max, y_min, y_max)
#  Indexed by target_idx 0–6 (see constants.py module docstring).
# ============================================================

_TARGET_ZONES = [
    # 0: Center red box
    ((TARGET_X_MIN + TARGET_X_MAX) / 2, (TARGET_Y_MIN + TARGET_Y_MAX) / 2,
     TARGET_X_MIN, TARGET_X_MAX, TARGET_Y_MIN, TARGET_Y_MAX),
    # 1: Left Wing red box
    ((TARGET_X_MIN_P2 + TARGET_X_MAX_P2) / 2, (TARGET_Y_MIN_P2 + TARGET_Y_MAX_P2) / 2,
     TARGET_X_MIN_P2, TARGET_X_MAX_P2, TARGET_Y_MIN_P2, TARGET_Y_MAX_P2),
    # 2: Right D zone 2 center
    (TARGET_RIGHT_D_Z2_X, TARGET_RIGHT_D_Z2_Y,
     TARGET_RIGHT_D_Z2_X_MIN, TARGET_RIGHT_D_Z2_X_MAX,
     TARGET_RIGHT_D_Z2_Y_MIN, TARGET_RIGHT_D_Z2_Y_MAX),
    # 3: Yellow box
    (YELLOW_BOX_TARGET_X, YELLOW_BOX_TARGET_Y,
     YELLOW_BOX_TARGET_X_MIN, YELLOW_BOX_TARGET_X_MAX,
     YELLOW_BOX_TARGET_Y_MIN, YELLOW_BOX_TARGET_Y_MAX),
    # 4: Left D zone 2 center
    (TARGET_LEFT_D_Z2_X, TARGET_LEFT_D_Z2_Y,
     TARGET_LEFT_D_Z2_X_MIN, TARGET_LEFT_D_Z2_X_MAX,
     TARGET_LEFT_D_Z2_Y_MIN, TARGET_LEFT_D_Z2_Y_MAX),
    # 5: Left D zone 3 center
    (TARGET_LEFT_D_Z3_X, TARGET_LEFT_D_Z3_Y,
     TARGET_LEFT_D_Z3_X_MIN, TARGET_LEFT_D_Z3_X_MAX,
     TARGET_LEFT_D_Z3_Y_MIN, TARGET_LEFT_D_Z3_Y_MAX),
    # 6: Right Wing zone 2 center
    (TARGET_RIGHT_WING_Z2_X, TARGET_RIGHT_WING_Z2_Y,
     TARGET_RIGHT_WING_Z2_X_MIN, TARGET_RIGHT_WING_Z2_X_MAX,
     TARGET_RIGHT_WING_Z2_Y_MIN, TARGET_RIGHT_WING_Z2_Y_MAX),
]


# ============================================================
#  Private helpers
# ============================================================

def _dist_to_target(puck, target_idx, prioritize_horizontal=False):
    """Distance from puck to the center of the given target zone.

    If prioritize_horizontal=True, x-distance is weighted 5× (used for Left Wing
    zone 1 passes where horizontal alignment matters most).
    """
    cx, cy, *_ = _TARGET_ZONES[target_idx]
    if prioritize_horizontal:
        return abs(puck.x - cx) * 5.0 + abs(puck.y - cy)
    return math.hypot(puck.x - cx, puck.y - cy)


def _guided_action(puck_y, player_idx, max_speed=1.0):
    """Generate a guided action for the given player and puck y position."""
    player = players[player_idx]
    movement_range  = player.max_y - player.min_y
    y_clamped       = max(player.min_y, min(player.max_y, puck_y))
    linear_distance = max(0.0, min(1.0, (y_clamped - player.min_y) / movement_range))

    # More variance when the puck is near the far end of the player's range
    if linear_distance > 0.8:
        linear_distance += random.uniform(-0.15, 0.05)
    else:
        linear_distance += random.uniform(-0.1, 0.1)

    speed_low = min(0.8, max_speed * 0.8)
    return [
        max(0.0, min(1.0, linear_distance)),
        random.choice([-1.0, 1.0]),
        random.uniform(speed_low, max_speed),
    ]


# ============================================================
#  Simulation & scoring
# ============================================================

def simulate_action_for_player(action, puck_x, puck_y, player_idx, target_idx, is_scoring=False):
    """Simulate an action and return (success, score, final_x, final_y, puck_was_hit).

    Scoring breakdown:
      1. Goal bonus (10 000) if the puck enters the net in scoring mode.
      2. Base score = 1000 / (dist_to_target + 1).
      3. +500 zone bonus if puck lands inside the target bounding box.
      4. Movement bonus for how far the puck traveled.
      5. Directional bonus for moving closer to the target y-coordinate.
      6. Left Wing override: 2D zone-specific rewards based on where the puck is
         relative to the goal line and the behind-net x-midpoint.
    """
    test_player = copy.deepcopy(players[player_idx])
    test_puck   = Puck(x=puck_x, y=puck_y)
    test_player.do_action(action)

    hit_after_rotation  = False
    puck_was_hit        = False
    crossed_goal_line   = False
    goal_crossing_speed = 0.0

    # --- Simulate 100 frames ---
    for _ in range(100):
        test_player.update()
        test_puck.move()

        if test_puck.collide(test_player):
            puck_was_hit = True
            if test_player.has_rotated:
                hit_after_rotation = True

        # Goal check (scoring mode only)
        if is_scoring and hit_after_rotation:
            speed = math.hypot(test_puck.vx, test_puck.vy)
            if test_puck.y + test_puck.radius > BOTTOM_GOAL_Y + SCALE / 2:
                if WIDTH / 2 - GOAL_WIDTH / 2 < test_puck.x < WIDTH / 2 + GOAL_WIDTH / 2:
                    # Goal scored — reward velocity so harder shots score higher
                    return True, 10000.0 + speed * 200.0, test_puck.x, test_puck.y, True
            # Track first crossing of the goal line (even if it misses the net)
            if not crossed_goal_line and test_puck.y > BOTTOM_GOAL_Y:
                crossed_goal_line   = True
                goal_crossing_speed = speed

    if not puck_was_hit:
        return False, 0.0, test_puck.x, test_puck.y, False

    # --- Base score ---
    score = 1000.0 / (_dist_to_target(test_puck, target_idx) + 1.0)

    # --- Zone bonus ---
    cx, cy, x_min, x_max, y_min, y_max = _TARGET_ZONES[target_idx]
    if x_min <= test_puck.x <= x_max and y_min <= test_puck.y <= y_max:
        score += 500.0

    # --- Movement bonus ---
    puck_movement = math.hypot(test_puck.x - puck_x, test_puck.y - puck_y)
    score += puck_movement * 2.0
    if puck_movement > 50:
        score += 200.0

    # --- Directional bonus: reward moving closer to target y ---
    y_improvement = abs(puck_y - cy) - abs(test_puck.y - cy)
    if y_improvement > 0:
        score += y_improvement * 5.0
    if y_min <= test_puck.y <= y_max:
        score += 300.0

    # --- Center scoring mode: reward getting past the goal line with speed ---
    if is_scoring and player_idx == PlayerID.CENTER:
        dist_to_goal = max(0.0, (BOTTOM_GOAL_Y + SCALE / 2) - test_puck.y)
        score += 500.0 / (dist_to_goal + 1.0)
        if crossed_goal_line:
            score += 2000.0 + goal_crossing_speed * 150.0

    # --- Left Wing special scoring (2D zone-based) ---
    if player_idx == PlayerID.LEFT_WING:
        if puck_y <= BOTTOM_GOAL_Y:
            # Zone 1: above goal line — reward passing toward center's red box
            target_cx = (TARGET_X_MIN + TARGET_X_MAX) / 2
            target_cy = (TARGET_Y_MIN + TARGET_Y_MAX) / 2

            horiz_gain = abs(puck_x - target_cx) - abs(test_puck.x - target_cx)
            score += horiz_gain * 50.0
            score -= abs(test_puck.x - target_cx) * 10.0
            if abs(test_puck.x - target_cx) < 20:
                score += 3000.0
            if TARGET_X_MIN <= test_puck.x <= TARGET_X_MAX and TARGET_Y_MIN <= test_puck.y <= TARGET_Y_MAX:
                score += 2000.0
            if TARGET_Y_MIN <= test_puck.y <= TARGET_Y_MAX:
                score += 500.0
            score += 1000.0 / (_dist_to_target(test_puck, 0, prioritize_horizontal=True) + 1.0)

        elif puck_x > LEFT_WING_SEG_B_X_MID:
            # Zone 2: right half behind net — reward moving puck up into zone 1
            d_before = math.hypot(puck_x      - LEFT_WING_Z1_TARGET_X, puck_y      - LEFT_WING_Z1_TARGET_Y)
            d_after  = math.hypot(test_puck.x - LEFT_WING_Z1_TARGET_X, test_puck.y - LEFT_WING_Z1_TARGET_Y)
            score += (d_before - d_after) * 6.0
            if test_puck.y <= BOTTOM_GOAL_Y:
                score += 600.0
            if abs(test_puck.x - LEFT_WING_Z1_TARGET_X) < 50 and abs(test_puck.y - LEFT_WING_Z1_TARGET_Y) < 50:
                score += 500.0

        else:
            # Zone 3: left half behind net — reward moving puck to Right Wing zone 3
            d_before = math.hypot(puck_x      - LEFT_WING_Z3_TARGET_X, puck_y      - LEFT_WING_Z3_TARGET_Y)
            d_after  = math.hypot(test_puck.x - LEFT_WING_Z3_TARGET_X, test_puck.y - LEFT_WING_Z3_TARGET_Y)
            score += (d_before - d_after) * 6.0
            if RIGHT_WING_ZONE2_MAX_Y <= test_puck.y <= max_y_right_wing and test_puck.x <= right_wing_x + 2 * SCALE:
                score += 800.0

    return False, score, test_puck.x, test_puck.y, True


def find_best_action_for_player(puck_x, puck_y, player_idx, target_idx,
                     is_scoring=False, max_attempts=10000, max_speed=1.0):
    """Two-phase action search: guided then random.

    Phase 1 (guided): actions biased toward the target geometry.
    Phase 2 (random): pure random exploration, biased to extreme y when needed.

    Returns the best action vector found, or None if no puck contact was made.
    """
    best_action    = None
    best_score     = -1
    best_puck_pos  = (puck_x, puck_y)
    puck_hit_count = 0

    player = players[player_idx]
    movement_range         = player.max_y - player.min_y
    y_clamped              = max(player.min_y, min(player.max_y, puck_y))
    linear_distance_needed = (y_clamped - player.min_y) / movement_range
    is_extreme_range       = linear_distance_needed > 0.8

    if is_extreme_range:
        log.debug("Puck at extreme range (%.2f) — widening search", linear_distance_needed)
        smart_ratio  = 0.4
        max_attempts = int(max_attempts * 2)
    else:
        smart_ratio = 0.7

    n_guided = int(max_attempts * smart_ratio)
    n_random = int(max_attempts * (1.0 - smart_ratio))
    log.info("Searching %d attempts (guided=%d, random=%d)...", max_attempts, n_guided, n_random)

    # Phase 1: Guided search
    for i in range(n_guided):
        if i % 1000 == 0 and i > 0:
            log.debug("Guided %d/%d — best=%.1f, hits=%d", i, n_guided, best_score, puck_hit_count)

        action = _guided_action(puck_y, player_idx, max_speed)
        success, score, final_x, final_y, puck_hit = simulate_action_for_player(
            action, puck_x, puck_y, player_idx, target_idx, is_scoring)

        if puck_hit: puck_hit_count += 1
        if success:
            log.info("Goal! (guided attempt %d)", i)
            return action

        if score > best_score:
            best_score    = score
            best_action   = action
            best_puck_pos = (final_x, final_y)
            if score > 800 and puck_hit and not is_extreme_range:
                log.debug("Excellent action (score=%.1f) at attempt %d", score, i)
                break

    # Phase 2: Random exploration
    for i in range(n_random):
        if i % 500 == 0 and i > 0:
            log.debug("Random %d/%d — best=%.1f, hits=%d", i, n_random, best_score, puck_hit_count)

        linear_dist = random.uniform(0.75, 1.0) if is_extreme_range else random.uniform(0, 1)
        action = [linear_dist, random.choice([-1.0, 1.0]), random.uniform(0.4 * max_speed, max_speed)]

        success, score, final_x, final_y, puck_hit = simulate_action_for_player(
            action, puck_x, puck_y, player_idx, target_idx, is_scoring)

        if puck_hit: puck_hit_count += 1
        if success:
            log.info("Goal! (random attempt %d)", i)
            return action

        if score > best_score:
            best_score    = score
            best_action   = action
            best_puck_pos = (final_x, final_y)

    if best_action:
        log.info("Best score=%.1f, final=(%.1f, %.1f), hits=%d/%d",
                 best_score, best_puck_pos[0], best_puck_pos[1], puck_hit_count, max_attempts)
    else:
        log.warning("No valid action found — puck may be unreachable")

    return best_action


# ============================================================
#  Action planning
# ============================================================

def can_reach_puck(puck_x, puck_y, player_idx):
    """Return True if the player at player_idx can physically reach the puck."""
    player    = players[player_idx]
    max_reach = PLAYER_DIAMETER / 2 + STICK_LENGTH + PUCK_DIAMETER

    if not (player.min_y <= puck_y <= player.max_y):
        return False

    if player_idx == PlayerID.LEFT_WING and isinstance(player, CurvedPlayer):
        # Left Wing has a curved 2D path — sample x across the full range
        sample_points = 20
        y_step = (player.max_y - player.min_y) / sample_points
        xs = [player.get_x_for_y(player.min_y + i * y_step) for i in range(sample_points + 1)]
        return (min(xs) - max_reach) <= puck_x <= (max(xs) + max_reach)

    return abs(puck_x - player.get_x_for_y(puck_y)) <= max_reach


def plan_action(puck_x, puck_y):
    """Select the nearest capable player and find the best action.

    Zone routing:
      CENTER     — score if in red box, otherwise set up
      RIGHT_WING — 3 zones (thirds): yellow box → red box → zone 2 center
      RIGHT_D    — 2 zones (midpoint): zone 2 center → yellow box
      LEFT_D     — 3 zones (thirds): zone 2 → zone 3 → yellow box
      LEFT_WING  — handled by simulation (2D zone logic inside simulate_action)

    Returns (action, PlayerID, stickhandle) or (None, None, False) if no player can reach the puck.
    """
    capable = [i for i in range(len(players)) if can_reach_puck(puck_x, puck_y, i)]
    if not capable:
        log.warning("No player can reach the puck.")
        return None, None, False

    capable.sort(key=lambda i: abs(puck_x - players[i].get_x_for_y(puck_y)))
    chosen = PlayerID(capable[0])
    log.info("Player: %s", chosen.name)

    stickhandle = False
    if chosen == PlayerID.CENTER:
        in_scoring_zone = TARGET_X_MIN <= puck_x <= TARGET_X_MAX and TARGET_Y_MIN <= puck_y <= TARGET_Y_MAX
        if in_scoring_zone:
            log.info("In scoring zone — aiming for goal")
            action = find_best_action_for_player(puck_x, puck_y, chosen, 0, is_scoring=True)
            if action:
                action[2] = max(0.9, action[2])
        else:
            log.info("Stickhandling puck into scoring zone")
            action = find_best_action_for_player(puck_x, puck_y, chosen, 0, max_speed=0.1)
            stickhandle = True
            if action:
                # Ensure the lateral slide reaches the center of the red zone
                p = players[chosen]
                red_zone_mid_y = (TARGET_Y_MIN + TARGET_Y_MAX) / 2
                min_action0 = (red_zone_mid_y - p.min_y) / (p.max_y - p.min_y)
                action[0] = max(action[0], min_action0)
        if action:
            action[1] = -1.0 if puck_x < center_x else 1.0

    elif chosen == PlayerID.RIGHT_WING:
        if puck_y < RIGHT_WING_ZONE1_MAX_Y:
            log.info("Zone 1 → yellow box")
            target_idx = 3
            rw_zone = 1
        elif puck_y < RIGHT_WING_ZONE2_MAX_Y:
            log.info("Zone 2 → center red box")
            target_idx = 0
            rw_zone = 2
        else:
            log.info("Zone 3 → center of zone 2")
            target_idx = 6
            rw_zone = 3
        action = find_best_action_for_player(puck_x, puck_y, chosen, target_idx)
        if action and rw_zone == 3:
            action[1] = 1.0 if puck_x < right_wing_x else -1.0

    elif chosen == PlayerID.RIGHT_D:
        if puck_y < RIGHT_D_ZONE_MID_Y:
            log.info("Zone 1 → middle of zone 2")
            target_idx = 2
        else:
            log.info("Zone 2 → yellow box")
            target_idx = 3
        action = find_best_action_for_player(puck_x, puck_y, chosen, target_idx)

    elif chosen == PlayerID.LEFT_D:
        if puck_y < LEFT_D_ZONE1_MAX_Y:
            log.info("Zone 1 → middle of zone 2")
            target_idx = 4
        elif puck_y < LEFT_D_ZONE2_MAX_Y:
            log.info("Zone 2 → middle of zone 3")
            target_idx = 5
        else:
            log.info("Zone 3 → yellow box")
            target_idx = 3
        action = find_best_action_for_player(puck_x, puck_y, chosen, target_idx)

    else:  # PlayerID.LEFT_WING — 2D zone logic lives inside simulate_action
        log.info("Aiming toward center scoring zone")
        action = find_best_action_for_player(puck_x, puck_y, chosen, 0)

    if action:
        action[1] = math.copysign(1.0, action[1])

    return action, chosen, stickhandle

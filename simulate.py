"""
Bubble hockey simulator — find the best action for a given puck position
and optionally visualize it.

Usage:
    # Single shot with visualization
    python simulate.py --puck_x 225 --puck_y 400

    # Loop with visualization (3-second pause between shots)
    python simulate.py --puck_x 225 --puck_y 400 --loop

    # Headless single shot (no pygame window — just prints the action)
    python simulate.py --puck_x 225 --puck_y 400 --headless

    # Headless loop (runs continuously, prints puck positions)
    python simulate.py --puck_x 225 --puck_y 400 --loop --headless

Module layout:
    constants.py      — all numeric constants, zone boundaries, target coords
    entities.py       — Player, CurvedPlayer, Puck classes + player instances
    planner.py        — pure-Python scoring and action search (no pygame)
    display.py        — pygame rendering (draw_field, episode playback)
    simulate.py       — CLI, player selection, loop orchestration  (this file)
"""

import logging
import sys
import time
import argparse

import pygame

from engine.constants import WIDTH, HEIGHT, PUCK_DIAMETER, WHITE, BLACK
from engine.entities import players
from engine.planner import simulate_action_for_player, plan_action
from robot.logging_setup import configure as configure_logging

log = logging.getLogger(__name__)


# ============================================================
#  CLI arguments
# ============================================================

parser = argparse.ArgumentParser(description="Bubble hockey motion planner.")
parser.add_argument("--puck_x", type=float, help="Initial puck x-coordinate (pixels)")
parser.add_argument("--puck_y", type=float, help="Initial puck y-coordinate (pixels)")
parser.add_argument("--loop",     action="store_true",
                    help="Loop continuously, feeding each final puck position back as the next start")
parser.add_argument("--headless", action="store_true",
                    help="Skip the pygame window — just search and print actions")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="Log the planner's per-phase search progress")
args = parser.parse_args()

configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)


# ============================================================
#  Pygame setup  (skipped in headless mode)
# ============================================================

if not args.headless:
    pygame.init()
    screen = pygame.display.set_mode((int(WIDTH), int(HEIGHT)))
    pygame.display.set_caption("Bubble Hockey Simulator")
    clock = pygame.time.Clock()
    from engine.display import draw_field, visualize_single_episode
else:
    screen = clock = None


# ============================================================
#  Loop mode
# ============================================================

def run_loop(start_x, start_y, headless=False):
    """Continuously find and execute shots, feeding each final puck position
    back as the start of the next shot.

    With visualization: renders each shot in the pygame window with a 3-second pause.
    Headless: runs the simulation internally and prints puck positions to stdout.
    """
    puck_x, puck_y = start_x, start_y
    shot_num = 0

    while True:
        shot_num += 1
        log.info("\n=== Shot %d — puck at (%.1f, %.1f) ===", shot_num, puck_x, puck_y)

        action, player_idx, stickhandle = plan_action(puck_x, puck_y)
        if action is None:
            log.info("No player can reach the puck. Stopping.")
            break

        log.info("Action: %s", [f"{v:.3f}" for v in action])

        if headless:
            # Use the internal simulation to get the final puck position
            _, _, final_x, final_y, _ = simulate_action_for_player(action, puck_x, puck_y, player_idx, 0)
            log.info("Puck ended at (%.1f, %.1f) — waiting 5 seconds...", final_x, final_y)
            time.sleep(5)
        else:
            final_x, final_y = visualize_single_episode(action, puck_x, puck_y, player_idx, screen, clock, stickhandle=stickhandle)
            log.info("Puck ended at (%.1f, %.1f) — waiting 3 seconds...", final_x, final_y)

            pause_start = pygame.time.get_ticks()
            while pygame.time.get_ticks() - pause_start < 3000:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        return
                screen.fill(WHITE)
                draw_field(screen)
                for p in players:
                    p.draw(screen)
                pygame.draw.circle(screen, BLACK, (int(final_x), int(final_y)), int(PUCK_DIAMETER / 2))
                pygame.display.flip()
                clock.tick(60)

        puck_x, puck_y = final_x, final_y

    if not headless:
        pygame.quit()


# ============================================================
#  Entry point
# ============================================================

puck_x = args.puck_x if args.puck_x is not None else WIDTH // 2
puck_y = args.puck_y if args.puck_y is not None else HEIGHT // 2

if args.loop:
    run_loop(puck_x, puck_y, headless=args.headless)
else:
    log.info("Puck: (%s, %s)", puck_x, puck_y)
    action, chosen, stickhandle = plan_action(puck_x, puck_y)
    if action is None:
        if not args.headless:
            pygame.quit()
        sys.exit()
    log.info("Action: %s", [f"{v:.3f}" for v in action])
    if args.headless:
        _, _, final_x, final_y, _ = simulate_action_for_player(action, puck_x, puck_y, chosen, 0)
        log.info("Puck ended at (%.1f, %.1f)", final_x, final_y)
    else:
        visualize_single_episode(action, puck_x, puck_y, chosen, screen, clock, stickhandle=stickhandle)
        pygame.quit()

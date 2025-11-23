# states/__init__.py
def get_state_handler(game):
    state = game.state
    if state == "menu":
        from .menu_state import handle_menu
        return handle_menu
    if state == "arcade_countdown":
        from .countdown_state import handle_countdown
        return handle_countdown
    if state == "race":
        from .race_state import handle_race
        return handle_race
    if state in ("arcade_transition", "gp_transition"):
        from .transition_state import handle_transition
        return handle_transition
    if state in ("arcade_results", "gp_results"):
        from .results_state import handle_results
        return handle_results
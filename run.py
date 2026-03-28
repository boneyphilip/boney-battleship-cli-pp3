# Battleship Game
# This file contains both the interface code that draws the terminal screens
# and the game logic that runs the Battleship match.
import os
import re
import sys
import random
import time
import shutil
from colorama import init, Fore, Style
from wcwidth import wcswidth

if os.name == "nt":
    import msvcrt
else:
    import tty
    import termios

# Initialize colorama (cross-platform color support)
# `autoreset=True` means each print resets the color automatically.
init(autoreset=True)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def read_keypress() -> str:
    """Read one key press without waiting for a full input line."""
    if os.name == "nt":
        key = msvcrt.getwch()

        if key in ("\x00", "\xe0"):
            special = msvcrt.getwch()
            mapping = {
                "H": "up",
                "P": "down",
                "K": "left",
                "M": "right",
            }
            return mapping.get(special, "")

        if key == "\r":
            return "enter"

        if key == "\x08":
            return "backspace"

        return key

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        key = sys.stdin.read(1)

        if key == "\x1b":
            next1 = sys.stdin.read(1)
            next2 = sys.stdin.read(1)
            if next1 == "[":
                mapping = {
                    "A": "up",
                    "B": "down",
                    "D": "left",
                    "C": "right",
                }
                return mapping.get(next2, "")
            return ""

        if key in ("\r", "\n"):
            return "enter"

        if key in ("\x7f", "\b"):
            return "backspace"

        return key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ========= 1) Welcome Screen =========
class WelcomeScreen:
    """Arcade-style welcome screen with inline setup boxes."""

    def __init__(self, title_lines, width=80):
        # Save the artwork and keep the UI wide enough for the board layout.
        self.title_lines = title_lines
        self.width = min(width, GAME_UI_WIDTH)

    # ----- Utility Functions -----
    def strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes for alignment math."""
        # Terminal colors add hidden characters, so we remove them before
        # measuring string width.
        ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
        return ansi_escape.sub("", text)

    def visible_width(self, text: str) -> int:
        """Return visible width of text, ignoring ANSI color codes."""
        # `wcswidth` is better than `len` for emojis and wide characters.
        clean_text = self.strip_ansi(text)
        width = wcswidth(clean_text)
        return len(clean_text) if width < 0 else width

    def center_text(self, text: str, color: str = "") -> str:
        """Return centered text with optional color."""
        clean_width = self.visible_width(text)
        pad = max(0, (self.width - clean_width) // 2)
        return " " * pad + color + text + Style.RESET_ALL

    def fit_title_line(self, text: str) -> str:
        """Trim one title line so it never exceeds the terminal width."""
        fitted = text
        while self.visible_width(fitted) > self.width and fitted:
            fitted = fitted[:-1]
        return fitted

    def pad_line(
        self,
        text: str,
        target_width: int,
        align: str = "left",
    ) -> str:
        """Pad one line to target width."""
        # This keeps text aligned neatly inside panels, even when some lines
        # use colors or emojis.
        current = self.visible_width(text)

        if current >= target_width:
            return text

        if align == "center":
            left = (target_width - current) // 2
            right = target_width - current - left
            return (" " * left) + text + (" " * right)

        return text + (" " * (target_width - current))

    def gradient_line(self, text: str) -> str:
        """Apply rainbow gradient across one line of the title."""
        # The list order controls how the color fades across the title text.
        colors = [
            Fore.RED,
            Fore.MAGENTA,
            Fore.BLUE,
            Fore.CYAN,
            Fore.GREEN,
            Fore.YELLOW,
        ]
        n = len(text)
        gradient = ""
        for i, ch in enumerate(text):
            color = colors[int((i / max(1, n - 1)) * (len(colors) - 1))]
            gradient += color + ch
        return gradient + Style.RESET_ALL

    def build_panel_lines(
        self,
        title: str,
        lines: list[str],
        panel_width: int,
        align: str = "left",
        border_color: str = Fore.YELLOW,
        title_color: str = Fore.CYAN,
    ) -> list[str]:
        """Build one panel using board-style borders."""
        # A panel is the reusable "boxed UI" used for the ship art, setup
        # menu, mission briefing, and deployment messages.
        inner_width = panel_width - 2
        label = f" {title} "
        label_width = self.visible_width(label)
        spare = max(0, inner_width - label_width)
        left = spare // 2
        right = spare - left

        top = (
            border_color
            + "┌"
            + ("─" * left)
            + title_color
            + label
            + border_color
            + ("─" * right)
            + "┐"
            + Style.RESET_ALL
        )
        bottom = (
            border_color
            + "└"
            + ("─" * inner_width)
            + "┘"
            + Style.RESET_ALL
        )

        panel = [top]

        for line in lines:
            # Pad each content line so every row in the panel has the same
            # width before the right border is added.
            padded = self.pad_line(line, inner_width, align=align)
            row = (
                border_color
                + "│"
                + Style.RESET_ALL
                + padded
                + border_color
                + "│"
                + Style.RESET_ALL
            )
            panel.append(row)

        panel.append(bottom)
        return panel

    def print_panel(self, title: str, lines: list[str], align: str = "left"):
        """Print a centered full-width panel."""
        panel_lines = self.build_panel_lines(
            title,
            lines,
            self.width,
            align=align,
        )
        for line in panel_lines:
            print(self.center_text(line))

    def print_custom_panel(
        self,
        title: str,
        lines: list[str],
        panel_width: int,
        align: str = "left",
    ):
        """Print a centered custom-width panel."""
        panel_lines = self.build_panel_lines(
            title,
            lines,
            panel_width,
            align=align,
        )
        for line in panel_lines:
            print(self.center_text(line))

    def selector_row(
        self,
        label: str,
        min_value: int,
        max_value: int,
        value_text: str,
        selected: bool = False,
    ) -> str:
        """Render one compact setup row inside mission setup."""
        display_value = value_text if value_text else ""
        display_value = display_value[:3]

        # Each setup row uses the same fixed indent so the menu feels like
        # one clean column inside the outer mission panel.
        menu_indent = max(2, (self.width - 56) // 2)
        marker = "▶" if selected else " "
        label_part = f"{label} ({min_value}-{max_value})".ljust(22)
        value_box = f"[  {display_value:^3}  ]"

        if selected:
            return (
                " " * menu_indent
                + Style.BRIGHT
                + Fore.CYAN
                + f"{marker} "
                + label_part
                + Fore.YELLOW
                + value_box
                + Style.RESET_ALL
            )

        return (
            " " * menu_indent
            + Fore.WHITE
            + f"{marker} "
            + label_part
            + value_box
            + Style.RESET_ALL
        )

    def action_row(self, label: str, selected: bool = False) -> str:
        """Render the deploy button in a cleaner centered style."""
        # The action button is centered separately so it feels like a menu
        # action rather than another value field.
        button = "[ DEPLOY FLEET ]"
        active_button = "[ PRESS ENTER TO START ]"

        inner_width = self.width - 2
        shown = active_button if selected else button
        left_pad = max(0, (inner_width - len(shown)) // 2)

        if selected:
            return (
                " " * left_pad
                + Style.BRIGHT
                + Fore.GREEN
                + active_button
                + Style.RESET_ALL
            )
        return " " * left_pad + Fore.WHITE + button + Style.RESET_ALL

    def read_key(self) -> str:
        """Read one key without showing an extra input prompt."""
        return read_keypress().lower()

    # ----- Title -----
    def show_title(self):
        """Show a compact deployment-safe title section."""
        clear_screen()

        for line in self.title_lines:
            print(
                self.center_text(
                    self.gradient_line(self.fit_title_line(line))
                )
            )

        subtitle = (
            Fore.CYAN
            + Style.BRIGHT
            + "Command Center Online"
            + Style.RESET_ALL
        )
        print(self.center_text(subtitle))

    # ----- Input Screen -----
    def render_setup_screen(
        self,
        grid_text: str,
        ships_text: str,
        selected: int,
        message: str = "",
    ):
        """Render the compact deployment-friendly setup screen."""
        self.show_title()

        menu_indent = " " * max(2, (self.width - 56) // 2)

        setup_lines = [
            menu_indent
            + Fore.WHITE
            + "Choose settings, then press Enter."
            + Style.RESET_ALL,
            self.selector_row(
                "GRID SIZE",
                8,
                10,
                grid_text,
                selected == 0,
            ),
            self.selector_row(
                "NUMBER OF SHIPS",
                1,
                5,
                ships_text,
                selected == 1,
            ),
            "",
            self.action_row("DEPLOY FLEET", selected == 2),
            "",
            menu_indent
            + Fore.GREEN
            + "Use arrows or numbers. Press Enter."
            + Style.RESET_ALL,
        ]

        self.print_panel("MISSION SETUP", setup_lines, align="left")

        if message:
            print(
                self.center_text(
                    Fore.RED + Style.BRIGHT + message + Style.RESET_ALL
                )
            )

    def get_inputs(self):
        """Inline box editing inside mission setup."""
        # These are editable text values shown in the setup menu.
        grid_text = "8"
        ships_text = "3"
        selected = 0
        message = ""

        while True:
            # Render -> read one key -> update values -> render again.
            self.render_setup_screen(
                grid_text,
                ships_text,
                selected,
                message,
            )
            key = self.read_key()
            message = ""

            if key == "up":
                selected = max(0, selected - 1)
                continue

            if key == "down":
                selected = min(2, selected + 1)
                continue

            if key == "backspace":
                if selected == 0:
                    grid_text = grid_text[:-1]
                elif selected == 1:
                    ships_text = ships_text[:-1]
                continue

            if key == "left":
                # Left arrow decreases the selected value and wraps around
                # when it reaches the minimum.
                if selected == 0:
                    current = int(grid_text) if grid_text.isdigit() else 8
                    current = 10 if current <= 8 else current - 1
                    grid_text = str(current)
                elif selected == 1:
                    current = int(ships_text) if ships_text.isdigit() else 3
                    current = 5 if current <= 1 else current - 1
                    ships_text = str(current)
                continue

            if key == "right":
                # Right arrow increases the selected value and wraps around
                # when it reaches the maximum.
                if selected == 0:
                    current = int(grid_text) if grid_text.isdigit() else 8
                    current = 8 if current >= 10 else current + 1
                    grid_text = str(current)
                elif selected == 1:
                    current = int(ships_text) if ships_text.isdigit() else 3
                    current = 1 if current >= 5 else current + 1
                    ships_text = str(current)
                continue

            if key == "enter":
                # Enter either moves to the next field or starts the game,
                # but only after validating the current values.
                if selected == 0:
                    if grid_text.isdigit() and 8 <= int(grid_text) <= 10:
                        selected = 1
                    else:
                        message = "GRID SIZE must be between 8 and 10."
                    continue

                if selected == 1:
                    if ships_text.isdigit() and 1 <= int(ships_text) <= 5:
                        selected = 2
                    else:
                        message = "NUMBER OF SHIPS must be between 1 and 5."
                    continue

                if selected == 2:
                    if not (grid_text.isdigit() and 8 <= int(grid_text) <= 10):
                        message = "GRID SIZE must be between 8 and 10."
                        selected = 0
                        continue

                    if not (
                        ships_text.isdigit()
                        and 1 <= int(ships_text) <= 5
                    ):
                        message = "NUMBER OF SHIPS must be between 1 and 5."
                        selected = 1
                        continue

                    return int(grid_text), int(ships_text)

            if len(key) == 1 and key.isdigit():
                # Number keys let the player type values directly instead of
                # only cycling with arrow keys.
                if selected == 0:
                    if grid_text in ("8", ""):
                        grid_text = key
                    elif len(grid_text) < 2:
                        grid_text += key
                    else:
                        grid_text = key

                elif selected == 1:
                    if ships_text in ("3", ""):
                        ships_text = key
                    else:
                        ships_text = key
                continue

    # ----- Mission Briefing -----
    def mission_briefing(self, size, ships):
        """Show a compact deployment-safe mission briefing."""
        max_row = chr(64 + size)

        briefing_lines = [
            Fore.CYAN + Style.BRIGHT + "Welcome, Commander." + Style.RESET_ALL,
            f"Grid: {size}x{size} sectors (A-{max_row}, 1-{size})",
            f"Fleet: {ships} battleships deployed",
            f"Controls: Enter A1 to {max_row}{size}, or Q",
            (
                f"Marks: {HIT} hit  {MISS} miss  "
                f"{WATER} water  {SHIP_CHAR} fleet"
            ),
            "Objective: destroy the enemy fleet",
        ]

        self.show_title()

        self.print_custom_panel(
            "MISSION BRIEFING",
            briefing_lines,
            panel_width=min(72, self.width - 4),
            align="left",
        )

        print(
            self.center_text(
                Fore.GREEN
                + Style.BRIGHT
                + "Press Enter to deploy..."
                + Style.RESET_ALL
            )
        )

        input()


# ========= 2) Battleship Game =========
# Emoji constants
# These symbols are reused across the boards and status messages.
WATER = "🌊"
MISS = "💦"
HIT = "💥"
SHIP_CHAR = "🚢"

# Layout constants keep the terminal UI consistent in one place.
LEFT_TITLE = "Enemy Fleet"
RIGHT_TITLE = "Your Fleet"


def get_terminal_width() -> int:
    """Return a safe terminal width for local and deployed play."""
    cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    return max(68, min(80, cols - 2))


GAME_UI_WIDTH = get_terminal_width()
STATUS_UI_WIDTH = max(56, GAME_UI_WIDTH - 8)

# Use a readable cell width while keeping two 10x10 boards side by side.
CELL_VISUAL = 3
GAP_BETWEEN_BOARDS = " " * 2


def clear_screen():
    """Clear terminal window (Windows & Unix)."""
    # Windows uses `cls`, while Linux/macOS terminals usually use `clear`.
    os.system("cls" if os.name == "nt" else "clear")


def redraw_screen():
    """Redraw the terminal in place without spawning a shell clear command."""
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def strip_ansi(s: str) -> str:
    """Strip ANSI color codes (fixes alignment math)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def pad_visual(s: str, width: int) -> str:
    """Pad text so visual width matches width (handles emoji)."""
    # Emojis often take more than one terminal column, so normal len()
    # is not accurate for board alignment.
    vis = wcswidth(strip_ansi(s))
    if vis < 0:
        vis = len(strip_ansi(s))
    return s + " " * max(0, width - vis)


def center_visual(text: str, width: int) -> str:
    """Center text using terminal display width, not Python string length."""
    vis = wcswidth(strip_ansi(text))
    if vis < 0:
        vis = len(strip_ansi(text))
    left_pad = max(0, (width - vis) // 2)
    return (" " * left_pad) + text


def format_cell(symbol: str) -> str:
    """Return one cell padded to CELL_VISUAL columns."""
    return pad_visual(symbol, CELL_VISUAL)


def build_board_block(
    title_text: str,
    grid_rows: list[list[str]],
) -> list[str]:
    """Build one framed board with title, numbers, rows, and border."""
    # This turns a 2D grid into a printable board with column numbers and
    # row letters like a classic Battleship display.
    size = len(grid_rows)
    inner_width = 3 + (size * CELL_VISUAL)
    lines = []

    label = f" {title_text} "
    # Calculate how much border should go on the left and right of the title
    # so the title looks centered in the top border.
    spare = inner_width - len(strip_ansi(label))
    left = max(0, spare // 2)
    right = max(0, spare - left)
    lines.append("┌" + ("─" * left) + label + ("─" * right) + "┐")

    nums = "".join(format_cell(str(i)) for i in range(1, size + 1))
    lines.append("│" + "   " + nums + "│")

    for r in range(size):
        # Convert row index 0, 1, 2... into A, B, C...
        row_label = chr(65 + r)
        row_cells = "".join(format_cell(ch) for ch in grid_rows[r])
        content = f"{row_label}  {row_cells}"
        content = pad_visual(content, inner_width)
        lines.append("│" + content + "│")

    lines.append("└" + ("─" * inner_width) + "┘")
    return lines


def display_boards(enemy_view: list[list[str]], player_board: list[list[str]]):
    """Print boards side by side when they fit, else stack them."""
    enemy_block = build_board_block(LEFT_TITLE, enemy_view)
    player_block = build_board_block(RIGHT_TITLE, player_board)

    board_width = max(wcswidth(strip_ansi(row)) for row in enemy_block)
    gap = GAP_BETWEEN_BOARDS
    combined_width = (board_width * 2) + len(gap)

    if combined_width <= (GAME_UI_WIDTH - 2):
        for enemy_row, player_row in zip(enemy_block, player_block):
            print(center_visual(enemy_row + gap + player_row, GAME_UI_WIDTH))
        return

    for row in enemy_block:
        print(center_visual(row, GAME_UI_WIDTH))

    print()

    for row in player_block:
        print(center_visual(row, GAME_UI_WIDTH))


class BattleshipGame:
    """Main Battleship game logic."""

    def __init__(self, size=8, num_ships=3, title_lines=None):
        # enemy_view is what the player knows about the enemy board.
        # player_board is the real board containing the player's ships.
        self.size = size
        self.num_ships = num_ships
        # Build two boards full of water to start with.
        self.enemy_view = [[WATER] * size for _ in range(size)]
        self.player_board = [[WATER] * size for _ in range(size)]
        # Ship coordinates are also stored in sets for quick hit detection.
        self.enemy_ships = self._place_ships()
        self.player_ships = self._place_ships(reveal=True)
        # The enemy remembers its previous shots so it does not repeat them.
        self.enemy_tried = set()
        self.total_player_shots = 0
        self.total_enemy_shots = 0
        self.player_msg = ""
        self.enemy_msg = ""
        self.battle_message = ""
        self.last_player_target = ""
        self.title_lines = title_lines or []
        self.frame_started = False
        # Developer mode keeps test-only commands available during build work.
        self.dev_mode = False

    def _place_ships(self, reveal=False):
        """Randomly place ships."""
        # Ships are stored as coordinate pairs in a set, which makes
        # hit-checking and removal simple.
        ships = set()
        while len(ships) < self.num_ships:
            # Pick a random row and column somewhere on the board.
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            # Using a set means duplicate positions are ignored automatically.
            ships.add((r, c))
        if reveal:
            # Only the player's ships are shown on the visible player board.
            for r, c in ships:
                self.player_board[r][c] = SHIP_CHAR
        return ships

    def _print_ascii_banner(self):
        """Print gameplay title centered to the gameplay canvas."""
        for line in self.title_lines:
            print(center_visual(line, GAME_UI_WIDTH))

    def _show_target_console(self, prompt: bool = False):
        """Render a fixed-height battle message and target input area."""
        message_line = self.battle_message if self.battle_message else " "
        prompt_label = "Enter target (example: A1). Type Q to quit: "
        rule = Fore.YELLOW + ("─" * STATUS_UI_WIDTH) + Style.RESET_ALL
        prompt_indent = max(0, (GAME_UI_WIDTH - wcswidth(prompt_label)) // 2)

        print(center_visual(message_line, GAME_UI_WIDTH))
        print(center_visual(rule, GAME_UI_WIDTH))

        if not prompt:
            print(
                (" " * prompt_indent)
                + Fore.YELLOW
                + prompt_label
                + Style.RESET_ALL
            )
            print(center_visual(rule, GAME_UI_WIDTH))
            return None

        # Draw an empty prompt row first so the layout height stays stable.
        print(" " * GAME_UI_WIDTH)
        print(center_visual(rule, GAME_UI_WIDTH))

        # Move cursor back up to the prompt row.
        sys.stdout.write("\033[2A\r")
        sys.stdout.write(
            (" " * prompt_indent)
            + Fore.YELLOW
            + prompt_label
            + Style.RESET_ALL
        )
        sys.stdout.flush()

        typed = ""

        while True:
            key = read_keypress()

            if key == "enter":
                # Move cursor below the lower divider before returning.
                sys.stdout.write("\033[2B\r")
                sys.stdout.flush()
                return typed.strip().upper()

            if key == "backspace":
                if typed:
                    typed = typed[:-1]
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue

            if len(key) == 1 and key.isprintable():
                # Prevent the typed value from growing too long and
                # breaking the gameplay layout.
                if len(typed) < 10:
                    ch = key.upper()
                    typed += ch
                    sys.stdout.write(ch)
                    sys.stdout.flush()

    def _render_game_frame(
        self, current_turn="Player", prompt: bool = False
    ):
        """Draw the complete gameplay frame."""
        # The first draw uses a full clear, later draws repaint in place.
        if self.frame_started:
            redraw_screen()
        else:
            clear_screen()
            self.frame_started = True
        self._print_ascii_banner()
        display_boards(self.enemy_view, self.player_board)
        self._show_status(current_turn=current_turn)
        return self._show_target_console(prompt=prompt)

    def _show_battle_message(
        self,
        message: str,
        current_turn="Player",
        delay: float = 1.15,
    ):
        """Show one temporary battle message above target input."""
        # Save the message, draw it, wait briefly, then clear it again.
        self.battle_message = message
        self._render_game_frame(current_turn=current_turn, prompt=False)
        time.sleep(delay)
        self.battle_message = ""

    def _flash_warning(self, message: str, current_turn="Enemy"):
        """Show a steady warning message without blinking the full screen."""
        warning_text = Fore.RED + Style.BRIGHT + message + Style.RESET_ALL
        self.battle_message = warning_text
        self._render_game_frame(current_turn=current_turn, prompt=False)
        time.sleep(0.50)
        self.battle_message = ""

    def play(self):
        """Main loop with sequential turn pacing and battle messages."""
        # Keep looping until either the player or the enemy has no ships left.
        while self.player_ships and self.enemy_ships:
            self.battle_message = ""
            guess = self._render_game_frame(current_turn="Player", prompt=True)

            result = self._player_turn(guess)

            if result == "quit":
                return

            if result == "invalid":
                # Invalid input does not cost the player a turn.
                self._show_battle_message(
                    Fore.RED + self.player_msg + Style.RESET_ALL,
                    current_turn="Player",
                    delay=1.0,
                )
                continue

            if result == "cheat_win":
                self._show_battle_message(
                    Fore.GREEN + self.player_msg + Style.RESET_ALL,
                    current_turn="Player",
                    delay=1.0,
                )
                break

            if result == "cheat_lose":
                self._show_battle_message(
                    Fore.RED + self.player_msg + Style.RESET_ALL,
                    current_turn="Player",
                    delay=1.0,
                )
                break

            if result == "cheat_hit":
                self._show_battle_message(
                    Fore.CYAN + self.player_msg + Style.RESET_ALL,
                    current_turn="Player",
                    delay=1.0,
                )
                if not self.enemy_ships:
                    break
                continue

            if result == "cheat_enemy_hit":
                self._show_battle_message(
                    Fore.MAGENTA + self.player_msg + Style.RESET_ALL,
                    current_turn="Player",
                    delay=1.0,
                )
                if not self.player_ships:
                    break
                continue

            self._show_battle_message(
                Fore.CYAN + self.player_msg + Style.RESET_ALL,
                current_turn="Player",
                delay=0.80,
            )

            if not self.enemy_ships:
                # Stop immediately if the player has destroyed the last ship.
                break

            self._flash_warning(
                "⚠ Enemy torpedo incoming...",
                current_turn="Enemy",
            )

            self.enemy_msg = self._enemy_turn()

            self._show_battle_message(
                Fore.MAGENTA + self.enemy_msg + Style.RESET_ALL,
                current_turn="Enemy",
                delay=0.80,
            )

        self._end_screen()

    def _player_turn(self, guess: str):
        """Resolve player strike after input is already collected."""
        if guess == "Q":
            clear_screen()
            print("👋 Game ended by user.")
            return "quit"

        if self.dev_mode:
            # Developer cheat codes help test special game states quickly.
            if guess == "/WIN":
                # Removing all enemy ships triggers the win ending.
                self.enemy_ships.clear()
                self.player_msg = (
                    "🛠 Developer cheat activated: instant win."
                )
                return "cheat_win"

            if guess == "/LOSE":
                # Removing all player ships triggers the loss ending.
                self.player_ships.clear()
                self.player_msg = (
                    "🛠 Developer cheat activated: instant lose."
                )
                return "cheat_lose"

            if guess == "/PHIT":
                if self.enemy_ships:
                    # Grab one enemy ship location and turn it into a hit.
                    r, c = next(iter(self.enemy_ships))
                    self.enemy_ships.remove((r, c))
                    self.enemy_view[r][c] = HIT
                    self.last_player_target = f"{chr(65 + r)}{c + 1}"
                    self.total_player_shots += 1
                    self.player_msg = (
                        "🛠 Developer cheat: forced player hit at "
                        f"{self.last_player_target}."
                    )
                    return "cheat_hit"
                self.player_msg = "🛠 No enemy ships left to hit."
                return "invalid"

            if guess == "/EHIT":
                if self.player_ships:
                    # Grab one player ship location and simulate an enemy hit.
                    r, c = next(iter(self.player_ships))
                    self.player_ships.remove((r, c))
                    self.player_board[r][c] = HIT
                    self.player_msg = "🛠 Developer cheat: forced enemy hit."
                    return "cheat_enemy_hit"
                self.player_msg = "🛠 No player ships left to hit."
                return "invalid"

        if len(guess) < 2:
            self.player_msg = "❌ Format must be Letter+Number (e.g., A1)."
            return "invalid"

        # Split a guess like "B7" into its row part and column part.
        row_letter, digits = guess[0], guess[1:]
        if not digits.isdigit():
            self.player_msg = "❌ Column must be a number (e.g., A1)."
            return "invalid"

        # Convert from user-friendly coordinates into Python list indexes.
        # Example: A1 becomes row 0, column 0.
        r = ord(row_letter) - 65
        c = int(digits) - 1
        if not (0 <= r < self.size and 0 <= c < self.size):
            self.player_msg = (
                "❌ Coordinates must be "
                f"A-{chr(64 + self.size)} + 1-{self.size}."
            )
            return "invalid"

        if self.enemy_view[r][c] in (MISS, HIT):
            # The enemy view stores old results, so it can block repeats.
            self.player_msg = "⚠️ Already tried that sector."
            return "invalid"

        self.last_player_target = f"{row_letter}{c + 1}"
        self.total_player_shots += 1

        if (r, c) in self.enemy_ships:
            # A hit updates the visible enemy board and removes that ship from
            # the hidden set of remaining enemy ships.
            self.enemy_view[r][c] = HIT
            self.enemy_ships.remove((r, c))
            self.player_msg = (
                f"💥 Direct hit at {row_letter}{c + 1}! Enemy ship damaged!"
            )
        else:
            # A miss is still recorded so the player sees where they fired.
            self.enemy_view[r][c] = MISS
            self.player_msg = (
                f"💦 Torpedo missed at {row_letter}{c + 1}, enemy evaded!"
            )

        return "ok"

    def _enemy_turn(self):
        """Enemy AI randomly fires at player fleet."""
        # This is a simple AI: keep picking random coordinates until it finds
        # one that has not been used before.
        while True:
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            if (r, c) not in self.enemy_tried:
                self.enemy_tried.add((r, c))
                break

        self.total_enemy_shots += 1
        pos = f"{chr(65 + r)}{c + 1}"

        if (r, c) in self.player_ships:
            # Update the real player board so the hit appears on screen.
            self.player_board[r][c] = HIT
            self.player_ships.remove((r, c))
            return f"💥 Enemy fires at {pos} - Direct Hit!"

        # If the enemy misses, mark that square as a miss on the player board.
        self.player_board[r][c] = MISS
        return f"💦 Enemy fires at {pos} - Torpedo missed, you evaded!"

    def _show_status(self, current_turn="Player"):
        """Show a clean centered status panel with three sections."""
        enemy_left = len(self.enemy_ships)
        player_left = len(self.player_ships)

        if current_turn == "Player":
            turn_value = (
                Fore.CYAN + Style.BRIGHT + "PLAYER TURN" + Style.RESET_ALL
            )
        else:
            turn_value = (
                Fore.MAGENTA + Style.BRIGHT + "ENEMY TURN" + Style.RESET_ALL
            )

        panel_width = min(72, GAME_UI_WIDTH - 2)
        inner_width = panel_width - 2
        side_pad = 2
        content_width = inner_width - (side_pad * 2)

        def fit_cell(text: str, width: int, align: str = "left") -> str:
            visible = wcswidth(strip_ansi(text))
            if visible < 0:
                visible = len(strip_ansi(text))

            if visible >= width:
                return text

            if align == "center":
                left_pad = (width - visible) // 2
                right_pad = width - visible - left_pad
                return (" " * left_pad) + text + (" " * right_pad)

            return text + (" " * (width - visible))

        title = " STATUS "
        spare = max(0, inner_width - len(title))
        left = spare // 2
        right = spare - left

        top = (
            Fore.YELLOW
            + "┌"
            + ("─" * left)
            + title
            + ("─" * right)
            + "┐"
            + Style.RESET_ALL
        )
        bottom = (
            Fore.YELLOW
            + "└"
            + ("─" * inner_width)
            + "┘"
            + Style.RESET_ALL
        )

        def row(text: str) -> str:
            return (
                Fore.YELLOW
                + "│"
                + Style.RESET_ALL
                + (" " * side_pad)
                + fit_cell(text, content_width)
                + (" " * side_pad)
                + Fore.YELLOW
                + "│"
                + Style.RESET_ALL
            )

        sep = " │ "
        col1 = 18
        col2 = 18
        col3 = content_width - (len(sep) * 2) - col1 - col2

        header = (
            fit_cell("TURN STATUS", col1, "center")
            + sep
            + fit_cell("FLEET STATUS", col2, "center")
            + sep
            + fit_cell("SHOTS FIRED", col3, "center")
        )

        row1 = (
            fit_cell(turn_value, col1, "center")
            + sep
            + fit_cell(f"Enemy Ships: {enemy_left}", col2)
            + sep
            + fit_cell(f"Player: {self.total_player_shots}", col3)
        )

        row2 = (
            fit_cell("", col1, "center")
            + sep
            + fit_cell(f"Your Ships:  {player_left}", col2)
            + sep
            + fit_cell(f"Enemy: {self.total_enemy_shots}", col3)
        )

        legend = (
            f"Legend: {HIT} hit  {MISS} miss  "
            f"{WATER} water  {SHIP_CHAR} fleet"
        )

        print(center_visual(top, GAME_UI_WIDTH))
        print(
            center_visual(
                row(Fore.YELLOW + Style.BRIGHT + header + Style.RESET_ALL),
                GAME_UI_WIDTH,
            )
        )
        print(center_visual(row(row1), GAME_UI_WIDTH))
        print(center_visual(row(row2), GAME_UI_WIDTH))
        print(
            center_visual(
                row(fit_cell(legend, content_width, "center")),
                GAME_UI_WIDTH,
            )
        )
        print(center_visual(bottom, GAME_UI_WIDTH))

    def _end_screen(self):
        """Show final victory or defeat screen in arcade style."""
        clear_screen()
        self._print_ascii_banner()

        # Choose the final message based on which side still has ships.
        if self.enemy_ships and not self.player_ships:
            lines = [
                Fore.RED + Style.BRIGHT + "MISSION FAILED" + Style.RESET_ALL,
                "Your fleet has been destroyed.",
                "The enemy controls these waters.",
                (
                    Fore.YELLOW
                    + (
                        "Final Shots Fired - "
                        f"Player: {self.total_player_shots} | "
                        f"Enemy: {self.total_enemy_shots}"
                    )
                    + Style.RESET_ALL
                ),
            ]
        else:
            lines = [
                Fore.GREEN
                + Style.BRIGHT
                + "MISSION ACCOMPLISHED"
                + Style.RESET_ALL,
                "All enemy ships have been destroyed.",
                "The battlefield is yours, Commander.",
                (
                    Fore.YELLOW
                    + (
                        "Final Shots Fired - "
                        f"Player: {self.total_player_shots} | "
                        f"Enemy: {self.total_enemy_shots}"
                    )
                    + Style.RESET_ALL
                ),
            ]

        panel_width = min(76, GAME_UI_WIDTH - 4)
        inner_width = panel_width - 2
        label = " BATTLE RESULT "
        spare = inner_width - len(label)
        left = spare // 2
        right = spare - left

        top = "┌" + ("─" * left) + label + ("─" * right) + "┐"
        bottom = "└" + ("─" * inner_width) + "┘"

        print(center_visual(top, GAME_UI_WIDTH))

        # Leave a little space inside the panel so the text does not touch
        # the border directly.
        content_width = inner_width - 8

        for line in lines:
            row = "│    " + pad_visual(line, content_width) + "    │"
            print(center_visual(row, GAME_UI_WIDTH))

        print(center_visual(bottom, GAME_UI_WIDTH))


# ========= 3) Run Game =========
if __name__ == "__main__":
    # Compact deployment assets sized for the Code Institute 80x24 terminal.
    welcome_title_lines = [
        (
            "█████▄ ▄████▄ ██████ "
            "██████ ██     "
            "██████ ▄█████ "
            "██  ██ ██ █████▄ ▄█████"
        ),
        (
            "██▄▄██ ██▄▄██   ██     "
            "██   ██     "
            "██▄▄   ▀▀▀▄▄▄ "
            "██████ ██ ██▄▄█▀ ▀▀▀▄▄▄"
        ),
        (
            "██▄▄█▀ ██  ██   ██     "
            "██   ██████ "
            "██▄▄▄▄ █████▀ "
            "██  ██ ██ ██     █████▀"
        ),
    ]

    if GAME_UI_WIDTH < 76:
        welcome_title_lines = ["<< BATTLESHIPS >>"]

    gameplay_title_lines = [
        Fore.CYAN + Style.BRIGHT + "<< BATTLESHIPS >>" + Style.RESET_ALL,
    ]

    # Run the setup screens first so the player can choose the board size
    # and number of ships before the actual battle starts.
    ws = WelcomeScreen(welcome_title_lines, width=GAME_UI_WIDTH)
    size, ships = ws.get_inputs()
    ws.mission_briefing(size, ships)

    # Create the game object with the chosen settings, then begin the match.
    game = BattleshipGame(
        size=size,
        num_ships=ships,
        title_lines=gameplay_title_lines,
    )
    game.play()

import pygame
import random

pygame.init()

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BLACK = (0, 0, 0)
BG_GRID = (22, 22, 26)
PANEL_BG = (26, 26, 31)
CARD_BG = (36, 36, 43)
CARD_BORDER = (54, 54, 64)
DIVIDER = (48, 48, 57)
TEXT_MAIN = (235, 235, 240)
TEXT_DIM = (150, 150, 160)
ACCENT = (94, 179, 255)
ACCENT_DIM = (60, 100, 140)
BTN_BG = (52, 52, 62)
BTN_BG_HOVER = (66, 66, 78)
BTN_BORDER = (74, 74, 88)
DANGER = (235, 90, 90)

WIDTH, HEIGHT = 1040, 820
PANEL_WIDTH = 260
GRID_AREA_WIDTH = WIDTH - PANEL_WIDTH

MIN_ZOOM = 4
MAX_ZOOM = 80
DEFAULT_ZOOM = 20
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Conway's Game of Life")
clock = pygame.time.Clock()

title_font = pygame.font.SysFont("arial", 20, bold=True)
header_font = pygame.font.SysFont("arial", 14, bold=True)
font = pygame.font.SysFont("consolas", 17)
small_font = pygame.font.SysFont("consolas", 13)
tiny_font = pygame.font.SysFont("arial", 12)

COLOR_OPTIONS = [
    ("Yellow", (255, 255, 0)),
    ("Cyan", (0, 255, 255)),
    ("Green", (60, 220, 60)),
    ("Red", (235, 60, 60)),
    ("Magenta", (235, 60, 235)),
    ("Orange", (255, 165, 0)),
    ("White", (255, 255, 255)),
]


# ---------------------------------------------------------------------------
# RLE pattern loading (patterns copied verbatim from LifeWiki, in Conway's
# standard B3/S23 rule, and verified by simulation before shipping)
# ---------------------------------------------------------------------------
def parse_rle(rle):
    """Decode a headerless RLE string into a set of (x, y) live-cell offsets,
    normalized so the pattern's top-left is at (0, 0)."""
    rle = rle.strip()
    if rle.endswith("!"):
        rle = rle[:-1]
    x, y = 0, 0
    cells = []
    num = ""
    for ch in rle:
        if ch.isdigit():
            num += ch
        elif ch == "b":
            x += int(num) if num else 1
            num = ""
        elif ch == "o":
            n = int(num) if num else 1
            for _ in range(n):
                cells.append((x, y))
                x += 1
            num = ""
        elif ch == "$":
            y += int(num) if num else 1
            x = 0
            num = ""
    minx = min(c[0] for c in cells)
    miny = min(c[1] for c in cells)
    return [(cx - minx, cy - miny) for (cx, cy) in cells]


PATTERNS = [
    {"name": "Block", "category": "Still life", "rle": "2o$2o!"},
    {"name": "Beehive", "category": "Still life", "rle": "b2o$o2bo$b2o!"},
    {"name": "Blinker", "category": "Oscillator", "rle": "3o!"},
    {"name": "Toad", "category": "Oscillator", "rle": "b2o$o$3bo$b2o!"},
    {"name": "Glider", "category": "Spaceship", "rle": "bo$2bo$3o!"},
    {"name": "LW spaceship", "category": "Spaceship", "rle": "o2bo$4bo$o3bo$b4o!"},
    {
        "name": "Gosper gun",
        "category": "Gun",
        "rle": (
            "24bo11b$22bobo11b$12b2o6b2o12b2o$11bo3bo4b2o12b2o$2o8bo5bo3b2o14b$"
            "2o8bo3bob2o4bobo11b$10bo5bo7bo11b$11bo3bo20b$12b2o!"
        ),
    },
]
for _p in PATTERNS:
    _p["cells"] = parse_rle(_p["rle"])
    _p["w"] = max(c[0] for c in _p["cells"]) + 1
    _p["h"] = max(c[1] for c in _p["cells"]) + 1


# ---------------------------------------------------------------------------
# Small UI widgets
# ---------------------------------------------------------------------------
class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, value, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.value = value
        self.label = label
        self.dragging = False

    def handle_x(self):
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        return self.rect.x + int(ratio * self.rect.width)

    def set_from_mouse(self, mx):
        ratio = (mx - self.rect.x) / self.rect.width
        ratio = max(0.0, min(1.0, ratio))
        self.value = self.min_val + ratio * (self.max_val - self.min_val)

    def hit(self, content_pos):
        handle_rect = pygame.Rect(0, 0, 20, 20)
        handle_rect.center = (self.handle_x(), self.rect.centery)
        return self.rect.inflate(0, 12).collidepoint(content_pos) or handle_rect.collidepoint(content_pos)

    def draw(self, surf, scroll):
        r = pygame.Rect(self.rect.x, self.rect.y - scroll, self.rect.w, self.rect.h)
        pygame.draw.rect(surf, BTN_BG, r, border_radius=5)
        ratio = (self.value - self.min_val) / (self.max_val - self.min_val)
        fill_w = max(6, int(ratio * r.width))
        fill_rect = pygame.Rect(r.x, r.y, fill_w, r.height)
        pygame.draw.rect(surf, ACCENT_DIM, fill_rect, border_radius=5)
        hx = r.x + int(ratio * r.width)
        pygame.draw.circle(surf, ACCENT, (hx, r.centery), r.height // 2 + 5)
        pygame.draw.circle(surf, TEXT_MAIN, (hx, r.centery), r.height // 2 + 5, 1)
        label = f"{self.label}: {int(self.value)}"
        text = small_font.render(label, True, TEXT_DIM)
        surf.blit(text, (r.x, r.y - 18))


def draw_button(surf, rect, text, scroll=0, active=False, hovered=False, danger=False, font_=None):
    r = pygame.Rect(rect.x, rect.y - scroll, rect.w, rect.h)
    if active:
        bg = ACCENT
    elif danger:
        bg = (70, 40, 40)
    elif hovered:
        bg = BTN_BG_HOVER
    else:
        bg = BTN_BG
    border = DANGER if danger else (ACCENT if active else BTN_BORDER)
    pygame.draw.rect(surf, bg, r, border_radius=7)
    pygame.draw.rect(surf, border, r, 1, border_radius=7)
    label = (font_ or small_font).render(text, True, (BLACK if active else TEXT_MAIN))
    surf.blit(label, (r.centerx - label.get_width() // 2, r.centery - label.get_height() // 2))


def draw_section_header(surf, x, y, scroll, text):
    sy = y - scroll
    label = header_font.render(text.upper(), True, ACCENT)
    surf.blit(label, (x, sy))
    line_y = sy + label.get_height() + 4
    pygame.draw.line(surf, DIVIDER, (x, line_y), (x + PANEL_WIDTH - 40, line_y), 1)


# ---------------------------------------------------------------------------
# Game of Life logic (works on an unbounded set of (x, y) coordinates)
# ---------------------------------------------------------------------------
def get_neighbors(pos):
    x, y = pos
    return [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if not (dx == 0 and dy == 0)]


def adjust_grid(positions):
    all_neighbors = set()
    new_positions = set()

    for position in positions:
        neighbors = get_neighbors(position)
        all_neighbors.update(neighbors)
        live_neighbors = sum(1 for n in neighbors if n in positions)
        if live_neighbors in (2, 3):
            new_positions.add(position)

    for position in all_neighbors - positions:
        live_neighbors = sum(1 for n in get_neighbors(position) if n in positions)
        if live_neighbors == 3:
            new_positions.add(position)

    return new_positions


def compute_centroid(positions):
    if not positions:
        return None
    n = len(positions)
    sx = sum(p[0] for p in positions)
    sy = sum(p[1] for p in positions)
    return sx / n + 0.5, sy / n + 0.5


def gen_random(num, cam_x, cam_y, zoom):
    view_w = max(1, int(GRID_AREA_WIDTH / zoom) + 2)
    view_h = max(1, int(HEIGHT / zoom) + 2)
    cells = set()
    for _ in range(num):
        wx = int(cam_x) + random.randrange(0, view_w)
        wy = int(cam_y) + random.randrange(0, view_h)
        cells.add((wx, wy))
    return cells


def stamp_pattern(positions, pattern, anchor_wx, anchor_wy):
    """Union a pattern's live cells into positions, centered on the anchor cell."""
    cx, cy = pattern["w"] // 2, pattern["h"] // 2
    for (dx, dy) in pattern["cells"]:
        positions.add((anchor_wx + dx - cx, anchor_wy + dy - cy))
    return positions


# ---------------------------------------------------------------------------
# Camera transforms
# ---------------------------------------------------------------------------
def world_to_screen(wx, wy, cam_x, cam_y, zoom):
    return (wx - cam_x) * zoom, (wy - cam_y) * zoom


def screen_to_world(sx, sy, cam_x, cam_y, zoom):
    return sx / zoom + cam_x, sy / zoom + cam_y


def draw_grid(positions, cam_x, cam_y, zoom, cell_color, ghost_pattern=None, ghost_pos=None):
    grid_surf = screen.subsurface((0, 0, GRID_AREA_WIDTH, HEIGHT))
    grid_surf.fill(BG_GRID)

    left, top = cam_x, cam_y
    right = cam_x + GRID_AREA_WIDTH / zoom
    bottom = cam_y + HEIGHT / zoom

    for (wx, wy) in positions:
        if wx + 1 < left or wx > right or wy + 1 < top or wy > bottom:
            continue
        sx, sy = world_to_screen(wx, wy, cam_x, cam_y, zoom)
        pygame.draw.rect(grid_surf, cell_color, (sx, sy, zoom, zoom))

    if zoom >= 8:
        for col in range(int(left) - 1, int(right) + 2):
            sx, _ = world_to_screen(col, 0, cam_x, cam_y, zoom)
            pygame.draw.line(grid_surf, BLACK, (sx, 0), (sx, HEIGHT))
        for row in range(int(top) - 1, int(bottom) + 2):
            _, sy = world_to_screen(0, row, cam_x, cam_y, zoom)
            pygame.draw.line(grid_surf, BLACK, (0, sy), (GRID_AREA_WIDTH, sy))

    # Ghost preview of the pattern that will be stamped, following the mouse.
    if ghost_pattern is not None and ghost_pos is not None:
        anchor_wx, anchor_wy = ghost_pos
        cx, cy = ghost_pattern["w"] // 2, ghost_pattern["h"] // 2
        for (dx, dy) in ghost_pattern["cells"]:
            wx = anchor_wx + dx - cx
            wy = anchor_wy + dy - cy
            sx, sy = world_to_screen(wx, wy, cam_x, cam_y, zoom)
            ghost_surf = pygame.Surface((zoom, zoom), pygame.SRCALPHA)
            ghost_surf.fill((*ACCENT, 110))
            grid_surf.blit(ghost_surf, (sx, sy))

    pygame.draw.line(screen, CARD_BORDER, (GRID_AREA_WIDTH, 0), (GRID_AREA_WIDTH, HEIGHT), 2)


# ---------------------------------------------------------------------------
# Control panel layout
# ---------------------------------------------------------------------------
def build_panel_layout():
    x0 = GRID_AREA_WIDTH + 20
    inner_w = PANEL_WIDTH - 40
    y = 18

    layout = {"x0": x0, "inner_w": inner_w}

    y += 30  # title space
    layout["sim_header_y"] = y
    y += 26

    layout["play_btn"] = pygame.Rect(x0, y, inner_w // 2 - 5, 34)
    layout["clear_btn"] = pygame.Rect(x0 + inner_w // 2 + 5, y, inner_w // 2 - 5, 34)
    y += 42

    layout["random_btn"] = pygame.Rect(x0, y, inner_w, 30)
    y += 38

    layout["track_btn"] = pygame.Rect(x0, y, inner_w, 30)
    y += 46

    layout["speed_slider"] = Slider(x0, y, inner_w, 14, 1, 60, 10, "Update every N frames")
    y += 40

    layout["color_header_y"] = y
    y += 26
    swatch_size = 32
    gap = 8
    per_row = 5
    swatches = []
    for i, (name, color) in enumerate(COLOR_OPTIONS):
        row = i // per_row
        col = i % per_row
        rect = pygame.Rect(x0 + col * (swatch_size + gap), y + row * (swatch_size + gap), swatch_size, swatch_size)
        swatches.append((rect, name, color))
    layout["swatches"] = swatches
    rows_used = (len(COLOR_OPTIONS) - 1) // per_row + 1
    y += rows_used * (swatch_size + gap) + 6

    layout["patterns_header_y"] = y
    y += 26

    none_btn = pygame.Rect(x0, y, inner_w, 28)
    layout["none_pattern_btn"] = none_btn
    y += 34

    pattern_buttons = []
    last_category = None
    for i, p in enumerate(PATTERNS):
        if p["category"] != last_category:
            layout[f"cat_label_{i}_y"] = y
            y += 18
            last_category = p["category"]
        rect = pygame.Rect(x0, y, inner_w, 28)
        pattern_buttons.append((rect, i))
        y += 32
    layout["pattern_buttons"] = pattern_buttons
    y += 8

    layout["stats_header_y"] = y
    y += 26
    layout["stats_y"] = y
    y += 3 * 22 + 8

    layout["help_header_y"] = y
    y += 26
    layout["help_y"] = y
    help_lines = [
        "Left click: toggle / stamp",
        "Right or middle drag: pan",
        "Mouse wheel: zoom (or scroll panel)",
        "Space: play  |  C: clear  |  G: random",
        "F: toggle tracking  |  Arrows: pan",
    ]
    layout["help_lines"] = help_lines
    y += len(help_lines) * 17 + 20

    layout["content_height"] = y
    return layout


def draw_panel(layout, playing, cell_color, generation, population, zoom, follow_enabled, selected_pattern, scroll, mouse_pos, in_panel):
    panel_rect = pygame.Rect(GRID_AREA_WIDTH, 0, PANEL_WIDTH, HEIGHT)
    pygame.draw.rect(screen, PANEL_BG, panel_rect)

    x0 = layout["x0"]

    title = title_font.render("GAME OF LIFE", True, TEXT_MAIN)
    screen.blit(title, (x0, 16))

    def hovered(rect):
        if not in_panel:
            return False
        content_pos = (mouse_pos[0], mouse_pos[1] + scroll)
        return rect.collidepoint(content_pos)

    draw_section_header(screen, x0, layout["sim_header_y"], scroll, "Simulation")
    draw_button(screen, layout["play_btn"], "Pause" if playing else "Play", scroll, active=playing, hovered=hovered(layout["play_btn"]))
    draw_button(screen, layout["clear_btn"], "Clear", scroll, hovered=hovered(layout["clear_btn"]), danger=True)
    draw_button(screen, layout["random_btn"], "Random fill", scroll, hovered=hovered(layout["random_btn"]))
    draw_button(
        screen, layout["track_btn"],
        "Tracking: On" if follow_enabled else "Tracking: Off",
        scroll, active=follow_enabled, hovered=hovered(layout["track_btn"]),
    )
    layout["speed_slider"].draw(screen, scroll)

    draw_section_header(screen, x0, layout["color_header_y"], scroll, "Cell color")
    for rect, name, color in layout["swatches"]:
        r = pygame.Rect(rect.x, rect.y - scroll, rect.w, rect.h)
        pygame.draw.rect(screen, color, r, border_radius=6)
        border = TEXT_MAIN if color == cell_color else CARD_BORDER
        width = 3 if color == cell_color else 1
        pygame.draw.rect(screen, border, r, width, border_radius=6)

    draw_section_header(screen, x0, layout["patterns_header_y"], scroll, "Patterns")
    draw_button(
        screen, layout["none_pattern_btn"], "Draw single cells",
        scroll, active=(selected_pattern is None), hovered=hovered(layout["none_pattern_btn"]),
    )
    last_category = None
    for rect, idx in layout["pattern_buttons"]:
        p = PATTERNS[idx]
        if p["category"] != last_category:
            cat_y = layout[f"cat_label_{idx}_y"] if f"cat_label_{idx}_y" in layout else None
            if cat_y is not None:
                cat_label = tiny_font.render(p["category"].upper(), True, TEXT_DIM)
                screen.blit(cat_label, (x0, cat_y - scroll))
            last_category = p["category"]
        label = f"{p['name']}  ({len(p['cells'])} cells)"
        draw_button(screen, rect, label, scroll, active=(selected_pattern == idx), hovered=hovered(rect), font_=small_font)

    draw_section_header(screen, x0, layout["stats_header_y"], scroll, "Stats")
    stats_lines = [
        f"Generation: {generation}",
        f"Population: {population}",
        f"Zoom: {zoom:.0f}px/cell",
    ]
    sy = layout["stats_y"] - scroll
    for line in stats_lines:
        text = font.render(line, True, TEXT_MAIN)
        screen.blit(text, (x0, sy))
        sy += 22

    draw_section_header(screen, x0, layout["help_header_y"], scroll, "Controls")
    hy = layout["help_y"] - scroll
    for line in layout["help_lines"]:
        text = tiny_font.render(line, True, TEXT_DIM)
        screen.blit(text, (x0, hy))
        hy += 17

    # Scrollbar
    content_h = layout["content_height"]
    if content_h > HEIGHT:
        track_x = WIDTH - 8
        pygame.draw.rect(screen, CARD_BORDER, (track_x, 4, 4, HEIGHT - 8), border_radius=2)
        bar_h = max(30, int(HEIGHT * HEIGHT / content_h))
        max_scroll = content_h - HEIGHT
        bar_y = 4 + int((HEIGHT - 8 - bar_h) * (scroll / max_scroll if max_scroll else 0))
        pygame.draw.rect(screen, ACCENT_DIM, (track_x, bar_y, 4, bar_h), border_radius=2)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    running = True
    playing = False
    count = 0
    update_freq = 10
    generation = 0

    cam_x, cam_y = 0.0, 0.0
    zoom = float(DEFAULT_ZOOM)
    cell_color = COLOR_OPTIONS[0][1]
    follow_enabled = False
    FOLLOW_LERP = 0.08

    selected_pattern = None  # None => toggle single cells; else index into PATTERNS

    positions = set()
    layout = build_panel_layout()
    layout["speed_slider"].value = update_freq

    panning = False
    pan_start = (0, 0)

    panel_scroll = 0.0

    while running:
        clock.tick(FPS)
        mouse_pos = pygame.mouse.get_pos()
        in_panel = mouse_pos[0] >= GRID_AREA_WIDTH

        if playing:
            count += 1
        if count >= update_freq:
            count = 0
            positions = adjust_grid(positions)
            generation += 1

        content_height = layout["content_height"]
        max_scroll = max(0, content_height - HEIGHT)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                if in_panel:
                    panel_scroll -= event.y * 30
                    panel_scroll = max(0, min(max_scroll, panel_scroll))
                else:
                    mx, my = mouse_pos
                    old_wx, old_wy = screen_to_world(mx, my, cam_x, cam_y, zoom)
                    factor = 1.15 if event.y > 0 else (1 / 1.15)
                    zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom * factor))
                    cam_x = old_wx - mx / zoom
                    cam_y = old_wy - my / zoom

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if in_panel:
                    content_pos = (event.pos[0], event.pos[1] + panel_scroll)
                    if layout["speed_slider"].hit(content_pos):
                        layout["speed_slider"].dragging = True
                        layout["speed_slider"].set_from_mouse(content_pos[0])
                        update_freq = max(1, int(layout["speed_slider"].value))
                    elif layout["play_btn"].collidepoint(content_pos):
                        playing = not playing
                    elif layout["clear_btn"].collidepoint(content_pos):
                        positions = set()
                        playing = False
                        count = 0
                        generation = 0
                    elif layout["random_btn"].collidepoint(content_pos):
                        positions = gen_random(random.randrange(150, 400), cam_x, cam_y, zoom)
                        generation = 0
                    elif layout["track_btn"].collidepoint(content_pos):
                        follow_enabled = not follow_enabled
                    elif layout["none_pattern_btn"].collidepoint(content_pos):
                        selected_pattern = None
                    else:
                        clicked_swatch = False
                        for rect, name, color in layout["swatches"]:
                            if rect.collidepoint(content_pos):
                                cell_color = color
                                clicked_swatch = True
                                break
                        if not clicked_swatch:
                            for rect, idx in layout["pattern_buttons"]:
                                if rect.collidepoint(content_pos):
                                    selected_pattern = idx
                                    break
                else:
                    if event.button == 1:
                        wx, wy = screen_to_world(event.pos[0], event.pos[1], cam_x, cam_y, zoom)
                        pos = (int(wx // 1), int(wy // 1))
                        if selected_pattern is None:
                            if pos in positions:
                                positions.remove(pos)
                            else:
                                positions.add(pos)
                        else:
                            positions = stamp_pattern(positions, PATTERNS[selected_pattern], pos[0], pos[1])
                    elif event.button in (2, 3):
                        panning = True
                        pan_start = event.pos
                        follow_enabled = False

            elif event.type == pygame.MOUSEBUTTONUP:
                layout["speed_slider"].dragging = False
                if event.button in (2, 3):
                    panning = False

            elif event.type == pygame.MOUSEMOTION:
                if layout["speed_slider"].dragging:
                    layout["speed_slider"].set_from_mouse(event.pos[0])
                    update_freq = max(1, int(layout["speed_slider"].value))
                if panning:
                    dx = event.pos[0] - pan_start[0]
                    dy = event.pos[1] - pan_start[1]
                    cam_x -= dx / zoom
                    cam_y -= dy / zoom
                    pan_start = event.pos

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    playing = not playing
                elif event.key == pygame.K_c:
                    positions = set()
                    playing = False
                    count = 0
                    generation = 0
                elif event.key == pygame.K_g:
                    positions = gen_random(random.randrange(150, 400), cam_x, cam_y, zoom)
                    generation = 0
                elif event.key == pygame.K_f:
                    follow_enabled = not follow_enabled
                elif event.key == pygame.K_ESCAPE:
                    selected_pattern = None
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    follow_enabled = False
                    pan_speed = 20 / zoom
                    if event.key == pygame.K_LEFT:
                        cam_x -= pan_speed
                    elif event.key == pygame.K_RIGHT:
                        cam_x += pan_speed
                    elif event.key == pygame.K_UP:
                        cam_y -= pan_speed
                    elif event.key == pygame.K_DOWN:
                        cam_y += pan_speed
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    zoom = min(MAX_ZOOM, zoom * 1.15)
                elif event.key == pygame.K_MINUS:
                    zoom = max(MIN_ZOOM, zoom / 1.15)

        if follow_enabled:
            centroid = compute_centroid(positions)
            if centroid:
                target_cam_x = centroid[0] - (GRID_AREA_WIDTH / 2) / zoom
                target_cam_y = centroid[1] - HEIGHT / 2 / zoom
                cam_x += (target_cam_x - cam_x) * FOLLOW_LERP
                cam_y += (target_cam_y - cam_y) * FOLLOW_LERP

        pygame.display.set_caption("Playing" if playing else "Paused")

        ghost_pattern, ghost_pos = None, None
        if selected_pattern is not None and not in_panel:
            wx, wy = screen_to_world(mouse_pos[0], mouse_pos[1], cam_x, cam_y, zoom)
            ghost_pattern = PATTERNS[selected_pattern]
            ghost_pos = (int(wx // 1), int(wy // 1))

        draw_grid(positions, cam_x, cam_y, zoom, cell_color, ghost_pattern, ghost_pos)
        draw_panel(layout, playing, cell_color, generation, len(positions), zoom, follow_enabled, selected_pattern, panel_scroll, mouse_pos, in_panel)
        pygame.display.update()

    pygame.quit()


if __name__ == "__main__":
    main()
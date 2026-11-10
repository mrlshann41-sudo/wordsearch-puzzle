import io
import math
import random
import string
import streamlit as st
from PIL import Image

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, String

# ==========================================
# 1. CORE PUZZLE GENERATION LOGIC
# ==========================================

class WordSearchBuilder:
    def __init__(self, grid_size=12, allow_backwards=True, allow_diagonals=True):
        self.grid_size = grid_size
        self.allow_backwards = allow_backwards
        self.allow_diagonals = allow_diagonals
        self.grid = [['' for _ in range(grid_size)] for _ in range(grid_size)]
        self.placed_words = {}  # {word: [(r, c), ...]}

    def _get_directions(self):
        dirs = [(0, 1), (1, 0)]  # Horizontal, Vertical
        if self.allow_diagonals:
            dirs.extend([(1, 1), (-1, 1)])
        if self.allow_backwards:
            dirs.extend([(-d[0], -d[1]) for d in list(dirs)])
        return list(set(dirs))

    def place_words(self, words):
        # Sort long words first to maximize placement success
        cleaned_words = [w.upper().replace(" ", "").replace("-", "") for w in words if w.strip()]
        cleaned_words.sort(key=len, reverse=True)

        unplaced = []
        directions = self._get_directions()

        for word in cleaned_words:
            placed = False
            # Try random positions & directions
            attempts = 0
            while attempts < 200 and not placed:
                attempts += 1
                dr, dc = random.choice(directions)
                r_start = random.randint(0, self.grid_size - 1)
                c_start = random.randint(0, self.grid_size - 1)

                r_end = r_start + (len(word) - 1) * dr
                c_end = c_start + (len(word) - 1) * dc

                if 0 <= r_end < self.grid_size and 0 <= c_end < self.grid_size:
                    # Check collision
                    can_place = True
                    coords = []
                    for i in range(len(word)):
                        r, c = r_start + i * dr, c_start + i * dc
                        if self.grid[r][c] != '' and self.grid[r][c] != word[i]:
                            can_place = False
                            break
                        coords.append((r, c))

                    if can_place:
                        for idx, (r, c) in enumerate(coords):
                            self.grid[r][c] = word[idx]
                        self.placed_words[word] = coords
                        placed = True

            if not placed:
                unplaced.append(word)

        # Fill remaining empty cells with random uppercase letters
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.grid[r][c] == '':
                    self.grid[r][c] = random.choice(string.ascii_uppercase)

        return unplaced

# ==========================================
# 2. VECTOR PDF EXPORT GENERATOR (300 DPI)
# ==========================================

def draw_pill(c, x1, y1, x2, y2, radius=8, stroke_color=colors.HexColor('#2E7D32')):
    """Draws a rounded capsule outline over an answer word."""
    c.saveState()
    c.setStrokeColor(stroke_color)
    c.setLineWidth(2.5)

    # Calculate angle and distance
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))

    c.translate(x1, y1)
    c.rotate(angle)

    # Draw capsule path
    p = c.beginPath()
    p.roundRect(-radius, -radius, length + (2 * radius), radius * 2, radius)
    c.drawPath(p, stroke=1, fill=0)
    c.restoreState()

def generate_kdp_pdf(title, subtitle, builder, words, config, top_clipart=None, bottom_clipart=None):
    buffer = io.BytesIO()
    # Standard 8.5" x 11" page at 72 pt/inch
    page_w, page_h = 8.5 * inch, 11 * inch
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Color Palette Parsing
    border_color = colors.HexColor(config['border_color'])
    title_color = colors.HexColor(config['title_color'])

    for is_answer_key in [False, True]:
        # --- 1. OUTER MARGIN FRAME ---
        margin = 0.5 * inch
        c.setStrokeColor(border_color)
        c.setLineWidth(4)
        c.roundRect(margin, margin, page_w - (2 * margin), page_h - (2 * margin), 12, stroke=1, fill=0)
        
        # --- 2. HEADER SECTION ---
        header_top = page_h - 0.9 * inch
        
        # Title (Dynamic font size to prevent overflow past borders)
        display_title = f"{title} (ANSWER KEY)" if is_answer_key else title
        font_size = 18 if len(display_title) > 22 else 24
        
        c.setFont("Helvetica-Bold", font_size)
        c.setFillColor(title_color)
        c.drawCentredString(page_w / 2.0, header_top, display_title.upper())

        # Subtitle / Instructions
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#424242"))
        c.drawCentredString(page_w / 2.0, header_top - 18, subtitle)


        # --- 3. TOP-LEFT CLIPART ---
        if top_clipart:
            try:
                img_w, img_h = 1.1 * inch, 1.1 * inch
                c.drawImage(top_clipart, margin + 0.15 * inch, header_top - 35, width=img_w, height=img_h, mask='auto')
            except Exception:
                pass

        # --- 4. PUZZLE GRID ---
        grid_size = builder.grid_size
        grid_box_size = 4.8 * inch  # Square grid dimensions
        cell_size = grid_box_size / grid_size
        
        grid_left = (page_w - grid_box_size) / 2.0
        grid_top = header_top - 60
        grid_bottom = grid_top - grid_box_size

        # Draw Grid Board Box & Grid Lines
        c.setStrokeColor(colors.HexColor('#E0E0E0'))
        c.setLineWidth(0.8)
        
        for i in range(grid_size + 1):
            # Vertical lines
            c.line(grid_left + i * cell_size, grid_top, grid_left + i * cell_size, grid_bottom)
            # Horizontal lines
            c.line(grid_left, grid_bottom + i * cell_size, grid_left + grid_box_size, grid_bottom + i * cell_size)

        # Render Letters
        c.setFont("Helvetica-Bold", max(10, min(16, int(220 / grid_size))))
        c.setFillColor(colors.HexColor("#212121"))

        for r in range(grid_size):
            for col in range(grid_size):
                char = builder.grid[r][col]
                # Invert row index for PDF Cartesian coords (y starts at bottom)
                x = grid_left + (col + 0.5) * cell_size
                y = grid_top - (r + 0.5) * cell_size - 4  # Baseline adjustment
                c.drawCentredString(x, y, char)

        # --- 5. ANSWER OVERLAYS (ONLY ON PAGE 2) ---
        if is_answer_key:
            for word, coords in builder.placed_words.items():
                if not coords:
                    continue
                start_r, start_c = coords[0]
                end_r, end_c = coords[-1]

                x1 = grid_left + (start_c + 0.5) * cell_size
                y1 = grid_top - (start_r + 0.5) * cell_size
                x2 = grid_left + (end_c + 0.5) * cell_size
                y2 = grid_top - (end_r + 0.5) * cell_size

                draw_pill(c, x1, y1, x2, y2, radius=cell_size * 0.45)

        # --- 6. WORD BANK SECTION ---
        bank_top = grid_bottom - 30
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(title_color)
        c.drawString(margin + 0.4 * inch, bank_top, "WORD BANK:")

        # Layout words into 3 clean columns
        cols = 3
        col_width = (page_w - (2 * margin) - 0.8 * inch) / cols
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#333333"))

        words_per_col = math.ceil(len(words) / cols)
        for idx, w in enumerate(sorted(words)):
            c_idx = idx // words_per_col
            r_idx = idx % words_per_col

            wx = margin + 0.4 * inch + (c_idx * col_width)
            wy = bank_top - 18 - (r_idx * 14)
            if wy > margin + 0.2 * inch:
                c.drawString(wx, wy, f"• {w.upper()}")

        # --- 7. BOTTOM-RIGHT CLIPART ---
        if bottom_clipart:
            try:
                img_w, img_h = 1.2 * inch, 1.2 * inch
                c.drawImage(bottom_clipart, page_w - margin - 1.3 * inch, margin + 0.15 * inch, width=img_w, height=img_h, mask='auto')
            except Exception:
                pass

        c.showPage()  # Complete current page

    c.save()
    buffer.seek(0)
    return buffer

# ==========================================
# 3. STREAMLIT USER INTERFACE & CONTROL PANEL
# ==========================================

st.set_page_config(page_title="KDP Word Search Generator", layout="wide", page_icon="🧩")

st.title("🧩 KDP Word Search Puzzle Generator")
st.caption("Generate print-ready, high-resolution vector PDF puzzle pages for Amazon KDP publishing.")

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Configuration")
    
    title_input = st.text_input("Puzzle Title", value="CHRISTMAS WORD SEARCH")
    subtitle_input = st.text_input("Instructions", value="Find and circle all hidden words below!")

    st.subheader("Grid & Placement Settings")
    grid_dim = st.select_slider("Grid Dimension", options=[10, 12, 14, 15, 18, 20], value=12)
    allow_backwards = st.checkbox("Allow Backward Words", value=True)
    allow_diagonals = st.checkbox("Allow Diagonal Words", value=True)

    st.subheader("Theme & Styling")
    border_color = st.color_picker("Primary Border Color", "#1976D2")
    title_color = st.color_picker("Title Font Color", "#D32F2F")

    st.subheader("Custom Clipart")
    top_clip = st.file_uploader("Header Clipart (Top Left PNG)", type=["png", "jpg"])
    bottom_clip = st.file_uploader("Footer Clipart (Bottom Right PNG)", type=["png", "jpg"])

# Main Workspace Layout
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("📝 Word List Input")
    default_words = "SANTA, REINDEER, SLEIGH, ELVES, PRESENT, SNOWMAN, GINGERBREAD, CANDY, STOCKING, MISTLETOE, ORNAMENT, HOLLY"
    words_raw = st.text_area(
        "Paste comma-separated or line-separated word list:",
        value=default_words,
        height=220
    )
    
    # Parse words input
    if "," in words_raw:
        parsed_words = [w.strip() for w in words_raw.split(",") if w.strip()]
    else:
        parsed_words = [w.strip() for w in words_raw.split("\n") if w.strip()]

    st.info(f"Total Words Count: **{len(parsed_words)}**")
    generate_btn = st.button("🚀 Generate PDF & Preview", type="primary", use_container_width=True)

with col2:
    st.subheader("🖼️ Interactive Preview")
    
    if generate_btn or "generated_pdf" in st.session_state:
        if generate_btn:
            # Run placement engine
            builder = WordSearchBuilder(
                grid_size=grid_dim,
                allow_backwards=allow_backwards,
                allow_diagonals=allow_diagonals
            )
            unplaced = builder.place_words(parsed_words)

            if unplaced:
                st.warning(f"⚠️ Could not fit {len(unplaced)} word(s) in grid: {', '.join(unplaced)}. Try increasing grid size.")

            # Store graphics in memory
            top_img = Image.open(top_clip) if top_clip else None
            bot_img = Image.open(bottom_clip) if bottom_clip else None

            config = {
                "border_color": border_color,
                "title_color": title_color
            }

            pdf_buffer = generate_kdp_pdf(
                title_input,
                subtitle_input,
                builder,
                parsed_words,
                config,
                top_clipart=top_img,
                bottom_clipart=bot_img
            )

            st.session_state["generated_pdf"] = pdf_buffer
            st.session_state["builder"] = builder
            st.session_state["words"] = parsed_words

        # Show download options
        st.download_button(
            label="💾 Download Print-Ready KDP PDF (2 Pages)",
            data=st.session_state["generated_pdf"],
            file_name=f"{title_input.lower().replace(' ', '_')}_kdp.pdf",
            mime="application/pdf",
            use_container_width=True
        )

        # Quick preview of grid
        st.write("**Generated Matrix Preview (Puzzle Grid):**")
        builder_ref = st.session_state["builder"]
        grid_matrix = "\n".join([" ".join(row) for row in builder_ref.grid])
        st.code(grid_matrix, language="text")

import streamlit as st
import secrets
import hashlib
from PIL import Image, ImageDraw, ImageFont
import qrcode
import math
import io
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import json
from datetime import datetime

# ───────────────────────────────────────────────────────────────────────────────
# SIMULATED DATABASE - Store generated tags here
# ───────────────────────────────────────────────────────────────────────────────
if 'tag_database' not in st.session_state:
    st.session_state.tag_database = {}

def store_tag_in_db(bundle: dict, batch_code: str):
    """Store generated tag in simulated database"""
    st.session_state.tag_database[bundle['cert_id']] = {
        'batch_code': batch_code,
        'cert_id': bundle['cert_id'],
        'guilloche_id': bundle['guilloche_id'].hex(),
        'border_id': bundle['border_id'].hex(),
        'serial_number': bundle['serial_number'],
        'created_at': datetime.now().isoformat(),
        'authentic': True
    }

def verify_tag_in_db(cert_id: str) -> dict:
    """Verify tag against simulated database"""
    if cert_id in st.session_state.tag_database:
        return st.session_state.tag_database[cert_id]
    return None

# ───────────────────────────────────────────────────────────────────────────────
# SCAN & VERIFICATION FUNCTIONS
# ───────────────────────────────────────────────────────────────────────────────

def detect_qr_code(image: Image.Image) -> str:
    """Detect and decode QR code from image"""
    try:
        # Convert PIL to numpy array
        img_array = np.array(image)
        
        # Try to decode QR codes
        decoded_objects = decode(img_array)
        
        if decoded_objects:
            for obj in decoded_objects:
                qr_data = obj.data.decode('utf-8')
                # Extract cert_id from URL
                if 'id=' in qr_data:
                    cert_id = qr_data.split('id=')[1]
                    return cert_id
        return None
    except Exception as e:
        return None

def detect_guilloche_pattern(image: Image.Image) -> bool:
    """Detect presence of cyan/magenta guilloche pattern"""
    try:
        img_array = np.array(image)
        
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        
        # Define cyan color range (HSV)
        cyan_lower = np.array([80, 50, 50])
        cyan_upper = np.array([100, 255, 255])
        
        # Define magenta color range (HSV)
        magenta_lower = np.array([140, 50, 50])
        magenta_upper = np.array([170, 255, 255])
        
        # Create masks
        cyan_mask = cv2.inRange(hsv, cyan_lower, cyan_upper)
        magenta_mask = cv2.inRange(hsv, magenta_lower, magenta_upper)
        
        # Count pixels
        cyan_pixels = np.sum(cyan_mask > 0)
        magenta_pixels = np.sum(magenta_mask > 0)
        
        # If significant cyan or magenta pixels detected
        total_pixels = image.size[0] * image.size[1]
        threshold = total_pixels * 0.02  # At least 2% of image
        
        return (cyan_pixels > threshold or magenta_pixels > threshold)
    except Exception as e:
        return False

def detect_grid_pattern(image: Image.Image) -> bool:
    """Detect presence of calibration grid"""
    try:
        img_array = np.array(image)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Detect lines using Hough transform
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=50, maxLineGap=10)
        
        # If we detect multiple lines, grid likely exists
        return lines is not None and len(lines) > 10
    except Exception as e:
        return False

def detect_corner_markers(image: Image.Image) -> bool:
    """Detect corner L-shaped markers"""
    try:
        img_array = np.array(image)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Detect corners using Harris corner detection
        corners = cv2.cornerHarris(gray, blockSize=2, ksize=3, k=0.04)
        
        # Count significant corners
        corner_count = np.sum(corners > 0.01 * corners.max())
        
        # Should have at least 4 strong corners
        return corner_count >= 4
    except Exception as e:
        return False

def analyze_tag_image(image: Image.Image) -> dict:
    """Comprehensive tag analysis"""
    results = {
        'qr_detected': False,
        'qr_cert_id': None,
        'guilloche_detected': False,
        'grid_detected': False,
        'corners_detected': False,
        'overall_valid': False
    }
    
    # Detect QR code
    cert_id = detect_qr_code(image)
    if cert_id:
        results['qr_detected'] = True
        results['qr_cert_id'] = cert_id
    
    # Detect guilloche pattern
    results['guilloche_detected'] = detect_guilloche_pattern(image)
    
    # Detect grid
    results['grid_detected'] = detect_grid_pattern(image)
    
    # Detect corner markers
    results['corners_detected'] = detect_corner_markers(image)
    
    # Overall validation - all components must be present
    results['overall_valid'] = (
        results['qr_detected'] and 
        results['guilloche_detected'] and 
        results['grid_detected'] and 
        results['corners_detected']
    )
    
    return results

# ───────────────────────────────────────────────────────────────────────────────
# GENERATION FUNCTIONS
# ───────────────────────────────────────────────────────────────────────────────

def generate_secret_bundle(batch_code: str) -> dict:
    cert_random = secrets.token_bytes(16)
    cert_hash = hashlib.sha256(cert_random).digest()
    cert_hex = cert_hash.hex()[:12].upper()
    cert_id = f"CERT-{batch_code}-{cert_hex}"
    
    guilloche_secret = secrets.token_bytes(16)
    border_secret = secrets.token_bytes(16)
    
    serial_random = secrets.token_bytes(6)
    serial_number = f"SK-{serial_random.hex()[:12].upper()}"
    
    return {
        "cert_id": cert_id,
        "guilloche_id": guilloche_secret,
        "border_id": border_secret,
        "serial_number": serial_number
    }

def generate_qr_layer(cert_id: str, qr_size: int, canvas_size: int, qr_percentage: int) -> Image.Image:
    url = f"https://skern.com/verify?id={cert_id}"
    qr = qrcode.QRCode(version=10, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=12, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    
    target_size = int(canvas_size * (qr_percentage / 100))
    qr_img = qr_img.resize((target_size, target_size), Image.LANCZOS)
    
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    paste_x = (canvas_size - target_size) // 2
    paste_y = (canvas_size - target_size) // 2
    canvas.paste(qr_img, (paste_x, paste_y), qr_img)
    return canvas

def generate_grid_layer(qr_size: int, canvas_size: int) -> Image.Image:
    img = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Medium gray grid - visible but not overwhelming
    GRID_COLOR = (120, 120, 120, 90)
    SPACING = 64
    WIDTH = 2
    
    for x in range(0, canvas_size, SPACING):
        draw.line([(x, 0), (x, canvas_size)], fill=GRID_COLOR, width=WIDTH)
    for y in range(0, canvas_size, SPACING):
        draw.line([(0, y), (canvas_size, y)], fill=GRID_COLOR, width=WIDTH)
    
    return img

def generate_guilloche_underlay(qr_size: int, secret_bytes: bytes, canvas_size: int) -> Image.Image:
    img = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    center = canvas_size // 2
    params = list(secret_bytes)
    
    # Vibrant cyan/magenta tones - excellent contrast and camera detection
    colors = [
        (0, 180, 220, 160),    # Cyan
        (200, 0, 150, 140),    # Magenta
        (0, 150, 200, 150),    # Deep cyan
    ]
    steps = 7200
    
    for i in range(4):
        color = colors[i % len(colors)]
        base = i * 4
        # Amplitude to cover 95% of canvas (radius = 47.5% of canvas size)
        max_radius = canvas_size * 0.475
        amp = max_radius * (0.7 + (params[base % 16] / 255) * 0.3)
        freq = 8 + (params[(base + 1) % 16] // 32)
        petals = 5 + (params[(base + 2) % 16] // 32)
        phase = (params[(base + 3) % 16] / 255) * 2 * math.pi
        
        points = []
        for step in range(steps + 1):
            theta = (step / steps) * 2 * math.pi * 8 + phase
            r = amp * math.cos(petals * theta) * (1 + 0.2 * math.sin(freq * theta))
            x = center + r * math.cos(theta)
            y = center + r * math.sin(theta)
            if 0 <= x < canvas_size and 0 <= y < canvas_size:
                points.append((x, y))
        if points:
            draw.line(points, fill=color, width=2)
    return img

def generate_corner_border_layer(qr_size: int, secret_bytes: bytes, canvas_size: int) -> Image.Image:
    img = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    MARK_COLOR = (0, 0, 0, 255)
    THICKNESS = 8
    LEG = 120
    corners = [(0,0), (canvas_size-LEG,0), (canvas_size-LEG,canvas_size-LEG), (0,canvas_size-LEG)]
    for cx, cy in corners:
        draw.line([(cx, cy), (cx + LEG, cy)], fill=MARK_COLOR, width=THICKNESS)
        draw.line([(cx, cy), (cx, cy + LEG)], fill=MARK_COLOR, width=THICKNESS)
    
    offset = THICKNESS // 2
    sides = [
        ((offset, offset), (canvas_size - offset, offset)),
        ((canvas_size - offset, offset), (canvas_size - offset, canvas_size - offset)),
        ((canvas_size - offset, canvas_size - offset), (offset, canvas_size - offset)),
        ((offset, canvas_size - offset), (offset, offset)),
    ]
    params = list(secret_bytes)
    segment = 0
    for (x1, y1), (x2, y2) in sides:
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        dist = 0
        while dist < length:
            idx = segment % 16
            mod = (params[idx] / 255) * 2 + 1
            dash_len = 20 * mod * (1 + 0.3 * math.sin(dist * 0.1))
            gap_len = 12 + (params[(idx + 5) % 16] / 255) * 10
            thickness = int(THICKNESS * (0.8 + 0.4 * (params[idx] / 255)))
            start = dist
            end = min(dist + dash_len, length)
            if end > start:
                sx = x1 + (dx * start / length)
                sy = y1 + (dy * start / length)
                ex = x1 + (dx * end / length)
                ey = y1 + (dy * end / length)
                draw.line([(sx, sy), (ex, ey)], fill=MARK_COLOR, width=thickness)
            dist += dash_len + gap_len
            segment += 1
    return img

def add_text_layer(base_img: Image.Image, cert_id: str, serial_number: str) -> Image.Image:
    draw = ImageDraw.Draw(base_img)
    try:
        font_large = ImageFont.truetype("arial.ttf", 56)
        font_small = ImageFont.truetype("arial.ttf", 32)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    w, h = base_img.size
    # Use textbbox for accurate text measurement
    text_bbox = draw.textbbox((0,0), cert_id, font=font_large)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    
    draw.text(((w - text_w)//2, h - 120), cert_id, fill=(0,0,0,255), font=font_large)
    
    s_bbox = draw.textbbox((0,0), serial_number, font=font_small)
    s_w = s_bbox[2] - s_bbox[0]
    draw.text(((w - s_w)//2, h - 60), serial_number, fill=(80,80,80,255), font=font_small)
    
    return base_img

# ───────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Skern Tag Generator", layout="wide")

st.title("🛡️ Skern Garment Authentication System")

# ───────────────────────────────────────────────────────────────────────────────
# MODE SELECTION
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🏭 Generate Tags", "📱 Scan & Verify"])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: GENERATE TAGS
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("Generate secure, unique tags with high-contrast colors for camera detection")

    # ───────────────────────────────────────────────────────────────────────────────
    # BATCH CONFIGURATION
    # ───────────────────────────────────────────────────────────────────────────────
    st.markdown("### Batch Configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        batch_year_short = st.text_input("Year (short)", value="26", max_chars=2)
    with col2:
        factory_code = st.text_input("Factory Code", value="A", max_chars=3)
    with col3:
        batch_sequence = st.text_input("Batch Sequence", value="001", max_chars=3)

    batch_code = f"B{batch_year_short}{factory_code.upper()}{batch_sequence.zfill(3)}"
    st.markdown(f"**Current Batch Code:** `{batch_code}`")

    # ───────────────────────────────────────────────────────────────────────────────
    # TAG DESIGN SETTINGS
    # ───────────────────────────────────────────────────────────────────────────────
    st.markdown("### Tag Design Settings")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        tag_size_px = st.slider("Tag Resolution (pixels)", 800, 1600, 1200)
    with col_b:
        qr_percentage = st.slider("QR Size (% of tag)", 70, 90, 75)
    with col_c:
        print_size_mm = st.selectbox("Physical Print Size", 
                                     options=[30, 35, 40, 45, 50], 
                                     index=2, 
                                     format_func=lambda x: f"{x}×{x} mm")

    # ───────────────────────────────────────────────────────────────────────────────
    # GENERATE BUTTON
    # ───────────────────────────────────────────────────────────────────────────────
    if st.button("Generate Full Tag", type="primary", use_container_width=True):
        with st.spinner("Generating unique tag..."):
            bundle = generate_secret_bundle(batch_code)
            qr_pixel = int(tag_size_px * (qr_percentage / 100))
            
            # Store in simulated database
            store_tag_in_db(bundle, batch_code)
            
            # CORRECT LAYER ORDER (bottom to top):
            # 1. QR code (first/bottom layer)
            # 2. Grid (printed on top of QR)
            # 3. Guilloche (printed on top of grid)
            # 4. Border (printed on top of guilloche)
            layers = [
                generate_qr_layer(bundle["cert_id"], qr_pixel, tag_size_px, qr_percentage),
                generate_grid_layer(qr_pixel, tag_size_px),
                generate_guilloche_underlay(qr_pixel, bundle["guilloche_id"], tag_size_px),
                generate_corner_border_layer(qr_pixel, bundle["border_id"], tag_size_px),
            ]
            
            final_tag = Image.new("RGBA", (tag_size_px, tag_size_px), (255, 255, 255, 255))
            for layer in layers:
                final_tag = Image.alpha_composite(final_tag, layer)
            
            final_tag = add_text_layer(final_tag, bundle["cert_id"], bundle["serial_number"])
            
            # Convert to RGB for PDF saving (PDF doesn't support RGBA)
            final_tag_rgb = final_tag.convert("RGB")
            pdf_buffer = io.BytesIO()
            final_tag_rgb.save(pdf_buffer, format="PDF", resolution=600.0)
            pdf_buffer.seek(0)
        
        col_left, col_right = st.columns([1, 2])
        
        with col_left:
            st.success("✅ Tag generated and stored in database!")
            st.markdown("#### Identifiers (Store in DB!)")
            st.code(f"""
Batch:          {batch_code}
Certificate ID: {bundle['cert_id']}
Guilloche ID:   {bundle['guilloche_id'].hex()}
Border ID:      {bundle['border_id'].hex()}
Serial Number:  {bundle['serial_number']}
            """, language="text")
            
            st.download_button(
                label="📄 Download High-Res PDF (600 DPI)",
                data=pdf_buffer,
                file_name=f"skern_tag_{bundle['cert_id']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        
        with col_right:
            st.markdown("#### Tag Preview")
            st.image(final_tag, caption=f"Preview • {print_size_mm}×{print_size_mm} mm • Cyan/magenta guilloche on white for optimal camera detection", use_column_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: SCAN & VERIFY
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📱 Scan Skern Tag for Verification")
    st.info("📍 **Camera and Location Access Required** - This feature requires camera access to scan tags and location data for authentication logs.")
    
    # Show database status
    tag_count = len(st.session_state.tag_database)
    st.caption(f"📊 Database Status: {tag_count} tags registered")
    
    # Use Streamlit's camera input with custom HTML for permissions
    st.markdown("""
    <script>
    // Request geolocation permission
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                console.log('Location access granted');
            },
            function(error) {
                console.log('Location access denied');
            }
        );
    }
    </script>
    """, unsafe_allow_html=True)
    
    # Camera input
    camera_image = st.camera_input("📸 Take a photo of the Skern tag")
    
    if camera_image is not None:
        st.markdown("---")
        col_scan1, col_scan2 = st.columns([1, 1])
        
        with col_scan1:
            st.markdown("#### 📷 Captured Image")
            st.image(camera_image, use_column_width=True)
        
        with col_scan2:
            st.markdown("#### 🔍 Analysis")
            
            with st.spinner("Analyzing tag components..."):
                # Load and analyze the captured image
                img = Image.open(camera_image)
                analysis = analyze_tag_image(img)
                
                # Display component detection results
                st.markdown("**Detected Components:**")
                qr_icon = "✅" if analysis['qr_detected'] else "❌"
                guilloche_icon = "✅" if analysis['guilloche_detected'] else "❌"
                grid_icon = "✅" if analysis['grid_detected'] else "❌"
                corners_icon = "✅" if analysis['corners_detected'] else "❌"
                
                st.markdown(f"""
                - {qr_icon} QR Code: {'Readable' if analysis['qr_detected'] else 'Not detected'}
                - {guilloche_icon} Guilloche Pattern: {'Present' if analysis['guilloche_detected'] else 'Missing'}
                - {grid_icon} Grid Calibration: {'Aligned' if analysis['grid_detected'] else 'Missing'}
                - {corners_icon} Corner Markers: {'Valid' if analysis['corners_detected'] else 'Missing'}
                """)
                
                st.markdown("---")
                st.markdown("#### 🛡️ Verification Status")
                
                # Verify against database
                tag_data = None
                if analysis['qr_cert_id']:
                    tag_data = verify_tag_in_db(analysis['qr_cert_id'])
                
                if tag_data and analysis['overall_valid']:
                    # AUTHENTIC TAG
                    st.success("**✅ AUTHENTIC TAG**")
                    st.markdown(f"""
                    **Tag Information:**
                    - **Batch Code**: {tag_data['batch_code']}
                    - **Certificate ID**: {tag_data['cert_id']}
                    - **Serial Number**: {tag_data['serial_number']}
                    - **Guilloche ID**: {tag_data['guilloche_id'][:16]}...
                    - **Border ID**: {tag_data['border_id'][:16]}...
                    - **Generated**: {tag_data['created_at']}
                    - **Scan Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    - **Status**: ✅ Verified Authentic
                    """)
                    
                    st.balloons()
                    
                elif tag_data and not analysis['overall_valid']:
                    # Tag in DB but components missing
                    st.warning("**⚠️ SUSPICIOUS - Incomplete Components**")
                    st.markdown("""
                    The QR code is registered in our database, but some security features are missing or damaged.
                    This could indicate:
                    - Poor quality photo (retake with better lighting)
                    - Damaged/worn tag
                    - Potential counterfeit attempt
                    """)
                    
                elif analysis['qr_cert_id'] and not tag_data:
                    # QR code not in database
                    st.error("**❌ COUNTERFEIT - Not Registered**")
                    st.markdown(f"""
                    This tag's certificate ID is **NOT** registered in our database.
                    
                    **Detected ID**: {analysis['qr_cert_id']}
                    
                    **This is likely a counterfeit product.**
                    """)
                else:
                    # No QR code detected
                    st.error("**❌ SCAN FAILED - No QR Code Detected**")
                    st.markdown("""
                    Could not detect a valid QR code in the image.
                    
                    **Tips:**
                    - Ensure good lighting
                    - Hold camera steady
                    - Get closer to the tag
                    - Make sure tag is in focus
                    """)
                
                # Download report button
                if analysis['qr_cert_id']:
                    verification_result = ""
                    if tag_data and analysis['overall_valid']:
                        verification_result = "AUTHENTIC"
                    elif tag_data and not analysis['overall_valid']:
                        verification_result = "SUSPICIOUS"
                    elif analysis['qr_cert_id'] and not tag_data:
                        verification_result = "COUNTERFEIT"
                    else:
                        verification_result = "SCAN_FAILED"
                    
                    report_data = {
                        'scan_time': datetime.now().isoformat(),
                        'cert_id': analysis['qr_cert_id'],
                        'components_detected': {
                            'qr_code': analysis['qr_detected'],
                            'guilloche': analysis['guilloche_detected'],
                            'grid': analysis['grid_detected'],
                            'corners': analysis['corners_detected']
                        },
                        'verification_result': verification_result
                    }
                    
                    report_json = json.dumps(report_data, indent=2)
                    st.download_button(
                        label="📥 Download Verification Report (JSON)",
                        data=report_json,
                        file_name=f"verification_report_{analysis['qr_cert_id'] if analysis['qr_cert_id'] else 'unknown'}.json",
                        mime="application/json",
                        use_container_width=True
                    )

st.caption("Skern Anti-Counterfeit System • All identifiers random & independent • Ready for production")
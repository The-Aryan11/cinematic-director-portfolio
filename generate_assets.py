import zlib
import struct
import math
import os

def create_png(width, height, get_pixel_rgba, filepath):
    # Prepare uncompressed scanlines
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)  # Filter type 0 (None)
        for x in range(width):
            r, g, b, a = get_pixel_rgba(x, y, width, height)
            raw_data.extend([int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF, int(a) & 0xFF])
    
    compressed = zlib.compress(bytes(raw_data), 9)
    
    png = bytearray(b'\x89PNG\r\n\x1a\n')
    
    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
    png.extend(struct.pack('>I', len(ihdr_data)) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc))
    
    # IDAT
    idat_crc = zlib.crc32(b'IDAT' + compressed)
    png.extend(struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc))
    
    # IEND
    iend_crc = zlib.crc32(b'IEND')
    png.extend(struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc))
    
    with open(filepath, 'wb') as f:
        f.write(png)
    print(f"Generated {filepath} ({width}x{height})")

def clamp(v, min_v=0, max_v=255):
    return max(min_v, min(max_v, int(v)))

# 1. BLADE SLICE: strictly 52px wide, seamless vertically (height = 120px)
# Styled to match the battle-worn dark steel with central spine ridge and edge bevels
def blade_slice_pixel(x, y, w, h):
    center = (w - 1) / 2.0  # 25.5
    dist = abs(x - center)
    norm_dist = dist / center
    
    # Central spine ridge at x ~ 25.5
    is_spine = dist <= 1.2
    
    # Left and right bevel edges (x in [0, 4] and [47, 51])
    is_left_edge = x <= 4
    is_right_edge = x >= 47
    
    # Organic mottled weathered steel texture (scratches and dark carbon patina)
    noise1 = math.sin(x * 1.7 + y * 0.45) * 8 + math.cos(y * 1.8 - x * 0.3) * 6
    noise2 = math.sin(y * 3.2 + x * 0.8) * 5 + math.sin(x * 4.5) * 4
    patina = noise1 + noise2
    
    if is_spine:
        # Sharp raised central ridge with highlight on the right, shadow on the left
        spine_light = 35 if (x >= center) else -25
        val = 65 + spine_light + patina * 0.5
        r = clamp(val)
        g = clamp(val + 1)
        b = clamp(val + 3)
    elif is_left_edge or is_right_edge:
        # Sharp beveled cutting edge with bright silver highlights
        edge_pos = (4 - x) / 4.0 if is_left_edge else (x - 47) / 4.0
        val = 140 + edge_pos * 60 + math.sin(y * 0.25) * 15
        if x == 0 or x == 51:
            val = 210
        r = clamp(val)
        g = clamp(val + 2)
        b = clamp(val + 5)
    else:
        # Dark battle-worn blade face (dark slate grey / charcoal steel)
        # Left half is slightly darker in angled lighting than right half
        side_bias = 12 if (x > center) else -10
        base_steel = 48 + side_bias + patina
        # subtle longitudinal grind marks
        grind = math.sin(x * 7.5) * 6
        val = base_steel + grind
        r = clamp(val)
        g = clamp(val + 1)
        b = clamp(val + 3)
        
    return r, g, b, 255

# 2. BLADE TIP: strictly 52px wide, height = 128px
# Tapers from top (width 52px) down to the sharp gothic point at bottom center (x=25.5, y=120)
def tip_pixel(x, y, w, h):
    center = (w - 1) / 2.0  # 25.5
    dist = abs(x - center)
    
    tip_y = 120.0
    if y > tip_y:
        return 0, 0, 0, 0
        
    # Gothic dagger/sword taper curve
    t = y / tip_y  # 0 at top, 1 at point
    cur_half_width = center * (1.0 - (t ** 1.35))
    
    if dist > cur_half_width + 0.8:
        return 0, 0, 0, 0
    elif dist > cur_half_width:
        # Anti-aliasing boundary
        alpha = int((1.0 - (dist - cur_half_width) / 0.8) * 255)
        return 160, 165, 175, clamp(alpha)
        
    norm_dist = dist / max(cur_half_width, 0.1)
    
    # Continuous central spine running down to the point
    is_spine = dist <= 1.2 * (1.0 - t * 0.7)
    is_edge = norm_dist > 0.84
    
    patina = math.sin(x * 1.5 + y * 0.6) * 7 + math.cos(y * 1.2) * 5
    
    if is_spine:
        spine_light = 35 if (x >= center) else -25
        val = 70 + spine_light + patina * 0.4
        r = clamp(val)
        g = clamp(val + 1)
        b = clamp(val + 3)
    elif is_edge:
        val = 145 + (norm_dist - 0.84) / 0.16 * 60 + math.sin(y * 0.3) * 15
        r = clamp(val)
        g = clamp(val + 2)
        b = clamp(val + 6)
    else:
        side_bias = 12 if (x > center) else -10
        base_steel = 50 + side_bias + patina
        val = base_steel
        r = clamp(val)
        g = clamp(val + 1)
        b = clamp(val + 3)
        
    # Gleaming sharp point
    if y >= tip_y - 3:
        r = clamp(r + 80)
        g = clamp(g + 85)
        b = clamp(b + 95)
        
    return r, g, b, 255

# 3. ANCHOR: The knight holding sword hilt.
# Dimensions: 500w x 560h.
# Center is x=250.
# The sword blade exits at the bottom with EXACT width 52px (x = 224 to 276)
def knight_anchor_pixel(x, y, w, h):
    cx = w / 2.0 # 250
    dx = x - cx
    
    # 1. Sword blade extending down to bottom of image (y >= 430):
    blade_w = 26.0
    if y >= 430:
        if abs(dx) <= blade_w:
            blade_x = int(dx + 25.5)
            blade_x = max(0, min(51, blade_x))
            return blade_slice_pixel(blade_x, y % 120, 52, 120)
        elif abs(dx) <= blade_w + 1.2:
            return 170, 175, 185, 200
            
    # 2. Rock base at the bottom (y from 480 to 560, dx from -220 to 220)
    rock_mask = math.sqrt(((dx) / 225)**2 + ((y - 530) / 45)**2)
    if rock_mask <= 1.0 and abs(dx) > blade_w + 2:
        # Jagged slate rock
        crags = math.sin(dx * 0.15) * 8 + math.cos(y * 0.2) * 6
        rock_val = clamp(35 + crags - (y - 480) * 0.2)
        return rock_val, rock_val, rock_val + 2, 255

    # 3. Crossguard: located around y=390..430
    guard_y = 412
    guard_half_w = 95
    guard_half_h = 16
    if abs(dx) <= guard_half_w and abs(y - guard_y) <= guard_half_h:
        dist_g = math.sqrt((dx / guard_half_w)**2 + ((y - guard_y) / guard_half_h)**2)
        if dist_g <= 1.0:
            quillon = 1.0 - abs(dx) / guard_half_w
            steel = 55 + int(quillon * 65) + int(math.sin(dx * 0.25) * 15)
            # Center diamond crossguard emblem
            if abs(dx) <= 18 and abs(y - guard_y) <= 12:
                gem = 1.0 - (abs(dx)/18.0 + abs(y-guard_y)/12.0)
                if gem > 0:
                    val = 110 + int(gem * 80)
                    return val, val, val + 5, 255
            return clamp(steel), clamp(steel + 2), clamp(steel + 6), 255

    # 4. Sword hilt grip & pommel: y from 260 to 400, dx from -12 to 12
    if y >= 250 and y < 400 and abs(dx) <= 14:
        if abs(dx) <= 10:
            wrap = math.sin(y * 0.5) * 20
            leather = 35 + wrap
            return clamp(leather), clamp(leather), clamp(leather), 255

    # 5. Clasped Gauntlets over sword hilt (y from 230 to 350, dx from -45 to 45)
    hands_dist = math.sqrt((dx / 38)**2 + ((y - 290) / 48)**2)
    if hands_dist <= 1.0:
        plate = 60 + int((1.0 - hands_dist) * 60) + int(math.sin(y * 0.4 + dx * 0.2) * 15)
        # Steel highlight on knuckles
        if y > 270 and y < 320:
            plate += 15
        return clamp(plate), clamp(plate + 2), clamp(plate + 5), 255

    # 6. Gothic Pointed Helmet / Visor (y from 40 to 170, dx from -55 to 55)
    helm_dist = math.sqrt((dx / 52)**2 + ((y - 110) / 68)**2)
    if helm_dist <= 1.0:
        depth = 1.0 - helm_dist
        steel = 52 + int(depth * 75)
        # Spiked crest on top of helmet
        if abs(dx) <= 5 and y < 85:
            steel += 45
        # Visor slit / aperture at y ~ 118
        if abs(y - 118) <= 4 and abs(dx) <= 32:
            return 10, 8, 12, 255
        return clamp(steel), clamp(steel + 2), clamp(steel + 4), 255

    # 7. Pauldrons / Shoulders (dx from -135 to -60, y from 130 to 260 and +60 to +135)
    left_p = math.sqrt(((dx + 105)/55)**2 + ((y - 195)/65)**2)
    right_p = math.sqrt(((dx - 105)/55)**2 + ((y - 195)/65)**2)
    if left_p <= 1.0 or right_p <= 1.0:
        p_val = left_p if left_p <= 1.0 else right_p
        plate = 45 + int((1.0 - p_val) * 70) + int(math.sin(y * 0.2) * 15)
        return clamp(plate), clamp(plate + 2), clamp(plate + 5), 255

    # 8. Chestplate & Gorget (dx from -70 to 70, y from 160 to 360)
    chest_dist = math.sqrt((dx / 68)**2 + ((y - 250) / 90)**2)
    if chest_dist <= 1.0:
        depth = 1.0 - chest_dist
        ridge = max(0, 1.0 - abs(dx) / 8.0) * 35
        steel = 42 + int(depth * 60) + ridge
        return clamp(steel), clamp(steel + 2), clamp(steel + 4), 255

    # 9. Greaves & Knees kneeling down (dx from -100 to 100, y from 360 to 510)
    left_knee = math.sqrt(((dx + 65)/45)**2 + ((y - 425)/65)**2)
    right_knee = math.sqrt(((dx - 65)/45)**2 + ((y - 435)/65)**2)
    if left_knee <= 1.0 or right_knee <= 1.0:
        k_val = left_knee if left_knee <= 1.0 else right_knee
        plate = 45 + int((1.0 - k_val) * 65)
        return clamp(plate), clamp(plate + 2), clamp(plate + 5), 255

    # 10. Billowing ragged dark tattered cape / silhouette (dx from -210 to 210, y from 140 to 520)
    cape_dist = math.sqrt((dx / 195)**2 + ((y - 340) / 180)**2)
    if cape_dist <= 1.0 and y > 130:
        # Tattered edge raggedness
        ragged = math.sin(dx * 0.3) * math.cos(y * 0.25) * 0.15
        if cape_dist + ragged <= 1.0:
            alpha = int((1.0 - cape_dist) * 230)
            fade = 1.0 if y < 490 else max(0, 1.0 - (y - 490)/40.0)
            return 16, 16, 20, clamp(alpha * fade)

    return 0, 0, 0, 0

if __name__ == '__main__':
    os.makedirs('public', exist_ok=True)
    
    # 1. blade-slice.png (52x120)
    create_png(52, 120, blade_slice_pixel, 'public/blade-slice.png')
    create_png(52, 120, blade_slice_pixel, 'blade-slice.png')
    
    # 2. tip.png (52x128)
    create_png(52, 128, tip_pixel, 'public/tip.png')
    create_png(52, 128, tip_pixel, 'tip.png')
    
    # 3. anchor.png (500x560)
    create_png(500, 560, knight_anchor_pixel, 'public/anchor.png')
    create_png(500, 560, knight_anchor_pixel, 'anchor.png')
    print("All 3 assets successfully generated in ./ and ./public/")

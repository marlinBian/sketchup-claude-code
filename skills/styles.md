# Design Style Presets

## Purpose

Pre-defined color palettes and material combinations for quick style application to interior designs.

---

## Style: Japandi 奶油风 (Japandi Cream)

**Description**: Blend of Japanese and Scandinavian aesthetics. Warm creams, natural woods, soft textures.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Warm Cream | `#F5F0E8` | 245, 240, 232 | Walls, ceiling |
| Soft Sand | `#E8DFD0` | 232, 223, 208 | Floor base |
| Warm Beige | `#D4C4B0` | 212, 196, 176 | Accent walls |
| Charcoal | `#3D3D3D` | 61, 61, 61 | Furniture, fixtures |
| Terracotta | `#C67B5C` | 198, 123, 92 | Throw pillows, plants |
| Sage Green | `#9CAF88` | 156, 175, 136 | Plants, accessories |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `japandi_wall_cream` | Paint | `#F5F0E8` | Matte |
| `japandi_wood_oak` | Wood | `#C4A77D` | Oak grain, 200x200 |
| `japandi_fabric_linen` | Fabric | `#E8E4DC` | Linen texture |
| `japandi_matte_black` | Paint | `#3D3D3D` | Matte |
| `japandi_terracotta` | Ceramic | `#C67B5C` | Glossy |

### Application Rules

```
Walls: japandi_wall_cream
Floor: japandi_wood_oak ( herringbone pattern)
Furniture: japandi_wood_oak + japandi_fabric_linen
Accents: japandi_terracotta (cushions, vases)
```

---

## Style: Modern Industrial 现代工业风

**Description**: Exposed structural elements, dark metals, concrete textures, minimal color palette.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Concrete Gray | `#B8B5B0` | 184, 181, 176 | Walls |
| Charcoal Black | `#2A2A2A` | 42, 42, 42 | Metal, furniture |
| Steel Gray | `#71797E` | 113, 121, 126 | Fixtures, pipes |
| Brick Red | `#8B4513` | 139, 69, 19 | Accent walls |
| Warm Wood | `#8B5A2B` | 139, 90, 43 | Wood accents |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `industrial_concrete` | Concrete | `#B8B5B0` | Rough, 400x400 |
| `industrial_metal_black` | Metal | `#2A2A2A` | Brushed, 100x100 |
| `industrial_steel` | Metal | `#71797E` | Brushed |
| `industrial_brick` | Brick | `#8B4513` | Exposed, 300x150 |
| `industrial_wood_dark` | Wood | `#8B5A2B` | Reclaimed |

### Application Rules

```
Walls: industrial_concrete (full height)
Accent wall: industrial_brick
Metal elements: industrial_metal_black
Furniture: industrial_wood_dark + industrial_metal_black
```

---

## Style: Scandinavian 北欧极简

**Description**: Clean lines, white dominant, light woods, functional minimalism.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Pure White | `#FFFFFF` | 255, 255, 255 | Walls, ceiling |
| Off White | `#F7F7F7` | 247, 247, 247 | Large surfaces |
| Light Oak | `#E8DCC8` | 232, 220, 200 | Floor, furniture |
| Pale Gray | `#D3D3D3` | 211, 211, 211 | Textiles |
| Black | `#1A1A1A` | 26, 26, 26 | Accents, fixtures |
| Dusty Rose | `#D4A5A5` | 212, 165, 165 | Soft accents |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `scandi_white` | Paint | `#FFFFFF` | Eggshell |
| `scandi_oak_light` | Wood | `#E8DCC8` | White oak, 250x250 |
| `scandi_gray_soft` | Fabric | `#D3D3D3` | Wool texture |
| `scandi_black` | Metal | `#1A1A1A` | Matte |
| `scandi_rose_dusty` | Fabric | `#D4A5A5` | Linen |

### Application Rules

```
Walls: scandi_white (full)
Floor: scandi_oak_light (plank pattern)
Furniture: scandi_oak_light + scandi_gray_soft
Accents: scandi_black (lamps, hardware)
Textiles: scandi_rose_dusty (cushions, throws)
```

---

## Style: Mediterranean 地中海风

**Description**: Warm terracottas, white walls, blue accents, rustic textures.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Whitewash | `#F8F4F0` | 248, 244, 240 | Walls |
| Terracotta | `#C67B5C` | 198, 123, 92 | Floor, tiles |
| Aegean Blue | `#4A90A4` | 74, 144, 164 | Accents, tiles |
| Olive Green | `#6B7B5F` | 107, 123, 95 | Plants, wood |
| Sand | `#E8DFD0` | 232, 223, 208 | Texture base |
| Warm Wood | `#A67C52` | 166, 124, 82 | Furniture |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `med_whitewash` | Paint | `#F8F4F0` | Lime wash |
| `med_terracotta` | Tile | `#C67B5C` | 200x200, staggered |
| `med_blue_aegean` | Tile | `#4A90A4` | 100x100, subway |
| `med_olive` | Paint | `#6B7B5F` | Matte |
| `med_wood_warm` | Wood | `#A67C52` | Terracotta stain |

### Application Rules

```
Walls: med_whitewash (lime wash finish)
Floor wet areas: med_terracotta (hex pattern)
Accent: med_blue_aegean (kitchen backsplash)
Wood: med_wood_warm (furniture, beams)
```

---

## Style: Bohemian 波西米亚

**Description**: Eclectic mix of patterns, rich jewel tones, layered textures, global influences.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Cream | `#F5F0E6` | 245, 240, 230 | Base |
| Terracotta | `#C67B5C` | 198, 123, 92 | Warm accents |
| Deep Teal | `#1D6B6B` | 29, 107, 107 | Jewel tone |
| Mustard | `#C9A227` | 201, 162, 39 | Pattern accents |
| Plum | `#6B3A5B` | 107, 58, 91 | Rich accent |
| Forest Green | `#3D5A45` | 61, 90, 69 | Plants, textiles |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `boho_cream` | Paint | `#F5F0E6` | Matte |
| `boho_terracotta` | Ceramic | `#C67B5C` | Glossy |
| `boho_teal` | Fabric | `#1D6B6B` | Velvet |
| `boho_mustard` | Fabric | `#C9A227` | Woven |
| `boho_pattern` | Wallpaper | `#6B3A5B` | Moroccan |

### Application Rules

```
Base walls: boho_cream
Furniture: Natural wood + boho_terracotta
Textiles: Mix of boho_teal, boho_mustard, boho_plum
Accent wall: boho_pattern (Moroccan style)
Plants: boho_forest as backdrop
```

---

## Style: Contemporary Minimalist 当代极简

**Description**: Neutral foundation, subtle warm accents, clean architectural lines.

### Color Palette

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| Warm White | `#FAFAF8` | 250, 250, 248 | Walls |
| Greige | `#B5A99A` | 181, 169, 154 | Large surfaces |
| Taupe | `#8B7D6B` | 139, 125, 107 | Wood, leather |
| Deep Charcoal | `#2D2D2D` | 45, 45, 45 | Accents |
| Warm Brass | `#C9A86C` | 201, 168, 108 | Metal fixtures |

### Materials

| Material ID | Type | Color | Texture |
|-------------|------|-------|---------|
| `minimal_warm_white` | Paint | `#FAFAF8` | Eggshell |
| `minimal_greige` | Stone | `#B5A99A` | Honed marble |
| `minimal_taupe_wood` | Wood | `#8B7D6B` | Wide plank |
| `minimal_charcoal` | Metal | `#2D2D2D` | Matte |
| `minimal_brass` | Metal | `#C9A86C` | Brushed |

### Application Rules

```
Walls: minimal_warm_white
Feature surfaces: minimal_greige (marble)
Furniture: minimal_taupe_wood + minimal_charcoal
Fixtures: minimal_brass (taps, handles)
```

---

## Color Format Reference

### Hex Color
```json
{ "color": "#C67B5C" }
```

### RGB
```json
{ "color": [198, 123, 92] }
```

### SketchUp Built-in Material
```json
{ "material_id": "DefaultMaterialName" }
```

---

## Applying a Style

### Apply Full Style
```python
# Apply Japandi style to all surfaces
apply_style("japandi_cream")
```

### Apply Style to Specific Entities
```python
# Apply material to specific wall
apply_material(
    entity_ids=["wall_001", "wall_002"],
    color="#F5F0E8"
)
```

### Custom Color
```python
apply_material(
    entity_ids=["entity_123"],
    color="#C67B5C"  # Hex or RGB
)
```

---

## Material Texture Scaling

Texture scale is specified in material application:

```json
{
  "material_id": "wood_oak",
  "color": "#C4A77D",
  "texture_scale": [200, 200]  // 200mm x 200mm tile
}
```

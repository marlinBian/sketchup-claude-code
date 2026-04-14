# Spatial Constraints Specification

## Coordinate System

The SCC protocol uses a consistent coordinate system across all layers.

---

## Units

### Internal Units: Millimeters (mm)

All coordinates in the protocol are in **millimeters**. No unit suffixes.

| Value | Meaning |
|-------|---------|
| `1000` | 1000 millimeters (1 meter) |
| `2.5` | 2.5 millimeters (not 2.5 meters) |

### Unit Conversion (Python Layer Responsibility)

The Python MCP server is responsible for converting user-facing units to mm:

| User Input | Internal Value |
|------------|----------------|
| `2m` | `2000` mm |
| `3m x 4m` | `3000` x `4000` mm |
| `6 feet` | `1828.8` mm |
| `12 inches` | `304.8` mm |

---

## Axis Conventions

### Z-Up Coordinate System

- **X-axis**: Positive = East
- **Y-axis**: Positive = North
- **Z-axis**: Positive = Up (elevation)

```
        Z
        ↑
        │   Y
        │  /
        │ /
        │/____ X
       /____
```

### SketchUp Compatibility

The protocol matches SketchUp's internal coordinate system:
- Origin: Model origin (0, 0, 0)
- Units: Millimeters
- Z-up: Yes

---

## Coordinate Representation

### Points

Arrays of 3 numbers: `[x, y, z]`

```json
[1000, 2000, 500]
```

### Bounding Boxes

Two points: `min` (lower-left-back) and `max` (upper-right-front)

```json
{
  "min": [0, 0, 0],
  "max": [2000, 1000, 500]
}
```

### Vertex Arrays

Ordered vertex lists for face creation. Vertices must be coplanar.

```json
[[0, 0, 0], [2000, 0, 0], [2000, 1000, 0], [0, 1000, 0]]
```

---

## Geometry Validation Rules

### Face Creation

1. Vertices must be coplanar (all points on same plane)
2. Minimum 3 vertices
3. Vertices must not be collinear
4. Polygon must not self-intersect
5. Resulting face area must be > 0

### Box Creation

1. All dimensions (width, depth, height) must be > 0
2. Corner point + dimensions must not produce invalid geometry

### Group Creation

1. All referenced entities must exist
2. At least one entity required

---

## Spatial Operations

### Distance Calculation

Uses Euclidean distance in 3D space:

```
d = √((x₂-x₁)² + (y₂-y₁)² + (z₂-z₁)²)
```

### Area Calculation (Faces)

Uses the Shoelace formula for planar polygons.

### Volume Calculation (Closed Meshes)

Uses divergence theorem with face normals.

---

## Orientation

### Face Normals

Outward-facing normals using right-hand rule.

```
[v₁, v₂, v₃, ...]
   ↓
  Right-hand rule determines normal direction
```

### Layer Conventions

| Layer Name | Purpose |
|------------|---------|
| `Walls` | Wall geometry |
| `Floors` | Floor surfaces |
| `Ceilings` | Ceiling surfaces |
| `Windows` | Window openings |
| `Doors` | Door openings |
| `Furniture` | Furniture groups |
| `Fixtures` | Bathroom/kitchen fixtures |

---

## Transformation Conventions

### Position (Translation)

Single point `[x, y, z]`

### Scale

Uniform or per-axis scale factors

### Rotation

Not supported in v1.0. Faces created in XY plane, then grouped and rotated.

---

## Performance Considerations

- Coordinates stored as integers (mm precision)
- Sub-millimeter precision not supported
- Large models (>1M vertices) should use chunked queries

---

## Wall Geometry

### Wall Alignment Modes

Walls have three alignment modes relative to the centerline:

| Mode | Description | Use Case |
|------|-------------|----------|
| `"center"` | Wall centered on line | Standard architectural drawings |
| `"inner"` | Wall inside the line | Interior walls, maximize space |
| `"outer"` | Wall outside the line | Exterior walls, weatherproofing |

### Alignment Offset Calculation

Given:
- `P1` = start point `[x1, y1, z1]`
- `P2` = end point `[x2, y2, z2]`
- `thickness` = wall thickness
- `height` = wall height

**Direction vector (along wall):**
```
D = normalize(P2 - P1) = [dx, dy, dz]
where dx = (x2-x1)/length, dy = (y2-y1)/length, dz = (z2-z1)/length
```

**Perpendicular normal (Z-up, points left of wall direction):**
```
N = [-dy, dx, 0]  # 2D normal in XY plane, left-hand side
```

**Offset for alignment:**
```
offset = thickness / 2  (for center alignment)
offset = thickness       (for inner alignment)
offset = 0              (for outer alignment)
```

### Vertex Calculation for Wall

Creates an 8-vertex box (3D extrusion of wall path):

```
P1 = [x1, y1, z1]  (start, at floor level)
P2 = [x2, y2, z2]  (end, at floor level)

Wall is extruded up by `height` in Z direction.
Wall is extruded perpendicular by `thickness` using normal N.

Vertices (counter-clockwise when viewed from above, for outward normals):

For alignment = "center":
  v1 = P1 + N * (thickness/2)           (bottom-left at start)
  v2 = P1 - N * (thickness/2)           (bottom-right at start)
  v3 = P2 - N * (thickness/2)           (bottom-right at end)
  v4 = P2 + N * (thickness/2)           (bottom-left at end)
  v5 = v1 + [0, 0, height]              (top-left at start)
  v6 = v2 + [0, 0, height]              (top-right at start)
  v7 = v3 + [0, 0, height]              (top-right at end)
  v8 = v4 + [0, 0, height]              (top-left at end)

For alignment = "inner":
  v1 = P1 + N * thickness
  v2 = P1
  v3 = P2
  v4 = P2 + N * thickness
  (then extruded up by height)

For alignment = "outer":
  v1 = P1
  v2 = P1 - N * thickness
  v3 = P2 - N * thickness
  v4 = P2
  (then extruded up by height)
```

### Wall Creation Payload

```json
{
  "operation_type": "create_wall",
  "payload": {
    "start": [0, 0, 0],
    "end": [3000, 0, 0],
    "height": 2400,
    "thickness": 150,
    "alignment": "center",
    "material_id": "mat_concrete",
    "layer": "Walls"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `start` | number[] | Yes | Start point [x, y, z] in mm |
| `end` | number[] | Yes | End point [x, y, z] in mm |
| `height` | number | Yes | Wall height in mm |
| `thickness` | number | Yes | Wall thickness in mm |
| `alignment` | string | No | `"center"` (default), `"inner"`, `"outer"` |
| `material_id` | string | No | Material to apply |
| `layer` | string | No | Layer name (default: `"Walls"`) |

### Wall Validation Rules

1. `start` and `end` must be different points
2. `height` > 0
3. `thickness` > 0
4. `alignment` must be one of: `"center"`, `"inner"`, `"outer"`
5. Wall is always vertical (extruded in Z direction)

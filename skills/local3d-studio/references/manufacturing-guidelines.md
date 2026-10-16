# 3D Print & Slicer Manufacturing Guidelines

## Slicer Compatibility
Local3D Studio outputs files ready for direct import into modern 3D slicers:
- **Bambu Studio** / **OrcaSlicer**: Native `.3mf` files preserving unit scale in millimeters and bed placement.
- **PrusaSlicer** / **Cura**: Standard binary `.stl` files.

## Geometric Tolerances
- **Bed Contact ($Z=0$)**: Every asset is plane-clipped or aligned so that the bottom-most vertices lie exactly at $Z=0.00$ mm.
- **Key & Mortise Joinery (`auto_split_model`)**:
  - Clearance tolerance: 0.20 mm for standard FDM printing (0.4mm nozzle, 0.2mm layer height).
  - Key angle: 10° draft angle for easy push-fit insertion.
  - Key orientation: Aligned perpendicular to the split cut plane.

## Wall Thickness & Voxel Sizing
- **Tier 1 (Eco / 16GB)**: Voxel size 0.0025, target 80,000 triangles.
- **Tier 3 (Pro 64GB)**: Voxel size 0.0025, target 90,000 triangles.
- **Tier 4 (Ultra)**: Voxel size 0.0035, target 120,000 triangles.

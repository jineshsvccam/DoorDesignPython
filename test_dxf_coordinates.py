"""
Test script to extract frame coordinates from DXF files in outputBulk folder.
"""
from typing import cast
from ezdxf.filemanagement import readfile
from ezdxf.entities.lwpolyline import LWPolyline
import os
from pathlib import Path


def get_frame_coordinates(dxf_path):
    """Extract all frame coordinates from a DXF file.
    
    Returns a dict with layer names as keys and lists of coordinates as values.
    """
    try:
        doc = readfile(dxf_path)
        msp = doc.modelspace()
        
        frames = {}
        
        # Iterate through all entities
        for entity in msp:
            layer = entity.dxf.layer
            
            # Look for polylines (frames are typically polylines)
            if entity.dxftype() == 'LWPOLYLINE':
                polyline = cast(LWPolyline, entity)
                points = list(polyline.get_points())
                if layer not in frames:
                    frames[layer] = []
                frames[layer].append({
                    'type': 'LWPOLYLINE',
                    'points': points,
                    'num_points': len(points)
                })
            
            # Look for lines
            elif entity.dxftype() == 'LINE':
                start = (entity.dxf.start.x, entity.dxf.start.y)
                end = (entity.dxf.end.x, entity.dxf.end.y)
                if layer not in frames:
                    frames[layer] = []
                frames[layer].append({
                    'type': 'LINE',
                    'start': start,
                    'end': end
                })
            
            # Look for circles (holes)
            elif entity.dxftype() == 'CIRCLE':
                center = (entity.dxf.center.x, entity.dxf.center.y)
                radius = entity.dxf.radius
                if layer not in frames:
                    frames[layer] = []
                frames[layer].append({
                    'type': 'CIRCLE',
                    'center': center,
                    'radius': radius
                })
        
        return frames
    
    except Exception as e:
        print(f"Error reading {dxf_path}: {e}")
        return None


def analyze_dxf_file(dxf_path):
    """Analyze a single DXF file and print only main frame coordinates."""
    print(f"\n{'='*80}")
    print(f"Analyzing: {Path(dxf_path).name}")
    print(f"{'='*80}")
    
    frames = get_frame_coordinates(dxf_path)
    
    if not frames:
        print("No frames found or error reading file")
        return
    
    # Get only CUT layer polylines (main frames)
    cut_layer = frames.get('CUT', [])
    if not cut_layer:
        print("No CUT layer found")
        return
    
    # Filter for main frames (polylines with 5 points and large bounding boxes)
    main_frames = []
    for entity in cut_layer:
        if entity['type'] == 'LWPOLYLINE' and entity['num_points'] == 5:
            xs = [p[0] for p in entity['points']]
            ys = [p[1] for p in entity['points']]
            width = max(xs) - min(xs)
            height = max(ys) - min(ys)
            # Consider it a main frame if width or height > 500mm
            if width > 500 or height > 500:
                main_frames.append({
                    'x_min': min(xs),
                    'x_max': max(xs),
                    'y_min': min(ys),
                    'y_max': max(ys),
                    'width': width,
                    'height': height
                })
    
    if not main_frames:
        print("No main frames found")
        return
    
    # Sort by Y position to show doors in order
    main_frames.sort(key=lambda f: f['y_min'])
    
    print(f"\nFound {len(main_frames)} main door frames:\n")
    for i, frame in enumerate(main_frames, 1):
        print(f"Frame {i}:")
        print(f"  Y range: [{frame['y_min']:.1f} to {frame['y_max']:.1f}]  (height: {frame['height']:.1f}mm)")
        print(f"  X range: [{frame['x_min']:.1f} to {frame['x_max']:.1f}]  (width: {frame['width']:.1f}mm)")
        
        if i > 1:
            gap = frame['y_min'] - main_frames[i-2]['y_max']
            if gap < 0:
                print(f"  [OVERLAP] with Frame {i-1}: {abs(gap):.1f}mm")
            else:
                print(f"  [OK] Gap from Frame {i-1}: {gap:.1f}mm")
        print()


def analyze_all_dxf_in_folder(folder_path):
    """Analyze all DXF files in a folder."""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    dxf_files = list(folder.glob("*.dxf"))
    
    if not dxf_files:
        print(f"No DXF files found in {folder_path}")
        return
    
    print(f"Found {len(dxf_files)} DXF files in {folder_path}")
    
    for dxf_file in dxf_files:
        analyze_dxf_file(str(dxf_file))


if __name__ == "__main__":
    # Get the script directory and build path to outputBulk
    script_dir = Path(__file__).parent
    output_folder = script_dir / "outputBulk"
    
    # Analyze all DXF files
    analyze_all_dxf_in_folder(output_folder)

"""
Test script to extract frame coordinates from DXF files in outputBulk folder.
"""
from typing import cast
from ezdxf.filemanagement import readfile
from ezdxf.entities.lwpolyline import LWPolyline
import os
import json
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


def load_manifest_data(dxf_path):
    """Load the corresponding JSON manifest for the DXF file."""
    json_path = Path(dxf_path).with_suffix('.json')
    
    if not json_path.exists():
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('doors', [])
    except Exception as e:
        print(f"Error reading manifest {json_path}: {e}")
        return None


def analyze_dxf_file(dxf_path, output_json=False):
    """Analyze a single DXF file and identify how many doors are placed."""
    if not output_json:
        print(f"\n{'='*80}")
        print(f"Analyzing: {Path(dxf_path).name}")
        print(f"{'='*80}")
    
    # Load manifest data
    manifest_doors = load_manifest_data(dxf_path)
    
    frames = get_frame_coordinates(dxf_path)
    
    if not frames:
        if not output_json:
            print("No frames found or error reading file")
        return None
    
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
                    'height': height,
                    'center_x': (min(xs) + max(xs)) / 2,
                    'center_y': (min(ys) + max(ys)) / 2
                })
    
    if not main_frames:
        print("No main frames found")
        return
    
    # Step 1: Identify frame pairs (outer + inner frames that overlap significantly)
    # Two frames form a pair if they're nearly concentric (one inside the other)
    # with very high overlap (>95%) and similar positioning
    frame_pairs = []
    used_frames = set()
    
    main_frames.sort(key=lambda f: (f['y_min'], f['x_min']))
    
    for i, frame1 in enumerate(main_frames):
        if i in used_frames:
            continue
        
        best_match = None
        best_match_idx = None
        best_score = 0
        
        for j, frame2 in enumerate(main_frames):
            if j in used_frames or i == j or j <= i:
                continue
            
            # Calculate overlap ratios
            x_overlap = max(0, min(frame1['x_max'], frame2['x_max']) - max(frame1['x_min'], frame2['x_min']))
            y_overlap = max(0, min(frame1['y_max'], frame2['y_max']) - max(frame1['y_min'], frame2['y_min']))
            
            x_min_size = min(frame1['x_max'] - frame1['x_min'], frame2['x_max'] - frame2['x_min'])
            y_min_size = min(frame1['y_max'] - frame1['y_min'], frame2['y_max'] - frame2['y_min'])
            
            x_overlap_ratio = x_overlap / x_min_size if x_min_size > 0 else 0
            y_overlap_ratio = y_overlap / y_min_size if y_min_size > 0 else 0
            
            # Check if frames are centered similarly (one inside the other)
            frame1_center_x = (frame1['x_min'] + frame1['x_max']) / 2
            frame1_center_y = (frame1['y_min'] + frame1['y_max']) / 2
            frame2_center_x = (frame2['x_min'] + frame2['x_max']) / 2
            frame2_center_y = (frame2['y_min'] + frame2['y_max']) / 2
            
            center_dist_x = abs(frame1_center_x - frame2_center_x)
            center_dist_y = abs(frame1_center_y - frame2_center_y)
            
            # Frames are a pair if they have very high overlap AND centers are very close
            # (indicating one frame is inside the other, typical of outer+inner frame)
            if x_overlap_ratio > 0.95 and y_overlap_ratio > 0.95 and center_dist_x < 20 and center_dist_y < 20:
                score = (x_overlap_ratio + y_overlap_ratio) / 2
                if score > best_score:
                    best_score = score
                    best_match = frame2
                    best_match_idx = j
        
        if best_match is not None:
            frame_pairs.append([frame1, best_match])
            used_frames.add(i)
            used_frames.add(best_match_idx)
    
    if not frame_pairs:
        print("No frame pairs found")
        return
    
    # Step 2: Identify doors from frame pairs
    # Single door = 1 frame pair (2 frames)
    # Double door = 2 frame pairs (4 frames) that are adjacent/close together
    doors = []
    used_pairs = set()
    
    for i, pair1 in enumerate(frame_pairs):
        if i in used_pairs:
            continue
        
        # Calculate bounding box for this pair
        p1_x_min = min(f['x_min'] for f in pair1)
        p1_x_max = max(f['x_max'] for f in pair1)
        p1_y_min = min(f['y_min'] for f in pair1)
        p1_y_max = max(f['y_max'] for f in pair1)
        
        # Try to find another pair that forms a double door with this one
        found_double = False
        for j, pair2 in enumerate(frame_pairs):
            if j in used_pairs or i == j:
                continue
            
            p2_x_min = min(f['x_min'] for f in pair2)
            p2_x_max = max(f['x_max'] for f in pair2)
            p2_y_min = min(f['y_min'] for f in pair2)
            p2_y_max = max(f['y_max'] for f in pair2)
            
            # Check if these pairs form a double door
            # Be VERY strict - only merge if they're truly part of same door
            
            # Pattern 1: Side-by-side (share Y coordinates almost perfectly, adjacent in X)
            y_overlap = max(0, min(p1_y_max, p2_y_max) - max(p1_y_min, p2_y_min))
            y_total = max(p1_y_max, p2_y_max) - min(p1_y_min, p2_y_min)
            y_overlap_ratio = y_overlap / y_total if y_total > 0 else 0
            
            # Check X gap (should be very small for double door halves)
            x_gap = min(abs(p1_x_max - p2_x_min), abs(p2_x_max - p1_x_min))
            
            # Pattern 2: Vertically stacked (share X coordinates almost perfectly, very close in Y)
            x_overlap = max(0, min(p1_x_max, p2_x_max) - max(p1_x_min, p2_x_min))
            x_total = max(p1_x_max, p2_x_max) - min(p1_x_min, p2_x_min)
            x_overlap_ratio = x_overlap / x_total if x_total > 0 else 0
            y_gap = min(abs(p1_y_max - p2_y_min), abs(p2_y_max - p1_y_min))
            
            # Double door only if:
            # - Side-by-side: >98% Y overlap AND X gap < 10mm (touching/very close)
            # - Stacked: >98% X overlap AND Y gap < 10mm (for rotated double doors)
            is_double = (y_overlap_ratio > 0.98 and x_gap < 10) or \
                       (x_overlap_ratio > 0.98 and y_gap < 10)
            
            if is_double:
                # This is a double door (4 frames)
                all_frames = pair1 + pair2
                doors.append({
                    'type': 'Double',
                    'frames': all_frames,
                    'frame_count': 4
                })
                used_pairs.add(i)
                used_pairs.add(j)
                found_double = True
                break
        
        if not found_double:
            # This is a single door (2 frames)
            doors.append({
                'type': 'Single',
                'frames': pair1,
                'frame_count': 2
            })
            used_pairs.add(i)
    
    # Step 3: Calculate space occupied and prepare output
    result = {
        'file_name': Path(dxf_path).name,
        'door_count': len(doors),
        'expected_count': len(manifest_doors) if manifest_doors else None,
        'doors': []
    }
    
    # Display door information and store bounding boxes
    for idx, door in enumerate(doors, 1):
        frames = door['frames']
        
        # Calculate space occupied by this door
        x_min = min(f['x_min'] for f in frames)
        x_max = max(f['x_max'] for f in frames)
        y_min = min(f['y_min'] for f in frames)
        y_max = max(f['y_max'] for f in frames)
        width = x_max - x_min
        height = y_max - y_min
        
        # Store bounding box for overlap check
        door['bbox'] = {
            'x_min': x_min,
            'x_max': x_max,
            'y_min': y_min,
            'y_max': y_max,
            'width': width,
            'height': height
        }
        
        door_data = {
            'door_number': idx,
            'type': door['type'],
            'frame_count': door['frame_count'],
            'space_occupied': {
                'width': round(width, 1),
                'height': round(height, 1)
            },
            'position': {
                'x_min': round(x_min, 1),
                'x_max': round(x_max, 1),
                'y_min': round(y_min, 1),
                'y_max': round(y_max, 1)
            }
        }
        
        # Try to match with manifest data
        if manifest_doors and idx <= len(manifest_doors):
            manifest = manifest_doors[idx - 1]
            # Get metadata from transformed section (has actual dimensions)
            meta = manifest.get('transformed', {}).get('metadata', {})
            door_data['manifest'] = {
                'label': meta.get('label', 'Unknown'),
                'file_name': meta.get('file_name', 'Unknown'),
                'json_dimensions': {
                    'width': round(meta.get('width', 0), 1),
                    'height': round(meta.get('height', 0), 1)
                },
                'rotated': meta.get('rotated', False)
            }
        
        result['doors'].append(door_data)
        
        if not output_json:
            print(f"Door {idx}:")
            print(f"  Type: {door['type']} Door")
            print(f"  Frame count: {door['frame_count']}")
            print(f"  Space occupied: {width:.1f}mm (W) x {height:.1f}mm (H)")
            print(f"  Position: X=[{x_min:.1f}, {x_max:.1f}], Y=[{y_min:.1f}, {y_max:.1f}]")
            
            if 'manifest' in door_data:
                m = door_data['manifest']
                print(f"  Manifest: {m['label']} ({m['file_name']})")
                print(f"    JSON dimensions: {m['json_dimensions']['width']:.1f}mm (W) x {m['json_dimensions']['height']:.1f}mm (H), Rotated: {m['rotated']}")
            
            print()
    
    # Check for overlaps between doors
    overlaps = []
    for i, door1 in enumerate(doors):
        for j, door2 in enumerate(doors):
            if i >= j:
                continue
            
            bbox1 = door1['bbox']
            bbox2 = door2['bbox']
            
            # Check if bounding boxes overlap
            x_overlap = max(0, min(bbox1['x_max'], bbox2['x_max']) - max(bbox1['x_min'], bbox2['x_min']))
            y_overlap = max(0, min(bbox1['y_max'], bbox2['y_max']) - max(bbox1['y_min'], bbox2['y_min']))
            
            if x_overlap > 0 and y_overlap > 0:
                overlaps.append({
                    'door_1': i + 1,
                    'door_2': j + 1,
                    'overlap_area': {
                        'width': round(x_overlap, 1),
                        'height': round(y_overlap, 1)
                    }
                })
                if not output_json:
                    print(f"WARNING: Door {i+1} and Door {j+1} overlap!")
                    print(f"  Overlap area: {x_overlap:.1f}mm (W) x {y_overlap:.1f}mm (H)")
                    print()
    
    result['overlaps'] = overlaps
    result['has_overlaps'] = len(overlaps) > 0
    result['status'] = 'FAIL' if result['has_overlaps'] else 'PASS'
    
    if not output_json:
        if not result['has_overlaps']:
            print("✓ No overlaps detected - all doors are properly separated")
            print()
    
    # Write JSON to file in the same folder as DXF
    json_output_path = Path(dxf_path).parent / f"{Path(dxf_path).stem}_analysis.json"
    try:
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        if not output_json:
            print(f"Analysis saved to: {json_output_path.name}")
            print()
    except Exception as e:
        if not output_json:
            print(f"Error saving JSON: {e}")
    
    return result


def analyze_all_dxf_in_folder(folder_path, output_json=False):
    """Analyze all DXF files in a folder."""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"Folder not found: {folder_path}")
        return
    
    dxf_files = list(folder.glob("*.dxf"))
    
    if not dxf_files:
        print(f"No DXF files found in {folder_path}")
        return
    
    if not output_json:
        print(f"Found {len(dxf_files)} DXF files in {folder_path}")
    
    all_results = []
    for dxf_file in dxf_files:
        result = analyze_dxf_file(str(dxf_file), output_json=output_json)
        if result:
            all_results.append(result)
    
    # Create summary report
    summary = {
        'total_files': len(all_results),
        'bins': all_results,
        'overall_status': 'PASS' if all(r['status'] == 'PASS' for r in all_results) else 'FAIL',
        'pass_count': sum(1 for r in all_results if r['status'] == 'PASS'),
        'fail_count': sum(1 for r in all_results if r['status'] == 'FAIL')
    }
    
    # Write summary JSON
    summary_path = folder / "analysis_summary.json"
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        if not output_json:
            print(f"\n{'='*80}")
            print("SUMMARY:")
            print(f"  Total bins analyzed: {summary['total_files']}")
            print(f"  Passed: {summary['pass_count']}")
            print(f"  Failed: {summary['fail_count']}")
            print(f"  Overall Status: {summary['overall_status']}")
            print(f"  Summary saved to: {summary_path.name}")
            print(f"{'='*80}")
    except Exception as e:
        if not output_json:
            print(f"Error saving summary: {e}")
    
    return summary


if __name__ == "__main__":
    import argparse
    
    # Get the repository root (one level up from tools directory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    output_folder = repo_root / "outputBulk"
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Analyze DXF files to count doors and detect overlaps')
    parser.add_argument('--file', type=str, help='Analyze a specific DXF file (e.g., bin_1_transformed.dxf)')
    parser.add_argument('--folder', type=str, help='Analyze all DXF files in a specific folder')
    parser.add_argument('--json', action='store_true', help='Output results in JSON format')
    
    args = parser.parse_args()
    
    if args.file:
        # Analyze a single file
        file_path = output_folder / args.file if not Path(args.file).is_absolute() else Path(args.file)
        
        if not file_path.exists():
            print(f"File not found: {file_path}")
        else:
            if not args.json:
                print(f"Analyzing single file: {file_path.name}\n")
            result = analyze_dxf_file(str(file_path), output_json=args.json)
            if args.json and result:
                print(json.dumps(result, indent=2))
    elif args.folder:
        # Analyze all files in specified folder
        summary = analyze_all_dxf_in_folder(args.folder, output_json=args.json)
        if args.json and summary:
            print(json.dumps(summary, indent=2))
    else:
        # Default: Analyze all DXF files in outputBulk folder
        summary = analyze_all_dxf_in_folder(output_folder, output_json=args.json)
        if args.json and summary:
            print(json.dumps(summary, indent=2))

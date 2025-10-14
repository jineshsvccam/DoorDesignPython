from ezdxf.filemanagement import new
import math
from typing import Any, cast

# Create a new DXF document with a default dimension style setup
doc = new("R2010", setup=True)
msp = doc.modelspace()
doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})  # Red


def dim_base_for_edge(p1, p2, offset, sign=1):
	"""Return a base point for a linear dimension for edge p1->p2 offset by `offset` units
	in the perpendicular direction. sign=1 moves to one side, sign=-1 to the other."""
	x1, y1 = p1
	x2, y2 = p2
	dx = x2 - x1
	dy = y2 - y1
	length = math.hypot(dx, dy)
	if length == 0:
		return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
	# unit normal (perp) = (-dy/len, dx/len)
	nx = -dy / length
	ny = dx / length
	mx = (x1 + x2) / 2.0
	my = (y1 + y2) / 2.0
	return (mx + sign * nx * offset, my + sign * ny * offset)


# --- First rectangle (original) ---
rect1_w = 10
rect1_h = 5
p1 = (0, 0)
p2 = (rect1_w, 0)
p3 = (rect1_w, rect1_h)
p4 = (0, rect1_h)
msp.add_lwpolyline([p1, p2, p3, p4, p1])

offset = 0.5
# bottom (horizontal) dimension for rect1: place the dim line offset downwards
base_bottom = dim_base_for_edge(p1, p2, offset+1, sign=-1)
dim_bottom = msp.add_linear_dim(base=base_bottom, p1=p1, p2=p2, angle=0, dxfattribs={"layer": "DIMENSIONS"})
dim_bottom.render()

# right (vertical) dimension for rect1: place the dim line offset to the right
base_right = dim_base_for_edge(p2, p3, offset, sign=1)
dim_right = msp.add_linear_dim(base=base_right, p1=p2, p2=p3, angle=90, dxfattribs={"layer": "DIMENSIONS"})
dim_right.render()


# --- Second rectangle (new) ---
# Place its lower-left corner at (0.5, -1)
rect2_origin = (0.5, -1)
rect2_w = 8
rect2_h = 7
q1 = rect2_origin
q2 = (rect2_origin[0] + rect2_w, rect2_origin[1])
q3 = (rect2_origin[0] + rect2_w, rect2_origin[1] + rect2_h)
q4 = (rect2_origin[0], rect2_origin[1] + rect2_h)
msp.add_lwpolyline([q1, q2, q3, q4, q1])

# Add dims for second rect using same offset (0.5)
# For the second rectangle we want the dims on the top (horizontal) and left (vertical)
# Top: use top edge q4->q3 and offset upward (sign=+1)
base_top2 = dim_base_for_edge(q4, q3, offset, sign=1)
dim_top2 = msp.add_linear_dim(base=base_top2, p1=q4, p2=q3, angle=0, dxfattribs={"layer": "DIMENSIONS"})
dim_top2.render()

# Left: use left edge q1->q4 and offset to the left (sign=+1)
base_left2 = dim_base_for_edge(q1, q4, offset+1, sign=1)
dim_left2 = msp.add_linear_dim(base=base_left2, p1=q1, p2=q4, angle=90, dxfattribs={"layer": "DIMENSIONS"})
dim_left2.render()


# Save the drawing
doc.saveas("rectangle_with_dimensions.dxf")
print("DXF file 'rectangle_with_dimensions.dxf' created.")

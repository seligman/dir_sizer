#!/usr/bin/env python3

from colorsys import hsv_to_rgb
from math import cos
from utils import Folder, size_to_string, count_to_string
import json

class TreeMapNode:
    __slots__ = ("x", "y", "width", "height", "current_height", "vertical", "area", "value", "output", "key")
    def __init__(self, width=0, height=0, value=0, key=None):
        self.x = 0
        self.y = 0
        self.current_height = 0
        self.vertical = False
        self.width = width
        self.height = height
        self.area = 0
        self.value = value
        self.key = key
        self.output = []

def plot(width, height, folder):
    temp = TreeMapNode(width=width, height=height)
    values = [TreeMapNode(value=value.size, key=key) for key, value in folder.sub.items()]
    remaining = folder.size - sum(x.value for x in values)
    if remaining > 0:
        values.append(TreeMapNode(value=remaining))
    _squarify(temp, _prepare_nodes(temp, values), [], _get_width(temp), 0)
    return temp.output

def _prepare_nodes(temp, values):
    temp_sum = sum(x.value for x in values if x.value > 0)
    ret = [x for x in values if (x.value / temp_sum) >= 0.01]
    ret.sort(key=lambda x: x.value, reverse=True)
    temp_sum = sum(x.value for x in ret)
    total_area = temp.width * temp.height
    for cur in ret:
        cur.area = (cur.value / temp_sum) * total_area
    return ret

def _squarify(temp, values, current_row, width, bail):
    if bail > 100:
        return
    
    next_iter_preview = current_row[:]
    if len(values) > 1:
        next_iter_preview.append(values[0])
    
    current_ratio = _calc_aspect_ratio(current_row, width)
    next_ratio = _calc_aspect_ratio(next_iter_preview, width)

    if current_ratio == 0 or (next_ratio < current_ratio and next_ratio >= 1):
        if len(values) > 0:
            current_row.append(values.pop(0))
        temp.current_height = _calc_height(current_row, width)
        if len(values) > 0:
            _squarify(temp, values, current_row, width, bail + 1)
        else:
            _layout_row(temp, current_row)
    else:
        _layout_row(temp, current_row)
        _squarify(temp, values, [], _get_width(temp), bail + 1)

def _layout_row(temp, row_nodes):
    x, y = temp.x, temp.y

    if not temp.vertical:
        if temp.height != temp.current_height:
            temp.y = temp.height - temp.current_height

    for cur in row_nodes:
        if temp.current_height > 0:
            width, height = 0, 0
            if temp.vertical:
                width = temp.current_height
                height = cur.area / temp.current_height
            else:
                width = cur.area / temp.current_height
                height = temp.current_height
            cur.x, cur.y, cur.width, cur.height = temp.x, temp.y, width, height
            temp.output.append(cur)
            if temp.vertical:
                temp.y += height
            else:
                temp.x += width

    if temp.vertical:
        temp.x += temp.current_height
        temp.y = y
        temp.width -= temp.current_height
    else:
        temp.x = x
        temp.y = y
        temp.height -= temp.current_height

    temp.current_height = 0

def _calc_aspect_ratio(current_row, width):
    if len(current_row) == 0:
        return 0
    sum_of_areas = sum(x.area for x in current_row)
    if sum_of_areas == 0:
        return 0
    max_area = max(x.area for x in current_row)
    min_area = max(x.area for x in current_row)
    width_squared = width * width
    sum_of_areas_squared = sum_of_areas * sum_of_areas
    return max((width_squared * max_area) / sum_of_areas_squared, sum_of_areas_squared / (width_squared * min_area))

def _calc_height(current_row, width):
    if width > 0:
        return sum(x.area for x in current_row) / width
    else:
        return 0

def _get_width(temp):
    if temp.height > temp.width:
        temp.vertical = False
        return temp.width
    else:
        temp.vertical = True
        return temp.height

def get_color(depth):
    depth += 1
    hue = depth * 40
    red = 0.47450980392156861 + 0.20392156862745098 * cos(0.017453292519943295 * hue)
    green = 0.52352941176470591 - 0.0803921568627451 * cos(0.017453292519943295 * hue)
    blue = 0.47254901960784312 + 0.19411764705882353 * cos(0.017453292519943295 * hue + 1.8849555921538759)

    if depth % 2 == 1:
        saturation = 0.75
        red = red * saturation + 1.0 - saturation;
        green = green * saturation + 1.0 - saturation;
        blue = blue * saturation + 1.0 - saturation;

    return f"#{int(red*255):02x}{int(green*255):02x}{int(blue*255):02x}"

def draw_layout(abstraction, width, height, x, y, folder, tooltips, path, depth=0):
    if width < 20 or height < 20:
        return ""

    padding = 5

    x += padding
    y += padding
    width -= padding * 2
    height -= padding * 2

    tool_id = f"t{len(tooltips)}"
    tooltips[tool_id] = [
        abstraction.join(path),
        size_to_string(folder.size),
        count_to_string(folder.count),
    ]
    
    html = f'{"  " * depth}<div id="{tool_id}" style="'
    html += f'width:{round(width)}px;'
    html += f'height:{round(height)}px;'
    html += f'left:{round(x)}px;'
    html += f'top:{round(y)}px;'
    html += f'background-color:{get_color(depth)}'
    html += f'">\n'

    x = 0
    y = 0

    width -= 1
    height -= 1

    temp = plot(width, height, folder)

    for cur in temp:
        if cur.width >= 10 and cur.height >= 10 and cur.key is not None:
            html += draw_layout(
                abstraction, 
                cur.width, cur.height, cur.x + x, cur.y + y, 
                folder[cur.key], tooltips, path + [cur.key], depth + 1
            )
    html += f'{"  " * depth}</div>\n'
    return html

def get_webpage(folder, width, height):
    import s3_abstraction
    tooltips = {}
    tree_html = draw_layout(s3_abstraction, width, height, 0, 0, folder, tooltips, [])
    tooltips = ",\n".join(json.dumps(x) + ":" + json.dumps(y, separators=(',', ':')) for x,y in tooltips.items())

    return """<!DOCTYPE html>
<html>
<head>
<title>Dir Sizer</title>
<style>
div {
    border-radius:5px;
    border-width:1px;
    border-style:solid;
    position:absolute;
}
.tooltip {
    display: none;
    background: #C8C8C8;
    margin: 25px;
    padding: 10px;
    position: absolute;
    z-index: 1000;
}
</style>
<script>
document.addEventListener('mousemove', on_mousemove, false);
var last = null;
var lastColor = "";
var tooltips = {""" + tooltips + """};
function safe_html(value) {
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function on_mousemove(e) {
    var tooltip = document.getElementById("tooltip");
    tooltip.style.left = e.pageX + 'px';
    tooltip.style.top = e.pageY + 'px';
    var cur = e.srcElement;
    if (cur.tagName != "DIV" || !(cur.id in tooltips)) {
        cur = null;
    }

    if (last != cur) {
        if (last != null) {
            last.style.backgroundColor = lastColor;
        }
        if (cur != null) {
            lastColor = cur.style.backgroundColor;
            cur.style.backgroundColor = 'yellow';
            document.getElementById("folder").innerHTML = safe_html(tooltips[cur.id][0]);
            document.getElementById("size").innerHTML = tooltips[cur.id][1];
            document.getElementById("objects").innerHTML = tooltips[cur.id][2];
            tooltip.style.display = 'block';
        } else {
            tooltip.style.display = 'none';
        }
        last = cur;
    }
}
</script>
</head>
<body>
""" + tree_html + """
<div class="tooltip" id="tooltip">
<nobr>Folder: <span id="folder"></span></nobr><br>
<nobr>Size: <span id="size"></span></nobr><br>
<nobr>Objects: <span id="objects"></span></nobr><br>
</div>
</body>
</html>
"""

if __name__ == "__main__":
    print("This module is not meant to be run directly")

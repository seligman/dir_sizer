#!/usr/bin/env python3

from colorsys import hsv_to_rgb
from math import cos
from utils import size_to_string, count_to_string
import html
import json

class TreeMapNode:
    # A single node on the tree view of nodes
    __slots__ = ("x", "y", "width", "height", "current_height", "vertical", "area", "value", "output", "key")
    def __init__(self, width=0, height=0, value=0, key=None):
        # Description of this node
        self.value = value
        self.key = key
        # Coords for this node
        self.x = 0
        self.y = 0
        self.width = width
        self.height = height
        self.current_height = 0
        self.vertical = False
        self.area = 0
        self.output = []

def plot(width, height, folder):
    # Turn a list objects in a folder to a corresponding list of tree map nodes
    # On return, it will have n+1 or less objects.  Small objects might be dropped
    # and an extra object with a key of None is added if there's extra space

    # Construct the node for this object, note that it's not offset, x,y are 0,0
    temp = TreeMapNode(width=width, height=height)
    # Build up the list of sub nodes, adding a padding one if needed
    values = [TreeMapNode(value=value.size, key=key) for key, value in folder.sub.items()]
    remaining = folder.size - sum(x.value for x in values)
    if remaining > 0:
        values.append(TreeMapNode(value=remaining))
    # And do the main work of laying out the nodes
    _squarify(temp, _prepare_nodes(temp, values), [], _get_width(temp), 0)
    # Return the sub-nodes.  This is for this level only
    return temp.output

def _prepare_nodes(temp, values):
    # Figure out the area for each node in turn, and sort by area
    # This is technically the same as sorting by value directly, but
    # this is done to allow us to also know which nodes are so small
    # as to be useless, so they're dropped here
    temp_sum = sum(x.value for x in values if x.value > 0)
    ret = [x for x in values if (x.value / temp_sum) >= 0.01]
    ret.sort(key=lambda x: x.value, reverse=True)
    temp_sum = sum(x.value for x in ret)
    total_area = temp.width * temp.height
    for cur in ret:
        cur.area = (cur.value / temp_sum) * total_area
    return ret

def _squarify(temp, values, current_row, width, bail):
    # Attempt to layout the squares, they'll be stretched to fit

    if bail > 100:
        # An edge case, if we're 100 sub-rows in this process
        # just give up, whatever we end up with is nonsense at this
        # point
        return
    
    # Try to build up the current row
    next_iter_preview = current_row[:]
    if len(values) > 1:
        next_iter_preview.append(values[0])
    
    current_ratio = _calc_aspect_ratio(current_row, width)
    next_ratio = _calc_aspect_ratio(next_iter_preview, width)

    if current_ratio == 0 or (next_ratio < current_ratio and next_ratio >= 1):
        # This gets us further away from a square row, so move on to the next row
        if len(values) > 0:
            current_row.append(values.pop(0))
        temp.current_height = _calc_height(current_row, width)
        if len(values) > 0:
            _squarify(temp, values, current_row, width, bail + 1)
        else:
            _layout_row(temp, current_row)
    else:
        # This gets us closer to a square row, so use it
        _layout_row(temp, current_row)
        _squarify(temp, values, [], _get_width(temp), bail + 1)

def _layout_row(temp, row_nodes):
    # Layout elements on a row, fitting as much as possible
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
    # Calculate the aspect ratio for a given row in two orientations
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
    # Return a color for a grid cell, only the depth of the cell is taken into context
    depth += 1
    hue = depth * 40

    # This is a simple HSV to RGB, with constants to skew the colors to a pastel palette
    red = 0.47450980392156861 + 0.20392156862745098 * cos(0.017453292519943295 * hue)
    green = 0.52352941176470591 - 0.0803921568627451 * cos(0.017453292519943295 * hue)
    blue = 0.47254901960784312 + 0.19411764705882353 * cos(0.017453292519943295 * hue + 1.8849555921538759)

    # Every other depth is closer to white to make them "pop"
    if depth % 2 == 1:
        saturation = 0.75
        red = red * saturation + 1.0 - saturation;
        green = green * saturation + 1.0 - saturation;
        blue = blue * saturation + 1.0 - saturation;

    # Return the color as an HTML color
    return f"#{int(red*255):02x}{int(green*255):02x}{int(blue*255):02x}"

def draw_layout(opts, abstraction, width, height, x, y, folder, tooltips, path, depth=0):
    # Draw a layout, returning the new layout as HTML
    if width < 20 or height < 20:
        # This cell is too small to care about
        return ""

    padding = 5

    x += padding
    y += padding
    width -= padding * 2
    height -= padding * 2

    # Track the tool tip information
    tool_id = f"t{len(tooltips)}"
    tooltips[tool_id] = [
        abstraction.join(path) if depth > 0 else "<base>",
        abstraction.dump_size(opts, folder.size),
        abstraction.dump_count(opts, folder.count),
        # And store the raw numbers as a string for the CSV download
        str(folder.size),
        str(folder.count),
    ]
    
    # And draw each cell
    output_html = ""
    if depth > 0:
        output_html += f'{"  " * depth}<div id="{tool_id}" style="'
        output_html += f'width:{round(width)}px;'
        output_html += f'height:{round(height)}px;'
        output_html += f'left:{round(x)}px;'
        output_html += f'top:{round(y)}px;'
        output_html += f'background-color:{get_color(depth)}'
        output_html += f'">\n'
    else:
        # The root cell needs to exist, but it's just a placeholder, it isn't visible
        output_html += f'{"  " * depth}<div id="{tool_id}" style="'
        output_html += f'width:{round(width)}px;'
        output_html += f'height:{round(height)}px;'
        output_html += f'border-style:none'
        output_html += f'">\n'

    x = 0
    y = 0

    width -= 1
    height -= 1

    temp = plot(width, height, folder)

    for cur in temp:
        # For all the sub cells, show them if they're big enough
        if cur.width >= 10 and cur.height >= 10 and cur.key is not None:
            output_html += draw_layout(
                opts,
                abstraction, 
                cur.width, cur.height, cur.x + x, cur.y + y, 
                folder[cur.key], tooltips, path + [cur.key], depth + 1
            )

    if depth == 1 and path[-1] is not None:
        # The first level off the root gets a label
        output_html += f'{"  " * (depth + 1)}<div class="label">{html.escape(path[-1])}</div>\n'

    output_html += f'{"  " * depth}</div>\n'

    return output_html

def get_summary(opts, abstraction, folder):
    # Turn the dict summary from the abstraction layer into a simple HTML header
    info = abstraction.get_summary(opts, folder)
    output_html = ""
    location = None
    for key, value in info:
        output_html += f"<b>{html.escape(key)}</b>: {html.escape(value)}<br>\n"
        if location is None:
            location = value
    return output_html, location

def get_webpage(opts, abstraction, folder, width, height):
    # Layout everything and output to HTML
    tooltips = {}
    # Create the main HTML, along the tooltips
    tree_html = draw_layout(opts, abstraction, width, height, 0, 0, folder, tooltips, [])
    # Create the header HTML
    summary_html, location = get_summary(opts, abstraction, folder)
    # Pull out the page title
    if location is not None:
        title = "Dir Sizer - " + html.escape(location)
    else:
        title = "Dir Sizer"
    # The HTML is just packages as is
    # Use a slightly bespoked json.dump layout just to keep things compact, but still somewhat human legible
    tooltips = ",\n".join(json.dumps(x) + ":" + json.dumps(y, separators=(',', ':')) for x,y in tooltips.items())

    # And the rest of the webpage is hardcoded
    return """<!DOCTYPE html>
<html>
<head>
<link rel="apple-touch-icon" sizes="180x180" href="https://raw.githubusercontent.com/seligman/dir_sizer/master/images/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="https://raw.githubusercontent.com/seligman/dir_sizer/master/images/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="https://raw.githubusercontent.com/seligman/dir_sizer/master/images/favicon-16x16.png">
<title>""" + title + """</title>
<style>
div {
    border-radius:5px;
    border-width:1px;
    border-style:solid;
    position:absolute;
}
.tooltip {
    display: none;
    background: #c8c8c8;
    margin: 25px;
    padding: 10px;
    position: absolute;
    z-index: 1000;
}
.label {
    background-color: #eed;
    border-radius: 0;
    border-width: 1px;
    border-style: solid;
    border-color: #222;
    font-size: 10pt;
    padding-left: 0.2em;
    padding-right: 0.2em;
    opacity: 80%;
    bottom: 2px;
    right: 2px;
}
a {
    color: #4040f2;
    text-decoration: none;
}
a:hover {
    color: #4040f2;
    text-decoration: underline;
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
function generate_csv() {
    rows = [["Folder", "Size", "Count"]];
    for (var key in tooltips) {
        rows.push([tooltips[key][0], tooltips[key][3], tooltips[key][4]]);
    }
    export_to_csv("data.csv", rows);
}
function export_to_csv(filename, rows) {
    var processRow = function (row) {
        var finalVal = '';
        for (var j = 0; j < row.length; j++) {
            var innerValue = row[j] === null ? '' : row[j].toString();
            if (row[j] instanceof Date) {
                innerValue = row[j].toLocaleString();
            };
            var result = innerValue.replace(/"/g, '""');
            if (result.search(/("|,|\\n)/g) >= 0)
                result = '"' + result + '"';
            if (j > 0)
                finalVal += ',';
            finalVal += result;
        }
        return finalVal + '\\n';
    };

    var csvFile = '';
    for (var i = 0; i < rows.length; i++) {
        csvFile += processRow(rows[i]);
    }

    var blob = new Blob([csvFile], { type: 'text/csv;charset=utf-8;' });
    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, filename);
    } else {
        var link = document.createElement("a");
        if (link.download !== undefined) { // feature detection
            // Browsers that support HTML5 download attribute
            var url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
}
</script>
</head>
<body>
""" + summary_html + """
Download all <a href="#" onclick="generate_csv();">data</a>.
<hr>
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

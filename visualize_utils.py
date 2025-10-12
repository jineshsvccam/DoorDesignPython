import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def visualize_placements(placements, sheet_width, sheet_height):
    from collections import defaultdict
    import matplotlib.widgets as mwidgets
    bins = defaultdict(list)
    for p in placements:
        bins[p['bin_id']].append(p)
    bin_ids = sorted(bins.keys())
    num_bins = len(bin_ids)

    fig, ax = plt.subplots(figsize=(8, 12))
    plt.subplots_adjust(bottom=0.2)
    current_bin = [0]

    def draw_bin(idx):
        ax.clear()
        bin_id = bin_ids[idx]
        bin_rects = bins[bin_id]
        ax.set_xlim(0, sheet_width)
        ax.set_ylim(0, sheet_height)
        ax.set_aspect('equal')
        for p in bin_rects:
            rect = Rectangle((p['x'], p['y']), p['width'], p['height'], fill=True, edgecolor='black', alpha=0.5)
            ax.add_patch(rect)
            label = f"{p['file_name']}\n{int(p['width'])} x {int(p['height'])}\n({int(p['x'])}, {int(p['y'])})"
            rect = Rectangle((p['x'], p['y']), p['width'], p['height'], fill=True, edgecolor='black', linewidth=1, alpha=0.5)
            ax.add_patch(rect)
            ax.text(p['x'] + p['width']/2, p['y'] + p['height']/2, label, ha='center', va='center', fontsize=8)
        ax.set_xlabel('Width')
        ax.set_ylabel('Height')
        ax.set_title(f'Bin {bin_id+1} / Total Sheets: {num_bins}')
        fig.canvas.draw_idle()

    def next_bin(event):
        if current_bin[0] < num_bins - 1:
            current_bin[0] += 1
            draw_bin(current_bin[0])

    def prev_bin(event):
        if current_bin[0] > 0:
            current_bin[0] -= 1
            draw_bin(current_bin[0])

    axprev = plt.axes((0.3, 0.05, 0.1, 0.075))
    axnext = plt.axes((0.6, 0.05, 0.1, 0.075))
    bnext = mwidgets.Button(axnext, 'Next')
    bprev = mwidgets.Button(axprev, 'Prev')
    bnext.on_clicked(next_bin)
    bprev.on_clicked(prev_bin)

    draw_bin(current_bin[0])
    plt.show()

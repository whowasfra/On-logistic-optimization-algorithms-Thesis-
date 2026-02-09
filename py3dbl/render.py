import matplotlib.pyplot as plt
import plotly.graph_objects as go
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from .Bin import Bin
from .Item import Item
from .Space import Volume

COLORS = ["cyan","red","yellow","blue","green","brown","magenta"]
BORDER_WIDTH = 1
BORDER_COLOR = "black"
TRANSPARENCY = .5

def render_volume_interactive(volume : Volume, fig : go.Figure, color : str, name : str = "", show_border : bool = True, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):   
    """
    An interactive 3D rendering
    
    :param volume: Description
    :type volume: Volume
    :param fig: Description
    :type fig: go.Figure
    :param color: Description
    :type color: str
    :param name: A Name
    :type name: str
    :param border_width: Description
    :type border_width: float
    :param border_color: Description
    :type border_color: str
    :param transparency: Description
    :type transparency: float

    Author: Martina Iacoponi (dear colleague)
    """
    x, y, z = [float(value) for value in volume.position]   # position from bottom-back-left corner
    w, h, d = [float(value) for value in volume.size] # actual dimensions of the item (considered rotation)
    fig.add_trace(go.Mesh3d(
            x=[x, x+w, x+w, x, x, x+w, x+w, x],
            z=[y, y, y+h, y+h, y, y, y+h, y+h],
            y=[z, z, z, z, z+d, z+d, z+d, z+d],
            contour_show = show_border,
            contour_width= border_width,
            contour_color= border_color,
            color=color,
            opacity= (1.0 - transparency),
            name=name,
            alphahull=0,
            showscale=False
        ))
    
def render_item_interactive(item : Item, fig : go.Figure, color : str, show_border : bool = True, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
    render_volume_interactive(item.volume,fig,color,item.name,show_border,border_width,border_color,transparency)

def render_volume(volume : Volume, axes, color : str, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
    base = [float(value) for value in volume.position]   # position from bottom-back-left corner
    dim  = [float(value) for value in volume.size] # actual dimensions of the item (considered rotation)
    verts = [
        [base[0],        base[1],        base[2]],         # bottom-back-left
        [base[0]+dim[0], base[1],        base[2]],         # bottom-back-right
        [base[0],        base[1],        base[2]+dim[2]],  # bottom-front-left
        [base[0]+dim[0], base[1],        base[2]+dim[2]],  # bottom-front-right
        [base[0],        base[1]+dim[1], base[2]],         # top-back-left
        [base[0]+dim[0], base[1]+dim[1], base[2]],         # top-back-right
        [base[0],        base[1]+dim[1], base[2]+dim[2]],  # top-front-left
        [base[0]+dim[0], base[1]+dim[1], base[2]+dim[2]]   # top-front-right
    ]
    # for make a comprensible rendering we have to swap z with y
    for l in range(len(verts)):
        verts[l] = [verts[l][0],verts[l][2],verts[l][1]]
    
    faces = [
        [0,1,3,2],  # bottom
        [0,1,5,4],  # back
        [0,2,6,4],  # left
        [1,3,7,5],  # right
        [2,3,7,6],  # front
        [4,5,7,6]   # top
    ]
    toRender =  [ [ verts[i] for i in p] for p in faces]

    axes.add_collection3d(
        Poly3DCollection(
            toRender, 
            facecolors = color,
            linewidths = border_width,
            edgecolors = border_color,
            alpha      = transparency,
        )
    )

def render_item(item : Item, axes, color : str, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
    render_volume(item.volume,axes,color,border_width,border_color,transparency)

def render_bin_interactive(bin : Bin, colors : list[str] = COLORS, render_bin : bool = True, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
    if not bin.items:
            return

    fig = go.Figure()

    for idx,item in enumerate(bin.items):
        render_item_interactive(item=item,fig=fig,color=colors[idx%len(colors)],border_width=border_width,border_color=border_color,transparency=transparency)

    if render_bin:
        render_volume_interactive(Volume(size=bin.dimension),fig=fig,color="lightgrey",transparency=.9,name="Bin",show_border=False)

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Width'),
            zaxis=dict(title='Height'),
            yaxis=dict(title='Depth'),
            aspectmode='data'
        ),
        title=f"3D Packing Visualization - {bin} ({len(bin.items)} items)"
    )

    fig.show()

def render_bin(bin : Bin, colors : list[str] = COLORS, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
        if not bin.items:
            return
        
        fig = plt.figure()

        fig.set_label(bin.id)
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xbound(lower=0,upper=float(bin.width))
        ax.set_ybound(lower=0,upper=float(bin.depth))
        ax.set_zbound(lower=0,upper=float(bin.height))

        for idx,item in enumerate(bin.items):
            render_item(item=item,axes=ax,color=colors[idx%len(colors)],border_width=border_width,border_color=border_color,transparency=transparency)

        #render_volume(volume=Volume(bin.dimension),axes=ax,color="lightgrey",transparency=.9)

        ax.set_xlabel('WIDTH')
        ax.set_ylabel('DEPTH')
        ax.set_zlabel('HEIGHT')

        plt.show()
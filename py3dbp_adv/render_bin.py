import matplotlib.pyplot as plt
from py3dbp import Bin
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

COLORS = ["cyan","red","yellow","blue","green"]
BORDER_WIDTH = .5
BORDER_COLOR = "black"
TRANSPARENCY = .5

def render_bin(bin : Bin, colors : list[str] = COLORS, border_width : float = BORDER_WIDTH, border_color : str = BORDER_COLOR, transparency : float = TRANSPARENCY):
    if not bin or not bin.items:
        return

    fig = plt.figure()
    fig.set_label(bin.name)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_xbound(lower=0,upper=float(bin.width))
    ax.set_ybound(lower=0,upper=float(bin.depth))
    ax.set_zbound(lower=0,upper=float(bin.height))
    #ax.set(xbound=(None,bin.width), ybound=(None,bin.height), zbound=(None,bin.depth))
    for idx,item in enumerate(bin.items):
        base = [float(value) for value in item.position]        # position from bottom-back-left corner
        dim  = [float(value) for value in item.get_dimension()] # actual dimensions of the item (considered rotation)
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

        ax.add_collection3d(
            Poly3DCollection(
                toRender, 
                facecolors = colors[idx%len(colors)],
                linewidths = border_width,
                edgecolors = border_color,
                alpha      = transparency
            )
        )


    ax.set_xlabel('WIDTH')
    ax.set_ylabel('DEPTH')
    ax.set_zlabel('HEIGHT')

    plt.show()
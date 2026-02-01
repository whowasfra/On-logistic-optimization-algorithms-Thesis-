from random import random,randint
from .main import Item

def item_generator(w_range : tuple[float,float] , h_range : tuple[float,float], d_range : tuple[float,float], weight_range : tuple[float,float], priority_range : tuple[int,int] = (0,0), batch_size : int = 1):
    if batch_size == 1:
        return Item(
            name=None,
            width=(w_range[0]+random()*(w_range[1]-w_range[0])),
            height=(h_range[0]+random()*(h_range[1]-h_range[0])),
            depth=(d_range[0]+random()*(d_range[1]-d_range[0])),
            weight=(weight_range[0]+random()*(weight_range[1]-weight_range[0])),
            priority=(randint(priority_range[0],priority_range[1]))
        )
    else:
        items = []
        for i in range(0,batch_size):
            item = Item(
                name=str(i),
                width=(w_range[0]+random()*(w_range[1]-w_range[0])),
                height=(h_range[0]+random()*(h_range[1]-h_range[0])),
                depth=(d_range[0]+random()*(d_range[1]-d_range[0])),
                weight=(weight_range[0]+random()*(weight_range[1]-weight_range[0])),
                priority=(randint(priority_range[0],priority_range[1]))
            )
            items.append(item)
        return items
from .Bin import Bin
from .Item import Item
from .Space import Volume, Vector3, intersect, rect_intersect

class Constraint:
    """
    A Constraint to apply to a bin packing problem
    """
    def __init__(self,func ,weight : int = 0):
        """
        :param func: Function that evaluates the constraint
        :param weight: Weight used for evaluation order (generally more expensive constraint should have higher weight)
        :type weight: int
        :param type: A Type used to distinguish between constraints: STATIC a constraint that depends on statical properties of the bin and the item, SPACE_DEPENDENT a constraint that depends on the position of the item
        :type type: ConstraintType
        """
        self.func = func
        self.weight = weight
        self.kwargs = dict()
    
    def set_parameter(self,name : str, value):
        """
        Set parameter different from the bin and the item
        
        :param name: Name of the parameter
        :type name: str
        :param value: Value to set
        """
        self.kwargs[name] = value

    # used for ordering
    def __lt__(self,cmp):
        return self.weight < cmp.weight
    def __call__(self, bin : Bin, item : Item):
        return self.func(bin,item,**self.kwargs)
    def __str__(self):
        return f"Constraint {self.func.__name__} weight({self.weight})"

# dictionary of currently available constraints
constraints = dict()

def constraint(weight : int):
    """
    Decorator for simple Constraint generation
    
    :param weight: Weight of the constraint
    :type weight: int
    """
    def wrapper(func):
        constraints[func.__name__] = Constraint(func,weight)
        return func
    return wrapper

# Ready-Made Constraint

@constraint(weight=5)
def weight_within_limit(bin : Bin, item : Item):
    return bin.weight+item.weight <= bin.max_weight

@constraint(weight=10)
def fits_inside_bin(bin : Bin, item : Item):
    return all([bin.dimension[axis] >= (item.position[axis] + item.dimensions[axis]) for axis in range(3)])
    
@constraint(weight=15)
def no_overlap(bin : Bin, item : Item):
    return len(bin.items) == 0 or not any([intersect(ib.volume,item.volume) for ib in bin.items])

@constraint(weight=20)
def is_supported(bin: Bin, item : Item, allow_item_fall : bool = False, minimum_support : float = 0.5):
    if item.position.y == 0:
        return True
    else:
        highest_y = 0
        target_items = []
        for ib in bin.items:
            # check for base intersection (plane x-z)
            if rect_intersect(ib.volume,item.volume,Vector3.AXIS['x'],Vector3.AXIS['z']) > minimum_support:
                target_items.append(ib)
                highest_y = max(highest_y,ib.position.y+ib.height)

        if len(target_items)==0 or (not allow_item_fall and highest_y!=item.position.y):
            return False
        else:
            item.position.y = highest_y
            return True
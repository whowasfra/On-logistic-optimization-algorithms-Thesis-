from .Bin import Bin
from .Item import Item
from .Space import Volume, Vector3, intersect, rect_intersect
from decimal import Decimal

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
def is_supported(bin: Bin, item : Item, minimum_support : float = 0.75):
    """
    Check that the item is physically supported by direct contact.
    Only counts support from items whose top surface is exactly at the item's bottom Y.
    This is a pure validator: it does NOT modify the item's position.
    
    :param minimum_support: Minimum ratio of the item's base area that must be supported (0.0-1.0)
    :type minimum_support: float
    """
    # Items on the floor are always supported
    if item.position.y == 0:
        return True
    
    # Base area of the item (X-Z plane)
    item_base_area = item.dimensions[Vector3.AXIS['x']] * item.dimensions[Vector3.AXIS['z']]
    if item_base_area <= 0:
        return False
    
    # Only count support from items in direct contact:
    # their top surface must be exactly at the item's bottom Y
    contact_area = Decimal(0)
    for ib in bin.items:
        ib_top_y = ib.position.y + ib.height
        if ib_top_y == item.position.y:
            overlap = rect_intersect(ib.volume, item.volume, Vector3.AXIS['x'], Vector3.AXIS['z'])
            if overlap > 0:
                contact_area += overlap
    
    support_ratio = contact_area / item_base_area
    return support_ratio >= Decimal(str(minimum_support))

@constraint(weight=25) 
def maintain_center_of_gravity(bin : Bin, item : Item, 
                              tol_x_percent : float = 0.3,
                              tol_z_percent : float = 0.3,
                              min_load_threshold : float = 0.3):
    """
    Check that the center of gravity of the bin after placing the item is within a certain tolerance from the center of the bin.
    :param tol_x_percent: Tolerance on the X axis as a percentage of the bin width (0.0-1.0)
    :type tol_x_percent: float
    :param tol_z_percent: Tolerance on the Z axis as a percentage of the bin depth (0.0-1.0)
    :type tol_z_percent: float
    :param min_load_threshold: Minimum load ratio (current weight + item weight) / max weight to apply the constraint, to avoid penalizing the placement of the first items
    :type min_load_threshold: float
    """
    
    # Calculate the future weight
    future_weight = bin.weight + item.weight
    if bin.max_weight > 0:
        load_ratio = future_weight / bin.max_weight
        if load_ratio < min_load_threshold:
            return True  # Skip the constraint for low load ratios
        
    # Calculate the current center of gravity
    current_cog = bin.calculate_center_of_gravity()

    # Calculate the center of gravity of the item to be added
    current_moment_x = current_cog.x * item.weight
    current_moment_z = current_cog.z * item.weight

    # Calculate the moments of the new item
    item_center_x = item.position.x + (item.width / Decimal(2))
    item_center_z = item.position.z + (item.depth / Decimal(2))

    item_moment_x = item_center_x * item.weight
    item_moment_z = item_center_z * item.weight

    # Calculate the future center of gravity
    future_cog_x = (current_moment_x + item_moment_x) / future_weight
    future_cog_z = (current_moment_z + item_moment_z) / future_weight

    # Calculate the center of the bin
    bin_center_x = bin.width / Decimal(2)
    #bin_center_z = bin.depth * Decimal(0.4) # consider the center of gravity more tolerant towards the back of the bin, where the load is generally more stable
    bin_center_z = bin.depth / Decimal(2)

    # Calculate the tolerances in absolute terms
    tol_x = bin.width * Decimal(tol_x_percent)
    tol_z = bin.depth * Decimal(tol_z_percent)

    # Check if the future center of gravity is within the tolerances
    if abs(future_cog_x - bin_center_x) > tol_x :
        return False

    if abs(future_cog_z - bin_center_z) > tol_z :
        return False

    return True  
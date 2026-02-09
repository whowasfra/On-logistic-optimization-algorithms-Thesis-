from decimal import Decimal
from .Item import Item
from .Bin import Bin, BinModel
from .Space import Vector3, Volume, rect_intersect
from .Decimal import decimals
from .Constraints import constraints, Constraint

# basical constraints 
BASE_CONSTRAINTS = [
    constraints['weight_within_limit'],
    constraints['fits_inside_bin'],
    constraints['no_overlap']
]

PACKING_STRATEGIES = []


def base_packer(available_bins : list[BinModel], items_to_pack : list[Item], default_bin : None|BinModel = None, constraints : list[Constraint] = BASE_CONSTRAINTS):
    
    def try_fit(bin : Bin, item : Item):
        old_pos = Vector3(*item.position)
        old_size = Vector3(*item.dimensions)
        
        for ib in bin.items:
            pivot = Vector3(*ib.position)
            for axis in range(3):
                # Set the item's position next to the current item along the specified axis
                new_pos = Vector3(*pivot)
                new_pos[axis] += ib.dimensions[axis]
                
                for oriz_deg_free in range(2):
                    for vert_deg_free in range(2):
                        # Set temporary X-Z position to compute surface heights
                        item.position = Vector3(new_pos.x, Decimal(0), new_pos.z)
                        
                        if axis == 1:
                            # Placing on top of pivot item: Y is fixed
                            y_candidates = [new_pos.y]
                        else:
                            # Placing along X or Z: find all valid resting surfaces
                            # by scanning items that overlap in X-Z at current rotation
                            y_set = set()
                            y_set.add(Decimal(0))  # floor is always an option
                            for existing in bin.items:
                                existing_top = existing.position.y + existing.height
                                overlap = rect_intersect(existing.volume, item.volume, 
                                                        Vector3.AXIS['x'], Vector3.AXIS['z'])
                                if overlap > 0:
                                    y_set.add(existing_top)
                            # Try highest surfaces first (prefer stacking)
                            y_candidates = sorted(y_set, reverse=True)
                        
                        for y_pos in y_candidates:
                            item.position = Vector3(new_pos.x, y_pos, new_pos.z)
                            if bin.put_item(item, constraints):
                                return True
                        
                        item.rotate90(vertical=True)
                    item.rotate90(orizontal=True)
        
        # Restore original position and dimensions if the item could not be placed
        item.position = old_pos
        item._volume.size = old_size
        return False

    current_configuration = []
    unfitted_items = []
    constraints.sort()

    while len(items_to_pack) != 0:
        if available_bins != None and len(available_bins) != 0:
            bin = Bin(len(current_configuration),available_bins.pop(0))
        elif default_bin != None:
            bin = Bin(len(current_configuration),default_bin)
        else:
            break

        for item in items_to_pack:
            if not bin.items:
                if not bin.put_item(item,constraints):
                    unfitted_items.append(item)
            else:
                if not try_fit(bin,item):
                    unfitted_items.append(item)

        # if no item has been packed probably there's no solution
        if len(bin.items) == 0:
            break

        items_to_pack = unfitted_items
        unfitted_items = []
        current_configuration.append(bin)
    
    return current_configuration

class Packer():
    """
    Store configurations and execute 3D bin packing algorithm(s)
    """
    def __init__(self, default_bin : None|BinModel = None, fleet : list[BinModel] = [], items : list[Item] = [], current_configuration : list[Bin] = []):
        """
        :param default_bin: a bin model that describes the preferred bin to pack in case the fleet is insufficent
        :type default_bin: None | BinModel
        :param bins: list of bin models that describes the fleet to pack
        :type bins: list[BinModel]
        :param items: list of items to fit in the fleet
        :type items: list[Item]
        :param current_configuration: a configuration to start on
        :type current_configuration: None | list[Bin]
        """
        self.bins   =  fleet
        self.items  =  items
        self.default_bin           = default_bin
        self.current_configuration = current_configuration
    
    def set_default_bin(self, bin : BinModel):
        self.default_bin = bin
    
    def add_bin(self, bin : BinModel):
        self.bins.append(bin)

    def add_fleet(self, fleet : list[BinModel]):
        self.bins.extend(fleet)

    def add_batch(self, batch : list[Item]):
        self.items.extend(batch)

    def clear_current_configuration(self):
        self.current_configuration.clear()

    def _pack_to_bin(self, bin : Bin, item : Item, constraints):
        if not bin.items:
            return bin.put_item(item, constraints)
        else:
            for axis in range(0, 3):
                for ib in bin.items:
                    pivot = Vector3(*ib.position)
                    pivot[axis] += ib.dimensions[axis]
                    item.position = pivot
                    if bin.put_item(item, constraints):
                        return True
            return False

    def pack_test_on_models(self, models : list[BinModel], constraints : list[Constraint] = BASE_CONSTRAINTS):
        configuration = []
        for model in models:
            bin = Bin(0,model)
            for item in self.items:
                self._pack_to_bin(bin,item,constraints)
            configuration.append(bin)
        return configuration
    
    
    def pack(self, constraints : list[Constraint] = BASE_CONSTRAINTS, bigger_first=True, follow_priority=True, number_of_decimals=decimals):
        """
        Execute the 3D bin packing on the given batch and fleet
        
        :param self: Current Packer object
        :param bigger_first: Description
        :param number_of_decimals: Description
        """
        available_bins = self.bins
        items_to_pack = self.items

        for bin in available_bins:
            bin.format_numbers(number_of_decimals)

        for item in items_to_pack:
            item.format_numbers(number_of_decimals)

        if self.default_bin is not None:
            self.default_bin.format_numbers(number_of_decimals)
        
        available_bins.sort(
            key=lambda bin: bin.volume, reverse=bigger_first
        )
        items_to_pack.sort(
            key=lambda item: item.volume.volume(), reverse=bigger_first
        )
        self.current_configuration = base_packer(available_bins=available_bins,items_to_pack=items_to_pack,default_bin=self.default_bin,constraints=constraints)
        """
        unfitted_items = []
        static_constraints, space_constraints = process_constraints(constraints)

        while len(items_to_pack) != 0:
            if available_bins != None and len(available_bins) != 0:
                bin = available_bins.pop(0)
            elif self.default_bin != None:
                bin = Bin(len(self.current_configuration),self.default_bin)
            else:
                return

            for item in items_to_pack:
               if not self._pack_to_bin(bin,item,static_constraints=static_constraints.copy(),space_constraints=space_constraints.copy()):
                   unfitted_items.append(item)

            if len(bin.items) == 0:
                break

            items_to_pack = unfitted_items
            unfitted_items = []
            self.current_configuration.append(bin)
        return len(items_to_pack)"""

    def calculate_statistics(self):
        statistics = {
            "loaded_volume": Decimal(0),
            "loaded_weight": Decimal(0),
        }
        configuration_volume = Decimal(0)
        for bin in self.current_configuration:
            for item in bin.items:
                statistics["loaded_volume"] += item.volume.volume()
            statistics["loaded_weight"] += bin.weight
            configuration_volume += bin._model.volume
        
        # Evita divisione per zero
        if configuration_volume > 0:
            statistics["average_volume"] = statistics["loaded_volume"]/configuration_volume
        else:
            statistics["average_volume"] = Decimal(0)
        
        return statistics
import py3dbp
import time
from .render_bin import render_bin
import functools

MINIMUM_SUPPORT_SURFACE = .2

class Item(py3dbp.Item):
    def __init__(self,name,width,height,depth,weight,priority=0):
        py3dbp.Item.__init__(self,name,width,height,depth,weight)
        self.priority = priority

    def string(self):
        return py3dbp.Item.string(self)


class Bin(py3dbp.Bin):
    def __init__(self,name,width,height,depth,max_weight):
        py3dbp.Bin.__init__(self,name,width,height,depth,max_weight)
    
    def render(self):
        render_bin(self)
"""
    def copy(self):
        ret = Bin(self.name,self.width,self.height,self.depth,self.max_weight)
        ret.items = self.items
        ret.unfitted_items = self.unfitted_items
        ret.number_of_decimals = self.number_of_decimals

        return ret  
"""
class Packer(py3dbp.Packer):
    def __init__(self):
        py3dbp.Packer.__init__(self)
        self.default_bin = None
        self.current_configuration = None
    
    def set_default_bin(self, bin : Bin):
        self.default_bin = Bin(
            bin.name,
            bin.width,
            bin.height,
            bin.depth,
            bin.max_weight
        )
    
    def add_fleet(self, fleet : list[Bin]):
        self.bins.extend(fleet)

    def add_batch(self, batch : list[Item]):
        self.items.extend(batch)

    def calculate_statistics(self):
        statistics = {
            "loaded_volume": 0,
            "loaded_weight": 0,
        }
        configuration_volume = 0
        for bin in self.current_configuration:
            for item in bin.items:
                statistics["loaded_volume"] += item.get_volume()
                statistics["loaded_weight"] += item.weight
            configuration_volume += bin.get_volume()
        statistics["average_volume"] = statistics["loaded_volume"]/configuration_volume
        return statistics        

    def pack(
        self, bigger_first=False,
        number_of_decimals=3
    ):
        for bin in self.bins:
            bin.format_numbers(number_of_decimals)

        for item in self.items:
            item.format_numbers(number_of_decimals)

        self.bins.sort(
            key=lambda bin: bin.get_volume(), reverse=bigger_first
        )
        self.items.sort(
            key=lambda item: item.get_volume(), reverse=bigger_first
        )

        available_bins = self.bins
        self.current_configuration = []

        while len(self.items) != 0:
            if available_bins != None and len(available_bins) != 0:
                bin = available_bins.pop(0)
            elif self.default_bin != None:
                bin = Bin(self.default_bin.name,self.default_bin.width,self.default_bin.height,self.default_bin.depth,self.default_bin.max_weight)
            else:                   
                return
            
            for item in self.items:
                self.pack_to_bin(bin,item)

            self.items = bin.unfitted_items
            self.current_configuration.append(bin)
            
        """else:
            for bin in self.bins:
                for item in self.items:
                    self.pack_to_bin(bin, item)
        """
        
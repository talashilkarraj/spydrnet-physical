"""
===================================
Merging two instances in the design
===================================

This example demonstrate how to merge two instance in the design to create a new
merged definition

.. hdl-diagram:: ../../../examples/basic/_initial_design_merge.v
   :type: netlistsvg
   :align: center
   :module: top


**Output1** Merged design Instance 

.. hdl-diagram:: ../../../examples/basic/_merged_design.v
   :type: netlistsvg
   :align: center
   :module: top

**Initial Design**

.. hdl-diagram:: ../../../examples/basic/_initial_design.v
   :type: netlistsvg
   :align: center
   :module: top

**Output** ``inst_1_0`` and ``inst_1_1`` merged to form ``merged_inst_1``

.. hdl-diagram:: ../../../examples/basic/_merge_instance.v
   :type: netlistsvg
   :align: center
   :module: top

"""


from os import path
import spydrnet as sdn
import spydrnet_physical as sdnphy
import logging
logger = logging.getLogger('spydrnet_logs')
sdn.enable_file_logging(LOG_LEVEL='INFO')

netlist = sdnphy.load_netlist_by_name('nested_hierarchy')
sdn.compose(netlist, '_initial_design_merge.v', skip_constraints=True)

netlist = sdnphy.load_netlist_by_name('nested_hierarchy')
top = netlist.top_instance.reference
inst1 = next(top.get_instances("inst_1_0"))
inst2 = next(top.get_instances("inst_1_1"))

top.merge_instance([inst1, inst2],
                   new_definition_name="merged_module",
                   new_instance_name="merged_module_instance_0")

netlist = sdnphy.load_netlist_by_name('basic_hierarchy')
top = netlist.top_instance.reference

inst_1_0  = next(top.get_instances("inst_1_0"))
inst_1_1  = next(top.get_instances("inst_1_1"))

top.merge_instance([inst_1_0, inst_1_1], "merged_module_1", "merged_inst_1", lambda ex,pin,instance: f"{pin}_{instance}" )
sdn.compose(netlist,'_merge_instance.v',skip_constraints=True)


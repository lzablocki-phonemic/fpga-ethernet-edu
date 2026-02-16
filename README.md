# fpga-ethernet-edu
TASK PLAN:


I. Basic simulation structure:

In fact the best way to operate at simulation level is to :
1. design of the FIR IP wrapped with the UDP/IP/Ethernet interface from the external block (verilog-ethernet)
2. generate the test-vectors on the verilog-ethernet api using XGMII/RGMII

+-------------------------------+-------------------+
| FIR IP                        | APB interface     |
| + FIR functionality           |                   |
+-------------------------------+-------------------+
            A
            | AXI. 
            V
+-------------------------------+-------------------+
| + Axi_fifo interface          |                   |
| + UDP Complete                |                   |
| + Decission logic             | APB interface     |
+-------------------------------+                   +
| MAC 10G/1G                    |                   |
+-------------------------------+-------------------+
                        A
                        |
                        V
            +-------------------------------+
            |RGMII/xGMII Generator          |
            +-------------------------------+

II. Model to be implemented on the FPGA (zynq)
1. This apporach allows to generate full IP packets, focus on the clocking and deployment aspects.
2. allow to simulate real network cases

                                                                        +============+
                                                                        |    ARM     |
                                                                        +============+
                                                                        |    AXI     |
                                                                        +============+
    +---------------------+--------------+                                A         A 
    | FIR IP.             |APB interface |                                |         | 
    |    APB interface    |              |                                |         | 
    +---------------------+--------------+                                |         | 
        A                                                                 |         | 
        | AXI                                                             |         | 
        V                                                                 V         V 
    +------------------------------------------+              +-----------------------------------------+ 
    | PORT_CHECK & DECISION     |              |              |              |PORT_CHECK & DECISION     |
    +---------------------------| APB interface|              | APB interface|--------------------------+
    | UDP Complete + MAC 10/1G  |              |              |              | MAC          10/1G       |
    +---------+-----------------+--------------+              +--------------+--------------------------+
        A                                                                                   A
        |                                 xGMII/CROSS                                       |
        -------------------------------------------------------------------------------------



III. FUTURE PLAN:
1. Dedicated design with the full range of configuration. enablement of the basic switch 

Future enchancements: use IP switch with complex switching rules (e.g.  flower - flow based traffic control filter)
                               +============+                      +============+
                               |    ARM     |                      |    ARM     | 
                               +============+                      +============+
                               |    AXI     |                      |    AXI     | <-----------+ 
                               +============+                      +============+             V
    +-----------------------+       A      A                         A        A         +--------------------+
    | FIR core   |          |       |      |                         |        |         |                    |        
    +------------+----------+       |      |                         |        |         | PHY PROCESSING.    |        
    | UDP        | APB      |       |      |                         |        |         | COPROCESOR         |        
    | COMPLETE   |          |       |      |                         |        |         |                    |        
    +-----------------------+       |      |                         |        |         +--------------------+
            A                       |      |                         |        |             A      
            |AXI STREAM             |      |                         |        |          AXI STREAM                     
            | ETHERNET              |      |                         |        |             |                     
            V                       V      V                         V        V             V    
    +---------------------------------------------------+     +------------------------------------------+ 
    | eth_mac_1g_fifo                    |              |     |              |  (SWITCH)                 |
    | eth_axis_tx,eth_axis_rx            | APB interface|     | APB interface| eth_axis_tx,eth_axis_rx   |
    |       (NEW SWITCH)                 |              |     |              |+eth_mac_1g_fifo           |
    +------------------------------------+--------------+     +------------------------------------------+
        A                                                                             A
        |                                  B2B/XGMII/PHY                              |
        -------------------------------------------------------------------------------
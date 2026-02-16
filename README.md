# fpga-ethernet-edu

1. this is IP core which mix 1G (IP mode), FIR IP core and the APB interface configuration aspects:
    - following architecture is maintained:


                                                                        +============+
                                                                        |    ARM     |
                                                                        +============+
                                                                        |    AXI     |
                                                                        +============+
    +---------------------+                                               A         A    +---------------------+
    | FIR core            |                                               |         |    | (Test Bench) Noise  |
    |    APB interface    |                                               |         |    | Generator.          |        
    +---------------------+                                               Ethernet  |    +---------------------+
        A                                                                 |         |                 A      
        | UDP Payload.                                                    |         | UDP Payload.    |                    
        V                                                                 V         V                 V    
    +------------------------------------------+              +-----------------------------------------+ 
    | PORT_CHECK & DECISION     |              |              |              |PORT_CHECK & DECISION     |
    +---------------------------| APB interface|              | APB interface|--------------------------+
    | UDP 1G                    |              |              |              | UDP 1G                   |
    +---------+-----------------+--------------+              +--------------+--------------------------+
        A                                                                                   A
        |                                                                                   |
        -------------------------------------------------------------------------------------



Future enchancements: use IP switch with complex routing capabilities (xdp-like):
                             +============+                      +============+
                             |    ARM     |                      |    ARM     |
                             +============+                      +============+
                             |    AXI     |                      |    AXI     |
                             +============+                      +============+
    +---------------------+       A      A                         A        A         +---------------------+
    | FIR core            |       |      |                         |        |         | Noise Generator.    |        
    +---------------------+       |      |                         |        |         +---------------------+
            A                     |      |                         |        |             A      
            | IP packet.          |      |                         |        |             |                    
            V                     V      V                         V        V             V    
    +---------------------------------------------------+     +------------------------------------------+ 
    | IP/UDP (L3/L4 Layer analysis)      |              |     |              | IP/UDP (L3/L4 Layer)      |
    | + decision making                  | APB interface|     | APB interface| + decision making         |
    | + IP/UDP packet processing         |              |     |              |+ IP/UDP packet processing |
    +------------------------------------+--------------+     +------------------------------------------+
        A                                                                             A
        |  (IP frame connections)                            (IP frame connections)   |
        V                                                                             V
    +--------+--------------------------+                +-------------------------+--------+   
    | IP 1G  | LOCAL IP/MAC APB Config  |                | LOCAL IP/MAC APB Config | IP 1G  |  
    +--------+--------------------------+                +-------------------------+--------+
        A                                                                             A
        |                                                                             |
        -------------------------------------------------------------------------------
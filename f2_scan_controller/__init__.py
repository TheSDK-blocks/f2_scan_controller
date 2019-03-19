# f2_scan_controller class 
# Marko Kosunen, marko.kosunen@aalto.fi, 05.01.2018 11:07
        # Serdes test scan write modes:
        # 0= Zero, do nothing
        # 1= Scan, Write fom scan
        # 2= Fill from write_val selcted by Test addressing
        # 3= Loop, Keep on filling until changed to zero

        #Test addressing 
        #dsp_to_serdes_address   = Vec(numserdes+2,Input(UInt(log2Ceil(neighbours+2).W)))
        #serdes_to_dsp_address   = Vec(neighbours+2,Input(UInt(log2Ceil(numserdes+2).W)))
        # from_dsp 0, from rx_dsp
        # from_dsp 1-neighbours from tx_dsp outputs to neighbours
        # from_dsp neighbours+1 from serdestest memory

        # from_serdes( 0 to numseres-1) from serdes rx
        # from_serdes(numserdes) from rx_dsp
        # from_serdes(numserdes+1) from serdestest_memory

        # to dsp (0) to tx_dsp_iptr_A
        # to dsp (1-neighbours) to rx_dsp_neighbours
        # to dsp (neighbours+1) to serdestest_memory
        
        # To serdes has only nserdes valid addresses
        # to_serdes(0 to nserdes-1) io.lanes_tx(0 to nserdes-1)

        #To connect to tx_iptr_A the output of the memory
        #serdes_to_dsp_address(0)=numserdess+1

        #To connect to memory the output of the serdes0_rx
        #serdes_to_dsp_address(neighbours+1)=0

        #To connect to memory the output of the rx_dsp 
        # serdes_to_dsp_address(neighbours+1)=numserdes

        #To connect to serdes0_tx the output of the rx_dsp
        #dsp_to_serdes_address(0)=0

        #To connect to serdes0_tx the output of the memory
        #dsp_to_serdes_address(0)=neighbours+1

        #To connect to serdes0_tx the output of the tx_neighbour_output1
        #dsp_to_serdes_address(0)=1


import os
import sys

import numpy as np
import tempfile

from thesdk import *
from verilog import *
from verilog.connector import *
from verilog.module import *

class f2_scan_controller(verilog,thesdk):
    @property
    def _classfile(self):
        return os.path.dirname(os.path.realpath(__file__)) + "/"+__name__

    def __init__(self,*arg): 
        self.proplist = [ 'Rs', 
                          'Rs_dsp'
                          'Rxantennas', 
                          'Users',
                          'rx_output_mode', 
                          'rx_dsp_mode', 
                          'dsp_interpolator_scales',
                          'dsp_decimator_scales',
                          'dsp_interpolator_cic3shift',   
                          'dsp_decimator_cic3shift',
                          'nserdes',
                          'neighbours'
                        ];    # properties that can be propagated from parent
        self.Rs = 160e6;                 # Highest sampling frequency at 
        self.Rs_dsp = 20e6;              # dsp sampling frequency
        self.Txantennas = 4;             # Number of antennas
        self.Rxantennas = 4;             # Nuber of antenna
        self.Users      = 4;             # Users
        self.nserdes    = 2;             # Serdeses
        self.neighbours = 2;             # neighbours
        self.memsize    =2**13;          # Test memory size
        self.rx_output_mode = 1;
        self.rx_dsp_mode = 4; #Log2(decimratio) or 4
        self.dsp_interpolator_scales=[1,1,1,1]
        self.dsp_interpolator_cic3shift=4
        self.dsp_decimator_scales=[1,1,1,1]
        self.dsp_decimator_cic3shift=4
        self.model='py';             # can be set externally, but is not propagated
        self.par= False              # By default, no parallel processing
        self.queue= []               # By default, no parallel processing

        # We now where the verilog file is. 
        # Let's read in the file to have IOs defined
        self.dut=verilog_module(file=self.entitypath + '/../f2_dsp/sv/f2_dsp.sv')
        # We need to replicate this in order to get witdth automatically
        self.clockdivider=verilog_module(file=self.entitypath +
                '/../f2_dsp/sv/clkdiv_n_2_4_8.v')
        self.clockdivider.io_signals.mv(fro='io_Ndiv',to='lane_refclk_Ndiv')
        self.clockdivider.io_signals.mv(fro='io_shift',to='lane_refclk_shift')
        self.clockdivider.io_signals.mv(fro='io_clkpn',to='lane_refclk')
        self.clockdivider.io_signals.mv(fro='io_reset_clk',to='lane_refclk_reset')
        self.clockdivider.io_signals.mv(fro='reset',to='reset_clock_div')

        # Scan ins the way to pass the controls# 
        # Format: Time in rows, 
        # Signals in columns, first column is the timestamp
        self._scan = IO();           # Pointer for output data
        self._scan.Data=Bundle()

        # Define the signal connectors associeted with this 
        # controller
        # These are signals of tb driving several targets
        # Not present in DUT
        self.connectors=verilog_connector_bundle()

        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;

        #These are signals not in dut
        self.newsigs=[
                 'initdone',
                 'flag',        #Suprisingly, signal that can be used for flagging
                 'reset_loop'
                ]
        # Initialize Selected signals with parameter values
        # These are tuples defining name init value pair
        self.signallist=[
                ('reset', 1),
                ('flag', 0),
                ('reset_loop',1),
                ('initdone',0),
                ('reset_clock_div',1),
                ('lane_refclk_reset',1),
                ('io_ctrl_and_clocks_tx_reset_clkdiv', 1),
                ('io_ctrl_and_clocks_rx_reset_clkdiv', 1),
                ('io_ctrl_and_clocks_reset_dacfifo', 1),
                ('io_ctrl_and_clocks_reset_outfifo', 1),
                ('io_ctrl_and_clocks_reset_infifo', 1),
                ('io_ctrl_and_clocks_reset_adcfifo', 1),
                ('lane_refclk_Ndiv', 16),
                ('lane_refclk_shift', 0),
                ('io_ctrl_and_clocks_tx_Ndiv', int(self.Rs/(8*self.Rs_dsp))),
                ('io_ctrl_and_clocks_tx_clkdiv_shift', 0),
                ('io_ctrl_and_clocks_rx_Ndiv', int(self.Rs/(8*self.Rs_dsp))),
                ('io_ctrl_and_clocks_rx_clkdiv_shift', 0),
                ('io_ctrl_and_clocks_user_spread_mode', 0),
                ('io_ctrl_and_clocks_user_index', 0),
                ('io_ctrl_and_clocks_antenna_index', 0),
                ('io_ctrl_and_clocks_input_mode', 0),
                ('io_ctrl_and_clocks_adc_fifo_lut_mode', 2),
                ('io_ctrl_and_clocks_rx_output_mode', self.rx_output_mode),
                ('io_ctrl_and_clocks_serdestest_scan_write_mode', 0),
                ('io_ctrl_and_clocks_serdestest_scan_write_address', 0),
                ('io_ctrl_and_clocks_serdestest_scan_write_en', 0),
                ('io_ctrl_and_clocks_serdestest_scan_read_mode', 0),
                ('io_ctrl_and_clocks_serdestest_scan_read_address', 0),
                ('io_ctrl_and_clocks_serdestest_scan_read_en', 0)
            ]
        for user in range(self.Users):
            self.signallist+=[ 
                ('io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_real' \
                            %(user), 0), 
                ('io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_imag' \
                        %(user), 0) 
            ]
                # This is scan output. No bidirectional scan yet
                #('io_ctrl_and_clocks_serdestest_scan_write_value' 0),
        for tx in range(self.Txantennas):
            self.signallist+=[
                ('io_ctrl_and_clocks_interpolator_controls_%s_cic3derivscale' %(tx), 
                    self.dsp_interpolator_scales[3]),
                ('io_ctrl_and_clocks_interpolator_controls_%s_cic3derivshift' %(tx), 
                    self.dsp_interpolator_cic3shift),
                ('io_ctrl_and_clocks_interpolator_controls_%s_hb1scale' %(tx), 
                    self.dsp_interpolator_scales[0]),
                ('io_ctrl_and_clocks_interpolator_controls_%s_hb2scale' %(tx), 
                    self.dsp_interpolator_scales[1]),
                ('io_ctrl_and_clocks_interpolator_controls_%s_hb3scale' %(tx), 
                    self.dsp_interpolator_scales[2]),
                ('io_ctrl_and_clocks_interpolator_controls_%s_mode' %(tx), 
                    4),
                ('io_ctrl_and_clocks_user_sum_mode_%s' %(tx), 0),
                ('io_ctrl_and_clocks_user_select_index_%s' %(tx), 0),
                ('io_ctrl_and_clocks_dac_data_mode_%s' %(tx), 6),
                ('io_ctrl_and_clocks_dac_lut_write_en_%s' %(tx), 0),
                ('io_ctrl_and_clocks_dac_lut_write_addr_%s' %(tx), 0),
                ('io_ctrl_and_clocks_dac_lut_write_vals_%s_real' %(tx), 0),
                ('io_ctrl_and_clocks_dac_lut_write_vals_%s_imag' %(tx), 0)
            ]
            for user in range(self.Users):
                self.signallist+=[
                    ('io_ctrl_and_clocks_tx_user_weights_%s_%s_real' %(tx,user),1),
                    ('io_ctrl_and_clocks_tx_user_weights_%s_%s_imag' %(tx,user),1)
                ]


        for rx in range(self.Rxantennas):
            self.signallist+=[
                ('io_ctrl_and_clocks_decimator_controls_%s_cic3integscale' %(rx), 
                    self.dsp_decimator_scales[0]),
                ('io_ctrl_and_clocks_decimator_controls_%s_cic3integshift' %(rx), 
                    self.dsp_decimator_cic3shift),
                ('io_ctrl_and_clocks_decimator_controls_%s_hb1scale' %(rx), 
                    self.dsp_decimator_scales[1]),
                ('io_ctrl_and_clocks_decimator_controls_%s_hb2scale' %(rx), 
                    self.dsp_decimator_scales[2]),
                ('io_ctrl_and_clocks_decimator_controls_%s_hb3scale' %(rx), 
                    self.dsp_decimator_scales[3]),
                ('io_ctrl_and_clocks_decimator_controls_%s_mode' %(rx), 
                    self.rx_dsp_mode),
                ('io_ctrl_and_clocks_inv_adc_clk_pol_%s' %(rx), 1),
                ('io_ctrl_and_clocks_adc_lut_write_vals_%s_real' %(rx), 0),
                ('io_ctrl_and_clocks_adc_lut_write_vals_%s_imag' %(rx), 0)
            ]
            for user in range(self.Users):
                self.signallist+=[
                    ('io_ctrl_and_clocks_rx_user_weights_%s_%s_real' %(rx,user),1),
                    ('io_ctrl_and_clocks_rx_user_weights_%s_%s_imag' %(rx,user),1)
                ]

        self.signallist+=[
            ('io_ctrl_and_clocks_adc_lut_reset',1),
            ('io_ctrl_and_clocks_adc_lut_write_en',0),
            ('io_ctrl_and_clocks_adc_lut_write_addr',0)
        ]

        for scanind in range(self.nserdes+2):
            self.signallist+=[ 
                ('io_ctrl_and_clocks_from_serdes_scan_%s_valid' %(scanind), 1),
                ('io_ctrl_and_clocks_from_dsp_scan_%s_valid' %(scanind),1),
                ('io_ctrl_and_clocks_to_serdes_mode_%s' %(scanind), 1),
                ('io_ctrl_and_clocks_dsp_to_serdes_address_%s' %(scanind), 0),
            ]

        for scanind in range(self.neighbours+2):
            self.signallist+=[ ('io_ctrl_and_clocks_to_dsp_mode_%s' %(scanind), 1),
                ('io_ctrl_and_clocks_serdes_to_dsp_address_%s' %(scanind), 0) ]
            
        self.init()

    def init(self):
        self._vlogparameters =dict([('Rs',self.Rs)])
        # This gets interesting
        # IO is a file data stucture
        scanfiles=[
                'scan_inputs'
                ]
        for name in scanfiles:
            self._scan.Data.Members[name]=verilog_iofile(self,name=name,
                    dir='in',iotype='ctrl')
        f=self._scan.Data.Members['scan_inputs']

        self.define_scan()
        self.reset()
        self.init_dac_lut()
        self.init_adc_lut()
        f.set_control_data(time=self.curr_time,name='initdone', val=1)
        
    # First we start to control Verilog simulations with 
    # This controller. I.e we pass the IOfile definition
    #def default_setup(self):
    #    if mode=='serdes_rx_to_memory':
    #        self.fill_test_memory_through_serdes_rx()
    #    elif mode=='fill_test_memory_through_scan':
    #        f=self._scan.Data.Members['scan_inputs']
    #        f.set_control_data(time=self.curr_time,name='initdone', val=1)
    #        self.fill_test_memory_through_scan()
    #        self.read_test_memory_through_scan()

    def define_scan(self):
        # This is a bit complex way of passing the data,
        # But eventually we pass only the data , not the file
        # Definition. File should be created in the testbench
        scansigs=[]
        for name, val in self.signallist:
            # We manipulate connectors as verilog_iofile operate on those
            if name in self.newsigs:
                self.connectors.new(name=name, cls='reg')
            elif name in [
                'lane_refclk_Ndiv',
                'lane_refclk_shift',
                'lane_refclk',
                'lane_refclk_reset',
                'reset_clock_div']:
                self.connectors.Members[name]=\
                        self.clockdivider.io_signals.Members[name] 
            else:
                self.connectors.Members[name]=self.dut.io_signals.Members[name] 
                self.connectors.Members[name].init=''
            scansigs.append(name) 
        f=self._scan.Data.Members['scan_inputs']
        f.verilog_connectors=self.connectors.list(names=scansigs)
        f.set_control_data(init=0) # Initialize to zeros at time 0
        for name, val in self.signallist:
            f.set_control_data(time=0,name=name,val=val) 

    def reset(self):
        #start defining the file
        reset_time=int(64/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['scan_inputs']
        time=0
        for name in [ 
                      'reset', 
                      'reset_loop', 
                      'reset_clock_div', 
                      'io_ctrl_and_clocks_tx_reset_clkdiv',
                      'io_ctrl_and_clocks_rx_reset_clkdiv',
                      'lane_refclk_reset',
                      'io_ctrl_and_clocks_reset_dacfifo',
                      'io_ctrl_and_clocks_reset_outfifo',                      
                      'io_ctrl_and_clocks_reset_infifo',
                      'io_ctrl_and_clocks_reset_adcfifo'
                      ]:
            f.set_control_data(time=time,name=name,val=1)

        # After awhile, switch off reset of some blocks 
        time=reset_time
        for name in [ 
                      'reset_clock_div', 
                      'io_ctrl_and_clocks_tx_reset_clkdiv',
                      'io_ctrl_and_clocks_rx_reset_clkdiv',
                      'lane_refclk_reset',
                      'io_ctrl_and_clocks_reset_dacfifo',
                      'io_ctrl_and_clocks_reset_adcfifo',
                      'io_ctrl_and_clocks_reset_outfifo',                      
                      'io_ctrl_and_clocks_reset_infifo'
                      ]:
            f.set_control_data(time=time,name=name,val=0)

        # Switch off the master reset
        time=2*reset_time
        for name in [ 
                      'reset', 
                      ]:
            f.set_control_data(time=time,name=name,val=0)

        # Switch off the last ones
        time=32*reset_time
        for name in [ 
                      'reset_loop', 
                      ]:
            f.set_control_data(time=time,name=name,val=0)
        self.curr_time=time

    def init_dac_lut(self):
        #Define the signals
        step=int(16/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['scan_inputs']
        memaddrcount=0;
        time=self.curr_time
        while (memaddrcount<2**9):
            #This is really controlled by Scan, but we do not have scan model
            for index in range(self.Txantennas): 
                f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_en_%s' %(index),val=1)
                f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_addr_%s' %(index),val=memaddrcount)
                if (memaddrcount < 2**8):
                    f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_vals_%s_real' %(index),val=memaddrcount+2**8)
                    f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_vals_%s_imag' %(index),val=memaddrcount+2**8)
                else:
                    f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_vals_%s_real' %(index),val=memaddrcount-2**8)
                    f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_vals_%s_imag' %(index),val=memaddrcount-2**8)
            memaddrcount+=1
            time+=step
            for index in range(self.Txantennas): 
                f.set_control_data(time=time,name='io_ctrl_and_clocks_dac_lut_write_en_%s' %(index),val=0)
        self.curr_time=time

    def init_adc_lut(self):
        #Define the signals
        time_offset=self.curr_time
        step=int(16/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['scan_inputs']
        memaddrcount=0;
        time=time_offset
        while (memaddrcount<2**9):
            f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_en',val=1)
            f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_addr',val=memaddrcount)
            for index in range(self.Rxantennas): 
                f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_vals_%s_real' %(index),val=memaddrcount)
                f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_vals_%s_imag' %(index),val=memaddrcount)
            memaddrcount+=1
            time+=step
            f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_en', val=0)
            f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_reset', val=0)
        self.curr_time=time

    # Fill test memory methods
    def fill_test_memory_through_serdes_rx(self):
        f=self._scan.Data.Members['scan_inputs']
        #To connect to memory the output of the serdes0_rx
        #serdes_to_dsp_address(neighbours+1)=0
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdes_to_dsp_address_%s' %(self.neighbours+1),val=0)
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=2)
        #This is how long it takes, 
        self.curr_time+=self.memsize*int(1/(self.Rs_dsp*1e-12))
        #Lets flag for it
        f.set_control_data(time=self.curr_time,name\
            ='flag', val=1)
        self.curr_time+=int(1/(self.Rs_dsp*1e-12))
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=0)

    def fill_test_memory_through_dsp_rx(self,**kwargs):
        rate=kwargs.get('rate',self.Rs_dsp)
        f=self._scan.Data.Members['scan_inputs']
        #To connect to memory the output of the rx_dsp 
        # serdes_to_dsp_address(neighbours+1)=numserdes
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdes_to_dsp_address_%s' %(self.neighbours+1),
            val=self.nserdes)
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=2)
        #This is how long it takes, 
        self.curr_time+=(self.memsize+64)*int(1/(rate*1e-12))
        #Lets flag for it
        f.set_control_data(time=self.curr_time,name\
            ='flag', val=1)
        self.curr_time+=int(1/(rate*1e-12))
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=0)
        self.curr_time+=int(64/(rate*1e-12))

    def fill_test_memory_through_scan(self):
        # Serdes test scan write modes:
        # 0=Zero, do nothing
        # 1= Scan, Write fom scan
        # 2= Fill from write_val selcted by Test addressing
        # 3= Loop, Keep on filling until changed to zero
        f=self._scan.Data.Members['scan_inputs']
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=1)
        step=int(1/(self.Rs_dsp*1e-12))
        for address in range(self.memsize):
            f.set_control_data(time=self.curr_time,name\
                ='io_ctrl_and_clocks_serdestest_scan_write_address', val=address)
            for user in range(self.Users):
                # Let's make this simple first
                f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_real'\
                            %(user) ,val=address)
                f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_imag'\
                            %(user) ,val=address)
            f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_en', val=1)
            self.curr_time+=2*step
            f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_en', val=0)
        f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=0)
        self.curr_time+=64*step

    def write_loop_test_memory_through_serdes_rx(self,**kwargs):
        f=self._scan.Data.Members['scan_inputs']
        rate=kwargs.get('rate',self.Rs_dsp)
        duration=kwargs.get('duration',self.memsize*int(1/(rate*1e-12)))
        #To connect to memory the output of the serdes0_rx
        #serdes_to_dsp_address(neighbours+1)=0
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdes_to_dsp_address_%s' %(self.neighbours+1),val=0)
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=3)
        #Lets flag for it
        if duration !=float('Inf'):
            #This is how long it takes, 
            self.curr_time+=duration
            f.set_control_data(time=self.curr_time,name\
                ='io_ctrl_and_clocks_serdestest_scan_write_mode', val=0)

    #Flush test memory methods
    def flush_test_memory_through_serdes_tx(self,**kwargs):
        f=self._scan.Data.Members['scan_inputs']
        rate=kwargs.get('rate',self.Rs_dsp)
        duration=kwargs.get('duration',self.memsize*int(1/(rate*1e-12)))
        #To connect to serdes0_tx the output of the memory
        #dsp_to_serdes_address(0)=neighbours+1
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_dsp_to_serdes_address_%s' %(0),val=self.neighbours+1)
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=2)
        #This is how long it takes, 
        self.curr_time+=duration
        #Lets flag for it
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=0)


    def flush_test_memory_through_dsp_tx(self,**kwargs):
        f=self._scan.Data.Members['scan_inputs']
        rate=kwargs.get('rate',self.Rs_dsp)
        duration=kwargs.get('duration',self.memsize*int(1/(rate*1e-12)))
        #To connect to tx_iptr_A the output of the memory
        #serdes_to_dsp_address(0)=numserdess+1
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdes_to_dsp_address_%s' %(0),val=self.nserdes+1)
        #Mode2 is to fill
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=2)
        #This is how long it takes, 
        self.curr_time+=duration
        #Lets flag for it
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=0)

    def flush_test_memory_through_scan(self):
        # Serdes test scan write modes:
        # 0=Zero, do nothing
        # 1= Scan, Write fom scan
        # 2= Fill from write_val selcted by Test addressing
        # 3= Loop, Keep on filling until changed to zero
        f=self._scan.Data.Members['scan_inputs']
        #Mode21 is to scan
        f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=1)
        step=int(1/(self.Rs_dsp*1e-12))
        for address in range(self.memsize):
            f.set_control_data(time=self.curr_time,name\
                ='io_ctrl_and_clocks_serdestest_scan_read_address', val=address)
            #for user in range(self.Users):
            #    # Let's make this simple first
            #    f.set_control_data(time=self.curr_time,name\
            #        ='io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_real'\
            #                %(user) ,val=address)
            #    f.set_control_data(time=self.curr_time,name\
            #        ='io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_imag'\
            #                %(user) ,val=address)
            f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_read_en', val=1)
            self.curr_time+=step
            f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_read_en', val=0)
        f.set_control_data(time=self.curr_time,name\
                    ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=0)
        self.curr_time+=step

    def read_loop_test_memory_through_serdes_tx(self,**kwargs):
        f=self._scan.Data.Members['scan_inputs']
        duration=kwargs.get('duration',self.memsize*int(1/(self.Rs_dsp*1e-12)))
        #To connect to serdes0_tx the output of the memory
        #dsp_to_serdes_address(0)=neighbours+1
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_dsp_to_serdes_address_%s' %(0),val=self.neighbours+1)
        #Mode3 is to loop
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=3)

        if duration !=float('Inf'):
            #This is how long it takes, 
            self.curr_time+=duration
            f.set_control_data(time=self.curr_time,name\
                ='io_ctrl_and_clocks_serdestest_scan_read_mode', val=0)

    def bypass_rx_dsp(self):
        f=self._scan.Data.Members['scan_inputs']
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_rx_output_mode',val=0)
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_adc_fifo_lut_mode',val=1)
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_rx_Ndiv',val=2)
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_rx_clkdiv_shift',val=0)
        f.set_control_data(time=self.curr_time,name\
            ='lane_refclk_Ndiv',val=1)
        f.set_control_data(time=self.curr_time,name\
            ='lane_refclk_shift',val=0)

    def bypass_tx_dsp(self):
        f=self._scan.Data.Members['scan_inputs']
        for tx in range(self.Txantennas):
            f.set_control_data(time=self.curr_time,name\
                ='io_ctrl_and_clocks_dac_data_mode_%s' %(tx),val=0)
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_tx_Ndiv',val=2)
        f.set_control_data(time=self.curr_time,name\
            ='io_ctrl_and_clocks_tx_clkdiv_shift',val=0)
        f.set_control_data(time=self.curr_time,name\
            ='lane_refclk_Ndiv',val=1)
        f.set_control_data(time=self.curr_time,name\
            ='lane_refclk_shift',val=0)

    #def set_dsp_interpolator_scales(self,**kwargs):
    #    dsp_interpolator_scales=kwargs.get('dsp_interpolator_scales',self.dsp_interpolator_scales)
    #    f=self._scan.Data.Members['scan_inputs']
    #    for tx in range(self.Txantennas):
    #        self.signallist+=[
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_cic3derivscale' %(tx), 
    #                self.dsp_interpolator_scales[3]),
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_cic3derivshift' %(tx), 
    #                self.dsp_interpolator_cic3shift),
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_hb1scale' %(tx), 
    #                self.dsp_interpolator_scales[0]),
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_hb2scale' %(tx), 
    #                self.dsp_interpolator_scales[1]),
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_hb3scale' %(tx), 
    #                self.dsp_interpolator_scales[2]),
    #            ('io_ctrl_and_clocks_interpolator_controls_%s_mode' %(tx), 
    #                4),
    #    f.set_control_data(time=self.curr_time,name\
    #                ='dsp_interpolator_scales', val=0)

if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  f2_scan_controller import *
    t=thesdk()
    t.print_log({'type':'I', 'msg': "This is a testing template. Enjoy"})

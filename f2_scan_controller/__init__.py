# f2_scan_controller class 
# Last modification by Marko Kosunen, marko.kosunen@aalto.fi, 05.01.2018 11:07
#Add TheSDK to path. Importing it first adds the rest of the modules
#Simple buffer template
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
                          'Rxantennas', 
                          'rx_output_mode' 
                        ];    # properties that can be propagated from parent
        self.Rs = 1;                 # sampling frequency
        self.Txantennas = 4;                 # sampling frequency
        self.Rxantennas = 4;                 # sampling frequency
        self.model='py';             # can be set externally, but is not propagated
        self.par= False              # By default, no parallel processing
        self.queue= []               # By default, no parallel processing
        # We now where the verilog file is. 
        # Let's read in the file to have IOs defined
        self.dut=verilog_module(file=self.entitypath + '/../f2_dsp/sv/f2_dsp.sv')

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
        self.init()

    def init(self):
        self._vlogparameters =dict([('Rs',self.Rs)])
        # This gets interesting
        # IO is a file data stucture
        scanfiles=[
                'scan_inputs'
                ]
        for name in scanfiles:
            self._scan.Data.Members[name]=verilog_iofile(self,name=name,dir='in',iotype='ctrl')

        self.define_scan()
        self.reset()
        self.init_dac_lut()
        self.init_adc_lut()

    # First we start to control Verilog simulations with 
    # This controller. I.e we pass the IOfile definition
    def setup(self,**kwargs):
        mode=kwargs.get(mode,'default')
        if mode=='default':
            pass
        elif mode=='rx_outmode':
            pass

    def define_scan(self):
        # This is a bit complex way of passing the data,
        # But eventually we pass only the data , not the file
        # Definition. File should be created in the testbench
        newsigs=['reset_loop',
                 'reset_clock_div',
                 'lane_refclk_reset'
                ]
        for name in newsigs:
            # We manipulate connectors as verilog_iofile operate on those
            self.connectors.new(name=name, cls='reg') 

        # These are dut signals
        dutsigs=[
            'reset',
            'io_ctrl_and_clocks_tx_reset_clkdiv',
            'io_ctrl_and_clocks_rx_reset_clkdiv',
            'io_ctrl_and_clocks_reset_dacfifo',
            'io_ctrl_and_clocks_reset_outfifo',
            'io_ctrl_and_clocks_reset_infifo',
            'io_ctrl_and_clocks_reset_adcfifo'
        ]
        for name in dutsigs:
            #i Reveals if those signals even exist.
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''
        self.scansigs=newsigs+dutsigs

        dutsigs=[]
        for i in range(self.Txantennas):
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_en_%s' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_addr_%s' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_vals_%s_real' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_vals_%s_imag' %(i))

        for name in dutsigs:
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''
        self.scansigs+=dutsigs

        dutsigs=['io_ctrl_and_clocks_adc_lut_write_en']
        dutsigs.append('io_ctrl_and_clocks_adc_lut_write_addr')
        for i in range(self.Txantennas):
            dutsigs.append('io_ctrl_and_clocks_adc_lut_write_vals_%s_real' %(i))
            dutsigs.append('io_ctrl_and_clocks_adc_lut_write_vals_%s_imag' %(i))
        for name in dutsigs:
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''

        self.scansigs+=dutsigs

        f=self._scan.Data.Members['scan_inputs']
        f.verilog_connectors=self.connectors.list(names=self.scansigs)
        f.set_control_data(init=0) # Initialize to zeros at time 0

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

    def init_dac_lut(self):
        #Define the signals
        time_offset=int(32*64/(self.Rs*1e-12))
        step=int(16/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['scan_inputs']
        memaddrcount=0;
        time=time_offset
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

    def init_adc_lut(self):
        #Define the signals
        time_offset=int(32*64/(self.Rs*1e-12))
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

    def serdestest(self):
        pass
  #output        io_ctrl_and_clocks_from_serdes_scan_0_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_serdes_scan_0_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_0_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_serdes_scan_0_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_serdes_scan_1_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_serdes_scan_1_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_1_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_serdes_scan_1_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_serdes_scan_2_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_serdes_scan_2_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_2_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_serdes_scan_2_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_serdes_scan_3_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_serdes_scan_3_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_serdes_scan_3_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_serdes_scan_3_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_dsp_scan_0_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_dsp_scan_0_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_0_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_dsp_scan_0_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_dsp_scan_1_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_dsp_scan_1_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_1_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_dsp_scan_1_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_dsp_scan_2_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_dsp_scan_2_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_2_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_dsp_scan_2_bits_rxindex, // @[:@123372.4]
  #output        io_ctrl_and_clocks_from_dsp_scan_3_ready, // @[:@123372.4]
  #input         io_ctrl_and_clocks_from_dsp_scan_3_valid, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_0_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_0_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_0_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_1_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_1_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_1_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_2_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_2_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_2_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_3_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_3_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_3_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_4_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_4_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_4_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_5_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_5_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_5_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_6_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_6_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_6_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_7_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_7_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_7_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_8_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_8_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_8_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_9_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_9_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_9_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_10_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_10_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_10_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_11_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_11_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_11_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_12_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_12_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_12_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_13_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_13_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_13_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_14_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_14_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_14_uindex, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_15_udata_real, // @[:@123372.4]
  #input  [15:0] io_ctrl_and_clocks_from_dsp_scan_3_bits_data_15_udata_imag, // @[:@123372.4]
  #input  [3:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_data_15_uindex, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_from_dsp_scan_3_bits_rxindex, // @[:@123372.4]
  #input  [2:0]  io_ctrl_and_clocks_dsp_to_serdes_address_0, // @[:@123372.4]
  #input  [2:0]  io_ctrl_and_clocks_dsp_to_serdes_address_1, // @[:@123372.4]
  #input  [2:0]  io_ctrl_and_clocks_dsp_to_serdes_address_2, // @[:@123372.4]
  #input  [2:0]  io_ctrl_and_clocks_dsp_to_serdes_address_3, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_0, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_1, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_2, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_3, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_4, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_serdes_to_dsp_address_5, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_serdes_mode_0, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_serdes_mode_1, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_serdes_mode_2, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_serdes_mode_3, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_0, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_1, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_2, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_3, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_4, // @[:@123372.4]
  #input  [1:0]  io_ctrl_and_clocks_to_dsp_mode_5, // @[:@123372.4]
        #Signals
        # write_address
        # write_value  
        # write_en     
        # read_mode    
        # read_address 
        # read_value   
        # read_en      
        pass
        #name='serdestest_write'
        #ionames=[]
        #ionames+=['io_ctrl_and_clocks_serdestest_scan_write_mode',
        #          'io_ctrl_and_clocks_serdestest_scan_write_address']
        #ionames.append('io_ctrl_and_clocks_serdestest_scan_write_en')
        #ionames.append('io_ctrl_and_clocks_serdestest_scan_write_value_rxindex')
        #for user in range(self.Users):
        #    ionames.append('io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_real' %(user))
        #    ionames.append('io_ctrl_and_clocks_serdestest_scan_write_value_data_%s_udata_imag' %(user))
        #self.iofile_bundle.Members[name].verilog_connectors=\
        #        self.tb.connectors.list(names=ionames)

if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  f2_scan_controller import *
    t=thesdk()
    t.print_log({'type':'I', 'msg': "This is a testing template. Enjoy"})

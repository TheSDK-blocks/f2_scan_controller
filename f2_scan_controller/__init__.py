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
        self.proplist = [ 'Rs' ];    # properties that can be propagated from parent
        self.Rs = 1;                 # sampling frequency
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

        # Define the sign connectors associeted with this 
        # controller
        # These are signals of tb driving several targets
        # Not present in DUT
        self.connectors=verilog_connector_bundle()
        newsigs=['reset_loop',
                 'reset_clock_div',
                 'lane_refclk_reset'
                ]
        for name in newsigs:
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
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''
        self.scansigs=newsigs+dutsigs

        if len(arg)>=1:
            parent=arg[0]
            self.copy_propval(parent,self.proplist)
            self.parent =parent;
        self.init()

    def init(self):
        self._vlogparameters =dict([('Rs',self.Rs)])
        self.reset_sequence_gen()

    # First we start to control Verilog simulations with 
    # This controller. I.e we pass the IOfile definition
    def main(self):
        pass


    def reset_sequence_gen(self):
        # This gets interesting
        # IO is a file data stucture
        self._scan.Data.Members['reset_sequence']=verilog_iofile(self,name='reset_sequence',dir='in',iotype='ctrl')
        reset_time=int(32/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['reset_sequence']
        
        #Define the connectors associeted with this file
        ## Start initializations
        #Init the signals connected to the dut input to zero
        f.verilog_connectors=self.connectors.list(names=self.scansigs)
        print(f.verilog_connectors)

        # Define the control sequence time and data values
        # [TODO]: de-init could be added to this method
        f.set_control_data(init=1) # Initialize to ones at time 0

        # After awhile, switch off reset of some blocks 
        time=reset_time
        for name in [ 
                      'reset_clock_div', 
                      'io_ctrl_and_clocks_tx_reset_clkdiv',
                      'io_ctrl_and_clocks_rx_reset_clkdiv',
                      'lane_refclk_reset',
                      'io_ctrl_and_clocks_reset_dacfifo',
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
        time=16*reset_time
        for name in [ 
                      'reset_loop', 
                      'io_ctrl_and_clocks_reset_adcfifo' 
                      ]:
            f.set_control_data(time=time,name=name,val=0)
        print(f.data)

if __name__=="__main__":
    import matplotlib.pyplot as plt
    from  f2_scan_controller import *
    t=thesdk()
    t.print_log({'type':'I', 'msg': "This is a testing template. Enjoy"})

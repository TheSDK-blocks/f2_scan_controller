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
        self.proplist = [ 'Rs', 'Rxantennas' ];    # properties that can be propagated from parent
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

        # Define the sign connectors associeted with this 
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
                'reset',
                'daclut',
                'adclut'
                ]
        for name in scanfiles:
            self._scan.Data.Members[name]=verilog_iofile(self,name=name,dir='in',iotype='ctrl')

        self.reset()
        self.init_dac_lut()
        self.init_adc_lut()

    # First we start to control Verilog simulations with 
    # This controller. I.e we pass the IOfile definition
    def main(self):
        pass

    def reset(self):
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
        self.resetsigs=newsigs+dutsigs

        #start defining the file
        reset_time=int(64/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['reset']
        
        #Define the connectors associeted with this file
        ## Start initializations
        f.verilog_connectors=self.connectors.list(names=self.resetsigs)

        # Define the control sequence time and data values
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

    def init_dac_lut(self):
        dutsigs=[]
        for i in range(self.Txantennas):
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_en_%s' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_addr_%s' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_vals_%s_real' %(i))
            dutsigs.append('io_ctrl_and_clocks_dac_lut_write_vals_%s_imag' %(i))
        self.daclutsigs=dutsigs

        for name in self.daclutsigs:
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''

        f=self._scan.Data.Members['daclut']
        f.verilog_connectors=self.connectors.list(names=self.daclutsigs)
        f.set_control_data(init=0) # Initialize to ones at time 0

        #Define the signals
        time_offset=int(16*64/(self.Rs*1e-12))
        step=int(2/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['daclut']
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
        dutsigs=['io_ctrl_and_clocks_adc_lut_write_en']
        dutsigs.append('io_ctrl_and_clocks_adc_lut_write_addr')
        for i in range(self.Txantennas):
            dutsigs.append('io_ctrl_and_clocks_adc_lut_write_vals_%s_real' %(i))
            dutsigs.append('io_ctrl_and_clocks_adc_lut_write_vals_%s_imag' %(i))
        self.adclutsigs=dutsigs
        for name in self.adclutsigs:
            self.connectors.Members[name]=self.dut.io_signals.Members[name] 
            self.connectors.Members[name].init=''

        f=self._scan.Data.Members['adclut']
        f.verilog_connectors=self.connectors.list(names=self.adclutsigs)
        f.set_control_data(init=0) # Initialize to ones at time 0

        #Define the signals
        time_offset=int(16*64/(self.Rs*1e-12))
        step=int(2/(self.Rs*1e-12))
        # Let's assign the shorthand for the iofile
        f=self._scan.Data.Members['adclut']
        memaddrcount=0;
        time=time_offset
        f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_en',val=1)
        while (memaddrcount<2**9):
            f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_addr',val=memaddrcount)
            for index in range(self.Rxantennas): 
                f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_vals_%s_real' %(index),val=memaddrcount)
                f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_vals_%s_imag' %(index),val=memaddrcount)
            memaddrcount+=1
            time+=step
        f.set_control_data(time=time,name='io_ctrl_and_clocks_adc_lut_write_en', val=0)

    def serdestest(self):
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

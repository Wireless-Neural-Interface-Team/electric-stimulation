
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 27 15:41:00 2020

@author: btlabs
"""


import pyvisa
import PyDAQmx as nidaq
import numpy as np
from ctypes import byref, c_int32
import matplotlib.pyplot as plt
from scipy import signal
import math
from scipy import interpolate


#import keyboard
read = c_int32()
sampling_rate =  1e3
tps_inter_stim = 20  #in seconde
time = np.linspace(0, 1,int(sampling_rate*tps_inter_stim), endpoint=False)
Sig=np.zeros((len(time)))
n=0

for i in range(0,200): 

 Sig[i] =2
 
 
# n=n+1
# print(n)




    


t = nidaq.Task()
t.CreateAOVoltageChan("Dev1/ao0", None, -10.0, 10.0, nidaq.DAQmx_Val_Volts, None)
t.CfgSampClkTiming("", 1e3, nidaq.DAQmx_Val_Rising, nidaq.DAQmx_Val_ContSamps, 1000)


t.WriteAnalogF64(int(sampling_rate*tps_inter_stim),False,10,nidaq.DAQmx_Val_GroupByScanNumber,Sig,byref(read),None)
t.StartTask()





#t2.ClearTask()    
        






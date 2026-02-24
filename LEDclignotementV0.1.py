# -*- coding: utf-8 -*-
"""
Created on Fri Feb 28 15:06:27 2025

@author: WNIlabs
"""

# import pyvisa
import PyDAQmx as nidaq
import numpy as np
from ctypes import byref, c_int32
import time
import matplotlib.pyplot as plt

# NI parameter 
Freq_clignotement = 0.2  #Hz
nb_clignotement   = 1
Duty_cycle_clignotement =  1    # 
Duty_cycle_intensité  = 1  # 
Inter_train_interval  = 20 #s
 


 
# controls pulse start in “cycle” mode (rising edge only the first tuple value is used)
# in “gate mode” the signal is held for the duration of the signal. 

################################### Start system ###################################
FreqNi            = 5e3   #Hz  max 5Khz
Freq_intensite    = 1000   #Hz
start = 1
Period_un_clignotement = np.ceil(FreqNi/Freq_clignotement)
temps_pour_un_train = int(Period_un_clignotement*nb_clignotement) #arrondi au supérieur
timer = int(temps_pour_un_train+Inter_train_interval*FreqNi) # résolution de 1/FreqNi s
PeriodNi = 1/FreqNi
Periodintensite  = np.ceil(FreqNi/Freq_intensite)
# rangeintensite  = int((Periodintensite*Duty_cycle_intensité)/PeriodNi) # résolution de 1/FreqNi s pour 20KHZ une imprécision de 200µs
###############################################################################################################################
#signal 

if Freq_clignotement<Freq_intensite:
    if Duty_cycle_intensité>=0 and Duty_cycle_intensité<=1:
        Sig=np.zeros((timer,1))
        Sig_clignotement = [3]*timer
        Sig_Intensite    = [3]*timer
        for j in range(timer):
            Sig[j,0] = 3
            if j<temps_pour_un_train:
                if j%Period_un_clignotement < np.ceil(Period_un_clignotement*Duty_cycle_clignotement):
                    Sig_clignotement[j] = 0
                    if j%Periodintensite < np.ceil(Periodintensite*Duty_cycle_intensité):
                      Sig[j,0] = 0
                      Sig_Intensite[j] = 0

        # for j in range(temps_pour_un_train):
        #     for i in range(rangeintensite):        #(0,6):   #(0,16):   #(0,6): 
        #         Sig[i,0] = 3
    else :
        print("ERROR please select a valid Duty_cycle_intensité (value between 0 and 1)")
else :
    print("Error Freq_clignotement>Freq_intensite")
    
try:
    plt.figure()
    plt.plot(Sig_clignotement, color ='r', label ="clignotement")
    plt.plot(Sig_Intensite, color ='g', label ="Intensité")
    plt.legend()
    read = c_int32()
    t = nidaq.Task()
    t.CreateAOVoltageChan("Dev1/ao0", None, 0.0, 10.0, nidaq.DAQmx_Val_Volts, None)
    t.CfgSampClkTiming("", FreqNi, nidaq.DAQmx_Val_Rising, nidaq.DAQmx_Val_ContSamps, 100000)
    t.WriteAnalogF64(timer,False,10,nidaq.DAQmx_Val_GroupByScanNumber,Sig,byref(read),None)
    t.StartTask()
    while True :
       #print("éclairage en cours")
       plt.pause(0.1)
        # time.sleep(0.1)

except KeyboardInterrupt:
    t.StopTask()
    t.ClearTask()
    t = nidaq.Task()
    t.CreateAOVoltageChan("Dev1/ao0", None, 0.0, 10.0, nidaq.DAQmx_Val_Volts, None)
    t.WriteAnalogScalarF64(1,10.0,3, None)
    t.StartTask()
    t.ClearTask()

    
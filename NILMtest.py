#execfile("NILM.py")

from NILM import *
import numpy as np
import math
import warnings



with warnings.catch_warnings(record=True) as w:
    # Cause all warnings to always be triggered.
    warnings.simplefilter("error")

#size median fiter used for edge detection
    #0: Filter deactivated
filterSize=0

#min amount of datapoint required to from a network (steady) state (in practice: minStatePoints+filterSize)
minStatePoints=5

#Edge detection algortihm used:
    # 1: Deviation from temporary data 
    # 2: Deviation from previously identified data (uses 1 when few data yet collected)
edgeDetectionNr=4

#Measured power when no appliance is active
ground=None
realGroundPower=-62
reactiveGroundPower=-276
ground=[realGroundPower,reactiveGroundPower]

#Edge detection algortihm used for anomaly detection:
    # 1: Deviation from temporary data 
    # 2: Deviation from previously identified data (uses 1 when few data yet collected)
edgeAnomalyNr=5

#Edge detection algortihm used for calculating deviation (edge detection 2):
    # 0: Fixed Value
    # 1: Statistical average
    # 2: Simple average
edgeDeviationNr=1

#Check whether or not a new appliace can be identified
    # 1: DBSCAN: Cluster network states (remainder)
    # 2: DBSCAN: Cluster difference between consecutive network states
    # 3: K-Means: Cluster network states (remainder)
preClusterNr=2

#Update All appliances
optimizeClusterNr=2

#Estimates for the given (or all if no state is given) network state(s) the appliance state of each appliance 
    #1: Allows but one state change at any given moment 
optimizeStateNr=11

system=NILM(filterSize,minStatePoints,edgeDetectionNr,ground,edgeAnomalyNr,edgeDeviationNr, preClusterNr,optimizeClusterNr,optimizeStateNr)
testNr=9
if (testNr==1):
    d=[]
    for x in range(0,5):
        for i1 in range(0,20):
            p=DataPoint(system,[np.random.normal(10,1,1)[0],np.random.normal(11,1,1)[0]])
            d.append(p)
        for i2 in range(0,20):
            p=DataPoint(system,[np.random.normal(13,1,1)[0],np.random.normal(7,1,1)[0]])
            d.append(p)
        for i3 in range(0,25):
            p=DataPoint(system,[np.random.normal(5,1,1)[0],np.random.normal(15,1,1)[0]])
            d.append(p)
elif (testNr==2):
    system.read('9.csv',[1,2])
elif (testNr==3):
    system.read('9.csv',[1,2])
    system.error
    reference=NILM(filterSize,minStatePoints,edgeDetectionNr,ground,0,edgeDeviationNr, preClusterNr,optimizeClusterNr,optimizeStateNr)
    reference.read('9.csv',[1,2])
    reference.error
elif (testNr==4):
    system.iterate('9.csv',[1,2],1,'CSV',None,2)
elif (testNr==5):
    system.read('CaseLight1S.xls',[12,14],9,'XLS',None)
    system.read('CaseLight2S.xls',[12,14],8,'XLS',None)
    system.read('CaseLight3S.xls',[12,14],8,'XLS',None)
    system.read('CaseLight4S.xls',[12,14],8,'XLS',None)
elif (testNr==6):
    system.read('CaseIN.xls',[12,14],9,'XLS',None)
elif testNr==7:
    system.read('CaseIN1.xls',[12,14],9,'XLS',None)
elif testNr==8:
    system.read('CaseLA2.xls',[12,14],9,'XLS',None)
elif testNr==9:
    system.read('MK1.xls',[11,13,0],9,'XLS',None)
    system.read('MK2.xls',[11,13,0],9,'XLS',None)
    system.read('MK3.xls',[11,13,0],9,'XLS',None)
    system.read('MK4.xls',[11,13,0],9,'XLS',None)
print "END"
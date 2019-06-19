from NILM import *
import numpy as np
import math
import warnings
class NILMrun:
  def __init__():
    self.step=1
    self.edgeDetectionNr=1
    self.edgeDeviationNr=1
    self.filterSize=0
    self.edgeAnomalyNr=6
    self.preClusterNr=4
    self.optimizeStateNr=6
    self.optimizeClusterNr=4
    self.ground=None
    self.fileType=None
    self.columns=None
    self.firstRow=None
    self.system=None
    print("This algortihm will aid you in the setup of the NILM algortihm.")
    print("The algortihm will give several existing options, answer using'setup.select(VAUE)'.")
    print("With VALUE being the integer (or sometimes other parameter) representing the selected option.")
    print("Leaving the VALUE emty will result in the algortihm selecting the default option.")
    print("Using a VALUE that does not exist will lead to errors")
    print("It is recommended to remain consistent with choices among the different steps(eg.: Average power VS Power difference)")
    print("")
    print("The first selection is the type of edge detection used:")
    print("0: No edge detection used (Only recomended if the data has already been separated per steady state.")
    print("1: Limit Value Edge Detection (Default)")
    print("2: Limit Value Edge Detection in combination with a student T-test")
    print("3: Statistical Edge Detection using local average and deviation")
    print("4: Statistical Edge Detection using local average and deviation in combination with a student T-test")
    print("5: Statistical Edge Detection using local average and global deviation")
    print("6: Statistical Edge Detection using local average and global deviation in combination with a student T-test")
    print("7: Statistical Edge Detection using local average and manual deviation")
    print("8: Statistical Edge Detection using local average and manual deviation in combination with a student T-test")
          
  def select(Value=None):
    if self.step==1:
      if not Value==None:
        self.edgeDetectionNr=Value
      if Value==7 or Value==8:
        self.step=2
        print("Suply manual devialtion: 'setup.select([RealPowerDeviation,ReactivePowerDeviation])'")
      else:
        self.step=3
        print("Select is the way of calcualting the global deviation:")
        print("1: Weigted average (Default)")
        print("2: Simple average")
    elif self.step==2:
      if len(Value)==2:
        self.PowerDeviation==[Value[0],Value[1]]
        self.edgeDeviationNr=0
        self.step=4
        print("Select size of median filter (0 to deactivate (default))")
      else:
        print("Value not recognised")
        print("Suply manual devialtion: 'setup.select([RealPowerDeviation,ReactivePowerDeviation])'")
    elif self.step==3:
      if not Value==None:
        self.edgeDeviationNr=Value
      self.step=4
      print("Select size of median filter (0 to deactivate (default))")
    elif self.step==4:
      if not Value==None:
        self.filterSize=Value
      self.step=5
      print("Select is the analy detection algorithm used for creating network states:")
      print("0: No Anomaly detection used.")
      print("1: Statistical Anomaly Detection using local average and deviation")
      print("2: Statistical Anomaly Detection using local average and global deviation")
      print("3: Statistical Anomaly Detection using local average and deviation")
      print("4: Statistical Anomaly Detection using local average and combined* deviation or lower limit")
      print("5: Statistical Anomaly Detection using local average and global deviation or lower limit")
      print("6: Statistical Anomaly Detection using local average and combined* deviation or lower limit (Default)")
      print("* Combined deviation uses both local and global deviation.")
    elif self.step==5:
      if not Value==None:
        self.edgeAnomalyNr=Value
      self.step=6
      print("Select is the algorithm used for identifying (Type-I) appliances:")
      print("1: K-means clustering of the average power of network states.")
      print("2: K-means clustering of the power difference between consecutive network states.")
      print("3: DBSCAN clustering of average power of network states.")
      print("4: DBSCAN clustering of the power difference between consecutive network states. (Default)")
      print("5: Agglomerative clustering of average power of network states.")
      print("6: Agglomerative clustering of the power difference between consecutive network states.")
    elif self.step==6:
      if not Value==None:
        self.preClusterNr=Value
      self.step=7
      print("Select is the algorithm used for estimating the power disaggregation of individual netsork states:")
      print(" 1: Minimization of the average power of network states.")
      print(" 2: Minimization of the power difference between consecutive network states.")
      print(" 3: Assymetrical* minimization of the average power of network states.")
      print(" 4: Assymetrical* minimization of the power difference between consecutive network states.")
      print(" 5: Assymetrical* minimization of the power difference between consecutive network states with missed edge detection.")
      print(" 6: Assymetrical* minimization of the power difference between consecutive network states with missed edge and dual edge detection (Default).")
      print(" 7: Minimization of the probability according to average power (and deviation) of network states.")
      print(" 8: Minimization of the probability according to the power difference between consecutive network states.")
      print(" 9: Assymetrical* Minimization of the probability according to the power difference between consecutive network states with missed edge detection.")
      print("10: Assymetrical* Minimization of the probability according to the power difference between consecutive network states with missed edge and dual edge detection.")
      print("11: Minimization of the probability according to average power, deviation, and duration of network states.")
      print("12: Minimization of the probability according to average power, deviation, and duration of network states with dual edge detection.")
      print("* Assymetrical aproaches treat upward and downward power changes slightly diffent (diffent thresholds).")
    elif self.step==7:
      if not Value==None:
        self.optimizeStateNr=Value
      self.step=8
      print("Select is the algorithm used for optimizing applaince parameters:")
      print(" 1: Minimization of the average power of network states.")
      print(" 2: Minimization of the power difference between consecutive network states.")
      print(" 3: Minimization of the average power of network states and Type-II appliance detection.")
      print(" 4: Minimization of the power difference between consecutive network states and Type-II appliance detection. (Default)")
    elif self.step==8:
      if not Value==None:
        self.optimizeClusterNr=Value
      self.step=9
      print("Enter the background power present during all measurements: 'setup.select([RealPowerGround,ReactivePowerGround])'")
      print("Leaving this empty result in the algorithm incrementaly estimating these values (slows the algortihm down)")
    elif self.step==9:
      if len(Value)==2
        self.ground=[Value[0],Value[1]]
        self.step=10
        self.system=NILM(self.filterSize,self.minStatePoints,self.edgeDetectionNr,self.ground,self.edgeAnomalyNr,self.edgeDeviationNr, self.preClusterNr,self.optimizeClusterNr,self.optimizeStateNr)
        print("Select is the format of the data file: 'XLS' (1) or 'CSV' (2):")
      elif Value==None:
        self.step=10
        self.system=NILM(self.filterSize,self.minStatePoints,self.edgeDetectionNr,self.ground,self.edgeAnomalyNr,self.edgeDeviationNr, self.preClusterNr,self.optimizeClusterNr,self.optimizeStateNr)
        print("Select is the format of the data file: 'XLS' (1) or 'CSV' (2):")
      else:
        print("Value not recognised")
        print("Enter the background power present during all measurements: 'setup.select([RealPowerGround,ReactivePowerGround])'")
        print("Leaving this empty result in the algorithm incrementaly estimating these values (slows the algortihm down)")
    elif self.step==10:
      if Value='XLS' or Value==1:
        self.fileType='XLS'
        self.step=11
        print("Suply columns in with measurement values are present: 'setup.select([RealPower,ReactivePower,Timestamp])'")
        print("TimeStamp is optional")
      if Value='CSV' or Value==2:
        self.fileType='CSV'
        self.step=11
        print("Suply columns in with measurement values are present: 'setup.select([RealPower,ReactivePower,Timestamp])'")
        print("TimeStamp is optional")
      else:
        print("Value not recognised")
        print("Select is the format of the data file: 'XLS' (1) or 'CSV' (2):")
    elif self.step==11:
      if len(Value)>1:
        self.columns=Value
        self.step=12
        print("Select the first row of the file with measurement data (Default 0)")
      else:
        print("Value not recognised")
        print("Suply columns in with measurement values are present: 'setup.select([RealPower,ReactivePower,Timestamp])'")
    elif self.step==12:
      if not Value==None:
        self.firstRow=Value
      self.step=13
      print("Select the last row of the file with measurement data (Default None)")
      print("Using 'None' the algorithm runs untill the end of the data file")
    elif self.step==13:
      self.finalRow=Value
      self.step=14
      print("Select the name of the file with measurement data")
    elif self.step==14:
      if Value==None:
        print("Select the name of the file with measurement data:'setup.select('Name')'")
      else:
        self.system.read(Value,self.columns,self.firstRow,self.fileType,self.finalRow)
        
        
        
        
        

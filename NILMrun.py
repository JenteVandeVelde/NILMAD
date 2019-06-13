from NILM import *
import numpy as np
import math
import warnings
class NILM:
  def __init__():
    self.step=1
    self.edgeDetectionNr=1
    self.edgeDeviationNr=1
    print("This algortihm will aid you in the setup of the NILM algortihm.")
    print("The algortihm will give several existing options, answer using'setup.select(VAUE)'.")
    print("With VALUE being the integer (or sometimes other parameter) representing the selected option.")
    print("Leaving the VALUE emty will result in the algortihm selecting the default option.")
    print("Using a VALUE that does not exist will lead to errors")
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
          
  def select(Value):
    if self.step==1:
      if not Value==None:
        self.edgeDetectionNr=Value
      if Value==7 or Value==8:
        self.step=2
        print("Suply manual devialtion: 'setup.select([RealPowerDeviation,ReactivePowerDeviation]'")
      else:
        self.step=3
        print("Select is the way of calcualting the global deviation:")
        print("1: Weigted average (Default)")
        print("2: Simple average")
    elif self.step==2:
      self.RealPowerDeviation=Value[0]
      self.ReactivePowerDeviation=Value[1]
      self.edgeDeviationNr=0
      self.step=4
    elif self.step==2:
      self.edgeDeviationNr=Value
      self.step=4

from __future__ import print_function
import math
import random
import numpy as np
from simanneal import Annealer
from NILM import *
#inverse of the probability
class SimulatedAnnaelingEstimator(Annealer):
    # pass extra data (NILM information) into the constructor
    def __init__(self, state, NILM):
        self.NILM = NILM
        super(SimulatedAnnaelingEstimator, self).__init__(state)  # important!

    def move(self):
        """Changes Network Estimation"""
        NetworkStateNrLenght=int(2*round(abs(random.randint(0, len(self.NILM.states)-2 )-random.randint(1, len(self.NILM.states)-2))/2))
        NetworkStateNrMid = random.randint(NetworkStateNrLenght/2, len(self.NILM.states)-NetworkStateNrLenght/2-1 )
        NetworkStateNrStart = int(round(NetworkStateNrMid-NetworkStateNrLenght/2))
        NetworkStateNrStop =  int(round(NetworkStateNrMid+NetworkStateNrLenght/2))
        ApplianceNr = random.randint(0, len(self.NILM.appliances)-1)
        ApplianceStateNr=random.randint(0, len(self.NILM.appliances[ApplianceNr].states) - 2)
        if ApplianceStateNr<self.NILM.states[NetworkStateNrMid].applianceStates[ApplianceNr].index:
            for i in range(NetworkStateNrStart,NetworkStateNrStop+1):
                self.state[i][ApplianceNr]=self.NILM.appliances[ApplianceNr].states[ApplianceStateNr]
        else:
            for i in range(NetworkStateNrStart,NetworkStateNrStop+1):
                self.state[i][ApplianceNr]=self.NILM.appliances[ApplianceNr].states[ApplianceStateNr+1]
    #temporary: error
    def energy(self):
        """Inverse likelyhood state"""
        probabilityMeasurement=1
        probabilityAppliance=1
        probabilityDuration=1
        duration=np.zeros(len(self.NILM.appliances))
        states=self.state[0]
        for NetworkStateNr in range(0,len(self.state)):
            currentNetworkState=self.NILM.states[NetworkStateNr]
            realEstimate=self.NILM.groundRealPower()
            reactiveEstimate=self.NILM.groundReactivePower()
            variationReal=currentNetworkState.getRealPowerDeviation()**2/ currentNetworkState.getDuration()
            variationReactive=currentNetworkState.getReactivePowerDeviation()**2/ currentNetworkState.getDuration()
            for stateNr in range(len(self.state[NetworkStateNr])):
                
                if self.state[NetworkStateNr][stateNr].ONstate():
                    variationReal+=self.state[NetworkStateNr][stateNr].getRealPowerDeviation()**2
                    variationReactive+=self.state[NetworkStateNr][stateNr].getReactivePowerDeviation()**2
                    realEstimate+=self.state[NetworkStateNr][stateNr].getRealPower()
                    reactiveEstimate+=self.state[NetworkStateNr][stateNr].getReactivePower()
                    
                if not states[stateNr]==self.state[NetworkStateNr][stateNr]:
                    probabilityDuration*=states[stateNr].probability(duration[stateNr])
                    states[stateNr]=self.state[NetworkStateNr][stateNr]
                    duration[stateNr]=0
                duration[stateNr]+=currentNetworkState.getDuration()
                
            realPowerDifference=currentNetworkState.getRealPower()-realEstimate
            reactivePowerDifference=currentNetworkState.getReactivePower()-reactiveEstimate
            probabilityMeasurement*=scipy.stats.norm(0,math.sqrt(variationReal)).pdf(realPowerDifference)* scipy.stats.norm(0,math.sqrt(variationReactive)).cdf(reactivePowerDifference)
            
        return 1/(probabilityMeasurement*probabilityAppliance*probabilityDuration)
        
        #error=0
        #for NetworkStateNr in range(len(self.state)):
        #    real=0
        #    reactive=0
        #    for state in self.state[NetworkStateNr]:
        #        real += state.realPower
        #        reactive += state.reactivePower
        #    error+= (self.NILM.states[NetworkStateNr].realPower-real)**2+ (self.NILM.states[NetworkStateNr].reactivePower-reactive)**2
        #return error
    
   
        
        
    
   
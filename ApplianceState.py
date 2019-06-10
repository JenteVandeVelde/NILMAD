from Appliance import *
import scipy.stats
import random
import numpy as np
import math

class ApplianceState:
    def __init__(self,realPower,realPowerDeviation,reactivePower,reactivePowerDeviation,applianceCount=0):
        if (realPower==0 and reactivePower == 0):
            self.label='OFF state'
            self.shape=0.01
            self.scale=None
        else:
            self.label='Unknown ON state'
            self.shape=1#k
            self.scale=10#theta
            self.timeProb=[0]*24
            #self.other=[0]
        self.applianceProbabilities=[0,0]*applianceCount
        self.value=[realPower,reactivePower]
        self.deviations=[realPowerDeviation,reactivePowerDeviation]
        self.index=0
        self.applianceIndex=applianceCount
        self.currentDuration=0
        # print "New state " + str(self.index) +" lasting " + str(self.duration) +" s."
    
    def copy(self):
        applianceState=ApplianceState(self.getRealPower(), self.getRealPowerDeviation(), self.getReactivePower(), self.getReactivePowerDeviation())
        applianceState.label=self.label
        applianceState.shape=self.shape
        applianceState.scale=self.scale
        if self.ONstate():
            for timePro in self.timeProb:
                applianceState.timeProb.append(timePro)
        for applianceProbability in self.applianceProbabilities:
            applianceState.applianceProbabilities.append(applianceProbability)
        applianceState.index=self.index
        applianceState.currentDuration=self.currentDuration
        applianceState.applianceIndex=self.applianceIndex
        return applianceState
    def negativeCopy(self):
        applianceState=self.copy()
        applianceState.addRealPower(-2*applianceState.getRealPower())
        applianceState.addReactivePower(-2*applianceState.getReactivePower())
        return applianceState
    def addAppliance(self):
        self.applianceProbabilities.append([0,0])
    
    def removeAppliance(self,applianceIndex):
        self.applianceProbabilities.pop(applianceIndex)
        if self.applianceIndex>applianceIndex:
            self.applianceIndex-=1
    
    def ONstate(self):
        return not self.scale==None
    
    def getPower(self):
        return self.value
    
    def getRealPower(self):
        return self.getPower()[0]
    
    def getReactivePower(self):
        return self.getPower()[1]
    
    def getDeviation(self):
        return self.deviations
    
    def getRealPowerDeviation(self):
        return self.getDeviation()[0]
    
    def getReactivePowerDeviation(self):
        return self.getDeviation()[1]
    
    def setRealPowerDeviation(self,value):
        self.deviations[0]=value
    
    def setReactivePowerDeviation(self,value):
        self.deviations[1]=value
    
    def getIndex(self):
        return self.index
    
    def getIndexAppliance(self):
        return self.applianceIndex
    
    def addDuration(self,duration):
        self.currentDuration+=duration
    
    def resetDuration(self):
        self.currentDuration=0
                
    def getCurrentDuration(self):
        return abs(self.currentDuration)
    
    def on(self):
        return self.currentDuration>0
    
    def addRealPower(self,amount):
        self.value[0]+=amount
    
    def addReactivePower(self,amount):
        self.value[1]+=amount
        
    def addPower(self,power):
        self.addRealPower(power[0])
        self.addReactivePower(power[1])
    
    def addRealPowerDeviation(self,amount):
        self.setRealPowerDeviation(math.sqrt(abs(self.getRealPowerDeviation()**2 + (amount**2)*np.sign(amount))))
    def combineRealPowerDeviation(self,amount):
        self.setRealPowerDeviation(math.sqrt(2*min(self.getRealPowerDeviation()**2 ,amount**2)))
    
    def addReactivePowerDeviation(self,amount):
        self.setReactivePowerDeviation(math.sqrt(abs(self.getReactivePowerDeviation()**2 + (amount**2)*np.sign(amount))))
    def combineReactivePowerDeviation(self,amount):
        self.setReactivePowerDeviation(math.sqrt(2*min(self.getReactivePowerDeviation()**2 ,amount**2)))
    def addDeviation(self,power):
        self.addRealPowerDeviation(abs(power[0]))
        self.addReactivePowerDeviation(abs(power[1]))
    def combineDeviation(self,power):
        self.combineRealPowerDeviation(abs(power[0]))
        self.combineReactivePowerDeviation(abs(power[1]))
    
    #def substractDeviation(self,power):
    #    self.addRealPowerDeviation(-power[0])
    #    self.addReactivePowerDeviation(-power[1])
    
    def setTimeProbabilities(self,timeProbabilities):
        self.timeProb=timeProbabilities
    def setApplianceProbabilities(self,applianceProbabilities):
        self.applianceProbabilities=applianceProbabilities
    def fit(self,durations):
        if self.scale == None:
            durations=[duration for duration in durations if duration <30000]
            if len(durations)>5:
                best=self.shape
                current=best
                bestProb=1
                for duration in durations:
                        bestProb*=scipy.stats.geom.pmf(duration,best)
                for i in range(10):
                    currentPos=(10+random.random()*(10-i))/20
                    posProb=1
                    currentNeg=current/currentPos
                    negProb=1
                    currentPos=current*current
                    
                    for duration in durations:
                        posProb*=scipy.stats.geom.pmf(duration,currentPos)
                        negProb*=scipy.stats.geom.pmf(duration,currentNeg)
                    if posProb>negProb:
                        current=(current+currentPos)/2
                        if posProb>bestProb:
                            best=currentPos
                    else:
                        current=(current+currentNeg)/2
                        if negProb>bestProb:
                            best=currentNeg
                self.shape=best
                #print "Shape " + str(self.shape)
        else:
            if len(durations)>5:
                s=np.log(sum(durations)/len(durations))-sum([np.log(duration) for duration in durations])/len(durations)
                                                            
                self.shape=(3-s+math.sqrt(max((s-3)**3+24*s,0)))/(12*s)
                self.scale=sum(durations)/(len(durations)*self.shape)
                #print "Shape "+str(self.shape)+" and scale "+str(self.scale)
    
    def probability(self,duration):
        if self.ONstate():
            return scipy.stats.gamma.pdf(duration,self.shape,0,self.scale)
        else:
            if duration <=30000:
                return scipy.stats.geom.pmf(duration,self.shape)
            else:
                return 1
        
    def probabilityChange(self,duration):
        currentDuration=self.getCurrentDuration()
        if self.ONstate():
            return (scipy.stats.gamma.cdf(currentDuration+duration,self.shape,0,self.scale)/ scipy.stats.gamma.cdf(currentDuration,self.shape,0,self.scale))-1
        else:
            return (scipy.stats.geom.cdf(currentDuration+duration,self.shape)/ scipy.stats.geom.cdf(currentDuration,self.shape))-1

    def probabilityNoChange(self,duration):
        currentDuration=self.getCurrentDuration()
        if self.ONstate():
            return (1-scipy.stats.gamma.cdf(currentDuration+duration,self.shape,0,self.scale)) /scipy.stats.gamma.cdf(currentDuration,self.shape,0,self.scale)
        else:
            return (1-scipy.stats.geom.cdf(currentDuration+duration,self.shape))/ scipy.stats.geom.cdf(currentDuration,self.shape)

    
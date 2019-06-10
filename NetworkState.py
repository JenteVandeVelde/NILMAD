from NILM import *
from ApplianceState import *
import scipy.stats

class NetworkState:
    def __init__(self,NILM,averageValues,deviations,indexStart,indexEnd,day=None,intitialValues=None,endValues=None,anomalyCount=0,anomaly=None):
        self.value=averageValues
        self.startValue=intitialValues
        self.stopValue=endValues
        self.deviations=deviations
        
        self.timeIndex=indexStart #mod amount of indexes in a single day (yet to be implemented!)
        if indexEnd>indexStart:
            self.duration=indexEnd-indexStart
        else:
            self.duration=24*60*60+indexEnd-indexStart
        self.day=day
        if day==None:
            self.day=NILM.day
        self.index=NILM.indexStates
        self.anomalyCount=anomalyCount
        [hours,minutes,seconds]=self.getStartTimeArray()
        self.anomalies=[]
        if not anomaly==None:
            self.anomalies.append(anomaly)
            print "Anomalous State with real power: "+ '{:7.2f}'.format(self.value[0]) + ", "+'{:7.2f}'.format(self.deviations[0])+" and reactive power: "+ '{:6.2f}'.format(self.value[1]) + ", "+'{:7.2f}'.format(self.deviations[1]) + " At: " + str(hours)+":"+str(minutes)+":"+str(seconds)+" For: " + str(self.duration-anomalyCount)
        else:
            print "State with real power: "+ '{:7.2f}'.format(self.value[0]) + ", "+'{:7.2f}'.format(self.deviations[0])+" and reactive power: "+ '{:6.2f}'.format(self.value[1]) + ", "+'{:7.2f}'.format(self.deviations[1]) + " At: " + str(hours)+":"+str(minutes)+":"+str(seconds)+" For: " + str(self.duration-anomalyCount)
        self.applianceStates=[]
        NILM.addNetworkState(self)
        #print "New state " + str(self.index) +" lasting " + str(self.duration) +" s."
    def getApplianceStates(self):
        return self.applianceStates
    def getApplianceState(self,applianceNr):
        return self.getApplianceStates()[applianceNr]
    def isApplianceState(self,applianceState):
        try:
            return self.getApplianceState(applianceState.getIndexAppliance())==applianceState
        except IndexError:
            return False
    def remainders(self,ApplianceNrs=[]):
        [real, reactive]=self.estimate(ApplianceNrs)        
        return [self.getRealPower()-real,self.getReactivePower()-reactive]
    def remaindersDifference(self,networkstate,ApplianceNrs=[]):
        [ereal, ereactive]=self.estimatedDifference(networkstate,ApplianceNrs)
        [real, reactive]=self.getDifference(networkstate)
        return [real-ereal,reactive-ereactive]
    def getDifference(self,networkstate):
        real=self.getStartRealPower() - networkstate.getStopRealPower()
        reactive=self.getStartReactivePower() - networkstate.getStopReactivePower()
        return  [real,reactive]
    def estimate(self,ApplianceNrs=[]):
        real=0
        reactive=0
        for state in self.applianceStates:
            if not state.getIndex() in ApplianceNrs:
                real += state.getRealPower()
                reactive += state.getReactivePower()
        return [real,reactive]
    def estimatedDifference(self,networkstate,ApplianceNrs=[]):
        real=0
        reactive=0
        for stateNr in range(len(self.getApplianceStates())):
            if not stateNr in ApplianceNrs and not self.isAnomaly("MissedEdge"+str(stateNr)):
                real += self.getApplianceState(stateNr).getRealPower()-networkstate.getApplianceState(stateNr).getRealPower()
                reactive += self.getApplianceState(stateNr).getReactivePower()-networkstate.getApplianceState(stateNr).getReactivePower()
        return [real,reactive]
        

    def applianceCount(self,ApplianceNrs=[]):
        count=0
        for state in self.getApplianceStates():
            if not state.getIndexAppliance() in ApplianceNrs:
                if not state.getRealPower() == 0:
                    count+=1
        return count
    
    def setAnomaly(self,newAnomaly):
        for anomaly in self.anomalies:
            if anomaly==newAnomaly:
                return False
        self.anomalies.append(newAnomaly)
        return True
    def applianceCountDifference(self,networkState,ApplianceNrs=[]):
        if self== networkState:
            count=self.applianceCount(ApplianceNrs)
        else:
            count=0
            for stateNr in range(len(self.getApplianceStates())):
                if not stateNr in ApplianceNrs:
                    if not self.getApplianceState(stateNr).getRealPower() == networkState.getApplianceState(stateNr).getRealPower():
                        count+=1
        return count
    def removeAnomaly(self,oldAnomaly):
        found=0
        for anomaly in self.anomalies:
            if anomaly[0:(len(oldAnomaly))] == oldAnomaly:
                self.anomalies.remove(anomaly)
                found+=1
        return found
    
    def getValues(self):
        return self.value
    
    def getRealPower(self):
        return self.getValues()[0]
    
    def getReactivePower(self):
        return self.getValues()[1]
    
    def getStartValues(self):
        if not self.startValue==None:
            return self.startValue
        else:
            return self.getValues()
    
    def getStartRealPower(self):
        return self.getStartValues()[0]
    
    def getStartReactivePower(self):
        return self.getStartValues()[1]
    
    def getStopValues(self):
        if not self.stopValue==None:
            return self.stopValue
        else:
            return self.getValues()
            print"No stopValue"
    
    def getStopRealPower(self):
        return self.getStopValues()[0]
    
    def getStopReactivePower(self):
        return self.getStopValues()[1]
    
    def getDeviation(self):
        return self.deviations
    
    def getRealPowerDeviation(self):
        return self.getDeviation()[0]
    
    def getReactivePowerDeviation(self):
        return self.getDeviation()[1]
    
    def getTotalVariation(self,ApplianceNrs=[]):
        variationReal=self.getRealPowerDeviation()**2/self.getDuration()
        variationReactive=self.getReactivePowerDeviation()**2/self.getDuration()
        
        for applianceState in self.applianceStates:
            if applianceState.ONstate() and not applianceState.getIndexAppliance() in ApplianceNrs:
                variationReal+=applianceState.getRealPowerDeviation()**2
                variationReactive+=applianceState.getReactivePowerDeviation()**2
        return [variationReal,variationReactive]
    def getTotalVariationDifference(self,networkstate,ApplianceNrs=[]):
        variationReal=self.getRealPowerDeviation()**2/self.getDuration()
        variationReactive=self.getReactivePowerDeviation()**2/self.getDuration()
        variationReal+=networkstate.getRealPowerDeviation()**2/networkstate.getDuration()
        variationReactive+=networkstate.getReactivePowerDeviation()**2/networkstate.getDuration()
        for stateNr in range(len(self.getApplianceStates())):
            if not stateNr in ApplianceNrs and not self.isAnomaly("MissedEdge"+str(stateNr)):
                variationReal += (self.getApplianceState(stateNr).getRealPowerDeviation()- networkstate.getApplianceState(stateNr).getRealPowerDeviation())**2
                variationReactive += (self.getApplianceState(stateNr).getReactivePowerDeviation()- networkstate.getApplianceState(stateNr).getReactivePowerDeviation())**2
        return [variationReal,variationReactive]
    def getDay(self):
        return self.day
    
    def getStartTime(self):
        return self.timeIndex
    
    def getStartDayTime(self):
        return (self.getDay() - 25569) * 86400.0+self.getStartTime()
    
    def getStopTime(self):
        return self.getStartTime()+self.getDuration()
    
    def getStartTimeArrayFull(self):
        seconds = self.getStartTime()
        minutes=0
        if not seconds == 0:
            minutes = (round(seconds/60-0.5))
            seconds=(round(seconds-minutes*60))
        hours=0
        if not minutes == 0:
            hours= (round(minutes/60-0.5))
            minutes=minutes-hours*60
        days=0
        if not hours == 0:
            days=int(round(hours/24-0.5))
            hours=hours-days*24
        return [int(days),int(hours),int(minutes),int(seconds)]
    
    def printStr(self):
        [hours,minutes,seconds]=self.getStartTimeArray()
        string = "Time: " + '{:2d}'.format(hours)+":"+'{:2d}'.format(minutes)+":"+'{:2d}'.format(seconds)
        string += " Power:"+'{:8.2f}'.format(self.getRealPower())+"; "+'{:8.2f}'.format(self.getReactivePower())
        for anomaly in self.getAnomalies():
            string+= " " + anomaly
        return string
        
    def getStopTimeArrayFull(self):
        seconds = self.getStartTime()
        minutes=0
        if not seconds == 0:
            minutes = (round(seconds/60-0.5))
            seconds=(round(seconds-minutes*60))
        hours=0
        if not minutes == 0:
            hours= (round(minutes/60-0.5))
            minutes=minutes-hours*60
        days=0
        if not hours == 0:
            days=int(round(hours/24-0.5))
            hours=hours-days*24
        return [int(days),int(hours),int(minutes),int(seconds)]
    
    def getStartTimeArray(self):
        [days,hours,minutes,seconds]=self.getStartTimeArrayFull()
        return [hours,minutes,seconds]
    
    def getStopTimeArray(self):
        [days,hours,minutes,seconds]=self.getStartTimeArrayFull()
        return [hours,minutes,seconds]
    
    def getDuration(self):
        return self.duration
    
    def isAnomaly(self,anomalyType=None):
        if anomalyType==None:
            return not len(self.getAnomalies())==0
        else:
            for anomaly in self.getAnomalies():
                if anomaly[0:len(anomalyType)] == anomalyType:
                    return True
            return False
    
    def getAnomalies(self):
        return self.anomalies
    def getIndex(self):
        return self.index
    def probabilityMeasurement(self,realPowerDifference=None,reactivePowerDifference=None):
        if realPowerDifference==None or reactivePowerDifference==None:
            [realPowerDifference,reactivePowerDifference]=self.remainders()
        [variationReal,variationReactive]=self.getTotalVariation()
        #return 4*scipy.stats.norm(0,math.sqrt(variationReal)).cdf(-abs(realPowerDifference))* scipy.stats.norm(0,math.sqrt(variationReactive)).cdf(-abs(reactivePowerDifference))
        return scipy.stats.norm(0,math.sqrt(variationReal)).pdf(realPowerDifference)* scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(reactivePowerDifference)
    
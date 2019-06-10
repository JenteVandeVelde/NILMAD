from ApplianceState import *

class Appliance:
    def __init__(self,NILM,groundState,applianceState,index):
        self.name='Unknown appliance'
        self.states=[]
        self.stateAmount=0
        
        self.NILM=NILM
        self.index=index
        self.addApplianceState(groundState)
        self.addApplianceState(applianceState)
        # print "New state " + str(self.index) +" lasting " + str(self.duration) +" s."

    def addApplianceState(self,applianceState):
        added=False
        for i in range(len(self.getStates())+1):
            if i ==len(self.getStates()) and not added:
                applianceState.index=i
                applianceState.applianceIndex=self.getIndex()
                self.states.append(applianceState)
            elif applianceState.getRealPower()<self.getState(i).getRealPower():
                if not added:
                    applianceState.index=i
                    applianceState.applianceIndex=self.getIndex()
                    self.states.insert(i,applianceState)
                    added=True
                else:
                    self.getState(i).index+=1
        self.stateAmount+=1
    
    def addState(self,realPower,realPowerDeviation,reactivePower,reactivePowerDeviation):
        state=ApplianceState(self,realPower,realPowerDeviation,reactivePower,reactivePowerDeviation)
        self.addApplianceState(state)
    
    def addAppliance(self):
        for applianceState in self.states:
            applianceState.addAppliance()
    
    def removeAppliance(self, applianceIndex):
        if self.index>applianceIndex:
            self.index-=1
            for applianceState in self.states:
                applianceState.removeAppliance(applianceIndex)
        elif self.index<applianceIndex:
            for applianceState in self.states:
                applianceState.removeAppliance(applianceIndex-1)
    
    def addDuration(self,applianceState,duration):
        for state in self.states:
            if state==applianceState:
                state.addDuration(duration)
            else:
                state.resetDuration()
    
    def removeApplianceState(self,applianceStateNr):
        #print "Remove state " +str(applianceStateNr)+" of "+str(self.stateAmount)
        if self.stateAmount<=2:
            self.NILM.removeAppliance(self.index)
            applianceState=self.states.pop(applianceStateNr)
        else:
            applianceState=self.states.pop(applianceStateNr)
            for state in self.states:
                if state.index>applianceStateNr:
                    state.index-=1
            self.stateAmount-=1
        return applianceState
    
    def getIndex(self):
        return self.index
    
    def getStates(self):
        return self.states
    
    def getState(self,stateNr):
        return self.getStates()[stateNr]
from NILM import *
class DataPoint:
    def __init__(self,values,index):
        self.value=values
        self.index=index
        self.edge=False
        
    def getValues(self):
        return self.value
    
    def getRealPower(self):
        return self.getValues()[0]
    
    def getReactivePower(self):
        return self.getValues()[1]
    
    def getDay(self):
        return round(self.getDayTime()+0.5)-1
    
    def getTime(self):
        if len(self.getValues())>2:
            return round((self.getDayTime()-self.getDay())*24*60*60)
        else:
            return 0
    def getDayTime(self):
        if len(self.getValues())>2:
            return self.getValues()[len(self.getValues())-1]
        else:
            return 0
    def getIndex(self):
        return self.index
        
    def getEdge(self):
        return self.edge
    
    def setEdge(self):
        self.edge=True
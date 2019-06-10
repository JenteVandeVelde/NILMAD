#Imports
from __future__ import division
from DataPoint import *
from NetworkState import *
from Appliance import *
from ApplianceState import *
from SimulatedAnnaelingEstimator import *
import math
import numpy as np
import heapq as hp
import matplotlib.pyplot as plt
import scipy.stats
import csv
import datetime
from xlrd import open_workbook

from sklearn.cluster import *
from sklearn.preprocessing import StandardScaler
from sklearn import metrics


class NILM:
    #Initializes all global parameters:
    # indexData: The timestamp used if none present in the data file
    # dataWindow: The buffer in wich individual DataPoints are temporarely stored
    # total: the sum of all values in dataWindow
    # deviation: [4] deviation calculated from all known network states
    #    - average real power deviation
    #    - average reactive power deviation
    #    - number of network states considered for calculation deviation
    #    - number of data points considered for calculation deviation
    # ground: [3] power reading when no appliance is enabled
    #    - average real power
    #    - average reactive power
    #    - number of data points considered for calculation ground
    # indexstates: amount of network states
    # states: array containing all NetworkStates
    # appliances: array containing all appliances
    # filtersize: size of medianFilter
    # minstatePoints: minimum amount of datapoints required to from a networl state (in practice: minStatePoints+filterSize)
    # count internal counter used to limit excessive searching for new appliances (allow for new data to gather)
    # plotFirstNetworkStateAmount: If the number of networkstates is a multiple of this number, a plot is generated
    # allowedDeviation: the deviation allowed for a state to be considered completely assigned
    #Edge detection algortihm used:
    # 1: Deviation from temporary data 
    # 2: Deviation from previously identified data (uses 1 when few data yet collected)
    
    #Edge detection algortihm used for anomaly detection:
    # 1: Deviation from temporary data 
    # 2: Deviation from previously identified data (uses 1 when few data yet collected)

    #Edge detection algortihm used for calculating deviation (edge detection 2):
    # 1: Statistical average
    # 2: Simple average

    #Check whether or not a new appliace can be identified
    # 1: DBSCAN: Cluster network states (remainder)
    # 2: DBSCAN: Cluster difference between consecutive network states
    # 3: K-Means: Cluster network states (remainder)
    
    #Update All appliances
    
    #Estimates for the given (or all if no state is given) network state(s) the appliance state of each appliance 
    #1: Allows but one state change at any given moment 
    
    
    def __init__(self, filterSize=3, minStatePoints=4, edgeDetectionNr=2,ground=None, edgeAnomalyNr=1, edgeDeviationNr=1, preClusterNr=3, optimizeClusterNr=1, optimizeStateNr=1):
        self.indexData=0
        self.dataWindow=[] #data window to execute edge detection
        self.dataAnomalies=[]
        self.total=None #sum of data in window, automaticly addapts to amount of values in dataPoint
        self.weightedAverage=None #sum of data in window, automaticly addapts to amount of values in dataPoint
        self.initialDeviation=[8,4]
        self.deviation=[None,None,0,0] #average deviation (real and reactive measurement) if calculated over total past and amount of point used in its calculation
        if ground==None:
            self.ground=[None,None,0] #average value of unrecognised states (real and reactive measurement) if calculated over total past and amount of point used in its calculation
        else:
            self.ground=ground
        self.indexStates=0
        self.states=[]
        self.appliances=[]
        self.filterSize=filterSize
        self.minStatePoints=minStatePoints
        self.count=0
        self.countNewAppliance=0
        self.plotFirstNetworkStateAmount=50
        self.allowedDeviation=0
        self.algorithmEdgeDetection=edgeDetectionNr
        self.algorithmEdgeDeviation=edgeDeviationNr
        self.algorithmEdgeAnomaly=edgeAnomalyNr
        self.algorithmEstimate=optimizeStateNr
        self.algorithmEstimateFull=2
        self.algorithmNewAppliance=preClusterNr
        self.algorithmUpdate=optimizeClusterNr
        self.day=0
        self.printFile=open("printLog.txt","w")
        self.printFileAnomalies=open("anomalyLog.txt","w")
        self.printEdgeFile=self.printFile
    
    #resets NILM to its initial values
    def reset(self):
        self.indexData=0
        self.dataWindow=[] #data window to execute edge detection
        self.dataAnomalies=[]
        self.total=None #average of data in window, automaticly addapts to amount of values in dataPoint
        self.deviation=[None,None,0,0] #average deviation (real and reactive measurement) if calculated over total past and amount of point used in calculation
        if len(self.ground)>2:
            self.ground=[None,None,0]
        self.indexStates=0
        self.states=[]
        self.appliances=[]
        self.count=0
        self.allowedDeviation=0
    
    # Depriciated method to iterate over the read-file to improve the deviation estimation.
        # Does not stich data togheter: resets known data between iterations
        # Possible to improve by optimising this rest function (exaple NOT remove appliances)
        # But influence on other algorithms has to be checked
    # - name:Name of the file to be read (has to be located in the same location as this programm)
    # - colums: The colums in the file in wich the required data is stored [realPowerColumn, reactivePowerColumn]
    # - textRowNr: The amount of rows that do NOT contain data at the top of the file
    # - fileType: 'CSV' or 'XLS'
    # - end: can be used to limit the amount of rows to be read
    # - number: The amaunt of time the fie is iterated over
    def iterate(self,name,columns,TextRowNr=1,FileType='CSV',end=None,number=1):
        for nr in range(number):
            self.read(name,columns,TextRowNr,FileType,end)
            deviation=[self.deviation[0],self.deviation[1],self.deviation[2]/2,self.deviation[3]/2]
            self.reset()
            self.deviation=deviation
            print str(nr)
        return True
    
    # Method used to read extrnal file
    # Reads a single row and creates a DataPoint with data from the selected colums.
    # The creation of a DataPoint will trigger the addDataPoint method below
    # - name:Name of the file to be read (has to be located in the same location as this programm)
    # - colums: The colums in the file in wich the required data is stored [realPowerColumn, reactivePowerColumn]
    # - textRowNr: The amount of rows that do NOT contain data at the top of the file
    # - fileType: 'CSV' or 'XLS'
    # - end: can be used to limit the amount of rows to be read
    def read(self,name,columns,textRowNr=0,fileType='CSV',end=None):
        self.printEdgeFile=open(name+".txt","w")
        if fileType=='CSV':
            with open(name,'rb') as csvfile:
                dialect = csv.Sniffer().sniff(csvfile.read(1024))
                csvfile.seek(0)
                reader = csv.reader(csvfile, dialect)
                rowId=0
                for row in reader:
                    if rowId>=textRowNr:
                        dataPoint=DataPoint([float(row[columns[i]]) for i in range(len(columns))],self.indexData)
                        self.addDataPoint(dataPoint)
                    rowId+=1
                    if not end == None:
                        if (rowId>=end):
                            #self.printFile.close()
                            self.printEdgeFile.close()
                            print "Target value reached"
                            return True
                self.plotNetworkStates()
                self.plotNetworkStatesAdditive()
                
                self.plotNetworkStatesAdditiveBlank()
                #self.printFile.close()
                self.printEdgeFile.close()
                print "Reading file completed"
                return False
        elif fileType=='XLS':
            wb = open_workbook(name)
            for sheet in wb.sheets():
                number_of_rows = sheet.nrows
                for row in range(textRowNr, number_of_rows):
                    dataPoint=None
                    try:
                        values=[]
                        for col in columns:
                            values.append(float(sheet.cell(row,col).value ))
                        dataPoint=DataPoint(values,self.indexData)
                        
                    except ValueError:
                        pass
                    finally:
                        if not end == None:
                            if (rowId>=end):
                                self.addDataPoint(dataPoint)
                                #self.printFile.close()
                                self.printEdgeFile.close()
                                print "Target value reached"
                                return True
                    #datePointd default None will result in the ignoring of the current row
                    self.addDataPoint(dataPoint)
                textRowNr=0
            self.plotNetworkStates()
            self.plotNetworkStatesAdditive()
            self.plotNetworkStatesAdditiveBlank()
            #self.printFile.close()
            self.printEdgeFile.close()
            print "Reading file completed"
            return False
        else:
            #self.printFile.close()
            self.printEdgeFile.close()
            print "FileType not recognised"
    
    #export supplied string to dedicated print file
    def write(self,string):
        self.printFile.write(string+"\n")
        
    # Method used to add a DataPoint to the dataWindow 
    # Uses edge detection algortihm and creates Network state IF this algorithm return a possitive result 
    def addDataPoint(self,dataPoint):
        # Negate empty rows
        if dataPoint==None:
            return False
        # determine the date of the last data processes
        if self.day < dataPoint.getDay():
            self.day=dataPoint.getDay()
            print  datetime.datetime.utcfromtimestamp((self.day - 25569) * 86400.0).strftime('%Y-%m-%d') +" being processed."
        # Save new DataPoint to buffer
        self.dataWindow.append(dataPoint)
        # Update total (used to calculate ALL averages) (last value: Time is ignored)
        if (self.total==None):
            self.total=[dataPoint.value[i] for i in range(max(2,len(dataPoint.value)-1))]
        else:
            self.total=[dataPoint.value[i]+self.total[i] for i in range(max(2,len(dataPoint.value)-1))]
        # Update weigted average (used to calculate ALL averages) (last value: Time is ignored)
        if (self.weightedAverage==None):
            self.weightedAverage=[dataPoint.value[i] for i in range(max(2,len(dataPoint.value)-1))]
        else:
            self.weightedAverage=[(dataPoint.value[i]+self.weightedAverage[i])/2 for i in range(max(2,len(dataPoint.value)-1))]
        # update index DataPoints
        self.indexData+=1
        # trigger edge detection and save result
        edgePosition=self.edgeDetection(dataPoint.getIndex())
        
        #edgePosition will only be 0 when edgeDetection is disabled: each DataPOint becomes seperate NetworkState (not advised)
        if edgePosition==0:
            timeStart=dataPoint.getIndex()
            if not dataPoint.getDay()==0:
                timeStart=dataPoint.getTime()
            print "NO edgeDetection!"
            self.dataWindow=[]
            NetworkState(self,[dataPoint.getRealPower(),dataPoint.getReactivePower()], [0,0], timeStart, timeStart+1)
        else:
            
            indexDataStart=self.dataWindow[0].getIndex()
            indexDayStart=25569
            #print "From " +str(indexDataStart) + " at " + str(edgePosition) + " to " + str(self.indexData) + "."#edgePosition is calculated relative to dataStart
            if edgePosition+indexDataStart<=dataPoint.getIndex():#edge has been detected
                #print "From " +str(indexDataStart) + " for " + str(edgePosition) + "."
                if not dataPoint.getDay()==0:
                    indexDataStart=self.dataWindow[0].getTime()
                    indexDayStart=self.dataWindow[0].getDay()
                tempData=[]
                for i in range(0,edgePosition):
                    tempData.append(self.dataWindow.pop(0))
                anomalyCount=0
                
                [noTransData,anomalyCount]=self.anomalyFilter(tempData,0.0005,False,0)
                dataListNT=np.array(noTransData).T.tolist()
                [tempData,anomalyCount]=self.anomalyFilter(tempData,0.02)
                dataList=np.array(tempData).T.tolist()
                if len(tempData)>=self.minStatePoints:
                    averages=[np.average(dataList[i]) for i in range(len(dataList))]
                    deviations=[np.std(dataList[i]) for i in range(len(dataList))]
                    if len(self.ground)>2:
                        self.updateGround(averages[0],averages[1],len(dataList[0]))
                    self.updateDeviation(deviations[0],deviations[1],len(dataList[0]))
                    #print str(self.deviationRealPower())
                    indexDataStop=self.dataWindow[0].getIndex()
                    if not dataPoint.getDay()==0:
                        indexDataStop=self.dataWindow[0].getTime()
                    startValues  = noTransData[0]
                    stopValues  = noTransData[len(noTransData)-1]
                    avereagingPoints=max(min(8,int(len(dataList[i])/2)-1),2)
                    #if avereagingPoints>8:
                    #    print "WHATH"
                    startValues=[np.average(dataListNT[i][4:avereagingPoints+4]) for i in range(len(dataListNT))]
                    stopValues=[np.average(dataListNT[i][(len(dataListNT[i])-avereagingPoints):len(dataListNT[i])]) for i in range(len(dataList))]
                    anomaly=None
                    if averages[0]>4000:
                        anomaly="OutOfBounds"
                    self.printEdgeFile.write('\n'+datetime.datetime.utcfromtimestamp((indexDayStart - 25569) * 86400.0+indexDataStart).strftime('%d/%m/%Y %H:%M:%S'))
                    NetworkState(self, averages,deviations, indexDataStart,indexDataStop, indexDayStart,startValues,stopValues, anomalyCount,anomaly)
                        
                    
                #else:
                 #   print "Anomalous State"
                self.total=[self.dataWindow[0].value[i] for i in range(max(2,len(self.dataWindow[0].value)-1))]
                self.weightedAverage=self.total
                for dataPointNr in range(1,len(self.dataWindow)):
                    self.total=[self.dataWindow[dataPointNr].value[i]+self.total[i] for i in range(max(2,len(dataPoint.value)-1))]
                    self.weightedAverage=[(self.dataWindow[dataPointNr].value[i]+self.weightedAverage[i])/2 for i in range(max(2,len(dataPoint.value)-1))]
                for dataPointN in self.dataWindow:
                    dataPointN.edge=False
         
    #return the average values for the DataPoints in the buffer         
    def average(self):
        return [value/(len(self.dataWindow)-1) for value in self.total]
    
    #return the average real power for the DataPoints in the buffer 
    def averageRealPower(self):
        return self.average()[0]
    
    #return the average reactive power for the DataPoints in the buffer 
    def averageReactivePower(self):
        return self.average()[1]  
    
    #Edge detection algortihm used:
# 1: Deviation from temporary data 
# 2: Deviation from previously identified data (uses 1 when few data yet collected)
# 3: Deviation from previously identified data (uses fixed deviation when few data yet collected)
    def edgeDetection(self,index,algorithm=None):
        if algorithm==None:
            algorithm=self.algorithmEdgeDetection
        if (algorithm==1):
            return self.edgeDetection_1(index)
        elif (algorithm==2):
            if self.deviation[0] == None:
                return self.edgeDetection_1(index)
            else:
                return self.edgeDetection_2(index)
        elif (algorithm==3):
            if len(self.states)=<100:
                return self.edgeDetection_3(index)
            else:
                return self.edgeDetection_2(index)
        elif (algorithm==4):
            return self.edgeDetection_4(index)
        elif (algorithm==5):
            return self.edgeDetection_5(index)
        else:
            return 0
        
    #r return real and reactive power of a DataPoint after a median filter is used
    # - index: possition in the databuffer of the DataPoint to be processed
    def medianFilter(self,index=None):
        if index==None:
            index=self.getDataPoint(None).getIndex()
        realPower=self.getDataPoint(index).getRealPower()
        reactivePower=self.getDataPoint(index).getReactivePower()
        if self.filterSize>1:
            numbersP=[]
            numbersQ=[]
            for i in range(self.filterSize):
                numbersP.append(self.getDataPoint(index-i).getRealPower())
                numbersQ.append(self.getDataPoint(index-i).getReactivePower())
            realPower=np.median(numbersP)
            reactivePower=np.median(numbersQ)
        return [realPower,reactivePower]
    
    # Deviation calculated as average deviation data in window
    def edgeDetection_1(self,index):
        #PRIMARY EDGE DETECTION
        
        #minAmount of points?
        if self.getDataWindowLenght()>=max(self.filterSize,self.minStatePoints):
            #Estimate of deviation in data window
            standartDeviation=(sum((dataPoint.getRealPower()-self.averageRealPower())**2 for dataPoint in self.dataWindow)+sum((dataPoint.getReactivePower()-self.averageReactivePower())**2 for dataPoint in self.dataWindow))/(self.getDataWindowLenght()*2)
            #Median Filter
            [realPower,reactivePower]=self.medianFilter(index)
            #large/unlikely difference
            if (scipy.stats.norm(self.averageRealPower(), math.sqrt(standartDeviation)).pdf(realPower) * scipy.stats.norm(self.averageReactivePower(), math.sqrt(standartDeviation)).pdf(reactivePower))<.0001:
                self.getDataPoint().setEdge()
        
        return self.edgeDetectionttest()
    
    def edgeDetectionttest(self):
        if(self.getDataWindowLenght()>=2*self.minStatePoints+max(self.filterSize,self.minStatePoints)):
            if(self.dataWindow[self.getDataWindowLenght()-1-self.minStatePoints].getEdge()):
                pMin=1
                pIndex=0
                for i in range(max(self.filterSize,self.minStatePoints)):
                    p=ttest(self.getDataWindow(),self.getDataWindowLenght()-self.minStatePoints-i)
                    if (p<pMin):
                        pMin=p
                        pIndex=i
                if pMin<0.0001:#insesitivity edge detection (larger= less sensitive trigger)
                    return self.getDataWindowLenght()-self.minStatePoints-pIndex
                if not self.day == 0:
                    time=self.dataWindow[self.getDataWindowLenght()-1-self.minStatePoints].getTime()
                    print "no edge detected at" + datetime.datetime.utcfromtimestamp(time).strftime("%H:%M:%S") +" With " + str(pMin)
        return self.getDataWindowLenght()
    
    # Deviation calculated as average deviation previous network states
    def edgeDetection_2(self,index):
        #print str(self.getDataWindowLenght()) + str(self.filterSize) + str(self.minStatePoints)
        if self.getDataWindowLenght()>=max(self.filterSize,self.minStatePoints):
            #Median Filter
            [realPower,reactivePower]=self.medianFilter(index)
            #print str(self.getDataWindowLenght()) +">"+ str(self.deviationWeight())
            if self.getDataWindowLenght()>self.deviationWeight():
                #print "ok"
                standartDeviationReal=sum((dataPoint.getRealPower()-self.averageRealPower())**2 for dataPoint in self.dataWindow)/self.getDataWindowLenght()
                standartDeviationReactive=sum((dataPoint.getReactivePower()-self.averageReactivePower())**2 for dataPoint in self.dataWindow)/self.getDataWindowLenght()
                if (scipy.stats.norm(self.averageRealPower(), math.sqrt(standartDeviationReal)).pdf(realPower) * scipy.stats.norm(self.averageReactivePower(), math.sqrt(standartDeviationReactive)).pdf(reactivePower))<.0001:
                    self.getDataPoint().edge=True
                #print "edge detected at " + str(data[len(data)-1].index)
            else:
                #print str(self.deviationRealPower())+str(self.deviationWeight())
                if (scipy.stats.norm(self.averageRealPower(), self.deviationRealPower()).pdf(realPower) * scipy.stats.norm(self.averageReactivePower(),  self.deviationReactivePower()).pdf(reactivePower))<.0007:
                    self.getDataPoint().setEdge()
                    #print "Cumulative " + str(scipy.stats.norm(0,self.deviationRealPower()).cdf(-abs(np.median(numbersP)-self.averageRealPower())) * scipy.stats.norm(0,self.deviationReactivePower()).cdf(-abs(np.median(numbersQ)-self.averageReactivePower())))
        return self.edgeDetectionttest()
    
    # Fixed ('initial') deviation
    def edgeDetection_3(self,index):
        #PRIMARY EDGE DETECTION
        
        #minAmount of points?
        if self.getDataWindowLenght()>=max(self.filterSize,self.minStatePoints):
            #
            #Median Filter
            [realPower,reactivePower]=self.medianFilter(index)
            #large/unlikely difference
            if (scipy.stats.norm(self.averageRealPower(), math.sqrt(self.initialDeviation[0])).pdf(realPower) * scipy.stats.norm(self.averageReactivePower(), math.sqrt(self.initialDeviation[1])).pdf(reactivePower))<.0005:
                self.getDataPoint().setEdge()
        return self.edgeDetectionttest()
    
    # Simple Edge detection 
    def edgeDetection_4(self,index):
        #minAmount of points?
        if self.getDataWindowLenght()>=max(2,self.filterSize,self.minStatePoints):

            realPowerDifference=abs(self.getDataPoint(index).getRealPower()-self.getDataPoint(index-1).getRealPower())
            reactivePowerDifference=abs(self.getDataPoint(index).getReactivePower()-self.getDataPoint(index-1).getReactivePower())
            
            if realPowerDifference>max(25, abs(self.weightedAverage[0]-self.groundRealPower())/40):
                #print "dif =" +str( realPowerDifference) +"avg =" +str(self.weightedAverage[0])+"ground"+str(self.groundRealPower())
                
                return index-(self.dataWindow[0].getIndex())
            elif reactivePowerDifference>2*max(20, abs(self.weightedAverage[1]-self.groundReactivePower())/20):
                #print "dif =" +str( reactivePowerDifference) +"avg =" +str(self.weightedAverage[1])+"ground"+str(self.groundReactivePower())
                return index-(self.dataWindow[0].getIndex())
        return self.getDataWindowLenght()
    
    # Simple Edge detection tTest optimization
    def edgeDetection_5(self,index):
        #minAmount of points?
        if self.getDataWindowLenght()>=max(2,self.filterSize,self.minStatePoints):

            realPowerDifference=abs(self.getDataPoint(index).getRealPower()-self.getDataPoint(index-1).getRealPower())
            reactivePowerDifference=abs(self.getDataPoint(index).getReactivePower()-self.getDataPoint(index-1).getReactivePower())
            
            if realPowerDifference>max(25, abs(self.weightedAverage[0]-self.groundRealPower())/25):
                #print "dif =" +str( realPowerDifference) +"avg =" +str(self.weightedAverage[0])+"ground"+str(self.groundRealPower())
                self.getDataPoint(index).setEdge()
            elif reactivePowerDifference>2*max(20, abs(self.weightedAverage[1]-self.groundReactivePower())/25):
                #print "dif =" +str( reactivePowerDifference) +"avg =" +str(self.weightedAverage[1])+"ground"+str(self.groundReactivePower())
                self.getDataPoint(index).setEdge()
        return self.edgeDetectionttest()

    #Edge detection algortihm used for anomaly detection:
# 0: No anomaly detection used    
# 1: Deviation from temporary data 
# 2: Deviation from previously identified data (uses 1 when few data yet collected)
# 3: Combination of both previous methods
    def anomalyFilter(self,data,alowedProbability,final=True,algorithm=None):
        if algorithm==None:
            algorithm=self.algorithmEdgeAnomaly
        if (algorithm==1):
            return self.anomalyFilter_1(data,alowedProbability,final)
        elif (algorithm==2):
            if (self.deviationRealPower() == None) or len(data)>self.deviationWeight():
                return self.anomalyFilter_1(data,alowedProbability,final)
            else:
                return self.anomalyFilter_2(data,alowedProbability,final)
        elif (algorithm==3):
            if (self.deviationRealPower() == None) or len(data)>self.deviationWeight():
                return self.anomalyFilter_1(data,alowedProbability,final)
            else:
                return self.anomalyFilter_3(data,alowedProbability,final)
        elif (algorithm==4):
            return self.anomalyFilter_4(data,alowedProbability)
        elif (algorithm==5):
            if (self.deviationRealPower() == None) or len(data)>self.deviationWeight():
                return self.anomalyFilter_4(data,alowedProbability,final)
            else:
                return self.anomalyFilter_5(data,alowedProbability,final)
        else:
            data=[tempDataPoint.getValues()[0:max(2,len(tempDataPoint.getValues())-1)]for tempDataPoint in data]
            return [data,0]
        
    def anomalyFilter_1(self,dataPoints,alowedProbability,final):
        data=[dataPoint.getValues()[0:max(2,len(dataPoint.getValues())-1)]for dataPoint in dataPoints]
        completed=False
        initialLenght=len(data)
        lenght=initialLenght
        while not completed:
            dataList=np.array(data).T.tolist()
            averages=[np.average(dataList[i])for i in range(len(dataList))]
            deviations=[np.std(dataList[i])for i in range(len(dataList))]
            valueNr=0
            while valueNr <len(data):
                values=data[valueNr]
                if (min(scipy.stats.norm(0,deviations[i]).cdf(-abs(values[i]-averages[i])) for i in range(len(values)))<alowedProbability):
                    if final:
                        dataPoint=dataPoints[valueNr]
                        self.dataAnomalies.append(dataPoint)
                        self.printFileAnomalies.write(datetime.datetime.utcfromtimestamp((dataPoint.getDayTime() - 25569) * 86400.0).strftime('%d/%m/%Y %H:%M:%S')+"\n")
                    data.remove(values)
                else:
                    valueNr+=1
            if len(data)==lenght or len(data)==0:
                completed=True
            lenght=len(data)
        return [data,initialLenght-lenght]
    # 4: Deviation from temporary data & minimalDeviation
    def anomalyFilter_4(self,dataPoints,alowedProbability,final):
        data=[dataPoint.getValues()[0:max(2,len(dataPoint.getValues())-1)]for dataPoint in dataPoints]
        completed=False
        initialLenght=len(data)
        lenght=initialLenght
        while not completed:
            dataList=np.array(data).T.tolist()
            averages=[np.average(dataList[i])for i in range(len(dataList))]
            deviations=[max(np.std(dataList[i]),2)for i in range(len(dataList))]
            valueNr=0
            dataPointNrs=range(len(data))
            while valueNr <len(data):
                values=data[valueNr]
                if (min(scipy.stats.norm(0,deviations[i]).cdf(-abs(values[i]-averages[i])) for i in range(len(values)))<alowedProbability):
                    if final:
                        dataPointNr=dataPointNrs.pop(valueNr)
                        dataPoint=dataPoints[dataPointNr]
                        self.dataAnomalies.append(dataPoint)
                        self.printFileAnomalies.write(datetime.datetime.utcfromtimestamp((dataPoint.getDayTime() - 25569) * 86400.0).strftime('%d/%m/%Y %H:%M:%S')+"\n")
                    data.remove(values)
                    
                else:
                    valueNr+=1
            if len(data)==lenght or len(data)==0:
                completed=True
            lenght=len(data)
        return [data,initialLenght-lenght]
    def anomalyFilter_2(self,dataPoints,alowedProbability,final):
        data=[dataPoint.getValues()[0:max(2,len(dataPoint.getValues())-1)]for dataPoint in dataPoints]
        dataList=np.array(data).T.tolist()
        averages=[np.average(dataList[i])for i in range(len(dataList))]
        deviations=[self.deviationRealPower(),self.deviationReactivePower()]
        completed=False
        initialLenght=len(data)
        lenght=initialLenght
        while not completed:
            dataList=np.array(data).T.tolist()
            averages=[np.average(dataList[i])for i in range(len(dataList))]
            valueNr=0
            while valueNr <len(data):
                values=data[valueNr]
                if (min(scipy.stats.norm(0,deviations[i]).cdf(-abs(values[i]-averages[i])) for i in range(len(values)))<alowedProbability):
                    if final:
                        dataPoint=dataPoints[valueNr]
                        self.dataAnomalies.append(dataPoint)
                        self.printFileAnomalies.write(datetime.datetime.utcfromtimestamp((dataPoint.getDayTime() - 25569) * 86400.0).strftime('%d/%m/%Y %H:%M:%S')+"\n")
                    data.remove(values)
                else:
                    valueNr+=1
            if len(data)==lenght or len(data)==0:
                completed=True
            lenght=len(data)
        return [data,initialLenght-lenght]
    
    def anomalyFilter_3(self,dataPoints,alowedProbability,final):
        data=[dataPoint.getValues()[0:max(2,len(dataPoint.getValues())-1)]for dataPoint in dataPoints]
        completed=False
        initialLenght=len(data)
        lenght=initialLenght
        while not completed:
            dataList=np.array(data).T.tolist()
            averages=[np.average(dataList[i])for i in range(len(dataList))]
            deviations=[np.std(dataList[i])for i in range(len(dataList))]
            deviations=[(deviations[0]+self.deviationRealPower())/2,(deviations[1]+self.deviationReactivePower())/2]
        
            valueNr=0
            while valueNr <len(data):
                values=data[valueNr]
                if (min(scipy.stats.norm(0,deviations[i]).cdf(-abs(values[i]-averages[i])) for i in range(len(values)))<alowedProbability):
                    if final:
                        dataPoint=dataPoints[valueNr]
                        self.dataAnomalies.append(dataPoint)
                        self.printFileAnomalies.write(datetime.datetime.utcfromtimestamp((dataPoint.getDayTime() - 25569) * 86400.0).strftime('%d/%m/%Y %H:%M:%S')+"\n")
                    data.remove(values)
                else:
                    valueNr+=1
            if len(data)==lenght or len(data)==0:
                completed=True
            lenght=len(data)
        return [data,initialLenght-lenght]
    def anomalyFilter_5(self,dataPoints,alowedProbability,final):
        data=[dataPoint.getValues()[0:max(2,len(dataPoint.getValues())-1)]for dataPoint in dataPoints]
        completed=False
        initialLenght=len(data)
        lenght=initialLenght
        while not completed:
            dataList=np.array(data).T.tolist()
            averages=[np.average(dataList[i])for i in range(len(dataList))]
            deviations=[np.std(dataList[i])for i in range(len(dataList))]
            deviations=[max(2,(deviations[0]+self.deviationRealPower())/2),max(2,(deviations[1]+self.deviationReactivePower())/2)]
            valueNr=0
            dataPointNrs=range(len(data))
            while valueNr <len(data):
                values=data[valueNr]
                if (min(scipy.stats.norm(0,deviations[i]).cdf(-abs(values[i]-averages[i])) for i in range(len(values)))<alowedProbability):
                    if final:
                        dataPointNr=dataPointNrs.pop(valueNr)
                        dataPoint=dataPoints[dataPointNr]
                        self.dataAnomalies.append(dataPoint)
                        self.printFileAnomalies.write(datetime.datetime.utcfromtimestamp((dataPoint.getDayTime() - 25569) * 86400.0).strftime('%d/%m/%Y %H:%M:%S')+"\n")
                    data.remove(values)
                else:
                    valueNr+=1
            if len(data)==lenght or len(data)==0:
                completed=True
            lenght=len(data)
        return [data,initialLenght-lenght]
    
    def groundRealPower(self):
        if not self.ground[0]==None:
            return (self.ground[0])
        else:
            return 0
        
    def groundReactivePower(self):
        if not self.ground[1]==None:
            return (self.ground[1])
        else:
            return 0 
        
    def groundWeight(self):
        return self.ground[len(self.ground)-1]
    
    def updateGround(self,realPower,reactivePower,points):
        if self.ground[0]==None:
            self.setGround(realPower,reactivePower,points)
        else:
            self.setGround( (self.groundRealPower()*self.groundWeight()+realPower*points)/(self.groundWeight()+points), (self.groundReactivePower()*self.groundWeight()+reactivePower*points)/(self.groundWeight()+points), self.groundWeight()+points)
    
    def correctGround(self,realPower,reactivePower,points):
        if self.ground[0]==None:
            self.setGround(-realPower,-reactivePower,points)
        else:
            self.setGround(self.groundRealPower()-realPower*points/self.groundWeight(), self.groundReactivePower() -reactivePower*points/self.groundWeight())
            
    def setGround(self,realPower=None,reactivePower=None,points=None):
        if realPower==None:
            realPower=self.groundRealPower()
        if reactivePower==None:
            reactivePower=self.groundReactivePower()
        if points==None:
            points=self.groundWeight()
        self.ground=[realPower,reactivePower,points]
       
    def deviationRealPower(self):
        if not self.deviation[0]==None:
            return (self.deviation[0])
        else:
            return self.initialDeviation[0]
        
    def deviationReactivePower(self):
        if not self.deviation[1]==None:
            return (self.deviation[1])
        else:
            return self.initialDeviation[1]
        
    def deviationCount(self):
        return self.deviation[2] 
    
    def deviationWeight(self):
        return self.deviation[len(self.deviation)-1]
    
    #Edge detection algortihm used for calculating deviation (edge detection 2):
# 1: Statistical average
# 2: Simple average
    def updateDeviation(self,deviationRealPower,deviationReactivePower,points,algorithm=None):
        if algorithm==None:
            algorithm=self.algorithmEdgeDeviation
        if (algorithm==1):
            return self.updateDeviation_1(deviationRealPower,deviationReactivePower,points)
        elif (algorithm==2):
            return self.updateDeviation_2(deviationRealPower,deviationReactivePower,points)
        else:
            return None
    
    #Average deviation over amount of datapoints (statistical approach)
    def updateDeviation_1(self,deviationRealPower,deviationReactivePower,points):
        if self.deviation[0]==None:
            self.deviation=[deviationRealPower,deviationReactivePower,1,points]
        else:
            self.deviation=[math.sqrt(((self.deviation[0]**2)*self.deviationWeight()+(deviationRealPower**2)*points)/(self.deviationWeight()+points)), math.sqrt(((self.deviation[1]**2)*self.deviationWeight()+(deviationReactivePower**2)*points)/(self.deviationWeight()+points)),self.deviation[2]+1, self.deviationWeight()+points]           
    
    #Average deviation (simple approach) 
    def updateDeviation_2(self,deviationRealPower,deviationReactivePower,points):
        if self.deviation[0]==None:
            self.deviation=[deviationRealPower,deviationReactivePower,1,points]
        else:
            self.deviation=[math.sqrt(((self.deviation[0]**2)*self.deviation[2]+(deviationRealPower**2))/(self.deviation[2]+1)), math.sqrt(((self.deviation[1]**2)*self.deviation[2]+(deviationReactivePower**2))/(self.deviation[2]+1)),self.deviation[2]+1, self.deviation[len(self.deviation)-1]+points]
         
    #return the current DataWindow (array)
    def getDataWindow(self):
        return self.dataWindow
    
    #return the number of points in the DataWindow (array)
    def getDataWindowLenght(self):
        return len(self.getDataWindow())
    
    #Return the DataPoint which has the given index, if no index given, this method returns the last DataPoint
    def getDataPoint(self,index=None):
        if index==None:
            return self.getDataWindow()[self.getDataWindowLenght()-1]
        else:
            return self.getDataWindow()[index-self.getDataWindow()[0].index]

        
        
        
        
        
        
        
        
        
        
        
    def addNetworkState(self,networkState):
        self.write(networkState.printStr())
        if not len(self.states)==0:
            previousState=self.getNetworkState()
            self.states.append(networkState)
            
            
            self.indexStates+=1
            
            if self.estimate(networkState,previousState):
                if self.count > 21600:
                    self.update()
                    self.estimateFull()
                    self.countNewAppliance=0
                    self.count=0
            elif self.countNewAppliance > 3600:
                if self.newAppliance():
                    #print "New appliance"
                    #ApplianceState()
                    self.plotNetworkStatesAdditive()
                    self.update()   
                    self.estimateFull(0)
                    
                        
                self.countNewAppliance=0
                self.count+=networkState.getDuration()
            else:
                #print "First" + str(networkState.getStartTime()) + "Duration" + str(networkState.getDuration())
                self.count+=networkState.getDuration()
                self.countNewAppliance+=networkState.getDuration()
            if self.indexStates % self.plotFirstNetworkStateAmount==0:
                self.plotNetworkStatesAdditive()
        else:
            self.states.append(networkState)
            self.indexStates+=1
            
    def getNetworkState(self,index=None):
        if index is None:
            return self.states[len(self.states)-1] 
        for i in range(len(self.states)-1):
            if (self.states[i].index==index):
                return self.states[i]
            
    #def networkStateRemainders(self,networkstate):
    #    realPower = networkstate.remainders()[0]+self.groundRealPower()*(networkState.applianceCount()-1)
    #    reactiverPower = networkstate.remainders()[0]+self.groundReactivePower()*(networkState.applianceCount()-1)
    #    return [realPower,reactivePower]
    
       
    def plotNetworkStates(self):
        plt.close('all')
        real=[[]]
        reactive=[[]]
        count=[False]
        colors=['#0053c9', '#ff9000', '#28ff41', '#ff3f00', '#bfbc0b', '#dd57f2', '#008c10', '#663c93', '#9b4153', '#00b7a1']
        #colors=['bo','go','ro','ko','co','mo','yo']
        for appliance in self.appliances:
            real.append([])
            reactive.append([])
            count.append(False)
        for state in self.states:
            if not state.isAnomaly("OutOfBounds"):
                base=True
                for applianceNr in range(len(self.appliances)):
                    if len(state.applianceStates)>applianceNr:
                        if not state.applianceStates[applianceNr]==self.appliances[applianceNr].states[0]:
                            real[applianceNr+1].append(state.getRealPower())
                            reactive[applianceNr+1].append(state.getReactivePower())
                            count[applianceNr+1]=True
                            base=False
                    else:
                        print "Out of bound "+str(len(state.applianceStates))+" for " +str(len(self.appliances))+" at "+str(state.index)
                if base:
                    real[0].append(state.getRealPower())
                    reactive[0].append(state.getReactivePower())
                    count[0]=True
        
        nr=0
        figure=plt.figure()
        while nr < len(real):
            if count[nr]:
                plt.plot(real[nr], reactive[nr], colors[nr-len(colors)*int(round(nr/len(colors)-0.499))], marker='o',linewidth=0)
                nr+=1
            else:
                real.pop(nr)
                reactive.pop(nr)
                count.pop(nr)
        if len(real)>0:
            plt.axis([-100,1900, -500, 750])
            plt.show()
            
            
            
    def plotNetworkStatesAdditive(self):
        plt.close('all')
        real=[[]]
        reactive=[[]]
        count=[False]
        colors=['#0053c9', '#ff9000', '#28ff41', '#ff3f00', '#bfbc0b', '#dd57f2', '#008c10', '#663c93', '#9b4153', '#00b7a1']
        for appliance in self.appliances:
            real.append([])
            reactive.append([])
            count.append(False)
        
        for stateNr in range(1,len(self.states)):
            state=self.states[stateNr]
            oldstate=self.states[stateNr-1]
            realValue=state.getStartRealPower()-oldstate.getStopRealPower()
            reactiveValue=state.getStartReactivePower()-oldstate.getStopReactivePower()
            sign=realValue/abs(realValue)
            realValue*=sign
            reactiveValue*=sign
            if (not state.isAnomaly()) and (not oldstate.isAnomaly("OutOfBounds")):
                base=True
                for applianceNr in range(len(self.appliances)):
                    if len(state.applianceStates)>applianceNr:
                        if not state.applianceStates[applianceNr]== oldstate.applianceStates[applianceNr]:
                            real[applianceNr+1].append(realValue)
                            reactive[applianceNr+1].append(reactiveValue)
                            count[applianceNr+1]=True
                            base=False
                    else:
                        print "Out of bound plot"+str(len(state.applianceStates))+" for " +str(len(self.appliances))+" at "+str(state.index)
                if base:
                    real[0].append(realValue)
                    reactive[0].append(reactiveValue)
                    count[0]=True
        
        nr=0
        figure=plt.figure()
        while nr < len(real):
            if count[nr]:
                plt.plot(real[nr], reactive[nr], colors[nr-len(colors)*int(round(nr/len(colors)-0.499))], marker='o',linewidth=0)
                nr+=1
            else:
                real.pop(nr)
                reactive.pop(nr)
                count.pop(nr)
        if len(real)>0:
            plt.axis([0, 1750,-200, 1000])
            #plt.axis([0, 750,-200, 200])
            plt.show()
        plt.close('all')
        figure=plt.figure()
        nr=0
        while nr < len(real):
            if count[nr]:
                plt.plot(real[nr], reactive[nr], colors[nr-len(colors)*int(round(nr/len(colors)-0.499))], marker='o',linewidth=0)
                nr+=1
            else:
                real.pop(nr)
                reactive.pop(nr)
                count.pop(nr)
        if len(real)>0:
            #plt.axis([0, 1750,-200, 1000])
            plt.axis([0, 450,-150, 150])
            plt.show()
            
            
    def plotNetworkStatesAdditiveBlank(self):
        plt.close('all')
        real=[]
        reactive=[]
        colors=['#0053c9', '#ff9000', '#28ff41', '#ff3f00', '#bfbc0b', '#dd57f2', '#008c10', '#663c93', '#9b4153', '#00b7a1']
        
        
        for stateNr in range(1,len(self.states)):
            state=self.states[stateNr]
            oldstate=self.states[stateNr-1]
            
            if (not state.isAnomaly()) and (not oldstate.isAnomaly("OutOfBounds")):
                realValue=state.getStartRealPower()-oldstate.getStopRealPower()
                reactiveValue=state.getStartReactivePower()-oldstate.getStopReactivePower()
                sign=realValue/abs(realValue)
                realValue*=sign
                reactiveValue*=sign
                real.append(realValue)
                reactive.append(reactiveValue)
        figure=plt.figure()
        plt.plot(real, reactive, colors[0], marker='o',linewidth=0)
        plt.axis([0, 1750,-200, 1000])
        plt.show()
        plt.close('all')
        figure=plt.figure()
        plt.plot(real, reactive, colors[0], marker='o',linewidth=0)
        plt.axis([0, 1750,-200, 1000])
        plt.show()
            
            
            
            
            
            
            
          
    #Estimates for the given (or all if no state is given) network state(s) the appliance state of each appliance 
#1: Allows but one state change at any given moment 
    def estimate(self,networkState=None,previousState=None,algorithm=None):
        sufficient=False
        if len(self.appliances)==0:
            return False
        if networkState==None:
            return self.estimateFull(algorithm)
        else:
            if algorithm==None:
                algorithm=self.algorithmEstimate
            if (algorithm==1):
                sufficient= self.estimate_1(networkState,previousState,self.allowedDeviation)
            elif (algorithm==2):
                sufficient= self.estimate_2(networkState,previousState,self.allowedDeviation)
            elif (algorithm==3):
                sufficient= self.estimate_3(networkState,previousState,self.allowedDeviation)
            elif (algorithm==4):
                sufficient= self.estimate_4(networkState,previousState,self.allowedDeviation)
            elif (algorithm==5):
                sufficient= self.estimate_5(networkState,previousState,self.allowedDeviation)
            elif (algorithm==6):
                sufficient= self.estimate_6(networkState,previousState,self.allowedDeviation)
            elif (algorithm==7):
                sufficient= self.estimate_7(networkState,previousState,self.allowedDeviation)
            elif (algorithm==8):
                sufficient= self.estimate_8(networkState,previousState,self.allowedDeviation)
            elif (algorithm==9):
                sufficient= self.estimate_9(networkState,previousState,self.allowedDeviation)
            elif (algorithm==10):
                sufficient= self.estimate_10(networkState,previousState,self.allowedDeviation)
            elif (algorithm==11):
                sufficient= self.estimate_11(networkState,previousState,self.allowedDeviation)
            elif (algorithm==12):
                sufficient= self.estimate_12(networkState,previousState,self.allowedDeviation)
            #else:
            #    return False
            for applianceNr in range(len(self.appliances)):
                self.printEdgeFile.write(" "+str(self.states[networkState.getIndex()].applianceStates[applianceNr].getIndex()))
                self.appliances[applianceNr].addDuration( self.states[len(self.states)-1].applianceStates[applianceNr],networkState.getDuration())
            for anomaly in self.states[networkState.getIndex()].getAnomalies():
                self.printEdgeFile.write(" "+anomaly[0])
                
        return sufficient
    
    def estimateFull(self,algorithm=None):
        if algorithm==None:
            algorithm=self.algorithmEstimateFull
        sufficient=False
        if len(self.appliances)==0:
            return False
        else:
            self.write("ReEstimation")
            if (algorithm==1) and len(self.appliances)>=4:
                init_state = [networkState.applianceStates for networkState in self.states]
                sae = SimulatedAnnaelingEstimator(init_state, self)
                sae.steps = 100000
                sae.Tmax = 10000000
                sae.copy_strategy = 'slice'
                states, e = sae.anneal()
                print len(states)
                print len(states[len(states)-1])
                for i in range(len(states)-1):
                    self.states[i].applianceStates=states[i]
                for networkState in self.states:
                    self.estimate(networkState,None,0)
            elif (algorithm==2):
                for appliance in self.appliances:
                    for applianceState in appliance.states:
                        applianceState.resetDuration()
                previousState=self.states[0]
                
                self.printEdgeFile.write('\n'+ datetime.datetime.utcfromtimestamp(previousState.getStartDayTime()).strftime('%d/%m/%Y %H:%M:%S'))
                self.write(previousState.printStr())
                
                self.estimate(previousState,None)
                for networkState in self.states[1:]:
                    #if not networkState.isAnomaly("OutOfBounds"):
                    self.printEdgeFile.write('\n'+ datetime.datetime.utcfromtimestamp(networkState.getStartDayTime()).strftime('%d/%m/%Y %H:%M:%S'))
                    self.write(networkState.printStr())
                    networkState.removeAnomaly("MissedEdge")
                    self.estimate(networkState,previousState)
                    previousState=networkState
            else:
                for networkState in self.states:
                    self.printEdgeFile.write('\n'+ datetime.datetime.utcfromtimestamp(networkState.getStartDayTime()).strftime('%d/%m/%Y %H:%M:%S'))
                    for applianceNr in range(len(self.appliances)):
                        self.printEdgeFile.write(" "+str(self.states[networkState.getIndex()].applianceStates[applianceNr].getIndex()))
                    for anomaly in self.states[networkState.getIndex()].getAnomalies():
                        self.printEdgeFile.write(" "+anomaly[0])

        return False
    
    #single state change
    def estimate_1(self,networkState,previousState,allowedDeviation=0):
        if (allowedDeviation==0):
            for appliance in self.appliances:
                for stateNr in range(len(appliance.states)):
                    allowedDeviation=max(allowedDeviation,appliance.states[stateNr].getRealPowerDeviation()**2+appliance.states[stateNr].getReactivePowerDeviation()**2)
        
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
            
        allowedDeviation+=networkState.getRealPowerDeviation()**2 + networkState.getReactivePowerDeviation()**2
        sufficient=False
        
        for i in range(len(self.appliances)):
            for state in self.appliances[i].states:
                if not (state==previousState.applianceStates[i]):
                    [real,reactive]= previousState.estimate()
                    real=self.states[networkState.getIndex()].getRealPower()-(real-previousState.applianceStates[i].getRealPower() + state.getRealPower())
                    reactive=self.states[networkState.getIndex()].getReactivePower() - (reactive-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())
                    if real**2+reactive**2<allowedDeviation:
                        sufficient=True
                        allowedDeviation=real**2+reactive**2
                        self.states[networkState.getIndex()].applianceStates=[]
                        for applianceState in previousState.applianceStates:
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                        self.states[networkState.getIndex()].applianceStates[i]=state
        return sufficient
    
    #Multiple state change, No cost 
    def estimate_2(self,networkState,previousState,allowedDeviation=0):
        if (allowedDeviation==0):
            allowedDeviation=0
            for appliance in self.appliances:
                for stateNr in range(len(appliance.states)):
                    allowedDeviation=max(allowedDeviation,appliance.states[stateNr].getRealPowerDeviation()**2+appliance.states[stateNr].getReactivePowerDeviation()**2)
        allowedDeviation+=networkState.getRealPowerDeviation()**2 + networkState.getReactivePowerDeviation()**2
        sufficient=False
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
        nr=0
        [real,reactive]= networkState.remainders()
        currentDeviation=real**2+reactive**2
        
        while nr <len(self.appliances):
            for state in self.appliances[nr].states:
                if not (state==networkState.applianceStates[nr]):
                    [real,reactive]= networkState.estimate()
                    real=networkState.getRealPower()-(real-previousState.applianceStates[i].getRealPower() + state.getRealPower())
                    reactive=networkState.getReactivePower() - (reactive-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())
                    if real**2+reactive**2<currentDeviation:
                        if real**2+reactive**2<allowedDeviation:
                            sufficient=True
                        currentDeviation=real**2+reactive**2
                        networkState.applianceStates[nr]=state
                        nr=0
            nr+=1
        return sufficient
    
    #Multiple state change, Cost in form of minimum improvement (allowed deviation) required
    def estimate_3(self,networkState,previousState,allowedDeviation=0):
        if (allowedDeviation==0):
            allowedDeviation=0
            for appliance in self.appliances:
                for stateNr in range(len(appliance.states)):
                    allowedDeviation=2*max(allowedDeviation/2,appliance.states[stateNr].getRealPowerDeviation()**2+appliance.states[stateNr].getReactivePowerDeviation()**2)
            
        allowedDeviation+=networkState.getRealPowerDeviation()**2 + networkState.getReactivePowerDeviation()**2
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
        nr=0
        [real,reactive]= networkState.remainders()
        currentDeviation=real**2+reactive**2
        if currentDeviation<allowedDeviation:
            return False
            print "SMALL"
        while nr <len(self.appliances):
            for state in self.appliances[nr].states:
                if not (state==networkState.applianceStates[nr]):
                    [real,reactive]= networkState.estimate()
                    real=networkState.getRealPower()-(real-previousState.applianceStates[i].getRealPower() + state.getRealPower())
                    reactive=networkState.getReactivePower() - (reactive-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())
                    if real**2+reactive**2<max(allowedDeviation,currentDeviation-allowedDeviation):
                        if real**2+reactive**2<allowedDeviation:
                            return True
                        currentDeviation=real**2+reactive**2
                        networkState.applianceStates[nr]=state
                        
                        nr=0
            nr+=1
        return False
    
    #Diminished requirement on turning appliances off
    def estimate_4(self,networkState,previousState,allowedDeviation=0):
        if networkState.getRealPower()>=previousState.getRealPower():
            return self.estimate_1(networkState,previousState,allowedDeviation)
        else:
            if (allowedDeviation==0):
                allowedDeviation=0
                for appliance in self.appliances:
                    for stateNr in range(len(appliance.states)):
                        allowedDeviation= 2*max(allowedDeviation/2, appliance.states[stateNr].getRealPowerDeviation()**2 + appliance.states[stateNr].getReactivePowerDeviation()**2)
            allowedDeviation+=networkState.getRealPowerDeviation()**2 + networkState.getReactivePowerDeviation()**2
            [real,reactive]= self.networkStateRemainders(networkState)
            currentDeviation=real**2+reactive**2
            sufficient=False
            self.states[networkState.getIndex()].applianceStates=[]
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            for i in range(len(self.appliances)):
                for stateNr in range(len(self.appliances[i].states)):
                    state=self.appliances[i].states[stateNr]
                    if not (state==previousState.applianceStates[i]):
                        [realEstimate,reactiveEstimate]= previousState.estimate()
                        #current=total-newEstimate-ground| newEStimate=OldEstimate-removedState+AddedState
                        real=networkState.getRealPower()-(realEstimate-previousState.applianceStates[i].getRealPower() + state.getRealPower())-self.groundRealPower()
                        reactive=networkState.getReactivePower() - (reactiveEstimate-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())-self.groundReactivePower()
                        if real**2+reactive**2<max(allowedDeviation,currentDeviation-allowedDeviation):
                            if real**2+reactive**2<allowedDeviation:
                                sufficient= True
                            currentDeviation=real**2+reactive**2
                            self.states[networkState.getIndex()].applianceStates=[]
                            for applianceState in previousState.applianceStates:
                                self.states[networkState.getIndex()].applianceStates.append(applianceState)
                            self.states[networkState.getIndex()].applianceStates[i]=state
            return sufficient
        
    #Highest probability 1 state change
    def estimate_5(self,networkState,previousState,allowedDeviation=0,allowedPobability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
        if (allowedPobability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)

        probabilityDuration=1
        for applianceState in networkState.applianceStates:
            probabilityDuration*=applianceState.probabilityNoChange(networkState.getDuration())
        
        [real,reactive]= self.networkStateRemainders(networkState)
        probabilityMeasurement=scipy.stats.norm(0,math.sqrt(variationReal)).pdf(real)* scipy.stats.norm(0,math.sqrt(variationReactive)).cdf(reactive)
        
        #probabilityAppliance (conditional)
        
        sufficient=probabilityMeasurement>allowedProbability
        currentProbability=probabilityMeasurement*probabilityDuration
        
        
        
        for i in range(len(self.appliances)):
            for stateNr in range(len(self.appliances[i].states)):
                state=self.appliances[i].states[stateNr]
                if not (state==previousState.applianceStates[i]):
                    [realEstimate,reactiveEstimate]= previousState.estimate()
                    #current=total-newEstimate-ground| newEStimate=OldEstimate-removedState+AddedState
                    real=networkState.getRealPower()-(realEstimate-previousState.applianceStates[i].getRealPower() + state.getRealPower())-self.groundRealPower()
                    reactive=networkState.getReactivePower() - (reactiveEstimate-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())-self.groundReactivePower()
                    deviationRealNew=math.sqrt(variationReal)
                    deviationReactiveNew=math.sqrt(variationReactive)
                    if state.ONstate():
                        deviationRealNew+=state.getRealPowerDeviation()**2
                        deviationReactiveNew+=state.getReactivePowerDeviation()**2
                    if previousState.applianceStates[i].ONstate():
                        deviationRealNew-=previousState.applianceStates[i].getRealPowerDeviation()**2
                        deviationReactiveNew-=previousState.applianceStates[i].getReactivePowerDeviation()**2
                    probabilityMeasurementNew=scipy.stats.norm(0,math.sqrt(deviationRealNew)).pdf(real) * scipy.stats.norm(0,math.sqrt(deviationReactiveNew)).pdf(reactive)
                    ref=previousState.applianceStates[i].probabilityNoChange(networkState.getDuration())
                    if ref==0:
                        probabilityDurationNew = 1
                    else:
                        probabilityDurationNew = probabilityDuration*previousState.applianceStates[i].probabilityChange(networkState.getDuration())/ ref
                    if probabilityMeasurementNew*probabilityDurationNew>probabilityMeasurement*probabilityDuration:
                        if probabilityMeasurementNew>allowedProbability:
                            sufficient= True
                        probabilityMeasurement=probabilityMeasurementNew
                        probabilityDuration=probabilityDurationNew
                        
                        self.states[networkState.getIndex()].applianceStates=[]
                        for applianceState in previousState.applianceStates:
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                        self.states[networkState.getIndex()].applianceStates[i]=state
        return sufficient
    
    
    #Highest probability 1 state change & Diminished requirement on turning appliances off
    def estimate_6(self,networkState,previousState,allowedDeviation=0,allowedPobability=0):
        if networkState.getRealPower()>=previousState.getRealPower():
            return self.estimate_5(networkState,previousState,allowedDeviation)
        else:
            self.states[networkState.getIndex()].applianceStates=[]
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            
            [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
            if (allowedPobability==0):
                allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
                allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
                allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)

            probabilityDuration=1
            for applianceState in networkState.applianceStates:
                probabilityDuration*=applianceState.probabilityNoChange(networkState.getDuration())
        
            [real,reactive]= self.networkStateRemainders(networkState)
            probabilityMeasurement=scipy.stats.norm(0,math.sqrt(variationReal)).pdf(real)* scipy.stats.norm(0,math.sqrt(variationReactive)).cdf(reactive)
        
            #probabilityAppliance (conditional)
        
            sufficient=probabilityMeasurement>allowedProbability
            currentProbability=probabilityMeasurement*probabilityDuration
        
        
        
            for i in range(len(self.appliances)):
                for stateNr in range(len(self.appliances[i].states)):
                    state=self.appliances[i].states[stateNr]
                    if not (state==previousState.applianceStates[i]):
                        [realEstimate,reactiveEstimate]= previousState.estimate()
                        #current=total-newEstimate-ground| newEStimate=OldEstimate-removedState+AddedState
                        real=networkState.getRealPower()-(realEstimate-previousState.applianceStates[i].getRealPower() + state.getRealPower())-self.groundRealPower()
                        reactive=networkState.getReactivePower() - (reactiveEstimate-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())-self.groundReactivePower()
                        deviationRealNew=math.sqrt(variationReal)
                        deviationReactiveNew=math.sqrt(variationReactive)
                        if state.ONstate():
                            deviationRealNew+=state.getRealPowerDeviation()**2
                            deviationReactiveNew+=state.getReactivePowerDeviation()**2
                        if previousState.applianceStates[i].ONstate():
                            deviationRealNew-=previousState.applianceStates[i].getRealPowerDeviation()**2
                            deviationReactiveNew-=previousState.applianceStates[i].getReactivePowerDeviation()**2
                        probabilityMeasurementNew=scipy.stats.norm(0,math.sqrt(deviationRealNew)).pdf(real) * scipy.stats.norm(0,math.sqrt(deviationReactiveNew)).pdf(reactive)
                        probabilityDurationNew=1
                        if probabilityMeasurementNew*probabilityDurationNew>probabilityMeasurement*probabilityDuration:
                            if probabilityMeasurementNew>allowedProbability:
                                sufficient= True
                            probabilityMeasurement=probabilityMeasurementNew
                            probabilityDuration=probabilityDurationNew
                            
                            self.states[networkState.getIndex()].applianceStates=[]
                            for applianceState in previousState.applianceStates:
                                self.states[networkState.getIndex()].applianceStates.append(applianceState)
                            self.states[networkState.getIndex()].applianceStates[i]=state
            return sufficient
    
    #Highest probability 1 state change no duration
    def estimate_7(self,networkState,previousState,allowedDeviation=0,allowedProbability=10**(-7)):
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)

        [real,reactive]= self.networkStateRemainders(networkState)
        probabilityMeasurement=scipy.stats.norm(0,math.sqrt(variationReal)).pdf(real)* scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(reactive)
        
        #probabilityAppliance (conditional)
        
        sufficient=probabilityMeasurement>allowedProbability
        currentProbability=probabilityMeasurement
        
        
        
        for i in range(len(self.appliances)):
            for stateNr in range(0,len(self.appliances[i].states)):
                state=self.appliances[i].states[stateNr]
                if not (state==previousState.applianceStates[i]):
                    [realEstimate,reactiveEstimate]= previousState.estimate()
                    #current=total-newEstimate-ground| newEStimate=OldEstimate-removedState+AddedState
                    real=networkState.getRealPower()-(realEstimate-previousState.applianceStates[i].getRealPower() + state.getRealPower())-self.groundRealPower()
                    reactive=networkState.getReactivePower() - (reactiveEstimate-previousState.applianceStates[i].getReactivePower()+ state.getReactivePower())-self.groundReactivePower()
                    deviationRealNew=math.sqrt(variationReal)
                    deviationReactiveNew=math.sqrt(variationReactive)
                    if state.ONstate():
                        deviationRealNew+=state.getRealPowerDeviation()**2
                        deviationReactiveNew+=state.getReactivePowerDeviation()**2
                    if previousState.applianceStates[i].ONstate():
                        deviationRealNew-=previousState.applianceStates[i].getRealPowerDeviation()**2
                        deviationReactiveNew-=previousState.applianceStates[i].getReactivePowerDeviation()**2
                    probabilityMeasurementNew=scipy.stats.norm(0,math.sqrt(deviationRealNew)).pdf(real) * scipy.stats.norm(0,math.sqrt(deviationReactiveNew)).pdf(reactive)
                    if probabilityMeasurementNew>probabilityMeasurement:
                        if probabilityMeasurementNew>allowedProbability:
                            sufficient= True
                        probabilityMeasurement=probabilityMeasurementNew
                        
                        self.states[networkState.getIndex()].applianceStates=[]
                        for applianceState in previousState.applianceStates:
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                        self.states[networkState.getIndex()].applianceStates[i]=state
        
        if probabilityMeasurement<allowedProbability:
            self.states[networkState.getIndex()].applianceStates=[]
            for appliance in self.appliances:
                self.states[networkState.getIndex()].applianceStates.append(appliance.states[0])
                
                
            for i in range(len(self.appliances)):
                for stateNr in range(1,len(self.appliances[i].states)):
                    state=self.appliances[i].states[stateNr]
                    real=networkState.getRealPower()- state.getRealPower()-self.groundRealPower()
                    reactive=networkState.getReactivePower() - state.getReactivePower()-self.groundReactivePower()
                    deviationRealNew=math.sqrt(variationReal)
                    deviationReactiveNew=math.sqrt(variationReactive)
                    if state.ONstate():
                        deviationRealNew+=state.getRealPowerDeviation()**2
                        deviationReactiveNew+=state.getReactivePowerDeviation()**2
                    probabilityMeasurementNew=scipy.stats.norm(0,math.sqrt(deviationRealNew)).pdf(real) * scipy.stats.norm(0,math.sqrt(deviationReactiveNew)).pdf(reactive)
                    if probabilityMeasurementNew>probabilityMeasurement:
                        if probabilityMeasurementNew>allowedProbability:
                            sufficient= True
                        probabilityMeasurement=probabilityMeasurementNew
                        self.states[networkState.getIndex()].applianceStates=[]
                        for appliance in self.appliances:
                            self.states[networkState.getIndex()].applianceStates.append(appliance.states[0])
                        self.states[networkState.getIndex()].applianceStates[i]=state
            
        return sufficient
    
    #Highest probability 1 state change no duration ADDITIVE
    def estimate_8(self,networkState,previousState,allowedDeviation=0,allowedProbability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        for applianceState in previousState.applianceStates:
            self.states[networkState.getIndex()].applianceStates.append(applianceState)
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)
        real=networkState.getStartRealPower() - previousState.getStopRealPower()
        reactive=networkState.getStartReactivePower() - previousState.getStopReactivePower()
        probabilityMeasurement=scipy.stats.norm(0,math.sqrt(variationReal)).pdf(real)* scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(reactive)
        
        #probabilityAppliance (conditional)
        
        sufficient=probabilityMeasurement>allowedProbability
        currentProbability=probabilityMeasurement
        
        
        
        for i in range(len(self.appliances)):
            for stateNr in range(0,len(self.appliances[i].states)):
                state=self.appliances[i].states[stateNr]
                if not (state==previousState.applianceStates[i]):
                    [realEstimate,reactiveEstimate]= previousState.estimate()
                    #remainder=total-AddedState-otherStates |otherStates~ prevousState-removedState
                    real=networkState.getStartRealPower() - state.getRealPower()-(previousState.getStopRealPower()-previousState.applianceStates[i].getRealPower())
                    reactive=networkState.getStartReactivePower() - state.getReactivePower()-(previousState.getStopReactivePower()-previousState.applianceStates[i].getReactivePower())
                    deviationRealNew=0
                    deviationReactiveNew=0
                    if state.ONstate():
                        deviationRealNew+=state.getRealPowerDeviation()**2
                        deviationReactiveNew+=state.getReactivePowerDeviation()**2
                    if previousState.applianceStates[i].ONstate():
                        deviationRealNew-=previousState.applianceStates[i].getRealPowerDeviation()**2
                        deviationReactiveNew-=previousState.applianceStates[i].getReactivePowerDeviation()**2
                    deviationRealNew=math.sqrt(abs(deviationRealNew))
                    deviationReactiveNew=math.sqrt(abs(deviationReactiveNew))
                    
                    if max(networkState.getRealPower(),state.getRealPower())<previousState.applianceStates[i].getRealPower() or ( real<2*deviationRealNew and reactive<2*deviationReactiveNew):
                        probabilityMeasurementNew=scipy.stats.norm(0,deviationRealNew).pdf(real) * scipy.stats.norm(0,deviationReactiveNew).pdf(reactive)
                        if probabilityMeasurementNew>probabilityMeasurement:
                            if probabilityMeasurementNew>allowedProbability:
                                sufficient= True
                            probabilityMeasurement=probabilityMeasurementNew

                            self.states[networkState.getIndex()].applianceStates=[]
                            for applianceState in previousState.applianceStates:
                                self.states[networkState.getIndex()].applianceStates.append(applianceState)
                            self.states[networkState.getIndex()].applianceStates[i]=state
        return sufficient
    
    
    #Simple ADDITIVE 1 state change+missed
    def estimate_9(self,networkState,previousState=None,allowedDeviation=0,allowedProbability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        sufficient=5.61
        missed=[]
        if not previousState==None:
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            networkRealPower = networkState.getStartRealPower() - previousState.getStopRealPower()
            networkReactivePower = networkState.getStartReactivePower() - previousState.getStopReactivePower()   
        else:
            previousState=networkState
            for appliance in self.appliances:
                #previousState.applianceStates.append(appliance.getState(0))
                self.states[networkState.getIndex()].applianceStates.append(appliance.getState(0))
            networkRealPower = networkState.getStartRealPower() - self.groundRealPower()
            networkReactivePower = networkState.getStartReactivePower() - self.groundReactivePower()
            #start=True
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)
        self.write( "   power " + str(networkRealPower)+ " = " +str(networkState.getStartRealPower()) + " - "+ str(previousState.getStopRealPower()))
        
        for applianceNr in range(len(self.appliances)):
            for stateNr in  list(reversed(range(len(self.appliances[applianceNr].states)))):
                state=self.appliances[applianceNr].states[stateNr]
                if not (state==previousState.applianceStates[applianceNr]):
                    self.write("   appliancePower " + str(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower()))
                    if (networkRealPower < 0 and state.getRealPower()<previousState.applianceStates[applianceNr].getRealPower())or(networkRealPower > 0 and state.getRealPower()>previousState.applianceStates[applianceNr].getRealPower()):
                        [sufficient,missed]= self.estimate_9_sub(networkState,previousState,sufficient, missed, networkRealPower, networkReactivePower, applianceNr, state)
        for appliance in missed:
            self.states[networkState.getIndex()].setAnomaly("MissedEdge"+str(appliance.getIndex()))
            self.states[networkState.getIndex()].applianceStates[appliance.getIndex()]=appliance.getState(0)
        return sufficient<5.61
    
    def estimate_9_sub(self,networkState,previousState,sufficient,missed,networkRealPower,networkReactivePower,applianceNr,state):
        difRealPower=networkRealPower-(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower())
        difReactivePower=networkReactivePower-(state.getReactivePower()-previousState.applianceStates[applianceNr].getReactivePower())
        self.write("   improvement")
        if distance(networkRealPower, networkReactivePower) > distance(difRealPower,difReactivePower):
            
            deviationRealNew=0
            deviationReactiveNew=0
            if state.ONstate():
                deviationRealNew+=state.getRealPowerDeviation()**2
                deviationReactiveNew+=state.getReactivePowerDeviation()**2
            elif previousState.applianceStates[applianceNr].ONstate():
                deviationRealNew+=previousState.applianceStates[applianceNr].getRealPowerDeviation()**2
                deviationReactiveNew+=previousState.applianceStates[applianceNr].getReactivePowerDeviation()**2
                deviationRealNew/=2
                deviationReactiveNew/=2
            deviationRealNew=math.sqrt(abs(deviationRealNew))
            deviationReactiveNew=math.sqrt(abs(deviationReactiveNew))
            self.write( "   powerDif " + str(difRealPower) +" "+ str(difReactivePower))
            self.write( "   dev " + str(abs(deviationRealNew))+" "+ str(abs(deviationReactiveNew)))
            relativeError= distance(abs(difRealPower)/abs(deviationRealNew), abs(difReactivePower)/abs(deviationReactiveNew))
            if  min(sufficient,3.92)>relativeError:
                #print "OK " +str(state.getRealPower())
                self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower()))
                sufficient=relativeError
                
                self.states[networkState.getIndex()].applianceStates=[]
                
                for applianceNr2 in range(len(self.appliances)):
                    if networkState.getIndex()==0:
                        applianceState=self.appliances[applianceNr2].getState(0)
                        self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    else:
                        applianceState=previousState.applianceStates[applianceNr2]
                        self.states[networkState.getIndex()].applianceStates.append(applianceState)
                self.states[networkState.getIndex()].applianceStates[applianceNr]=state
            elif networkState.getRealPower()-self.groundRealPower()<previousState.applianceStates[applianceNr].getRealPower()-2*deviationRealNew and state.getIndex()==0:
                #print "NOK " +str(state.getRealPower())
                if sufficient>relativeError:
                    self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " NOMissedEdge")
                    sufficient=relativeError
                    
                    self.states[networkState.getIndex()].applianceStates=[]
                    for applianceNr2 in range(len(self.appliances)):
                        if networkState.getIndex()==0:
                            applianceState=self.appliances[applianceNr2].getState(0)
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                        else:
                            applianceState=previousState.applianceStates[applianceNr2]
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    self.states[networkState.getIndex()].applianceStates[applianceNr]=state
                else:
                    self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " MissedEdge")
                    #self.states[networkState.getIndex()].applianceStates=[]
                    #for applianceState in previousState.applianceStates:
                    #    self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    missed.append(self.appliances[applianceNr])
                    #return True
        return [sufficient,missed]
    def estimate_9_missed(self,networkState,missed=[]):
        for applianceNr in range(len(self.appliances)):
            state=self.appliances[applianceNr].states[0]
            oldState= networkState.applianceStates[applianceNr]
            if not (state==networkState.applianceStates[applianceNr]):
                if distance(networkRealPower, networkReactivePower) > distance(networkRealPower,networkReactivePower,state.getRealPower()-oldState.getRealPower(), state.getReactivePower()-oldState.getReactivePower()):
                    [realReamainder,reactiveRemainder]=networkStateRemainders(self,networkState)
                    if -realReamainder>oldState.getRealPower()+2*oldState.getRealPowerDeviation() :
                        self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " MissedEdge")
                        missed.append(self.appliances[applianceNr])
        return missed
    #Simple ADDITIVE 2 state change+missed
    def estimate_10(self,networkState,previousState=None,allowedDeviation=0,allowedProbability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        sufficient=5.61
        missed=[]
        if not previousState==None:
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            networkRealPower = networkState.getStartRealPower() - previousState.getStopRealPower()
            networkReactivePower = networkState.getStartReactivePower() - previousState.getStopReactivePower()   
        else:
            previousState=networkState
            for appliance in self.appliances:
                #previousState.applianceStates.append(appliance.getState(0))
                self.states[networkState.getIndex()].applianceStates.append(appliance.getState(0))
            networkRealPower = networkState.getStartRealPower() - self.groundRealPower()
            networkReactivePower = networkState.getStartReactivePower() - self.groundReactivePower()
            #start=True
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)
        self.write( "   power " + str(networkRealPower)+ " = " +str(networkState.getStartRealPower()) + " - "+ str(previousState.getStopRealPower()))
        
        for applianceNrMain in range(len(self.appliances)):
            for stateNrMain in  list(reversed(range(len(self.appliances[applianceNrMain].states)))):
                stateMain=self.appliances[applianceNrMain].states[stateNrMain]
                if not (stateMain==previousState.applianceStates[applianceNrMain]):
                    self.write("   appliancePower " + str(stateMain.getRealPower()-previousState.applianceStates[applianceNrMain].getRealPower()))
                    if (networkRealPower < 0 and stateMain.getRealPower()<previousState.applianceStates[applianceNrMain].getRealPower()) or (networkRealPower > 0 and stateMain.getRealPower()>previousState.applianceStates[applianceNrMain].getRealPower()):
                        [sufficientNew,missed]= self.estimate_9_sub(networkState,previousState,sufficient, missed, networkRealPower, networkReactivePower, applianceNrMain, stateMain)
                        if sufficientNew<sufficient:
                            sufficient=sufficientNew
                        else:
                            difRealPower=networkRealPower-(stateMain.getRealPower()-previousState.applianceStates[applianceNrMain].getRealPower())
                            difReactivePower=networkReactivePower-(stateMain.getReactivePower()-previousState.applianceStates[applianceNrMain].getReactivePower())
                            for applianceNr in range(applianceNrMain+1,len(self.appliances)):
                                for stateNr in  list(reversed(range(len(self.appliances[applianceNr].states)))):
                                    state=self.appliances[applianceNr].states[stateNr]
                                    if not (state==previousState.applianceStates[applianceNr]):
                                        self.write("   appliancePowerRemaining " + str(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower()))
                                        if (difRealPower<0 and state.getRealPower()<previousState.applianceStates[applianceNr].getRealPower()) or (difRealPower>0 and state.getRealPower()>previousState.applianceStates[applianceNr].getRealPower()):
                                            [sufficientNew,dummy]= self.estimate_9_sub(networkState,previousState,sufficient, [], difRealPower, difReactivePower, applianceNr, state)
                                            if sufficientNew<sufficient:
                                                self.write("   OK"+str(applianceNrMain)+ " "+str(stateMain.getRealPower())+ " DualEdge")
                                                self.states[networkState.getIndex()].applianceStates[applianceNrMain]=stateMain
                                                self.states[networkState.getIndex()].setAnomaly("DualEdge"+str(applianceNrMain))
                                                self.states[networkState.getIndex()].setAnomaly("DualEdge"+str(applianceNr))
                                                sufficient=sufficientNew
                            
        for appliance in missed:
            
            self.states[networkState.getIndex()].setAnomaly("MissedEdge"+str(appliance.getIndex()))
            self.states[networkState.getIndex()].applianceStates[appliance.getIndex()]=appliance.getState(0)
            
        return sufficient<5.61
    #Closest ADDITIVE 2 state change+missed
    def estimate_11(self,networkState,previousState=None,allowedDeviation=0,allowedProbability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        missed=[]
        if not previousState==None:
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            networkRealPower = networkState.getStartRealPower() - previousState.getStopRealPower()
            networkReactivePower = networkState.getStartReactivePower() - previousState.getStopReactivePower()   
        else:
            previousState=networkState
            for appliance in self.appliances:
                #previousState.applianceStates.append(appliance.getState(0))
                self.states[networkState.getIndex()].applianceStates.append(appliance.getState(0))
            networkRealPower = networkState.getStartRealPower() - self.groundRealPower()
            networkReactivePower = networkState.getStartReactivePower() - self.groundReactivePower()
            #start=True
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        sufficient=distance(networkRealPower, networkReactivePower)
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)
        self.write( "   power " + str(networkRealPower)+ " = " +str(networkState.getStartRealPower()) + " - "+ str(previousState.getStopRealPower()))
        
        for applianceNr in range(len(self.appliances)):
            for stateNr in  list(reversed(range(len(self.appliances[applianceNr].states)))):
                state=self.appliances[applianceNr].states[stateNr]
                if not (state==previousState.applianceStates[applianceNr]):
                    self.write("   appliancePower " + str(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower()))
                    if (networkRealPower < 0 and state.getRealPower()<previousState.applianceStates[applianceNr].getRealPower())or(networkRealPower > 0 and state.getRealPower()>previousState.applianceStates[applianceNr].getRealPower()):
                        [sufficient,missed]= self.estimate_11_sub(networkState,previousState,sufficient, missed, networkRealPower, networkReactivePower, applianceNr, state)
        for appliance in missed:
            self.states[networkState.getIndex()].setAnomaly("MissedEdge"+str(appliance.getIndex()))
            self.states[networkState.getIndex()].applianceStates[appliance.getIndex()]=appliance.getState(0)
        return sufficient<5.61
    
    def estimate_11_sub(self,networkState,previousState,sufficient,missed,networkRealPower,networkReactivePower,applianceNr,state):
        difRealPower=networkRealPower-(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower())
        difReactivePower=networkReactivePower-(state.getReactivePower()-previousState.applianceStates[applianceNr].getReactivePower())
        self.write("   improvement")
        if sufficient > distance(difRealPower,difReactivePower):
            
            deviationRealNew=0
            deviationReactiveNew=0
            if state.ONstate():
                deviationRealNew+=state.getRealPowerDeviation()**2
                deviationReactiveNew+=state.getReactivePowerDeviation()**2
            elif previousState.applianceStates[applianceNr].ONstate():
                deviationRealNew+=previousState.applianceStates[applianceNr].getRealPowerDeviation()**2
                deviationReactiveNew+=previousState.applianceStates[applianceNr].getReactivePowerDeviation()**2
                deviationRealNew/=2
                deviationReactiveNew/=2
            deviationRealNew=math.sqrt(abs(deviationRealNew))
            deviationReactiveNew=math.sqrt(abs(deviationReactiveNew))
            self.write( "   powerDif " + str(difRealPower) +" "+ str(difReactivePower))
            self.write( "   dev " + str(abs(deviationRealNew))+" "+ str(abs(deviationReactiveNew)))
            relativeError= distance(abs(difRealPower)/abs(deviationRealNew), abs(difReactivePower)/abs(deviationReactiveNew))
            if  3.92>relativeError:
                #print "OK " +str(state.getRealPower())
                self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower()))
                sufficient=distance(difRealPower,difReactivePower)
                
                self.states[networkState.getIndex()].applianceStates=[]
                
                for applianceNr2 in range(len(self.appliances)):
                    if networkState.getIndex()==0:
                        applianceState=self.appliances[applianceNr2].getState(0)
                        self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    else:
                        applianceState=previousState.applianceStates[applianceNr2]
                        self.states[networkState.getIndex()].applianceStates.append(applianceState)
                self.states[networkState.getIndex()].applianceStates[applianceNr]=state
            elif networkState.getRealPower()-self.groundRealPower()<previousState.applianceStates[applianceNr].getRealPower()-2*deviationRealNew and state.getIndex()==0:
                #print "NOK " +str(state.getRealPower())
                if 5.61>relativeError:
                    self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " NOMissedEdge")
                    sufficient=distance(difRealPower,difReactivePower)
                    
                    self.states[networkState.getIndex()].applianceStates=[]
                    for applianceNr2 in range(len(self.appliances)):
                        if networkState.getIndex()==0:
                            applianceState=self.appliances[applianceNr2].getState(0)
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                        else:
                            applianceState=previousState.applianceStates[applianceNr2]
                            self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    self.states[networkState.getIndex()].applianceStates[applianceNr]=state
                else:
                    self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " MissedEdge")
                    #self.states[networkState.getIndex()].applianceStates=[]
                    #for applianceState in previousState.applianceStates:
                    #    self.states[networkState.getIndex()].applianceStates.append(applianceState)
                    missed.append(self.appliances[applianceNr])
                    #return True
        return [sufficient,missed]
    def estimate_11_missed(self,networkState,missed=[]):
        for applianceNr in range(len(self.appliances)):
            state=self.appliances[applianceNr].states[0]
            oldState= networkState.applianceStates[applianceNr]
            if not (state==networkState.applianceStates[applianceNr]):
                if distance(networkRealPower, networkReactivePower) > distance(networkRealPower,networkReactivePower,state.getRealPower()-oldState.getRealPower(), state.getReactivePower()-oldState.getReactivePower()):
                    [realReamainder,reactiveRemainder]=networkStateRemainders(self,networkState)
                    if -realReamainder>oldState.getRealPower()+2*oldState.getRealPowerDeviation() :
                        self.write("   OK"+str(applianceNr)+ " "+str(state.getRealPower())+ " MissedEdge")
                        missed.append(self.appliances[applianceNr])
        return missed
    #Closest ADDITIVE 2 state change+missed
    def estimate_12(self,networkState,previousState=None,allowedDeviation=0,allowedProbability=0):
        self.states[networkState.getIndex()].applianceStates=[]
        missed=[]
        if not previousState==None:
            for applianceState in previousState.applianceStates:
                self.states[networkState.getIndex()].applianceStates.append(applianceState)
            networkRealPower = networkState.getStartRealPower() - previousState.getStopRealPower()
            networkReactivePower = networkState.getStartReactivePower() - previousState.getStopReactivePower()   
        else:
            previousState=networkState
            for appliance in self.appliances:
                #previousState.applianceStates.append(appliance.getState(0))
                self.states[networkState.getIndex()].applianceStates.append(appliance.getState(0))
            networkRealPower = networkState.getStartRealPower() - self.groundRealPower()
            networkReactivePower = networkState.getStartReactivePower() - self.groundReactivePower()
            #start=True
            
        [variationReal,variationReactive]=self.states[networkState.getIndex()].getTotalVariation()
        sufficient=distance(networkRealPower, networkReactivePower)
        if (allowedProbability==0):
            allowedRealPower=2*networkState.getRealPowerDeviation()/ math.sqrt(networkState.getDuration())
            allowedReactivePower=2*networkState.getReactivePowerDeviation() / math.sqrt(networkState.getDuration())
            allowedProbability= scipy.stats.norm(0, math.sqrt(variationReal)).pdf(allowedRealPower) * scipy.stats.norm(0,math.sqrt(variationReactive)).pdf(allowedReactivePower)
        self.write( "   power " + str(networkRealPower)+ " = " +str(networkState.getStartRealPower()) + " - "+ str(previousState.getStopRealPower()))
        
        for applianceNrMain in range(len(self.appliances)):
            for stateNrMain in  list(reversed(range(len(self.appliances[applianceNrMain].states)))):
                stateMain=self.appliances[applianceNrMain].states[stateNrMain]
                if not (stateMain==previousState.applianceStates[applianceNrMain]):
                    self.write("   appliancePower " + str(stateMain.getRealPower()-previousState.applianceStates[applianceNrMain].getRealPower()))
                    if (networkRealPower < 0 and stateMain.getRealPower()<previousState.applianceStates[applianceNrMain].getRealPower()) or (networkRealPower > 0 and stateMain.getRealPower()>previousState.applianceStates[applianceNrMain].getRealPower()):
                        [sufficientNew,missed]= self.estimate_11_sub(networkState,previousState,sufficient, missed, networkRealPower, networkReactivePower, applianceNrMain, stateMain)
                        if sufficientNew<sufficient:
                            sufficient=sufficientNew
                        else:
                            difRealPower=networkRealPower-(stateMain.getRealPower()-previousState.applianceStates[applianceNrMain].getRealPower())
                            difReactivePower=networkReactivePower-(stateMain.getReactivePower()-previousState.applianceStates[applianceNrMain].getReactivePower())
                            for applianceNr in range(applianceNrMain+1,len(self.appliances)):
                                for stateNr in  list(reversed(range(len(self.appliances[applianceNr].states)))):
                                    state=self.appliances[applianceNr].states[stateNr]
                                    if not (state==previousState.applianceStates[applianceNr]):
                                        self.write("   appliancePowerRemaining " + str(state.getRealPower()-previousState.applianceStates[applianceNr].getRealPower()))
                                        if (difRealPower<0 and state.getRealPower()<previousState.applianceStates[applianceNr].getRealPower()) or (difRealPower>0 and state.getRealPower()>previousState.applianceStates[applianceNr].getRealPower()):
                                            [sufficientNew,dummy]= self.estimate_11_sub(networkState,previousState,sufficient, [], difRealPower, difReactivePower, applianceNr, state)
                                            if sufficientNew<sufficient:
                                                self.write("   OK"+str(applianceNrMain)+ " "+str(stateMain.getRealPower())+ " DualEdge")
                                                self.states[networkState.getIndex()].applianceStates[applianceNrMain]=stateMain
                                                self.states[networkState.getIndex()].setAnomaly("DualEdge"+str(applianceNrMain))
                                                self.states[networkState.getIndex()].setAnomaly("DualEdge"+str(applianceNr))
                                                sufficient=sufficientNew
                            
        for appliance in missed:
            
            self.states[networkState.getIndex()].setAnomaly("MissedEdge"+str(appliance.getIndex()))
            self.states[networkState.getIndex()].applianceStates[appliance.getIndex()]=appliance.getState(0)
            
        return sufficient<5.61
    
    
    
    
    
    
    
    
    #Update All appliances
    def update(self,algorithm=None):
        self.write("UPDATE")
        if algorithm==None:
            algorithm=self.algorithmUpdate
        if (algorithm==1):
            return self.update_1()
        elif (algorithm==2):
            return self.update_2()
        else:
            return None
    
    def update_1(self):
        #updateGround
        if len(self.ground)>2:
            real=0
            reactive=0
            duration=0
            for networkState in self.states:
                if not networkState.isAnomaly():
                    real+=networkState.remainders()[0]*networkState.getDuration()
                    reactive+=networkState.remainders()[1]*networkState.getDuration()
                    duration+=networkState.getDuration()
            real=real/duration
            reactive=reactive/duration
            self.setGround(real,reactive)
            
        #updateAppliancePower
        
        appNr=0
        while appNr < len(self.appliances):
            
            durations=[]
            duration=0
            for networkState in self.states:
                if self.appliances[appNr].states[0]==networkState.applianceStates[appNr]:
                    duration+=networkState.getDuration()
                elif not duration == 0:
                    durations.append(duration)
                    duration=0
            if not duration == 0:
                durations.append(duration)
            self.appliances[appNr].states[0].fit(durations)
            
 
            for appStateNr in range(1,len(self.appliances[appNr].states)):
                realPower=0
                reactivePower=0
                durations=[]
                duration=0
                
                for networkState in self.states:
                    if self.appliances[appNr].states[appStateNr]==networkState.applianceStates[appNr]:
                        duration+=networkState.getDuration()
                        realPower=networkState.remainders()[0]*networkState.duration/networkState.applianceCount()
                        reactivePower=networkState.remainders()[1]*networkState.duration/networkState.applianceCount()
                    elif not duration == 0:
                        durations.append(duration)
                        duration=0
                if not duration == 0:
                    durations.append(duration)
                self.appliances[appNr].states[0].fit(durations)
                if len(durations) == 0:
                    if not len(self.appliances[appNr].getStates())>2:
                        self.appliances[appNr].removeApplianceState(appStateNr)
                        appNr-=1
                    else:
                        self.appliances[appNr].removeApplianceState(appStateNr)
                else:
                    self.appliances[appNr].states[appStateNr].addRealPower(realPower/sum(durations))
                    self.appliances[appNr].states[appStateNr].addReactivePower(reactivePower/sum(durations))
            appNr+=1
         
        #updateApplianceDeviation
        appNr=0
        while appNr < len(self.appliances):
            for appStateNr in range(1,len(self.appliances[appNr].states)):
                realPowerDeviation=0
                reactivePowerDeviation=0
                duration=0
                for networkState in self.states:
                    if self.appliances[appNr].states[appStateNr]==networkState.applianceStates[appNr]:
                        duration+=networkState.duration
                        realPowerDeviation=((networkState.remainders()[0]/networkState.applianceCount())**2)*networkState.duration
                        reactivePowerDeviation=((networkState.remainders()[1]/networkState.applianceCount())**2)*networkState.duration
                if duration == 0:
                    if not len(self.appliances[appNr].getStates())>2:
                        self.appliances[appNr].removeApplianceState(appStateNr)
                        appNr-=1
                    else:
                        self.appliances[appNr].removeApplianceState(appStateNr)
                else:
                    self.appliances[appNr].states[appStateNr].setRealPowerDeviation(math.sqrt(realPowerDeviation/duration))
                    self.appliances[appNr].states[appStateNr].setReactivePowerDeviation(math.sqrt(reactivePowerDeviation/duration))
            appNr+=1
        
        
        
        #update appliace ON distribution over time
        if not self.day == 0:
            referenceTimeArray=[0]*24
            timeArray=[]
            for applianceNr in range(len(self.appliances)):
                timeArray.append([])
                for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                    timeArray[applianceNr].append([0]*24)
                
            for networkState in self.states:
                [hours,minutes,seconds]= networkState.getStartTimeArray()
                seconds+=minutes*60
                duration=networkState.getDuration()
                while duration+seconds>3600:
                    referenceTimeArray[hours]+=3600-seconds
                    for applianceNr in range(len(self.appliances)):
                        for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                            if networkState.getApplianceState(applianceNr) == self.appliances[applianceNr].getState(appStateNr):
                                timeArray[applianceNr][appStateNr-1][hours]+=3600-seconds
                    duration=duration-(3600-seconds)
                    seconds=0
                    hours+=1
                    while hours >= 24:
                        hours-=24

                referenceTimeArray[hours]+=duration 
                for applianceNr in range(len(self.appliances)):
                    for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                        if networkState.getApplianceState(applianceNr) == self.appliances[applianceNr].getState(appStateNr):
                             timeArray[applianceNr][appStateNr-1][hours]+=duration
            
            for applianceNr in range(len(self.appliances)):
                for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                    for hours in range(24):
                        if not referenceTimeArray[hours]==0:
                            timeArray[applianceNr][appStateNr-1][hours]/=sum(timeArray[applianceNr][appStateNr-1])
                    self.appliances[applianceNr].states[appStateNr].setTimeProbabilities(timeArray[applianceNr][appStateNr-1])
        
        
        
        #update appliace distribution over other appliance
        if len(self.appliances)>=2:
            for applianceNr in range(len(self.appliances)):
                for appState in self.appliances[applianceNr].getStates():
                    durations=[]
                    referenceDuration=0
                    for appliance2Nr in range(len(self.appliances)):
                        durations.append([])
                        for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                            durations[appliance2Nr].append(0)
                    for  networkState in self.states:
                        if networkState.getApplianceState(applianceNr) == appState:
                            referenceDuration+=networkState.getDuration()
                            for appliance2Nr in range(applianceNr+1,len(self.appliances)):
                                for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                                    if networkState.getApplianceState(appliance2Nr) == self.appliances[appliance2Nr].getState(appState2Nr):
                                        durations[appliance2Nr][appState2Nr]+=networkState.getDuration()
                    for appliance2Nr in range(len(self.appliances)):
                        for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                            durations[appliance2Nr][appState2Nr]/=referenceDuration
                    appState.setApplianceProbabilities(durations)
                               
        # Check Type II
        
        return None
    
    
    def updatePowerDeviationAdditive(self,appNr,appStateNr):
        appState=self.appliances[appNr].states[appStateNr]
        realPower=0
        reactivePower=0
        count=0

        for networkStateNr in range(len(self.states)):
            networkState=self.states[networkStateNr]
            if not (networkState.isAnomaly("OutOfBounds") or networkState.isAnomaly("MissedEdge"+str(appNr)) or networkState.isAnomaly("DualEdge"+str(appNr))):
                difNr=1
                previousState=networkState
                while difNr<=networkStateNr:
                    if not self.states[networkStateNr-difNr].isAnomaly("OutOfBounds"):
                        previousState=self.states[networkStateNr-difNr]
                        #networkRealPower-=previousState.getStopRealPower()
                        #networkReactivePower-=previousState.getStopReactivePower()
                        difNr=networkStateNr
                    difNr+=1
                [networkRealPower,networkReactivePower]= self.networkStateRemaindersDifference(networkState,previousState)
                #networkRealPower=networkState.getStartRealPower()
                #networkReactivePower=networkState.getStartReactivePower()
                #if networkState==previousState:
                #    networkRealPower-=self.groundRealPower()
                #    networkReactivePower-=self.groundReactivePower()
                #sign=networkRealPower/abs(networkRealPower)
                #networkReactivePower*=sign
                #networkRealPower*=sign

                if appState==networkState.applianceStates[appNr]:
                    if networkState==previousState or appStateNr>previousState.applianceStates[appNr].getIndex():
                        applianceCount=networkState.applianceCountDifference(previousState)
                        realPowerAdd=networkRealPower/applianceCount
                        realPower+=realPowerAdd**2+networkState.getRealPowerDeviation()**2
                        reactivePowerAdd=networkReactivePower/applianceCount
                        reactivePower+=reactivePowerAdd**2+networkState.getReactivePowerDeviation()**2
                        count+=1
                        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
       
                elif (appState==previousState.applianceStates[appNr]):
                    if appStateNr>networkState.applianceStates[appNr].getIndex():
                        applianceCount=networkState.applianceCountDifference(previousState)
                        realPowerAdd=networkRealPower/applianceCount
                        realPower+=realPowerAdd**2+networkState.getRealPowerDeviation()**2
                        reactivePowerAdd=networkReactivePower/applianceCount
                        reactivePower+=reactivePowerAdd**2+networkState.getReactivePowerDeviation()**2
                        count+=1
                        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
                #if appState==networkState.applianceStates[appNr]:
                #    
                #    if networkState==previousState:
                #        realPowerAdd=networkRealPower-appState.getRealPower()
                #        #realPowerAdd=min(abs(realPowerAdd),1.64*appState.getRealPowerDeviation())
                #        #realPowerAdd=min(abs(realPowerAdd),max(4,networkState.getRealPowerDeviation()*math.sqrt(8)))
                #        realPower+=realPowerAdd**2+networkState.getRealPowerDeviation()**2
                #        reactivePowerAdd=networkReactivePower-appState.getReactivePower()
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),1.64*appState.getReactivePowerDeviation())
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),max(4,networkState.getReactivePowerDeviation()*math.sqrt(8)))
                #        reactivePower+=reactivePowerAdd**2+networkState.getReactivePowerDeviation()**2
                #        count+=1
                #        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
                #    elif appStateNr>previousState.applianceStates[appNr].getIndex():
                #        realPowerAdd=(networkRealPower-(appState.getRealPower()-previousState.applianceStates[appNr].getRealPower()))
                #        #realPowerAdd=min(abs(realPowerAdd),1.64*appState.getRealPowerDeviation())
                #        #realPowerAdd=min(abs(realPowerAdd),max(4,networkState.getRealPowerDeviation()*math.sqrt(8)))
                #        realPower+=realPowerAdd**2+networkState.getRealPowerDeviation()**2
                #        reactivePowerAdd=(networkReactivePower-(appState.getReactivePower()-previousState.applianceStates[appNr].getReactivePower()))
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),1.64*appState.getReactivePowerDeviation())
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),max(4,networkState.getReactivePowerDeviation()*math.sqrt(8)))
                #        reactivePower+=reactivePowerAdd**2+networkState.getReactivePowerDeviation()**2
                #        count+=1
                #        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
                #elif (appState==previousState.applianceStates[appNr]):
                #    if appStateNr>networkState.applianceStates[appNr].getIndex():
                #        realPowerAdd=(networkRealPower-(appState.getRealPower()-networkState.applianceStates[appNr].getRealPower()))
                #        #realPowerAdd=min(abs(realPowerAdd),1.64*appState.getRealPowerDeviation())
                #        #realPowerAdd=min(abs(realPowerAdd),max(4,networkState.getRealPowerDeviation()*math.sqrt(8)))
                #        realPower+=realPowerAdd**2+networkState.getRealPowerDeviation()**2
                #        reactivePowerAdd=(networkReactivePower-(appState.getReactivePower()-networkState.applianceStates[appNr].getReactivePower()))
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),1.64*appState.getReactivePowerDeviation())
                #        #reactivePowerAdd=min(abs(reactivePowerAdd),max(4,networkState.getReactivePowerDeviation()*math.sqrt(8)))
                #        reactivePower+=reactivePowerAdd**2+networkState.getReactivePowerDeviation()**2
                #        count+=1
                #        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
        if (count) == 0:
            if not len(self.appliances[appNr].getStates())>2:
                self.appliances[appNr].removeApplianceState(appStateNr)
                appNr-=1
            else:
                self.appliances[appNr].removeApplianceState(appStateNr)
                appStateNr-=1
        else:
            self.appliances[appNr].states[appStateNr].setRealPowerDeviation( math.sqrt(realPower/count))
            self.appliances[appNr].states[appStateNr].setReactivePowerDeviation( math.sqrt(reactivePower/count))
        return [appNr,appStateNr+1]
    
    def updatePowerAverageAdditive(self,appNr,appStateNr):
        
        appState=self.appliances[appNr].states[appStateNr]
        realPower=0
        reactivePower=0
        count=0
        for networkStateNr in range(len(self.states)):
            networkState=self.states[networkStateNr]
            if not (networkState.isAnomaly("OutOfBounds") or networkState.isAnomaly("MissedEdge"+str(appNr))or networkState.isAnomaly("DualEdge"+str(appNr))):
                difNr=1
                previousState=networkState
                while difNr<=networkStateNr:
                    if not self.states[networkStateNr-difNr].isAnomaly("OutOfBounds"):
                        previousState=self.states[networkStateNr-difNr]
                        #networkRealPower-=previousState.getStopRealPower()
                        #networkReactivePower-=previousState.getStopReactivePower()
                        difNr=networkStateNr
                    difNr+=1
                [networkRealPower,networkReactivePower]= self.networkStateRemaindersDifference(networkState,previousState)
                #networkRealPower=networkState.getStartRealPower()
                #networkReactivePower=networkState.getStartReactivePower()
                #if networkState==previousState:
                #    networkRealPower-=self.groundRealPower()
                #    networkReactivePower-=self.groundReactivePower()
                #sign=networkRealPower/abs(networkRealPower)
                #networkReactivePower*=sign
                #networkRealPower*=sign

                if appState==networkState.applianceStates[appNr]:
                    if networkState==previousState or appStateNr>previousState.applianceStates[appNr].getIndex():
                        applianceCount=networkState.applianceCountDifference(previousState)
                        realPowerAdd=networkRealPower/applianceCount
                        realPower+=realPowerAdd
                        reactivePowerAdd=networkReactivePower/applianceCount
                        reactivePower+=reactivePowerAdd
                        count+=1
                        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
       
                elif (appState==previousState.applianceStates[appNr]):
                    if appStateNr>networkState.applianceStates[appNr].getIndex():
                        applianceCount=networkState.applianceCountDifference(previousState)
                        realPowerAdd=networkRealPower/applianceCount
                        realPower-=realPowerAdd
                        reactivePowerAdd=networkReactivePower/applianceCount
                        reactivePower-=reactivePowerAdd
                        count+=1
                        self.write(str(count)+": "+str(realPowerAdd)+"; "+str(reactivePowerAdd))
        if (count) == 0:
            if not len(self.appliances[appNr].getStates())>2:
                self.appliances[appNr].removeApplianceState(appStateNr)
                appNr-=1
            else:
                self.appliances[appNr].removeApplianceState(appStateNr)
                appStateNr-=1
        else:
            self.appliances[appNr].states[appStateNr].addRealPower(realPower/count)
            self.appliances[appNr].states[appStateNr].addReactivePower(reactivePower/count)
        return [appNr,appStateNr+1]
    
    def update_2(self):
        #updateGround
        if len(self.ground)>2:
            real=0
            reactive=0
            duration=0
            for networkState in self.states:
                if not networkState.isAnomaly():
                    if self.isEstimated(networkState):
                        real+=networkState.remainders()[0]*networkState.getDuration()
                        reactive+=networkState.remainders()[1]*networkState.getDuration()
                        duration+=networkState.getDuration()
            if not duration==0:
                real=real/duration
                reactive=reactive/duration
            self.setGround(real,reactive)
            
        #updateAppliancePower
        
        appNr=0
        while appNr < len(self.appliances):
            self.write("Appliance "+ str(appNr))
            
            
            appStateNr=0
            while appStateNr < len(self.appliances[appNr].states):
                #updateApplianceDurationDistribution
                durations=[]
                duration=0
                for networkState in self.states:
                    if self.appliances[appNr].states[appStateNr]==networkState.applianceStates[appNr]:
                        duration+=networkState.getDuration()
                    elif not duration == 0:
                        durations.append(duration)
                        duration=0
                if not duration == 0:
                    durations.append(duration)
                self.appliances[appNr].states[appStateNr].fit(durations)
                self.write( "Shape "+str(self.appliances[appNr].states[appStateNr].shape)+" and scale " +str(self.appliances[appNr].states[appStateNr].scale))
                #updateAppliancePower
                if not appStateNr ==0:
                    [appNr,appStateNr]=self.updatePowerAverageAdditive(appNr,appStateNr)
                else:
                    appStateNr=1
            appNr+=1
         
        #updateApplianceDeviation
        appNr=0
        while appNr < len(self.appliances):
            self.write("Appliance  "+ str(appNr))
            appStateNr=1
            while appStateNr < len(self.appliances[appNr].states):
                [appNr,appStateNr]=self.updatePowerDeviationAdditive(appNr,appStateNr)
            appNr+=1
        
        
        
        #update appliace ON distribution over time
        if not self.day == 0:
            referenceTimeArray=[0]*24
            timeArray=[]
            for applianceNr in range(len(self.appliances)):
                timeArray.append([])
                for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                    timeArray[applianceNr].append([0]*24)
                
            for networkState in self.states:
                
                [hours,minutes,seconds]= networkState.getStartTimeArray()
                seconds+=minutes*60
                duration=networkState.getDuration()
                while duration+seconds>3600:
                    referenceTimeArray[hours]+=3600-seconds
                    for applianceNr in range(len(self.appliances)):
                        for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                            if networkState.getApplianceState(applianceNr) == self.appliances[applianceNr].getState(appStateNr):
                                timeArray[applianceNr][appStateNr-1][hours]+=3600-seconds
                    duration=duration-(3600-seconds)
                    seconds=0
                    hours+=1
                    while hours >= 24:
                        hours-=24

                referenceTimeArray[hours]+=duration 
                for applianceNr in range(len(self.appliances)):
                    for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                        if networkState.getApplianceState(applianceNr) == self.appliances[applianceNr].getState(appStateNr):
                             timeArray[applianceNr][appStateNr-1][hours]+=duration
            
            for applianceNr in range(len(self.appliances)):
                for appStateNr in range(1,len(self.appliances[applianceNr].getStates())):
                    for hours in range(24):
                        if not referenceTimeArray[hours]==0:
                            timeArray[applianceNr][appStateNr-1][hours]/=sum(timeArray[applianceNr][appStateNr-1])
                    self.appliances[applianceNr].states[appStateNr].setTimeProbabilities(timeArray[applianceNr][appStateNr-1])
        
        
        
        #update appliace distribution over other appliance
        if len(self.appliances)>=2:
            for applianceNr in range(len(self.appliances)):
                for appState in self.appliances[applianceNr].getStates():
                    durations=[]
                    referenceDuration=0
                    for appliance2Nr in range(len(self.appliances)):
                        durations.append([])
                        for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                            durations[appliance2Nr].append(0)
                    for  networkState in self.states:
                        if networkState.getApplianceState(applianceNr) == appState:
                            referenceDuration+=networkState.getDuration()
                            for appliance2Nr in range(applianceNr+1,len(self.appliances)):
                                for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                                    if networkState.getApplianceState(appliance2Nr) == self.appliances[appliance2Nr].getState(appState2Nr):
                                        durations[appliance2Nr][appState2Nr]+=networkState.getDuration()
                    for appliance2Nr in range(len(self.appliances)):
                        for appState2Nr in range(len(self.appliances[appliance2Nr].getStates())):
                            durations[appliance2Nr][appState2Nr]/=referenceDuration
                    if len(durations)>5:
                        appState.setApplianceProbabilities(durations)
                               
        # Check Type II
        if len(self.appliances)>=2:
            typeTwo=[]
            for applianceNr in range(len(self.appliances)):
                appliance=self.appliances[applianceNr]
                for appState in appliance.getStates()[1:]:
                    previouState=self.states[0]
                    edgeCount=0
                    missedEdgeCount=0
                    for networkStateNr in range(1,len(self.states)):
                        networkState=self.states[networkStateNr]
                        
                        if not networkState.getApplianceState(applianceNr)==previouState.getApplianceState(applianceNr):
                            if previouState.getApplianceState(applianceNr)==appState:
                                edgeCount+=1
                                if networkState.isAnomaly("MissedEdge"+str(applianceNr))or networkState.isAnomaly("DualEdge"+str(applianceNr)):
                                    missedEdgeCount+=1
                            elif networkState.getApplianceState(applianceNr)==appState:
                                edgeCount+=1
                        previouState=networkState
                    self.write( str(applianceNr)+": "+str(edgeCount) +" T2 "+str(missedEdgeCount))
                    if  edgeCount>8 and missedEdgeCount>=max(edgeCount/8,4):
                        found=False
                        for element in typeTwo:
                            if element[0]==appliance:
                                element[1]+=missedEdgeCount
                                element[2]+=edgeCount
                                found=True
                        if not found:
                            typeTwo.append([appliance,missedEdgeCount,edgeCount])

            if len(typeTwo)>=2:
                
                for i1 in range(len(typeTwo)-1):
                    applianceA=typeTwo[i1][0]
                    applianceANr=applianceA.getIndex()
                    for i2 in range(i1+1,len(typeTwo)):
                        applianceB=typeTwo[i2][0]
                        applianceBNr=applianceB.getIndex()
                         #missedEdgeCountRef=(typeTwo[i1][1]+typeTwo[i2][1])
                        missedEdgeCountRef=(min(typeTwo[i1][1],typeTwo[i2][1]*1.5)+min(typeTwo[i1][1]*1.5,typeTwo[i2][1]))
                        #missedEdgeCountRef=(math.sqrt(typeTwo[i1][1]/2)+math.sqrt(typeTwo[i2][1]/2))**2
                        edgeCountRef=typeTwo[i1][2]+typeTwo[i2][2]
                        missedEdgeCountSuficient=missedEdgeCountRef*3/(edgeCountRef*4)
                        self.write("TwoRef "+str(applianceANr)+" "+str(applianceBNr)+" : " + str(missedEdgeCountRef) + " / " + str(edgeCountRef)+ " > ")
                        applianceStatesNewBest=None
                        applianceStatesOld=[]
                        for applianceState in applianceA.getStates():
                            applianceStatesOld.append(applianceState) 
                        applianceStatesNew=[]
                        for applianceState in applianceB.getStates()[1:]:
                            applianceStatesNew.append(applianceState) 
                                  
                        missedEdgeCount=self.estimateTypeTwoAdditive(applianceStatesOld,applianceStatesNew,missedEdgeCountSuficient)
                        if missedEdgeCount < missedEdgeCountSuficient:
                            missedEdgeCountSuficient=missedEdgeCount
                            applianceStatesNewBest=applianceStatesNew
                            
                        if len(applianceB.getStates())==2:
                            if len(applianceA.getStates())>2:
                                [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_1(applianceA,applianceB, missedEdgeCountSuficient,applianceStatesNewBest)
                            [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_2(applianceA,applianceB, missedEdgeCountSuficient,applianceStatesNewBest)
                            [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_3(applianceA,applianceB, missedEdgeCountSuficient,applianceStatesNewBest)
                        if len(applianceA.getStates())==2:
                            if len(applianceB.getStates())>2:
                                [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_1(applianceB,applianceA, missedEdgeCountSuficient,applianceStatesNewBest)
                            [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_2(applianceB,applianceA, missedEdgeCountSuficient,applianceStatesNewBest)
                            [missedEdgeCountSuficient,applianceStatesNewBest]= self.updateTypeTwoAdditive_3(applianceB,applianceA, missedEdgeCountSuficient,applianceStatesNewBest)
                        
                        if missedEdgeCountSuficient<missedEdgeCountRef*3/(edgeCountRef*4):
                            applianceNewNr=applianceStatesNewBest[0].getIndexAppliance()
                            
                            for applianceState in list(reversed(applianceStatesNewBest)):
                                self.appliances[applianceNewNr].removeApplianceState(applianceState.getIndex())
                                if applianceB.getIndex()==applianceNewNr:
                                    applianceOldNr=applianceA.getIndex()
                                else:
                                    applianceOldNr=applianceB.getIndex()
                                self.appliances[applianceOldNr].addApplianceState(applianceState)
                            print"TYPE II"
                            self.estimateFull()
                            self.update()
                            self.plotNetworkStatesAdditive()
                            return True     
                        
                    
        return None
    
    #all of B and ALL of A+B (B has to be Type I)
    def updateTypeTwoAdditive_1(self,applianceA,applianceB,missedEdgeCountSuficient,applianceStatesNewBest):
        applianceStatesOld=[applianceB.getState(0)] 
        applianceStatesOld.append(applianceB.getState(1))
        applianceStatesCumulative=[]
        for applianceState in applianceA.getStates()[1:]:
            applianceStateNew=applianceState.copy()
            applianceStateNew.addPower(applianceB.getState(1).getPower())
            #applianceStateNew.addDeviation(applianceB.getState(1).getDeviation())
            applianceStateNew.combineDeviation(applianceB.getState(1).getDeviation())
            applianceStatesCumulative.append(applianceStateNew)
        missedEdgeCount=self.estimateTypeTwoAdditive(applianceStatesOld,applianceStatesCumulative,missedEdgeCountSuficient,"++ ")
        if missedEdgeCount < missedEdgeCountSuficient:
            self.write("Type II")
            missedEdgeCountSuficient=missedEdgeCount
            applianceStatesNewBest=applianceStatesCumulative
        return [missedEdgeCountSuficient,applianceStatesNewBest]
   
    
    #all of A and ONE of A+B (B has to be Type I)
    def updateTypeTwoAdditive_2(self,applianceA,applianceB,missedEdgeCountSuficient,applianceStatesNewBest):
        for applianceStatesCumulative in applianceA.getStates()[1:]:
            applianceStates=[] 
            for applianceState in applianceA.getStates():
                applianceStates.append(applianceState) 
            applianceStateNew=applianceB.getState(1).copy()
            applianceStateNew.addPower(applianceStatesCumulative.getPower())
            #applianceStateNew.addDeviation(applianceStatesCumulative.getDeviation())
            applianceStateNew.combineDeviation(applianceStatesCumulative.getDeviation())
            missedEdgeCount=self.estimateTypeTwoAdditive(applianceStates,[applianceStateNew],missedEdgeCountSuficient," + ")
            if missedEdgeCount < missedEdgeCountSuficient:
                self.write("Type II")
                missedEdgeCountSuficient=missedEdgeCount
                applianceStatesNewBest=[applianceStateNew]
        return [missedEdgeCountSuficient,applianceStatesNewBest]
       
    #all of A and ONE of A-B (B has to be Type I)
    def updateTypeTwoAdditive_3(self,applianceA,applianceB,missedEdgeCountSuficient,applianceStatesNewBest):
        for applianceStatesCumulative in applianceA.getStates()[1:]:
            if applianceStatesCumulative.getRealPower()>applianceB.getState(1).getRealPower():
                applianceStates=[] 
                for applianceState in applianceA.getStates():
                    applianceStates.append(applianceState) 
                applianceStateNew=applianceB.getState(1).negativeCopy()
                applianceStateNew.addPower(applianceStatesCumulative.getPower())
                #applianceStateNew.addDeviation(applianceStatesCumulative.getDeviation())
                applianceStateNew.combineDeviation(applianceStatesCumulative.getDeviation())
                missedEdgeCount=self.estimateTypeTwoAdditive(applianceStates,[applianceStateNew],missedEdgeCountSuficient," - ")
                if missedEdgeCount < missedEdgeCountSuficient:
                    self.write("Type II")
                    missedEdgeCountSuficient=missedEdgeCount
                    applianceStatesNewBest=[applianceStateNew]
        return [missedEdgeCountSuficient,applianceStatesNewBest]
    
    def estimateTypeTwoAdditive(self,applianceStatesOld,applianceStatesNew,missedEdgeCountSuficient,symbol=" & "):
        applianceStates=sortApplianceStates(applianceStatesOld+applianceStatesNew)  
        applianceNrs=[]
        for state in applianceStates:
            if not state.getIndexAppliance() in applianceNrs:
                applianceNrs.append(state.getIndexAppliance())
        count=[0]*int((len(applianceStates)*(len(applianceStates)-1)/2))
        missedCount=0
        currentStateNr=0
        currentState=applianceStates[currentStateNr]
        for networkStateNr in range(len(self.states)):
            if not self.states[networkStateNr].isAnomaly("OutOfBounds"):
                networkState=self.states[networkStateNr]
                self.write(networkState.printStr())
                difNr=1
                previousState=networkState
                while difNr<=networkStateNr:
                    if not self.states[networkStateNr-difNr].isAnomaly("OutOfBounds"):
                        previousState=self.states[networkStateNr-difNr]
                        difNr=networkStateNr
                    difNr+=1
                [networkRealPower,networkReactivePower]= self.networkStateRemaindersDifference(networkState,previousState,applianceNrs)
                error=distance(networkRealPower,networkReactivePower)
                sufficient=False
                if networkRealPower>0:
                    for applianceStateNr in range(currentStateNr+1,len(applianceStates)):
                        applianceState=applianceStates[applianceStateNr]
                        realPower=applianceState.getRealPower()-currentState.getRealPower()
                        reactivePower=applianceState.getReactivePower()-currentState.getReactivePower()
                        realPowerDeviation=applianceState.getRealPowerDeviation()
                        reactivePowerDeviation=applianceState.getReactivePowerDeviation()
                        if error>distance(networkRealPower,networkReactivePower,realPower,reactivePower):
                            relativeRealError=math.sqrt(((networkRealPower-realPower)**2)/ (realPowerDeviation**2+self.deviationRealPower()**2))
                            relativeReactiveError=math.sqrt(((networkReactivePower-reactivePower)**2)/ (reactivePowerDeviation**2+self.deviationReactivePower()**2))
                            relativeError=distance(relativeRealError,relativeReactiveError)
                            if 4 >  relativeError:
                                sufficient=True
                                self.write( "    OK+ =" + str(networkRealPower-realPower)+" "+str(networkReactivePower-reactivePower)+ " " +str(relativeError))
                                tempStateNr=applianceStateNr
                                error=distance(networkRealPower,networkReactivePower,realPower,reactivePower)
                            else:
                                self.write( "    NO+ =" + str(networkRealPower-realPower)+" "+str(networkReactivePower-reactivePower)+ " " +str(relativeError))

                    if sufficient:
                        count[int(len(count)-(len(applianceStates)-currentStateNr)*(len(applianceStates)-(currentStateNr+1))/2+tempStateNr-(currentStateNr+1))]+=1
                        currentStateNr=tempStateNr
                        currentState=applianceStates[currentStateNr]
                     
                else:
                    error=distance(networkRealPower,networkReactivePower)
                    for applianceStateNr in list(reversed(range(0,currentStateNr))):
                        applianceState=applianceStates[applianceStateNr]
                        realPower=applianceState.getRealPower()-currentState.getRealPower()
                        reactivePower=applianceState.getReactivePower()-currentState.getReactivePower()
                        realPowerDeviation= currentState.getRealPowerDeviation()
                        reactivePowerDeviation=currentState.getReactivePowerDeviation()
                        if error>distance(networkRealPower,networkReactivePower,realPower,reactivePower):
                            relativeRealError=math.sqrt(((networkRealPower-realPower)**2)/ (realPowerDeviation**2+self.deviationRealPower()**2))
                            relativeReactiveError=math.sqrt(((networkReactivePower-reactivePower)**2)/ (reactivePowerDeviation**2+self.deviationReactivePower()**2))
                            relativeError=distance(relativeRealError,relativeReactiveError)
                            if 5.61 >  relativeError:
                                sufficient=True
                                self.write( "    OK- =" + str(networkRealPower-realPower)+" "+str(networkReactivePower-reactivePower)+ " " +str(relativeError))
                                tempStateNr=applianceStateNr
                                error=distance(networkRealPower,networkReactivePower,realPower,reactivePower)
                            else:
                                self.write( "    NO- =" + str(networkRealPower-realPower)+" "+str(networkReactivePower-reactivePower)+ " " +str(relativeError))
                    if sufficient:
                        count[int(len(count)-(len(applianceStates)-tempStateNr)*(len(applianceStates)-(tempStateNr+1))/2+currentStateNr-(tempStateNr+1))]+=1
                        currentStateNr=tempStateNr
                        currentState=applianceStates[currentStateNr]
                    elif networkState.getRealPower()-self.groundRealPower()<currentState.getRealPower()-2*currentState.getRealPowerDeviation() and not currentStateNr ==0:
                        missedCount+=1
                        currentStateNr=0
                        currentState=applianceStates[currentStateNr]
                        self.write("MISSED")
        totalCount=sum(count)+missedCount
        
        minCount=hp.nsmallest(max(1,len(applianceStates)-2), count)[-1]
        self.write( str(applianceStatesOld[0].getIndexAppliance())+symbol+ str(applianceStatesNew[0].getIndexAppliance())+ ": "+ str(missedEdgeCountSuficient) +  "> "+ str(missedCount)+" / "+str(totalCount) +" For: "+ str(len(count)) +" Min: "+str(minCount))
        if not totalCount==0:
            missedCount=missedCount/totalCount
        else:
            missedCount=1
        if minCount>max(5,totalCount/25) and missedCount <= missedEdgeCountSuficient:# and totalEdgeCount>(edgeCountRef)*1.2:
            missedEdgeCountSuficient=missedCount
        return missedEdgeCountSuficient






 #Check whether or not a new appliace can be identified
# 1: DBSCAN: Cluster network states (remainder)
# 2: DBSCAN: Cluster difference between consecutive network states
# 3: K-Means: Cluster network states (remainder)
# 4: Agglomerative: Cluster network states (compare networkstate to estimated value)
    def newAppliance(self,eps=4,min_samples=3,amountMin=8,pointsMin=900,VarianceMax=None,algorithm=None):
        if algorithm==None:
            algorithm=self.algorithmNewAppliance
        if not len(self.states)>10*amountMin:
            return False
        if (algorithm==1):
            return self.newAppliance_1(eps,min_samples,amountMin,pointsMin,VarianceMax)
        elif (algorithm==2):
            return self.newAppliance_2(eps,min_samples,amountMin,pointsMin,VarianceMax)
        elif (algorithm==3):
            return self.newAppliance_3(10,25,pointsMin)
        elif (algorithm==4):
            return self.newAppliance_4(10,25,pointsMin)
        elif (algorithm==5):
            return self.newAppliance_5(15,25,pointsMin)
        elif (algorithm==6):
            return self.newAppliance_6(10,25,pointsMin)
        else:
            return None
    
    #returns unassigned real and reactive power of given networkState relative to the ground
    # Note: does NOT equal networkState.remainders()!
    def networkStateRemainders(self,networkState):
        [real,reactive]=networkState.remainders()
        return [real-self.groundRealPower(),reactive-self.groundReactivePower()]
    #returns unassigned real and reactive power of edge between given networkStates relative to the ground
    # I able to hande first networkState
    # ApplainceNr's supplied are NOT taken into account
    def networkStateRemaindersDifference(self,networkState,previousState=None,ApplianceNrs=[]):
        if previousState==None or previousState==networkState:
            [real,reactive]=networkState.getStartValues()
            [estimatedReal,estimatedReactive]=networkState.estimate(ApplianceNrs)
            return [real-estimatedReal-self.groundRealPower(),reactive-estimatedReactive-self.groundReactivePower()]
        else:
            [real,reactive]=networkState.remaindersDifference(previousState,ApplianceNrs)
            return [real,reactive]
        
    def isEstimated(self,networkState):
        [real,reactive]=self.networkStateRemainders(networkState)
        [variationReal,variationReactive]=networkState.getTotalVariation()
        deviationReal=math.sqrt(variationReal)
        deviationReactive=math.sqrt(variationReactive)
        return real<2*deviationReal and reactive<2*deviationReactive
    def isEstimatedDifference(self,networkState,previousState=None,ApplianceNrs=[]):
        [real,reactive]=self.networkStateRemaindersDifference(networkState,previousState,ApplianceNrs)
        if previousState==None or previousState==networkState:
            [variationReal,variationReactive]=networkState.getTotalVariation(ApplianceNrs)
        else:
            [variationReal,variationReactive]=networkState.getTotalVariationDifference(previousState,ApplianceNrs)
        deviationReal=math.sqrt(variationReal)
        deviationReactive=math.sqrt(variationReactive)
        return real<2*deviationReal and reactive<2*deviationReactive
    #returns real and reactive power of given networkState relative to the ground
    def networkStateRelative(self,networkState):
        real=networkState.getRealPower()
        reactive=networkState.getReactivePower()
        return [real-self.groundRealPower(),reactive-self.groundReactivePower()]
    
    def uncathegorized(self,networkState):
        return networkState.probabilityMeasurement()<0.01
    
    #return the array of all insufficiently assigned networkStates
    def clusterData(self):
        X=[]
        Y=[]
        durations=[]
        for i in np.arange(len(self.states)-1):
            state=self.states[i]
            if not state.isAnomaly("OutOfBounds"):
                [networkRealPower,networkReactivePower]=self.networkStateRemainders(state)
                if networkRealPower > (2*self.deviationRealPower() + self.allowedDeviation) or networkReactivePower > (2*self.deviationReactivePower() + self.allowedDeviation):
                    X.append([networkRealPower,networkReactivePower])
                    Y.append(state.getDeviation())
                    durations.append(state.getDuration())
        return [X,Y,durations]
    
    #return the array of all insufficiently assigned networkStates relative to previous networkState
    def clusterDataAdditive(self):
        X=[]
        Y=[]
        durations=[]
        for i in np.arange(0,len(self.states)-1):
            state=self.states[i]
            if not state.isAnomaly("OutOfBounds"):
                ib=1
                oldState=state
                while ib<=i:
                    if not self.states[i-ib].isAnomaly("OutOfBounds"):
                        oldState=self.states[i-ib]
                        ib=i
                    ib+=1
                
                [networkRealPower,networkReactivePower]= self.networkStateRemaindersDifference(state,oldState)
                #if networkRealPower > (2*self.deviationRealPower() + self.allowedDeviation) or networkReactivePower > (2*self.deviationReactivePower() + self.allowedDeviation):
                if not self.isEstimatedDifference(state,oldState):
                    sign=(networkRealPower)/abs(networkRealPower)
                    X.append([(networkRealPower)*sign,(networkReactivePower)*sign])
                    Y.append(state.getDeviation())
                    durations.append(state.getDuration())
        return [X,Y,durations]
    
    def newApplianceCreator(self,X,Y,durations, clusters, top_cluster, pointsMin, amountMin, VarianceMax):
        duration=0;
        for i0 in range(len(clusters)):
            if clusters[i0]==top_cluster:
                duration+= durations[i0]
        if duration>pointsMin:
            #top_cluster_size= counts[top_cluster]
            realPower=0
            reactivePower=0
            for i1 in range(len(clusters)):
                if clusters[i1]==top_cluster:
                    realPower+=X[i1][0]*durations[i1]
                    reactivePower+=X[i1][1]*durations[i1]
            realPower=realPower/duration
            reactivePower=reactivePower/duration

            realPowerVariance=0
            reactivePowerVariance=0
            for i2 in range(len(clusters)):
                if clusters[i2]==top_cluster:
                    realPowerVariance+=((X[i2][0]-realPower)**2+Y[i2][0]**2)*durations[i2]
                    reactivePowerVariance+=((X[i2][1]-reactivePower)**2+Y[i2][1]**2)*durations[i2]
            realPowerVariance=realPowerVariance/duration
            reactivePowerVariance=reactivePowerVariance/duration
            
            
            if realPowerVariance+reactivePowerVariance < VarianceMax:
                if realPower>2*math.sqrt(realPowerVariance):
                    new= self.addAppliance(realPower, math.sqrt(realPowerVariance), reactivePower, math.sqrt(reactivePowerVariance),pointsMin,amountMin)
                    return new
                elif reactivePower>2*math.sqrt(reactivePowerVariance) and realPower>math.sqrt(realPowerVariance):
                    new= self.addAppliance(realPower, math.sqrt(realPowerVariance), reactivePower, math.sqrt(reactivePowerVariance),pointsMin,amountMin)
                    return new
        return False
    def newApplianceCreatorAdditive(self,X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax):
        duration=0;
        for i0 in range(len(clusters)):
            if clusters[i0]==top_cluster:
                duration+= durations[i0]
        if duration>pointsMin:
            #top_cluster_size= counts[top_cluster]
            realPower=0
            reactivePower=0
            for i1 in range(len(clusters)):
                if clusters[i1]==top_cluster:
                    realPower+=X[i1][0]*durations[i1]
                    reactivePower+=X[i1][1]*durations[i1]
            realPower=realPower/duration
            reactivePower=reactivePower/duration

            realPowerVariance=0
            reactivePowerVariance=0
            for i2 in range(len(clusters)):
                if clusters[i2]==top_cluster:
                    realPowerVariance+=((X[i2][0]-realPower)**2+Y[i2][0]**2)*durations[i2]
                    reactivePowerVariance+=((X[i2][1]-reactivePower)**2+Y[i2][1]**2)*durations[i2]
            realPowerVariance=realPowerVariance/duration
            reactivePowerVariance=reactivePowerVariance/duration
            
            
            if realPowerVariance+reactivePowerVariance < VarianceMax:
                if realPower>2*math.sqrt(realPowerVariance)+20:
                    new= self.addApplianceAdditive(realPower, math.sqrt(realPowerVariance), reactivePower, math.sqrt(reactivePowerVariance),pointsMin,amountMin)
                    return new
                elif reactivePower>2*math.sqrt(reactivePowerVariance) and realPower>math.sqrt(realPowerVariance)+10:
                    new= self.addApplianceAdditive(realPower, math.sqrt(realPowerVariance), reactivePower, math.sqrt(reactivePowerVariance),pointsMin,amountMin)
                    return new
        return False
    # DBSCAN: Cluster network states (compare networkstate to estimated value)
    def newAppliance_1(self,eps=0.5,min_samples=5,amountMin=5,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*1000
        [X,Y,durations]=self.clusterData()
        db = DBSCAN(eps, min_samples).fit(X)
        clusters = db.labels_
        counts = np.bincount(clusters[clusters>=0])
        
        nr=0
        top_cluster = np.argsort(-counts)[:1][0]
        #print counts
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreator(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            top_cluster = np.argsort(-counts)[:nr+1][nr]
        return False
    
    # DBSCAN: Cluster additive (compare networkstate to previous networkState)
    def newAppliance_2(self,eps=0.7,min_samples=10,amountMin=5,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*100
        [X,Y,durations]=self.clusterDataAdditive()
        db = DBSCAN(eps, min_samples).fit(X)
        clusters = db.labels_
        #print str(len(X[0])) + "vs" +str(len(clusters))
        #print "Max Cluster: " + str(max(clusters))
        counts = np.bincount(clusters[clusters>=0])
        nr=0
        #print counts
        if nr>=len(counts):
            return False 
        top_cluster = np.argsort(-counts)[:1][0]
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreatorAdditive(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            if nr>=len(counts):
                return False 
            top_cluster = np.argsort(-counts)[nr:nr+1][0]
        return False
    
     # K-Means: Cluster network states (compare networkstate to estimated value)
    def newAppliance_3(self,n_clusters=3,amountMin=15,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*100
        [X,Y,durations]=self.clusterData()
        if len(X)<2*n_clusters:
            return False
        kmeans = KMeans(n_clusters).fit(X)

        clusters = kmeans.labels_
        counts = np.bincount(clusters[clusters>=0])
        #print "Max Cluster: " + str(max(clusters))
        nr=0
        top_cluster = np.argsort(-counts)[:1][0]
        #print counts
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreator(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            top_cluster = np.argsort(-counts)[nr:nr+1][0]
        return False
    # K-Means: Cluster network states (compare networkstate to estimated value)
    def newAppliance_4(self,n_clusters=3,amountMin=15,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*100
        [X,Y,durations]=self.clusterDataAdditive()
        if len(X)<2*n_clusters:
            return False
        kmeans = KMeans(n_clusters).fit(X)

        clusters = kmeans.labels_
        counts = np.bincount(clusters[clusters>=0])
        #print "Max Cluster: " + str(max(clusters))
        nr=0
        top_cluster = np.argsort(-counts)[:1][0]
        #print counts
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreatorAdditive(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            top_cluster = np.argsort(-counts)[:nr+1][nr]
        return False
     # Agglomerative: Cluster network states (compare networkstate to estimated value)
    def newAppliance_5(self,n_clusters=3,amountMin=15,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*100
        [X,Y,durations]=self.clusterData()
        agglomerativeClustering = AgglomerativeClustering(n_clusters).fit(X)

        clusters = agglomerativeClustering.labels_
        counts = np.bincount(clusters[clusters>=0])
        #print "Max Cluster: " + str(max(clusters))
        nr=0
        top_cluster = np.argsort(-counts)[:1][0]
        #print counts
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreator(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            top_cluster = np.argsort(-counts)[:nr+1][nr]
        return False
     # Agglomerative: Cluster network states (compare networkstate to estimated value)
    def newAppliance_6(self,n_clusters=3,amountMin=15,pointsMin=300,VarianceMax=None): 
        if VarianceMax==None:
            VarianceMax=(self.deviationRealPower()**2+self.deviationReactivePower()**2)*100
        [X,Y,durations]=self.clusterDataAdditive()
        agglomerativeClustering = AgglomerativeClustering(n_clusters).fit(X)

        clusters = agglomerativeClustering.labels_
        counts = np.bincount(clusters[clusters>=0])
        #print "Max Cluster: " + str(max(clusters))
        nr=0
        top_cluster = np.argsort(-counts)[:1][0]
        #print counts
        while counts[top_cluster]> amountMin:
            new=self.newApplianceCreatorAdditive(X,Y,durations,clusters,top_cluster,pointsMin,amountMin,VarianceMax)
            if new:
                return True
            nr+=1
            top_cluster = np.argsort(-counts)[:nr+1][nr]
        return False
    
    def addAppliance(self,realPower,realPowerDeviation,reactivePower,reactivePowerDeviation,pointsMin):
        groundState=ApplianceState(0,0,0,0,len(self.appliances))
        applianceState=ApplianceState(realPower,realPowerDeviation,reactivePower,reactivePowerDeviation,len(self.appliances))
        appliance=Appliance(self,groundState,applianceState,len(self.appliances))
        self.appliances.append(appliance)
        self.allowedDeviation=math.sqrt(((self.allowedDeviation**2)*(len(self.appliances)-1)+ realPowerDeviation**2 + reactivePowerDeviation**2)/len(self.appliances))
        durationON=0
        for applianceNr in range(len(self.appliances)-1):
            self.appliances[applianceNr].addAppliance()
        for stateNr in range(len(self.states)):
            state=self.states[stateNr]
            [networkRealPower,networkReactivePower]=self.networkStateRemainders(state)
            if distance(networkRealPower,networkReactivePower)>distance(networkRealPower,networkReactivePower,realPower,reactivePower) and 5.61>((((realPower-networkRealPower)**2)/ (realPowerDeviation**2+self.deviationRealPower()**2)) + (((reactivePower-networkReactivePower)**2)/ (reactivePowerDeviation**2+self.deviationReactivePower()**2))) :
                #print "1=" + str(len(state.applianceStates))
                self.states[stateNr].applianceStates.append(appliance.states[1])
                durationON+=state.getDuration()                              
                appliance.addDuration(appliance.states[1],state.getDuration())
                                               
            else:
                #print "1=" + str(len(state.applianceStates))
                self.states[stateNr].applianceStates.append(appliance.states[0])
                appliance.addDuration(appliance.states[0],state.getDuration())
        if durationON>pointsMin:
            if len(self.ground)>2:

                self.correctGround(realPower,reactivePower,durationON) 

                if self.groundWeight() > 0 :
                    #print "real " + str(realPower)
                    #print "real " + str(self.groundRealPower())
                    #print "real " + str(self.groundWeight())
                    realPowerCorrect=realPower*(durationON/self.groundWeight())

                    reactivePowerCorrect=reactivePower*(durationON/self.groundWeight())
                    appliance.states[1].addPower([realPowerCorrect,reactivePowerCorrect])
                    print "New Appliance with real power: "+ '{:10.6f}'.format(realPower+realPowerCorrect) + ", "+'{:10.6f}'.format(realPowerDeviation) + " and reactive power: " + '{:10.6f}'.format(reactivePower+reactivePowerCorrect) + ", "+'{:10.6f}'.format(reactivePowerDeviation)
                else:
                    print "New Appliance with real power: "+ '{:10.6f}'.format(realPower) + ", "+'{:10.6f}'.format(realPowerDeviation)+" and reactive power: "+ '{:10.6f}'.format(reactivePower) + ", "+'{:10.6f}'.format(reactivePowerDeviation) +"Ground " + str(self.groundWeight())
            else:
                print "New Appliance with real power: "+ '{:10.6f}'.format(realPower) + ", "+'{:10.6f}'.format(realPowerDeviation)+" and reactive power: "+ '{:10.6f}'.format(reactivePower) + ", "+'{:10.6f}'.format(reactivePowerDeviation)
            return True
        else:
            self.removeAppliance(len(self.appliances)-1)
            return False
    
    def addApplianceAdditive(self, realPower, realPowerDeviation, reactivePower, reactivePowerDeviation, pointsMin, amountMin):
        #self.write("New Appliance Power: "+str(realPower)+"; "+str(reactivePower) + " & Deviation: "+str(realPowerDeviation)+"; "+str(reactivePowerDeviation))
        groundState=ApplianceState(0,0,0,0,len(self.appliances))
        applianceState=ApplianceState(realPower,realPowerDeviation,reactivePower,reactivePowerDeviation,len(self.appliances))
        appliance=Appliance(self,groundState,applianceState,len(self.appliances))
        self.appliances.append(appliance)
        self.allowedDeviation=math.sqrt(((self.allowedDeviation**2)*(len(self.appliances)-1)+ realPowerDeviation**2 + reactivePowerDeviation**2)/len(self.appliances))
        durationON=0
        count=0
        for applianceNr in range(len(self.appliances)-1):
            self.appliances[applianceNr].addAppliance()
        for networkStateNr in range(len(self.states)):
            
            networkState=self.states[networkStateNr]
            self.write(networkState.printStr())
            difNr=1
            previousState=networkState
            while difNr<=networkStateNr:
                if not self.states[networkStateNr-difNr].isAnomaly("OutOfBounds"):
                    previousState=self.states[networkStateNr-difNr]
                    difNr=networkStateNr
                difNr+=1
            [networkRealPower,networkReactivePower]=self.networkStateRemaindersDifference(networkState,previousState)
            if previousState.isApplianceState(appliance.states[1]):
                relativeRealError=math.sqrt(((networkRealPower+realPower)**2)/ (realPowerDeviation**2+self.deviationRealPower()**2))
                relativeReactiveError=math.sqrt(((networkReactivePower+reactivePower)**2)/ (reactivePowerDeviation**2+self.deviationReactivePower()**2))
                relativeError=distance(relativeRealError,relativeReactiveError)
                if distance(networkRealPower,networkReactivePower) > distance(networkRealPower,networkReactivePower, -realPower,-reactivePower) and 5.61 >  relativeError:
                    #self.write( "    OK off=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeRealError+relativeReactiveError))
                    self.states[networkStateNr].applianceStates.append(appliance.states[0])             
                    appliance.addDuration(appliance.states[0],networkState.getDuration())
                    count+=1
                    if networkState.isAnomaly("MissedEdge"):
                        self.states[networkStateNr].setAnomaly("MissedEdge"+str(appliance.getIndex()))
                        self.write( "    nOK off=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                    else:
                        self.write( "    OK off=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                elif networkState.getRealPower()-self.groundRealPower()<realPower-2*realPowerDeviation:
                    self.write( "    NOK off=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                    self.states[networkStateNr].applianceStates.append(appliance.states[0])
                    self.states[networkStateNr].setAnomaly("MissedEdge"+str(appliance.getIndex()))                  
                    appliance.addDuration(appliance.states[0],networkState.getDuration())
                else:
                    self.write( "    onr=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                    self.write("     "+ str(distance(networkRealPower,networkReactivePower)/distance(networkRealPower,networkReactivePower,-realPower,-reactivePower)))
                    self.states[networkStateNr].applianceStates.append(appliance.states[1])
                    durationON+=networkState.getDuration()                              
                    appliance.addDuration(appliance.states[1],networkState.getDuration())

            else:
                relativeRealError=math.sqrt(((realPower-networkRealPower)**2)/ (realPowerDeviation**2+self.deviationRealPower()**2))
                relativeReactiveError=math.sqrt(((reactivePower-networkReactivePower)**2)/ (reactivePowerDeviation**2+self.deviationReactivePower()**2))
                relativeError=distance(relativeRealError,relativeReactiveError)
                if distance(networkRealPower,networkReactivePower) > distance(networkRealPower,networkReactivePower,realPower,reactivePower) and 5.61 > relativeError:

                    self.write( "    OK on=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                    self.states[networkStateNr].applianceStates.append(appliance.states[1])
                    durationON+=networkState.getDuration()                              
                    appliance.addDuration(appliance.states[1],networkState.getDuration())
                    count+=1

                else:
                    self.write( "    offr=" + str(networkRealPower)+" "+str(networkReactivePower)+ " " +str(relativeError))
                    self.write("     "+ str(distance(networkRealPower,networkReactivePower)/distance(networkRealPower,networkReactivePower,realPower,reactivePower)))
                    self.states[networkStateNr].applianceStates.append(appliance.states[0])
                    appliance.addDuration(appliance.states[0],networkState.getDuration())
        
        if durationON>pointsMin and count>=amountMin:
            self.write("New appliance with power: "+str(realPower)+"; "+str(reactivePower) + " and deviation: "+str(realPowerDeviation)+"; "+str(reactivePowerDeviation))
            if len(self.ground)>2:

                self.correctGround(realPower,reactivePower,durationON) 

                if self.groundWeight() > 0 :
                    #print "real " + str(realPower)
                    #print "real " + str(self.groundRealPower())
                    #print "real " + str(self.groundWeight())
                    realPowerCorrect=realPower*(durationON/self.groundWeight())

                    reactivePowerCorrect=reactivePower*(durationON/self.groundWeight())
                    appliance.states[1].addPower([realPowerCorrect,reactivePowerCorrect])
                    print "New Appliance with real power: "+ '{:10.6f}'.format(realPower+realPowerCorrect) + ", "+'{:10.6f}'.format(realPowerDeviation) + " and reactive power: " + '{:10.6f}'.format(reactivePower+reactivePowerCorrect) + ", "+'{:10.6f}'.format(reactivePowerDeviation)
                else:
                    print "New Appliance with real power: "+ '{:10.6f}'.format(realPower) + ", "+'{:10.6f}'.format(realPowerDeviation)+" and reactive power: "+ '{:10.6f}'.format(reactivePower) + ", "+'{:10.6f}'.format(reactivePowerDeviation) +"Ground " + str(self.groundWeight())
            else:
                print "New Appliance with real power: "+ '{:10.6f}'.format(realPower) + ", "+'{:10.6f}'.format(realPowerDeviation)+" and reactive power: "+ '{:10.6f}'.format(reactivePower) + ", "+'{:10.6f}'.format(reactivePowerDeviation)
            return True
        else:
            self.write("No appliance with power: "+str(realPower)+"; "+str(reactivePower) + " and deviation: "+str(realPowerDeviation)+"; "+str(reactivePowerDeviation))
            self.removeAppliance(len(self.appliances)-1)
            return False
    
    def removeAppliance(self, applianceIndex):
        self.write( "Appliance Removed")
        print  "Appliance Removed"
        for appId in range(len(self.appliances)):
            self.appliances[appId].removeAppliance(applianceIndex)
            
        appliance=self.appliances.pop(applianceIndex)
        for nr in range(len(self.states)):
            self.states[nr].applianceStates.pop(applianceIndex)
        
            
    #calculates the average difference between the estimate and the measured value
    def error(self):
        error=0
        duration=0
        for networkstate in self.states:
            duration+=networkstate.duration
            error+=math.sqrt(networkstate.remainders()[0]**2+networkstate.remainders()[1]**2)*networkstate.duration
        print "Error = " + str(error/duration) 
        return error/duration
        
#Edge Detection
def ttest(data,estimatedFirst):
    realPowerFirst=[]
    reactivePowerFirst=[]
    realPowerSecond=[]
    reactivePowerSecond=[]
    for dataPoint in data[0:estimatedFirst-1]:
        realPowerFirst.append(dataPoint.getRealPower())
        reactivePowerFirst.append(dataPoint.getReactivePower())
    for dataPoint in data[estimatedFirst:len(data)-1]:
        realPowerSecond.append(dataPoint.getRealPower())
        reactivePowerSecond.append(dataPoint.getReactivePower())
    a=scipy.stats.ttest_ind(realPowerFirst,realPowerSecond)[1]
    b=scipy.stats.ttest_ind(reactivePowerFirst,reactivePowerSecond)[1]
    if np.isnan(a):
        if np.isnan(b):
            print "NAN a+b at "+ str(data[len(data)-1].index)
            print realPowerFirst
            print realPowerSecond
            #print reactivePowerFirst
            #print reactivePowerSecond
            return 1
        else:
            print "NAN a at "+ str(data[len(data)-1].index)
            print realPowerFirst
            print realPowerSecond
            return b   
    else:
        if np.isnan(b):
            print "NAN b at "+ str(data[len(data)-1].index)
            #print reactivePowerFirst
            #print reactivePowerSecond
            return a
        else:
            return min(a,b)
            
def sortApplianceStates(applianceStates):
        loc=0
        while loc<len(applianceStates)-1:
            if applianceStates[loc].getRealPower()>applianceStates[loc+1].getRealPower():
                applianceStates.append(applianceStates.pop(loc))
                loc-=1
            else:
                loc+=1
        return applianceStates
    
def distance(realPower1,reactivePower1,realPower2=0,reactivePower2=0):
        return math.sqrt((realPower1-realPower2)**2+(reactivePower1-reactivePower2)**2)
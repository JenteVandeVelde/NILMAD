
from __future__ import division
import math
import numpy as np
import matplotlib.pyplot as plt
import csv
import datetime as dt
from xlrd import open_workbook
class NILManalyzeTime:
    def __init__(self,filepath = 'MKCorrected.xls.txt' ,filepathRef='RefMK.xlsx'):
        appliances=[]
        applianceAccuracy=[]
        applianceAccuracyLog=[]
        appliancePrecisionLog=[]
        applianceRecallLog=[]
        anomaliePoints=[]
        anomalieOStates=[]
        anomalieMStates=[]
        maxTimeDelta=dt.timedelta(0,20)
        applianceStatesRef=[]

        wb = open_workbook(filepathRef)
        sheet= wb.sheets()[0]
        for row in range(1,sheet.nrows):
            time=0
            try:
                time=dt.datetime.utcfromtimestamp((float(sheet.cell(row,1).value ) - 25569) * 86400.0)
            except ValueError:
                try:
                    time=dt.datetime.utcfromtimestamp((float(sheet.cell(row,0).value ) - 25569) * 86400.0)
                except ValueError:
                    print "empty row at "+str(row)
            try:
                applianceState=[]
                for col in range(2,11):
                    applianceState.append(int(sheet.cell(row,col).value))
                applianceState.append(0)
                applianceStatesRef.append([time,applianceState])
            except ValueError:
                print "empty row values at "+str(row)

        with open(filepath) as results:
            result = results.readline()
            startTime=dt.datetime(int(result[6:10]), int(result[3:5]), int(result[0:2]), int(result[11:13]), int(result[14:16]), int(result[17:19]))
            currentTime=dt.datetime(int(result[6:10]), int(result[3:5]), int(result[0:2]), int(result[11:13]), int(result[14:16]), int(result[17:19]))
            applianceState=[]
            refIndex=0
            while result and refIndex+1<len(applianceStatesRef):
                time= dt.datetime(int(result[6:10]), int(result[3:5]), int(result[0:2]), int(result[11:13]), int(result[14:16]), int(result[17:19]))
                duration=applianceStatesRef[refIndex+1][0]-applianceStatesRef[refIndex][0]
                duration=duration.total_seconds()
                while maxTimeDelta<(time-applianceStatesRef[refIndex][0]):

                    for applianceNr in range(len(appliances)):
                        while applianceState[applianceNr]>=appliances[applianceNr]:
                            print 'New State at ' +currentTime.strftime('%d/%m/%Y %H:%M:%S')
                            try:
                                appliances[applianceNr]+=1
                                durationStart=applianceStatesRef[refIndex][0]-startTime
                                durationStart=durationStart.total_seconds()
                                applianceAccuracy[applianceNr].append([0,0,0,durationStart])
                            except IndexError:
                                pass
                        for applianceStateNr in range(appliances[applianceNr]):
                            try:
                                applianceAccuracy[applianceNr][applianceStateNr][3]+=duration
                                if applianceState[applianceNr]==applianceStateNr:
                                    applianceAccuracy[applianceNr][applianceStateNr][2]+=duration
                                    if applianceStatesRef[refIndex][1][applianceNr]==applianceStateNr:
                                        applianceAccuracy[applianceNr][applianceStateNr][0]+=duration
                                if applianceStatesRef[refIndex][1][applianceNr]==applianceStateNr:
                                    applianceAccuracy[applianceNr][applianceStateNr][1]+=duration
                            except IndexError:
                                pass

                    #TODO SKIP
                    if applianceStatesRef[refIndex][0]>currentTime:
                        applianceAccuracyLog.append([applianceStatesRef[refIndex][0]]+[sum([element[0]/element[3] for element in appliance])for appliance in applianceAccuracy])
                        appliancePrecisionLog.append([applianceStatesRef[refIndex][0]]+[[element[0]/(element[2]+10**(-20)) for element in appliance]for appliance in applianceAccuracy])
                        applianceRecallLog.append([applianceStatesRef[refIndex][0]]+[[element[0]/(element[1]+10**(-20)) for element in appliance]for appliance in applianceAccuracy])
                        currentTime=applianceStatesRef[refIndex][0]
                    refIndex+=1
                    duration=applianceStatesRef[refIndex+1][0]-applianceStatesRef[refIndex][0]
                    duration=duration.total_seconds()
                applianceState=[]
                i=20
                done=False
                while not done:
                    try: 
                        applianceState.append(int(result[i]))
                        i+=2
                    except (ValueError,IndexError):
                        done=True
                if len(anomalieOStates)>0:
                    if anomalieOStates[len(anomalieOStates)-1][1]==None:
                        anomalieOStates[len(anomalieOStates)-1][1]=time
                if len(anomalieMStates)>0:
                    if anomalieMStates[len(anomalieMStates)-1][1]==None:
                        anomalieMStates[len(anomalieMStates)-1][1]=time
                try:
                    if not result[i]=='':
                        try: 
                            if 'O'==(int(result[i])):
                                anomalieOStates.append([time,None])
                            if 'M'==(int(result[i])):
                                anomalieMStates.append([time,None])
                        except ValueError:
                            pass
                except IndexError:
                    pass
                if startTime==time:
                    for element in (applianceAccuracy):
                        for subElement in element:
                            subElement=[0,0,0,0]
                    refIndex=0
                    anomalieOStates=[]
                    anomalieMStates=[]
                    while len(appliances)<len(applianceState):
                        appliances.append(2)    
                        print 'New at ' +currentTime.strftime('%d/%m/%Y %H:%M:%S')
                        applianceAccuracy.append([[0,0,0,0],[0,0,0,0]])
                    while len(appliances)>len(applianceState):
                        appliances.pop()
                        applianceAccuracy.pop()
                        print 'Remove at ' +currentTime.strftime('%d/%m/%Y %H:%M:%S')
                else:
                    while len(appliances)>len(applianceState):
                        appliances.pop()
                        applianceAccuracy.pop()
                        print 'Remove at ' +currentTime.strftime('%d/%m/%Y %H:%M:%S')
                    for applianceNr in range(len(appliances)):
                        while applianceState[applianceNr]>=appliances[applianceNr]:
                            print 'New State at ' +currentTime.strftime('%d/%m/%Y %H:%M:%S')
                            try:
                                appliances[applianceNr]+=1
                                durationStart=applianceStatesRef[refIndex][0]-startTime
                                durationStart=durationStart.total_seconds()
                                applianceAccuracy[applianceNr].append([0,0,0,durationStart])
                            except IndexError:
                                pass
                        for applianceStateNr in range(appliances[applianceNr]):
                            try:
                                applianceAccuracy[applianceNr][applianceStateNr][3]+=duration
                                if applianceState[applianceNr]==applianceStateNr:
                                    applianceAccuracy[applianceNr][applianceStateNr][2]+=duration
                                    if applianceStatesRef[refIndex][1][applianceNr]==applianceStateNr:
                                        applianceAccuracy[applianceNr][applianceStateNr][0]+=duration
                                if applianceStatesRef[refIndex][1][applianceNr]==applianceStateNr:
                                    applianceAccuracy[applianceNr][applianceStateNr][1]+=duration
                            except IndexError:
                                pass
                if time>currentTime:
                    applianceAccuracyLog.append([time]+[sum([element[0]/element[3] for element in appliance])for appliance in applianceAccuracy])
                    appliancePrecisionLog.append([time]+[[element[0]/(element[2]+10**(-20)) for element in appliance]for appliance in applianceAccuracy])
                    applianceRecallLog.append([time]+[[element[0]/(element[1]+10**(-20)) for element in appliance]for appliance in applianceAccuracy])
                    currentTime=time
                refIndex+=1
                result = results.readline()

        self.log=[applianceAccuracyLog,appliancePrecisionLog,applianceRecallLog]
        self.anomalyPoints=anomaliePoints
        self.anomalyStates=[anomalieOStates,anomalieMStates]
    
    def Log(self,typeNr,applianceNr=0,applianceStateNr=1,start=None,end=None):
        if start==None:
            start=self.log[0][0][0]
        if end==None:
            end=self.log[0][len(self.log[0])-1][0]
        time=[]
        data=[]
        figure=plt.figure()
        #Data is compiled in reverse ("[:--1]") in order to avoid logged acuraccy data from removed temporary appliances/states (this data in itself is meaningless)
        if typeNr==3:
            F1=None
            for elementNr in range(len(self.log[2]))[::-1]:
                precision=self.log[1][elementNr]
                recall=self.log[2][elementNr]
                if precision[0]>=start and precision[0]<end:
                    try:
                        precisionValue=precision[applianceNr+1][applianceStateNr]
                        recallValue=recall[applianceNr+1][applianceStateNr]
                        F1=2*precisionValue*recallValue
                        if not F1==0:
                            F1/=precisionValue+recallValue
                        data.append(F1)
                        timeDif=precision[0]-start
                        day=timeDif.total_seconds()/(24*60*60)
                        time.append(day) 
                    except IndexError:
                        if len(time)==0:
                            end=precision[0]
                        else:
                            start=precision[0]
                    
        else:
            for element in self.log[typeNr][::-1]:
                if element[0]>=start and element[0]<end:
                    try:
                        if typeNr==0:
                            data.append(element[applianceNr+1])
                        else:
                            data.append(element[applianceNr+1][applianceStateNr])
                        timeDif=element[0]-start
                        day=timeDif.total_seconds()/(24*60*60)
                        #if day<2:
                        #   print day
                        time.append(day) 
                    except IndexError:
                        if len(time)==0:
                            end=element[0]
                        else:
                            start=element[0]
        return [time,data]
    
    def plotLog(self,typeNr,applianceNr=0,applianceStateNr=1,start=None,end=None):
        plt.close('all')
        [time,data]=self.Log(typeNr,applianceNr,applianceStateNr,start,end)
        plt.plot(time,data)
        plt.axis([0,21,0,1])
        plt.show()
    
    def plotLogs(self,applianceNr=0,applianceStateNr=1,start=None,end=None):
        plt.close('all')
        figure=plt.figure()
        colors=['#0053c9', '#ff9000', '#28ff41', '#ff3f00', '#dd57f2', '#008c10', '#006372', '#663c93', '#9b4153', '#00b7a1', '#bfbc0b']
        timeData=[]
        for i in range(4):
            timeData.append(self.Log(i,applianceNr,applianceStateNr,start,end))
        for i in range(4):
            plt.plot(timeData[i][0],timeData[i][1],colors[i])
        plt.axis([0,21,0,1])
        plt.show()
        
        
        
        
        
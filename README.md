# NILMAD
Unsupervised FHMM algortihm to disagregate a network with Type-I and/or Type-II appliances using Non-Intrusive Load Monitoring with aditional aide of several Anomaly Detection methods.
The algortihm is build modular and object oriented in order to be more easely understood, adapted, and compared.

Compiled using anaconda2 and suplementory package simanneal (0.4.2)

To use: 
1) Initialize NILM using integers or using suplied interface NILMrun: 'setup=NILMrun()'
2) Use NILM.read to read a .xls or .csv file
3) (Optional) Use one of the (four) analysis algorithms to compare the results to a reference (.xls) file

Example Case Study Data can be found at:
  https://drive.google.com/open?id=1zhLVajWB7y7LDO0RasjlzgFHVu3Agc9D
MK.xls.txt are the results after (manually) correcting the order of the Type-II states.
The algorithm does NOT return the appliance (states) in a predetermined order 


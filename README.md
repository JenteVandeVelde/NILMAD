# NILMAD
Unsupervised FHMM algortihm to disagregate a network with Type-I and/or Type-II appliances using Non-Intrusive Load Monitoring with aditional aide of several Anomaly Detection methods.
The algortihm is build modular and object oriented in order to be more easely understood, adapted, and compared.

Compiled using anaconda2 and suplementory package simanneal (0.4.2)

To use: 
1) Initialize NILM using integers or using suplied interface 'NILMrun'

a) To start using the 'NILMrun' interface add all python files to the same map

b) Execute 'setup=NILMrun()'

c) Folow instructions given

2) Use NILM.read to read a .xls or .csv file
3) (Optional) Use one of the (four) analysis algorithms to compare the results to a reference (.xls) file

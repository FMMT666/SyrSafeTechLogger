#!/usr/bin/env python3
#
# Q&D Syr SafeTech Connect Data Logger
#   Reads the most important data from a Syr SafeTech Connect device and
#   prints it to the console.
#   Use console redirection to save the data to a file.
#   E.g.: python3 SyrSafeTechLogger.py > syrData.txt
#
#   >>> Set the IP address of your Syr SafeTech Connect device in the variable SYR_IPADDR.<<<
#
# FMMT666(ASkr) 02/2024
#


# CHANGES 02/2024:
#   - initial version
#


import time
import requests


SYR_IPADDR = "192.168.2.120"       # SET YOUR SYR'S IP ADDRESS RIGHT HERE
SYR_UNITS  = "metric"              # unused; only metric so far (°C, bar, Liter)
SYR_DELAY  = 1                     # delay between a set of requests in seconds




#############################################################################################################
#SYR_CMD_VALVE       = "AB"         # valve state; 1 = open, 2 = closed (according to the manual; but that's wrong, as it seems)
SYR_CMD_VALVE       = "VLV"        # valve state; 10 = Closed, 11 = Closing, 20 = Open, 21 = Opening, 30 = Undefined
SYR_CMD_TEMP        = "CEL"        # temperature in 0..1000 representing 0..100.0°C (if imperial maybe 0..100.0F; not sure)
SYR_CMD_PRESSURE    = "BAR"        # pressure in mbar (if imperial maybe psi?; not sure)
SYR_CMD_FLOW        = "FLO"        # flow in L/h; not very sensitive
SYR_CMD_VOLUME      = "AVO"        # volume of the current, single water consumption, in mL (always?); (imperial: fl.oz.?)
SYR_CMD_VOLUME_LAST = "LTV"        # volume of the last,    single water consumption, in Liter





#############################################################################################################
## GetData
#############################################################################################################
def GetDataRaw( command, timeout = 5 ):
    """Read data from Syr SafeTech
    
    command: RestAPI command in lower or upper case letters. E.g. "AVO", "CEL", ...
    timeout: seconds to wait for a response

    Returns: the raw value of the requested command or "ERROR" if no response
    """
    command = command.upper()
    try:
        response = requests.get( "http://" + SYR_IPADDR + ":5333/safe-tec/get/" + command, timeout = timeout )
    except:
        # one for all
        return "ERROR"

    if response.status_code == 200:
        data = response.json()
        return data.get( 'get' + command )
    else:
        # unused
        return "ERROR: " + str( response.status_code )



#############################################################################################################
if __name__ == "__main__":
    # Q&D dirty test only, so far.
    # Absolutely unsure about the timing and stability.
    # Will slamming protocols at the Syr even hinder it from working properly?
    # Let's find out ...

    # TESTING, TESTING, TESTING 123
    polls = 0
    while True:
        # log everything in its raw form
        print( time.asctime(),                  ";",
              GetDataRaw( SYR_CMD_VALVE ),      ";",
              GetDataRaw( SYR_CMD_PRESSURE ),   ";",
              GetDataRaw( SYR_CMD_FLOW ),       ";",
              GetDataRaw( SYR_CMD_VOLUME ),     ";",
              GetDataRaw( SYR_CMD_VOLUME_LAST ) )

        # break

        # if ( polls := polls + 1 ) > 100:
        #     break

        time.sleep( SYR_DELAY )


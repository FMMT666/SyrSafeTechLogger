#!/usr/bin/env python3
#
# Q&D Syr SafeTech Connect Data Logger
#   Reads the most important data from a Syr SafeTech Connect device,
#   prints it to the console and logs it to a file.
#
#   >>> Set the IP address of your Syr SafeTech Connect device in the variable SYR_IPADDR.<<<
#
#
# https://github.com/FMMT666/SyrSafeTechLogger
#
# FMMT666(ASkr) 02/2024
#



import sys
import time
import requests


SYR_IPADDR = "192.168.2.120"       # SET YOUR SYR'S IP ADDRESS RIGHT HERE
SYR_UNITS  = "metric"              # unused yet; only metric so far (°C, bar, Liter)
SYR_DELAY  = 1                     # delay between a set of requests in seconds




#############################################################################################################
#SYR_CMD_VALVE       = "AB"         # valve state; 1 = open, 2 = closed (according to the manual; but that's wrong, as it seems)
SYR_CMD_VALVE       = "VLV"        # valve state; 10 = Closed, 11 = Closing, 20 = Open, 21 = Opening, 30 = Undefined
SYR_CMD_TEMP        = "CEL"        # temperature in 0..1000 representing 0..100.0°C (if imperial maybe 0..100.0F; not sure)
SYR_CMD_PRESSURE    = "BAR"        # pressure in mbar (if imperial maybe psi?; not sure)
SYR_CMD_FLOW        = "FLO"        # flow in L/h; not very sensitive
SYR_CMD_VOLUME      = "AVO"        # volume of the current, single water consumption, in mL (always?); (imperial: fl.oz.?)
SYR_CMD_VOLUME_LAST = "LTV"        # volume of the last,    single water consumption, in Liter
SYR_CMD_ALARM       = "ALA"        # current alarm state; FF = no alarm,

SYR_ERROR_STRING    = "ERROR"      # error string to be returned if something went wrong; maybe "-1" would be better?

APP_NOFILE          = False        # by default, everything is written to a file
APP_NOSTDOUT        = False        # by default, everything is printed to stdout

# TODO: alarm codes for further anylysis:
#    FF   NO ALARM
#    A1   ALARM END SWITCH
#    A2   NO NETWORK
#    A3   ALARM VOLUME LEAKAGE
#    A4   ALARM TIME LEAKAGE
#    A5   ALARM MAX FLOW LEAKAGE
#    A6   ALARM MICRO LEAKAGE
#    A7   ALARM EXT. SENSOR LEAKAGE
#    A8   ALARM TURBINE BLOCKED
#    A9   ALARM PRESSURE SENSOR ERROR
#    AA   ALARM TEMPERATURE SENSOR ERROR
#    AB   ALARM CONDUCTIVITY SENSOR ERROR
#    AC   ALARM TO HIGH CONDUCTIVITY
#    AD   LOW BATTERY
#    AE   WARNING VOLUME LEAKAGE
#    AF   ALARM NO POWER SUPPLY

#############################################################################################################
## PrintUsage
#############################################################################################################
def PrintUsage():
    """Prints the usage, command line options to stdout.
    """
    print( "Usage: SyrSafeTechLogger.py [options]" )
    print( "Options:" )
    print( "  --help        : print this help" )
    print( "  --nofile      : do not write to a file" )
    print( "  --nostdout    : do not print to stdout (useful when used with nohup)" )
    print( "  --maxpolls=n  : stop after n polls" )
    print( "  --delay=n     : delay between set of polls in seconds; floating point allowed, e.g. --delay=1.5" )


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
        return SYR_ERROR_STRING

    if response.status_code == 200:
        data = response.json()
        return data.get( 'get' + command )

    # just in case; unused; will not be reached
    return SYR_ERROR_STRING



#############################################################################################################
if __name__ == "__main__":
    # Q&D dirty test only, so far.
    # Absolutely unsure about the timing and stability.
    # Will slamming protocols at the Syr even hinder it from working properly?
    # Let's find out ...

    # TESTING, TESTING, TESTING 123


    maxpolls = -1 # -1 = infinite (default); can be overridden by command line option "--maxpolls=<n>"

    # -------------------------------------------------------------------------------------------------------
    # minimal command line options
    for args in sys.argv:
        # ------------------------------
        if args == sys.argv[0]:
            continue
        # ------------------------------
        if args == "--help" or args == "-h" or args == "-?" or args == "/?":
            PrintUsage()
            sys.exit( 0 )
        # ------------------------------
        elif args == "--nofile":
            APP_NOFILE = True
        # ------------------------------
        elif args == "--nostdout":
            APP_NOSTDOUT = True
        # ------------------------------
        elif "--maxpolls=" in args:
            try:
                maxpolls = int( args[11:] )
            except:
                print( "ERROR: invalid value for --maxpolls" )
                PrintUsage()
                sys.exit( 0 )
            if maxpolls < 1:
                maxpolls = 1
        # ------------------------------
        elif "--delay=" in args:
            try:
                SYR_DELAY = abs( float( args[8:] ) )
            except:
                print( "ERROR: invalid value for --delay" )
                PrintUsage()
                sys.exit( 0 )
            if SYR_DELAY < 0.1:
                SYR_DELAY = 0
        # ------------------------------
        else:
            if args == "--maxpolls" or args == "--delay":
                print( "ERROR: missing value for " + args )
            else:
                print( "ERROR: unknown option: " + args )
            PrintUsage()
            sys.exit( 0 )

    if APP_NOFILE and APP_NOSTDOUT:
        print( "ERROR: --nofile and --nostdout together does not make sense at all" )
        sys.exit( 0 )


    # -------------------------------------------------------------------------------------------------------

    if APP_NOFILE is False:
        fout = open( time.strftime("%Y%m%d%H%M%S") + "_SyrSafeTech.log", "w+t" )
    else:
        fout = None


    while True:
        timeHuman   = time.asctime()
        timeMachine = time.strftime("%Y;%m;%d; %H;%M;%S")

        # log everything in its raw form for now
        dataLine = GetDataRaw( SYR_CMD_VALVE )       + "; " + \
                   GetDataRaw( SYR_CMD_PRESSURE )    + "; " + \
                   GetDataRaw( SYR_CMD_FLOW )        + "; " + \
                   GetDataRaw( SYR_CMD_VOLUME )      + "; " + \
                   GetDataRaw( SYR_CMD_VOLUME_LAST ) + "; " + \
                   GetDataRaw( SYR_CMD_ALARM )

        if APP_NOSTDOUT is False:
            print( timeHuman + "; " + dataLine )

        if APP_NOFILE is False:
            fout.write( timeMachine + "; " + dataLine + "\n" )
            fout.flush() 

        if ( maxpolls > 0 ):
            if ( maxpolls := maxpolls - 1 ) == 0:
                break

        time.sleep( SYR_DELAY )
    # END while


    if APP_NOFILE is False:
        fout.close()

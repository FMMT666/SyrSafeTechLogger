#!/usr/bin/env python3
#
# Q&D Syr SafeTech Connect Data Logger
#   Reads the most important data from a Syr SafeTech Connect device,
#   prints it to the console and logs it to a file.
#
#
# https://github.com/FMMT666/SyrSafeTechLogger
#
# FMMT666(ASkr) 02/2024, 03/2024
#



import sys
import time
import re
import requests


#############################################################################################################
SYR_IPADDR = "0.0.0.0"             # IP address of Syr (set by command line option "--ipaddr=addr")
SYR_UNITS  = "metric"              # unused yet; only metric so far (°C, bar, Liter)
SYR_DELAY  = 1                     # delay between a set of requests in seconds

#############################################################################################################
SYR_CMD_VALVE            = "AB"         # valve state; 1 = open, 2 = closed (according to the manual; but that's wrong, as it seems)
SYR_CMD_VALVE            = "VLV"        # valve state; 10 = Closed, 11 = Closing, 20 = Open, 21 = Opening, 30 = Undefined
SYR_CMD_TEMP             = "CEL"        # temperature in 0-1000 representing 0..100.0°C (if imperial maybe 0-100.0F; not sure)
SYR_CMD_PRESSURE         = "BAR"        # pressure in mbar (if imperial maybe psi?; not sure)
SYR_CMD_FLOW             = "FLO"        # flow in L/h; not very sensitive
SYR_CMD_VOLUME           = "AVO"        # volume of the current, single water consumption, in mL (always?); (imperial: fl.oz.?)
SYR_CMD_VOLUME_LAST      = "LTV"        # volume of the last,    single water consumption, in Liter
SYR_CMD_ALARM            = "ALA"        # current alarm state; FF = no alarm, rest see table below
SYR_CMD_UNITS            = "UNI"        # units; 0 = metric, 1 = imperial; I always get "mbar" and mL", even in imperial mode; FW bug?
SYR_CMD_VERSION          = "VER"        # firmware version; e.g. "Safe-Tech V4.04"
SYR_CMD_SERIAL           = "SRN"        # serial number; e.g. "123456789"
SYR_CMD_PROFILE          = "PRF"        # read or set profile number (1..8) 
SYR_CMD_PROFILENUMS      = "PRN"        # read number of profiles (1..8)
SYR_CMD_PROFILE_X_AVAIL  = "PA"         # (PA1..PA8) read if profile X available; 0 = no, 1 = yes
SYR_CMD_PROFILE_X_NAME   = "PN"         # (PN1..PN8) read profile X name
SYR_CMD_PROFILE_X_VOL    = "PV"         # (PV1..PV8) read profile X volume level
SYR_CMD_PROFILE_X_TIME   = "PT"         # (PT1..PT8) read profile X time level
SYR_CMD_PROFILE_X_FLOW   = "PF"         # (PF1..PF8) read profile X flow level
SYR_CMD_PROFILE_X_MLEAK  = "PM"         # (PM1..PM8) read profile X micro leakage; 0 = no, 1 = yes
SYR_CMD_PROFILE_X_RTIME  = "PR"         # (PR1..PR8) read profile X return time; 0 = never, 1-720 hours (30 days)
SYR_CMD_PROFILE_X_BUZZ   = "PB"         # (PB1..PB8) read profile X buzzer; 0 = off, 1 = on
SYR_CMD_PROFILE_X_LEAKW  = "PW"         # (PW1..PW8) read profile X leakage warning; 0 = off, 1 = on
SYR_CMD_TMP              = "TMP"        # leakage temporary deactivation; 0 = disabled, 0-4294967295 seconds
SYR_CMD_BUZZER           = "BUZ"        # 0 = disabled, 1 = enabled
SYR_CMD_CONDUCT_LIMIT    = "CNL"        # conductivity limit; 0-5000uS/cm
SYR_CMD_CONDUCT_FACTOR   = "CNF"        # conductivity factor; 5-50 representing 0.5-5.0
SYR_CMD_LEAKAGE_WARNING  = "LWT"        # leakage warning notification; 80-99 in percent
SYR_CMD_NEXT_MAINTENANCE = "SRV"        # next maintenance date; dd.mm.yyyy 
SYR_CMD_BATTERY          = "BAT"        #  battery voltage;   1/100V x.xx
SYR_CMD_VOLTAGE          = "NET"        #  dc supply voltage; 1/100V x.xx
SYR_CMD_RTC              = "RTC"        #  linux epoch time; 0-4294967295

SYR_ERROR_STRING    = "ERROR"      # error string to be returned if something went wrong; maybe "-1" would be better?

SYR_UNITS           = [ " mbar", "mL" ]  # for text/data replacement; imperial yet unknown; my device always puts out " mbar"

#############################################################################################################
APP_NOFILE          = False        # by default, everything is written to a file
APP_NOSTDOUT        = False        # by default, everything is printed to stdout
APP_RAW             = False        # by default, everything is printed in a human readable form

APP_CMD_HENLO       = 1            # typos and enums sock; the cool thing is that this copilot thingy :)
APP_CMD_STATUS      = 2
APP_CMD_PROFILE     = 3

APP_COMMAND         = None         # wild mix


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
    print( "  --ipaddr=addr : set the IP address of the Syr SafeTech Connect device" )
    print( "  --henlo       : test presence of the device, print serial number, SW version and then quit" )
    print( "  --nofile      : do not write to a file" )
    print( "  --nostdout    : do not print to stdout (useful when used with nohup)" )
    print( "  --maxpolls=n  : stop after n polls" )
    print( "  --delay=n     : delay between set of polls in seconds; floating point allowed, e.g. --delay=1.5" )
    print( "  --raw         : print raw data; units 'mbar', 'mL', etc. are not removed" )
    print( "  --status      : print the current status and settings of the Syr, then quit" )
    print( "  --profile     : print name and number of active profile, then quit" )



#############################################################################################################
## CheckIPv4
#############################################################################################################
def CheckIPv4( ipaddr ):
    """Check if a string is a valid IPv4 address.

    ipaddr: IPv4 address as string

    Returns: True if valid, False if not
    """

    pattern = re.compile(r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
    return bool( pattern.match(ipaddr) )


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
## GetAndPrintStatus
#############################################################################################################
def GetAndPrintStatus():
    """Read (almost) all settings the Syr SafeTech and print them to stdout.
    """

    print( "  Profiles available ....... " + GetDataRaw( SYR_CMD_PROFILENUMS ) )
    print( "  Profile numbers .......... ", end = "" )
    for i in range( 1, 9 ):
        if ( ret := GetDataRaw( SYR_CMD_PROFILE_X_AVAIL + str(i) ) ) != SYR_ERROR_STRING:
            if ret == "1":
                print( str(i), end = " " )
        else:
            # not nice :-/
            print( SYR_ERROR_STRING, end = " " )
    print()
    print( "  Profile selected ......... " + (profNum:=GetDataRaw( SYR_CMD_PROFILE )) )
    print( "  Profile " + str(profNum ) + " name ........... " + GetDataRaw( SYR_CMD_PROFILE_X_NAME + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " volume level ... " + GetDataRaw( SYR_CMD_PROFILE_X_VOL + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " time level ..... " + GetDataRaw( SYR_CMD_PROFILE_X_TIME + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " flow level ..... " + GetDataRaw( SYR_CMD_PROFILE_X_FLOW + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " microleakage ... " + GetDataRaw( SYR_CMD_PROFILE_X_MLEAK + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " return time .... " + GetDataRaw( SYR_CMD_PROFILE_X_RTIME + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " buzzer ......... " + GetDataRaw( SYR_CMD_PROFILE_X_BUZZ + str(profNum ) ) )
    print( "  Profile " + str(profNum ) + " leakage warning. " + GetDataRaw( SYR_CMD_PROFILE_X_LEAKW + str(profNum ) ) )
    print( "  Leakage temp disable ..... " + GetDataRaw( SYR_CMD_TMP) )
    print( "  Buzzer ................... " + GetDataRaw( SYR_CMD_BUZZER) )
    print( "  Conductivity limit ....... " + GetDataRaw( SYR_CMD_CONDUCT_LIMIT) )
    print( "  Conductivity factor ...... " + GetDataRaw( SYR_CMD_CONDUCT_FACTOR) )
    print( "  Leakage warning .......... " + GetDataRaw( SYR_CMD_LEAKAGE_WARNING) )
    print( "  Next maintenance ......... " + GetDataRaw( SYR_CMD_NEXT_MAINTENANCE) )
    print( "  Battery voltage .......... " + GetDataRaw( SYR_CMD_BATTERY) )

#    print( "  Power supply voltage ..... " + GetDataRaw( SYR_CMD_VOLTAGE) )
    print( "  Power supply voltage ..... has issues; not supported yet" )

    print( "  RTC ...................... " + GetDataRaw( SYR_CMD_RTC) )


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
        elif args == "--raw":
            APP_RAW = True
        # ------------------------------
        elif args == "--henlo":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_HENLO
        # ------------------------------
        elif args == "--status":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_STATUS
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
        elif "--ipaddr=" in args:
            SYR_IPADDR = args[9:]
            if CheckIPv4( SYR_IPADDR ) is False:
                print( "ERROR: invalid IP address" )
                PrintUsage()
                sys.exit( 0 )
        # ------------------------------
        elif args == "--profile":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_PROFILE
        # ------------------------------
        else:
            if args == "--maxpolls" or args == "--delay" or args == "--ipaddr":
                print( "ERROR: missing value for " + args )
            else:
                print( "ERROR: unknown option: " + args )
            PrintUsage()
            sys.exit( 0 )

    if APP_NOFILE and APP_NOSTDOUT:
        print( "ERROR: --nofile and --nostdout together does not make sense at all" )
        sys.exit( 0 )

    if SYR_IPADDR == "0.0.0.0":
        print( "ERROR: missing IP address" )
        PrintUsage()
        sys.exit( 0 )

    # -------------------------------------------------------------------------------------------------------
    # check if the device is there and alive
    if ( syrVersion := GetDataRaw( SYR_CMD_VERSION ) ) == SYR_ERROR_STRING:
        print( "ERROR: no response from Syr SafeTech Connect device" )
        sys.exit( 0 )
    if ( syrSerial := GetDataRaw( SYR_CMD_SERIAL ) ) == SYR_ERROR_STRING:
        print( "ERROR: no response from Syr SafeTech Connect device" )
        sys.exit( 0 )

    if APP_COMMAND == APP_CMD_PROFILE:
        print( "  Profile selected ......... " + (profNum:=GetDataRaw( SYR_CMD_PROFILE )) )
        print( "  Profile " + str(profNum ) + " name ........... " + GetDataRaw( SYR_CMD_PROFILE_X_NAME + str(profNum ) ) )
        sys.exit( 0 )

    if APP_COMMAND == APP_CMD_HENLO or APP_COMMAND == APP_CMD_STATUS:
        print( "Found device:" )
        print( "  Serial ................... " + syrSerial )
        print( "  Version .................. " + syrVersion )
        if APP_COMMAND == APP_CMD_STATUS:
            GetAndPrintStatus()
        sys.exit( 0 )

    if APP_NOFILE is False:
        fout = open( time.strftime("%Y%m%d%H%M%S") + "_SyrSafeTech.log", "w+t" )
    else:
        fout = None


    # -------------------------------------------------------------------------------------------------------
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

        if APP_RAW is False:
            for i in range( len( SYR_UNITS ) ):
                dataLine = dataLine.replace( SYR_UNITS[i], "" )

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

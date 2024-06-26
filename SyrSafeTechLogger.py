#!/usr/bin/env python3
#
# Q&D Syr SafeTech Connect Data Logger
#   Reads the most important data from a Syr SafeTech Connect device,
#   prints it to the console and logs it to a file.
#
#
# https://github.com/FMMT666/SyrSafeTechLogger
#
# FMMT666(ASkr) 02/2024, 03/2024, 04/2024
#


import sys
import time
import re
import datetime
import requests


#############################################################################################################
SYR_IPADDR = "0.0.0.0"             # IP address of Syr (set by command line option "--ipaddr=addr")
SYR_UNITS  = "metric"              # unused yet; only metric so far (°C, bar, Liter)
SYR_DELAY  = 2                     # delay between a set of requests in seconds

#############################################################################################################
SYR_CMD_SHUTOFF          = "AB"         # valve state; 1 = opened, 2 = closed (according to the manual; but that's wrong, as it seems)
SYR_CMD_VALVE            = "VLV"        # valve state; 10 = closed, 11 = closing, 20 = open, 21 = opening, 30 = undefined
SYR_CMD_TEMP             = "CEL"        # temperature in 0-1000 representing 0..100.0°C (if imperial maybe 0-100.0F; not sure)
SYR_CMD_PRESSURE         = "BAR"        # pressure in mbar (if imperial maybe psi?; not sure)
SYR_CMD_FLOW             = "FLO"        # flow in L/h; not very sensitive
SYR_CMD_CONDUCTIVITY     = "CND"        # conductivity in uS/cm; 0-5000
SYR_CMD_VOLUME           = "AVO"        # volume of the current, single water consumption, in mL (always?); (imperial: fl.oz.?)
SYR_CMD_VOLUME_LAST      = "LTV"        # volume of the last,    single water consumption, in Liter
SYR_CMD_VOLUME_TOTAL     = "VOL"        # total cumulative volume of water consumed; in Liter (admin mode)
SYR_CMD_ALARM            = "ALA"        # current alarm state; FF = no alarm, rest see table below
SYR_CMD_ALARM_MEMORY     = "ALM"        # alarm history; requires admin mode; "Alarms:->A3 A3 A4 A4 A4 A4 A4 A4"
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
SYR_CMD_LANGUAGE         = "LNG"        # language; 0 = DE, 1 = EN, 2 = ES, 3 = IT, 4 = PL
SYR_CMD_FLOOR_SENSOR     = "BSA"        # floor sensor; 0 = disabled, 1 = enabled
SYR_CMD_TMP              = "TMP"        # leakage temporary deactivation; 0 = disabled, 0-4294967295 seconds
SYR_CMD_BUZZER           = "BUZ"        # 0 = disabled, 1 = enabled
SYR_CMD_CONDUCT_LIMIT    = "CNL"        # conductivity limit; 0-5000uS/cm
SYR_CMD_CONDUCT_FACTOR   = "CNF"        # conductivity factor; 5-50 representing 0.5-5.0
SYR_CMD_LEAKAGE_WARNING  = "LWT"        # leakage warning notification; 80-99 in percent, 0 = off (presumably)
SYR_CMD_NEXT_MAINTENANCE = "SRV"        # next maintenance date; dd.mm.yyyy 
SYR_CMD_BATTERY          = "BAT"        # battery voltage;   1/100V x.xx
SYR_CMD_VOLTAGE          = "NET"        # dc supply voltage; 1/100V x.xx
SYR_CMD_RTC              = "RTC"        # linux epoch time; 0-4294967295
SYR_CMD_ADMIN            = "ADM"        # service = "(1)", admin = "(2)f"; reset with "clr" instead of "set" (".../clr/ADM")


SYR_ERROR_STRING    = "ERROR"      # error string to be returned if something went wrong; maybe "-1" would be better?

SYR_UNITS_REPL      = [ " mbar", "mL", "Vol[L]" ]  # for text/data replacement; imperial yet unknown; my device always puts out " mbar"

SYR_ALARM_CODES = {
    "FF" : "NO ALARM",
    "A1" : "ALARM END SWITCH",
    "A2" : "NO NETWORK",
    "A3" : "ALARM VOLUME LEAKAGE",
    "A4" : "ALARM TIME LEAKAGE",
    "A5" : "ALARM MAX FLOW LEAKAGE",
    "A6" : "ALARM MICRO LEAKAGE",
    "A7" : "ALARM EXT. SENSOR LEAKAGE",
    "A8" : "ALARM TURBINE BLOCKED",
    "A9" : "ALARM PRESSURE SENSOR ERROR",
    "AA" : "ALARM TEMPERATURE SENSOR ERROR",
    "AB" : "ALARM CONDUCTIVITY SENSOR ERROR",
    "AC" : "ALARM TO HIGH CONDUCTIVITY",
    "AD" : "LOW BATTERY",
    "AE" : "WARNING VOLUME LEAKAGE",
    "AF" : "ALARM NO POWER SUPPLY"
}

# TODO: The following are just placeholders; the real values are unknown (Co-Pilot did this :)
# Apparnetly that's not implemented in the device yet; the manual says "EN" and "DE" only.
# Querying "LNG" returns the string "0 (0=Deutsch 1=English)"
SYR_LANGUAGES = {
    0 : "Kartoffel",
    1 : "Brexit",
    2 : "Sangria",
    3 : "Pizza",
    4 : "Tyskie"
}

SYR_VALVE_STATES = {
    "10" : "CLOSED",
    "11" : "CLOSING",
    "20" : "OPEN",
    "21" : "OPENING",
    "30" : "UNDEFINED"
}


#############################################################################################################
APP_NOFILE           = False        # by default, everything is written to a file
APP_NOSTDOUT         = False        # by default, everything is printed to stdout
APP_RAW              = False        # by default, everything is printed in a human readable form
APP_LOGCONDUCTIVITY  = False        # by default, conductivity is not logged
APP_LOGTEMPERATURE   = False        # by default, temperature is not logged
APP_LOGPROFILE       = False        # by default, the currently activated profile is not logged

APP_CMD_HENLO        = 1            # typos and enums sock
APP_CMD_STATUS       = 2
APP_CMD_PROFILE      = 3
APP_CMD_PROFILE_SET  = 4
APP_CMD_CLEARALARM   = 5
APP_CMD_ALARMCODES   = 6
APP_CMD_SHOWPROFILES = 7
APP_CMD_SHOWPROFILE  = 8

APP_COMMAND          = None         # wild mix

APP_ERROR_NONE       = 0
APP_ERROR_ARGS       = 1
APP_ERROR_COMM       = 2


#############################################################################################################
# TESTING TESTING TESTING
# Only drafting some ideas here

SyrProfile_Cmd_dict = {
    # also funny; one could easily iterate over this dict
    # and use the same keys to store the data in another dict/class/...
    "SYR_CMD_PROFILE_X_NAME" : "PN",
    "SYR_CMD_PROFILE_X_VOL"  : "PV",
    "SYR_CMD_PROFILE_X_TIME" : "PT",
    "SYR_CMD_PROFILE_X_FLOW" : "PF",
    "SYR_CMD_PROFILE_X_MLEAK": "PM",
    "SYR_CMD_PROFILE_X_RTIME": "PR",
    "SYR_CMD_PROFILE_X_BUZZ" : "PB",
    "SYR_CMD_PROFILE_X_LEAKW": "PW"
}

SyrProfile_Values_dict = {
    # with keys from above
    "SYR_CMD_PROFILE_X_NAME" : "",
    "SYR_CMD_PROFILE_X_VOL"  : 0,
    "SYR_CMD_PROFILE_X_TIME" : 0,
    "SYR_CMD_PROFILE_X_FLOW" : 0,
    "SYR_CMD_PROFILE_X_MLEAK": 0,
    "SYR_CMD_PROFILE_X_RTIME": 0,
    "SYR_CMD_PROFILE_X_BUZZ" : 0,
    "SYR_CMD_PROFILE_X_LEAKW": 0
}

SyrProfile_Prints_dict = {
    # with keys from above
    "SYR_CMD_PROFILE_X_NAME" : "  name ........... ",
    "SYR_CMD_PROFILE_X_VOL"  : "  volume level ... ",
    "SYR_CMD_PROFILE_X_TIME" : "  time level ..... ",
    "SYR_CMD_PROFILE_X_FLOW" : "  flow level ..... ",
    "SYR_CMD_PROFILE_X_MLEAK": "  microleakage ... ",
    "SYR_CMD_PROFILE_X_RTIME": "  return time .... ",
    "SYR_CMD_PROFILE_X_BUZZ" : "  buzzer ......... ",
    "SYR_CMD_PROFILE_X_LEAKW": "  leakage warning. "
}


class SyrProfile_class:
    # probably overkill bc this is a fire and forget script
    def __init__(self) -> None:
        self.name           = ""
        self.volume         = 0
        self.time           = 0
        self.flow           = 0
        self.microleakage   = 0
        self.returntime     = 0
        self.buzzer         = 0
        self.leakagewarning = 0






#############################################################################################################
# NOTES

# getALA  returns ongoing alarm
# clrALA  clears ongoing alarm and opens the valve
# setALA  sets ongoing alarm; probably used by water sensors

# getALM  returns alarm history; requires admin mode; "Alarms:->A3 A3 A4 A4 A4 A4 A4 A4"
# clrALM  clears the complete alarm history list



#############################################################################################################
## PrintUsage
#############################################################################################################
def PrintUsage():
    """Prints the usage and command line options to stdout.
    """
    print( "Usage: SyrSafeTechLogger.py [options]" )
    print( "Options:" )
    print( "  --help          : print this help" )
    print( "  --ipaddr=addr   : set the IP address of the Syr SafeTech Connect device" )
    print( "  --henlo         : test presence of the device, print serial number, SW version and then quit" )
    print( "  --nofile        : do not write to a file" )
    print( "  --nostdout      : do not print to stdout (useful when used with nohup)" )
    print( "  --maxpolls=n    : stop after n polls" )
    print( "  --delay=n       : delay between set of polls in seconds; floating point allowed, e.g. --delay=1.5" )
    print( "  --raw           : print raw data; units 'mbar', 'mL', etc. are not removed" )
    print( "  --status        : print the current status and settings of the Syr, then quit" )
    print( "  --profile       : print name and number of active profile, then quit" )
    print( "  --profile=n     : select and activate profile number n" )
    print( "  --showprofiles  : print all available profiles, then quit")
    print( "  --showprofile=n : print the settings of profile number n, then quit; can display disabled profiles too")
    print( "  --clearalarm    : clear the ongoing alarm and open the valve" )
    print( "  --alarmcodes    : print a list with alarm codes, then quit" )
    print( "  --logcond       : measure and log conductivity too, off by default" )
    print( "  --logtemp       : measure and log temperature too, off by default" )
    print( "  --logprofile    : log currently activated profile" )
    print( "  --logall        : log all optional log options: conductivity, temperature, profile" )



#############################################################################################################
## CheckIPv4
#############################################################################################################
def CheckIPv4( ipaddr ):
    """Check if a string contains a valid IPv4 address.

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
    
    command: Command as string in lower or upper case letters. E.g. "AVO", "CEL", ...
    timeout: seconds to wait for a response

    Returns: the raw value of the requested command or "ERROR" if no response was received
    """
    command = command.upper()
    try:
        response = requests.get( "http://" + SYR_IPADDR + ":5333/safe-tec/get/" + command, timeout = timeout )
        # DEBUG DOTS
#        print(".", end="", flush=True)
    except:
        # one for all
        return SYR_ERROR_STRING

    if response.status_code == 200:
        # TODO: Apparently, this can really return None.
        # Output in the nohup.out file, from a days long run:
        #   Traceback (most recent call last):
        #     File "SyrSafeTechLogger/./SyrSafeTechLogger.py", line 378, in <module>
        #       dataLine = GetDataRaw( SYR_CMD_VALVE )       + "; " + \
        #   TypeError: can only concatenate str (not "NoneType") to str
        data = response.json()
        # quick and dirty fix for the above problem:
#        return data.get( 'get' + command )
        return str( data.get( 'get' + command ) )

    # just in case; unused; will not be reached
    return SYR_ERROR_STRING


#############################################################################################################
## SetData
#############################################################################################################
def SetDataRaw( command, parameter = None, timeout = 5, useCLR = False):
    """Write data to the Syr SafeTech
    
    command  : Command as string, in lower or upper case letters. E.g. "PRF", "PN1", "ADM" ...
    parameter: The parameter to be set, as a string. E.g. "0", "1", "(1)", "(2)f" 
    timeout  : seconds to wait for a response
    useCLR   : if true, use "clr" instead of "set", e.g. for a ".../clr/ADM" command to reset admin rights.

    Returns: the raw value of the requested command or "ERROR" if no response was received
    """
    command = command.upper()
    if parameter is None:
        parameter = ""
    else:
        parameter = "/" + parameter

    strReq = "http://" + SYR_IPADDR + ":5333/safe-tec/" + ( "clr/" if useCLR else "set/" ) + command + parameter

    try:
#        response = requests.get( "http://" + SYR_IPADDR + ":5333/safe-tec/set/" + command + "/" + parameter, timeout = timeout )
        response = requests.get( strReq, timeout = timeout )

    except:
        # one for all
        return SYR_ERROR_STRING

    if response.status_code == 200:
        data = response.json()
        # TODO: the responses are manifold; needs to be checked
        #       set/PRF/3    -->   {"setPRF3":"OK"}
        #       set/ADM(1)   -->   {"setADM(1)":"SERVICE"}
        return data
#        return data.get( 'set' + command )

    # just in case; unused; will not be reached
    return SYR_ERROR_STRING


#############################################################################################################
## ClrDataRaw
#############################################################################################################
def ClrDataRaw( command, timeout = 5 ):
    """Write ("clr") data to the Syr SafeTech
    
    command  : Command as string in lower or upper case letters. E.g. "PRF", "PN1", "ADM" ...
    timeout  : seconds to wait for a response

    Returns: the raw value of the requested command or "ERROR" if no response was received
    """

    return SetDataRaw( command, parameter=None, timeout=timeout, useCLR=True )


#############################################################################################################
## GetAndPrintProfiles
#############################################################################################################
# Actually, there should be something like a HAL here and for all the other things.
# Directly reading the data and printing it in the same function is horseshite.
# This thing's already a mess :)
def GetAndPrintProfiles( quiet = False ):
    """Read the number of available and configured profiles in the Syr.
    Print them to stdout if 'quiet' is False.

    quiet:  Do not print anything if set to True.

    Returns: An array with numbers of available profiles (1..8) or an empty array if no profiles are available.
    E.g. [ 1, 2, 3 ]
    """

    lstProfiles = []
    print( "  Profiles available ....... " + GetDataRaw( SYR_CMD_PROFILENUMS ) )
    print( "  Profile numbers .......... ", end = "" )
    for i in range( 1, 9 ):
        if ( ret := GetDataRaw( SYR_CMD_PROFILE_X_AVAIL + str(i) ) ) != SYR_ERROR_STRING:
            if ret == "1":
                print( str(i), end = " " )
                lstProfiles.append( i )
        else:
            # not nice :-/
            print( SYR_ERROR_STRING, end = " " )
    print()

    return lstProfiles



#############################################################################################################
## GetAndPrintProfileX
#############################################################################################################
# Actually, there should be something like a HAL here and for all the other things.
# Directly reading the data and printing it in the same function is horseshite.
# This thing's already a mess :)
def GetAndPrintProfileX( profNum = None, warnIfNotAvailable = False ):
    """Read the Syr SafeTech's profile number 'profNum' and print the contents to stdout.

    profNum: profile number as integer (1..8); None = active profile
    """

    # TODO: This will all fail if profNum is "ERROR" or None
    if profNum is None:
        profNum = GetDataRaw( SYR_CMD_PROFILE )
        print( "  Profile selected ......... " + (profNum:=GetDataRaw( SYR_CMD_PROFILE )) )

    # saves a lot of typing
    profNum = str( profNum )

    if warnIfNotAvailable:
        if GetDataRaw( SYR_CMD_PROFILE_X_AVAIL + profNum ) != "1":
            print( "  Profile " + profNum + " ................ WARNING, NOT CONFIGURED, NOT AVAILABLE!" )

    print( "  Profile " + profNum + " name ........... " + GetDataRaw( SYR_CMD_PROFILE_X_NAME  + profNum )         )
    print( "  Profile " + profNum + " volume level ... " + GetDataRaw( SYR_CMD_PROFILE_X_VOL   + profNum ) + "L"   )
    print( "  Profile " + profNum + " time level ..... " + GetDataRaw( SYR_CMD_PROFILE_X_TIME  + profNum ) + "s"   )
    print( "  Profile " + profNum + " flow level ..... " + GetDataRaw( SYR_CMD_PROFILE_X_FLOW  + profNum ) + "L/h" )
    print( "  Profile " + profNum + " microleakage ... " + ("on" if GetDataRaw( SYR_CMD_PROFILE_X_MLEAK + profNum ) == "1" else "off"))
    print( "  Profile " + profNum + " return time .... " + GetDataRaw( SYR_CMD_PROFILE_X_RTIME + profNum ) + "h"   )
    print( "  Profile " + profNum + " buzzer ......... " + ("on" if GetDataRaw( SYR_CMD_PROFILE_X_BUZZ  + profNum ) == "1" else "off"))    
    print( "  Profile " + profNum + " leakage warning. " + ("on" if GetDataRaw( SYR_CMD_PROFILE_X_LEAKW + profNum ) == "1" else "off"))



#############################################################################################################
## GetAndPrintStatus
#############################################################################################################
def GetAndPrintStatus():
    """Read (almost) all settings the Syr SafeTech and print them to stdout.
    """

    # print number of available/configured profiles
    GetAndPrintProfiles()

    # print content of active profile
    GetAndPrintProfileX()

    # set admin mode to read some of the data (power supply voltage, alarm history)
    print( "  Enter admin mode ......... " + str( SetDataRaw( SYR_CMD_ADMIN, "(1)" ) ) )

    print( "  Leakage temp disable ..... " + GetDataRaw( SYR_CMD_TMP)                        )
    print( "  Buzzer ................... " + ("on" if GetDataRaw( SYR_CMD_BUZZER) == "1" else "off"))
    print( "  Conductivity limit ....... " + GetDataRaw( SYR_CMD_CONDUCT_LIMIT)    + "uS/cm" )
    print( "  Conductivity factor ...... " + GetDataRaw( SYR_CMD_CONDUCT_FACTOR)             )
    print( "  Leakage warning .......... " + GetDataRaw( SYR_CMD_LEAKAGE_WARNING)  + "%"     )
    # not supported yet
    # print( "  Language ................. " + SYR_LANGUAGES.get( GetDataRaw( SYR_CMD_LANGUAGE), "UNKNOWN LANGUAGE" ) )
    print( "  Floor sensor ............. " + ("on" if GetDataRaw( SYR_CMD_FLOOR_SENSOR) == "1" else "off"))
    print( "  Next maintenance ......... " + GetDataRaw( SYR_CMD_NEXT_MAINTENANCE)           )
    print( "  Battery voltage .......... " + GetDataRaw( SYR_CMD_BATTERY)          + "V"     )
    print( "  Power supply voltage ..... " + GetDataRaw( SYR_CMD_VOLTAGE)          + "V"     )
    print( "  RTC ...................... " + (strRTC:=GetDataRaw( SYR_CMD_RTC) )             )
    try:
        intRTC = int( strRTC )
    except:
        intRTC = -1
    print( "  RTC converted............. " + ( str(datetime.datetime.fromtimestamp( intRTC )) if intRTC > 0 else "ERROR" ) )
    print( "  Ongoing alarm ............ " + SYR_ALARM_CODES.get( GetDataRaw( SYR_CMD_ALARM ), "UNKNOWN STATE") )
    print( "  Alarm memory ............. " + GetDataRaw( SYR_CMD_ALARM_MEMORY) )
    print( "  Last volume consumed ..... " + GetDataRaw( SYR_CMD_VOLUME_LAST)       + "L"    )

    tmp = GetDataRaw( SYR_CMD_VOLUME_TOTAL )   
    for strReplace in SYR_UNITS_REPL:
        tmp = tmp.replace( strReplace, "" )
    print( "  Total volume consumed .... " + tmp                                    + "L"    )

    # reset admin mode
    print( "  Leave admin mode ......... " + str( ClrDataRaw( SYR_CMD_ADMIN ) ) )


#############################################################################################################
if __name__ == "__main__":

    maxpolls = -1  # -1 = infinite (default); can be overridden by command line option "--maxpolls=<n>"

    # -------------------------------------------------------------------------------------------------------
    # minimal command line options
    for args in sys.argv:
        # ------------------------------
        if args == sys.argv[0]:
            continue
        # ------------------------------
        if args == "--help" or args == "-h" or args == "-?" or args == "/?":
            PrintUsage()
            sys.exit( APP_ERROR_NONE )
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
        elif args == "--alarmcodes":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_ALARMCODES
        # ------------------------------
        elif "--maxpolls=" in args:
            try:
                maxpolls = int( args[11:] )
            except:
                print( "ERROR: invalid value for --maxpolls", file=sys.stderr, flush=True )
                PrintUsage()
                sys.exit( APP_ERROR_ARGS )
            if maxpolls < 1:
                maxpolls = 1
        # ------------------------------
        elif "--delay=" in args:
            try:
                SYR_DELAY = abs( float( args[8:] ) )
            except:
                print( "ERROR: invalid value for --delay", file=sys.stderr, flush=True )
                PrintUsage()
                sys.exit( APP_ERROR_ARGS )
            if SYR_DELAY < 0.1:
                SYR_DELAY = 0
        # ------------------------------
        elif "--ipaddr=" in args:
            SYR_IPADDR = args[9:]
            if CheckIPv4( SYR_IPADDR ) is False:
                print( "ERROR: invalid IP address", file=sys.stderr, flush=True )
                PrintUsage()
                sys.exit( APP_ERROR_ARGS )
        # ------------------------------
        elif args == "--profile":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_PROFILE
        # ------------------------------
        elif "--profile=" in args:
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_PROFILE_SET
            try:
                profNumSet = int( args[10:] )
                if profNumSet < 1 or profNumSet > 8:
                    raise ValueError
            except:
                print( "ERROR: invalid value for --profile", file=sys.stderr, flush=True )
                PrintUsage()
                sys.exit( APP_ERROR_ARGS )
        # ------------------------------
        elif args == "--clearalarm":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_CLEARALARM
        # ------------------------------
        elif args == "--logcond":
            APP_LOGCONDUCTIVITY = True
        # ------------------------------
        elif args == "--logtemp":
            APP_LOGTEMPERATURE = True
        # ------------------------------
        elif args == "--logprofile":
            APP_LOGPROFILE = True
        # ------------------------------
        elif args == "--logall":
            APP_LOGCONDUCTIVITY = True
            APP_LOGTEMPERATURE  = True
            APP_LOGPROFILE      = True
        # ------------------------------
        elif args == "--showprofiles":
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_SHOWPROFILES
        # ------------------------------
        elif "--showprofile=" in args:
            try:
                profNum = int( args[14:] )
                if profNum < 1 or profNum > 8:
                    raise ValueError
            except:
                print( "ERROR: invalid value for --showprofile", file=sys.stderr, flush=True )
                PrintUsage()
                sys.exit( APP_ERROR_ARGS )
            # only accept the first command
            if APP_COMMAND is None:
                APP_COMMAND = APP_CMD_SHOWPROFILE
        # ------------------------------
        else:
            if args == "--maxpolls" or args == "--delay" or args == "--ipaddr":
                print( "ERROR: missing value for " + args, file=sys.stderr, flush=True)
            else:
                print( "ERROR: unknown option: " + args, file=sys.stderr, flush=True )
            PrintUsage()
            sys.exit( APP_ERROR_ARGS )

    if APP_NOFILE and APP_NOSTDOUT:
        print( "ERROR: --nofile and --nostdout together does not make sense at all", file=sys.stderr, flush=True )
        sys.exit( APP_ERROR_ARGS )

    if SYR_IPADDR == "0.0.0.0":
        print( "ERROR: missing IP address", file=sys.stderr, flush=True )
        PrintUsage()
        sys.exit( APP_ERROR_ARGS )

    # -------------------------------------------------------------------------------------------------------
    # print a list with alarm codes
    if APP_COMMAND == APP_CMD_ALARMCODES:
        print( "Alarm codes:" )
        for key, value in SYR_ALARM_CODES.items():
            print( "  " + key + ": " + value )
        sys.exit( APP_ERROR_NONE )

    # -------------------------------------------------------------------------------------------------------
    # always: check if the device is there and alive
    if ( syrVersion := GetDataRaw( SYR_CMD_VERSION ) ) == SYR_ERROR_STRING:
        print( "ERROR: no response from Syr SafeTech Connect device", file=sys.stderr, flush=True )
        sys.exit( APP_ERROR_COMM )
    if ( syrSerial := GetDataRaw( SYR_CMD_SERIAL ) ) == SYR_ERROR_STRING:
        print( "ERROR: no response from Syr SafeTech Connect device", file=sys.stderr, flush=True )
        sys.exit( APP_ERROR_COMM )

    # -------------------------------------------------------------------------------------------------------
    # print or change the profile
    if APP_COMMAND == APP_CMD_PROFILE or APP_COMMAND == APP_CMD_PROFILE_SET:
        print( "  Profile selected ......... " + (profNum:=GetDataRaw( SYR_CMD_PROFILE )) )
        print( "  Profile " + profNum + " name ........... " + GetDataRaw( SYR_CMD_PROFILE_X_NAME + profNum ) )
        if APP_COMMAND == APP_CMD_PROFILE_SET:
            # profNum is a string
            if str(profNumSet) == profNum:
                print( "  Profile " + profNum + " ................ already active" )
            else:
                print( "  Setting profile " + str(profNumSet) + "......... " + str( SetDataRaw( SYR_CMD_PROFILE, str(profNumSet ) ) ) )
        sys.exit( APP_ERROR_NONE )

    # -------------------------------------------------------------------------------------------------------
    # a short "henlo" or a more detailed status
    if APP_COMMAND == APP_CMD_HENLO or APP_COMMAND == APP_CMD_STATUS:
        print( "Found device:" )
        print( "  Serial ................... " + syrSerial )
        print( "  Version .................. " + syrVersion )
        if APP_COMMAND == APP_CMD_STATUS:
            GetAndPrintStatus()
        sys.exit( APP_ERROR_NONE )

    # -------------------------------------------------------------------------------------------------------
    # show all available profiles
    if APP_COMMAND == APP_CMD_SHOWPROFILES:
        for profNum in GetAndPrintProfiles():
            print()
            GetAndPrintProfileX( profNum )
        sys.exit( APP_ERROR_NONE )

    # -------------------------------------------------------------------------------------------------------
    # show a single profile, even if it's not "available", aka configured
    if APP_COMMAND == APP_CMD_SHOWPROFILE:
        GetAndPrintProfileX( profNum, warnIfNotAvailable=True )
        sys.exit( APP_ERROR_NONE )

    # -------------------------------------------------------------------------------------------------------
    # clear the ongoing alarm
    if APP_COMMAND == APP_CMD_CLEARALARM:
        print( "  Ongoing alarm ............ " + SYR_ALARM_CODES.get( alarmState:=GetDataRaw( SYR_CMD_ALARM ), "UNKNOWN STATE") )
        if alarmState == "FF":
            # instead of ignoring the command, it could be a good idea to open the valve
#            sys.exit( APP_ERROR_NONE )
            pass
        print( "  Enter admin mode ......... " + str( SetDataRaw( SYR_CMD_ADMIN, "(1)" ) ) )
        print( "  Clear alarm .............. " + str( ClrDataRaw( SYR_CMD_ALARM ) ) )
        print( "  Leave admin mode ......... " + str( ClrDataRaw( SYR_CMD_ADMIN ) ) )
        print( "  Checking alarm state...... " + SYR_ALARM_CODES.get( GetDataRaw( SYR_CMD_ALARM ), "UNKNOWN STATE") )
        sys.exit( APP_ERROR_NONE )



    # -------------------------------------------------------------------------------------------------------
    # preparations for the main "logger" loop
    if APP_NOFILE is False:
        fout = open( time.strftime("%Y%m%d%H%M%S") + "_SyrSafeTech.log", "w+t" )
    else:
        fout = None

    # -------------------------------------------------------------------------------------------------------
    # the main "logger" loop
    while True:
        timeHuman   = time.asctime()
        timeMachine = time.strftime("%Y;%m;%d; %H;%M;%S")

        # get the valve state as a number and in human readable form for stdout
        valveStateCode = GetDataRaw( SYR_CMD_VALVE )
        valveStateStr  = SYR_VALVE_STATES.get( valveStateCode, "UNKNOWN STATE" )

        # log everything in its raw form for now
        dataLine = GetDataRaw( SYR_CMD_PRESSURE )    + "; " + \
                   GetDataRaw( SYR_CMD_FLOW )        + "; " + \
                   GetDataRaw( SYR_CMD_VOLUME )      + "; " + \
                   GetDataRaw( SYR_CMD_VOLUME_LAST )
        
        # get thealarm state as a number and in human readable form for stdout
        errorCode = GetDataRaw( SYR_CMD_ALARM )
        errorStr  = SYR_ALARM_CODES.get( errorCode, "UNKNOWN ERROR" )

        dataLine2 = ""

        if APP_LOGCONDUCTIVITY:
            dataLine2 =  "; " + GetDataRaw( SYR_CMD_CONDUCTIVITY )
        
        if APP_LOGTEMPERATURE:
            dataLine2 += "; " + GetDataRaw( SYR_CMD_TEMP )
        
        if APP_LOGPROFILE:
            dataLine2 += "; " + GetDataRaw( SYR_CMD_PROFILE )


        if APP_RAW is False:
            for strReplace in SYR_UNITS_REPL:
                dataLine = dataLine.replace( strReplace, "" )


        if APP_NOSTDOUT is False:
            print( timeHuman + "; " + valveStateStr + "; " + dataLine + "; " + errorStr + dataLine2 )

        if APP_NOFILE is False:
            fout.write( timeMachine + "; " + valveStateCode + "; " + dataLine + "; " + errorCode + dataLine2 + "\n" )
            fout.flush() 


        if ( maxpolls > 0 ):
            if ( maxpolls := maxpolls - 1 ) <= 0:
                break

        time.sleep( SYR_DELAY )
    # END while


    if APP_NOFILE is False:
        fout.close()

    sys.exit( APP_ERROR_NONE )

# END __main__

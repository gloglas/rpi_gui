import sys, time, json, os
import keyboard # https://github.com/boppreh/keyboard
if __name__ == "__main__":
    import argparse

script=[]
dontprint = True
lastevent = None
actualLine = None
delay_threshold=200
keys_count=0

input_log_file = None
output_log_file = None
ducky_file = None


# I don't wanna modify the library...
# but I did it anyway: https://github.com/boppreh/keyboard/pull/429
def _getjson(a, ensure_ascii=False):
    attrs = dict(
        (attr, getattr(a, attr)) for attr in ['event_type', 'scan_code', 'name', 'time', 'device', 'is_keypad','modifiers']
        if not attr.startswith('_')
    )
    return json.dumps(attrs, ensure_ascii=ensure_ascii)

rev_canonical_names = {
    'next': 'pagedown',
    'prior': 'pageup',
    "select": "end",
    "find": "home",
    "space": "spacebar",
}
scan_codes = {
    99: "PRINTSCREEN",
    125: "GUI",
    126: "GUI",
    142: "MOON",
    100: "ALTGR",
}

def cleanup():
    global script
    global dontprint
    global lastevent
    global actualLine
    global input_log_file
    global output_log_file
    global ducky_file
    global keys_count

    script=[]
    dontprint = True
    lastevent = None
    actualLine = None
    input_log_file = None
    output_log_file = None
    ducky_file = None
    keys_count = 0

def save_pressed_keys(e):
    global keys_count
    global script
    #Save only keys to get no errors in keypress logs
    if e.scan_code in scan_codes:
        e.name = scan_codes[e.scan_code]
    if e.name in rev_canonical_names:
        e.name = rev_canonical_names[e.name]
    with open("/tmp/.duckylog", "a") as af:
        af.write(_getjson(e) + ",")
    if e.event_type == "up":
        keys_count = keys_count + 1

def print_pressed_keys(e):
    global script
    global lastevent
    global actualLine
    global dontprint
        
    if e.scan_code in scan_codes:
        e.name = scan_codes[e.scan_code]
    if e.name in rev_canonical_names:
        e.name = rev_canonical_names[e.name]
    
    if output_log_file is not None:
        with open(output_log_file, "a") as af:
            af.write(_getjson(e) + ",")
    
    e.name = (e.name.upper(), e.name)[len(e.name) == 1]
    
    if lastevent is not None:
        if lastevent.event_type == "up" and e.event_type == "down":
            delay = round((e.time-lastevent.time)*1000)
            if delay >= delay_threshold:
                if actualLine is not None and actualLine.startswith("STRING"):
                    script.append(actualLine)
                    actualLine = None
                script.append("DELAY %s" % delay)
    
    if e.event_type == "down":
        dontprint = False
        if len(e.name) == 1 and not e.modifiers and not keyboard.is_modifier(e.scan_code):
            if actualLine is None:
                actualLine = "STRING "
            elif e.name in actualLine and not actualLine.startswith("STRING"):
                pass
            actualLine = actualLine + e.name
        
        else:
            if actualLine is not None:
                if e.name in actualLine:
                    pass
                if actualLine.startswith("STRING"):
                    if actualLine is not None:
                        script.append(actualLine)
                    actualLine = e.name
                else:
                    if e.name not in actualLine:
                        actualLine = actualLine + " " + e.name
            else:
                actualLine = e.name
        
    else: #up
        if actualLine is not None:
            if not actualLine.startswith("STRING"):
                if e.name in actualLine:
                    if not dontprint:
                        script.append(actualLine)
                    
                    actualLine = actualLine.replace(e.name, "").replace("  "," ").strip()
                    actualLine = (actualLine, None)[actualLine == ""]
                    if actualLine is not None:
                        dontprint = True

    lastevent = e
    i = actualLine

def hook(duckyfile=None, logfile=None):
    global ducky_file
    global output_log_file

    if duckyfile is not None and duckyfile != "":
        ducky_file = duckyfile
    if logfile is not None and logfile != "":
        output_log_file = logfile
        with open(output_log_file, "w") as wf:
            wf.write("[")
    
    os.system("rm -f /tmp/.duckylog")
    with open("/tmp/.duckylog", "w") as wf:
        wf.write("[")
    keyboard.hook(save_pressed_keys)

def fromFile(inputfile,duckyfile=None):
    global ducky_file
    global script
    global output_log_file
    if duckyfile is not None:
        ducky_file=duckyfile
    output_log_file = None
    
    i = script
    with open(inputfile) as json_file:
        data = json.load(json_file)

    for var in data:
        x = json.dumps(var)
        if x != "{}":
            print_pressed_keys(keyboard.KeyboardEvent(**json.loads(x)))
    
    if actualLine is not None:
        i.append(actualLine)

    if ducky_file is not None:
        with open(ducky_file, "w") as wf:
            for var in i:
                wf.write(var + "\n")
    cleanup()
    return i
    
def stop_gethook():
    global script
    
    i = script
    keyboard.unhook_all()
    if actualLine is not None:
        i.append(actualLine)

    if output_log_file is not None:
        with open(output_log_file, "a") as af:
            af.write("{}]")
        if len(i) == 0:
            os.remove(output_log_file)
    if ducky_file is not None:
        with open(ducky_file, "w") as wf:
            for var in i:
                wf.write(var + "\n")
        if len(i) == 0:
            os.remove(ducky_file)
    
    with open("/tmp/.duckylog", "a") as af:
        af.write("{}]")
    x = output_log_file
    fromFile("/tmp/.duckylog", ducky_file)
    if x is not None:
        os.system("cp -f /tmp/.duckylog " + x)
    cleanup()
    return i

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Keystrokes to duckyscript')
    parser.add_argument("-d", "--ducky", action="store", dest="ducky", default=None, help="Duckyscript output")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=None, help="Verbose output")
    parser.add_argument("-o", "--output-log", action="store", dest="outputlog", default=None, help="Raw json log output")
    parser.add_argument("-i", "--input-log", action="store", dest="analyzelog", default=None, help="Analyze from raw json log output")
    arguments = parser.parse_args()
    
    if arguments.analyzelog is None:
        if arguments.verbose:
            print("Initializing...")
        hook(arguments.ducky,arguments.outputlog)
        if arguments.verbose:
            print("Done! Hit ctrl+c to stop!")
        try:
            keyboard.wait()
        except KeyboardInterrupt:
            if arguments.verbose:
                print("Leaving...")
        for var in stop_gethook():
            print(var)
    else:
        for var in fromFile(arguments.analyzelog,arguments.ducky):
            print(var)

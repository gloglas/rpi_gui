#!/usr/bin/env python3
import threading, os, sys, smbus, time, pyudev, serial, netifaces, struct, json
from subprocess import STDOUT, check_output
from PIL import Image, ImageDraw, ImageFont, ImageColor
import LCD_Config
import LCD_1in44
import RPi.GPIO as GPIO
import keys
# https://github.com/linshuqin329/UPS-Lite
# https://www.waveshare.com/wiki/File:1.44inch-LCD-HAT-Code.7z

if os.getuid() != 0:
	print("You need a sudo to run this!")
	exit()

print("Hi! Display routine has started!")
start_time = time.time()
upslite = False

####### Classes except menu #######
### Global mostly static values ###
class Defaults():
    start_text = [12, 22]
    text_gap = 12
    
    updown_center = 52
    updown_pos = [15, updown_center, 88]
    
    hid_path = "/usr/local/P4wnP1/HIDScripts/"
    scripts_path = "/usr/local/P4wnP1/scripts/"
    munifying_path = "/root/munifying/"
    imgstart_path = "/root/"
    
    install_path = "/root/rpi_gui/"
    config_file = install_path + "gui_conf.json"
    
    hid_ducky_path = install_path + "ducky/"
    hid_log_path = install_path + "log/"

### Color scheme class ###
class template():
    # Color values
    border = "#0e0e6b"
    background = "#000000"
    text = "#9c9ccc"
    selected_text = "#EEEEEE"
    select = "#141494"
    gamepad = select
    gamepad_fill = selected_text

    # Render the border
    def DrawBorder(self):
        draw.line([(127, 12), (127, 127)], fill=self.border, width=5)
        draw.line([(127, 127), (0, 127)], fill=self.border, width=5)
        draw.line([(0, 127), (0, 12)], fill=self.border, width=5)
        draw.line([(0, 12), (128, 12)], fill=self.border, width=5)
        
    # Render inside of the border
    def DrawMenuBackground(self):
        draw.rectangle((3, 14, 124, 124), fill=self.background)

    # I don't know how to python pass 'class.variable' as reference properly
    def Set(self, index, color):
        if index == 0:
            self.background = color
        elif index == 1:
            self.border = color
            self.DrawBorder()
        elif index == 2:
            self.text = color
        elif index == 3:
            self.selected_text = color
        elif index == 4:
            self.select = color
        elif index == 5:
            self.gamepad = color
        elif index == 6:
            self.gamepad_fill = color
            
    def Get(self, index):
        if index == 0:
            return self.background
        elif index == 1:
            return self.border
        elif index == 2:
            return self.text
        elif index == 3:
            return self.selected_text
        elif index == 4:
            return self.select
        elif index == 5:
            return self.gamepad
        elif index == 6:
            return self.gamepad_fill

    # Methods for JSON export
    def Dictonary(self):
        x = {
            "BORDER" : self.border,
            "BACKGROUND" : self.background,
            "TEXT" : self.text,
            "SELECTED_TEXT" : self.selected_text,
            "SELECTED_TEXT_BACKGROUND" : self.select,
            "GAMEPAD" : self.gamepad,
            "GAMEPAD_FILL" : self.gamepad_fill
        }
        return x
    def LoadDictonary(self, dic):
        self.Set(1,dic["BORDER"])
        self.background = dic["BACKGROUND"]
        self.text = dic["TEXT"]
        self.selected_text = dic["SELECTED_TEXT"]
        self.select = dic["SELECTED_TEXT_BACKGROUND"]
        self.gamepad = dic["GAMEPAD"]
        self.gamepad_fill = dic["GAMEPAD_FILL"]

####### Simple methods #######
### Get any button press ###
def getButton():
    while 1:
        for item in PINS:
            if GPIO.input(PINS[item]) == 0:
                return item

### Get temperature of RPI ###
def temp():
    # return os.system("cat /sys/class/thermal/thermal_zone0/temp")
    file = open("/sys/class/thermal/thermal_zone0/temp", 'r')
    x = int(file.read())/1000
    file.close()
    return x

### Exit & cleanup ###
def Leave(poweroff=False):
    try:
        for x in range(5):
            for thread in threads:
                thread.cancel()
        GPIO.cleanup()
    except Exception:
        pass
    if poweroff:
        os.system("sync && poweroff")
    print("Bye!")
    exit()

def Restart():
    print("Restarting the UI!")
    Dialog("Restarting!", False)
    arg = ["-n","-5",os.sys.executable] + sys.argv
    os.execv(os.popen("whereis nice").read().split(" ")[1], arg)
    Leave()

### UPS Lite functions ###
def readVoltage(bus):
    if not upslite:
        return 0
    address = 0x36
    read = bus.read_word_data(address, 0X02)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    voltage = swapped * 1.25 / 1000/16
    return voltage
def readCapacity(bus):
    if not upslite:
        return 0
    address = 0x36
    read = bus.read_word_data(address, 0X04)
    swapped = struct.unpack("<H", struct.pack(">H", read))[0]
    capacity = swapped/256
    return capacity
def QuickStart(bus):
    if not upslite:
        return
    address = 0x36
    bus.write_word_data(address, 0x06, 0x4000)
def PowerOnReset(bus):
    if not upslite:
        return
    address = 0x36
    bus.write_word_data(address, 0xfe, 0x0054)
def charging():
    if not upslite:
        return False
    return (GPIO.input(4) == GPIO.HIGH)

### Two threaded functions ###
# One for updating status bar and one for refreshing display #
def updateStats():
    global threads
    if upslite:
        if (readCapacity(bus) < 5 or temp() > 70):
            os.system("sync && poweroff")

    draw.line([(0, 4), (128, 4)], fill="#222", width=10)
    if upslite:
        draw.text((0, 0), "%5i%%" % readCapacity(bus) + " %5.2fV" % readVoltage(bus) + "   " + ("N", "Y")
              [charging()] + "       " + str(temp()).split('.')[0] + " °C ", fill="WHITE", font=font)
    else:
	draw.text((0, 0),"                 " + str(temp()).split('.')[0] + " °C ", fill="WHITE", font=font)
    threads[0] = threading.Timer(5, updateStats)
    threads[0].start()
def refreshDisplay():
    global threads
    LCD.LCD_ShowImage(image, 0, 0)
    threads[1] = threading.Timer(0.011, refreshDisplay)
    threads[1].start()

### JSON config ###
def SaveConfig():
    data = {}
    data["PINS"] = PINS
    data["PATHS"] = { "BASH_SCRIPTS" : default.scripts_path, "HID" : default.hid_path, "MUNIFYING" : default.munifying_path, "IMAGEBROWSER_START" : default.imgstart_path, "ANALYZED_HID" : default.hid_ducky_path, "ANALYZED_HID_LOGS" : default.hid_log_path}
    data["COLORS"] = color.Dictonary()
    print(json.dumps(data, indent=4, sort_keys=True))
    json.dump(data, open(default.config_file, "w"), indent=4, sort_keys=True)
    print("Config has been saved!")
def LoadConfig():
    global PINS
    global default
    
    if not (os.path.exists(default.config_file) and os.path.isfile(default.config_file)):
        print("Can't find a config file! Creating one at '" + default.config_file + "'...")
        SaveConfig()

    with open(default.config_file, "r") as rf:
        data = json.load(rf)
        default.hid_path = data["PATHS"].get("HID",default.hid_path)
        default.scripts_path = data["PATHS"].get("BASH_SCRIPTS", default.scripts_path)
        default.munifying_path = data["PATHS"].get("MUNIFYING", default.munifying_path)
        default.hid_ducky_path = data["PATHS"].get("ANALYZED_HID", default.hid_ducky_path)
        default.hid_log_path = data["PATHS"].get("ANALYZED_HID_LOGS", default.hid_log_path)
        default.imgstart_path = data["PATHS"].get("IMAGEBROWSER_START", default.imgstart_path)
        
        os.popen("mkdir -p " + default.hid_ducky_path).read()
        os.popen("mkdir -p " + default.hid_log_path).read()
        
        PINS = data.get("PINS", PINS)
        try:
            color.LoadDictonary(data["COLORS"])
        except:
            pass
        GPIO.setmode(GPIO.BCM)
        for item in PINS:
            GPIO.setup(PINS[item], GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("Config loaded!")

####### Drawing functions #######

### Simple message box ###
# (Text, Wait for confirmation)  #
def Dialog(a, wait=True):
    draw.rectangle([7, 35, 120, 95], fill="#ADADAD")
    draw.text((35 - len(a), 45), a, fill="#000000")
    draw.rectangle([45, 65, 70, 80], fill="#FF0000")
    
    draw.text((50, 68), "OK", fill=color.selected_text)
    if wait:
        time.sleep(0.25) 
        getButton()

### Yes or no dialog ###
# (b is second text line)
def YNDialog(a="Are you sure?", y="Yes", n="No",b=""):
    draw.rectangle([7, 35, 120, 95], fill="#ADADAD")
    draw.text((35 - len(a), 40), a, fill="#000000")
    draw.text((12, 52), b, fill="#000000")
    time.sleep(0.25)
    answer = False
    while 1:
        render_color = "#000000"
        render_bg_color = "#ADADAD"
        if answer:
            render_bg_color = "#FF0000"
            render_color = color.selected_text
        draw.rectangle([15, 65, 45, 80], fill=render_bg_color)
        draw.text((20, 68), y, fill=render_color)

        render_color = "#000000"
        render_bg_color = "#ADADAD"
        if not answer:
            render_bg_color = "#FF0000"
            render_color = color.selected_text
        draw.rectangle([76, 65, 106, 80], fill=render_bg_color)
        draw.text((86, 68), n, fill=render_color)

        button = getButton()
        if button == "KEY_LEFT_PIN" or button == "KEY1_PIN":
            answer = True
        elif button == "KEY_RIGHT_PIN" or button == "KEY3_PIN":
            answer = False
        elif button == "KEY2_PIN" or button == "KEY_PRESS_PIN":
            return answer

### Scroll through text pictures ###
# 8 lines of text on screen at once
# No selection just scrolling through info
def GetMenuPic(a):
    # a=[ [row,2,3,4,5,6,7,8] <- slide, [1,2,3,4,5,6,7,8] ]
    slide=0
    while 1:
        arr=a[slide]
        color.DrawMenuBackground()
        for i in range(0, len(arr)):
            render_text = arr[i]
            render_color = color.text
            draw.text((default.start_text[0], default.start_text[1] + default.text_gap * i),
                      render_text[:m.max_len], fill=render_color)
        time.sleep(0.25)
        button = getButton()       
        if button == "KEY_UP_PIN":
            slide = slide-1
            if slide < 0:
                slide = len(a)-1
        elif button == "KEY_DOWN_PIN":
            slide = slide+1
            if slide >= len(a):
                slide = 0
        elif button == "KEY_PRESS_PIN" or button == "KEY_RIGHT_PIN":
            return slide
        elif button == "KEY_LEFT_PIN":
            return -1

### Render first lines of array ###
# Kinda useless but whatever
def ShowLines(arr,bold=[]):
    color.DrawMenuBackground()
    arr = arr[-8:]
    for i in range(0, len(arr)):
        render_text = arr[i]
        render_color = color.text
        if i in bold:
            render_text = m.char + render_text
            render_color = color.selected_text
            draw.rectangle([(default.start_text[0]-5, default.start_text[1] + default.text_gap * i),
                            (120, default.start_text[1] + default.text_gap * i + 10)], fill=color.select)
        draw.text((default.start_text[0], default.start_text[1] + default.text_gap * i),
                    render_text[:m.max_len], fill=render_color)

### Main method for selecting stuff ###
# Infinite scroll; Scrolling text;
# This newer one does deal with duplicates but not by default.
# When you deal with dupes the whole operation is 0.02sec slower.
def GetMenuString(inlist,duplicates=False):
    select = 0
    inc = 0
    empty = False
    if len(inlist) < 1:
        inlist = ["Nothing here :(   "]
        empty = True
    if duplicates:
        newlist=[]
        dic = {}
        i=0
        for var in inlist:
            newlist.append(''.join((str(i),"#",str(var))))
            i = i+1
        inlist = newlist
        #newlist still Used
        print(newlist)
    
    while 1:
        color.DrawMenuBackground()
        arr = inlist[0: (len(inlist), 8)[len(inlist) > 8] ]
        for i in range(0, len(arr)):
            render_text = (arr[i], ''.join(arr[i].split("#")[1:]))[duplicates]
            render_color = color.text
            if(select == i):
                render_text = m.char + render_text
                render_color = color.selected_text
                draw.rectangle([(default.start_text[0]-5, default.start_text[1] + default.text_gap * i),
                                (120, default.start_text[1] + default.text_gap * i + 10)], fill=color.select)
            draw.text((default.start_text[0], default.start_text[1] + default.text_gap * i),
                      render_text[:m.max_len], fill=render_color)
        time.sleep(0.25)
        
        if len(arr[inc] + m.char) >= m.max_len:
            counter = time.time()
            button = ""
            scroll_text = (" " + arr[inc]," " + ''.join(arr[inc].split("#")[1:]))[duplicates]
            
            while button == "":
                for item in PINS:
                    if GPIO.input(PINS[item]) == 0:
                        button = item
                        break
                if (time.time() - counter) > 0.75: # Less delay for the buttons -> scrolling
                    scroll_text = scroll_text[1:] + scroll_text[0]
                    draw.rectangle([(default.start_text[0]-5, default.start_text[1] + default.text_gap * select),
                                    (120, default.start_text[1] + default.text_gap * select + 10)], fill=color.select)
                    draw.text((default.start_text[0], default.start_text[1] + default.text_gap * select),
                          (m.char + scroll_text)[:m.max_len], fill=color.selected_text)    
                    counter = time.time()
        else:   
            button = getButton()
                     
        if button == "KEY_UP_PIN":
            inc = inc-1
            if inc < 0 and len(inlist) > 9:
                inlist = inlist[-1:] + inlist[:-1]
                inc = 0
        elif button == "KEY_DOWN_PIN":
            inc = inc+1
            if inc >= 7 and len(inlist) > 9:
                inlist = inlist[1:] + inlist[:1]
                inc = 6
        elif button == "KEY_PRESS_PIN" or button == "KEY_RIGHT_PIN":
            if duplicates:
                if empty:
                    return (-2,"")
                return (int(arr[inc].split("#")[0]),''.join(arr[inc].split("#")[1:]))
            else:
                if empty:
                    return ""
                return arr[inc]
        elif button == "KEY_LEFT_PIN":
            if duplicates:
                return (-1,"")
            else:
                return ""
        if inc >= len(arr) and len(inlist) <= 9:
            inc = 0
        if inc < 0 and len(inlist) <= 9:
            inc = len(arr)-1
        select = inc

### Draw up down triangles ###
color = template()
def DrawUpDown(value, offset=0, up=False,down=False, render_color=color.text):
    draw.polygon([(offset, 53), (10 + offset, 35), (20+offset, 53)],
        outline=color.gamepad, fill=(color.background, color.gamepad_fill)[up])
    draw.polygon([(10+offset, 93), (20+offset, 75), (offset, 75)],
        outline=color.gamepad, fill=(color.background, color.gamepad_fill)[down])
    
    draw.rectangle([( offset + 2, 60),(offset+30, 70)], fill=color.background)
    draw.text((offset + 2, 60), str(value) , fill=render_color)

### Screen for selecting RGB color ###
def GetColor(final_color="#000000"):
    color.DrawMenuBackground()
    time.sleep(0.4)
    i_rgb = 0
    render_offset = default.updown_pos
    desired_color = list(int(final_color[i:i+2], 16) for i in (1, 3, 5))

    while GPIO.input(PINS["KEY_PRESS_PIN"]):
        render_up = False
        render_down = False
        final_color='#%02x%02x%02x' % (desired_color[0],desired_color[1],desired_color[2])
        
        draw.rectangle([(default.start_text[0]-5, 1+ default.start_text[1] + default.text_gap * 0),(120, default.start_text[1] + default.text_gap * 0 + 10)], fill=final_color)
        draw.rectangle([(default.start_text[0]-5, 3+ default.start_text[1] + default.text_gap * 6),(120, default.start_text[1] + default.text_gap * 6 + 12)], fill=final_color)
        
        DrawUpDown(desired_color[0],render_offset[0],render_up,render_down,(color.text, color.selected_text)[i_rgb == 0])
        DrawUpDown(desired_color[1],render_offset[1],render_up,render_down,(color.text, color.selected_text)[i_rgb == 1])
        DrawUpDown(desired_color[2],render_offset[2],render_up,render_down,(color.text, color.selected_text)[i_rgb == 2])
        
        button = getButton()
        if button == "KEY_LEFT_PIN":
            i_rgb = i_rgb - 1
            time.sleep(0.1)
        elif button == "KEY_RIGHT_PIN":
            i_rgb = i_rgb + 1
            time.sleep(0.1)
        elif button == "KEY_UP_PIN":
            desired_color[i_rgb] = desired_color[i_rgb] + 5
            render_up = True
        elif button == "KEY_DOWN_PIN":
            desired_color[i_rgb] = desired_color[i_rgb] - 5
            render_down = True
        elif button == "KEY1_PIN":
            desired_color[i_rgb] = desired_color[i_rgb] + 1
            render_up = True
        elif button == "KEY3_PIN":
            desired_color[i_rgb] = desired_color[i_rgb] - 1
            render_down = True
        elif button == "KEY_PRESS_PIN":
            break

        if i_rgb > 2:
            i_rgb = 0
        elif i_rgb < 0:
            i_rgb = 2
        
        if desired_color[i_rgb] > 255:
            desired_color[i_rgb] = 0
        elif desired_color[i_rgb] < 0:
            desired_color[i_rgb] = 255
            
        DrawUpDown(desired_color[i_rgb],render_offset[i_rgb],render_up,render_down,color.selected_text)
        time.sleep(0.1)
    return final_color

### Set color based on indexes (not reference pls help)###
def SetColor(a):
    m.which = m.which + "1"
    c = GetColor(color.Get(a))
    if YNDialog(a="Set color to?", y="Yes", n="No",b=("    " + c) ):
        color.Set(a, c)
        Dialog("   Done!")
    m.which = m.which[:-1]

####### Attacks & menu functions #######

### Show munifying info on the screen ###
def RenderInfo(minfo):
    setup_info = True
    dev_num = 0
    render_data=[[]]
    dev_i = 1
    for item in minfo.split("\n"):
        if "losing Logitech" in item:
            break
        if setup_info:
            if "Firmware" in item:
                render_data[0].append("FW: " + item.split(':')[1].strip())
            elif "Bootloader" in item:
                render_data[0].append("Bootloader: " + item.split(':')[1].strip() )
            elif "WPID" in item:
                render_data[0].append("WPID: " + item.split(':')[1].strip() )
            elif "Connected devices" in item:
                dev_num = int(item.split(':')[1].strip())
                render_data[0].append("Devices:" + str(dev_num) )
            elif "Device Info" in item:
                setup_info = False
                if dev_num < 1:
                    break
        else:
            if "Device type" in item:
                render_data.append([])
                render_data[dev_i].append("T: " + item.split(':')[1].strip())
            elif "Serial" in item:
                render_data[dev_i].append("S: " + ':'.join(item.split(':')[1:]).strip())
            elif "Name" in item:
                render_data[dev_i].append("Name: " + item.split(':')[1].strip())
            elif "RF address" in item:
                render_data[dev_i].append(':'.join(item.split(':')[1:]).strip())
            elif "Device Info" in item:
                dev_i = dev_i + 1
            elif "Key:" in item:
                render_data[dev_i].append(item.split(':')[1].strip())
                if dev_i == dev_num:
                    break
    GetMenuPic(render_data)

### Gamepad ###
def Gamepad():
    color.DrawMenuBackground()
    time.sleep(0.5)
    draw.rectangle((25, 55, 45, 73), outline=color.gamepad,
                   fill=color.background)
    draw.text((28, 59), "<<<", fill=color.gamepad)
    m.which = m.which + "1"
    # Don't render if you dont need to => less flickering
    lastimg = [0, 0, 0, 0, 0, 0, 0]
    while GPIO.input(PINS["KEY_PRESS_PIN"]):
        write = ""
        x = 0
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY_UP_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " UP"
        if i != lastimg[x] or i == 0:
            draw.polygon([(25, 53), (35, 35), (45, 53)],
                         outline=color.gamepad, fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY_LEFT_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " LEFT"
        if i != lastimg[x] or i == 0:
            draw.polygon([(5, 63), (23, 54), (23, 74)],
                         outline=color.gamepad, fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY_RIGHT_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " RIGHT"
        if i != lastimg[x] or i == 0:
            draw.polygon([(65, 63), (47, 54), (47, 74)],
                         outline=color.gamepad, fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY_DOWN_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " DOWN"
        if i != lastimg[x] or i == 0:
            draw.polygon([(35, 93), (45, 75), (25, 75)],
                         outline=color.gamepad, fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY1_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " Q"
        if i != lastimg[x] or i == 0:
            draw.ellipse((70, 33, 90, 53), outline=color.gamepad,
                         fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY2_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " E"
        if i != lastimg[x] or i == 0:
            draw.ellipse((100, 53, 120, 73),
                         outline=color.gamepad, fill=render_color)
        lastimg[x] = i
        x += 1
        ######
        render_color = color.background
        i = GPIO.input(PINS["KEY3_PIN"])
        if i == 0:
            render_color = color.gamepad_fill
            write = write + " R"
        if i != lastimg[x] or i == 0:
            draw.ellipse((70, 73, 90, 93), outline=color.gamepad,
                         fill=render_color)
        lastimg[x] = i

        if write != "":
            render_chars = ""
            for item in write[1:].split(" "):
                render_chars += "press(\"" + item + "\");"
            print(os.popen("P4wnP1_cli hid job -t 5 -c '" + render_chars + "'").read())
            time.sleep(0.25)
    m.which = m.which[:-1]
    time.sleep(0.25)

### Munifying dump with automated Logitacker pairing ###
def RunLogitechAttack(logitacker=False,render_lines=[]):
    print("(1/3) Dumping...")
    render_lines.append("Dumping!...")
    ShowLines(render_lines)
    minfo = os.popen(default.munifying_path + 'munifying info').read()
    print(minfo)
    if "No known" in minfo or len(minfo) < 120:
        render_lines.append("No dongle!...")
        ShowLines(render_lines)
        time.sleep(0.5)
        return False
    render_lines.append("Done..")
    ShowLines(render_lines)
    if logitacker and "LOGITacker" not in minfo:
        print("(2/3) Plantting backdoor!...")
        render_lines.append("Pairing...")
        ShowLines(render_lines)
        ser = serial.Serial('/dev/ttyACM0')
        ser.write(b'\ndiscover run\npair device run\n')
        print(os.popen(default.munifying_path + 'munifying pair').read())
        render_lines.append("Attempt 2...")
        ShowLines(render_lines)
        print("(3/3) Attempt #2? just to be sure")
        ser.write(b'\npair device run\ndiscover run\n')
        ser.close()
        minfo = os.popen(default.munifying_path + 'munifying info').read()
        print(minfo)
    else:
        print("(2/3) Skipping backdoor")
        render_lines.append("Skipping backdoor")
        ShowLines(render_lines)

    print("(3/3) Done!")
    render_lines.append("Finished!...")
    ShowLines(render_lines)
    f = open(default.install_path + "muni_log", "w")
    f.write(minfo)
    f.close()
    time.sleep(0.4)
    RenderInfo(minfo)
    return True

### Logitech attack but waits for dongle to be inserted ###
def DumpDongle():
    logitacker = False
    runnow = True #False
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='usb')
    monitor.filter_by(subsystem='tty')
    devices = context.list_devices()
    for device in devices:
        if device.get('ID_VENDOR_ID') in ['1915'] and not logitacker:
            logitacker = True
        #if device.get('ID_VENDOR_ID') in ['046d'] and not runnow:
        #    runnow = True        
        #print(device)
    render_lines = []
    if runnow:
        if RunLogitechAttack(logitacker,render_lines):
            return
    for action,device in monitor:
        vendor_id = device.get('ID_VENDOR_ID')
        if vendor_id in ['1915']:
            if action in ["bind","add"]:
                logitacker = True
                print("Logitacker present!")
                
            elif action == "remove":
                logitacker = False
                print("Logitacker disconnected! :(")

        if vendor_id in ['046d']:
            print('Detected {} for device with vendor ID {}'.format(action, vendor_id))
            if action == "bind":
                RunLogitechAttack(logitacker,render_lines)
                return
            elif action == "remove":
                print("Target disconnected!")

### Basic info screen ###
def ShowInfo():
    color.DrawMenuBackground()
    m.which = m.which + "1"
    last = []  # Used to get rid of the flicker
    while 1:
        # Get right interface (no hostname -I)
        r_ip=["wlan0","usbeth","bteth"]
        for i in range(len(r_ip)):
            try:
                r_ip[i] = str(netifaces.ifaddresses(r_ip[i])[2][0]["addr"])
            except:
                pass

        render_array = ["W: " + r_ip[0],
                        "USB: " + r_ip[1],
                        "B: " + r_ip[2],
                        os.popen(
            "free -m | awk 'NR==2{printf \"Memory: %.2f%%\", $3*100/$2 }'").read(),
            os.popen(
            "df -h | awk '$NF==\"/\"{printf \"Disk: %d/%dGB %s\", $3,$2,$5}'").read(),
            time.strftime("%H:%M:%S")
        ]
        if last != render_array:
            for i in range(len(render_array)):
                draw.rectangle([(default.start_text[0]-5, default.start_text[1] + default.text_gap * i),
                                (120, default.start_text[1] + default.text_gap * i + 10)], fill=color.background)
                draw.text((default.start_text[0], default.start_text[1] + default.text_gap * i),
                          render_array[i][:m.max_len], fill=color.text)
            last = render_array
        time.sleep(0.2)
        if GPIO.input(PINS["KEY2_PIN"]) == 0 or GPIO.input(PINS["KEY_LEFT_PIN"]) == 0:
            m.which = m.which[:-1]
            return

### lsusb but on screen ###
def ListUSB():
    m.which = m.which + "1"
    extension = ".js"
    arr = os.popen("lsusb | cut -d' ' -f6-").read().split("\n")[:-1]
    while 1:
        output = GetMenuString(arr)
        break
    m.which = m.which[:-1]

### Loading P4wnP1 templates ###
def Templates(a):
    m.which = m.which + "1"
    cmd = os.popen("P4wnP1_cli template list -" +
                   a[0].lower()).read().split("\n")[2:-2]
    while 1:
        output = GetMenuString(cmd)
        if output != "":
            if YNDialog():
                status = os.popen("P4wnP1_cli template deploy -" +
                                  a[0].lower() + "'''" + output + "'''").read()
                draw.rectangle([7, 35, 120, 95], fill="#ADADAD")
                draw.text((32 - len(a), 52), status.split(":")
                          [1].replace("\n", "") + "!", fill="#000000")
                time.sleep(2.5)
                break
        elif output == "":
            break
    m.which = m.which[:-1]

def Explorer(path="/",extensions=""):
    # ".gif\|.png\|.bmp\|.jpg\|.tiff\|.jpeg"
    while 1:
        arr = ["../"] + os.popen("ls --format=single-column -F " + path + (" | grep \"" + extensions + "\|/\"","")[extensions==""] ).read().replace("*","").split("\n")[:-1]
        output = GetMenuString(arr,False)
        if output != "":
            if output == "../":
                if path == "/":
                    break
                else:
                    path = (path,path[:-1])[path[-1] == "/"]
                    path = path[:path.rindex("/")]
                    if path == "":
                        path = "/"
                    else:
                        path = (path + "/",path)[path[-1] == "/"]
            elif output[-1] == "/":
                path = (path + "/",path)[path[-1] == "/"]
                path = path + output
                path = (path + "/",path)[path[-1] == "/"]
            else:
                if YNDialog("Open?","Yes","No",output[:10]):
                    return path + output
        else:
            break
    return ""

def ReadTextFile():
    while 1:
        rfile = Explorer("/root/",extensions=".txt\|.json\|.conf")
        if rfile == "":
            break
        with open(rfile) as f:
            content = f.read().splitlines()
        GetMenuString(content)

def ImageExplorer():
    m.which = m.which + "1"
    path = default.imgstart_path
    while 1:
        arr = ["../"] + os.popen("ls --format=single-column -F " + path + " | grep \".gif\|.png\|.bmp\|.jpg\|.tiff\|.jpeg\|/\"").read().replace("*","").split("\n")[:-1]
        output = GetMenuString(arr,False)
        if output != "":
            if output == "../":
                if path == "/":
                    break
                else:
                    path = (path,path[:-1])[path[-1] == "/"]
                    path = path[:path.rindex("/")]
                    if path == "":
                        path = "/"
                    else:
                        path = (path + "/",path)[path[-1] == "/"]
            elif output[-1] == "/":
                path = (path + "/",path)[path[-1] == "/"]
                path = path + output
                path = (path + "/",path)[path[-1] == "/"]
            else:
                if YNDialog("Open?","Yes","No",output[:10]):
                    x = Image.open(path + output)
                    x = x.resize((128,128))
                    image.paste(x)
                    time.sleep(1)
                    getButton()
                    # Redraw border since we are taking up whole screen
                    color.DrawBorder()
                    #break
        else:
            break
    m.which = m.which[:-1]

### Executing hid scripts ###
def HidAttack():
    m.which = m.which + "1"
    extension = ".js"
    arr = os.popen("ls --format=single-column -F " + default.hid_path + " | grep " +
             extension).read().replace(default.hid_path, "").replace("*","").replace(extension, "").split("\n")[:-1]
    while 1:
        output = GetMenuString(arr)
        if output != "":
            if YNDialog("Run attack?","Yes","No",output[:10]):
                bbjob = YNDialog("Background job?")
                #try:
                render_text="Done!"
                if bbjob:
                    render_text=(check_output("P4wnP1_cli hid job " + output + extension, stderr=STDOUT,shell=True, timeout=10)).decode('UTF-8')
                else:
                    os.system("P4wnP1_cli hid run " + output + extension + " &")
                print(render_text)
                Dialog(render_text)
                #except:
                #    Dialog("Failed!")
                break
        elif output == "":
            break
    m.which = m.which[:-1]

### Screen for selecting P4wnP1 typing speed ###
def SetTypeSpeedMenu():
    m.which = m.which + "1"
    color.DrawMenuBackground()
    time.sleep(0.4)
    render_offset = [default.updown_pos[0],default.updown_pos[2]]
    i=0
    desired_value=[100, 150]
    
    draw.text((12, 20), "  Typing delays", fill=color.text)
    draw.text((10, 106), "Default     Random", fill=color.text)
    
    while GPIO.input(PINS["KEY_PRESS_PIN"]):
        render_up = False
        render_down = False
        
        DrawUpDown(desired_value[0],render_offset[0],render_up,render_down,(color.text, color.selected_text)[i == 0])
        DrawUpDown(desired_value[1],render_offset[1],render_up,render_down,(color.text, color.selected_text)[i == 1])
        
        button = getButton()
        if button == "KEY_LEFT_PIN":
            i = i - 1
            time.sleep(0.1)
        elif button == "KEY_RIGHT_PIN":
            i = i + 1
            time.sleep(0.1)
        elif button == "KEY_UP_PIN":
            desired_value[i] = desired_value[i] + 10
            render_up = True
        elif button == "KEY_DOWN_PIN":
            desired_value[i] = desired_value[i] - 10
            render_down = True
        elif button == "KEY1_PIN":
            desired_value[i] = desired_value[i] + 1
            render_up = True
        elif button == "KEY3_PIN":
            desired_value[i] = desired_value[i] - 1
            render_down = True
        elif button == "KEY_PRESS_PIN":
            break

        if i > 1:
            i = 0
        elif i < 0:
            i = 1
        
        if desired_value[i] > 5000:
            desired_value[i] = 0
        elif desired_value[i] < 0:
            desired_value[i] = 5000
        
        DrawUpDown(desired_value[i],render_offset[i],render_up,render_down,color.selected_text)
        time.sleep(0.1)
    if YNDialog(a="Set type speed?", y="Yes", n="No",b=( "    " + str(desired_value[0]) + "," + str(desired_value[1])) ):
        print(os.popen("P4wnP1_cli hid run -t 5 -c 'typingSpeed(" + str(desired_value[0]) + "," + str(desired_value[1]) + ");'").read())
        Dialog("   Done!")
    m.which = m.which[:-1]

### Getting duckyscript from BadUSBs ###
def AnalyzeHIDLive():
    global threads
    m.which = m.which + "1"
    color.DrawMenuBackground()
    time.sleep(0.4)
    filename = time.strftime("%H_%M_%S-%Y%m%d")
    Dialog("Waiting for USB", False)    
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='usb')
    monitor.filter_by(subsystem='tty')
    devices = context.list_devices()
    
    for action,device in monitor:
        # You get stuck in this loop
        # https://stackoverflow.com/questions/52098616/terminate-a-usbdetector-thread-using-monitor-from-pyudev
        if action in ["bind","add"]:
            break

    Dialog("USB! Hooking...", False)
    time.sleep(0.2)
    print("Hooking...")
    while 1:
        try:
            keys.hook(default.hid_ducky_path + filename + ".txt", default.hid_log_path + filename + ".log")
            break
        except:
            pass

    print("Hooked!")
    Dialog("Waiting for keys!", False)
    while 1:
        if keys.keys_count > 0:
            Dialog("Keys: " + str(keys.keys_count),False)
        time.sleep(1)
        if GPIO.input(PINS["KEY_PRESS_PIN"]) == 0 or GPIO.input(PINS["KEY2_PIN"]) == 0:
            Dialog("Generating...", False)
            break

    arr = keys.stop_gethook()
    time.sleep(0.1)
    if len(arr) == 0:
        Dialog("Empty :(")
    else:
        GetMenuString(arr)
    
    m.which = m.which[:-1]

### Selecting keystroke log file and making it into duckyscript ###
def AnalyzeHIDFile():
    m.which = m.which + "1"
    color.DrawMenuBackground()
    time.sleep(0.4)
    
    extension = ".log"
    arr = os.popen("ls --format=single-column -F " + default.hid_log_path + " | grep " +
             extension).read().replace(default.hid_log_path, "").replace("*","").split("\n")[:-1]

    time.sleep(0.1)
    if len(arr) == 0:
        Dialog("Empty :(")
    else:
        x = GetMenuString(arr)
        if x != "":
            try:
                GetMenuString(keys.fromFile(default.hid_log_path + x , None))
            except:
                print(sys.exc_info()[0])
                Dialog("Error!")
    
    m.which = m.which[:-1]

def SimpleBuilder():
    #TODO
    m.which = m.which + "1"
    color.DrawMenuBackground()
    time.sleep(0.4)
    
    # Add
    # Run/Save
    # Remove
    # Left -> Escape?
    lines = []
    
    while True:
        out = GetMenuString(lines,True)
        if out[0] < 0:
            break
        
        #Show menu
        while True:
            options = [out[1], "Add Line", "Remove line", "Save script", "Run script"]
            which = GetMenuString(options)
            if which == options:
                continue
            
    
    m.which = m.which[:-1]

####### -------- #######

### Menu class ###
class DisposableMenu:
    which = "a" # What menu you start and you are on.
    select = 0 # Use case: menu[self.which][self.select] => menu["a"][0]
    char = "> " # Character used for indention
    max_len = 17 # Max character count on 1 line

    # Basic menu structure
    # Some functions have their own submenus.
    menu = {
        "a": (
            ["System info", ShowInfo],
            ["HID", "ab"],
            ["Logitech attacks", "ac"],
            ["USB tools", "ad"],
            ["Template selector", "aa"],
            ["Other features","ag"],
            ["Options", "ae"],
            ["System", "af"]
        ),
        "aa": (
            ["Full settings", [Templates, "FULL_SETTINGS"]],
            ["WiFi", [Templates, "WIFI"]],
            ["Bluetooth", [Templates, "BLUETOOTH"]],
            ["USB", [Templates, "USB"]],
            ["Trigger actions", [Templates, "TRIGGER_ACTIONS"]],
            ["Network", [Templates, "NETWORK"]]
        ),
        "ab": (
            ["Run script!", HidAttack],
            ["Analyze HID", "aba"],
            ["Ducky builder", SimpleBuilder],
            ["Gamepad", Gamepad],
            ["Typing speed", SetTypeSpeedMenu]
        ),
        "aba": (
            ["Live from USB", AnalyzeHIDLive],
            ["From file", AnalyzeHIDFile]
        ),
        "ac": (
            ["Dump dongle", RunLogitechAttack],
            ["Wait on dongle", DumpDongle]
        ),
        "ad": (
            ["List USB", ListUSB],
        ),
        "ae": (
            ["Colors", "aea"],
            ["Refresh config", LoadConfig],
            ["Save config!", SaveConfig]
        ),
        "aea": (
            ["Background", [SetColor, 0]],
            ["Text", [SetColor, 2]],
            ["Selected text", [SetColor, 3]],
            ["Selected background", [SetColor, 4]],
            ["Border", [SetColor, 1]],
            ["Gamepad border", [SetColor, 5]],
            ["Gamepad fill", [SetColor, 6]]
        ),
        "af":(
            ["Shutdown system", [Leave,True]],
            ["Restart UI", Restart],
            ["Exit", Leave]
        ),
        "ag":(
            ["Browse Images", ImageExplorer],
            ["Read small textfile", ReadTextFile]
        )
    }

    # Get only list of strings with names
    def GetMenuList(self):
        menulist = []
        for item in self.menu[self.which]:
            menulist.append(item[0])
        return menulist

    # Get selection index based on string
    def GetMenuIndex(self, inlist):
        x = GetMenuString(inlist)
        if x != "":
            for i in range(0, len(m.menu[m.which])):
                if m.menu[m.which][i][0] == x:
                    return i
                    break
        else:
            return -1

def main():
    # Draw background once
    color.DrawMenuBackground()
    color.DrawBorder()

    # Start Threads
    updateStats()
    refreshDisplay()

    print("Booted in %s seconds! :)" % (time.time() - start_time))
    
    # Menu handling
    # Running functions from menu structure
    while True:
        x = m.GetMenuIndex(m.GetMenuList())
        if x >= 0:
            m.select = x
            if isinstance(m.menu[m.which][m.select][1], str):
                m.which = m.menu[m.which][m.select][1]
            elif isinstance(m.menu[m.which][m.select][1], list):
                m.menu[m.which][m.select][1][0](
                    m.menu[m.which][m.select][1][1])
            else:
                m.menu[m.which][m.select][1]()
        elif len(m.which) > 1:
            m.which = m.which[:-1]


if upslite:
    ### Setup UPS Lite ###
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    #GPIO.setup(4, GPIO.IN)
    # Floating pin (Need to short contacts on UPS Lite)
    GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_OFF)

    bus = None
    try:
        bus = smbus.SMBus(1)
    except:
        upslite = False
    PowerOnReset(bus)
    QuickStart(bus)
    readCapacity(bus)
    readVoltage(bus)

### Default values + LCD init ###
default = Defaults()

LCD = LCD_1in44.LCD()
Lcd_ScanDir = LCD_1in44.SCAN_DIR_DFT  # SCAN_DIR_DFT = D2U_L2R
LCD.LCD_Init(Lcd_ScanDir)
LCD_Config.Driver_Delay_ms(5)  # 8
LCD.LCD_Clear()

image = Image.open(default.install_path + 'logo.bmp')
LCD.LCD_ShowImage(image, 0, 0)

image = Image.new("RGB", (LCD.width, LCD.height), "WHITE")
draw = ImageDraw.Draw(image)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 8)

### Defining PINS, threads, loading JSON ###
PINS = {
    "KEY_UP_PIN": 6,
    "KEY_DOWN_PIN": 19,
    "KEY_LEFT_PIN": 5,
    "KEY_RIGHT_PIN": 26,
    "KEY_PRESS_PIN": 13,
    "KEY1_PIN": 21,
    "KEY2_PIN": 20,
    "KEY3_PIN": 16
}
threads = [threading.Timer(5, updateStats), threading.Timer(0.011, refreshDisplay)]
LoadConfig()
m = DisposableMenu()

### Info ###
print("I'm running on " + str(temp()).split('.')[0] + " °C.")
print(time.strftime("%H:%M:%S"))

# Delay for logo
time.sleep(2)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        Leave()

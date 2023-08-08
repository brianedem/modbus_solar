import time
import enum
import json
import sys
from pyModbusTCP.client import ModbusClient
from pyModbusTCP import utils

sunSpecModelPath = "../models"
c = ModbusClient(host='192.168.1.67', port=1502)
if 0 :
    dump_size = 16
    previous = ''
    for i in range (0,65536,dump_size) :
        marker = ''
        result = c.read_holding_registers(i, dump_size) #max 125
        if result is None :
            continue
        print("%x:" % (i), end='')
        for value in result :
            print(" %04x" % (value), end='')
            if (value & 0x8080)==0 :
                string2 = bytes(b for b in [value>>8, value&0xFF]).decode()
                if previous=='Su' and string2=='nS' :
                    marker = " SunS at %d" % (i)
            else :
                string2 = ''
            previous = string2

        print(marker)
        time.sleep(1)

    sys.exit()

class device :          # loaded from model_1
    Mn = ""
    sections = []

class section :         # loaded from model 101, 203, etc
    name = ""

class point :           # attributes organized as points
    desc = ""
    label = ""

def e_text(value):
    result = ""
    for i in value :
        for b in [i>>8,i&0xFF] :
            if b == 0 :
                continue
            result += chr(b)
    return result
    return bytes(b for i in value for b in [i>>8,i&0xFF]).decode(encoding='ascii')

    # models
models = {}             #
devices = []

    # report on section contents
#for reg_addr in [0,40000] :
for reg_addr in [40000] :
        # read the SunS marker
    m_data = c.read_holding_registers(reg_addr, 2)
    print (e_text(m_data))
    reg_addr += 2
        # walk through the headers
    hcount = 0
    while True :
            # read the Sunspec header
        m_data = c.read_holding_registers(reg_addr, 2)
            # check for end
        if m_data[0] == 0xFFFF :
            print("end found at %x" % reg_addr)
            break

            # report what was found
        m_type = m_data[0]
        m_length = m_data[1]
        print ("%d: header %d, %d words" % (reg_addr, m_type, m_length))

            # process section
        if m_type not in models :
            f = open(sunSpecModelPath+"/json/model_%s.json"%(m_type))
# FIXME check for error on open
            models[m_type] = json.load(f)
# FIXME check for error parsing file
        length = m_length
        reg_addr += 2
        while True :
            if length > 125 :
                m_data += c.read_holding_registers(reg_addr, 125)
                length -= 125
                reg_addr += 125
            else :
                m_data += c.read_holding_registers(reg_addr, length)
                reg_addr += length
                length = 0
                break
        print("module length = %d/%d" % (m_length, len(m_data)))
        print(models[m_type]['group']['label'])
        g = models[m_type]["group"]
#       if m_type == 1 :
#       if True :
        if m_type < 700 or m_type == 713 :
            # print (g)
            for p in g["points"] :
                valid = True
                f_size = p["size"]
                f_type = p["type"]
                f_name = p["name"]
                if f_type == "pad" :
                    continue
                if "label" in p :
                    f_label = p["label"]
                else :
                    f_label = None
#               print(m_data[:4], f_type)
                if f_type == "string" :
                    m_value = e_text(m_data[:f_size])
                    if m_value == '' :
                        m_value = None

                elif f_type == "sunssf" :   # scale factor
                    m_value = m_data[0]
                    if m_value & 0x1000 :
                        m_value = -((m_value ^ 0xFFFF) + 1)

                elif f_type == "uint16" :
                    m_value = m_data[0]
                    if m_value == 0xFFFF :
                        m_value = None
                elif f_type == "uint32" :
                    m_value = (m_data[0]<<16) + m_data[1]
                    if m_value == 0xFFFFFFFF :
                        m_value = None
                elif f_type == "uint64" :
                    m_value = (m_data[0]<<48) + (m_data[1]<<32) + (m_data[2]<<16) + m_data[3]
                    if m_value == 0xFFFFFFFFFFFFFFFF :
                        m_value = None

                elif f_type == "int16" :
                    m_value = m_data[0]
                    if m_value == 0x8000 :
                        m_value = None
                    elif m_value & 0x8000 :
                        m_value = -((m_value ^ 0xFFFF) + 1)
                elif f_type == "int32" :
                    m_value = (m_data[0]<<16) + m_data[1]
                    if m_value == 0x80000000 :
                        value = False
                    elif m_value & 0x80000000 :
                        m_value = -((m_value ^ 0xFFFFFFFF) + 1)

                elif f_type == "acc32" :    # 32-bit unsigned
                    m_value = (m_data[0]<<16) + m_data[1]
                elif f_type == 'enum16' :
                    m_value = m_data[0]
                    if m_value == 0xFFFF :
                        m_value = None
                elif f_type == "bitfield16" :
                    m_value = m_data[0]
                    if m_value == 0xFFFF :
                        m_value = None
                elif f_type == "bitfield32" :
                    m_value = (m_data[0]<<16) + m_data[1]
                    if m_value == 0xFFFFFFFF :
                        m_value = None

                else :
                    print("unexpected type", f_type)

                if m_value!=None :
                    print(f' {f_name:16} {m_value:>18} {f_label}')
                elif 1:
                    print(f' {f_name:16}   Unsupported      {f_label}')
                m_data = m_data[f_size:]
                    
            d = '''device()
            d.name = e_text(m_data[
            d.
            print (d.name)
            sys.exit()

        else :
            s = section()
            s.name = g["name"]
            for p in g["points"] :
                print (p)
                sys.exit()

            devices += device()
'''
#       sys.exit()

        hcount += 1
        if hcount>20 :
            print ("Too many headers")
            break

sys.exit()

for i in range(3):
#   if not client.is_socket_open():
#       client.connect()
#       time.sleep(0.1)
#       print ("not open")
#       continue

    result = client.read_holding_registers(40000, count=2, unit=1).registers
#   result = ()
    for value in result:
        print(hex(value))

    print (result, ReadHoldingRegistersResponse)
#   if not isinstance(result, ReadHoldingRegistersResponse):
#       print ("no response")
#       continue
#   if len(result.registers) != 2:
#       print ("insufficent registers")
#       continue
#   print (BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big, wordorder=Endian.Big))
    print (BinaryPayloadDecoder.fromRegisters(result, byteorder=Endian.Big, wordorder=Endian.Big))
    break

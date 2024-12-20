'''
Reading a device register will require four steps:
- Connect to the modbus server
    Establishes a modTCP connection to the server
    Read model headers from server
    Read contents of the common headers
    Load referenced SunSpec models
    Add relative register offsets and associate scale factors to the models
    Add list of dependent devices to the common header data structures
- Locate register(s)
    Use text parameters to locate a specific register
    Returns a class object that provides methods to extract register data from device
    Registers device model with server
- Read registers
    Class method of object returned when connecting to server
    Reads all registered models that are being used
- Get value
    Class method of object returned when locating the register
        value, label, name, units

'''
import logging
import os
import sys
import json
from time import time
from pyModbusTCP.client import ModbusClient

log = logging.getLogger(__name__)

# locate the SunSpec JSON model files
cwd = os.path.dirname(__file__)
sunSpecModelPath = os.path.join(cwd,"models",'json')

    # text is packed two characters per 16-bit modbus register
def e_text(value):
    result = ""
    for i in value :
        for b in [i>>8,i&0xFF] :
            if b == 0 :
                continue
            result += chr(b)
    return result
    return bytes(b for i in value for b in [i>>8,i&0xFF]).decode(encoding='ascii')

    # structure to hold information about each header encountered while parsing device modbus data
class header :
    def __init__(self, ID, offset, length, Md=None) :
        self.ID = ID
        self.offset = offset
        self.length = length
        self.Md = None
        self.Opt = None
        self.reference_count = 0
        self.members = []
        self.values = []

    # methods for accessing SolarEdge devices
verbose = False
class sEdge :
    models = {}
    
        # connect to inverter, discover models used, and map out register locations
    def __init__(self, host, port):
            # establish connection
        try:
            self.inverter = ModbusClient(host=host, port=port)
        except ValueError:
            log.exception(f'Unable to connect to modbus client {host}:{port}')
            raise RuntimeError('Unable to connect to modbus client') from None

            # register groups are identified by a "model identifier" from which specific registers can be located
            # The default start of the register groups is 40000, with the first two registers (16-bit) containing "SunS"
        reg_addr = 40000

            # verify the SunS identifier
        m_data = self.inverter.read_holding_registers(reg_addr, 2)
        if m_data==None :
            log.exception (f"Unable to read inverter holding register at offset {reg_addr}")
            raise RuntimeError('Unable to read inverter holding register') from None
        if e_text(m_data) != "SunS" :
            log.exception (f"Unable to locate SunS marker at register offset {reg_addr}")
            raise RuntimeError('Unable to locate SunS marker') from None
        reg_addr += 2

            # walk through the headers and add to the headers list

        self.headers = []
        current_common_header = None
        while True :

                # read the model ID
            m_data = self.inverter.read_holding_registers(reg_addr, 2)
            if m_data==None :
                log.exception (f"Unable to read model ID at register offset {reg_addr}")
                raise RuntimeError('Unable to read model ID') from None

                # check for end
            if m_data[0] == 0xFFFF :
                break

            m_type = m_data[0]
            m_length = m_data[1]

                # load model if needed
            if m_type not in sEdge.models :
                f = open(os.path.join(sunSpecModelPath,f'model_{m_type}.json'))
                sEdge.models[m_type] = json.load(f)

                    # build index and add relative offset information to model
                point_index = {}
                offset = 0
                for p in sEdge.models[m_type]['group']['points'] :
                    point_index[p['name']] = p
                    p['offset'] = offset
                        # create symbol table from symbols information, if present
                    if 'symbols' in p :
                        symbol_table = {}
                        for s in p['symbols'] :
                            symbol_table[s['value']] = s['name']
                        p['symbol_table'] = symbol_table
                    offset += p['size']
                sEdge.models[m_type]['group']['point_index'] = point_index

            self.headers.append(header(m_type, reg_addr, m_length+2))

                # pick up device name and Option strings from the common header and add to header entry
            if m_type == 1 :
                current_common_header = self.headers[-1]
                m_data = self.inverter.read_holding_registers(reg_addr, m_length+2)
                if m_data==None :
                    log.exception (f"Unable to read common header info at register offset {reg_addr}")
                    raise RuntimeError('Unable to read common header info') from None
                current_common_header.values = m_data
                for p in sEdge.models[1]['group']['points'] :
                    size = p['size']
                    if p['name'] == "Md" :
                        point_name = m_data[:size]
                        point_name = e_text(point_name)
                        self.headers[-1].Md = point_name
                    if p['name'] == "Opt" :
                        point_option = m_data[:size]
                        point_option = e_text(point_option)
                        self.headers[-1].Opt = point_option
                    m_data = m_data[size:]

            else :
                if current_common_header is None :
                    log.exception("Expected a common header before first model")
                    raise RuntimeError('Expected a common header before first model') from None
                current_common_header.members.append(sEdge.models[m_type]['group']['name'])
            reg_addr += m_length + 2


        # locate register using text description - used by point class creation
    def locate_point(self, device_name, model_name, point_name):
        common_header = None
        member_header = None
        for h in self.headers :
                # first find a common header that matches device_name
            if common_header==None :
                if h.ID==1 and h.Md.startswith(device_name) :
                    common_header = h
                elif h.ID==1 and h.Opt.startswith(device_name) :
                    common_header = h
                # then find a model member that matches the model name
            else :
                if sEdge.models[h.ID]['group']['name'].startswith(model_name)  :
                    member_header = h
                    break
                elif common_header!=None and h.ID==1 :
                    break
        
            # was a matching common header found?
        if common_header==None :
            log.error(f"Unable to locate device {device_name}")
            if verbose:
                log.error(f' available device names are:')
                for h in self.headers :
                    if h.ID==1:
                        log.error(f' {h.Md}')
            return None

            # was there a member model with a matching name?
        if member_header==None :
            log.error(f"Unable to locate model member '{model_name}' in {common_header.Md}")
            if verbose:
                log.error(f' available members are:')
                for m in common_header.members:
                    log.error(f'  {m}')
            return None

            # find the matching point within the points
        point_names = list(sEdge.models[member_header.ID]['group']['point_index'].keys())
        if point_name not in point_names :
            log.error(f"Unable to locate point named {point_name} in {model_name}")
            if verbose:
                log.error(f' available parameters are:')
                for pn in point_names:
                    log.error(f'  {pn}')
            return None

        log.debug("Found {point_name}")
        member_header.reference_count += 1

        return (member_header)

        # (re)read all referenced devices to local "cache"
    def refresh_readings(self):
        for h in self.headers :
            if h.reference_count > 0 :
                h.values = self.inverter.read_holding_registers(h.offset, h.length)

        # extract register value from cache and format - used by point.read_point()
    def extract_value(self, header, point_name) :
        if header.values==None :
            log.error (f"No register data to extract {point_name} from")
            return None
        p = sEdge.models[header.ID]['group']['point_index'][point_name]
        p_type = p['type']
        if 'units' in p :
            p_units = p['units']
        else :
            p_units = None
        if 'sf' in p :
            sf_name = p['sf']
            sf_point = sEdge.models[header.ID]['group']['point_index'][sf_name]
            sf_offset = sf_point['offset']
            sf_data = header.values[sf_offset]
            log.debug(f"Scale factor: {sf_data}")
            if sf_data == 32768 :
                p_sf = 0
            elif sf_data & 0x8000 :
                p_sf = sf_data - 65536
            else :
                p_sf = sf_data
            p_sf = 10**p_sf
            log.debug("Scale factor: {p_sf}")
        else :
            p_sf = None
        p_data = header.values[p['offset']:][:p['size']]

        log.debug(f'{p_data=}, {p_type=}')
        if   p_type == 'int16':
            if p_data[0] == 0x8000 :
                value = None
            elif p_data[0] & 0x8000 :
                value = (p_data[0]-65536) * p_sf
            else :
                value = p_data[0] * p_sf
        elif p_type == 'uint16':
            if p_data[0] == 0xFFFF :
                value = None
            else :
                value = p_data[0] * p_sf
        elif p_type == 'acc16':
            if p_data[0] == 0x0000 :
                value = None
            else :
                value = p_data[0] * p_sf
        elif p_type == 'enum16' :
            if p_data[0] == 0xFFFF:
                value = None
            elif 'symbol_table' in p :
                value = p['symbol_table'][p_data[0]]
            else :
                value = p_data[0]

        elif p_type == 'int32' :
            value = p_data[0]<<16 | p_data[1]
            if value == 0x80000000:
                value = None
            else:
                value = (value-0xFFFFFFFF) * p_sf
        elif p_type == 'uint32' :
            value = p_data[0]<<16 | p_data[1]
            if value == 0xFFFFFFFF:
                value = None
            else:
                value = value * p_sf
        elif p_type == 'acc32' :
            value = p_data[0]<<16 | p_data[1]
            if value == 0x00000000:
                value = None
            else:
                value = value * p_sf
        elif p_type == 'bitfield32' :
            log.debug(f'{p_data=}')
            value = p_data[0]<<16 | p_data[1]
            if value==0xFFFFFFFF :
                value = None
            elif 'symbol_table' in p :
                bit_values = {}
                for s in p['symbol_table'] :
                    bit = (value>>s) & 0x1
                    bit_values[p['symbol_table'][s]] = (bit==1)
                value = bit_values
            else :
                value = p_data[0]<<16 | p_data[1]
            pass


        elif p_type == 'string' :
            value = e_text(p_data)
        else :
            log.error(f"Unknown point type {p_type}")
            return None

        return (value, p_units)

    # methods for reading registers
class point:
    
    def __init__(self, server, device_name, model_name, point_name) :
        self.server = server
        self.point_name = point_name
        self.header = server.locate_point(device_name, model_name, point_name)
        if self.header is None:
            raise RuntimeError('Unable to locate data point') from None
        
    def read_point(self, refresh=False) :
        value = self.server.extract_value(self.header, self.point_name)
        return value

epilog = """
<system> is the Manufacturer (Mn) or Model (Md) of the associated common header
<subsystem> is either the header number or name of the device subsystem
<registers> is register name within the subsystem

Abbreviated text values will match the first occurance
"""
if __name__ == '__main__' :
    import argparse
    verbose = 1

    logging.basicConfig(level=logging.INFO)

    default_ip = '192.168.12.186'
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog)
    parser.add_argument("registers", help="<system>.<subsystem>.<reg_name>",
        nargs='*')
    parser.add_argument("--ip_address", help="IP address of the inverter",
        default=default_ip)
    parser.add_argument("--list", help="list all available registers in system",
        action="store_true")

    args = parser.parse_args()
    print(args.ip_address)

#   system = sEdge('solaredgeinv.local', 1502)
#   system = sEdge('192.168.1.67', 1502)
    try:
        system = sEdge(args.ip_address, 1502)
    except RuntimeError:
        sys.exit()

    if args.list:
        for h in system.headers :
            if h.ID==1 :
                print(h.ID, h.Md, h.Opt)
            else :
                print(f"{h.ID:5} {sEdge.models[h.ID]['group']['name']:20} | {sEdge.models[h.ID]['group']['label']}")
    else:
        points = {}
        if args.registers:
            for register in args.registers:
                (device, module, reg) = register.split('.', maxsplit=3)
                try:
                    p = point(system, device, module, reg)
                except RuntimeError:
                    print(f'Unknown point {register}')
                else:
                    points[register] = p
            system.refresh_readings()

            for p in points:
                (value, units) = points[p].read_point()
                if units:
                    print(f'{p} {value} {units}')
                else:
                    print(f'{p} {value}')
        else:
            pass    # TODO add code to dump all?

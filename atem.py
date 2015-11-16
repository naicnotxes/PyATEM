#!/usr/bin/env python2.7 
# -*- coding: utf-8 -*-
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import socket
import struct


def dumpHex (buffer):
    s = ''
    for c in buffer:
        s += hex(c) + ' '
    print(s)


def dumpAscii (buffer):
    s = ''
    for c in buffer:
        if (ord(c)>=0x20)and(ord(c)<=0x7F):
            s+=c
        else:
            s+='.'
    print(s)


# Handles changes in attributes of the Atem class
class AttrProxy(object):
    __slots__ = ["_obj", "__weakref__"]
    def __init__(self, obj, atem, name):
        self.atem = atem
        self.name = name
        object.__setattr__(self, "_obj", obj)

    #
    # proxying (special cases)
    #
    def __getattribute__(self, name):
        return getattr(object.__getattribute__(self, "_obj"), name)
    def __delattr__(self, name):
        delattr(object.__getattribute__(self, "_obj"), name)
    def __setattr__(self, name, value):
        # settings happens here
        print("'" + name + "' has been changed.")
        setattr(object.__getattribute__(self, "_obj"), name, value)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_obj"))
    def __str__(self):
        return str(object.__getattribute__(self, "_obj"))
    def __repr__(self):
        return repr(object.__getattribute__(self, "_obj"))

    #
    # factories
    #
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        def make_method(name):
            def method(self, *args, **kw):
                return getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw)
            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins


# implements communication with atem switcher
class Atem:

    # size of header data
    SIZE_OF_HEADER = 0x0c

    # packet types
    CMD_NOCOMMAND   = 0x00
    CMD_ACKREQUEST  = 0x01
    CMD_HELLOPACKET = 0x02
    CMD_RESEND      = 0x04
    CMD_UNDEFINED   = 0x08
    CMD_ACK         = 0x10

    # labels
    LABELS_VIDEOMODES = ['525i59.94NTSC', '625i50PAL', '525i59.94NTSC16:9', '625i50PAL16:9',
                         '720p50', '720p59.94', '1080i50', '1080i59.94',
                         '1080p23.98', '1080p24', '1080p25', '1080p29.97', '1080p50', '1080p59.94',
                         '2160p23.98', '2160p24', '2160p25', '2160p29.97']
    LABELS_PORTS_EXTERNAL = {0:'SDI', 1:'HDMI', 2:'Component', 3:'Composite', 4:'SVideo'}
    LABELS_PORTS_INTERNAL = {0:'External', 1:'Black', 2:'Color Bars', 3:'Color Generator', 4:'Media Player Fill',
                             5:'Media Player Key', 6:'SuperSource', 128:'ME Output', 129:'Auxilary', 130:'Mask'}
    LABELS_MULTIVIEWER_LAYOUT = ['top', 'bottom', 'left', 'right']
    LABELS_AUDIO_PLUG = ['Internal', 'SDI', 'HDMI', 'Component', 'Composite', 'SVideo', 'XLR', 'AES/EBU', 'RCA']
    LABELS_VIDEOSRC = { 0: 'Black', 1: 'Input 1', 2: 'Input 2', 3: 'Input 3', 4: 'Input 4', 5: 'Input 5', 6: 'Input 6', 7: 'Input 7', 8: 'Input 8', 9: 'Input 9', 10: 'Input 10', 11: 'Input 11', 12: 'Input 12', 13: 'Input 13', 14: 'Input 14', 15: 'Input 15', 16: 'Input 16', 17: 'Input 17', 18: 'Input 18', 19: 'Input 19', 20: 'Input 20', 1000: 'Color Bars', 2001: 'Color 1', 2002: 'Color 2', 3010: 'Media Player 1', 3011: 'Media Player 1 Key', 3020: 'Media Player 2', 3021: 'Media Player 2 Key', 4010: 'Key 1 Mask', 4020: 'Key 2 Mask', 4030: 'Key 3 Mask', 4040: 'Key 4 Mask', 5010: 'DSK 1 Mask', 5020: 'DSK 2 Mask', 6000: 'Super Source', 7001: 'Clean Feed 1', 7002: 'Clean Feed 2', 8001: 'Auxilary 1', 8002: 'Auxilary 2', 8003: 'Auxilary 3', 8004: 'Auxilary 4', 8005: 'Auxilary 5', 8006: 'Auxilary 6', 10010: 'ME 1 Prog', 10011: 'ME 1 Prev', 10020: 'ME 2 Prog', 10021: 'ME 2 Prev' }
    LABELS_AUDIOSRC = { 1: 'Input 1', 2: 'Input 2', 3: 'Input 3', 4: 'Input 4', 5: 'Input 5', 6: 'Input 6', 7: 'Input 7', 8: 'Input 8', 9: 'Input 9', 10: 'Input 10', 11: 'Input 11', 12: 'Input 12', 13: 'Input 13', 14: 'Input 14', 15: 'Input 15', 16: 'Input 16', 17: 'Input 17', 18: 'Input 18', 19: 'Input 19', 20: 'Input 20', 1001: 'XLR', 1101: 'AES/EBU', 1201: 'RCA', 2001: 'MP1', 2002: 'MP2' }
    # cc
    LABELS_CC_DOMAIN = {0:'lens', 1:'camera', 8:'chip'}
    LABELS_CC_LENS_FEATURE = {0:'focus', 1:'auto_focused', 3:'iris', 9:'zoom'}
    LABELS_CC_CAM_FEATURE = {1:'gain', 2:'white_balance', 5:'shutter'}
    LABELS_CC_CHIP_FEATURE = {0:'lift', 1:'gamma', 2:'gain', 3:'aperture', 4:'contrast', 5:'luminance', 6:'hue-saturation'}

    # value options
    VALUES_CC_GAIN = {512: '0db', 1024: '6db', 2048: '12db', 4096: '18db'}
    VALUES_CC_WB = {3200: '3200K', 4500: '4500K', 5000: '5000K', 5600: '5600K', 6500: '6500K', 7500: '7500K'}
    VALUES_CC_SHUTTER = {20000: '1/50', 16667: '1/60', 13333: '1/75', 11111: '1/90', 10000: '1/100', 8333: '1/120', 6667: '1/150', 5556: '1/180', 4000: '1/250', 2778: '1/360', 2000: '1/500', 1379: '1/725', 1000: '1/1000', 690: '1/1450', 500: '1/2000'}
    VALUES_AUDIO_MIX = { 0: 'off', 1: 'on', 2: 'AFV' }

    system_config = { 'inputs': {}, 'audio': {} }
    status = {}
    config = { 'multiviewers': {}, 'mediapool': {} }
    state = {
        'program': {},
        'preview': {},
        'keyers': {},
        'dskeyers': {},
        'aux': {},
        'mediaplayer': {},
        'mediapool': {},
        'audio': {},
        'tally_by_index': {},
        'tally': {}
    }
    cameracontrol = {}

    # initializes the class
    def __init__(self, address):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setblocking(0)
        self.socket.bind(('0.0.0.0', 9910))

        self.address = (address, 9910)
        self.packetCounter = 0
        self.isInitialized = False
        self.currentUid = 0x1337

    # hello packet
    def connectToSwitcher(self):
        datagram = self.createCommandHeader(self.CMD_HELLOPACKET, 8, self.currentUid, 0x0)
        datagram += struct.pack('!I', 0x01000000)
        datagram += struct.pack('!I', 0x00)
        self.sendDatagram(datagram)

    # reads packets sent by the switcher
    def handleSocketData (self) :
        # network is 100Mbit/s max, MTU is thus at most 1500
        try :
            d = self.socket.recvfrom(2048)
        except socket.error:
            return False
        datagram, server = d
        print('received datagram')
        header = self.parseCommandHeader(datagram)
        if header :
            self.currentUid = header['uid']
            
            if header['bitmask'] & self.CMD_HELLOPACKET :
                print('not initialized, received HELLOPACKET, sending ACK packet')
                self.isInitialized = False
                ackDatagram = self.createCommandHeader (self.CMD_ACK, 0, header['uid'], 0x0)
                self.sendDatagram (ackDatagram)
            elif self.isInitialized and (header['bitmask'] & self.CMD_ACKREQUEST) :
                print('initialized, received ACKREQUEST, sending ACK packet')
                ackDatagram = self.createCommandHeader (self.CMD_ACK, 0, header['uid'], header['packageId'])
                self.sendDatagram (ackDatagram)
            
            if len(datagram) > self.SIZE_OF_HEADER + 2 and not (header['bitmask'] & self.CMD_HELLOPACKET) :
                self.parsePayload (datagram)

        return True        

    def waitForPacket(self):
        print(">>> waiting for packet")
        while not self.handleSocketData():
            pass
        print(">>> packet obtained")

    # generates packet header data
    def createCommandHeader (self, bitmask, payloadSize, uid, ackId) :
        buffer = b''
        packageId = 0

        if not (bitmask & (self.CMD_HELLOPACKET | self.CMD_ACK)) :
            self.packetCounter+=1
            packageId = self.packetCounter
    
        val = bitmask << 11
        val |= (payloadSize + self.SIZE_OF_HEADER)
        buffer += struct.pack('!H',val)
        buffer += struct.pack('!H',uid)
        buffer += struct.pack('!H',ackId)
        buffer += struct.pack('!I',0)
        buffer += struct.pack('!H',packageId)
        return buffer

    # parses the packet header
    def parseCommandHeader (self, datagram) :
        header = {}

        if len(datagram)>=self.SIZE_OF_HEADER :
            header['bitmask'] = struct.unpack('B',datagram[0:1])[0] >> 3
            header['size'] = struct.unpack('!H',datagram[0:2])[0] & 0x07FF
            header['uid'] = struct.unpack('!H',datagram[2:4])[0]
            header['ackId'] = struct.unpack('!H',datagram[4:6])[0]
            header['packageId']=struct.unpack('!H',datagram[10:12])[0]
            print(header)
            return header
        return False

    def parsePayload (self, datagram) :
        print('parsing payload')
        # eat up header
        datagram = datagram[self.SIZE_OF_HEADER:]
        # handle data
        while len(datagram) > 0 :
            size = struct.unpack('!H',datagram[0:2])[0]
            packet = datagram[0:size]
            datagram = datagram[size:]

            # skip size and 2 unknown bytes
            packet = packet[4:]
            ptype = packet[:4]
            payload = packet[4:]

            # find the approporiate function in the class
            method = 'recv'+ptype
            if method in dir(self) :
                func = getattr(self, method)
                if callable(func) :
                    print('> calling '+method)
                    func(payload)
                else:
                    print('problem, member '+method+' not callable')
            else :
                print('unknown type '+ptype)
                #dumpAscii(payload)

        #sys.exit()

    def sendCommand (self, command, payload) :
        print('sending command')
        size = len(command) + len(payload) + 4
        dg = self.createCommandHeader(self.CMD_ACKREQUEST, size, self.currentUid, 0)
        dg += struct.pack('!H', size)
        dg += "\x00\x00"
        dg += command
        dg += payload
        self.sendDatagram(dg)

    # sends a datagram to the switcher
    def sendDatagram (self, datagram) :
        print('sending packet')
        dumpHex(datagram)
        self.socket.sendto (datagram, self.address)

    def parseBitmask(self, num, labels):
        states = {}
        for i, label in enumerate(labels):
            states[label] = bool(num & (1 << len(labels) - i - 1))
        return states


    # handling of subpackets
    # ----------------------

    def recv_ver(self, data):
        major, minor = struct.unpack('!HH', data[0:4])
        self.system_config['version'] = str(major)+'.'+str(minor)

    def recv_pin (self, data):
        self.system_config['name'] = data

    def recvWarn(self, text):
        print('Warning: '+text)

    def recv_top(self, data):
        self.system_config['topology'] = {}
        datalabels = ['mes', 'sources', 'color_generators', 'aux_busses', 'dsks', 'stingers', 'dves',
                      'supersources']
        for i, label in enumerate(datalabels):
            self.system_config['topology'][label] = data[i]

        self.system_config['topology']['hasSD'] = (data[9] > 0)

    def recv_MeC(self, data):
        index = data[0]
        self.system_config.setdefault('keyers', [])[index] = data[1]

    def recv_mpl(self, data):
        self.system_config['media_players'] = {}
        self.system_config['media_players']['still'] = data[0]
        self.system_config['media_players']['clip'] = data[1]

    def recv_MvC(self, data):
        self.system_config['multiviewers'] = data[0]

    def recv_SSC(self, data):
        self.system_config['super_source_boxes'] = data[0]

    def recv_TlC(self, data):
        self.system_config['tally_channels'] = data[4]

    def recv_AMC(self, data):
        self.system_config['audio_channels'] = data[0]
        self.system_config['has_monitor'] = (data[1] > 0)

    def recv_VMC(self, data):
        size = 18
        for i in range(size):
            self.system_config['video_modes'][i] = bool(data[0] & (1 << size - i - 1))

    def recv_MAC(self, data):
        self.system_config['macro_banks'] = data[0]

    def recvPowr(self, data):
        self.status['power'] = self.parseBitmask(data[0], ['main', 'backup'])

    def recvDcOt(self, data):
        self.config['down_converter'] = data[0]

    def recvVidM(self, data):
        self.config['video_mode'] = data[0]

    def recvInPr(self, data):
        index = struct.unpack('!H', data[0:2])[0]
        self.system_config['inputs'][index] = {}
        with self.system_config['inputs'][index] as input_setting:
            input_setting['name_long'] = data[2:22].decode("utf-8")
            input_setting['name_short'] = data[22:26].decode("utf-8")
            input_setting['types_available'] = self.parseBitmask(data[27], self.LABELS_PORTS_EXTERNAL)
            input_setting['port_type_external'] = data[29]
            input_setting['port_type_internal'] = data[30]
            input_setting['availability'] = self.parseBitmask(data[32], ['Auxilary', 'Multiviewer', 'SuperSourceArt',
                                                                 'SuperSourceBox', 'KeySource'])
            input_setting['me_availability'] = self.parseBitmask(data[33], ['ME1', 'ME2'])

    def recvMvPr(self, data):
        index = data[0]
        self.config['multiviewers'].setdefault(index, {})['layout'] = data[1]

    def recvMvIn(self, data):
        index = data[0]
        window = data[1]
        self.config['multiviewers'].setdefault(index, {}).setdefault('windows', {})[window] = struct.unpack('!H', data[2:4])[0]

    def recvPrgI(self, data):
        meIndex = data[0]
        self.state['program'][meIndex] = struct.unpack('!H', data[2:4])[0]

    def recvPrvI(self, data):
        meIndex = data[0]
        self.state['preview'][meIndex] = struct.unpack('!H', data[2:4])[0]

    def recvKeOn(self, data):
        meIndex = data[0]
        keyer = data[1]
        self.state['keyers'].setdefault(meIndex, {})[keyer] = (data[2] != 0)

    def recvDskB(self, data):
        keyer = data[0]
        with self.state['dskeyers'].setdefault(keyer, {}) as keyer_setting:
            keyer_setting['fill'] = struct.unpack('!H', data[2:4])[0]
            keyer_setting['key'] = struct.unpack('!H', data[4:6])[0]

    def recvDskS(self, data):
        keyer = data[0]
        with self.state['dskeyers'].setdefault(keyer, {}) as dsk_setting:
            dsk_setting['onAir'] = (data[1] != 0)
            dsk_setting['inTransition'] = (data[2] != 0)
            dsk_setting['autoTransitioning'] = (data[3] != 0)
            dsk_setting['framesRemaining'] = data[4]

    def recvAuxS(self, data):
        auxIndex = data[0]
        self.state[auxIndex] = struct.unpack('!H', data[2:4])[0]

    def recvCCdo(self, data):
        input_num = data[1]
        domain = data[2]
        feature = data[3]
        feature_label = feature
        try:
            if domain == 0:
                feature_label = self.LABELS_CC_LENS_FEATURE[feature]
            elif domain == 1:
                feature_label = self.LABELS_CC_CAM_FEATURE[feature]
            elif domain == 8:
                feature_label = self.LABELS_CC_CHIP_FEATURE[feature]
            self.cameracontrol.setdefault(input_num, {}).setdefault('features', {}).setdefault(self.LABELS_CC_DOMAIN[domain], {})[feature_label] = bool(data[4])
        except KeyError:
            print("Warning: CC Feature not recognized (no label)")

    def recvCCdP(self, data):
        input_num = data[1]
        domain = data[2]
        feature = data[3]
        feature_label = feature
        val = None
        val_translated = None
        if domain == 0: #lens
            if feature == 0: #focus
                val = val_translated = struct.unpack('!h', data[16:18])[0]
            elif feature == 1: #auto focused
                pass
            elif feature == 3: #iris
                val = val_translated = struct.unpack('!h', data[16:18])[0]
            elif feature == 9: #zoom
                val = val_translated = struct.unpack('!h', data[16:18])[0]
        elif domain == 1: #camera
            if feature == 1: #gain
                val = struct.unpack('!h', data[16:18])[0]
                val_translated = self.VALUES_CC_GAIN.get(val, 'unknown')
            elif feature == 2: #white balance
                val = struct.unpack('!h', data[16:18])[0]
                val_translated = self.VALUES_CC_WB.get(val, val + 'K')
            elif feature == 5: #shutter
                val = struct.unpack('!h', data[18:20])[0]
                val_translated = self.VALUES_CC_SHUTTER.get(val, 'off')
        elif domain == 8: #chip
            val_keys_color = ['R','G','B','Y']
            if feature == 0: #lift
                val = dict(zip(val_keys_color, struct.unpack('!hhhh', data[16:24])))
                val_translated = {k: float(v)/4096 for k, v in val.items()}
            elif feature == 1: #gamma
                val = dict(zip(val_keys_color, struct.unpack('!hhhh', data[16:24])))
                val_translated = {k: float(v)/8192 for k, v in val.items()}
            elif feature == 2: #gain
                val = dict(zip(val_keys_color, struct.unpack('!hhhh', data[16:24])))
                val_translated = {k: float(v)*16/32767 for k, v in val.items()}
            elif feature == 3: #aperture
                pass # no idea
            elif feature == 4: #contrast
                val = struct.unpack('!h', data[18:20])[0]
                val_translated = float(val) / 4096
            elif feature == 5: #luminance
                val = struct.unpack('!h', data[16:18])[0]
                val_translated = float(val) / 2048
            elif feature == 6: #hue-saturation
                val_keys = ['hue', 'saturation']
                val = dict(zip(val_keys, struct.unpack('!hh', data[16:20])))
                val_translated = {}
                val_translated['hue'] = float(val['hue']) * 360 / 2048 + 180
                val_translated['saturation'] = float(val['saturation']) / 4096
        try:
            if domain == 0:
                feature_label = self.LABELS_CC_LENS_FEATURE[feature]
            elif domain == 1:
                feature_label = self.LABELS_CC_CAM_FEATURE[feature]
            elif domain == 8:
                feature_label = self.LABELS_CC_CHIP_FEATURE[feature]
            self.cameracontrol.setdefault(input_num, {}).setdefault('state_raw', {}).setdefault(self.LABELS_CC_DOMAIN[domain], {})[feature_label] = val
            self.cameracontrol.setdefault(input_num, {}).setdefault('state', {}).setdefault(self.LABELS_CC_DOMAIN[domain], {})[feature_label] = val_translated
        except KeyError:
            print("Warning: CC Feature not recognized (no label)")

    def recvRCPS(self, data):
        player_num = data[0]
        with self.state['mediaplayer'].setdefault(player_num, {}) as player:
            player['playing'] = bool(data[1])
            player['loop'] = bool(data[2])
            player['beginning'] = bool(data[3])
            player['clip_frame'] = struct.unpack('!H', data[4:6])[0]

    def recvMPCE(self, data):
        player_num = data[0]
        with self.state['mediaplayer'].setdefault(player_num, {}) as player:
            player['type'] = { 1: 'still', 2: 'clip' }.get(data[1])
            player['still_index'] = data[2]
            player['clip_index'] = data[3]

    def recvMPSp(self, data):
        self.config['mediapool'].setdefault(0, {})['maxlength'] = struct.unpack('!H', data[0:2])[0]
        self.config['mediapool'].setdefault(1, {})['maxlength'] = struct.unpack('!H', data[2:4])[0]

    def recvMPCS(self, data):
        bank = data[0]
        with self.state['mediapool'].setdefault('clips', {}).setdefault(bank, {}) as clip_bank:
            clip_bank['used'] = bool(data[1])
            clip_bank['filename'] = data[2:18].decode("utf-8")
            clip_bank['length'] = struct.unpack('!H', data[66:68])[0]

    def recvMPAS(self, data):
        bank = data[0]
        with self.state['mediapool'].setdefault('audio', {}).setdefault(bank, {}) as audio_bank:
            audio_bank['used'] = bool(data[1])
            audio_bank['filename'] = data[18:34].decode("utf-8")

    def recvMPfe(self, data):
        if data[0] != 0:
            return
        bank = data[3]
        with self.state['mediapool'].setdefault('stills', {}).setdefault(bank, {}) as still_bank:
            still_bank['used'] = bool(data[4])
            still_bank['hash'] = data[5:21].decode("utf-8")
            filename_length = data[23]
            still_bank['filename'] = data[24:(24+filename_length)].decode("utf-8")

    def recvAMIP(self, data):
        channel = struct.unpack('!H', data[0:2])[0]
        with self.system_config['audio'].setdefault(channel, {}) as channel_config:
            channel_config['fromMediaPlayer'] = bool(data[6])
            channel_config['plug'] = data[7]
        with self.state['audio'].setdefault(channel, {}) as channel_state:
            channel_state['mix_option'] = data[8]
            channel_state['volume'] = struct.unpack('!H', data[10:12])[0]
            channel_state['balance'] = struct.unpack('!h', data[12:14])[0]

    def recvAMMO(self, data):
        self.state['audio']['master_volume'] = struct.unpack('!H', data[0:2])[0]

    def recvAMmO(self, data):
        with self.state['audio'].setdefault('monitor', {}) as monitor:
            monitor['enabled'] = bool(data[0])
            monitor['volume'] = struct.unpack('!H', data[2:4])[0]
            monitor['mute'] = bool(data[4])
            monitor['solo'] = bool(data[5])
            monitor['solo_input'] = struct.unpack('!H', data[6:8])[0]
            monitor['dim'] = bool(data[8])

    def recvAMTl(self, data):
        src_count = struct.unpack('!H', data[0:2])[0]
        for i in range(2, src_count*3+2):
            channel = struct.unpack('!H', data[i:i+2])[0]
            self.state['audio'].setdefault('tally', {})[channel] = bool(data[i+2])

    def recvTlIn(self, data):
        src_count = struct.unpack('!H', data[0:2])[0]
        for i in range(2, src_count+2):
            self.state['tally_by_index'][i] = self.parseBitmask(data[i], ['pgm', 'prv'])

    def recvTlSr(self, data):
        src_count = struct.unpack('!H', data[0:2])[0]
        for i in range(2, src_count*3+2):
            source = struct.unpack('!H', data[i:i+2])[0]
            self.state['tally'][source] = self.parseBitmask(data[i+2], ['pgm', 'prv'])

    def recvTime(self, data):
        self.state['last_state_change'] = struct.unpack('!BBBB', data[0:4])

    # handling of attribute setting
    # -----------------------------
    def __setattr__(self, name, value):
        if name in ['system_config', 'status', 'config', 'state', 'cameracontrol']:
            self.__dict__[name] = AttrProxy(value, self, name)
            print("object setting proxied")
        else:
            self.__dict__[name] = value

if __name__ == '__main__':
    import config
    a = Atem(config.address)
    a.connectToSwitcher()
    #while (True):
    import time
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    a.waitForPacket()
    print("sending command")
    a.sendCommand("DCut", "\x00\x00\x00\x00")
    a.waitForPacket()    

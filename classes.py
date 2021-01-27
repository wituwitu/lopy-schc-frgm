from math import floor, ceil
import ubinascii
from functions import bitstring_to_bytes, is_monochar, zfill
from machine import Timer


class Protocol:
    NAME = None
    RULE_ID_SIZE = 0
    L2_WORD_SIZE = 0
    TILE_SIZE = 0
    M = 0
    N = 0
    BITMAP_SIZE = 0
    RCS_SIZE = 0
    RCS_ALGORITHM = None
    T = 0
    MAX_ACK_REQUESTS = 0
    MAX_WIND_FCN = 0
    RETRANSMISSION_TIMER_VALUE = None
    INACTIVITY_TIMER_VALUE = None
    UPLINK_MTU = 0
    DOWNLINK_MTU = 0


class SigfoxProfile(Protocol):
    direction = None
    mode = None

    def __init__(self, direction, mode, header_bytes):

        # print("This protocol is in " + direction + " direction and " + mode + " mode.")

        self.NAME = "SIGFOX"
        self.direction = direction
        self.mode = mode
        self.RETRANSMISSION_TIMER_VALUE = 45.0  # (45) enough to let a downlink message to be sent if needed
        self.INACTIVITY_TIMER_VALUE = 60.0  # (60) for demo purposes

        self.SIGFOX_DL_TIMEOUT = 20.0  # This is to be tested

        self.L2_WORD_SIZE = 8  # The L2 word size used by Sigfox is 1 byte

        self.N = 0

        self.HEADER_LENGTH = 0

        self.MESSAGE_INTEGRITY_CHECK_SIZE = None  # TBD
        self.RCS_ALGORITHM = None  # TBD

        self.UPLINK_MTU = 12 * 8
        self.DOWNLINK_MTU = 8 * 8

        if direction == "UPLINK":
            # if mode == "NO ACK":
            #     self.HEADER_LENGTH = 8
            #     self.RULE_ID_SIZE = 2  # recommended
            #     self.T = 2  # recommended
            #     self.N = 4  # recommended
            #     self.M = 0

            if mode == "ACK ALWAYS":
                pass  # TBD

            if mode == "ACK ON ERROR" and header_bytes == 1:
                self.HEADER_LENGTH = 8
                self.RULE_ID_SIZE = 2
                self.T = 1
                self.N = 3
                self.M = 2  # recommended to be single
                self.WINDOW_SIZE = 2 ** self.N - 1
                self.BITMAP_SIZE = 2 ** self.N - 1  # from excel
                self.MAX_ACK_REQUESTS = 3  # SHOULD be 2
                self.MAX_WIND_FCN = 6  # SHOULD be

            if mode == "ACK ON ERROR" and header_bytes == 2:
                self.HEADER_LENGTH = 16
                self.RULE_ID_SIZE = 7
                self.T = 1
                self.N = 5
                self.M = 3  # recommended to be single
                self.WINDOW_SIZE = 2 ** self.N - 1
                self.BITMAP_SIZE = 2 ** self.N - 1  # from excel
                self.MAX_ACK_REQUESTS = 3  # SHOULD be 2
                self.MAX_WIND_FCN = 6  # SHOULD be

        if direction == "DOWNLINK":
            if mode == "NO ACK":
                self.HEADER_LENGTH = 8
                self.RULE_ID_SIZE = 2
                self.T = 1
                self.M = 2
                self.N = 3
            if mode == "ACK ALWAYS":
                self.HEADER_LENGTH = 8
                self.RULE_ID_SIZE = 2  # recommended
                self.T = 2  # recommended
                self.N = 3  # recommended
                self.M = 1  # MUST be present, recommended to be single
                self.MAX_ACK_REQUESTS = 3  # SHOULD be 2
                self.MAX_WIND_FCN = 6  # SHOULD be

            # Sigfox downlink frames have a fixed length of 8 bytes, which means
            #    that default SCHC algorithm for padding cannot be used.  Therefore,
            #    the 3 last bits of the fragmentation header are used to indicate in
            #    bytes the size of the padding.  A size of 000 means that the full
            #    ramaining frame is used to carry payload, a value of 001 indicates
            #    that the last byte contains padding, and so on.

            else:
                pass


class Header:
    profile = None

    RULE_ID = ""
    DTAG = ""
    W = ""
    FCN = ""
    C = ""

    string = ""
    bytes = None

    def __init__(self, profile, rule_id, dtag, w, fcn, c=""):  # rule_id is arbitrary, as it's not applicable for F/R

        self.profile = profile

        direction = profile.direction

        if direction == "DOWNLINK":
            self.FCN = ""
            self.C = c

        if len(rule_id) != profile.RULE_ID_SIZE:
            print('RULE must be of length RULE_ID_SIZE')
        else:
            self.RULE_ID = rule_id

        if profile.T == "0":
            self.DTAG = ""
        elif len(dtag) != profile.T:
            print('DTAG must be of length T')
        else:
            self.DTAG = dtag

        if len(w) != profile.M:
            print(w)
            print(profile.M)
            print('W must be of length M')
        else:
            self.W = w

        if fcn != "":
            if len(fcn) != profile.N:
                print('FCN must be of length N')
            else:
                self.FCN = fcn

        self.string = "".join([self.RULE_ID, self.DTAG, self.W, self.FCN, self.C])
        self.bytes = bytes(int(self.string[i:i + 8], 2) for i in range(0, len(self.string), 8))

    def test(self):

        print("HEADER:")
        print(self.string)

        if len(self.string) != self.profile.HEADER_LENGTH:
            print('The header has not been initialized correctly.')


class Fragment:
    profile = None
    header_length = 0
    rule_id_size = 0
    t = 0
    n = 0
    window_size = 0

    header = None
    payload = None
    string = ''

    def __init__(self, profile, fragment):
        self.profile = profile

        self.header_length = profile.HEADER_LENGTH
        self.rule_id_size = profile.RULE_ID_SIZE
        self.t = profile.T
        self.n = profile.N
        self.m = profile.M

        header = zfill(str(bin(int.from_bytes(fragment[0], 'big')))[2:], self.header_length)
        payload = fragment[1]

        rule_id = str(header[:self.rule_id_size])
        dtag = str(header[self.rule_id_size:self.rule_id_size + self.t])
        window = str(header[self.rule_id_size + self.t:self.rule_id_size + self.t + self.m])
        fcn = str(header[self.rule_id_size + self.t + self.m:self.rule_id_size + self.t + self.m + self.n])
        c = ""

        self.header = Header(self.profile, rule_id, dtag, window, fcn, c)
        self.payload = payload
        self.bytes = self.header.bytes + self.payload
        self.string = self.bytes.decode()
        self.hex = ubinascii.hexlify(self.bytes).decode()

    def is_all_1(self):
        fcn = self.header.FCN
        payload = self.payload.decode()
        return fcn[0] == '1' and is_monochar(fcn) and not (payload[0] == '0' and is_monochar(payload))

    def is_all_0(self):
        fcn = self.header.FCN
        return fcn[0] == '0' and is_monochar(fcn)

    def expects_ack(self):
        return self.is_all_0() or self.is_all_1()

    def is_sender_abort(self):
        fcn = self.header.FCN
        padding = self.payload.decode()
        return fcn[0] == '1' and is_monochar(fcn) and padding[0] == '0' and is_monochar(padding)


class ACK:
    profile = None
    rule_id = None
    dtag = None
    w = None
    bitmap = None
    c = None
    header = ''
    padding = ''

    window_number = None

    def __init__(self, profile, rule_id, dtag, w, c, bitmap, padding=''):
        self.profile = profile
        self.rule_id = rule_id
        self.dtag = dtag
        self.w = w
        self.c = c
        self.bitmap = bitmap
        self.padding = padding

        # Bitmap may or may not be carried
        self.header = self.rule_id + self.dtag + self.w + self.c + self.bitmap
        while len(self.header + self.padding) < profile.DOWNLINK_MTU:
            self.padding += '0'

        self.window_number = int(self.w, 2)

    def to_string(self):
        return self.header + self.padding

    def to_bytes(self):
        return bitstring_to_bytes(self.header + self.padding)

    def length(self):
        return len(self.header + self.padding)

    def is_receiver_abort(self):
        ack_string = self.to_string()
        l2_word_size = self.profile.L2_WORD_SIZE
        header = ack_string[:len(self.rule_id + self.dtag + self.w + self.c)]
        padding = ack_string[len(self.rule_id + self.dtag + self.w + self.c):ack_string.rfind('1') + 1]
        padding_start = padding[:-l2_word_size]
        padding_end = padding[-l2_word_size:]

        if padding_end == "1" * l2_word_size:
            if padding_start != '' and len(header) % l2_word_size != 0:
                return is_monochar(padding_start) and padding_start[0] == '1'
            else:
                return len(header) % l2_word_size == 0
        else:
            return False

    @staticmethod
    def parse_from_hex(profile, h):
        ack = zfill(bin(int(h, 16))[2:], profile.DOWNLINK_MTU)
        ack_index_dtag = profile.RULE_ID_SIZE
        ack_index_w = ack_index_dtag + profile.T
        ack_index_c = ack_index_w + profile.M
        ack_index_bitmap = ack_index_c + 1
        ack_index_padding = ack_index_bitmap + profile.BITMAP_SIZE

        return ACK(profile,
                   ack[:ack_index_dtag],
                   ack[ack_index_dtag:ack_index_w],
                   ack[ack_index_w:ack_index_c],
                   ack[ack_index_c],
                   ack[ack_index_bitmap:ack_index_padding],
                   ack[ack_index_padding:])


class ReceiverAbort(ACK):

    def __init__(self, profile, header):
        rule_id = header.RULE_ID
        dtag = header.DTAG
        w = header.W

        header = Header(profile=profile,
                        rule_id=rule_id,
                        dtag=dtag,
                        w=w,
                        fcn='',
                        c='1')

        padding = ''
        # if the Header does not end at an L2 Word boundary,
        # append bits set to 1 as needed to reach the next L2 Word boundary.
        while len(header.string + padding) % profile.L2_WORD_SIZE != 0:
            padding += '1'

        # append exactly one more L2 Word with bits all set to ones.
        padding += '1' * profile.L2_WORD_SIZE

        super().__init__(profile, rule_id, dtag, w, c='1', bitmap='', padding=padding)


class SenderAbort(Fragment):
    profile = None
    header_length = 0
    rule_id_size = 0
    t = 0
    n = 0
    window_size = 0

    header = None
    padding = ''

    def __init__(self, profile, header):
        self.profile = profile
        rule_id = header.RULE_ID
        dtag = header.DTAG
        w = header.W
        fcn = "1" * profile.N
        self.header = Header(profile, rule_id, dtag, w, fcn)

        while len(self.header.string + self.padding) < profile.UPLINK_MTU:
            self.padding += '0'

        super().__init__(profile, [bitstring_to_bytes(rule_id + dtag + w + fcn), self.padding.encode()])


class Fragmenter:
    profile = None
    schc_packet = None

    def __init__(self, profile, schc_packet):
        self.profile = profile
        self.schc_packet = schc_packet

    def fragment(self):
        payload_max_length = int((self.profile.UPLINK_MTU - self.profile.HEADER_LENGTH) / 8)
        message = self.schc_packet
        fragment_list = []
        n = self.profile.N
        m = self.profile.M
        number_of_fragments = int(ceil(float(len(message)) / payload_max_length))

        print("[FRGM] Fragmenting message into " + str(number_of_fragments) + " pieces...")

        # check if the packet size can be transmitted or not
        if len(fragment_list) > (2 ** self.profile.M) * self.profile.WINDOW_SIZE:
            print(len(fragment_list))
            print((2 ** self.profile.M) * self.profile.WINDOW_SIZE)
            print(
                "The SCHC packet cannot be fragmented in 2 ** M * WINDOW_SIZE fragments or less. A Rule ID cannot be "
                "selected.")
        # What does this mean?
        # Sending packet does not fit (should be tested in fragmentation)

        for i in range(number_of_fragments):
            w = zfill(bin(int(floor((i / (2 ** n - 1) % (2 ** m)))))[2:], self.profile.M)
            fcn = zfill(bin((2 ** n - 2) - (i % (2 ** n - 1)))[2:], self.profile.N)

            fragment_payload = message[i * payload_max_length:(i + 1) * payload_max_length]

            if len(self.schc_packet) <= 300:
                if len(fragment_payload) < payload_max_length or i == (len(range(number_of_fragments)) - 1):
                    header = Header(self.profile, rule_id="00", dtag="0", w=w, fcn="111", c=0)
                else:
                    header = Header(self.profile, rule_id="00", dtag="0", w=w, fcn=fcn, c=0)
            else:
                if len(fragment_payload) < payload_max_length or i == (len(range(number_of_fragments)) - 1):
                    header = Header(self.profile, rule_id="1111000", dtag="0", w=w, fcn="11111", c=0)
                else:
                    header = Header(self.profile, rule_id="1111000", dtag="0", w=w, fcn=fcn, c=0)
            fragment = [header.bytes, fragment_payload]
            # print("[" + header.string + "]" + str(fragment_payload))
            fragment_list.append(fragment)

        print("[FRGM] Fragmentation complete.")

        return fragment_list

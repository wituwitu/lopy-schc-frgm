from network import Sigfox
import socket
import ubinascii

from classes import *


def post(fragment_sent, retransmit=False):
    global attempts, current_window, last_window, i
    profile = fragment_sent.profile

    if fragment_sent.is_all_0() and not retransmit:
        print("[POST] This is an All-0. Using All-0 SIGFOX_DL_TIMEOUT.")

        s.setsockopt(socket.SOL_SIGFOX, socket.SO_RX, True)
        s.settimeout(profile.SIGFOX_DL_TIMEOUT)

    elif fragment_sent.is_all_1():
        print("[POST] This is an All-1. Using RETRANSMISSION_TIMER_VALUE. Increasing ACK attempts.")
        attempts += 1
        s.setsockopt(socket.SOL_SIGFOX, socket.SO_RX, True)
        s.settimeout(profile.RETRANSMISSION_TIMER_VALUE)

    else:
        s.setsockopt(socket.SOL_SIGFOX, socket.SO_RX, False)
        s.settimeout(40)

    data = fragment_sent.bytes

    print("[POST] Posting fragment {} ({})".format(fragment_sent.header.string, fragment_sent.hex))

    try:
        s.send(data)

        if fragment_sent.is_sender_abort():
            print("Sent Sender-Abort. Goodbye")
            exit(1)

        response = None

        if fragment_sent.expects_ack():
            response = s.recv(64)

        print("[POST] Response: {}".format(response))

        if response is None:
            if not retransmit:
                i += 1
                return

        else:
            print("Response: {}. Ressetting attempts counter to 0.".format(response))
            attempts = 0

            # Parse ACK
            ack = ubinascii.hexlify(response).decode()
            ack_object = ACK.parse_from_hex(profile, ack)

            if ack_object.is_receiver_abort():
                print("ERROR: Receiver Abort received. Aborting communication.")
                exit(1)

            # Extract data from ACK
            ack_window = ack_object.w
            ack_window_number = ack_object.window_number
            c = ack_object.c
            bitmap = ack_object.bitmap
            print("ACK: {}".format(ack))
            print("ACK window: {}".format(str(ack_window)))
            print("ACK bitmap: {}".format(bitmap))
            print("ACK C bit: {}".format(c))
            print("last window: {}".format(last_window))

            # If the W field in the SCHC ACK corresponds to the last window of the SCHC Packet:
            if ack_window_number == last_window:
                # If the C bit is set, the sender MAY exit successfully.
                if c == '1':
                    print("Last ACK received, fragments reassembled successfully. End of transmission.")
                    exit(0)
                # Otherwise,
                else:
                    # If the Profile mandates that the last tile be sent in an All-1 SCHC Fragment
                    # (we are in the last window), .is_all_1() should be true:
                    if fragment_sent.is_all_1():
                        # This is the last bitmap, it contains the data up to the All-1 fragment.
                        last_bitmap = bitmap[:len(fragment_list) % window_size]
                        print("last bitmap {}".format(last_bitmap))

                        # If the SCHC ACK shows no missing tile at the receiver, abort.
                        # (C = 0 but transmission complete)
                        if last_bitmap[0] == '1' and all(last_bitmap):
                            print("ERROR: SCHC ACK shows no missing tile at the receiver.")
                            post(SenderAbort(fragment_sent.profile, fragment_sent.header))

                        # Otherwise (fragments are lost),
                        else:
                            # Check for lost fragments.
                            for j in range(len(last_bitmap)):
                                # If the j-th bit of the bitmap is 0, then the j-th fragment was lost.
                                if last_bitmap[j] == '0':
                                    print(
                                        "The {}th ({} / {}) fragment was lost! Sending again...".format(j, window_size * ack_window_number + j, len(fragment_list)))
                                    # Try sending again the lost fragment.
                                    fragment_to_be_resent = Fragment(profile,
                                                                     fragment_list[window_size * ack_window + j])
                                    print("Lost fragment: {}".format(fragment_to_be_resent.string))
                                    post(fragment_to_be_resent, retransmit=True)

                            # Send All-1 again to end communication.
                            post(fragment_sent)

                    else:
                        print("ERROR: While being at the last window, the ACK-REQ was not an All-1."
                              "This is outside of the Sigfox scope.")
                        exit(1)

            # Otherwise, there are lost fragments in a non-final window.
            else:
                # Check for lost fragments.
                for j in range(len(bitmap)):
                    # If the j-th bit of the bitmap is 0, then the j-th fragment was lost.
                    if bitmap[j] == '0':
                        print(
                            "The {}th ({} / {}) fragment was lost! Sending again...".format(j, window_size * ack_window_number + j, len(fragment_list)))
                        # Try sending again the lost fragment.
                        fragment_to_be_resent = Fragment(profile,
                                                         fragment_list[window_size * ack_window_number + j])
                        print("Lost fragment: {}".format(fragment_to_be_resent.string))
                        post(fragment_to_be_resent, retransmit=True)
                if fragment_sent.is_all_1():
                    # Send All-1 again to end communication.
                    post(fragment_sent)
                elif fragment_sent.is_all_0():
                    i += 1
                    current_window += 1

    # If the timer expires
    except TimeoutError:
        # If an ACK was expected
        if fragment_sent.is_all_1():
            # If the attempts counter is strictly less than MAX_ACK_REQUESTS, try again
            if attempts < profile.MAX_ACK_REQUESTS:
                print("SCHC Timeout reached while waiting for an ACK. Sending the ACK Request again...")
                post(fragment_sent)
            # Else, exit with an error.
            else:
                print("ERROR: MAX_ACK_REQUESTS reached. Sending Sender-Abort.")
                header = fragment_sent.header
                abort = SenderAbort(profile, header)
                post(abort)

        # If the ACK can be not sent (Sigfox only)
        if fragment_sent.is_all_0():
            print("All-0 timeout reached. Proceeding to next window.")
            if not retransmit:
                i += 1
                current_window += 1

        # Else, HTTP communication failed.
        else:
            print("ERROR: HTTP Timeout reached.")
            exit(1)


# Read the file to be sent.
with open("example_300.txt", "rb") as data:
    f = data.read()
    message = bytearray(f)

# Initialize variables.
total_size = len(message)
current_size = 0
percent = round(0, 2)
i = 0
current_window = 0
header_bytes = 1 if total_size <= 300 else 2
profile = SigfoxProfile("UPLINK", "ACK ON ERROR", header_bytes)
window_size = profile.WINDOW_SIZE

# Fragment the file.
fragmenter = Fragmenter(profile, message)
fragment_list = fragmenter.fragment()
last_window = (len(fragment_list) - 1) // window_size

# The fragment sender MUST initialize the Attempts counter to 0 for that Rule ID and DTag value pair
# (a whole SCHC packet)
attempts = 0
fragment = None

# Initialize socket
sigfox = Sigfox(mode=Sigfox.SIGFOX, rcz=Sigfox.RCZ4)
s = socket.socket(socket.AF_SIGFOX, socket.SOCK_RAW)
s.setblocking(True)

if len(fragment_list) > (2 ** profile.M) * window_size:
    print(len(fragment_list))
    print((2 ** profile.M) * window_size)
    print("ERROR: The SCHC packet cannot be fragmented in 2 ** M * WINDOW_SIZE fragments or less. A Rule ID cannot be "
          "selected.")
    exit(1)

# Start sending fragments.
while i < len(fragment_list):
    # A fragment has the format "fragment = [header, payload]".
    data = bytes(fragment_list[i][0] + fragment_list[i][1])
    current_size += len(fragment_list[i][1])
    percent = round(float(current_size) / float(total_size) * 100, 2)

    # Convert to a Fragment class for easier manipulation.
    resent = None
    timeout = False
    fragment = Fragment(profile, fragment_list[i])

    # Send the data.
    print("Sending...")
    post(fragment)

# The code is subject to Purdue University copyright policies.
# Do not share, distribute, or post online.

import time
import sys
import queue
from client import Client
from packet import Packet


"""
1. connection setup
2. sender assign sequence number
    * await ack of the same number
    * if ack not received before timoeut send the same packet again
    * else, increment the sequence number and send next
3. receiver awaits for a message
    * successful receive
        - if the sequence number is less than the stored sequence number, discard it and send an ack for that packet sequence number
        - if the sequence number is equal to the stored sequence number, store it and send an ack for that sequence number
"""

IS_FINISHED = -1
IS_UNSENT = -2
class MyClient(Client):
    """Implement a reliable transport"""

    def __init__(self, addr, sendFile, recvFile, MSS):
        """Client A is sending bytes from file 'sendFile' to client B.
           Client B stores the received bytes from A in file 'recvFile'.
        """
        Client.__init__(self, addr, sendFile, recvFile, MSS)  # initialize superclass
        self.connSetup = 0
        self.connEstablished = 0
        self.connTerminate = 0
        self.sendFile = sendFile
        self.recvFile = recvFile

        self.send_timeout: float = 5

        self.max_in_flight: int = 50
        self.current_in_flight: int = 0
        self.receive_buffer: list = []
        self.timeout_buffer: list = []
        self.send_buffer: list = []
        self.send_queue: queue.Queue = queue.Queue()

        """add your own class fields and initialization code here"""


    def sender_receive(self, packet: Packet):
        if packet.synFlag == 1 and packet.ackFlag == 1:  # received a SYN-ACK packet
            packet = Packet("A", "B", 1, 1, 0, 1, 0, None)  # create an ACK packet
            if self.link:
                self.link.send(packet, self.addr)  # send ACK packet out into the network
            self.connEstablished = 1

        elif packet.finFlag == 1 and packet.ackFlag == 1:  # received a FIN-ACK packet
            packet = Packet("A", "B", 0, 0, 0, 1, 0, None)  # create an ACK packet
            if self.link:
                self.link.send(packet, self.addr)  # send ACK packet out into the network

        elif packet.ackFlag == 1:
            self.timeout_buffer[packet.seqNum] = IS_FINISHED
            self.current_in_flight -= 1


    def receiver_receive(self, packet: Packet):
        if packet.synFlag == 1:  # received a SYN packet
            packet = Packet("B", "A", 0, 1, 1, 1, 0, None)  # create a SYN-ACK packet
            if self.link:
                self.link.send(packet, self.addr)  # send SYN-ACK packet out into the network
            self.connSetup = 1

        elif packet.finFlag == 1:  # received a FIN packet
            packet = Packet("B", "A", 0, 0, 0, 1, 1, None)  # create a FIN-ACK packet
            if self.link:
                self.link.send(packet, self.addr)  # send FIN-ACK packet out into the network
            self.connTerminate = 1
            for content in self.receive_buffer:
                self.recvFile.write(content)

        elif self.connSetup == 1 and packet.ackFlag == 1:  # received an ACK packet for SYN-ACK
            self.connSetup = 0

        elif self.connTerminate == 1 and packet.ackFlag == 1:  # received an ACK packet for FIN-ACK
            self.connTerminate = 0

        elif packet.ackFlag == 1 and self.connSetup == 0 and self.connTerminate == 0:  # received a data packet
            if packet.seqNum > len(self.receive_buffer) - 1:
                needed_space = packet.seqNum - len(self.receive_buffer) + 1
                self.receive_buffer += ["" for x in range(needed_space)]
            if self.receive_buffer[packet.seqNum] == "":
                self.receive_buffer[packet.seqNum] = packet.payload
            ack_packet = Packet("B", "A", packet.seqNum, 0, 0, 1, 0, None)
            self.send_queue.put(ack_packet)


    def handleRecvdPackets(self):
        """Handle packets recvd from the network.
           This method is called every 0.1 seconds.
        """
        if self.link:
            packet = self.link.recv(self.addr) # receive a packet from the link
            if packet:
                # log recvd packet
                self.f.write("Packet - srcAddr: " + packet.srcAddr + " dstAddr: " + packet.dstAddr + " seqNum: " + str(packet.seqNum) + " ackNum: " + str(packet.ackNum) + " SYNFLag: " + str(packet.synFlag) + " ACKFlag: " + str(packet.ackFlag) + " FINFlag: " + str(packet.finFlag) + " Payload: " + str(packet.payload))
                self.f.write("\n")

                # handle recvd packets for client A (sender of the file)
                if self.addr == "A":
                    self.sender_receive(packet)

                # handle recvd packets for client B (receiver of the file)
                if self.addr == "B":
                    self.receiver_receive(packet)

    def sender_unpack_content(self):
        content = self.sendFile.read(self.MSS)
        while content:
            self.send_buffer.append(content)
            self.timeout_buffer.append(IS_UNSENT)
            content = self.sendFile.read(self.MSS)

    def sender_send_content(self, packet: Packet):
        if self.timeout_buffer[packet.seqNum] == IS_FINISHED:
            return
        if self.link:
            self.total_sends += 1
            self.link.send(packet, self.addr)  # send packet out into the network
            self.timeout_buffer[packet.seqNum] = time.time()
            self.current_in_flight += 1

    def sender_send(self):
        if self.connSetup == 0:
            self.sender_unpack_content()
            packet = Packet("A", "B", 0, 0, 1, 0, 0, None)  # create a SYN packet
            if self.link:
                self.link.send(packet, self.addr)  # send SYN packet out into the network
            self.connSetup = 1

        if self.connEstablished == 1 and self.connTerminate == 0:
            unsent_flag = False
            for seq_num, tup in enumerate(zip(self.send_buffer, self.timeout_buffer)):
                content, timer = tup
                if timer != IS_FINISHED:
                    unsent_flag = True
                if timer >= 0 and time.time() - timer > self.send_timeout_minimum: # if timeout incurred, re-insert the content to the send queue
                    self.send_queue.put(
                        Packet("A", "B", seq_num, 0, 0, 1, 0, content)
                    )
                    self.timeout_buffer[seq_num] = IS_UNSENT
                if self.current_in_flight < self.max_in_flight:
                    if timer == IS_UNSENT and self.current_in_flight <= self.max_in_flight:
                        self.send_queue.put(
                            Packet("A", "B", seq_num, 0, 0, 1, 0, content)
                        )
                    try:
                        packet = self.send_queue.get(block=False)
                        self.sender_send_content(packet)
                    except:
                        pass
            if not unsent_flag:
                # start connection termination
                packet = Packet("A", "B", 0, 0, 0, 1, 1, None)  # create a FIN packet
                if self.link:
                    self.link.send(packet, self.addr)  # send FIN packet out into the network
                self.connTerminate = 1

    def receiver_send(self):
        try:
            packet = self.send_queue.get(block=False)
            if self.link and packet is not None:
                self.link.send(packet, self.addr)
                self.last_send_time = time.time()
        except Exception:
            return

    def sendPackets(self):
        """Send packets into the network.
           This method is called every 0.1 seconds.
        """
        # send packets from client A (sender of the file)
        if self.addr == "A":
            self.sender_send()

        # send packets from client B (receiver of the file)
        if self.addr == "B":
            self.receiver_send()


# sender: Window size W dynamically sized
# window is non-contiguous, but sequence numbers always assigned.
# cumulative ack necessary

# receiver: if the received packet is retransmit duplicate
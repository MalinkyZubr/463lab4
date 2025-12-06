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

        self.last_send_time: float = time.time()
        self.send_timeout_minimum: float = 5
        self.send_timeout: float = self.send_timeout_minimum
        self.total_sends: int = 1
        self.failed_sends: int = 0

        self.max_in_flight: int = 5
        self.current_in_flight: int = 0
        receive_buffer: list = []
        timeout_buffer: list = []

        self.awaiting_ack: bool = False
        self.content: str = ""
        self.sequence_number: int = 0
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
            self.awaiting_ack = False

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

        elif self.connSetup == 1 and packet.ackFlag == 1:  # received an ACK packet for SYN-ACK
            self.connSetup = 0

        elif self.connTerminate == 1 and packet.ackFlag == 1:  # received an ACK packet for FIN-ACK
            self.connTerminate = 0

        elif packet.ackFlag == 1 and self.connSetup == 0 and self.connTerminate == 0:  # received a data packet
            if packet.seqNum == self.sequence_number + 1:
                self.recvFile.write(packet.payload)  # write the contents of the packet to recvFile
                self.sequence_number = packet.seqNum
            ack_packet = Packet("B", "A", self.sequence_number, 0, 0, 1, 0, None)
            if self.link:
                self.link.send(ack_packet, self.addr)
                self.last_send_time = time.time()
        # elif time.time() - self.last_send_time >= self.send_timeout_minimum:
        #     ack_packet = Packet("B", "A", self.sequence_number, 0, 0, 1, 0, None)
        #     if self.link:
        #         self.link.send(ack_packet, self.addr)


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

    def calculate_new_timeout(self):
        # I decided to dynamically calculate timeouts based on geometric distribution
        percent_success = 1 - (self.failed_sends / self.total_sends)


    def sender_send(self):
        if self.connSetup == 0:
            packet = Packet("A", "B", 0, 0, 1, 0, 0, None)  # create a SYN packet
            if self.link:
                self.link.send(packet, self.addr)  # send SYN packet out into the network
            self.connSetup = 1

        if self.connEstablished == 1 and self.connTerminate == 0:
            if not self.awaiting_ack:
                self.content = self.sendFile.read(self.MSS)  # read MSS bytes from sendFile
                self.sequence_number += 1
            elif self.awaiting_ack and time.time() - self.last_send_time <= self.send_timeout:
                return
            else:
                self.failed_sends += 1
            if self.content:
                packet = Packet("A", "B", self.sequence_number, 0, 0, 1, 0, self.content)  # create a packet
                if self.link:
                    self.total_sends += 1

                    self.link.send(packet, self.addr)  # send packet out into the network
                    self.awaiting_ack = True
                    self.last_send_time = time.time()
            else:
                # start connection termination
                packet = Packet("A", "B", 0, 0, 0, 1, 1, None)  # create a FIN packet
                if self.link:
                    self.link.send(packet, self.addr)  # send FIN packet out into the network
                self.connTerminate = 1

    def receiver_send(self):
        pass

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
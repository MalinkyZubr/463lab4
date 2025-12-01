# The code is subject to Purdue University copyright policies.
# Do not share, distribute, or post online.

import time
import sys
import queue
from client import Client
from packet import Packet

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
        """add your own class fields and initialization code here"""


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
                    if packet.synFlag == 1 and packet.ackFlag == 1: # received a SYN-ACK packet
                        packet = Packet("A", "B", 1, 1, 0, 1, 0, None) # create an ACK packet
                        if self.link:
                            self.link.send(packet, self.addr) # send ACK packet out into the network
                        self.connEstablished = 1

                    elif packet.finFlag == 1 and packet.ackFlag == 1: # received a FIN-ACK packet
                        packet = Packet("A", "B", 0, 0, 0, 1, 0, None) # create an ACK packet
                        if self.link:
                            self.link.send(packet, self.addr) # send ACK packet out into the network

                # handle recvd packets for client B (receiver of the file)
                if self.addr == "B":
                    if packet.synFlag == 1: # received a SYN packet
                        packet = Packet("B", "A", 0, 1, 1, 1, 0, None) # create a SYN-ACK packet
                        if self.link:
                            self.link.send(packet, self.addr) # send SYN-ACK packet out into the network
                        self.connSetup = 1

                    elif packet.finFlag == 1: # received a FIN packet
                        packet = Packet("B", "A", 0, 0, 0, 1, 1, None) # create a FIN-ACK packet
                        if self.link:
                            self.link.send(packet, self.addr) # send FIN-ACK packet out into the network
                        self.connTerminate = 1

                    elif self.connSetup == 1 and packet.ackFlag == 1: # received an ACK packet for SYN-ACK
                        self.connSetup = 0

                    elif self.connTerminate == 1 and packet.ackFlag == 1: # received an ACK packet for FIN-ACK
                        self.connTerminate = 0

                    elif packet.ackFlag == 1 and self.connSetup == 0 and self.connTerminate == 0: # received a data packet
                            self.recvFile.write(packet.payload) # write the contents of the packet to recvFile


    def sendPackets(self):
        """Send packets into the network.
           This method is called every 0.1 seconds.
        """
        # send packets from client A (sender of the file)
        if self.addr == "A":
            if self.connSetup == 0:
                packet = Packet("A", "B", 0, 0, 1, 0, 0, None) # create a SYN packet
                if self.link:
                    self.link.send(packet, self.addr) # send SYN packet out into the network
                self.connSetup = 1

            if self.connEstablished == 1 and self.connTerminate == 0:
                content = self.sendFile.read(self.MSS) # read MSS bytes from sendFile
                if content:
                    packet = Packet("A", "B", 0, 0, 0, 1, 0, content) # create a packet
                    if self.link:
                        self.link.send(packet, self.addr) # send packet out into the network
                else:
                    # start connection termination
                    packet = Packet("A", "B", 0, 0, 0, 1, 1, None) # create a FIN packet
                    if self.link:
                        self.link.send(packet, self.addr) # send FIN packet out into the network
                    self.connTerminate = 1

        # send packets from client B (receiver of the file)
        if self.addr == "B":
            pass


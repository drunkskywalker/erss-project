

from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.encoder import _EncodeVarint
from google.protobuf.reflection import GeneratedProtocolMessageType

from . import db
from . import world_amazon_pb2
from . import amazon_ups_pb2

import io
import socket
from typing import List


def send_message(socket: socket, message):
    s_message = message.SerializeToString()
    _EncodeVarint(socket.send, len(s_message), None)
    socket.send(s_message)
    var_int_buff = []
    """
    while True:
        buf = socket.recv(1)
        var_int_buff += buf
        msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
        if new_pos != 0:
            break
    whole_message = socket.recv(msg_len)
    print(whole_message)
    return whole_message
    """
    # return recv_message(socket)


# fixed recv message error: https://groups.google.com/g/protobuf/c/4RydUI1HkSM


def recv_message(socket: socket):
    # int length is at most 4 bytes long

    hdr_bytes = socket.recv(1024)
    (msg_length, hdr_length) = _DecodeVarint32(hdr_bytes, 0)
    return hdr_bytes[hdr_length: ]


    '''
    rsp_buffer = io.BytesIO()
    if hdr_length < 4:
        rsp_buffer.write(hdr_bytes[hdr_length:])
    print("hdr_length: ", hdr_length)
    # read the remaining message bytes
    msg_length = msg_length - (4 - hdr_length)
    print("msg_length: ", msg_length)
    rsp_bytes = socket.recv(msg_length)
    rsp_buffer.write(rsp_bytes)
    msg_length = msg_length - len(rsp_bytes)

    return rsp_buffer.getvalue()
    '''


def send_ack(socket: socket, acks: list, to_where: str):
    """
    :param socket: destination socket
    :param acks: list of acks
    :param to_where: "world" or "ups"
    """
    if to_where == "world":
        CommandsMsg = world_amazon_pb2.ACommands()
    elif to_where == "ups":
        CommandsMsg = amazon_ups_pb2.AUMessages()
    else:
        raise ValueError("to_where must be either 'world' or 'ups'")

    for ack in acks:
        CommandsMsg.acks.append(ack)
    s_message = CommandsMsg.SerializeToString()
    _EncodeVarint(socket.send, len(s_message), None)
    socket.send(s_message)


def queue_send_world_add(
    buy: list = None, topack: list = None, load: list = None, queries: list = None
):
    """
    Add a message to the world queue to send to world
    """
    if buy is not None:
        for i in range(len(buy)):
            db.queue_world_send.put(buy[i].seqnum)
            db.queue_world_send.put(0)
            db.queue_world_send.put(buy[i])
    else:
        print("no buy orders")
    if topack is not None:
        for i in range(len(topack)):
            db.queue_world_send.put(topack[i].seqnum)
            db.queue_world_send.put(1)
            db.queue_world_send.put(topack[i])
    else:
        print("no topack orders")
    if load is not None:
        for i in range(len(load)):
            db.queue_world_send.put(load[i].seqnum)
            db.queue_world_send.put(2)
            db.queue_world_send.put(load[i])
    else:
        print("no load orders")
    if queries is not None:
        for i in range(len(queries)):
            db.queue_world_send.put(queries[i].seqnum)
            db.queue_world_send.put(3)
            db.queue_world_send.put(queries[i])
    else:
        print("no queries")


def queue_send_ups_add(
    order: list = None,
    assodiateUserId: list = None,
    callTruck: list = None,
    updateTruckStatus: list = None,
    truckGoDeliver: list = None,
    error: list = None,
):
    """
    Add a message to the ups queue to send to ups
    """
    if order is not None:
        for i in range(len(order)):
            db.queue_ups_send.put(order[i].seqnum)
            db.queue_ups_send.put(0)
            db.queue_ups_send.put(order[i])

    if assodiateUserId is not None:
        for i in range(len(assodiateUserId)):
            db.queue_ups_send.put(assodiateUserId[i].seqnum)
            db.queue_ups_send.put(1)
            db.queue_ups_send.put(assodiateUserId[i])

    if callTruck is not None:
        for i in range(len(callTruck)):
            db.queue_ups_send.put(callTruck[i].seqnum)
            db.queue_ups_send.put(2)
            db.queue_ups_send.put(callTruck[i])

    if updateTruckStatus is not None:
        for i in range(len(updateTruckStatus)):
            db.queue_ups_send.put(updateTruckStatus[i].seqnum)
            db.queue_ups_send.put(3)
            db.queue_ups_send.put(updateTruckStatus[i])

    if truckGoDeliver is not None:
        for i in range(len(truckGoDeliver)):
            db.queue_ups_send.put(truckGoDeliver[i].seqnum)
            db.queue_ups_send.put(4)
            db.queue_ups_send.put(truckGoDeliver[i])

    if error is not None:
        for i in range(len(error)):
            db.queue_ups_send.put(error[i].seqnum)
            db.queue_ups_send.put(5)
            db.queue_ups_send.put(error[i])


class SeqAckRecordBase:
    """
    Track the sequence number of the received message which has already been handled and should be acked
    """

    def __init__(self, to_where: str):
        self.seq_acked_queue = set()
        self.to_where = to_where

    def contains_seqnum(self, seq: int):
        return seq in self.seq_acked_queue

    def contains_cmd(self, cmd: GeneratedProtocolMessageType):
        return self.contains_seqnum(cmd.seqnum)

    def seq_add_ack(self, cmds: List[GeneratedProtocolMessageType], socket):
        for cmd in cmds:
            self.seq_acked_queue.add(cmd.seqnum)
            send_ack(socket, [cmd.seqnum], self.to_where)


def connect_socket(host: str, port: int):
    s = socket.socket()
    s.connect((host, port))
    return s

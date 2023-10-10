import socket
import struct
import world_amazon_pb2
import world_ups_pb2
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.encoder import _EncodeVarint

s = socket.socket()
s.connect(("vcm-32083.vm.duke.edu", 23456))
print("Successfully connected to world as amazon")


AWarehouse = world_amazon_pb2.AInitWarehouse()
AWarehouse.id = 1
AWarehouse.x = 0
AWarehouse.y = 0

AConnectMsg = world_amazon_pb2.AConnect()

AConnectMsg.initwh.append(AWarehouse)
AConnectMsg.isAmazon = True
AConnectMsg

serialized_message = AConnectMsg.SerializeToString()

_EncodeVarint(s.send, len(serialized_message), None)
s.send(serialized_message)
var_int_buff = []
while True:
    buf = s.recv(1)
    var_int_buff += buf
    msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
    if new_pos != 0:
        break
whole_message = s.recv(msg_len)
aconnect_msg = world_amazon_pb2.AConnected()
aconnect_msg.ParseFromString(whole_message)
print(aconnect_msg)


AProductMsg = world_amazon_pb2.AProduct()
AProductMsg.id = 10
AProductMsg.description = "T800"
AProductMsg.count = 12

APurchaseMoreMsg = world_amazon_pb2.APurchaseMore()
APurchaseMoreMsg.whnum = 1
APurchaseMoreMsg.things.append(AProductMsg)
APurchaseMoreMsg.seqnum = 3

ACommandsMsg = world_amazon_pb2.ACommands()
ACommandsMsg.buy.append(APurchaseMoreMsg)
ACommandsMsg.simspeed = 200
ACommandsMsg.disconnect = False
print(ACommandsMsg)


sr = ACommandsMsg.SerializeToString()
dv = _EncodeVarint(s.send, len(sr), None)
s.send(sr)


var_int_buff = []
while True:
    buf = s.recv(1)

    var_int_buff += buf
    msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
    if new_pos != 0:
        break
print(msg_len)
whole_message = s.recv(msg_len)
print(whole_message)


aresponse_msg = world_amazon_pb2.AResponses()
aresponse_msg.ParseFromString(whole_message)
print(aresponse_msg)


ack = list(aresponse_msg.acks)
print(type(ack))
print("ack is:", ack)
ACommandsMsg = world_amazon_pb2.ACommands()
ACommandsMsg.buy.append(APurchaseMoreMsg)
ACommandsMsg.acks.append(ack[0])

print(ACommandsMsg)

sr = ACommandsMsg.SerializeToString()
dv = _EncodeVarint(s.send, len(sr), None)
s.send(sr)

sr = ACommandsMsg.SerializeToString()
dv = _EncodeVarint(s.send, len(sr), None)
s.send(sr)


var_int_buff = []
while True:
    buf = s.recv(1)

    var_int_buff += buf
    msg_len, new_pos = _DecodeVarint32(var_int_buff, 0)
    if new_pos != 0:
        break
print(msg_len)
whole_message = s.recv(msg_len)
print(whole_message)


aresponse_msg = world_amazon_pb2.AResponses()
aresponse_msg.ParseFromString(whole_message)
print(aresponse_msg)


ack = list(aresponse_msg.acks)
print(type(ack))
print("ack is:", ack)
ACommandsMsg = world_amazon_pb2.ACommands()
ACommandsMsg.buy.append(APurchaseMoreMsg)
ACommandsMsg.acks.append(ack[0])

print(ACommandsMsg)

sr = ACommandsMsg.SerializeToString()
dv = _EncodeVarint(s.send, len(sr), None)
s.send(sr)
s.close()

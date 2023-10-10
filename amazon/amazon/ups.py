# interaction with ups

import socket
from threading import Lock

from . import world_amazon_pb2
from . import amazon_ups_pb2
from . import world
from google.protobuf.internal.decoder import _DecodeVarint32
from google.protobuf.internal.encoder import _EncodeVarint
from .utils import send_message, recv_message

import io
from . import db


def connect_new(worldid, socket):
    connect = amazon_ups_pb2.AUConnect()
    connect.worldid = worldid
    send_message(socket, connect)
    message = recv_message(socket)

    uaConnected = amazon_ups_pb2.UAConnected()
    uaConnected.ParseFromString(message)
    return uaConnected


def create_AOrder(id, description, count, x, y, whid):
    aOrder = amazon_ups_pb2.AOrder()
    aOrder.id = id
    aOrder.description = description
    aOrder.count = count
    aOrder.x = x
    aOrder.y = y
    aOrder.whid = whid

    return aOrder


# w/ or w/o user_id
def send_AUorder(rder, shipid):

    plor = amazon_ups_pb2.AUPlaceOrder(order=rder, shipid=shipid, seqnum=db.get_sqn_ups()
    )
    return plor


# w/ user_id

"""
def send_AUorder(Aorder, shipid, user_id):
    aUorder = amazon_ups_pb2.AOrder()
    aUorder.order = Aorder
    aUorder.shipid = shipid
    aUorder.userid = user_id
    aUorder.sqnm = get_sqn()
    return aUorder
"""

# add user_id after placing order


def send_associate_user_id(user_id, shipid):
    AUAssociateUserId = amazon_ups_pb2.AUAssociateUserId()
    AUAssociateUserId.userid = user_id
    AUAssociateUserId.shipid = shipid
    AUAssociateUserId.seqnum = db.get_sqn_ups()
    return AUAssociateUserId


# send to ups to pick up all packages in warehouse


def send_pickup(whid: int, packs: list):
    auCallTruck = amazon_ups_pb2.AUCallTruck()
    auCallTruck.whnum = whid
    for pack in packs:
        auCallTruck.shipid.append(pack)
    auCallTruck.seqnum = db.get_sqn_ups()
    return auCallTruck


# send to UPS truck status


def update_truck_status(truckid: int, status: str):
    auUpdateTruckStatus = amazon_ups_pb2.AUUpdateTruckStatus()
    auUpdateTruckStatus.truckid = truckid
    auUpdateTruckStatus.status = status.upper()
    auUpdateTruckStatus.seqnum = db.get_sqn_ups()
    return auUpdateTruckStatus


def go_deliver(truckid: int, packages: list):
    auTruckGoDeliver = amazon_ups_pb2.AUTruckGoDeliver()
    auTruckGoDeliver.truckid = truckid
    for package in packages:
        auTruckGoDeliver.shipid.append(package)
    auTruckGoDeliver.seqnum = db.get_sqn_ups()
    return auTruckGoDeliver


def create_command(type: list, msgs: list):
    """
    This function should only be called by send_outside in db
    """
    amsgs = amazon_ups_pb2.AUMessages()
    for i in range(len(type)):
        if type[i] == 0:
            amsgs.order.append(msgs[i])
        elif type[i] == 1:
            amsgs.associateUserId.append(msgs[i])
        elif type[i] == 2:
            amsgs.callTruck.append(msgs[i])
        elif type[i] == 3:
            amsgs.updateTruckStatus.append(msgs[i])
        elif type[i] == 4:
            amsgs.truckGoDeliver.append(msgs[i])
        elif type[i] == 5:
            amsgs.error.append(msgs[i])
    return amsgs


# takes in a UACommand object and handles it


def handleUAcommand(msg, socket, lock: Lock):
    # load truck
    for truck in msg.truckArrived:
        if db.seq_ack_ups_record.contains_cmd(truck):
            print("already handled this response")
            continue

        whid = truck.whid
        tid = truck.truckid
        db.load_package(whid, tid, lock=lock)
        # send to world, send back to ups ack

        db.seq_ack_ups_record.seq_add_ack([truck], socket)

    for updatePS in msg.updatePackageStatus:
        if db.seq_ack_ups_record.contains_cmd(updatePS):
            print("already handled this response")
            continue

        # TODO: update package status in db
        shipid = updatePS.shipid
        status = updatePS.status
        db.update_pack_status(shipid=shipid, status=status.lower(), lock=lock)

        db.seq_ack_ups_record.seq_add_ack([updatePS], socket)

    for updatePA in msg.updatePackageAddress:
        if db.seq_ack_ups_record.contains_cmd(updatePA):
            print("already handled this response")
            continue

        # update the package address in db
        shipid = updatePA.shipid
        x = updatePA.x
        y = updatePA.y
        db.update_package_address(shipid=shipid, x=x, y=y, lock = lock)

        db.seq_ack_ups_record.seq_add_ack([updatePA], socket)
    
    for err in msg.error:
        sqnb = err.originseqnum
        print("error from ups! error = ", err)
        ord = db.query_order_by_sqn(sqnb)
        print("error from ups! error = ", err)
        try:
            db.reject_order_upsid(oid=ord.oid, upsid=None, lock=lock)
        except:
            print("This is not an invalid upsid error")
        db.queue_ups_ack.put(sqnb)
        db.seq_ack_ups_record.seq_add_ack([err], socket)

    for ack in msg.acks:
        print("ack from ups! ack = ", ack)
        db.queue_ups_ack.put(ack)

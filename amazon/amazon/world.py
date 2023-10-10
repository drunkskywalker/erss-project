# No stupidness level. No at-least-once semantic.

import socket
from . import world_amazon_pb2
from . import utils



# Creates a warehouse.


def create_warehouse(warehouse_id: int, x: int, y: int):
    aWarehouse = world_amazon_pb2.AInitWarehouse()
    aWarehouse.id = warehouse_id
    aWarehouse.x = x
    aWarehouse.y = y
    return aWarehouse


# Creates a product.


def create_product(id: int, description: str, count: int):
    aProduct = world_amazon_pb2.AProduct()
    aProduct.id = id
    aProduct.description = description
    aProduct.count = count
    return aProduct


# Creates a purchase order.


def create_purchase(whnum: int, things: list, seqnum: int):
    aPurchase = world_amazon_pb2.APurchaseMore()
    aPurchase.whnum = whnum
    for thing in things:
        aPurchase.things.append(thing)
    aPurchase.seqnum = seqnum
    return aPurchase


# Creates a pack order.


def create_pack(whnum: int, things: list, shipid: int, seqnum: int):
    aPack = world_amazon_pb2.APack()
    aPack.whnum = whnum
    for thing in things:
        aPack.things.append(thing)
    aPack.shipid = shipid
    aPack.seqnum = seqnum
    return aPack


# Creates a load truck order.


def create_load(whnum: int, truckid: int, shipid: int, seqnum: int):
    aLoad = world_amazon_pb2.APutOnTruck()
    aLoad.whnum = whnum
    aLoad.truckid = truckid
    aLoad.shipid = shipid
    aLoad.seqnum = seqnum
    return aLoad


# Connects to the world, returns the connected message


def connect_new(socket: socket, warehouses: list):

    aConnect = world_amazon_pb2.AConnect()
    for warehouse in warehouses:
        aConnect.initwh.append(warehouse)
    aConnect.isAmazon = True
    utils.send_message(socket, aConnect)
    message = utils.recv_message(socket)
    aConnected = world_amazon_pb2.AConnected()
    aConnected.ParseFromString(message)
    # print(aConnected)
    return aConnected


# create a ACommands message


def create_command(type: list, message: list):
    assert len(type) == len(message)
    aCommand = world_amazon_pb2.ACommands()
    for i in range(len(type)):
        if type[i] == 0:
            aCommand.buy.append(message[i])
        elif type[i] == 1:
            aCommand.topack.append(message[i])
        elif type[i] == 2:
            aCommand.load.append(message[i])
        elif type[i] == 3:
            aCommand.queries.append(message[i])
        aCommand.disconnect = False
    aCommand.simspeed = 500
    return aCommand

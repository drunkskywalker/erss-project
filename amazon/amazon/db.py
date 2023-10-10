import time
import sqlalchemy
import queue

from datetime import datetime
from threading import Lock

from sqlalchemy import (
    LargeBinary,
    Table,
    create_engine,
    MetaData,
    text,
    Column,
    Integer,
    String,
    Float,
    Sequence,
    ForeignKey,
    inspect,
    CheckConstraint,
)
from sqlalchemy import (
    Enum,
    Float,
    PrimaryKeyConstraint,
    DateTime,
    func,
    UniqueConstraint,
)
from sqlalchemy.engine import URL
from sqlalchemy.orm import relationship, declarative_base, subqueryload, sessionmaker

from . import world
from . import ups
from . import world_amazon_pb2
from . import amazon_ups_pb2

from .utils import (
    send_message,
    recv_message,
    send_ack,
    queue_send_world_add,
    queue_send_ups_add,
    SeqAckRecordBase,
    connect_socket,
)

lock = Lock()

# engine = create_engine(
#     URL.create(
#         username="amazon",
#         password="AlchOfRevo12A2",
#         database="amazon",
#         drivername="postgresql",
#     )
# )
engine = create_engine("postgresql://amazon:AlchOfRevo12A2@postgres:5432/amazon")

Base = declarative_base()

queue_world_send = queue.Queue()
queue_world_ack = queue.Queue()

queue_ups_send = queue.Queue()
queue_ups_ack = queue.Queue()

seq_ack_world_record = SeqAckRecordBase(to_where="world")
seq_ack_ups_record = SeqAckRecordBase(to_where="ups")


sqnb_world = 0
sqnb_ups = 0


def get_sqn_world():
    global sqnb_world
    sqnb_world += 1
    print("now the world sqnb is: ", str(sqnb_world))
    return sqnb_world


def get_sqn_ups():
    global sqnb_ups
    sqnb_ups += 1
    print("now the ups sqnb is: ", str(sqnb_ups))
    return sqnb_ups


class user(Base):
    __tablename__ = "auth_user"
    uid = Column("id", Integer, primary_key=True)
    username = Column("username", String, unique=True)
    email = Column("email", String)


class ups_user(Base):
    __tablename__ = "ups_user"
    uid = Column(Integer, ForeignKey("auth_user.id"), primary_key=True)
    upsid = Column("upsid", String)
    ownedBy = relationship("user", backref="ups_user")


class product(Base):
    __tablename__ = "product"

    pid = Column(
        Integer, Sequence("product_id_seq", start=1, increment=1), primary_key=True
    )
    descrption = Column(String, unique=True)
    icon = Column(LargeBinary)
    type = Column(String, nullable=True)
    detail = Column(String, nullable=True)


class warehouse(Base):
    __tablename__ = "warehouse"

    wid = Column(
        Integer, Sequence("warehouse_id_seq", start=1, increment=1), primary_key=True
    )
    x = Column(Integer)
    y = Column(Integer)


class inventory(Base):
    __tablename__ = "inventory"

    iid = Column(
        Integer, Sequence("inventory_id_seq", start=1, increment=1), primary_key=True
    )
    pid = Column(Integer, ForeignKey("product.pid"))
    wid = Column(Integer, ForeignKey("warehouse.wid"))
    amount = Column(Integer)

    isProduct = relationship("product", backref="inventory")
    storedIn = relationship("warehouse", backref="inventory")

    __table_args__ = (UniqueConstraint(pid, wid),)


class order(Base):
    __tablename__ = "order"

    oid = Column(
        Integer, Sequence("order_id_seq", start=1, increment=1), primary_key=True
    )
    pid = Column(Integer, ForeignKey("product.pid"))
    wid = Column(Integer, ForeignKey("warehouse.wid"))
    tid = Column(Integer)
    uid = Column(Integer, ForeignKey("auth_user.id"))
    amount = Column(Integer, nullable=False)
    status = Column(
        Enum(
            "created",
            "packing",
            "packed",  # packed. when packed packages reachcertain level in a warehouse, send to ups for truck
            "waiting_delivery",
            "loading",
            "loaded",
            "delivering",
            "delivered",
            "canceled",
            "wrong_ups",
            "commented",  # no further modification allowed
            "shipped",
            name="status",
            create_type=False,
        ),
        nullable=False,
    )
    x = Column(Integer)
    y = Column(Integer)
    sqn = Column(Integer)
    upsid = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    rate = Column(Integer, nullable=True)
    isProduct = relationship("product", backref="order")
    packedFrom = relationship("warehouse", backref="order")
    issuedBy = relationship("user", backref="order")


def db_add_product(descrption, path, tag):
    try:
        session = sessionmaker(bind=engine)()
        with open(path, "rb") as f:
            data = f.read()
        # print(data)
        new_product = product(descrption=descrption, icon=data, type = tag)
        session.add(new_product)
        session.commit()
        session.close()
    except sqlalchemy.exc.IntegrityError:
        print("The product already exists")


def query_products():
    session = sessionmaker(bind=engine)()
    products = session.query(product.descrption).all()
    session.close()
    return products


def query_inventory():
    session = sessionmaker(bind=engine)()
    inv = (
        session.query(inventory, warehouse, product).join(warehouse).join(product).all()
    )
    session.close()
    return inv


# w/o communication with world. (only db)

def db_add_inventory_no_comm(description, wid, amount, lock: Lock):
    with lock:
        session = sessionmaker(bind=engine)()
        p = session.query(product).filter(product.descrption == description).first()
        pid = p.pid
        inv = (
            session.query(inventory)
            .filter(inventory.pid == pid)
            .filter(inventory.wid == wid)
            .first()
        )
        if inv == None:
            new_inventory = inventory(pid=pid, wid=wid, amount=amount)
            session.add(new_inventory)
        else:
            inv.amount += amount

        # print(description)
        session.commit()
        session.close()
    return pid


# w/ communication with world.

@DeprecationWarning
def db_add_inventory(description, wid, amount, socket, lock):
    pid = db_add_inventory_no_comm(description, wid, amount, lock)

    inventory_msg = world.create_product(pid, description, amount)
    purchase_msg = world.create_purchase(wid, [inventory_msg], get_sqn_world())
    purchase_command_msg = world.create_command(buy=purchase_msg)
    purchase_return_msg = send_message(socket, purchase_command_msg)
    aresponse_msg = world.world_amazon_pb2.AResponses()
    aresponse_msg.ParseFromString(purchase_return_msg)
    print(aresponse_msg)

    send_ack(socket_world, aresponse_msg.acks, to_where="world")


def restock(pid, wid, amount):
    print("finding product...")
    session = sessionmaker(bind=engine)()
    inv = (
        session.query(inventory, product)
        .join(product)
        .filter(inventory.pid == pid)
        .first()
    )
    desc = inv.product.descrption
    session.commit()
    session.close()
    print("restocking...")
    inventory_msgs = []
    inventory_msgs.append(world.create_product(pid, desc, amount))
    purchase_msg = world.create_purchase(wid, inventory_msgs, get_sqn_world())
    queue_send_world_add(buy=[purchase_msg])

    # db_add_inventory(desc, wid, amount, socket_world)


def db_add_multiple_inventory(descriptions, wid, amount):
    pids = []

    session = sessionmaker(bind=engine)()
    for i in range(len(descriptions)):
        p = session.query(product).filter(product.descrption == descriptions[i]).first()
        pid = p.pid

        pids.append(pid)
    session.commit()
    session.close()

    inventory_msgs = []
    for i in range(len(pids)):
        inventory_msgs.append(world.create_product(pids[i], descriptions[i], amount))

    purchase_msg = world.create_purchase(wid, inventory_msgs, get_sqn_world())
    print("purchase msg: ", purchase_msg)
    queue_send_world_add(buy=[purchase_msg])


def add_warehouse(wid, x, y):
    session = sessionmaker(bind=engine)()
    new_warehouse = warehouse(wid=wid, x=x, y=y)
    session.add(new_warehouse)
    session.commit()
    session.close()

def add_order_w_ups(uid: int, pid: int, amount: int, x: int, y: int, upsid, lock):
    with lock:
        print("adding order")
        session = sessionmaker(bind=engine)()
        inv = session.query(inventory).filter(inventory.pid == pid).first()
        u = session.query(user).get(uid)
        cond = inv.amount >= amount

        if inv.amount >= amount:
            new_order = order(
                uid=u.uid, pid=pid, wid=inv.wid, status="created", amount=amount, x=x, y=y, upsid = upsid, rate = 0
            )
            session.add(new_order)
            oid = new_order.oid
            inv.amount -= amount
            session.commit()
            prod = session.query(product).get(pid)
            session.commit()
            desc = prod.descrption
            wid = inv.wid
            iid = inv.iid
            oid = new_order.oid

            session.commit()
            session.close()
            pack_prod_msg = world.create_product(pid, desc, amount)
            pack_msg = world.create_pack(wid, [pack_prod_msg], oid, get_sqn_world())
            queue_send_world_add(topack=[pack_msg])

            print("putting to queue: ", str(pack_msg.seqnum), str(1), pack_msg)
            neworder = ups.create_AOrder(oid, desc, amount, x, y, wid)
            orderwraper = ups.send_AUorder(neworder, oid)
            queue_send_ups_add(order=[orderwraper])
            

            # send to ups
            # world.send_message(socket_ups, cmd)
            print("complete")
            
        else:
            print("not enough inventory")
            session.rollback()
            session.close()
    if cond:
        update_order_upsid(oid, upsid, lock=lock)
        return True
    else:
        return False


def add_order(uid: int, pid: int, amount: int, x: int, y: int, lock):
    with lock:
        print("adding order")
        session = sessionmaker(bind=engine)()
        inv = session.query(inventory).filter(inventory.pid == pid).first()
        u = session.query(user).get(uid)

        if inv.amount >= amount:
            new_order = order(
                uid=u.uid, pid=pid, wid=inv.wid, status="created", amount=amount, x=x, y=y, rate = 0
            )
            session.add(new_order)
            oid = new_order.oid
            inv.amount -= amount
            session.commit()
            prod = session.query(product).get(pid)
            session.commit()
            desc = prod.descrption
            wid = inv.wid
            iid = inv.iid
            oid = new_order.oid

            session.commit()
            session.close()
            pack_prod_msg = world.create_product(pid, desc, amount)
            pack_msg = world.create_pack(wid, [pack_prod_msg], oid, get_sqn_world())
            queue_send_world_add(topack=[pack_msg])

            print("putting to queue: ", str(pack_msg.seqnum), str(1), pack_msg)
            neworder = ups.create_AOrder(oid, desc, amount, x, y, wid)
            orderwraper = ups.send_AUorder(neworder, oid)
            queue_send_ups_add(order=[orderwraper])

            # send to ups
            # world.send_message(socket_ups, cmd)
            print("complete")
            return True
        else:
            print("not enough inventory")
            session.rollback()
            session.close()
            return False


def query_order_by_sqn(sqn: int):
    session = sessionmaker(bind=engine)()
    ord = session.query(order).filter(order.sqn == sqn).first()
    session.close()
    return ord

def query_order_oid(oid: int):
    session = sessionmaker(bind=engine)()
    ord = session.query(order).get(oid)
    session.close()
    return ord


def query_order(uid: int):
    session = sessionmaker(bind=engine)()
    orders = session.query(order).filter(order.uid == uid).all()
    session.close()
    return orders


def query_order_wid(wid: int, tid: int, status):
    session = sessionmaker(bind=engine)()
    orders = (
        session.query(order)
        .filter(order.wid == wid)
        .filter(order.tid == tid)
        .filter(order.status == status)
        .all()
    )
    session.close()
    return orders


def query_order_detailed(uid: int):
    session = sessionmaker(bind=engine)()
    order_detail = (
        session.query(order, product, warehouse)
        .filter(order.uid == uid)
        .join(product)
        .join(warehouse)
        .all()
    )
    session.close()
    return order_detail


def query_order_same_warehouse_status(shipid, status, lock: Lock):
    with lock:
        session = sessionmaker(bind=engine)()
        ord = (
            session.query(order)
            .filter(order.oid == shipid)
            .first()
        )
        if ord:
            wid = ord.wid
            orders = (
                session.query(order)
                .filter(order.status == status)
                .filter(order.wid == wid)
                .all()
            )
            session.close()
            return orders
    return list()


def db_register_ups(uid, upsid):
    session = sessionmaker(bind=engine)()
    u = ups_user(uid=uid, upsid=upsid)
    session.add(u)
    print("upsid registered: " + str(u.upsid))
    session.commit()
    session.close()


def query_ups(uid):
    session = sessionmaker(bind=engine)()
    u = session.query(ups_user).get(uid)
    session.close()
    return u


def query_comments(pid):
    session = sessionmaker(bind=engine)()
    ord = session.query(order, product).join(product).filter(product.pid == pid).all()
    print("Number of orders: " + str(len(ord)))
    session.close()
    return ord



def mkcomment(oid, rate, comment, lock):
    with lock:
        session = sessionmaker(bind=engine)()
        o = session.query(order).get(oid)
        o.rate = rate
        o.comment = comment
        session.commit()
        session.close()
    update_pack_status(oid, "commented", lock)

def query_all():
    with lock:
        session = sessionmaker(bind=engine)()
        orders = session.query(order).all()
        session.close()
    return orders

def reject_order_upsid(oid, upsid, lock):
    with lock:
        session = sessionmaker(bind=engine)()
        o = session.query(order).get(oid)
        o.upsid = upsid
        session.commit()
        session.close()   

def update_order_upsid(oid, upsid, lock):
    with lock:
        session = sessionmaker(bind=engine)()
        o = session.query(order).get(oid)
        o.upsid = upsid
        session.commit()
        session.close()
    asso = ups.send_associate_user_id(upsid, oid)
    print("registered upsid in db.")
    sqn = asso.seqnum
    with lock:
        session = sessionmaker(bind=engine)()
        o = session.query(order).get(oid)
        o.sqn = sqn
        session.commit()
        session.close()
    queue_send_ups_add(assodiateUserId=[asso])

@DeprecationWarning
def db_modify_ups(uid, upsid):
    session = sessionmaker(bind=engine)()
    u = session.query(ups_user).get(uid)
    u.upsid = upsid
    print("upsid modified: " + str(u.upsid))
    session.commit()
    session.close()


# add list of loadRequests to queue_world_add


def load_package(whid, tid, lock: Lock):
    with lock:
        session = sessionmaker(bind=engine)()
        packed = (
            session.query(order)
            .filter(order.wid == whid)
            .filter(order.status == "waiting_delivery")
            .all()
        )
        for p in packed:
            p.status = "loading"
            p.tid = tid

        loadRequest = []

        # loadCmd = world_amazon_pb2.ACommands()
        for p in packed:
            loadRequest.append(world.create_load(whid, tid, p.oid, get_sqn_world()))
        session.commit()
        session.close()

        # loadCmd.load.append(world.create_load(whid, tid, p.oid, get_sqn_world()))
    queue_send_world_add(load=loadRequest)

    queue_send_ups_add(updateTruckStatus=[ups.update_truck_status(tid, "loading")])


"""
    world.send_message(socket, loadCmd)
"""


def init_db():
    Base.metadata.reflect(bind=engine)

    for table in reversed(Base.metadata.sorted_tables):
        if table.name != "auth_user":
            table.drop(bind=engine, checkfirst=True)
    Base.metadata.create_all(engine, checkfirst=True)


socket_world = connect_socket("vcm-30796.vm.duke.edu", 23456)
socket_ups = connect_socket("vcm-30796.vm.duke.edu", 34567)  # TODO: replace addresses


# socket_ups = ups.ups_socket("0", 23457)


def update_pack_status(shipid, status, lock: Lock):
    with lock:
        session = sessionmaker(bind=engine)()
        pack = session.query(order).get(shipid)
        pack.status = status
        session.commit()
        session.close()


def update_package_address(shipid, x, y, lock):
    with lock:
    #TODO: fix, no package current address in db
        session = sessionmaker(bind=engine)()
        order_to_update = session.query(order).get(shipid)
        
        if order_to_update:
            order_to_update.x = x
            order_to_update.y = y
            session.commit()
            print(f"Updated package address for shipid {shipid} to x: {x}, y: {y}")
        else:
            print(f"No order found with shipid {shipid}")
        
        session.close()
    pass


def handle_response_world(socket, lock: Lock):
    print("handling response...")
    while True:
        try:
            message = recv_message(socket)
            # print("raw", message)
            aResponses = world_amazon_pb2.AResponses()
            aResponses.ParseFromString(message)
            print("decode", aResponses)

            for arrives in aResponses.arrived:
                if seq_ack_world_record.contains_cmd(arrives):
                    print("already handled this response")
                    continue

                whid = arrives.whnum
                for thing in arrives.things:
                    db_add_inventory_no_comm(
                        thing.description, whid, thing.count, lock=lock
                    )
                    print("inventory added: ", whid, thing.id, thing.count)
                seq_ack_world_record.seq_add_ack([arrives], socket=socket)

            for packs in aResponses.ready:
                if seq_ack_world_record.contains_cmd(packs):
                    print("already handled this response")
                    continue
                update_pack_status(packs.shipid, "packed", lock=lock)

                # check number of packed orders in warehouse, if reaches a level, send to UPS
                # for now: one order-> one truck

                #
                # ord = query_order_oid(packs.shipid)
                # pickup = ups.send_pickup(ord.wid, [packs.shipid])

                # attempt: 10 orders-> one truck
                orders_packed = query_order_same_warehouse_status(packs.shipid, "packed", lock)
                orders_deliver = query_order_same_warehouse_status(packs.shipid, "waiting_delivery", lock)
                if len(orders_packed) >= 2:
                    pickup = []
                    oids = []
                    for i in orders_packed:
                        update_pack_status(i.oid, "waiting_delivery", lock=lock)
                        oids.append(i.oid)
                    pickup.append(ups.send_pickup(i.wid, oids))
                    if len(orders_deliver) == 0:
                        queue_send_ups_add(callTruck=pickup)

                print("pack packed: ", packs.shipid)
                seq_ack_world_record.seq_add_ack([packs], socket=socket)

            for ships in aResponses.loaded:
                if seq_ack_world_record.contains_cmd(ships):
                    print("already handled this response")
                    continue

                update_pack_status(ships.shipid, "loaded", lock=lock)
                orders_loading = query_order_same_warehouse_status(
                    ships.shipid, "loading", lock=lock
                )
                orders = []
                orders_loaded = query_order_same_warehouse_status(
                    ships.shipid, "loaded", lock=lock
                )

                orders_all = query_all()
                print("====================")
                for i in orders_all:
                    print("orders_all status = ", i.status)
                print("====================")

                if len(orders_loading) == 0:
                    for i in orders_loaded:
                        update_pack_status(i.oid, "shipped", lock=lock)

                        truckid = i.tid
                        orders.append(i.oid)
                    queue_send_ups_add(
                        updateTruckStatus=[ups.update_truck_status(truckid, "loaded")]
                    )
                    print("====================")
                    print("orders loaded len = ", len(orders_loaded))
                    print("====================")

                    print("====================")
                    print("ships = ", ships)
                    print("====================")
                    queue_send_ups_add(truckGoDeliver=[ups.go_deliver(truckid, orders)])
                print("pack shipped: ", ships.shipid)

                seq_ack_world_record.seq_add_ack([ships], socket=socket)

            for err in aResponses.error:
                if seq_ack_world_record.contains_cmd(err):
                    print("already handled this response")
                    continue

                print("error: ", err.err, err.originseqnum)

                seq_ack_world_record.seq_add_ack([err], socket=socket)

            for query in aResponses.packagestatus:
                if seq_ack_world_record.contains_cmd(query):
                    print("already handled this response")
                    continue

                update_pack_status(query.packageid, query.status, lock=lock)

                seq_ack_world_record.seq_add_ack([query], socket=socket)

            for ack in aResponses.acks:
                print("acking from world: ", ack)
                queue_world_ack.put(ack)
        except Exception as e:
            print("error: ", e)

def handle_response_ups(socket, lock: Lock):
    while True:
        try:
            message = recv_message(socket)
            print(message)
            uaMsg = amazon_ups_pb2.UAMessages()
            uaMsg.ParseFromString(message)
            ups.handleUAcommand(uaMsg, socket, lock=lock)
        except Exception as e:
            print("error: ", e)

# every 1 (?) second, send all unacked messages to world. if acked, remove from unacked.


def send_outside(
    socket, queue_send: queue.Queue, queue_ack: queue.Queue, to_where: str
):
    print("preparing to send to world simulator")
    unackeds = {}
    while True:
        if not queue_send.empty():
            print("receiving message to send")
            while not queue_send.empty():
                key = queue_send.get()
                typ = queue_send.get()
                value = queue_send.get()
                unackeds[key] = [typ, value]
        else:
            time.sleep(1)
        if not queue_ack.empty():
            while not queue_ack.empty():
                ack = queue_ack.get()

                try:
                    unackeds.pop(ack)
                except KeyError:
                    print("key error: ", str(ack), " probably already acked")
        types = []
        msgs = []
        for key, value in unackeds.items():
            types.append(value[0])
            msgs.append(value[1])

        if to_where == "world":
            create_cmd_func = world.create_command
        elif to_where == "ups":
            create_cmd_func = ups.create_command
        else:
            raise ValueError("to_where must be either world or ups")

        cmd = create_cmd_func(types, msgs)

        if len(types) != 0:
            send_message(socket, cmd)
            # print("sending", cmd, "to", to_where)

        if (len(unackeds) != 0):
            print("unackeds: ", len(unackeds))
        time.sleep(1)


# On response ack: send every time a message is received.
# Handle it only on first receiving.
# need to keep track of processed messages.
#


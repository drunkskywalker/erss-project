import sys

from django.apps import AppConfig
import os


class amazonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "amazon"

    def ready(self):
        from . import db
        from . import world
        from . import ups
        from . import world_amazon_pb2
        from . import amazon_ups_pb2
        import threading

        if os.environ.get("RUN_MAIN"):
            print("Already ready")
            return
        else:
            if "migrate" in sys.argv:
                return

            db.init_db()

            warehouse0 = world.create_warehouse(0, 0, 0)
            warehouse1 = world.create_warehouse(1, 10, 10)
            warehouse2 = world.create_warehouse(2, -10, -10)
            db.add_warehouse(0, 0, 0)
            db.add_warehouse(1, 10, 10)
            db.add_warehouse(2, -10, -10)

            # TODO: mechanism to reconnect back to the same world

            world_connected = world.connect_new(
                db.socket_world, [warehouse0, warehouse1, warehouse2]
            )
            wid = world_connected.worldid
            print("wid:", str(wid))
            """ connect to ups
            auc = amazon_ups_pb2.AConnect()
            auc.worldid = wid
            world.send_message(db.socket_ups, auc)
            """

            # connect to ups
            while True:
                uaConnected = ups.connect_new(wid, db.socket_ups)
                if uaConnected.result == "connected!":
                    print("connected to ups")
                    print("ups returned world id:", str(uaConnected.worldid))
                    break

            db.db_add_product("T800", "./amazon/icos/t800.png", "robot")
            db.db_add_product("ppsh41", "./amazon/icos/ppsh41.jpg", "household")
            db.db_add_product("spice", "./amazon/icos/spice.jpg", "food transportation")
            db.db_add_product("apple", "./amazon/icos/apple.png", "food")
            db.db_add_product(
                "Millennium Falcon", "./amazon/icos/MF.jpg", "transportation"
            )
            db.db_add_product("rocc", "./amazon/icos/rock.jpg", "gardening household")
            db.db_add_product("klein bottle", "./amazon/icos/KB.jpg", "household")
            db.db_add_multiple_inventory(
                [
                    "T800",
                    "ppsh41",
                ],
                0,
                200,
                
            )
            db.db_add_multiple_inventory(
                ["apple", "Millennium Falcon", "rocc"], 1, 200
            )
            db.db_add_multiple_inventory(
                ["spice", "klein bottle"], 2, 200
            )

            t = threading.Thread(
                target=db.handle_response_world, args=(db.socket_world, db.lock)
            )
            t.start()

            t2 = threading.Thread(
                target=db.send_outside,
                args=(
                    db.socket_world,
                    db.queue_world_send,
                    db.queue_world_ack,
                    "world",
                ),
            )
            t2.start()

            t3 = threading.Thread(
                target=db.handle_response_ups, args=(db.socket_ups, db.lock)
            )
            t3.start()

            t4 = threading.Thread(
                target=db.send_outside,
                args=(db.socket_ups, db.queue_ups_send, db.queue_ups_ack, "ups"),
            )
            t4.start()

            print("ready")

import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .forms import *
from .db import *
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.core import serializers


def register_request(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Register New Account Successful.")
            return redirect("/")
        return redirect("failed")

    form = RegisterForm()
    return render(request, "amazon/register.html", {"register_form": form})


def success(request):
    return render(request, "amazon/success.html", {"type": "register"})


def failed(request):
    return render(request, "amazon/failed.html", {"type": "register"})


def home(request):
    # form = AuthenticationForm(request, data=request.POST)
    return render(request, "amazon/home.html")


def logout_request(request):
    logout(request)

    messages.success(request, "Logout Successful.")
    return redirect("/")


def login_request(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, "Login Successful.")
                next_url = request.GET.get("next")
                if next_url is not None:
                    return redirect(next_url)
                return redirect("/")
            else:

                return render(request, "amazon/failed.html", {"type": "login"})
    form = AuthenticationForm()
    return render(request, "amazon/login.html", {"login_form": form})


def home(request):
    # print("querying...")
    inv = query_inventory()
    prod = {}
    for i in inv:
        prod[i.product.pid] = []
        if i.product.descrption in prod:

            prod[i.product.pid][0] += i.inventory.amount
        else:
            prod[i.product.pid].append(i.inventory.amount)
        prod[i.product.pid].append(i.product.descrption)
        prod[i.product.pid].append(base64.b64encode(i.product.icon).decode("utf-8"))
        prod[i.product.pid].append(i.product.type)
    # print(prod)

    order = query_order(request.user.id)
    orders = {}
    for i in order[::-1]:
        orders[i.oid] = []
        orders[i.oid].append(i.pid)
        orders[i.oid].append(i.wid)
        orders[i.oid].append(i.amount)
        orders[i.oid].append(i.status)


    u = query_ups(request.user.id)
    if u == None:
        u = "None"
    else:
        u = u.upsid
    return render(
        request, "amazon/home.html", {"products": prod, "orders": orders, "ups": u}
    )


@login_required(login_url=reverse_lazy("login"))
def orders(request):
    order = query_order_detailed(request.user.id)
    orders = {}
    for i in order:
        orders[i.order.oid] = []
        orders[i.order.oid].append(i.product.descrption)
        orders[i.order.oid].append(i.order.wid)
        orders[i.order.oid].append(str(i.warehouse.x) + ", " + str(i.warehouse.y))
        orders[i.order.oid].append(str(i.order.x) + ", " + str(i.order.y))
        orders[i.order.oid].append(i.order.amount)
        orders[i.order.oid].append(i.order.status)
        orders[i.order.oid].append(i.order.upsid)

    return render(
        request,
        "amazon/orders.html",
        {"orders": orders, "allowmodify": ["packing", "packed", "created"]},
    )


"""
@login_required(login_url=reverse_lazy("login"))
def order_modify(request, oid):
    form = ModifyForm()
    ord = query_order_detailed(request.user.id)
    for i in ord:
        if i.order.oid == oid:
            ord = i
            break
    if type(ord) == list or ord.order.oid != oid or ord.order.status not in ["packing","packed", "created"]:
        return HttpResponseForbidden("You cannot modify this order anymore.")
    if request.method == "POST":
        form = ModifyForm(request.POST)
        if form.is_valid():

            x = form.cleaned_data.get("x")
            y = form.cleaned_data.get("y")
            if modify_order(oid, x, y):
                messages.success(request, "Order Modified: " + str(oid))
                return redirect("orders")
            else:
                return render(request, "amazon/failed.html", {"type": "modify order"})

    return render(
        request, "amazon/buy.html", {"buy_form": form, "inv": ord, "type": "modify"}
    )
"""

def restockview(request, pid):
    form = restockform()
    inv = query_inventory()

    for i in inv:
        if i.product.pid == pid:
            inv = i
            break

    if request.method == "POST":
        form = restockform(request.POST)
        if form.is_valid():
            amount = form.cleaned_data.get("amount")
            print("restock amount ", amount)
            restock(inv.product.pid, inv.warehouse.wid, amount)
            messages.success(request, "Inventory Restock ordered: " + str(pid))
            return redirect("/")

    return render(
        request, "amazon/buy.html", {"buy_form": form, "inv": inv, "type": "restock"}
    )

@login_required(login_url=reverse_lazy("login"))
def order_modify(request, oid):
    form = ModifyStatus()
    ord = query_order_detailed(request.user.id)
    for i in ord:
        if i.order.oid == oid:
            ord = i
            break
    if (
        type(ord) == list
        or ord.order.oid != oid
        or ord.order.status not in ["packing", "packed", "created"]
    ):
        return HttpResponseForbidden("You cannot modify this order.")
    if request.method == "POST":
        form = ModifyStatus(request.POST)
        if form.is_valid():

            status = form.cleaned_data.get("status")
            update_pack_status(oid, status, lock)
            messages.success(request, "Order Modified: " + str(oid), status)
            return redirect("/")
    return render(
        request, "amazon/buy.html", {"buy_form": form, "inv": ord, "type": "modify"}
    )


@login_required(login_url=reverse_lazy("login"))
def comment_view(request, oid):
    ord = query_order_detailed(request.user.id)
    form = comment()
    for i in ord:
        if i.order.oid == oid:
            ord = i
            break
    if (
        type(ord) == list
        or ord.order.oid != oid
        or ord.order.status not in ["delivered"]
    ):
        return HttpResponseForbidden("You cannot comment this order yet.")
    if request.method == "POST":
        form = comment(request.POST)
        if form.is_valid():
            rate = form.cleaned_data.get("rate")
            comments = form.cleaned_data.get("comment")
            mkcomment(oid, rate, comments, lock)
            messages.success(request, "Comment Added: " + str(oid), comments)
            return redirect("/")
    return render(request, "amazon/comment.html", {"comment_form": form, "ord": ord})



@login_required(login_url=reverse_lazy("login"))
def register_ups(request, oid):
    form = UPSIdForm()
    u = query_order_oid(oid)
    if request.method == "POST":
        form = UPSIdForm(request.POST)
        if form.is_valid():
            uid = request.user.id
            print("uid", uid)

            update_order_upsid(oid, form.cleaned_data.get("upsid"), lock)
            messages.success(request, "Register UPS id Successful.")
            return redirect("/")

        return redirect("failed")
    return render(request, "amazon/register_ups.html", {"ups_register": form})


# Buy a product.
# Interaction with world: send buy request to world, update db if success, restock if failed;
# Interaction with ups: send pid (and upsid) to ups, update db if success, reject order if upsid does not exist.


@login_required(login_url=reverse_lazy("login"))
def buy(request, pid):
    form = BuyForm()
    inv = query_inventory()

    for i in inv:
        if i.product.pid == pid:
            inv = i
            break

    if request.method == "POST":
        form = BuyForm(request.POST)
        if form.is_valid():
            uid = request.user.id

            amount = form.cleaned_data.get("amount")
            x = form.cleaned_data.get("x")
            y = form.cleaned_data.get("y")
            provideups = form.cleaned_data.get("provideups")
            upsid = form.cleaned_data.get("upsid")
             
            if provideups:
                success = add_order_w_ups(uid, pid, amount, x, y, upsid, lock)
            else: 
                success = add_order(uid, pid, amount, x, y, lock)

            if success:

                # TODO: send buy request to world, update db if success
                #
                messages.success(
                    request,
                    "Purchase Successful: " + str(pid) + " amount: " + str(amount),
                )
                return redirect("/")
            else:
                # TODO: send buy request to world, update db if success in a different thread
                restock(pid, inv.inventory.wid, 200 + amount)
                return render(request, "amazon/failed.html", {"type": "out of stock"})

        return redirect("failed")

    return render(
        request,
        "amazon/buy.html",
        {"buy_form": form, "inv": inv.product.descrption, "type": "new"},
    )


def detail_request(request, pid):
    inv = query_inventory()
    for i in inv:
        if i.product.pid == pid:
            inv = i
            break

    info = []
    info.append(inv.product.pid)
    info.append(inv.product.descrption)
    info.append(inv.inventory.amount)
    info.append(base64.b64encode(inv.product.icon).decode("utf-8"))

    comments = query_comments(pid)

    comm = {}
    sum = 0
    for i in comments:


        if i.order.rate != 0:
            comm[i.order.oid] = []
            comm[i.order.oid].append(i.order.rate)
            comm[i.order.oid].append(i.order.comment)
            sum += i.order.rate
    avg = sum / len(comments) if len(comments) != 0 else 0

    return render(
        request, "amazon/detail.html", {"inv": info, "comments": comm, "avg": avg}
    )

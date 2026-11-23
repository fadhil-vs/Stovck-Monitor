import os
from datetime import date, datetime
from io import BytesIO, StringIO
import csv

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_file
)
from dotenv import load_dotenv
from supabase import create_client, Client
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-12345")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
CURRENCY = os.environ.get("CURRENCY_SYMBOL", "₹")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VALID_STATUSES = {
    "unpaid": "Unpaid",
    "paid": "Paid",
    "other": "Not Dealing"
}

@app.context_processor
def inject_context():
    return {
        "currency": CURRENCY,
        "today_str": date.today().isoformat(),
        "valid_statuses": VALID_STATUSES
    }


def fmt_currency(val):
    try:
        return f"{CURRENCY}{float(val):,.2f}"
    except (TypeError, ValueError):
        return f"{CURRENCY}0.00"

app.jinja_env.filters["currency"] = fmt_currency


def parse_date(date_val):
    if not date_val:
        return date.today()
    if isinstance(date_val, date):
        return date_val
    try:
        return datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()
    except Exception:
        return date.today()


# ==============================================================================
# MAIN PAGE: SALES & TABS (UNPAID, PAID, NOT DEALING, ALL)
# ==============================================================================

@app.route("/")
@app.route("/api/index")
def index():
    tab = request.args.get("tab", "unpaid")  # unpaid | paid | other | all
    search = request.args.get("q", "").strip()

    try:
        query = supabase.table("sales").select("*").order("sale_date", desc=True).order("sl_no", desc=True)
        if tab in VALID_STATUSES:
            query = query.eq("status", tab)

        response = query.execute()
        sales_data = response.data or []
    except Exception as e:
        flash(f"Error fetching sales: {e}", "error")
        sales_data = []

    # Client-side filtering
    if search:
        s_low = search.lower()
        sales_data = [
            s for s in sales_data
            if s_low in str(s.get("customer_name", "")).lower()
            or s_low in str(s.get("bill_no", "")).lower()
            or s_low in str(s.get("product_name", "")).lower()
        ]

    # Calculate days since purchase
    today = date.today()
    enriched_sales = []
    for s in sales_data:
        s_date = parse_date(s.get("sale_date"))
        days_diff = (today - s_date).days
        if days_diff < 0:
            days_label = "Upcoming"
        elif days_diff == 0:
            days_label = "Today"
        elif days_diff == 1:
            days_label = "Yesterday (1 day ago)"
        else:
            days_label = f"{days_diff} days ago"

        s_copy = dict(s)
        s_copy["days_diff"] = days_diff
        s_copy["days_label"] = days_label
        enriched_sales.append(s_copy)

    # Fetch counts & totals for each tab
    unpaid_count = 0
    total_unpaid_amount = 0
    paid_count = 0
    total_paid_amount = 0
    other_count = 0
    total_other_amount = 0

    try:
        all_sales = supabase.table("sales").select("status, amount").execute().data or []
        for item in all_sales:
            st = item.get("status")
            amt = float(item.get("amount", 0))
            if st == "unpaid":
                unpaid_count += 1
                total_unpaid_amount += amt
            elif st == "paid":
                paid_count += 1
                total_paid_amount += amt
            elif st == "other":
                other_count += 1
                total_other_amount += amt
    except Exception:
        pass

    return render_template(
        "index.html",
        sales=enriched_sales,
        active_tab=tab,
        search=search,
        unpaid_count=unpaid_count,
        paid_count=paid_count,
        other_count=other_count,
        total_unpaid_amount=total_unpaid_amount,
        total_paid_amount=total_paid_amount,
        total_other_amount=total_other_amount
    )


# ==============================================================================
# ADD SALE
# ==============================================================================

@app.route("/sales/new", methods=["GET", "POST"])
def add_sale():
    if request.method == "POST":
        sale_date_str = request.form.get("sale_date") or date.today().isoformat()
        sl_no_str     = request.form.get("sl_no", "1").strip()
        bill_no       = request.form.get("bill_no", "").strip()
        customer_name = request.form.get("customer_name", "").strip()
        product_name  = request.form.get("product_name", "").strip()
        qty_str       = request.form.get("qty", "1").strip()
        amount_str    = request.form.get("amount", "0").strip()
        status        = request.form.get("status", "unpaid").strip().lower()

        if status not in VALID_STATUSES:
            status = "unpaid"

        try:
            sl_no = int(sl_no_str)
            qty = int(qty_str)
            amount = float(amount_str)
        except ValueError:
            flash("Invalid numeric value for Sl No, Qty, or Amount.", "error")
            return redirect(url_for("add_sale"))

        if not customer_name or not product_name:
            flash("Customer Name and Product Name are required.", "error")
            return redirect(url_for("add_sale"))

        try:
            # 1. Insert into sales table
            supabase.table("sales").insert({
                "sl_no": sl_no,
                "bill_no": bill_no or f"BILL-{sl_no:04d}",
                "customer_name": customer_name,
                "product_name": product_name,
                "qty": qty,
                "amount": amount,
                "status": status,
                "sale_date": sale_date_str,
            }).execute()

            # 2. Reduce stock if product exists
            stock_res = supabase.table("stock").select("*").ilike("product_name", product_name).execute()
            if stock_res.data:
                item = stock_res.data[0]
                new_qty = max(0, item["quantity"] - qty)
                supabase.table("stock").update({
                    "quantity": new_qty,
                    "updated_at": datetime.now().isoformat()
                }).eq("id", item["id"]).execute()

            flash(f"Sale for {customer_name} ({bill_no}) saved!", "success")
            return redirect(url_for("index", tab=status))
        except Exception as e:
            flash(f"Error saving sale: {e}", "error")
            return redirect(url_for("add_sale"))

    # GET: Prepare default values
    try:
        sales_res = supabase.table("sales").select("sl_no").order("sl_no", desc=True).limit(1).execute()
        last_sl = sales_res.data[0]["sl_no"] if sales_res.data else 0
        next_sl = last_sl + 1
    except Exception:
        next_sl = 1

    next_bill = f"BILL-{next_sl:04d}"

    try:
        stock_items = supabase.table("stock").select("product_name, quantity").order("product_name").execute().data or []
    except Exception:
        stock_items = []

    return render_template(
        "add_sale.html",
        next_sl=next_sl,
        next_bill=next_bill,
        stock_items=stock_items,
        today_date=date.today().isoformat()
    )


# ==============================================================================
# CHANGE SALE STATUS (1-CLICK, UNPAID / PAID / NOT DEALING)
# ==============================================================================

@app.route("/sales/<int:sale_id>/set-status/<new_status>", methods=["POST"])
def set_status(sale_id, new_status):
    if new_status not in VALID_STATUSES:
        flash("Invalid status.", "error")
        return redirect(request.referrer or url_for("index"))

    try:
        supabase.table("sales").update({"status": new_status}).eq("id", sale_id).execute()
        flash(f"Bill status updated to {VALID_STATUSES[new_status]}.", "success")
    except Exception as e:
        flash(f"Error updating status: {e}", "error")

    return redirect(request.referrer or url_for("index"))


@app.route("/sales/<int:sale_id>/toggle-status", methods=["POST"])
def toggle_status(sale_id):
    """Fallback quick toggle"""
    try:
        res = supabase.table("sales").select("status").eq("id", sale_id).single().execute()
        if not res.data:
            return redirect(request.referrer or url_for("index"))
        curr = res.data.get("status", "unpaid")
        new_st = "paid" if curr == "unpaid" else "unpaid"
        supabase.table("sales").update({"status": new_st}).eq("id", sale_id).execute()
        flash(f"Status changed to {VALID_STATUSES.get(new_st, new_st)}.", "success")
    except Exception as e:
        flash(f"Error updating status: {e}", "error")
    return redirect(request.referrer or url_for("index"))


@app.route("/sales/<int:sale_id>/delete", methods=["POST"])
def delete_sale(sale_id):
    try:
        supabase.table("sales").delete().eq("id", sale_id).execute()
        flash("Sale deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting sale: {e}", "error")
    return redirect(request.referrer or url_for("index"))


# ==============================================================================
# STOCK MANAGEMENT & ADDING ORDERS
# ==============================================================================

@app.route("/stock")
def stock_page():
    try:
        stock_list = supabase.table("stock").select("*").order("product_name").execute().data or []
        orders_list = supabase.table("stock_orders").select("*").order("order_date", desc=True).order("id", desc=True).limit(100).execute().data or []
    except Exception as e:
        flash(f"Error loading stock: {e}", "error")
        stock_list, orders_list = [], []

    return render_template(
        "stock.html",
        stock=stock_list,
        orders=orders_list,
        today_date=date.today().isoformat()
    )


@app.route("/stock/add", methods=["POST"])
def add_stock():
    product_name = request.form.get("product_name", "").strip()
    qty_str      = request.form.get("qty", "0").strip()
    order_date   = request.form.get("order_date") or date.today().isoformat()
    note         = request.form.get("note", "").strip()

    if not product_name:
        flash("Product name is required.", "error")
        return redirect(url_for("stock_page"))

    try:
        qty = int(qty_str)
        if qty <= 0:
            flash("Quantity must be greater than zero.", "error")
            return redirect(url_for("stock_page"))
    except ValueError:
        flash("Invalid quantity number.", "error")
        return redirect(url_for("stock_page"))

    try:
        # 1. Record in stock_orders
        supabase.table("stock_orders").insert({
            "order_date": order_date,
            "product_name": product_name,
            "qty_added": qty,
            "note": note or "Stock addition"
        }).execute()

        # 2. Update stock table
        existing = supabase.table("stock").select("*").ilike("product_name", product_name).execute()
        if existing.data:
            item = existing.data[0]
            new_qty = item["quantity"] + qty
            supabase.table("stock").update({
                "quantity": new_qty,
                "updated_at": datetime.now().isoformat()
            }).eq("id", item["id"]).execute()
        else:
            supabase.table("stock").insert({
                "product_name": product_name,
                "quantity": qty,
                "updated_at": datetime.now().isoformat()
            }).execute()

        flash(f"Added {qty} units to {product_name}.", "success")
    except Exception as e:
        flash(f"Error adding stock: {e}", "error")

    return redirect(url_for("stock_page"))


# EDIT STOCK ORDER
@app.route("/stock-order/<int:order_id>/edit", methods=["GET", "POST"])
def edit_stock_order(order_id):
    try:
        order_res = supabase.table("stock_orders").select("*").eq("id", order_id).single().execute()
        order = order_res.data
        if not order:
            flash("Stock order not found.", "error")
            return redirect(url_for("stock_page"))
    except Exception as e:
        flash(f"Error fetching order: {e}", "error")
        return redirect(url_for("stock_page"))

    if request.method == "POST":
        new_product = request.form.get("product_name", "").strip()
        new_qty_str = request.form.get("qty_added", "0").strip()
        new_date    = request.form.get("order_date") or date.today().isoformat()
        new_note    = request.form.get("note", "").strip()

        if not new_product:
            flash("Product name is required.", "error")
            return redirect(url_for("edit_stock_order", order_id=order_id))

        try:
            new_qty = int(new_qty_str)
            if new_qty < 0:
                flash("Quantity cannot be negative.", "error")
                return redirect(url_for("edit_stock_order", order_id=order_id))
        except ValueError:
            flash("Invalid quantity value.", "error")
            return redirect(url_for("edit_stock_order", order_id=order_id))

        try:
            old_product = order.get("product_name")
            old_qty     = int(order.get("qty_added", 0))

            # Adjust stock levels accordingly
            if old_product.lower() == new_product.lower():
                qty_diff = new_qty - old_qty
                if qty_diff != 0:
                    st_res = supabase.table("stock").select("*").ilike("product_name", new_product).execute()
                    if st_res.data:
                        st_item = st_res.data[0]
                        updated_stock = max(0, st_item["quantity"] + qty_diff)
                        supabase.table("stock").update({
                            "quantity": updated_stock,
                            "updated_at": datetime.now().isoformat()
                        }).eq("id", st_item["id"]).execute()
            else:
                # Deduct old product qty
                old_st_res = supabase.table("stock").select("*").ilike("product_name", old_product).execute()
                if old_st_res.data:
                    old_item = old_st_res.data[0]
                    supabase.table("stock").update({
                        "quantity": max(0, old_item["quantity"] - old_qty),
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", old_item["id"]).execute()

                # Add to new product qty
                new_st_res = supabase.table("stock").select("*").ilike("product_name", new_product).execute()
                if new_st_res.data:
                    new_item = new_st_res.data[0]
                    supabase.table("stock").update({
                        "quantity": new_item["quantity"] + new_qty,
                        "updated_at": datetime.now().isoformat()
                    }).eq("id", new_item["id"]).execute()
                else:
                    supabase.table("stock").insert({
                        "product_name": new_product,
                        "quantity": new_qty,
                        "updated_at": datetime.now().isoformat()
                    }).execute()

            # Update order row
            supabase.table("stock_orders").update({
                "order_date": new_date,
                "product_name": new_product,
                "qty_added": new_qty,
                "note": new_note
            }).eq("id", order_id).execute()

            flash("Stock order updated successfully!", "success")
            return redirect(url_for("stock_page"))
        except Exception as e:
            flash(f"Error updating stock order: {e}", "error")
            return redirect(url_for("edit_stock_order", order_id=order_id))

    return render_template("edit_stock_order.html", order=order)


# DELETE STOCK ORDER
@app.route("/stock-order/<int:order_id>/delete", methods=["POST"])
def delete_stock_order(order_id):
    try:
        order_res = supabase.table("stock_orders").select("*").eq("id", order_id).single().execute()
        if not order_res.data:
            flash("Stock order not found.", "error")
            return redirect(url_for("stock_page"))

        order = order_res.data
        prod_name = order.get("product_name")
        qty_to_revert = int(order.get("qty_added", 0))

        # Revert stock quantity
        stock_res = supabase.table("stock").select("*").ilike("product_name", prod_name).execute()
        if stock_res.data:
            item = stock_res.data[0]
            new_qty = max(0, item["quantity"] - qty_to_revert)
            supabase.table("stock").update({
                "quantity": new_qty,
                "updated_at": datetime.now().isoformat()
            }).eq("id", item["id"]).execute()

        # Delete order
        supabase.table("stock_orders").delete().eq("id", order_id).execute()
        flash(f"Order for {prod_name} deleted and stock adjusted.", "success")
    except Exception as e:
        flash(f"Error deleting stock order: {e}", "error")

    return redirect(url_for("stock_page"))


# ==============================================================================
# EXPORTS (EXCEL & CSV)
# ==============================================================================

@app.route("/export/sales")
def export_sales():
    tab = request.args.get("status", "all")
    fmt = request.args.get("format", "xlsx")

    try:
        query = supabase.table("sales").select("*").order("sale_date", desc=True).order("sl_no", desc=True)
        if tab in VALID_STATUSES:
            query = query.eq("status", tab)
        sales = query.execute().data or []
    except Exception as e:
        flash(f"Export error: {e}", "error")
        return redirect(url_for("index"))

    today = date.today()
    headers = ["Sl No", "Bill No", "Date", "Customer Name", "Product Name", "Qty", "Amount", "Status", "Days Ago"]

    rows = []
    for s in sales:
        s_date = parse_date(s.get("sale_date"))
        days_ago = (today - s_date).days
        st_label = VALID_STATUSES.get(s.get("status", ""), s.get("status", "")).upper()
        rows.append([
            s.get("sl_no"),
            s.get("bill_no"),
            str(s_date),
            s.get("customer_name"),
            s.get("product_name"),
            s.get("qty"),
            float(s.get("amount", 0)),
            st_label,
            days_ago
        ])

    filename_base = f"sales_{tab}_{today.isoformat()}"

    if fmt == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{filename_base}.csv"
        )

    # Excel export
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"
    ws.append(headers)

    for r in rows:
        ws.append(r)

    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        max_len = max((len(str(r[0].value or "")) for r in ws.iter_rows(min_col=col, max_col=col)), default=10)
        ws.column_dimensions[letter].width = max(max_len + 4, 12)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"{filename_base}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/export/stock-orders")
def export_stock_orders():
    fmt = request.args.get("format", "xlsx")
    try:
        orders = supabase.table("stock_orders").select("*").order("order_date", desc=True).execute().data or []
    except Exception as e:
        flash(f"Export error: {e}", "error")
        return redirect(url_for("stock_page"))

    today = date.today()
    headers = ["Order Date", "Product Name", "Qty Added", "Note", "Logged At"]
    rows = [
        [o.get("order_date"), o.get("product_name"), o.get("qty_added"), o.get("note", ""), str(o.get("created_at"))[:19]]
        for o in orders
    ]

    filename_base = f"stock_orders_{today.isoformat()}"

    if fmt == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"{filename_base}.csv"
        )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stock Additions"
    ws.append(headers)
    for r in rows:
        ws.append(r)

    header_fill = PatternFill("solid", fgColor="059669")
    header_font = Font(bold=True, color="FFFFFF")
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for col in range(1, len(headers) + 1):
        letter = get_column_letter(col)
        max_len = max((len(str(r[0].value or "")) for r in ws.iter_rows(min_col=col, max_col=col)), default=10)
        ws.column_dimensions[letter].width = max(max_len + 4, 12)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"{filename_base}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)

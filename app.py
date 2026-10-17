import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import io
from openpyxl import load_workbook



DB_NAME = "drug_inventory.db"

# -----------------------------
# Database
# -----------------------------
def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            quantity REAL NOT NULL DEFAULT 0,
            min_quantity REAL NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_id INTEGER NOT NULL,
            operation TEXT NOT NULL,
            amount REAL NOT NULL,
            quantity_after REAL NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (drug_id) REFERENCES drugs(id)
        )
    """)

    conn.commit()
    conn.close()

def get_drugs():
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, quantity, min_quantity FROM drugs ORDER BY name",
        conn
    )
    conn.close()
    return df

def add_drug(name, quantity, min_quantity):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO drugs (name, quantity, min_quantity) VALUES (?, ?, ?)",
            (name, quantity, min_quantity)
        )
        conn.commit()
        return True, "دارو با موفقیت اضافه شد."
    except sqlite3.IntegrityError:
        return False, "این دارو قبلاً ثبت شده است."
    finally:
        conn.close()

def update_inventory(drug_id, operation, amount):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT quantity FROM drugs WHERE id = ?", (drug_id,))
    row = cur.fetchone()

    if row is None:
        conn.close()
        return False, "دارو پیدا نشد."

    current = float(row[0])

    if operation == "ورود":
        new_quantity = current + amount
    else:
        if amount > current:
            conn.close()
            return False, f"موجودی کافی نیست. موجودی فعلی: {current:g}"
        new_quantity = current - amount

    cur.execute(
        "UPDATE drugs SET quantity = ? WHERE id = ?",
        (new_quantity, drug_id)
    )

    cur.execute("""
        INSERT INTO transactions
        (drug_id, operation, amount, quantity_after, date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        drug_id,
        operation,
        amount,
        new_quantity,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return True, f"عملیات با موفقیت ثبت شد. موجودی جدید: {new_quantity:g}"

def get_transactions():
    conn = get_connection()
    df = pd.read_sql_query("""
        SELECT
            t.id,
            d.name AS دارو,
            t.operation AS عملیات,
            t.amount AS مقدار,
            t.quantity_after AS موجودی_بعد_از_عملیات,
            t.date AS تاریخ
        FROM transactions t
        JOIN drugs d ON d.id = t.drug_id
        ORDER BY t.id DESC
    """, conn)
    conn.close()
    return df


# -----------------------------
# App
# -----------------------------
st.set_page_config(
    page_title="مدیریت موجودی دارو",
    page_icon="💊",
    layout="wide"
)

init_db()

st.title("💊 مدیریت موجودی دارو")
st.caption("ثبت ورود، خروج و مشاهده موجودی داروها")

# Sidebar
page = st.sidebar.radio(
    "انتخاب بخش",
    [
        "داشبورد",
        "موجودی داروها",
        "ثبت ورود / خروج",
        "افزودن دارو",
        "گزارش تراکنش‌ها"
    ]
)


# -----------------------------
# Dashboard
# -----------------------------
if page == "داشبورد":
    
    
    
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(120deg, #123b45, #218b80);
            padding: 28px;
            border-radius: 18px;
            color: white;
            margin-bottom: 25px;
            direction: rtl;
            text-align: right;
            box-shadow: 0 6px 20px rgba(18,59,69,0.15);
        ">
            <h1 style="color: white !important; margin: 0;">
                💊 سامانه مدیریت دارو
            </h1>
            <p style="font-size: 16px; margin: 10px 0 0 0;">
                داشبورد هوشمند کنترل موجودی و بررسی تراکنش‌ها
            </p>
            <p style="font-size: 13px; margin: 12px 0 0 0; opacity: 0.9;">
                تاریخ امروز: {datetime.now().strftime("%Y/%m/%d")}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )


    # دریافت اطلاعات از دیتابیس
    drugs = get_drugs()
    transactions = get_transactions()

    # محاسبه آمار
    total_drugs = len(drugs)

    if not drugs.empty:
        low_stock = drugs[
            drugs["quantity"] <= drugs["min_quantity"]
        ]
        total_quantity = drugs["quantity"].sum()
    else:
        low_stock = drugs.copy()
        total_quantity = 0

    total_transactions = len(transactions)

    # کارت‌های آماری
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "💊 تعداد داروها",
        f"{total_drugs:,}"
    )

    col2.metric(
        "⚠️ داروهای کم‌موجود",
        f"{len(low_stock):,}"
    )

    col3.metric(
        "📦 مجموع موجودی",
        f"{total_quantity:g}"
    )

    col4.metric(
        "🔄 تعداد تراکنش‌ها",
        f"{total_transactions:,}"
    )

    st.divider()

    # نمودار ورود و خروج
    st.subheader("📈 مقایسه ورود و خروج")

    if transactions.empty:
        st.info("هنوز تراکنشی ثبت نشده است.")
    else:
        operation_counts = (
            transactions["عملیات"]
            .value_counts()
            .reindex(["ورود", "خروج"], fill_value=0)
        )

        chart_data = operation_counts.rename(
            "تعداد تراکنش"
        )

        st.bar_chart(chart_data)

    st.divider()

    # نمایش داروهای کم‌موجود
    st.subheader("⚠️ داروهای نیازمند تأمین موجودی")

    if low_stock.empty:
        st.success("در حال حاضر داروی کم‌موجودی وجود ندارد.")
    else:
        low_stock_display = low_stock.rename(
            columns={
                "name": "نام دارو",
                "quantity": "موجودی فعلی",
                "min_quantity": "حداقل موجودی"
            }
        )

        st.dataframe(
            low_stock_display[
                ["نام دارو", "موجودی فعلی", "حداقل موجودی"]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # آخرین تراکنش‌ها
    st.subheader("🕒 آخرین تراکنش‌ها")

    if transactions.empty:
        st.info("تراکنشی برای نمایش وجود ندارد.")
    else:
        st.dataframe(
            transactions.head(5),
            use_container_width=True,
            hide_index=True
        )

# -----------------------------
# Inventory
# -----------------------------
elif page == "موجودی داروها":
    st.subheader("📦 موجودی فعلی")

    drugs = get_drugs()

    if drugs.empty:
        st.info("هنوز دارویی ثبت نشده است. از بخش «افزودن دارو» شروع کنید.")
    else:

        # -----------------------------
        # Search & Filter
        # -----------------------------
        col1, col2 = st.columns([2, 1])

        with col1:
            search_name = st.text_input(
                "🔎 جست‌وجوی دارو",
                placeholder="نام دارو را وارد کنید..."
            )

        with col2:
            stock_filter = st.selectbox(
                "📋 فیلتر موجودی",
                ["همه داروها", "فقط موجودی کم"]
            )

        # -----------------------------
        # Warning for low stock
        # -----------------------------
        low_stock = drugs[
            drugs["quantity"] <= drugs["min_quantity"]
        ]

        if not low_stock.empty:
            st.warning(
                "⚠️ موجودی این داروها به حداقل تعیین‌شده رسیده یا کمتر شده است: "
                + "، ".join(low_stock["name"].tolist())
            )

        # -----------------------------
        # Apply search
        # -----------------------------
        filtered_drugs = drugs.copy()

        if search_name:
            filtered_drugs = filtered_drugs[
                filtered_drugs["name"].str.contains(
                    search_name,
                    case=False,
                    na=False
                )
            ]

        # -----------------------------
        # Apply stock filter
        # -----------------------------
        if stock_filter == "فقط موجودی کم":
            filtered_drugs = filtered_drugs[
                filtered_drugs["quantity"] <=
                filtered_drugs["min_quantity"]
            ]

        # -----------------------------
        # Result
        # -----------------------------
        st.caption(
            f"تعداد داروهای نمایش‌داده‌شده: {len(filtered_drugs)}"
        )

        if filtered_drugs.empty:
            st.info("دارویی با این مشخصات پیدا نشد.")
        else:
            display = filtered_drugs.rename(columns={
                "name": "نام دارو",
                "quantity": "موجودی",
                "min_quantity": "حداقل موجودی"
            })

            st.dataframe(
                display[
                    ["نام دارو", "موجودی", "حداقل موجودی"]
                ],
                use_container_width=True,
                hide_index=True
            )
# -----------------------------
# Transaction
# -----------------------------
elif page == "ثبت ورود / خروج":
    st.subheader("📥📤 ثبت ورود یا خروج دارو")

    drugs = get_drugs()

    if drugs.empty:
        st.info("ابتدا حداقل یک دارو اضافه کنید.")
    else:
        selected_name = st.selectbox("دارو", drugs["name"].tolist())
        selected = drugs[drugs["name"] == selected_name].iloc[0]

        st.info(f"موجودی فعلی «{selected_name}»: {selected['quantity']:g}")

        operation = st.radio(
            "نوع عملیات",
            ["ورود", "خروج"],
            horizontal=True
        )

        amount = st.number_input(
            "مقدار",
            min_value=0.01,
            value=1.0,
            step=1.0
        )

        if st.button("ثبت عملیات", type="primary"):
            ok, message = update_inventory(
                int(selected["id"]),
                operation,
                amount
            )

            if ok:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

# -----------------------------
# Add drug
# -----------------------------
elif page == "افزودن دارو":
    st.subheader("➕ افزودن داروی جدید")

    with st.form("add_drug_form"):
        name = st.text_input("نام دارو")
        quantity = st.number_input(
            "موجودی اولیه",
            min_value=0.0,
            value=0.0,
            step=1.0
        )
        min_quantity = st.number_input(
            "حداقل موجودی برای هشدار",
            min_value=0.0,
            value=10.0,
            step=1.0
        )

        submitted = st.form_submit_button(
            "افزودن دارو",
            type="primary"
        )

    if submitted:
        name = name.strip()

        if not name:
            st.error("نام دارو را وارد کنید.")
        else:
            ok, message = add_drug(
                name,
                quantity,
                min_quantity
            )

            if ok:
                st.success(message)
            else:
                st.error(message)

# -----------------------------
# Reports
# -----------------------------
# -----------------------------
# Reports
# -----------------------------
elif page == "گزارش تراکنش‌ها":
    st.subheader("📊 گزارش ورود و خروج")

    transactions = get_transactions()
    drugs = get_drugs()

    if transactions.empty:
        st.info("هنوز هیچ تراکنشی ثبت نشده است.")
    else:
        st.dataframe(
            transactions,
            use_container_width=True,
            hide_index=True
        )

        # -----------------------------
        # Create Excel file
        # -----------------------------
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:

            # Sheet 1: Inventory
            inventory_export = drugs.rename(columns={
                "id": "شناسه",
                "name": "نام دارو",
                "quantity": "موجودی",
                "min_quantity": "حداقل موجودی"
            })

            inventory_export[
                ["شناسه", "نام دارو", "موجودی", "حداقل موجودی"]
            ].to_excel(
                writer,
                index=False,
                sheet_name="موجودی داروها"
            )

            # Sheet 2: Transactions
            transactions.to_excel(
                writer,
                index=False,
                sheet_name="گزارش تراکنش‌ها"
            )

        # -----------------------------
        # Format Excel
        # -----------------------------
        output.seek(0)

        workbook = load_workbook(output)

        # Format Inventory Sheet
        inventory_sheet = workbook["موجودی داروها"]

        inventory_sheet.column_dimensions["A"].width = 12
        inventory_sheet.column_dimensions["B"].width = 25
        inventory_sheet.column_dimensions["C"].width = 15
        inventory_sheet.column_dimensions["D"].width = 20

        # Format Transactions Sheet
        transaction_sheet = workbook["گزارش تراکنش‌ها"]

        for column in transaction_sheet.columns:
            max_length = 0
            column_letter = column[0].column_letter

            for cell in column:
                if cell.value is not None:
                    max_length = max(
                        max_length,
                        len(str(cell.value))
                    )

            transaction_sheet.column_dimensions[
                column_letter
            ].width = min(max_length + 3, 30)

        # Save formatted Excel to memory
        final_output = io.BytesIO()
        workbook.save(final_output)
        final_output.seek(0)

        # -----------------------------
        # Download Excel
        # -----------------------------
        st.download_button(
            "⬇️ دانلود فایل Excel",
            data=final_output,
            file_name="drug_inventory.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
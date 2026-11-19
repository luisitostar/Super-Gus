import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
from datetime import datetime
import uuid
import os
import html

DB_NAME = "super_gus.db"
STOCK_MAXIMO_BAJO = 5

st.set_page_config(
    page_title="Súper Gus | Sistema de Gestión",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- BASE DE DATOS --------------------
def conectar():
    return sqlite3.connect(DB_NAME, timeout=10)

def init_db():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                categoria TEXT,
                stock INTEGER NOT NULL DEFAULT 0,
                precio_compra REAL NOT NULL DEFAULT 0,
                precio_venta REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL,
                producto_id INTEGER,
                producto TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                precio_unitario REAL NOT NULL,
                total REAL NOT NULL
            )
        """)
        # Columnas adicionales para conectar ventas con clientes y créditos.
        columnas = [fila[1] for fila in conn.execute("PRAGMA table_info(ventas)").fetchall()]
        if "tipo_pago" not in columnas:
            conn.execute("ALTER TABLE ventas ADD COLUMN tipo_pago TEXT NOT NULL DEFAULT 'Efectivo'")
        if "cliente_id" not in columnas:
            conn.execute("ALTER TABLE ventas ADD COLUMN cliente_id INTEGER")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clientes_credito (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT DEFAULT '',
                direccion TEXT DEFAULT '',
                limite_credito REAL NOT NULL DEFAULT 0,
                activo INTEGER NOT NULL DEFAULT 1,
                fecha_registro TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_credito (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                monto REAL NOT NULL,
                fecha TEXT NOT NULL,
                venta_id TEXT,
                FOREIGN KEY(cliente_id) REFERENCES clientes_credito(id)
            )
        """)
        conn.commit()

def consultar(sql, parametros=()):
    with conectar() as conn:
        return pd.read_sql_query(sql, conn, params=parametros)

def ejecutar(sql, parametros=()):
    with conectar() as conn:
        cur = conn.execute(sql, parametros)
        conn.commit()
        return cur.lastrowid

def dinero(valor):
    return f"${float(valor or 0):,.2f}"

def saldo_cliente(cliente_id):
    df = consultar(
        """SELECT COALESCE(SUM(
            CASE WHEN tipo='COMPRA' THEN monto
                 WHEN tipo='ABONO' THEN -monto
                 ELSE 0 END
        ),0) AS saldo
        FROM movimientos_credito WHERE cliente_id=?""",
        (cliente_id,)
    )
    return float(df.iloc[0]["saldo"] or 0)

def datos_cliente(cliente_id):
    df = consultar("SELECT * FROM clientes_credito WHERE id=?", (cliente_id,))
    return None if df.empty else df.iloc[0].to_dict()

def registrar_movimiento(cliente_id, tipo, descripcion, monto, venta_id=None):
    ejecutar(
        """INSERT INTO movimientos_credito
        (cliente_id, tipo, descripcion, monto, fecha, venta_id)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (cliente_id, tipo, descripcion, float(monto),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), venta_id)
    )

init_db()

# -------------------- ESTILO --------------------
st.markdown("""
<style>
    .stApp { background-color: #f5f8f6; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg,#087443,#064e32); }
    [data-testid="stSidebar"] * { color: white !important; }
    h1, h2, h3 { color: #087443; }
    div[data-testid="stMetric"] {
        background: white; border: 1px solid #dce9e0;
        padding: 14px; border-radius: 12px;
    }
    .bloque-info {
        background: white; padding: 16px; border-radius: 12px;
        border: 1px solid #dce9e0; margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

st.sidebar.markdown("# 🛒 SÚPER GUS")
st.sidebar.caption("Sistema de gestión empresarial")

menu = [
    "🏠 Inicio",
    "🛒 Nueva Venta",
    "📦 Productos",
    "➕ Agregar Producto",
    "💳 Créditos",
    "📊 Ingresos",
    "📜 Historial de Ventas",
    "💾 Respaldo"
]
opcion = st.sidebar.radio("MENÚ PRINCIPAL", menu)

# -------------------- FUNCIONES DE CRÉDITO --------------------
def tabla_clientes_con_saldos(solo_activos=False):
    filtro = "WHERE activo=1" if solo_activos else ""
    clientes = consultar(f"SELECT * FROM clientes_credito {filtro} ORDER BY nombre")
    if clientes.empty:
        return clientes
    saldos = []
    disponibles = []
    for _, c in clientes.iterrows():
        saldo = saldo_cliente(int(c["id"]))
        saldos.append(saldo)
        disponibles.append(float(c["limite_credito"]) - saldo)
    clientes["deuda_actual"] = saldos
    clientes["credito_disponible"] = disponibles
    return clientes

# -------------------- INICIO --------------------
if opcion == "🏠 Inicio":
    st.title("🏠 Panel principal")
    st.write("Bienvenido a **Súper Gus**, tu sistema de inventario, ventas y control de créditos.")
    productos = consultar("SELECT * FROM productos")
    ventas_hoy = consultar(
        "SELECT COALESCE(SUM(total),0) AS total FROM ventas WHERE fecha=?",
        (datetime.now().strftime("%Y-%m-%d"),)
    )
    ingresos = consultar("SELECT COALESCE(SUM(total),0) AS total FROM ventas")
    clientes = tabla_clientes_con_saldos()
    deuda_total = float(clientes["deuda_actual"].sum()) if not clientes.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos registrados", len(productos))
    c2.metric("Unidades en inventario", int(productos["stock"].sum()) if not productos.empty else 0)
    c3.metric("Ingresos por ventas", dinero(ingresos.iloc[0]["total"]))
    c4.metric("Ventas de hoy", dinero(ventas_hoy.iloc[0]["total"]))
    st.divider()
    c5, c6 = st.columns(2)
    c5.metric("Clientes con crédito", len(clientes))
    c6.metric("Saldo pendiente total", dinero(deuda_total))
    if not productos.empty:
        bajos = productos[productos["stock"] <= STOCK_MAXIMO_BAJO]
        st.subheader("⚠️ Alertas de inventario")
        if bajos.empty:
            st.success("Todos los productos tienen existencias suficientes.")
        else:
            st.dataframe(bajos[["nombre", "categoria", "stock", "precio_venta"]], use_container_width=True, hide_index=True)
    else:
        st.info("Todavía no hay productos. Ve a “Agregar Producto” para comenzar.")

# -------------------- NUEVA VENTA --------------------
elif opcion == "🛒 Nueva Venta":
    st.title("🛒 Nueva venta")
    productos = consultar("SELECT * FROM productos WHERE stock > 0 ORDER BY nombre")
    if productos.empty:
        st.warning("No hay productos con existencias disponibles. Agrega productos al inventario.")
    else:
        if "carrito" not in st.session_state:
            st.session_state.carrito = []

        st.subheader("1. Agregar productos")
        opciones = {
            f'{r["nombre"]} | Stock: {int(r["stock"])} | {dinero(r["precio_venta"])}': r
            for _, r in productos.iterrows()
        }
        seleccion = st.selectbox("Producto", list(opciones.keys()))
        producto = opciones[seleccion]
        col1, col2 = st.columns([1, 2])
        with col1:
            cantidad = st.number_input(
                "Cantidad", min_value=1, max_value=int(producto["stock"]),
                value=1, step=1, key="cantidad_venta"
            )
        with col2:
            st.write(f"**Precio unitario:** {dinero(producto['precio_venta'])}")
            st.write(f"**Subtotal:** {dinero(float(producto['precio_venta']) * int(cantidad))}")
        if st.button("➕ Agregar al carrito", use_container_width=True):
            encontrado = False
            for item in st.session_state.carrito:
                if item["id"] == int(producto["id"]):
                    nueva_cantidad = item["cantidad"] + int(cantidad)
                    if nueva_cantidad > int(producto["stock"]):
                        st.error("La cantidad del carrito supera el stock disponible.")
                    else:
                        item["cantidad"] = nueva_cantidad
                        item["subtotal"] = item["cantidad"] * item["precio"]
                        st.success("Cantidad actualizada en el carrito.")
                    encontrado = True
                    break
            if not encontrado:
                st.session_state.carrito.append({
                    "id": int(producto["id"]), "nombre": producto["nombre"],
                    "cantidad": int(cantidad), "precio": float(producto["precio_venta"]),
                    "subtotal": int(cantidad) * float(producto["precio_venta"])
                })
                st.success("Producto agregado.")
            st.rerun()

        st.subheader("2. Carrito")
        if not st.session_state.carrito:
            st.info("Agrega al menos un producto para continuar.")
        else:
            carrito_df = pd.DataFrame(st.session_state.carrito)
            st.dataframe(
                carrito_df.rename(columns={
                    "nombre": "Producto", "cantidad": "Cantidad",
                    "precio": "Precio unitario", "subtotal": "Subtotal"
                })[["Producto", "Cantidad", "Precio unitario", "Subtotal"]],
                use_container_width=True, hide_index=True
            )
            total = sum(item["subtotal"] for item in st.session_state.carrito)
            st.subheader(f"Total: {dinero(total)}")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🗑️ Vaciar carrito", use_container_width=True):
                    st.session_state.carrito = []
                    st.rerun()
            st.subheader("3. Forma de pago")
            tipo_pago = st.radio("Selecciona cómo pagará el cliente", ["Efectivo", "Crédito"], horizontal=True)
            cliente_id = None
            cliente_seleccionado = None
            if tipo_pago == "Crédito":
                clientes_activos = consultar(
                    "SELECT id, nombre, telefono, limite_credito FROM clientes_credito WHERE activo=1 ORDER BY nombre"
                )
                if clientes_activos.empty:
                    st.warning("No hay clientes activos. Registra uno primero en la sección Créditos.")
                else:
                    etiquetas = {}
                    for _, c in clientes_activos.iterrows():
                        saldo = saldo_cliente(int(c["id"]))
                        disponible = float(c["limite_credito"]) - saldo
                        etiquetas[f'{c["nombre"]} | Disponible: {dinero(disponible)}'] = int(c["id"])
                    etiqueta = st.selectbox("Cliente que comprará a crédito", list(etiquetas.keys()))
                    cliente_id = etiquetas[etiqueta]
                    cliente_seleccionado = datos_cliente(cliente_id)
                    saldo = saldo_cliente(cliente_id)
                    disponible = float(cliente_seleccionado["limite_credito"]) - saldo
                    st.info(f"Deuda actual: {dinero(saldo)} · Crédito disponible: {dinero(disponible)}")
                    if total > disponible:
                        st.error("El total supera el crédito disponible de este cliente.")
            confirmar_deshabilitado = (
                tipo_pago == "Crédito" and (
                    cliente_id is None or
                    total > (float(cliente_seleccionado["limite_credito"]) - saldo_cliente(cliente_id))
                )
            )
            with col_b:
                confirmar = st.button(
                    "✅ Finalizar venta", use_container_width=True,
                    disabled=confirmar_deshabilitado
                )
            if confirmar:
                ahora = datetime.now()
                venta_id = "VG-" + uuid.uuid4().hex[:8].upper()
                try:
                    with conectar() as conn:
                        # Validar y actualizar el stock dentro de una misma transacción.
                        for item in st.session_state.carrito:
                            cur = conn.execute(
                                "UPDATE productos SET stock=stock-? WHERE id=? AND stock>=?",
                                (item["cantidad"], item["id"], item["cantidad"])
                            )
                            if cur.rowcount != 1:
                                raise ValueError(f"No hay stock suficiente para {item['nombre']}.")
                        for item in st.session_state.carrito:
                            conn.execute("""
                                INSERT INTO ventas
                                (venta_id, fecha, hora, producto_id, producto, cantidad,
                                 precio_unitario, total, tipo_pago, cliente_id)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                venta_id, ahora.strftime("%Y-%m-%d"), ahora.strftime("%H:%M:%S"),
                                item["id"], item["nombre"], item["cantidad"], item["precio"],
                                item["subtotal"], tipo_pago, cliente_id
                            ))
                        if tipo_pago == "Crédito":
                            conn.execute("""
                                INSERT INTO movimientos_credito
                                (cliente_id, tipo, descripcion, monto, fecha, venta_id)
                                VALUES (?, 'COMPRA', ?, ?, ?, ?)
                            """, (
                                cliente_id, f"Venta a crédito {venta_id}", total,
                                ahora.strftime("%Y-%m-%d %H:%M:%S"), venta_id
                            ))
                        conn.commit()
                    st.session_state.carrito = []
                    st.success(f"Venta {venta_id} registrada correctamente.")
                    st.markdown("### 🧾 Ticket de venta")
                    if tipo_pago == "Crédito" and cliente_seleccionado:
                        nombre_cliente_ticket = str(cliente_seleccionado["nombre"])
                    else:
                        nombre_cliente_ticket = "Público general"

                    filas_ticket = ""
                    for item_ticket in carrito_df.to_dict("records"):
                        filas_ticket += (
                            "<tr>"
                            f"<td>{html.escape(str(item_ticket['nombre']))}</td>"
                            f"<td style='text-align:center'>{int(item_ticket['cantidad'])}</td>"
                            f"<td style='text-align:right'>{dinero(item_ticket['precio'])}</td>"
                            f"<td style='text-align:right'>{dinero(item_ticket['subtotal'])}</td>"
                            "</tr>"
                        )

                    ticket_html = f"""
                    <!DOCTYPE html>
                    <html lang="es">
                    <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: Arial, sans-serif; color: #222; padding: 12px; }}
                        .ticket {{ max-width: 440px; margin: auto; border: 1px solid #ddd;
                                   border-radius: 10px; padding: 18px; background: #fff; }}
                        h2 {{ text-align: center; margin: 0 0 4px; color: #087443; }}
                        .sub {{ text-align: center; font-size: 12px; margin-bottom: 16px; }}
                        .datos {{ font-size: 13px; line-height: 1.7; }}
                        table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 12px; }}
                        th, td {{ border-bottom: 1px solid #ddd; padding: 7px 3px; }}
                        th {{ text-align: left; background: #f0f7f2; }}
                        .total {{ text-align: right; font-size: 20px; font-weight: bold; margin-top: 16px; }}
                        .gracias {{ text-align: center; margin-top: 20px; font-size: 12px; }}
                        .print-btn {{ display: block; width: 100%; margin: 16px auto 0; padding: 11px;
                                      border: 0; border-radius: 7px; background: #087443; color: white;
                                      font-size: 15px; cursor: pointer; }}
                        @media print {{
                            body {{ padding: 0; }}
                            .ticket {{ border: 0; border-radius: 0; padding: 0; }}
                            .print-btn {{ display: none !important; }}
                        }}
                    </style>
                    </head>
                    <body>
                      <div class="ticket">
                        <h2>SÚPER GUS</h2>
                        <div class="sub">Comprobante de venta</div>
                        <div class="datos">
                          <b>Folio:</b> {html.escape(venta_id)}<br>
                          <b>Fecha:</b> {ahora.strftime('%d/%m/%Y %H:%M:%S')}<br>
                          <b>Forma de pago:</b> {html.escape(tipo_pago)}<br>
                          <b>Cliente:</b> {html.escape(nombre_cliente_ticket)}
                        </div>
                        <table>
                          <thead><tr><th>Producto</th><th>Cant.</th><th>Precio</th><th>Importe</th></tr></thead>
                          <tbody>{filas_ticket}</tbody>
                        </table>
                        <div class="total">TOTAL: {dinero(total)}</div>
                        <div class="gracias">¡Gracias por tu compra!</div>
                        <button class="print-btn" onclick="window.print()">🖨️ Imprimir ticket / Guardar PDF</button>
                      </div>
                    </body>
                    </html>
                    """
                    components.html(ticket_html, height=620, scrolling=True)
                    st.caption("Para imprimir, pulsa el botón verde dentro del ticket. En el cuadro del navegador podrás elegir una impresora o “Guardar como PDF”.")
                    if tipo_pago == "Crédito":
                        st.warning("La venta quedó registrada como deuda del cliente.")
                    if any(int(consultar("SELECT stock FROM productos WHERE id=?", (i["id"],)).iloc[0]["stock"]) <= STOCK_MAXIMO_BAJO for i in carrito_df.to_dict("records")):
                        st.warning("Atención: uno o más productos quedaron con stock bajo.")
                except Exception as e:
                    st.error(f"No se pudo registrar la venta: {e}")

# -------------------- PRODUCTOS --------------------
elif opcion == "📦 Productos":
    st.title("📦 Inventario de productos")
    df = consultar("SELECT id, nombre, categoria, stock, precio_compra, precio_venta FROM productos ORDER BY nombre")
    if df.empty:
        st.info("No hay productos registrados.")
    else:
        df["estado"] = df["stock"].apply(
            lambda x: "🔴 AGOTADO" if x == 0 else ("🟠 STOCK BAJO" if x <= STOCK_MAXIMO_BAJO else "🟢 DISPONIBLE")
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.subheader("Editar producto")
        producto_id = st.selectbox("Selecciona el ID del producto", df["id"].tolist())
        seleccionado = df[df["id"] == producto_id].iloc[0]
        with st.form("editar_producto"):
            nombre = st.text_input("Nombre", str(seleccionado["nombre"]))
            categoria = st.text_input("Categoría", str(seleccionado["categoria"] or ""))
            stock = st.number_input("Stock", min_value=0, value=int(seleccionado["stock"]), step=1)
            compra = st.number_input("Precio de compra", min_value=0.0, value=float(seleccionado["precio_compra"]), step=0.5)
            venta = st.number_input("Precio de venta", min_value=0.0, value=float(seleccionado["precio_venta"]), step=0.5)
            guardar = st.form_submit_button("Guardar cambios")
        if guardar:
            if not nombre.strip():
                st.error("El nombre no puede quedar vacío.")
            else:
                ejecutar(
                    "UPDATE productos SET nombre=?, categoria=?, stock=?, precio_compra=?, precio_venta=? WHERE id=?",
                    (nombre.strip(), categoria.strip(), int(stock), float(compra), float(venta), int(producto_id))
                )
                st.success("Producto actualizado.")
                st.rerun()
        with st.expander("Eliminar producto"):
            st.warning("Eliminar un producto no elimina las ventas históricas asociadas.")
            if st.button("Eliminar producto seleccionado", type="secondary"):
                ejecutar("DELETE FROM productos WHERE id=?", (int(producto_id),))
                st.success("Producto eliminado.")
                st.rerun()

# -------------------- AGREGAR PRODUCTO --------------------
elif opcion == "➕ Agregar Producto":
    st.title("➕ Agregar producto")
    with st.form("nuevo_producto", clear_on_submit=True):
        nombre = st.text_input("Nombre del producto *")
        categoria = st.text_input("Categoría")
        col1, col2, col3 = st.columns(3)
        with col1:
            stock = st.number_input("Stock inicial", min_value=0, value=0, step=1)
        with col2:
            compra = st.number_input("Precio de compra ($)", min_value=0.0, value=0.0, step=0.5)
        with col3:
            venta = st.number_input("Precio de venta ($)", min_value=0.0, value=0.0, step=0.5)
        guardar = st.form_submit_button("Guardar producto")
    if guardar:
        if not nombre.strip():
            st.error("Escribe el nombre del producto.")
        else:
            ejecutar(
                "INSERT INTO productos (nombre, categoria, stock, precio_compra, precio_venta) VALUES (?, ?, ?, ?, ?)",
                (nombre.strip(), categoria.strip(), int(stock), float(compra), float(venta))
            )
            st.success(f"Producto “{nombre.strip()}” agregado correctamente.")

# -------------------- CRÉDITOS --------------------
elif opcion == "💳 Créditos":
    st.title("💳 Control de créditos")
    st.caption("Registra clientes, autoriza límites, registra ventas a crédito y controla los abonos.")

    with st.expander("➕ Registrar cliente", expanded=False):
        with st.form("registrar_cliente", clear_on_submit=True):
            nombre_c = st.text_input("Nombre completo *")
            telefono_c = st.text_input("Teléfono")
            direccion_c = st.text_input("Dirección")
            limite_c = st.number_input("Límite de crédito ($)", min_value=0.0, value=500.0, step=50.0)
            activo_c = st.checkbox("Cliente activo", value=True)
            guardar_c = st.form_submit_button("Registrar cliente")
        if guardar_c:
            if not nombre_c.strip():
                st.error("El nombre del cliente es obligatorio.")
            else:
                ejecutar("""
                    INSERT INTO clientes_credito
                    (nombre, telefono, direccion, limite_credito, activo, fecha_registro)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    nombre_c.strip(), telefono_c.strip(), direccion_c.strip(), float(limite_c),
                    1 if activo_c else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
                st.success("Cliente registrado correctamente.")
                st.rerun()

    clientes = tabla_clientes_con_saldos()
    deuda_total = float(clientes["deuda_actual"].sum()) if not clientes.empty else 0
    limite_total = float(clientes["limite_credito"].sum()) if not clientes.empty else 0
    disponible_total = limite_total - deuda_total
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Clientes registrados", len(clientes))
    m2.metric("Deuda total", dinero(deuda_total))
    m3.metric("Límites autorizados", dinero(limite_total))
    m4.metric("Crédito disponible total", dinero(disponible_total))

    if clientes.empty:
        st.info("Registra un cliente para comenzar a usar el control de créditos.")
    else:
        st.subheader("Estado de clientes")
        vista = clientes[["id", "nombre", "telefono", "limite_credito", "deuda_actual", "credito_disponible", "activo"]].copy()
        vista["estado"] = vista["activo"].map({1: "Activo", 0: "Inactivo"})
        st.dataframe(vista, use_container_width=True, hide_index=True)

        st.subheader("Administrar cliente")
        opciones_c = {f'{r["nombre"]} (ID {int(r["id"])})': int(r["id"]) for _, r in clientes.iterrows()}
        etiqueta_c = st.selectbox("Selecciona un cliente", list(opciones_c.keys()))
        cid = opciones_c[etiqueta_c]
        cliente = datos_cliente(cid)
        saldo = saldo_cliente(cid)
        disponible = float(cliente["limite_credito"]) - saldo

        a, b, c = st.columns(3)
        a.metric("Límite de crédito", dinero(cliente["limite_credito"]))
        b.metric("Deuda actual", dinero(saldo))
        c.metric("Disponible", dinero(disponible))
        st.write(f"**Teléfono:** {cliente['telefono'] or 'No registrado'}")
        st.write(f"**Dirección:** {cliente['direccion'] or 'No registrada'}")

        with st.form("editar_cliente"):
            nuevo_limite = st.number_input(
                "Cambiar límite de crédito ($)", min_value=0.0,
                value=float(cliente["limite_credito"]), step=50.0
            )
            cliente_activo = st.checkbox("Cuenta activa", value=bool(cliente["activo"]))
            guardar_cliente = st.form_submit_button("Guardar configuración")
        if guardar_cliente:
            if nuevo_limite < saldo:
                st.error("El límite no puede ser menor que la deuda actual.")
            else:
                ejecutar(
                    "UPDATE clientes_credito SET limite_credito=?, activo=? WHERE id=?",
                    (float(nuevo_limite), 1 if cliente_activo else 0, cid)
                )
                st.success("Configuración del cliente actualizada.")
                st.rerun()

        st.divider()
        compra_tab, abono_tab = st.tabs(["🧾 Registrar cargo manual", "💵 Registrar abono"])
        with compra_tab:
            st.caption("Usa esta opción para agregar un cargo que no provenga de una venta del carrito. Para ventas normales, utiliza Nueva Venta y elige Crédito.")
            with st.form("cargo_manual"):
                descripcion_cargo = st.text_input("Descripción del cargo")
                monto_cargo = st.number_input("Monto ($)", min_value=0.0, value=0.0, step=10.0)
                registrar_cargo = st.form_submit_button("Registrar cargo")
            if registrar_cargo:
                if not cliente["activo"]:
                    st.error("La cuenta está inactiva.")
                elif monto_cargo <= 0:
                    st.error("El monto debe ser mayor que cero.")
                elif monto_cargo > disponible:
                    st.error("El cargo supera el crédito disponible.")
                else:
                    registrar_movimiento(cid, "COMPRA", descripcion_cargo.strip() or "Cargo manual", monto_cargo)
                    st.success("Cargo registrado.")
                    st.rerun()

        with abono_tab:
            with st.form("registrar_abono"):
                monto_abono = st.number_input("Monto del abono ($)", min_value=0.0, value=0.0, step=10.0)
                descripcion_abono = st.text_input("Nota del abono", value="Abono del cliente")
                registrar_abono = st.form_submit_button("Guardar abono")
            if registrar_abono:
                if monto_abono <= 0:
                    st.error("El abono debe ser mayor que cero.")
                elif saldo <= 0:
                    st.error("Este cliente no tiene deuda pendiente.")
                elif monto_abono > saldo:
                    st.error(f"El abono no puede superar la deuda actual de {dinero(saldo)}.")
                else:
                    registrar_movimiento(cid, "ABONO", descripcion_abono.strip() or "Abono del cliente", monto_abono)
                    st.success(f"Abono registrado. Nueva deuda: {dinero(saldo - monto_abono)}")
                    st.rerun()

        st.subheader("Historial de movimientos del cliente")
        movs = consultar("""
            SELECT fecha AS Fecha, tipo AS Tipo, descripcion AS Descripción,
                   monto AS Monto, venta_id AS Folio
            FROM movimientos_credito WHERE cliente_id=?
            ORDER BY id DESC
        """, (cid,))
        if movs.empty:
            st.info("Este cliente todavía no tiene movimientos.")
        else:
            st.dataframe(movs, use_container_width=True, hide_index=True)

# -------------------- INGRESOS --------------------
elif opcion == "📊 Ingresos":
    st.title("📊 Ingresos por ventas")
    ventas = consultar("SELECT fecha, total, tipo_pago FROM ventas ORDER BY fecha")
    if ventas.empty:
        st.info("Todavía no hay ventas registradas.")
    else:
        ventas["fecha"] = pd.to_datetime(ventas["fecha"], errors="coerce")
        ventas = ventas.dropna(subset=["fecha"])
        por_dia = ventas.groupby(ventas["fecha"].dt.strftime("%Y-%m-%d"), as_index=False)["total"].sum()
        por_dia = por_dia.rename(columns={"fecha": "Fecha", "total": "Ingresos"})
        st.metric("Total vendido", dinero(ventas["total"].sum()))
        st.line_chart(por_dia.set_index("fecha") if "fecha" in por_dia.columns else por_dia.set_index(por_dia.columns[0]))
        por_pago = ventas.groupby("tipo_pago", as_index=False)["total"].sum()
        por_pago.columns = ["Forma de pago", "Total"]
        st.subheader("Ventas por forma de pago")
        st.dataframe(por_pago, use_container_width=True, hide_index=True)

# -------------------- HISTORIAL --------------------
elif opcion == "📜 Historial de Ventas":
    st.title("📜 Historial de ventas")
    historial = consultar("""
        SELECT v.venta_id AS Folio, v.fecha AS Fecha, v.hora AS Hora,
               v.producto AS Producto, v.cantidad AS Cantidad,
               v.precio_unitario AS Precio, v.total AS Total,
               COALESCE(v.tipo_pago, 'Efectivo') AS 'Forma de pago',
               COALESCE(c.nombre, '') AS Cliente
        FROM ventas v
        LEFT JOIN clientes_credito c ON c.id=v.cliente_id
        ORDER BY v.id DESC
    """)
    if historial.empty:
        st.info("No hay ventas registradas.")
    else:
        st.dataframe(historial, use_container_width=True, hide_index=True)
        csv = historial.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Descargar historial CSV", csv, "historial_ventas_super_gus.csv", "text/csv")

# -------------------- RESPALDO --------------------
elif opcion == "💾 Respaldo":
    st.title("💾 Respaldo de la base de datos")
    st.write("Descarga una copia de la base de datos que contiene productos, ventas, clientes y movimientos de crédito.")
    if os.path.exists(DB_NAME):
        with open(DB_NAME, "rb") as archivo:
            st.download_button(
                "⬇️ Descargar respaldo de Súper Gus",
                data=archivo.read(),
                file_name=f"respaldo_super_gus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                mime="application/octet-stream"
            )
    st.divider()
    st.subheader("Restaurar respaldo")
    archivo_db = st.file_uploader("Selecciona un archivo de respaldo .db", type=["db"])
    if archivo_db is not None:
        st.warning("Restaurar reemplazará la base de datos actual. Descarga primero un respaldo por seguridad.")
        confirmar = st.checkbox("Confirmo que quiero reemplazar la base de datos actual.")
        if st.button("Restaurar base de datos", disabled=not confirmar):
            try:
                with open(DB_NAME, "wb") as destino:
                    destino.write(archivo_db.getvalue())
                init_db()
                st.success("Respaldo restaurado. Recarga la aplicación.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo restaurar el respaldo: {e}")

st.sidebar.divider()
st.sidebar.caption("Súper Gus · Inventario, ventas y créditos")
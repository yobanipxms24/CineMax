from datetime import datetime, timedelta
import uuid

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import or_

from config import Config
from extensions import db
from models.usuario import Usuario
from models.categoria import Categoria
from models.pelicula import Pelicula
from models.serie import Serie


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Duración de la sesión por inactividad.
TIEMPO_SESION_MINUTOS = 2


@app.before_request
def validar_sesion_y_token():
    """
    Se ejecuta antes de cada petición protegida.

    Si el usuario está autenticado:
    1. Comprueba que el token exista en la base de datos.
    2. Comprueba que coincida con el token de la sesión.
    3. Comprueba que no haya expirado.
    4. Renueva la expiración cuando el usuario navega.
    """
    rutas_publicas = {"index", "login", "static"}

    if request.endpoint in rutas_publicas or request.endpoint is None:
        return None

    usuario_id = session.get("usuario_id")
    token_sesion = session.get("token")

    if not usuario_id or not token_sesion:
        session.clear()
        flash("Debes iniciar sesión para acceder.", "warning")
        return redirect(url_for("login"))

    usuario = db.session.get(Usuario, usuario_id)

    if not usuario:
        session.clear()
        flash("El usuario ya no existe.", "danger")
        return redirect(url_for("login"))

    if not usuario.estado:
        session.clear()
        flash("Tu cuenta está desactivada.", "danger")
        return redirect(url_for("login"))

    if usuario.token != token_sesion:
        session.clear()
        flash("El token de la sesión no es válido.", "danger")
        return redirect(url_for("login"))

    ahora = datetime.now()

    if not usuario.token_expira or ahora > usuario.token_expira:
        usuario.token = None
        usuario.token_expira = None
        db.session.commit()

        session.clear()
        flash(
            "Tu sesión expiró por inactividad. Inicia sesión nuevamente.",
            "warning",
        )
        return redirect(url_for("login"))

    # Renovar el tiempo mientras el usuario siga navegando.
    usuario.token_expira = ahora + timedelta(minutes=TIEMPO_SESION_MINUTOS)
    session["ultima_actividad"] = ahora.isoformat()
    db.session.commit()

    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        usuario_form = request.form.get("usuario", "").strip()
        password_form = request.form.get("password", "").strip()

        usuario_encontrado = Usuario.query.filter_by(
            usuario=usuario_form,
            estado=True,
        ).first()

        if (
            usuario_encontrado
            and usuario_encontrado.password == password_form
        ):
            token = str(uuid.uuid4())
            expiracion = datetime.now() + timedelta(
                minutes=TIEMPO_SESION_MINUTOS
            )

            usuario_encontrado.token = token
            usuario_encontrado.token_expira = expiracion
            db.session.commit()

            session.clear()
            session["usuario_id"] = usuario_encontrado.id
            session["usuario_nombre"] = usuario_encontrado.nombre
            session["usuario_rol"] = usuario_encontrado.rol
            session["token"] = token
            session["ultima_actividad"] = datetime.now().isoformat()

            flash(
                f"Bienvenido, {usuario_encontrado.nombre}.",
                "success",
            )
            return redirect(url_for("dashboard"))

        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    usuario = db.session.get(Usuario, session.get("usuario_id"))

    total_usuarios = Usuario.query.count()
    total_peliculas = Pelicula.query.count()
    total_series = Serie.query.count()
    total_categorias = Categoria.query.count()

    ultimas_peliculas = (
        Pelicula.query
        .order_by(Pelicula.id.desc())
        .limit(5)
        .all()
    )

    ultimas_series = (
        Serie.query
        .order_by(Serie.id.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard.html",
        nombre=usuario.nombre,
        rol=usuario.rol,
        token=usuario.token,
        token_expira=usuario.token_expira,
        total_usuarios=total_usuarios,
        total_peliculas=total_peliculas,
        total_series=total_series,
        total_categorias=total_categorias,
        ultimas_peliculas=ultimas_peliculas,
        ultimas_series=ultimas_series,
    )


@app.route("/logout")
def logout():
    usuario_id = session.get("usuario_id")

    if usuario_id:
        usuario = db.session.get(Usuario, usuario_id)

        if usuario:
            usuario.token = None
            usuario.token_expira = None
            db.session.commit()

    session.clear()
    flash("Sesión cerrada correctamente.", "success")

    return redirect(url_for("login"))


@app.route("/usuarios")
def usuarios():
    texto_busqueda = request.args.get("buscar", "").strip()
    consulta = Usuario.query

    if texto_busqueda:
        patron = f"%{texto_busqueda}%"
        consulta = consulta.filter(
            or_(
                Usuario.nombre.like(patron),
                Usuario.usuario.like(patron),
                Usuario.correo.like(patron),
                Usuario.rol.like(patron),
            )
        )

    lista_usuarios = consulta.order_by(Usuario.id.desc()).all()

    return render_template(
        "usuarios.html",
        usuarios=lista_usuarios,
        buscar=texto_busqueda,
    )


@app.route("/usuarios/nuevo", methods=["POST"])
def crear_usuario():
    nombre = request.form.get("nombre", "").strip()
    nombre_usuario = request.form.get("usuario", "").strip()
    correo = request.form.get("correo", "").strip().lower()
    password = request.form.get("clave_nueva", "").strip()
    rol = request.form.get("rol", "Usuario").strip()

    if not nombre or not nombre_usuario or not correo or not password:
        flash(
            "Todos los campos obligatorios deben completarse.",
            "danger",
        )
        return redirect(url_for("usuarios"))

    usuario_existente = Usuario.query.filter(
        or_(
            Usuario.usuario == nombre_usuario,
            Usuario.correo == correo,
        )
    ).first()

    if usuario_existente:
        flash(
            "El nombre de usuario o el correo ya están registrados.",
            "warning",
        )
        return redirect(url_for("usuarios"))

    if rol not in {"Administrador", "Usuario"}:
        rol = "Usuario"

    nuevo_usuario = Usuario(
        nombre=nombre,
        usuario=nombre_usuario,
        correo=correo,
        password=password,
        rol=rol,
        estado=True,
    )

    db.session.add(nuevo_usuario)
    db.session.commit()

    flash("Usuario agregado correctamente.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/editar/<int:usuario_id>", methods=["POST"])
def editar_usuario(usuario_id):
    usuario_editar = db.session.get(Usuario, usuario_id)

    if not usuario_editar:
        flash("El usuario solicitado no existe.", "danger")
        return redirect(url_for("usuarios"))

    nombre = request.form.get("nombre", "").strip()
    nombre_usuario = request.form.get("usuario", "").strip()
    correo = request.form.get("correo", "").strip().lower()
    password = request.form.get("clave_nueva", "").strip()
    rol = request.form.get("rol", "Usuario").strip()

    if not nombre or not nombre_usuario or not correo:
        flash("Nombre, usuario y correo son obligatorios.", "danger")
        return redirect(url_for("usuarios"))

    duplicado = Usuario.query.filter(
        Usuario.id != usuario_id,
        or_(
            Usuario.usuario == nombre_usuario,
            Usuario.correo == correo,
        ),
    ).first()

    if duplicado:
        flash(
            "El usuario o correo ya pertenecen a otra cuenta.",
            "warning",
        )
        return redirect(url_for("usuarios"))

    usuario_editar.nombre = nombre
    usuario_editar.usuario = nombre_usuario
    usuario_editar.correo = correo
    usuario_editar.rol = (
        rol if rol in {"Administrador", "Usuario"} else "Usuario"
    )

    if password:
        usuario_editar.password = password

    db.session.commit()

    if usuario_editar.id == session.get("usuario_id"):
        session["usuario_nombre"] = usuario_editar.nombre
        session["usuario_rol"] = usuario_editar.rol

    flash("Usuario actualizado correctamente.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/estado/<int:usuario_id>", methods=["POST"])
def cambiar_estado_usuario(usuario_id):
    usuario_estado = db.session.get(Usuario, usuario_id)

    if not usuario_estado:
        flash("El usuario solicitado no existe.", "danger")
        return redirect(url_for("usuarios"))

    if usuario_estado.id == session.get("usuario_id"):
        flash("No puedes desactivar tu propia cuenta.", "warning")
        return redirect(url_for("usuarios"))

    usuario_estado.estado = not usuario_estado.estado

    if not usuario_estado.estado:
        usuario_estado.token = None
        usuario_estado.token_expira = None

    db.session.commit()

    mensaje = "activado" if usuario_estado.estado else "desactivado"
    flash(f"Usuario {mensaje} correctamente.", "success")

    return redirect(url_for("usuarios"))


@app.route("/usuarios/eliminar/<int:usuario_id>", methods=["POST"])
def eliminar_usuario(usuario_id):
    usuario_eliminar = db.session.get(Usuario, usuario_id)

    if not usuario_eliminar:
        flash("El usuario solicitado no existe.", "danger")
        return redirect(url_for("usuarios"))

    if usuario_eliminar.id == session.get("usuario_id"):
        flash("No puedes eliminar tu propia cuenta.", "warning")
        return redirect(url_for("usuarios"))

    db.session.delete(usuario_eliminar)
    db.session.commit()

    flash("Usuario eliminado correctamente.", "success")
    return redirect(url_for("usuarios"))

@app.route("/categorias")
def categorias():
    texto_busqueda = request.args.get("buscar", "").strip()

    consulta = Categoria.query

    if texto_busqueda:
        patron = f"%{texto_busqueda}%"
        consulta = consulta.filter(Categoria.nombre.like(patron))

    lista_categorias = consulta.order_by(Categoria.id.desc()).all()

    return render_template(
        "categorias.html",
        categorias=lista_categorias,
        buscar=texto_busqueda,
    )


@app.route("/categorias/nueva", methods=["POST"])
def crear_categoria():
    nombre = request.form.get("nombre", "").strip()

    if not nombre:
        flash("El nombre de la categoría es obligatorio.", "danger")
        return redirect(url_for("categorias"))

    categoria_existente = Categoria.query.filter(
        db.func.lower(Categoria.nombre) == nombre.lower()
    ).first()

    if categoria_existente:
        flash("Esa categoría ya existe.", "warning")
        return redirect(url_for("categorias"))

    nueva_categoria = Categoria(
        nombre=nombre,
        estado=True,
    )

    db.session.add(nueva_categoria)
    db.session.commit()

    flash("Categoría agregada correctamente.", "success")
    return redirect(url_for("categorias"))


@app.route("/categorias/editar/<int:categoria_id>", methods=["POST"])
def editar_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)

    if not categoria:
        flash("La categoría solicitada no existe.", "danger")
        return redirect(url_for("categorias"))

    nombre = request.form.get("nombre", "").strip()

    if not nombre:
        flash("El nombre de la categoría es obligatorio.", "danger")
        return redirect(url_for("categorias"))

    duplicada = Categoria.query.filter(
        Categoria.id != categoria_id,
        db.func.lower(Categoria.nombre) == nombre.lower(),
    ).first()

    if duplicada:
        flash("Ya existe otra categoría con ese nombre.", "warning")
        return redirect(url_for("categorias"))

    categoria.nombre = nombre
    db.session.commit()

    flash("Categoría actualizada correctamente.", "success")
    return redirect(url_for("categorias"))


@app.route("/categorias/estado/<int:categoria_id>", methods=["POST"])
def cambiar_estado_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)

    if not categoria:
        flash("La categoría solicitada no existe.", "danger")
        return redirect(url_for("categorias"))

    categoria.estado = not categoria.estado
    db.session.commit()

    mensaje = "activada" if categoria.estado else "desactivada"
    flash(f"Categoría {mensaje} correctamente.", "success")

    return redirect(url_for("categorias"))


@app.route("/categorias/eliminar/<int:categoria_id>", methods=["POST"])
def eliminar_categoria(categoria_id):
    categoria = db.session.get(Categoria, categoria_id)

    if not categoria:
        flash("La categoría solicitada no existe.", "danger")
        return redirect(url_for("categorias"))

    db.session.delete(categoria)
    db.session.commit()

    flash("Categoría eliminada correctamente.", "success")
    return redirect(url_for("categorias"))


@app.route("/peliculas")
def peliculas():
    texto_busqueda = request.args.get("buscar", "").strip()

    consulta = Pelicula.query.join(Categoria)

    if texto_busqueda:
        patron = f"%{texto_busqueda}%"
        consulta = consulta.filter(
            or_(
                Pelicula.nombre.like(patron),
                Categoria.nombre.like(patron),
            )
        )

    lista_peliculas = consulta.order_by(Pelicula.id.desc()).all()
    lista_categorias = Categoria.query.filter_by(
        estado=True
    ).order_by(Categoria.nombre.asc()).all()

    return render_template(
        "peliculas.html",
        peliculas=lista_peliculas,
        categorias=lista_categorias,
        buscar=texto_busqueda,
    )


@app.route("/peliculas/nueva", methods=["POST"])
def crear_pelicula():
    nombre = request.form.get("nombre", "").strip()
    duracion = request.form.get("duracion", type=int)
    categoria_id = request.form.get("categoria_id", type=int)

    if not nombre or not duracion or not categoria_id:
        flash(
            "El nombre, la duración y la categoría son obligatorios.",
            "danger",
        )
        return redirect(url_for("peliculas"))

    if duracion <= 0:
        flash("La duración debe ser mayor que cero.", "warning")
        return redirect(url_for("peliculas"))

    categoria = db.session.get(Categoria, categoria_id)

    if not categoria or not categoria.estado:
        flash("La categoría seleccionada no es válida.", "warning")
        return redirect(url_for("peliculas"))

    nueva_pelicula = Pelicula(
        nombre=nombre,
        duracion=duracion,
        categoria_id=categoria_id,
    )

    db.session.add(nueva_pelicula)
    db.session.commit()

    flash("Película agregada correctamente.", "success")
    return redirect(url_for("peliculas"))


@app.route("/peliculas/editar/<int:pelicula_id>", methods=["POST"])
def editar_pelicula(pelicula_id):
    pelicula = db.session.get(Pelicula, pelicula_id)

    if not pelicula:
        flash("La película solicitada no existe.", "danger")
        return redirect(url_for("peliculas"))

    nombre = request.form.get("nombre", "").strip()
    duracion = request.form.get("duracion", type=int)
    categoria_id = request.form.get("categoria_id", type=int)

    if not nombre or not duracion or not categoria_id:
        flash(
            "El nombre, la duración y la categoría son obligatorios.",
            "danger",
        )
        return redirect(url_for("peliculas"))

    if duracion <= 0:
        flash("La duración debe ser mayor que cero.", "warning")
        return redirect(url_for("peliculas"))

    categoria = db.session.get(Categoria, categoria_id)

    if not categoria or not categoria.estado:
        flash("La categoría seleccionada no es válida.", "warning")
        return redirect(url_for("peliculas"))

    pelicula.nombre = nombre
    pelicula.duracion = duracion
    pelicula.categoria_id = categoria_id

    db.session.commit()

    flash("Película actualizada correctamente.", "success")
    return redirect(url_for("peliculas"))


@app.route("/peliculas/eliminar/<int:pelicula_id>", methods=["POST"])
def eliminar_pelicula(pelicula_id):
    pelicula = db.session.get(Pelicula, pelicula_id)

    if not pelicula:
        flash("La película solicitada no existe.", "danger")
        return redirect(url_for("peliculas"))

    db.session.delete(pelicula)
    db.session.commit()

    flash("Película eliminada correctamente.", "success")
    return redirect(url_for("peliculas"))


@app.route("/series")
def series():
    texto_busqueda = request.args.get("buscar", "").strip()

    consulta = Serie.query.join(Categoria)

    if texto_busqueda:
        patron = f"%{texto_busqueda}%"
        consulta = consulta.filter(
            or_(
                Serie.nombre.like(patron),
                Categoria.nombre.like(patron),
            )
        )

    lista_series = consulta.order_by(Serie.id.desc()).all()

    lista_categorias = Categoria.query.filter_by(
        estado=True
    ).order_by(Categoria.nombre.asc()).all()

    return render_template(
        "series.html",
        series=lista_series,
        categorias=lista_categorias,
        buscar=texto_busqueda,
    )


@app.route("/series/nueva", methods=["POST"])
def crear_serie():
    nombre = request.form.get("nombre", "").strip()
    temporadas = request.form.get("temporadas", type=int)
    categoria_id = request.form.get("categoria_id", type=int)

    if not nombre or not temporadas or not categoria_id:
        flash(
            "El nombre, las temporadas y la categoría son obligatorios.",
            "danger",
        )
        return redirect(url_for("series"))

    if temporadas <= 0:
        flash("La cantidad de temporadas debe ser mayor que cero.", "warning")
        return redirect(url_for("series"))

    categoria = db.session.get(Categoria, categoria_id)

    if not categoria or not categoria.estado:
        flash("La categoría seleccionada no es válida.", "warning")
        return redirect(url_for("series"))

    nueva_serie = Serie(
        nombre=nombre,
        temporadas=temporadas,
        categoria_id=categoria_id,
    )

    db.session.add(nueva_serie)
    db.session.commit()

    flash("Serie agregada correctamente.", "success")
    return redirect(url_for("series"))


@app.route("/series/editar/<int:serie_id>", methods=["POST"])
def editar_serie(serie_id):
    serie = db.session.get(Serie, serie_id)

    if not serie:
        flash("La serie solicitada no existe.", "danger")
        return redirect(url_for("series"))

    nombre = request.form.get("nombre", "").strip()
    temporadas = request.form.get("temporadas", type=int)
    categoria_id = request.form.get("categoria_id", type=int)

    if not nombre or not temporadas or not categoria_id:
        flash(
            "El nombre, las temporadas y la categoría son obligatorios.",
            "danger",
        )
        return redirect(url_for("series"))

    if temporadas <= 0:
        flash("La cantidad de temporadas debe ser mayor que cero.", "warning")
        return redirect(url_for("series"))

    categoria = db.session.get(Categoria, categoria_id)

    if not categoria or not categoria.estado:
        flash("La categoría seleccionada no es válida.", "warning")
        return redirect(url_for("series"))

    serie.nombre = nombre
    serie.temporadas = temporadas
    serie.categoria_id = categoria_id

    db.session.commit()

    flash("Serie actualizada correctamente.", "success")
    return redirect(url_for("series"))


@app.route("/series/eliminar/<int:serie_id>", methods=["POST"])
def eliminar_serie(serie_id):
    serie = db.session.get(Serie, serie_id)

    if not serie:
        flash("La serie solicitada no existe.", "danger")
        return redirect(url_for("series"))

    db.session.delete(serie)
    db.session.commit()

    flash("Serie eliminada correctamente.", "success")
    return redirect(url_for("series"))


if __name__ == "__main__":
    app.run(debug=True)

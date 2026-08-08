from extensions import db


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    estado = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp()
    )